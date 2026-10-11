import json
import logging
import os
from datetime import datetime, timedelta, timezone

import azure.functions as func
import requests
from azure.eventhub import EventData, EventHubProducerClient

app = func.FunctionApp()

FR24_LIVE_URL = "https://fr24api.flightradar24.com/api/live/flight-positions/full"

GERMANY_BOUNDS = {
    "lamin": 47.2,
    "lomin": 5.8,
    "lamax": 55.1,
    "lomax": 15.1,
}

# Flightradar24 erwartet die Reihenfolge: north,south,west,east
FR24_BOUNDS = (
    f"{GERMANY_BOUNDS['lamax']},{GERMANY_BOUNDS['lamin']},"
    f"{GERMANY_BOUNDS['lomin']},{GERMANY_BOUNDS['lomax']}"
)

# Schutz vor versehentlichem Mehrfachaufruf (jeder Abruf kostet 160 Credits)
SPERRE = timedelta(hours=1)
letzter_abruf: datetime | None = None


def hole_fr24_deutschland() -> list[dict]:
    """Ein einziger Request für die ganze Deutschland-Box."""
    response = requests.get(
        FR24_LIVE_URL,
        headers={
            "Authorization": f"Bearer {os.environ['FR24_API_TOKEN']}",
            "Accept": "application/json",
            "Accept-Version": "v1",
        },
        params={"bounds": FR24_BOUNDS},
        timeout=60,
    )
    response.raise_for_status()
    return response.json().get("data", [])


def sende_an_eventstream(events: list[dict]) -> int:
    producer = EventHubProducerClient.from_connection_string(
        conn_str=os.environ["FABRIC_EVENTSTREAM_FR24_CONNECTION_STRING"]
    )

    gesendet = 0

    try:
        batch = producer.create_batch()

        for event in events:
            data = EventData(
                json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            )
            try:
                batch.add(data)
            except ValueError:
                producer.send_batch(batch)
                gesendet += len(batch)
                batch = producer.create_batch()
                batch.add(data)

        if len(batch) > 0:
            producer.send_batch(batch)
            gesendet += len(batch)
    finally:
        producer.close()

    return gesendet


@app.route(route="fr24deutschland", auth_level=func.AuthLevel.ANONYMOUS)
def fr24deutschland(req: func.HttpRequest) -> func.HttpResponse:
    global letzter_abruf

    jetzt = datetime.now(timezone.utc)

    # Zweiter Aufruf innerhalb einer Stunde nur mit ?force=1
    if (
        letzter_abruf
        and jetzt - letzter_abruf < SPERRE
        and req.params.get("force") != "1"
    ):
        return func.HttpResponse(
            "Der letzte Abruf war vor weniger als einer Stunde. "
            "Mit ?force=1 trotzdem abrufen (kostet erneut Credits).",
            status_code=429,
        )

    fluege = hole_fr24_deutschland()
    letzter_abruf = jetzt

    logging.info("FR24: %d Flüge für Deutschland abgerufen.", len(fluege))

    if not fluege:
        return func.HttpResponse("Flightradar24 hat keine Flüge geliefert.")

    abgerufen_am = jetzt.isoformat()
    events = [{**flug, "abgerufen_am": abgerufen_am} for flug in fluege]

    gesendet = sende_an_eventstream(events)

    # Kontrolle: Liegen die Flüge wirklich in der Deutschland-Box?
    lats = [f["lat"] for f in fluege if f.get("lat") is not None]
    lons = [f["lon"] for f in fluege if f.get("lon") is not None]

    return func.HttpResponse(
        f"{len(fluege)} Flüge abgerufen, {gesendet} Events gesendet. "
        f"Lat {min(lats):.1f} bis {max(lats):.1f}, "
        f"Lon {min(lons):.1f} bis {max(lons):.1f}."
    )