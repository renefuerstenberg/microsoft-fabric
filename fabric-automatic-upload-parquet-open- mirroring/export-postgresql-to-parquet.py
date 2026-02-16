import os
import pandas as pd
import psycopg2
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone

# ==============================
# CONFIG
# ==============================
OUTPUT_DIR = "parquet_export"
TABLE_NAME = "sensor_data"
CHUNK_ROWS = 100_000  # Zeilen pro Chunk
WATERMARK_FILE = "last_watermark.txt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==============================
# Fabric Schema Definition
# ==============================
FABRIC_SCHEMA = pa.schema([
    pa.field("id", pa.int64(), nullable=False),
    pa.field("house_name", pa.string(), nullable=False),
    pa.field("sensor_path", pa.string(), nullable=False),  # ltree als string
    pa.field("recorded_at", pa.timestamp('ms'), nullable=False),
    pa.field("value_numeric", pa.decimal128(12, 4), nullable=True),
    pa.field("value_text", pa.string(), nullable=True),
    pa.field("__rowMarker__", pa.string(), nullable=False)
])

# ==============================
# Load Watermark
# ==============================
if not os.path.exists(WATERMARK_FILE):
    raise ValueError("No watermark file found. Please create one manually!")

with open(WATERMARK_FILE, "r") as f:
    raw_ts = f.read().strip()
    try:
        # ISO 8601 Format
        last_watermark = datetime.fromisoformat(raw_ts)
    except ValueError:
        # PostgreSQL-Style Format "YYYY-MM-DD HH:MM:SS+00"
        last_watermark = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S%z")

print(f"Last Export unitl: {last_watermark.isoformat()}")

# ==============================
# DB Connection
# ==============================
conn = psycopg2.connect(
    host="localhost",
    dbname="db1",
    user="fabric",
    password="Kennwort1",
    port=5432
)

cur = conn.cursor(name="sensor_cursor")  # server-seitiger Cursor

# ==============================
# Prepare Query
# ==============================
cur.execute(f"""
    SELECT id, house_name, sensor_path::text AS sensor_path,
           recorded_at, value_numeric, value_text
    FROM {TABLE_NAME}
    WHERE recorded_at > %s
    ORDER BY recorded_at ASC
""", (last_watermark,))

# ==============================
# Starting Export
# ==============================
file_counter = 1
max_timestamp = None
export_time_str = datetime.now().strftime("%Y%m%d-%H%M%S")  # Export-Timestamp for Filenames

while True:
    rows = cur.fetchmany(CHUNK_ROWS)
    if not rows:
        break

    df = pd.DataFrame(rows, columns=[desc[0] for desc in cur.description])
    if df.empty:
        continue

    # Remember new max_timestamp
    chunk_max = df["recorded_at"].max()
    if max_timestamp is None or chunk_max > max_timestamp:
        max_timestamp = chunk_max

    #add  __rowMarker__
    df["__rowMarker__"] = "0"
    df = df[[c for c in df.columns if c != "__rowMarker__"] + ["__rowMarker__"]]

    # PyArrow Table with Schema
    table = pa.Table.from_pandas(df, schema=FABRIC_SCHEMA, preserve_index=False)

    #  Write parquet file with timestamp and chunk number
    filename = f"data-export-{export_time_str}-chunk{file_counter}.parquet"
    pq.write_table(table, os.path.join(OUTPUT_DIR, filename), compression="snappy")

    print(f"Written: {filename} ({len(df)} Rows)")
    file_counter += 1

cur.close()
conn.close()

# ==============================
# Update Watermark
# ==============================
if max_timestamp:
    if isinstance(max_timestamp, datetime):
        max_timestamp = max_timestamp.astimezone(timezone.utc)
    with open(WATERMARK_FILE, "w") as f:
        f.write(max_timestamp.isoformat())
    print(f"New watermark saved: {max_timestamp.isoformat()}")
else:
    print("No new data – Watermark remains unchanged.")

print("Export completed.")
