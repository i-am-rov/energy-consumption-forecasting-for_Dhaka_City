# Dhaka City Energy Consumption Forecasting API

A production-ready FastAPI application for forecasting Dhaka City's daily electricity demand. The service combines historical demand, temperature, calendar, holiday, lag, and rolling-demand features with 11 trained regression models.

## Features

- One-day and recursive seven-day electricity-demand forecasts
- Stable selection between 11 trained models, or all models at once
- Manual temperatures or automatic Dhaka weather from Open-Meteo
- Strict request validation with frontend-friendly error responses
- Browser dashboard, Swagger UI, ReDoc, and health monitoring
- Containerized deployment with a non-root runtime user

## Project layout

```text
app/                         FastAPI application package
  api/                       Routes, validation, forecasting, and weather logic
  api/static/                Browser interface assets
data/
  historical/                Feature-engineered demand history
  forecast_history/          Persisted predictions used for recursive lag features
models/
  artifacts/                 Eleven trained model files
  model_manifest.json        Feature and categorical-column schema
Dockerfile                   Production container image
requirements.txt             Runtime dependencies
```

## Run locally

Create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start the API from the project root:

```powershell
python -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

Open:

- Forecast dashboard: <http://127.0.0.1:8000/>
- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- Health check: <http://127.0.0.1:8000/health>

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/metadata` | Valid dates, constraints, holidays, and models |
| `GET` | `/api/v1/models` | Stable model-number catalog |
| `GET` | `/api/v1/weather/7-day` | Seven Dhaka daily mean temperatures |
| `POST` | `/api/v1/forecast` | Backward-compatible one-day forecast |
| `POST` | `/api/v1/forecast/7-day` | Recursive seven-day forecast |
| `GET` | `/health` | Service and model-artifact health |

Forecast dates advance with the Asia/Dhaka calendar. Call `/api/v1/metadata` before creating requests instead of hard-coding dates or temperature limits.

## Models

The service exposes Linear Regression, Ridge, Lasso, K-Nearest Neighbors, Random Forest, Extra Trees, CatBoost, Gradient Boosting, SVR with an RBF kernel, MLP Regressor, and Voting Regressor.

Model numbers are stable public identifiers. Their artifact mapping is defined in `app/api/model_registry.py`.

## Docker

Build and run the image:

```powershell
docker build -t dhaka-energy-api .
docker run --rm -p 8000:8000 dhaka-energy-api
```

The container runs `app.api.main:app` as an unprivileged user. Keep `app`, `data`, and `models` at the project root because their paths are resolved relative to the source package.

## Testing

Install the development dependencies and run the test suite:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Responsible use

Forecasts are decision-support estimates, not guarantees. Operational decisions should also consider current grid conditions, data drift, unusual weather, infrastructure changes, and expert review.
