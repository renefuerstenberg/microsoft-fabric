# energy-ingest – Azure Function App

Python Function App that polls the Energy-Charts API and sends the data to the Fabric
Eventstream *PowerMix Stream*. Full project documentation: [../Readme.md](../Readme.md).

| Function | Schedule (UTC) | Data |
|---|---|---|
| EnergyIngest | every 5 min | public_power, signal, cbpf |
| EnergyBackfill | every 3 h | public_power + cbpf (last 3 days), frequency (last 9 h) |
| EnergyPriceIngest | every 15 min | day-ahead prices DE-LU (today + tomorrow) |
| FrequencyIngest | every minute | grid frequency per second |

## Run locally

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp local.settings.json.example local.settings.json   # add EVENTSTREAM_CONNECTION_STRING
func start
```

Start one function manually:

```bash
curl -X POST http://localhost:7071/admin/functions/EnergyBackfill \
     -H "Content-Type: application/json" -d '{}'
```

## Deploy

```bash
az login
func azure functionapp publish <function-app-name>
```

Then check **Function App → Log stream**, e.g.
`FrequencyIngest: 60 new second values sent (available until …)`.

## Settings

Only `EVENTSTREAM_CONNECTION_STRING` is required. All other settings have defaults in the
code – see `local.settings.json.example` and the table in [../Readme.md](../Readme.md#configuration-app-settings).

`local.settings.json` contains the connection string and must never be committed
(it is listed in `.gitignore`).
