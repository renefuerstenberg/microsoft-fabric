import os
from azure.identity import ClientSecretCredential
from azure.storage.filedatalake import DataLakeServiceClient

# =======================
# CONFIGURATION
# =======================

TENANT_ID = "tenand_id"  # Replace with actual Tenant ID
CLIENT_ID = "client_id"  # Replace with actual Client ID
CLIENT_SECRET = "client_secret"  # Replace with actual Client Secret

ACCOUNT_URL = "https://onelake.dfs.fabric.microsoft.com"

# IMPORTANT:
FILE_SYSTEM_NAME = "f7624f8d-c8f4-4aaf-90c3-1270d5c37943"  # Workspace ID

LANDING_ZONE_PATH = (
    "263f9693-548b-44e3-a59d-dce12e92e5ef/"
    "Files/LandingZone/sensor_data/"
)

LOCAL_FOLDER = r"F:\Python\Export sensor_data\parquet_export"
TRACK_FILE = os.path.join(LOCAL_FOLDER, "uploaded_parquet_files.txt")

# =======================
# AUTHENTICATION
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
# Load already uploaded files
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
# Main logic – sorted & Parquet only
# =======================

# Collect only Parquet files
parquet_files = [
    f for f in os.listdir(LOCAL_FOLDER)
    if f.endswith(".parquet")
]

# Sort numerically (important for Open Mirroring)
parquet_files.sort()

for file_name in parquet_files:
    local_file_path = os.path.join(LOCAL_FOLDER, file_name)

    if file_name not in uploaded_files:
        target_path = LANDING_ZONE_PATH + file_name
        upload_file(local_file_path, target_path)
        uploaded_files.add(file_name)

# Update tracking
with open(TRACK_FILE, "w") as f:
    for fname in uploaded_files:
        f.write(fname + "\n")

print("✅ Upload completed – files uploaded in correct order.")

