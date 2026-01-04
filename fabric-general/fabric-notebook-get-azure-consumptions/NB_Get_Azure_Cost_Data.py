

import requests
import pandas as pd
import json
import time
from datetime import datetime, timedelta
import os

headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

body = {
    "metric": "ActualCost",
    "timePeriod": {
        "start": "2025-02-01",
        "end": "2025-02-28"
    }
}


url = f"https://management.azure.com/subscriptions/{microsoft_subscription_id}/providers/Microsoft.CostManagement/generateCostDetailsReport?api-version=2022-05-01"

# Schritt 1: Create a Report

response = requests.post(url, headers=headers, json=body)

print(response)

# Schritt 2: Read Report and save to Lakehouse

check_response = requests.get(response.headers["location"], headers=headers)

print (check_response)

if check_response.status_code == 200:
            response_dict = check_response.json()
            if 'manifest' in response_dict and 'blobs' in response_dict['manifest'] and len(response_dict['manifest']['blobs']) > 0:
                blob_link = response_dict['manifest']['blobs'][0]['blobLink']

                # Read CSV
                csv_df = pd.read_csv(blob_link, low_memory=False)

                spark_df = spark.read.option("header","true").csv(blob_link)

                 
                # Set Path
                filename = "AzureConsumption.csv"
                path = f"{LakehousePathActualCost}/{filename}"

                # Write File into Lakehouse and save to Path
                os.makedirs(os.path.dirname(path), exist_ok=True)
                csv_df.to_csv(path, index=False)
                print(f"Datei gespeichert: {path}")



else:
    print("Das ist nur eine Übung und du musst es nochmal versuchen")



