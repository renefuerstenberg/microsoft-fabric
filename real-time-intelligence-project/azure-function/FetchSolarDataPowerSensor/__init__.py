import pandas as pd
import json
import logging
import azure.functions as func
import os
from azure.eventhub import EventHubProducerClient, EventData

URL = os.getenv("SourceURL")
CONNECTION_STR = os.getenv("EventHubConnectionString")
EVENT_HUB_NAME = os.getenv("EventHubName")

def fetch_table_data(url: str, table_index: int = 3) -> pd.DataFrame:
    try:
        tables = pd.read_html(url)
        return tables[table_index]
    except Exception as e:
        logging.error(f"Fehler beim Laden der Tabelle: {e}")
        return pd.DataFrame()
    
def add_column_to_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if "Modul" not in df.columns:
        df["Modul"] = "Powersensor" 
    return df


def send_to_eventhub(df: pd.DataFrame):
    producer = EventHubProducerClient.from_connection_string(
        conn_str=CONNECTION_STR,
        eventhub_name=EVENT_HUB_NAME
    )
    try:
        batch = producer.create_batch()
        for _, row in df.iterrows():
            json_data = json.dumps(row.to_dict())
            batch.add(EventData(json_data))
        producer.send_batch(batch)
        logging.info("Daten erfolgreich gesendet.")
    except Exception as e:
        logging.error(f"Fehler beim Senden: {e}")
    finally:
        producer.close()

def main(mytimer: func.TimerRequest) -> None:
    logging.info("Funktion gestartet.")
    df = fetch_table_data(URL)
    if not df.empty:
        df= add_column_to_dataframe(df)
        send_to_eventhub(df)
    else:
        logging.warning("Keine Daten gefunden.")
