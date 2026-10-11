"""
EnergyIngest – Azure Functions app (Python, programming model v2)

Pulls German power-grid data from the Energy-Charts API v2 (Fraunhofer ISE)
and sends it as JSON events to a Microsoft Fabric Eventstream (custom
endpoint, Event Hubs protocol). The Eventstream routes the events into the
Eventhouse eh_1 (tables energy_raw and frequency_raw).

Functions in this app (all timer triggers, schedules in UTC):
  - EnergyIngest       every 5 min   public_power, signal, cbpf
  - EnergyBackfill     every 3 h     reloads public_power + cbpf (last 3 days)
                                     and frequency (last 4 h) to pick up late
                                     corrections and close gaps
  - EnergyPriceIngest  every 15 min  day-ahead prices DE-LU (today + tomorrow)
  - FrequencyIngest    every minute  grid frequency, 1 value per second

API endpoints used:
  - /v2/public_power  Net public power generation per source (MW, 15-min grid)
  - /v2/signal        Renewable share of load + traffic light incl. forecast
  - /v2/cbpf          Cross-border physical flows per neighbour country (GW)
  - /v2/price         Day-ahead price per bidding zone (EUR/MWh)
  - /v2/frequency     Grid frequency, measured in Freiburg (Hz, 1 s)

Rate limit according to the API: 2 requests/min per endpoint (signal 20/min).
HTTP 429 responses carry a Retry-After header, which is honoured.

Every single value becomes one event (long format). Deduplication of later
API corrections happens in the Eventhouse (materialized views energy_latest
and frequency_1s).

Data source: Energy-Charts.info, licence CC BY 4.0.
Prices DE-LU: Bundesnetzagentur | SMARD.de, licence CC BY 4.0.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import azure.functions as func
import requests
from azure.eventhub import EventData, EventHubProducerClient

app = func.FunctionApp()

# Suppress the verbose connection logs of the Event Hubs SDK
logging.getLogger("azure").setLevel(logging.WARNING)

API_BASE_URL = "https://api.energy-charts.info"
COUNTRY = os.getenv("ENERGY_COUNTRY", "de")
# How far back every EnergyIngest run queries. Chosen generously so that
# quarter-hours filled in or corrected later are picked up again.
LOOKBACK_HOURS = int(os.getenv("ENERGY_LOOKBACK_HOURS", "6"))
HTTP_TIMEOUT = 30
MAX_RETRY_AFTER_SECONDS = 60  # Longer waits are skipped until the next run
USER_AGENT = "EnergyIngest/1.0 (Fabric RTI)"
LOCAL_TZ = ZoneInfo("Europe/Berlin")  # The API's day format refers to local time

# Endpoint -> type of time range
#   "timestamp": start/end as ISO timestamp (UTC)
#   "days":      start/end in day format (YYYY-MM-DD, local time) – cbpf
#                currently returns HTTP 500 for ISO timestamps
#   "none":      no time range (API returns today, or today + forecast)
ENDPOINTS = {
    "public_power": "timestamp",
    "signal": "none",
    "cbpf": "days",
}


# ---------------------------------------------------------------------------
# HTTP request with 429 / Retry-After handling
# ---------------------------------------------------------------------------
def fetch_api(session: requests.Session, endpoint: str, params: dict) -> dict | None:
    """Calls a v2 endpoint. Returns None if no data is available or the
    request was not possible in this run."""
    url = f"{API_BASE_URL}/v2/{endpoint}"

    for attempt in range(1, 3):
        try:
            response = session.get(url, params=params, timeout=HTTP_TIMEOUT)
        except requests.RequestException as error:
            logging.warning("Network error for %s (attempt %d): %s", endpoint, attempt, error)
            time.sleep(5)
            continue

        if response.status_code == 200:
            return response.json()

        if response.status_code == 404:
            logging.info("No data for %s with %s", endpoint, params)
            return None

        if response.status_code == 429:
            wait = _retry_after_seconds(response)
            if wait > MAX_RETRY_AFTER_SECONDS:
                logging.warning("%s: rate limit, Retry-After %ds – skipping until next run",
                                endpoint, wait)
                return None
            logging.info("%s: rate limit, waiting %ds (attempt %d)", endpoint, wait, attempt)
            time.sleep(wait)
            continue

        if 500 <= response.status_code < 600:
            logging.warning("%s: server error %d (attempt %d)", endpoint, response.status_code, attempt)
            time.sleep(5)
            continue

        # 400/422 etc.: parameter error, retrying will not help
        logging.error("%s: HTTP %d – %s", endpoint, response.status_code, response.text[:300])
        return None

    logging.error("%s: request failed after retries", endpoint)
    return None


def _retry_after_seconds(response: requests.Response) -> int:
    value = response.headers.get("Retry-After", "")
    try:
        return max(1, int(float(value)))
    except ValueError:
        return 30  # Fallback if the header is missing or contains a date


# ---------------------------------------------------------------------------
# Conversion: v2 envelope -> events in long format
# ---------------------------------------------------------------------------
def _to_utc_iso(timestamp: str) -> str:
    """ISO 8601 with offset (local time) -> UTC in the format ...Z."""
    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def envelope_to_events(envelope: dict) -> list[dict]:
    """Flattens a v2 response: one event per (timestamp, series) with a value."""
    endpoint = envelope.get("endpoint", "")
    country = envelope.get("country") or COUNTRY
    default_unit = envelope.get("unit")
    generated_at = _to_utc_iso(envelope["generated_at"])
    generated_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))

    series_by_id = {s["id"]: s for s in envelope.get("series", [])}

    events = []
    for record in envelope.get("data", []):
        ts = _to_utc_iso(record["timestamp"])
        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        for series_id, value in (record.get("values") or {}).items():
            if value is None:
                continue  # not available yet – will arrive in a later run
            series = series_by_id.get(series_id, {})
            events.append({
                "endpoint": endpoint,
                "country": country,
                "ts": ts,
                "series_id": series_id,
                "series_name": series.get("name", series_id),
                "value": float(value),
                "unit": series.get("unit") or default_unit,
                "is_forecast": ts_dt > generated_dt,
                "generated_at": generated_at,
            })
    return events


# ---------------------------------------------------------------------------
# Sending to the Fabric Eventstream
# ---------------------------------------------------------------------------
def send_to_eventstream(events: list[dict]) -> int:
    if not events:
        return 0

    producer = EventHubProducerClient.from_connection_string(
        conn_str=os.environ["EVENTSTREAM_CONNECTION_STRING"],
        # The event hub name is already included as EntityPath in the connection string
    )
    sent = 0
    with producer:
        batch = producer.create_batch()
        for event in events:
            data = EventData(json.dumps(event))
            try:
                batch.add(data)
            except ValueError:
                # Batch full -> send it and start a new one
                producer.send_batch(batch)
                sent += len(batch)
                batch = producer.create_batch()
                batch.add(data)
        if len(batch) > 0:
            producer.send_batch(batch)
            sent += len(batch)
    return sent


# ---------------------------------------------------------------------------
# EnergyIngest – main timer function (every 5 minutes)
# ---------------------------------------------------------------------------
# Second 30 instead of 0 so the run does not collide with the OpenSky function.
@app.timer_trigger(schedule="30 */5 * * * *", arg_name="timer",
                   run_on_startup=False, use_monitor=True)
def EnergyIngest(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("EnergyIngest is running late")

    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=LOOKBACK_HOURS)).strftime("%Y-%m-%dT%H:%MZ")
    end = now.strftime("%Y-%m-%dT%H:%MZ")
    # Day format in local time: always yesterday + today. cbpf is sometimes
    # published 5 h+ late, so the late part of the previous day is not lost.
    today = now.astimezone(LOCAL_TZ).date()
    start_day = (today - timedelta(days=1)).isoformat()
    end_day = today.isoformat()

    all_events: list[dict] = []
    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        for endpoint, range_type in ENDPOINTS.items():
            params = {"country": COUNTRY}
            if range_type == "timestamp":
                params.update({"start": start, "end": end})
            elif range_type == "days":
                params.update({"start": start_day, "end": end_day})

            envelope = fetch_api(session, endpoint, params)
            if envelope is None and range_type == "days":
                # Fallback: today only. The previous day may then be missing for
                # this run, but it is fetched again on the next successful run
                # and in any case by EnergyBackfill.
                logging.warning("%s: request for day range %s..%s failed – "
                                "falling back to today", endpoint, start_day, end_day)
                envelope = fetch_api(session, endpoint, {"country": COUNTRY})
            if envelope is None:
                continue
            if envelope.get("deprecated"):
                logging.warning("Endpoint %s is marked as deprecated", endpoint)

            events = envelope_to_events(envelope)
            logging.info("%s: %d values (available until %s)",
                         endpoint, len(events), envelope.get("available_until"))
            all_events.extend(events)

    sent = send_to_eventstream(all_events)
    logging.info("EnergyIngest finished: %d events sent to Eventstream", sent)


# ---------------------------------------------------------------------------
# EnergyBackfill – reload for late corrections (every 3 hours)
# ---------------------------------------------------------------------------
# Energy-Charts keeps correcting public_power values for many hours after
# the first publication (measured: corrections beyond 6 h). EnergyIngest only
# covers the last ENERGY_LOOKBACK_HOURS, so this function reloads the last
# BACKFILL_DAYS days completely every 3 hours. energy_latest automatically
# takes the newest version (higher generated_at).
# It also reloads the grid frequency of the last FREQ_BACKFILL_HOURS hours
# to close gaps caused by restarts or outages of FrequencyIngest.
BACKFILL_DAYS = int(os.getenv("ENERGY_BACKFILL_DAYS", "3"))
BACKFILL_ENDPOINTS = ["public_power", "cbpf"]


# Minute 2, second 45: not at the same time as EnergyIngest (minute 0/5, second 30)
@app.timer_trigger(schedule="45 2 */3 * * *", arg_name="timer",
                   run_on_startup=False, use_monitor=True)
def EnergyBackfill(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("EnergyBackfill is running late")

    today = datetime.now(timezone.utc).astimezone(LOCAL_TZ).date()
    start_day = (today - timedelta(days=BACKFILL_DAYS - 1)).isoformat()
    end_day = today.isoformat()

    all_events: list[dict] = []
    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        for endpoint in BACKFILL_ENDPOINTS:
            params = {"country": COUNTRY, "start": start_day, "end": end_day}
            envelope = fetch_api(session, endpoint, params)
            if envelope is None:
                logging.warning("EnergyBackfill: %s %s..%s failed – next attempt in 3 h",
                                endpoint, start_day, end_day)
                continue
            events = envelope_to_events(envelope)
            logging.info("EnergyBackfill %s: %d values (%s..%s)",
                         endpoint, len(events), start_day, end_day)
            all_events.extend(events)

        # Reload the grid frequency of the last hours (repairs longer outages)
        now = datetime.now(timezone.utc)
        params = {"region": FREQ_REGION,
                  "start": (now - timedelta(hours=FREQ_BACKFILL_HOURS)).strftime("%Y-%m-%dT%H:%MZ"),
                  "end": now.strftime("%Y-%m-%dT%H:%MZ")}
        envelope = fetch_api(session, "frequency", params)
        if envelope is None:
            logging.warning("EnergyBackfill: frequency failed – next attempt in 3 h")
        else:
            events = _frequency_events(envelope)
            logging.info("EnergyBackfill frequency: %d second values (last %d h)",
                         len(events), FREQ_BACKFILL_HOURS)
            all_events.extend(events)

    sent = send_to_eventstream(all_events)
    logging.info("EnergyBackfill finished: %d events sent to Eventstream", sent)


# ---------------------------------------------------------------------------
# EnergyPriceIngest – day-ahead electricity prices (every 15 minutes)
# ---------------------------------------------------------------------------
# Exchange price of the day-ahead auction (EPEX) in EUR/MWh, 15-min grid.
# Tomorrow's prices are published daily at around 13:00 local time, so
# today + tomorrow is queried every 15 minutes – once the auction result is
# published, tomorrow's prices are in the Eventhouse at most 15 minutes later.
# Licence DE-LU: CC BY 4.0, Bundesnetzagentur | SMARD.de
BIDDING_ZONE = os.getenv("ENERGY_BIDDING_ZONE", "DE-LU")


# Minute 1/16/31/46, second 15: offset from EnergyIngest and EnergyBackfill
@app.timer_trigger(schedule="15 1/15 * * * *", arg_name="timer",
                   run_on_startup=False, use_monitor=True)
def EnergyPriceIngest(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("EnergyPriceIngest is running late")

    today = datetime.now(timezone.utc).astimezone(LOCAL_TZ).date()
    tomorrow = today + timedelta(days=1)

    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        # /price has no "country" parameter but the bidding zone "bzn"
        envelope = fetch_api(session, "price",
                             {"bzn": BIDDING_ZONE, "start": today.isoformat(),
                              "end": tomorrow.isoformat()})
        if envelope is None:
            logging.warning("EnergyPriceIngest: request today+tomorrow failed – falling back to today")
            envelope = fetch_api(session, "price", {"bzn": BIDDING_ZONE})
        if envelope is None:
            return

    events = envelope_to_events(envelope)
    for event in events:
        event["endpoint"] = "price"
        # Auction results are fixed prices, not a forecast
        event["is_forecast"] = False
    logging.info("EnergyPriceIngest: %d prices (available until %s, licence: %s)",
                 len(events), envelope.get("available_until"), envelope.get("license"))

    sent = send_to_eventstream(events)
    logging.info("EnergyPriceIngest finished: %d events sent to Eventstream", sent)


# ---------------------------------------------------------------------------
# FrequencyIngest – grid frequency in seconds (every minute)
# ---------------------------------------------------------------------------
# Grid frequency of the Continental European synchronous grid, measured at
# Fraunhofer ISE in Freiburg, 1 value per second (Hz). Queried every minute
# with an overlapping window (default 30 min). Every second already sent is
# remembered in the instance's memory and skipped; seconds that the API
# delivers late are therefore still captured. After a restart the whole
# window is sent again – duplicates are removed by frequency_1s.
# Longer outages are repaired by EnergyBackfill (last 4 h, every 3 h).
# Note: the source itself has a short gap (null values) every day shortly
# before midnight UTC; those seconds are never published and cannot be loaded.
FREQ_REGION = os.getenv("FREQUENCY_REGION", "DE-Freiburg")
FREQ_WINDOW_MINUTES = int(os.getenv("FREQUENCY_WINDOW_MINUTES", "30"))
FREQ_BACKFILL_HOURS = int(os.getenv("FREQUENCY_BACKFILL_HOURS", "4"))
_freq_sent: set[str] = set()


def _frequency_events(envelope: dict) -> list[dict]:
    """v2 response of /frequency -> events in the standard format (endpoint=frequency)."""
    events = []
    for event in envelope_to_events(envelope):
        event["endpoint"] = "frequency"
        event["is_forecast"] = False
        event["unit"] = event.get("unit") or "Hz"
        events.append(event)
    return events


# Every minute, second 50: offset from the other functions
@app.timer_trigger(schedule="50 * * * * *", arg_name="timer",
                   run_on_startup=False, use_monitor=True)
def FrequencyIngest(timer: func.TimerRequest) -> None:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=FREQ_WINDOW_MINUTES)
    start = window_start.strftime("%Y-%m-%dT%H:%MZ")
    end = (now + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%MZ")

    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        envelope = fetch_api(session, "frequency",
                             {"region": FREQ_REGION, "start": start, "end": end})
    if envelope is None:
        return

    events = [e for e in _frequency_events(envelope) if e["ts"] not in _freq_sent]

    sent = send_to_eventstream(events)
    _freq_sent.update(e["ts"] for e in events)
    # Limit the in-memory cache to the current window
    cutoff = (window_start - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _freq_sent.difference_update({t for t in _freq_sent if t < cutoff})
    logging.info("FrequencyIngest: %d new second values sent (available until %s)",
                 sent, envelope.get("available_until"))
