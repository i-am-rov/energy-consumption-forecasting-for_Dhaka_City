"""End-to-end smoke tests for the deployed FastAPI application."""

from datetime import date

from fastapi.testclient import TestClient

from app.api.main import get_forecast_service


def test_homepage_and_operational_endpoints(client: TestClient) -> None:
    homepage = client.get("/")
    health = client.get("/health")
    models = client.get("/api/v1/models")

    assert homepage.status_code == 200
    assert "Dhaka" in homepage.text
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["artifacts_available"] == 11
    assert models.status_code == 200
    assert [item["id"] for item in models.json()["models"]] == list(range(1, 12))


def test_metadata_exposes_a_seven_day_window(
    client: TestClient,
    metadata: dict,
) -> None:
    start = date.fromisoformat(metadata["allowed_forecast_date"])
    end = date.fromisoformat(metadata["forecast_horizon_end_date"])

    assert (end - start).days == 6
    assert metadata["forecast_horizon_days"] == 7
    assert metadata["model_selector"]["all_models_value"] == "all"


def test_single_model_forecast_runs_with_manual_temperature(
    client: TestClient,
) -> None:
    allowed_date = get_forecast_service().repository.allowed_forecast_date
    response = client.post(
        "/api/v1/forecast",
        json={
            "forecast_date": allowed_date.isoformat(),
            "daily_temperature_c": 30.0,
            "is_holiday": False,
            "model": 1,
            "collect_temperature_from_api": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model_count"] == 1
    assert body["predictions"][0]["model_id"] == 1
    assert body["predictions"][0]["forecast_demand_mw"] > 0
    assert body["temperature"]["source"] == "manual"


def test_validation_errors_use_a_stable_shape(client: TestClient) -> None:
    response = client.post(
        "/api/v1/forecast",
        json={"forecast_date": "not-a-date", "unexpected": True},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]
