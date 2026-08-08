# Dhaka City Energy Consumption Forecasting

This folder contains only the files required to run and containerize the
forecasting API.

## Folder structure

```text
energy-consumption-forecasting-for_Dhaka_City/
|-- app/                         FastAPI application package
|   |-- api/                     Routes, validation, forecasting, and weather logic
|   `-- api/static/              Browser interface assets
|-- data/
|   |-- historical/              Feature-engineered demand history
|   `-- forecast_history/        Persisted recursive predictions used for lag features
|-- models/
|   |-- artifacts/               Eleven trained model files
|   `-- model_manifest.json      Model feature and categorical-column schema
|-- .dockerignore                Excludes caches and local development files
|-- requirements.txt             Python runtime dependencies
`-- README.md                    Structure and startup instructions
```

## Run locally

From this folder:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

Then open `http://127.0.0.1:8000/`.

## Docker entry point

Use this application target in the container command:

```text
app.api.main:app
```

The application expects `app`, `data`, and `models` to remain at the project
root because their locations are resolved relative to the Python source files.
