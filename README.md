# Microsoft Fabric

## Repository Summary

This repository demonstrates how to collect, process, and analyze real-time energy and device telemetry using Microsoft Fabric and Azure serverless technologies. It contains a Real-Time Intelligence project that shows patterns for integrating IoT devices, sensors, and energy systems into a unified analytics workflow.

Key highlights:
- Serverless data collection using Azure Functions written in Python
- Real-time ingestion and processing patterns for telemetry data
- Integration-ready structure for Microsoft Fabric analytics and dashboards

The repository is intended as a reference implementation and starting point for building scalable, secure, and maintainable solutions that feed into Microsoft Fabric for monitoring, reporting, and AI-driven insights.

See the `real-time-intelligence-project/azure-function/README.md` for details about the Azure Functions and how to run or deploy them locally and to Azure.

## Structure

Top-level layout:

```
microsoft-fabric/
├── README.md
└── real-time-intelligence-project/
    └── azure-function/
        ├── host.json
        ├── local.settings.json
        ├── requirements.txt
        ├── FetchSolarDataBattery/
        ├── FetchSolarDataInverter/
        ├── FetchSolarDataIotEdgeDevice/
        ├── FetchSolarDataPowerSensor/
        ├── FetchSolarDataSiteData/
        └── FetchSolarDataWallbox/
```

## Getting Started

1. Open `real-time-intelligence-project/azure-function/README.md` for setup instructions.
2. Install Python dependencies and Azure Functions Core Tools to run functions locally.
3. Configure `local.settings.json` with required connection strings and keys for local testing.

## Contributing

Contributions are welcome — please follow the repository's structure, run and test changes locally, and update documentation accordingly.

## License

Add license information here.
# microsoft-fabric