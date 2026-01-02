# Azure Functions - Real-Time Intelligence Project

## Overview

This directory contains a collection of Azure Functions designed to fetch and process real-time solar energy and device data for the Real-Time Intelligence Project. The functions are triggered to retrieve data from various sources including solar inverters, battery systems, IoT edge devices, power sensors, site data, and Wallbox chargers.

## Functions

The project includes six Azure Functions, each responsible for collecting data from specific sources:

### 1. **FetchSolarDataBattery**
- Fetches battery system data and status information
- Monitors battery charge/discharge cycles and health metrics

### 2. **FetchSolarDataInverter**
- Retrieves solar inverter performance metrics
- Captures power generation and efficiency data

### 3. **FetchSolarDataIotEdgeDevice**
- Collects data from IoT Edge devices
- Processes sensor readings and device telemetry

### 4. **FetchSolarDataPowerSensor**
- Gathers power consumption and generation sensor data
- Provides real-time energy measurements

### 5. **FetchSolarDataSiteData**
- Retrieves aggregated site-level information
- Manages site configuration and metadata

### 6. **FetchSolarDataWallbox**
- Fetches Wallbox charging station data
- Monitors EV charging sessions and energy consumption

## Project Structure

```
azure-function/
├── host.json                          # Azure Functions host configuration
├── local.settings.json                # Local development settings
├── requirements.txt                   # Python dependencies
├── FetchSolarDataBattery/
├── FetchSolarDataInverter/
├── FetchSolarDataIotEdgeDevice/
├── FetchSolarDataPowerSensor/
├── FetchSolarDataSiteData/
└── FetchSolarDataWallbox/
```

Each function folder contains:
- `__init__.py` - Function implementation
- `function.json` - Function trigger and binding configuration
- `__pycache__/` - Python cache directory

## Configuration

- **host.json**: Defines Azure Functions host configuration, runtime settings, and global extensions
- **local.settings.json**: Contains local development settings and connection strings
- **requirements.txt**: Lists Python package dependencies required by all functions

## Development

To set up the development environment:

1. Install dependencies: `pip install -r requirements.txt`
2. Configure local settings in `local.settings.json`
3. Test functions locally using Azure Functions Core Tools

## Deployment

Deploy these functions to Azure using:
- Azure CLI: `func azure functionapp publish <function-app-name>`
- Visual Studio Code Azure Functions extension
- CI/CD pipeline integration

## Dependencies

All Python dependencies are listed in `requirements.txt` and are shared across all functions.
