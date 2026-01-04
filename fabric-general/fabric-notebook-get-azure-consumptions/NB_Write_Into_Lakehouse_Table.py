


# Convert Pandas DataFrame to Spark DataFrame
spark_df = spark.createDataFrame(csv_df)

# Write to Delta Table
delta_table_path = "Tables/AzureConsumption"
spark_df.write.format("delta").mode("overwrite").save(delta_table_path)

