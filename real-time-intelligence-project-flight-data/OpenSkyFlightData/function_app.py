import json
import logging
import os
from datetime import datetime, timedelta, timezone

import azure.functions as func
import requests
from azure.eventhub import EventData, EventHubProducerClient


app = func.FunctionApp()


# -------------------------------------------------------------------
# Konfiguration
# -------------------------------------------------------------------

OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/"
    "opensky-network/protocol/openid-connect/token"
)

OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"

TOKEN_REFRESH_MARGIN_SECONDS = 30

# Fallback-Wartezeit, falls OpenSky bei HTTP 429 keinen
# auswertbaren Retry-After-Header liefert
DEFAULT_RATE_LIMIT_WAIT_SECONDS = 60

# Rechteckige Bounding Box um Deutschland
# (enthält auch Teile der Nachbarländer)
GERMANY_BOUNDS = {
    "lamin": 47.2,
    "lomin": 5.8,
    "lamax": 55.1,
    "lomax": 15.1,
}

# Zeitpunkt, bis zu dem wegen eines Rate Limits keine Abrufe
# erfolgen sollen (nur im Speicher der aktuellen Instanz)
rate_limited_until = None


def get_required_setting(name: str) -> str:
    """
    Liest eine erforderliche Umgebungsvariable.
    Bricht mit verständlicher Meldung ab, wenn die Variable fehlt.
    """
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Die erforderliche App-Einstellung '{name}' fehlt."
        )

    return value


# -------------------------------------------------------------------
# OpenSky Token Management
# -------------------------------------------------------------------

class TokenManager:
    def __init__(self):
        self.token = None
        self.expires_at = None

    def get_token(self, force_refresh: bool = False) -> str:
        """
        Liefert ein gültiges Access Token.
        Ein bestehendes Token wird wiederverwendet, solange es gültig ist.
        """

        if (
            not force_refresh
            and self.token
            and self.expires_at
            and datetime.now(timezone.utc) < self.expires_at
        ):
            return self.token

        return self._refresh()

    def _refresh(self) -> str:
        """
        Ruft ein neues Access Token über den OAuth2
        Client-Credentials-Flow ab.
        """

        client_id = get_required_setting("OPENSKY_CLIENT_ID")
        client_secret = get_required_setting("OPENSKY_CLIENT_SECRET")

        response = requests.post(
            OPENSKY_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )

        response.raise_for_status()

        token_response = response.json()

        self.token = token_response["access_token"]

        expires_in = int(token_response.get("expires_in", 1800))

        valid_for_seconds = max(
            expires_in - TOKEN_REFRESH_MARGIN_SECONDS,
            1,
        )

        self.expires_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=valid_for_seconds)
        )

        logging.info(
            "Neues OpenSky Access Token geladen. "
            "Gültigkeit: %d Sekunden.",
            expires_in,
        )

        return self.token

    def get_headers(self, force_refresh: bool = False) -> dict:
        return {
            "Authorization": (
                f"Bearer {self.get_token(force_refresh=force_refresh)}"
            ),
            "Accept": "application/json",
        }


tokens = TokenManager()


# -------------------------------------------------------------------
# OpenSky abrufen
# -------------------------------------------------------------------

def get_opensky_states() -> tuple[dict, requests.Response]:
    """
    Ruft aktuelle State Vectors für Deutschland ab.

    Falls OpenSky mit HTTP 401 antwortet, wird das Access Token
    einmal erneuert und der Request wiederholt.
    """

    response = requests.get(
        OPENSKY_STATES_URL,
        headers=tokens.get_headers(),
        params=GERMANY_BOUNDS,
        timeout=45,
    )

    if response.status_code == 401:
        logging.warning(
            "OpenSky Token wurde abgelehnt. Token wird erneuert."
        )

        response = requests.get(
            OPENSKY_STATES_URL,
            headers=tokens.get_headers(force_refresh=True),
            params=GERMANY_BOUNDS,
            timeout=45,
        )

    response.raise_for_status()

    return response.json(), response


# -------------------------------------------------------------------
# OpenSky State Vector transformieren
# -------------------------------------------------------------------

def create_event(response_time, flight: list) -> dict:
    """
    Ordnet das positionsbasierte OpenSky-Array den originalen
    Feldnamen aus der OpenSky-Dokumentation zu.
    """

    if len(flight) < 17:
        raise ValueError(
            f"Ungültiger OpenSky State Vector: "
            f"17 Felder erwartet, {len(flight)} erhalten."
        )

    return {
        "time": response_time,
        "icao24": flight[0],
        "callsign": flight[1],
        "origin_country": flight[2],
        "time_position": flight[3],
        "last_contact": flight[4],
        "longitude": flight[5],
        "latitude": flight[6],
        "baro_altitude": flight[7],
        "on_ground": flight[8],
        "velocity": flight[9],
        "true_track": flight[10],
        "vertical_rate": flight[11],
        "sensors": flight[12],
        "geo_altitude": flight[13],
        "squawk": flight[14],
        "spi": flight[15],
        "position_source": flight[16],
    }


# -------------------------------------------------------------------
# Events an Fabric Eventstream senden
# -------------------------------------------------------------------

