# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "205682f8-a562-4f91-8f11-3c18ac1009b6",
# META       "default_lakehouse_name": "lakehouse_bronze",
# META       "default_lakehouse_workspace_id": "d7945fe0-0895-4697-94d2-ed9af544ebb1",
# META       "known_lakehouses": [
# META         {
# META           "id": "205682f8-a562-4f91-8f11-3c18ac1009b6"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Import Libraries

# CELL ********************

from datetime import datetime
import traceback

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# # Get Secrets from Azure Key Vault #

# CELL ********************

connection_id = "e0015372-2f36-407d-a8f3-8aa85491a4b8"


app_tenant_id = notebookutils.credentials.getSecretWithConnection(connection_id, "App-Tenant-Id")    
app_client_id = notebookutils.credentials.getSecretWithConnection(connection_id, "App-Client-Id")
app_secret = notebookutils.credentials.getSecretWithConnection(connection_id, "App-Secret")
fabric_sql = notebookutils.credentials.getSecretWithConnection(connection_id, "Fabric-SQL")
fabric_database = notebookutils.credentials.getSecretWithConnection(connection_id, "Fabric-Database")      

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# # Logging Notebook function

# CELL ********************

# Logging Setup – JDBC Fabric SQL with ActiveDirectoryInteractive

# ---------------- Runtime-Parameter ----------------
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
NOTEBOOK_NAME = "Notebook_Load_Parquet"
SQL_TABLE    = "dbo.notebook_logs"

# ---------------- Logging Function ----------------
def log(level, message):
    """Logs message to console and to Fabric SQL via JDBC"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Console
    print(f"{timestamp} | {level:<8} | {RUN_ID} | {NOTEBOOK_NAME} | {message}")

    try:
        # DataFrame for individual log entry
        log_df = spark.createDataFrame([
            (timestamp, level, RUN_ID, NOTEBOOK_NAME, message)
        ], schema=["log_timestamp", "log_level", "custom_run_id", "notebook_name", "message"])
        
        # JDBC URL with ActiveDirectoryInteractive
        jdbc_url = (
        f"jdbc:{fabric_sql};"
        f"database={fabric_database};"
        "encrypt=true;"
        "trustServerCertificate=false;"
        "authentication=ActiveDirectoryServicePrincipal;"
        f"user={app_client_id}@{app_tenant_id};"
        f"password={app_secret}"
)
        
        # Write Log in SQL Table #
        log_df.write \
            .format("jdbc") \
            .option("url", jdbc_url) \
            .option("dbtable", SQL_TABLE) \
            .option("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver") \
            .mode("append") \
            .save()
    except Exception as e:
        print(f"DB logging failed: {str(e)}")
        print(traceback.format_exc())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# # Read Parquet Files from lakehouse_bronze and write Logging to Fabric SQL Database

# CELL ********************

# ============================================================
# Start Process
# ============================================================

start_time = datetime.now()
file_path = "Files/parquet_upload"

try:
    log("INFO", "Notebook started")
    log("INFO", f"Read File: {file_path}")


    # --------------------------------------------------------
    # Parquet Spark Load
    # --------------------------------------------------------
    spark_df = spark.read.option("recursiveFileLookup", "true").parquet(file_path)
    log("INFO", "File loaded successfully")

    # Count Parquet Files
    num_files = len(spark_df.inputFiles())
    log("INFO", f"Number of Parquet files read: {num_files}")

    row_count = spark_df.count()
    col_count = len(spark_df.columns)

    log("METRIC", f"Rows: {row_count}")
    log("METRIC", f"Columns: {col_count}")

    # --------------------------------------------------------
    # Schema Logging
    # --------------------------------------------------------
    log("DEBUG", f"Columnnames: {spark_df.columns}")
    log("DEBUG", f"Datatypes: {[(f.name, str(f.dataType)) for f in spark_df.schema.fields]}")

    # --------------------------------------------------------
    # Measure running time
    # --------------------------------------------------------
    duration = datetime.now() - start_time
    log("METRIC", f"Total duration: {duration} Seconds")

    log("INFO", "Notebook Cell successfully completed")

except Exception as e:
    log("ERROR", f"Notebook error: {str(e)}")
    print(traceback.format_exc())

    duration = datetime.now() - start_time
    log("METRIC", f"Runtime until error: {duration} Seconds")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# # Write Dataframe to Tables/StagingSensorData Table and write Logging to Fabric SQL Database

# CELL ********************

# ============================================================
# Delta Write with Logging and Error Handling
# ============================================================

delta_table_path_sensor_data = "Tables/StagingSensorData"

try:
    # Info + metric before writing
    log("INFO", f"Starting write of Sensor DataFrame to Delta: {delta_table_path_sensor_data}")
    log("METRIC", f"Rows in DataFrame: {spark_df.count()} | Columns: {len(spark_df.columns)}")

    # Write to Delta
    spark_df.write.format("delta").mode("overwrite").save(delta_table_path_sensor_data)

    # Success log
    log("INFO", f"DataFrame successfully written to Delta: {delta_table_path_sensor_data}")

except Exception as e:
    # Error log
    log("ERROR", f"Error writing to Delta: {str(e)}")
    import traceback
    print(traceback.format_exc())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
