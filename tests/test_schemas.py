"""Validation tests for public forecast request contracts."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.api.catalog import HOLIDAY_NAMES, TEMPERATURE_MIN_C
from app.api.schemas import ForecastRequest, SevenDayForecastRequest


def test_manual_forecast_request_accepts_strict_valid_input() -> None:
    request = ForecastRequest(
        forecast_date="2030-01-01",
        daily_temperature_c=TEMPERATURE_MIN_C,
        is_holiday=False,
        model=1,
        collect_temperature_from_api=False,
    )

    assert request.forecast_date == date(2030, 1, 1)
    assert int(request.model) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"daily_temperature_c": "30"},
        {"model": "1"},
        {"is_holiday": "false"},
        {"unexpected": True},
    ],
)
def test_forecast_request_rejects_coercion_and_unknown_fields(overrides: dict) -> None:
    payload = {
        "forecast_date": "2030-01-01",
        "daily_temperature_c": 30.0,
        "is_holiday": False,
        "model": "all",
        "collect_temperature_from_api": False,
        **overrides,
    }

    with pytest.raises(ValidationError):
        ForecastRequest.model_validate(payload)


def test_holiday_name_is_conditionally_required() -> None:
    with pytest.raises(ValidationError, match="holiday_name is required"):
        ForecastRequest(
            forecast_date="2030-01-01",
            daily_temperature_c=30.0,
            is_holiday=True,
        )

    request = ForecastRequest(
        forecast_date="2030-01-01",
        daily_temperature_c=30.0,
        is_holiday=True,
        holiday_name=HOLIDAY_NAMES[0],
    )
    assert request.holiday_name == HOLIDAY_NAMES[0]


def test_seven_day_request_requires_consecutive_dates() -> None:
    start = date(2030, 1, 1)
    days = [
        {
            "forecast_date": (start + timedelta(days=offset)).isoformat(),
            "daily_temperature_c": 30.0,
            "is_holiday": False,
        }
        for offset in range(7)
    ]
    days[-1]["forecast_date"] = (start + timedelta(days=8)).isoformat()

    with pytest.raises(ValidationError, match="seven consecutive"):
        SevenDayForecastRequest(
            days=days,
            model=1,
            collect_temperature_from_api=False,
        )