def send_to_fabric_eventstream(events: list[dict]) -> int:
    """
    Sendet die Flugzeug-Events über das Event-Hubs-Protokoll
    an den Fabric Eventstream Custom Endpoint.

    Fabric stellt dafür eine Event-Hubs-kompatible
    Connection String bereit.
    """

    connection_string = get_required_setting(
        "FABRIC_EVENTSTREAM_CONNECTION_STRING"
    )

    producer = EventHubProducerClient.from_connection_string(
        conn_str=connection_string
    )

    sent_count = 0

    try:
        batch = producer.create_batch()

        for event in events:
            event_json = json.dumps(
                event,
                ensure_ascii=False,
                separators=(",", ":"),
            )

            event_data = EventData(event_json)

            try:
                batch.add(event_data)

            except ValueError:
                # Aktuellen vollen Batch senden
                if len(batch) > 0:
                    producer.send_batch(batch)
                    sent_count += len(batch)

                # Neuen Batch für das aktuelle Event erstellen
                batch = producer.create_batch()
                batch.add(event_data)

        # Letzten noch nicht gesendeten Batch übertragen
        if len(batch) > 0:
            producer.send_batch(batch)
            sent_count += len(batch)

    finally:
        producer.close()

    return sent_count


# -------------------------------------------------------------------
# Azure Function Timer Trigger
# -------------------------------------------------------------------

@app.timer_trigger(
    schedule="0 * * * * *",
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=True,
)
def OpenSkyIngest(mytimer: func.TimerRequest) -> None:
    """
    Wird jede Minute aufgerufen:

    OpenSky
      -> State Vectors Deutschland
      -> JSON-Events
      -> Fabric Eventstream Custom Endpoint
    """

    global rate_limited_until

    if mytimer.past_due:
        logging.warning("Die Timer-Ausführung ist verspätet.")

    # Bei aktivem Rate Limit keine weiteren Credits verbrauchen
    if (
        rate_limited_until
        and datetime.now(timezone.utc) < rate_limited_until
    ):
        logging.info(
            "Rate Limit aktiv bis %s. Lauf wird übersprungen.",
            rate_limited_until.isoformat(),
        )
        return

    try:
        data, response = get_opensky_states()

        states = data.get("states") or []
        response_time = data.get("time")

        credits_remaining = response.headers.get(
            "X-Rate-Limit-Remaining"
        )

        retry_after = response.headers.get(
            "X-Rate-Limit-Retry-After-Seconds"
        )

        logging.info("OpenSky HTTP Status: %s", response.status_code)
        logging.info("OpenSky Response Time: %s", response_time)
        logging.info("Gefundene Flugzeuge: %d", len(states))
        logging.info(
            "Verbleibende OpenSky Credits: %s",
            credits_remaining,
        )

        if retry_after:
            logging.warning(
                "OpenSky Retry After: %s Sekunden",
                retry_after,
            )

        if not states:
            logging.info(
                "OpenSky hat aktuell keine Flugzeuge "
                "für die Bounding Box geliefert."
            )
            return

        events = []

        for flight in states:
            try:
                event = create_event(response_time, flight)
                events.append(event)

            except (IndexError, ValueError, TypeError):
                logging.exception(
                    "Ein OpenSky State Vector konnte "
                    "nicht verarbeitet werden."
                )

        if not events:
            logging.warning(
                "Es wurden keine gültigen Events erstellt."
            )
            return

        sent_count = send_to_fabric_eventstream(events)

        logging.info(
            "%d Events wurden an den Fabric Eventstream gesendet.",
            sent_count,
        )

        # Nur eine kleine Vorschau ausgeben
        for event in events[:3]:
            logging.info(
                "Beispiel: %s | Lat=%s | Lon=%s | Alt=%s",
                (
                    event["callsign"].strip()
                    if event["callsign"]
                    else "N/A"
                ),
                event["latitude"],
                event["longitude"],
                event["baro_altitude"],
            )

    except requests.HTTPError as error:
        err_response = error.response

        status_code = (
            err_response.status_code
            if err_response is not None
            else "unbekannt"
        )

        # Rate Limit: Retry-After auslesen, Pause merken, sauber beenden
        if status_code == 429:
            retry_after = err_response.headers.get(
                "X-Rate-Limit-Retry-After-Seconds"
            )

            try:
                wait_seconds = int(retry_after)
            except (TypeError, ValueError):
                wait_seconds = DEFAULT_RATE_LIMIT_WAIT_SECONDS

            rate_limited_until = (
                datetime.now(timezone.utc)
                + timedelta(seconds=wait_seconds)
            )

            logging.warning(
                "OpenSky Rate Limit erreicht (HTTP 429). "
                "Retry After: %s Sekunden. "
                "Weitere Abrufe pausieren bis %s.",
                retry_after or "unbekannt",
                rate_limited_until.isoformat(),
            )
            return

        response_text = (
            err_response.text[:1000]
            if err_response is not None
            else str(error)
        )

        logging.error(
            "OpenSky HTTP-Fehler. Status=%s, Antwort=%s",
            status_code,
            response_text,
        )

        raise

    except Exception:
        logging.exception(
            "OpenSky-Ingestion oder Fabric-Übertragung fehlgeschlagen."
        )

        raise

@app.timer_trigger(schedule="0 * * * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=False) 
def FlightRadarIngest(myTimer: func.TimerRequest) -> None:
    
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function executed.')