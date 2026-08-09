"""Deterministic tests for the Open-Meteo integration."""

import asyncio
from datetime import date, timedelta

import httpx
import pytest

from app.api.weather import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_FORECAST_URL,
    WeatherServiceError,
    _weather_segments,
    get_dhaka_daily_temperatures,
    get_dhaka_today,
)


def test_weather_segments_split_archive_and_recent_dates() -> None:
    today = date(2030, 6, 1)
    recent_start = today - timedelta(days=92)
    start = recent_start - timedelta(days=2)

    segments = _weather_segments(start, recent_start, today)

    assert segments == [
        (start, recent_start - timedelta(days=1), OPEN_METEO_ARCHIVE_URL, "open_meteo_archive"),
        (recent_start, recent_start, OPEN_METEO_FORECAST_URL, "open_meteo_forecast"),
    ]


def test_weather_client_calculates_daily_mean_temperature() -> None:
    start = get_dhaka_today()

    def handler(request: httpx.Request) -> httpx.Response:
        requested_start = date.fromisoformat(request.url.params["start_date"])
        requested_end = date.fromisoformat(request.url.params["end_date"])
        days = (requested_end - requested_start).days + 1
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": [
                        (requested_start + timedelta(days=offset)).isoformat()
                        for offset in range(days)
                    ],
                    "temperature_2m_max": [34.0] * days,
                    "temperature_2m_min": [26.0] * days,
                }
            },
        )

    async def request_temperatures():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await get_dhaka_daily_temperatures(start, days=2, client=client)

    results = asyncio.run(request_temperatures())

    assert [item.daily_temperature_c for item in results] == [30.0, 30.0]
    assert all(item.collected_from_api for item in results)


def test_weather_client_rejects_impossible_high_low_pair() -> None:
    start = get_dhaka_today()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": [start.isoformat()],
                    "temperature_2m_max": [25.0],
                    "temperature_2m_min": [30.0],
                }
            },
        )

    async def request_temperature() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await get_dhaka_daily_temperatures(start, days=1, client=client)

    with pytest.raises(WeatherServiceError, match="high below the daily low"):
        asyncio.run(request_temperature())
