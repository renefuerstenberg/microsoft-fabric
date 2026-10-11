# Power Mix Germany – Real-Time Intelligence with Energy-Charts

Real-time pipeline for German power-grid data in Microsoft Fabric
(workspace "RTI Energy Germany").

```
Energy-Charts API v2 ──> Azure Functions (Python 3.13, Flex Consumption)
                              │  Event Hubs protocol
                              ▼
                     Fabric Eventstream (custom endpoint)
                       │ filter endpoint != "frequency"   │ filter endpoint == "frequency"
                       ▼                                  ▼
               Eventhouse eh_1: energy_raw        Eventhouse eh_1: frequency_raw
                       │                                  │
               MV energy_latest                   MV frequency_1s / frequency_1min
                       └──────────────┬───────────────────┘
                                      ▼
              Real-Time Dashboard "Power Mix Germany" (3 pages)
              Activator "Power Mix Activator" (7 rules)
```

## Azure Functions (`function_app.py`)

| Function | Schedule (UTC) | Data |
|---|---|---|
| EnergyIngest | every 5 min (`30 */5 * * * *`) | public_power (last 6 h), signal (today + forecast), cbpf (yesterday + today) |
| EnergyBackfill | every 3 h (`45 2 */3 * * *`) | public_power + cbpf of the last 3 days, frequency of the last 4 h |
| EnergyPriceIngest | every 15 min (`15 1/15 * * * *`) | day-ahead prices DE-LU, today + tomorrow |
| FrequencyIngest | every minute (`50 * * * * *`) | grid frequency, 1 value per second (30-min window) |

App settings (see `local.settings.json.example`):

| Setting | Default | Meaning |
|---|---|---|
| EVENTSTREAM_CONNECTION_STRING | – (required) | Connection string of the Eventstream custom endpoint (contains EntityPath) |
| ENERGY_COUNTRY | de | Country for public_power / signal / cbpf |
| ENERGY_LOOKBACK_HOURS | 6 | Look-back window of EnergyIngest |
| ENERGY_BACKFILL_DAYS | 3 | Days reloaded by EnergyBackfill |
| ENERGY_BIDDING_ZONE | DE-LU | Bidding zone for prices |
| FREQUENCY_REGION | DE-Freiburg | Measurement point (currently the only one) |
| FREQUENCY_WINDOW_MINUTES | 30 | Overlapping window of FrequencyIngest |
| FREQUENCY_BACKFILL_HOURS | 4 | Frequency hours reloaded by EnergyBackfill |

Deploy: `func azure functionapp publish <function-app-name>`

## KQL scripts (`kql/`)

| File | Content |
|---|---|
| 00_migration_to_english.kql | One-time switch of an existing installation to English names |
| 01_setup_eventhouse.kql | Table energy_raw, MV energy_latest, retention/caching, checks |
| 02_dashboard_grid_live.kql | Dashboard page "Grid Live" (10 tiles) |
| 03_dashboard_prices.kql | Dashboard page "Electricity Prices" (P1–P4 + sources) |
| 04_grid_frequency.kql | Table frequency_raw, MVs, function GridFrequency(), checks, page "Grid Frequency" (F1–F4) |
| 05_activator_alerts.kql | Queries and settings of all 7 Activator rules |

## Known data characteristics

- **Late corrections:** public_power values are corrected for many hours after the first
  publication → EnergyBackfill + MV energy_latest (latest generated_at wins).
- **cbpf:** the most recent quarter-hours are incomplete; Sweden often reports late (0 until
  then) → tiles and alerts use the latest completely reported timestamp.
- **cbpf with ISO start/end** returns HTTP 500 → day format (YYYY-MM-DD) is used.
- **Grid frequency:** the source has a gap (null values, seconds up to about a minute) every
  day shortly before midnight UTC. These seconds are never published.

## Retention

All tables and materialized views: soft delete 36500 days (permanent), recoverability enabled.

## Licences

- Data: Energy-Charts.info – Fraunhofer ISE, CC BY 4.0
- Prices DE-LU: Bundesnetzagentur | SMARD.de, CC BY 4.0
