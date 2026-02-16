import os
import shutil
from azure.identity import ClientSecretCredential
from azure.storage.filedatalake import DataLakeServiceClient
from datetime import datetime

# =======================
# Configuration
# =======================

TENANT_ID = "tenand_id",
CLIENT_ID = "client_id",
CLIENT_SECRET = "secret"

ACCOUNT_URL = "https://onelake.dfs.fabric.microsoft.com"
FILE_SYSTEM_NAME = "workspace-id"  # Workspace ID

LANDING_ZONE_PATH = (
    "263f9693-548b-44e3-a59d-dce12e92e5ef/"
    "Files/LandingZone/sensor_data/"
)

LOCAL_FOLDER = r"F:\VS Code\Open Mirroring\parquet_export"
TRACK_FILE = os.path.join(LOCAL_FOLDER, "uploaded_parquet_files.txt")
PROCESSED_FOLDER = r"F:\VS Code\Open Mirroring\parquet_verarbeitet"

# =======================
# AUTH
# =======================
credential = ClientSecretCredential(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
)

service_client = DataLakeServiceClient(
    account_url=ACCOUNT_URL,
    credential=credential
)

file_system_client = service_client.get_file_system_client(FILE_SYSTEM_NAME)

# =======================
# Load files that have already been uploaded
# =======================
if os.path.exists(TRACK_FILE):
    with open(TRACK_FILE, "r") as f:
        uploaded_files = set(line.strip() for line in f.readlines())
else:
    uploaded_files = set()

# =======================
# Upload function
# =======================
def upload_file(local_path, target_path):
    file_client = file_system_client.get_file_client(target_path)
    with open(local_path, "rb") as f:
        file_client.upload_data(f, overwrite=True)
    print(f"✔ Uploaded: {target_path}")

# =======================
# Mainlogic – sort by & only Parquet
# =======================
parquet_files = [f for f in os.listdir(LOCAL_FOLDER) if f.endswith(".parquet")]
parquet_files.sort()

for file_name in parquet_files:
    local_file_path = os.path.join(LOCAL_FOLDER, file_name)

    if file_name not in uploaded_files:
        # Upload
        target_path = LANDING_ZONE_PATH + file_name
        upload_file(local_file_path, target_path)
        uploaded_files.add(file_name)

        # =======================
        # Move to export_verarbeitet/Jahr/Monat
        # =======================
        now = datetime.now()
        year_folder = os.path.join(PROCESSED_FOLDER, str(now.year))
        month_folder = os.path.join(year_folder, f"{now.month:02d}")
        os.makedirs(month_folder, exist_ok=True)

        processed_file_path = os.path.join(month_folder, file_name)
        shutil.move(local_file_path, processed_file_path)
        print(f"📂 Move to : {processed_file_path}")

# =======================
# Update Tracking
# =======================
with open(TRACK_FILE, "w") as f:
    for fname in uploaded_files:
        f.write(fname + "\n")

# =======================
# Tidy up Export-Folder
# =======================
for f in os.listdir(LOCAL_FOLDER):
    file_path = os.path.join(LOCAL_FOLDER, f)
    if os.path.isfile(file_path) and f.endswith(".parquet"):
        os.remove(file_path)
        print(f"🗑 Datei gelöscht: {file_path}")

print("✅ Upload complete – Files move to Export-Files and tidy up.")
