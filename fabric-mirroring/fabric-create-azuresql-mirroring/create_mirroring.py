import requests, json, base64, uuid, time
from notebookutils import mssparkutils

token = mssparkutils.credentials.getToken("pbi")

workspaceId = "00000000-0000-0000-0000-000000000001"
connectionId = "00000000-0000-0000-0000-000000000002"
DATABASE = "azuresqldatabase"


headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

urlCreateMirror = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/mirroredDatabases"

payloadUnencoded = {
    "properties": {
        "source": {
            "type": "AzureSqlDatabase",
            "typeProperties": {
                "connection": connectionId,
                "database": DATABASE
            }
        },
        "target": {
            "type": "MountedRelationalDatabase",
            "typeProperties": {
                "defaultSchema": "SalesLT",
                "format": "Delta",
                "landingZone": {
                    "type": "Managed"
                }
            }
        }
    }
}

b64 = base64.b64encode(json.dumps(payloadUnencoded).encode()).decode()
body = {
    "displayName": f"Mirror Instance {DATABASE}",
    "description": "Mirror created in notebook",
    "definition": {
        "parts": [
            {
                "path": "mirroring.json",
                "payload": b64,
                "payloadType": "InlineBase64"
            }
        ]
    }
}

resp = requests.post(urlCreateMirror, headers=headers, json=body)
print("Status:", resp.status_code)
print("Antwort:", resp.text)
resp.raise_for_status()
mirroredDbId = resp.json()["id"]
print(json.dumps(resp.json(), indent=2))
time.sleep(30)

urlStart = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/mirroredDatabases/{mirroredDbId}/startMirroring"
resp = requests.post(urlStart, headers=headers)
resp.raise_for_status()
time.sleep(60)

urlStatus = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/mirroredDatabases/{mirroredDbId}/getmirroringStatus"
respStatus = requests.post(urlStatus, headers=headers)
print(json.dumps(respStatus.json(), indent=2))


