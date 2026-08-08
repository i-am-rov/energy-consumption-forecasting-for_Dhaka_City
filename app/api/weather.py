"""Dhaka daily-temperature lookup through Open-Meteo."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from .schemas import OpenMeteoPayload, TemperatureInfo


# The forecast endpoint and location are based on the URL supplied for this API.
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DHAKA_LATITUDE = 23.8103
DHAKA_LONGITUDE = 90.4125
DHAKA_TIMEZONE = "Asia/Dhaka"
RECENT_FORECAST_HISTORY_DAYS = 92
MAX_WEATHER_RANGE_DAYS = 3660


class WeatherServiceError(RuntimeError):
    """Raised when Open-Meteo cannot supply a valid daily temperature."""


def get_dhaka_today() -> date:
    """Return the calendar date currently visible in Dhaka."""

    return datetime.now(ZoneInfo(DHAKA_TIMEZONE)).date()


def _weather_segments(
    start_date: date,
    end_date: date,
    dhaka_today: date,
) -> list[tuple[date, date, str, str]]:
    """Split long ranges between archive and recent forecast data."""

    recent_start = dhaka_today - timedelta(days=RECENT_FORECAST_HISTORY_DAYS)
    segments: list[tuple[date, date, str, str]] = []
    if start_date < recent_start:
        archive_end = min(end_date, recent_start - timedelta(days=1))
        segments.append(
            (
                start_date,
                archive_end,
                OPEN_METEO_ARCHIVE_URL,
                "open_meteo_archive",
            )
        )
    if end_date >= recent_start:
        segments.append(
            (
                max(start_date, recent_start),
                end_date,
                OPEN_METEO_FORECAST_URL,
                "open_meteo_forecast",
            )
        )
    return segments


async def _fetch_temperature_segment(
    start_date: date,
    end_date: date,
    endpoint: str,
    source: str,
    client: httpx.AsyncClient,
) -> list[TemperatureInfo]:
    params = {
        "latitude": DHAKA_LATITUDE,
        "longitude": DHAKA_LONGITUDE,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": DHAKA_TIMEZONE,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    try:
        response = await client.get(endpoint, params=params)
        response.raise_for_status()
        payload = OpenMeteoPayload.model_validate(response.json())
    except (httpx.HTTPError, ValueError, ValidationError) as exc:
        raise WeatherServiceError(
            "Open-Meteo could not provide Dhaka weather for "
            f"{start_date.isoformat()} through {end_date.isoformat()}."
        ) from exc

    daily = payload.daily
    segment_days = (end_date - start_date).days + 1
    results: list[TemperatureInfo] = []
    for offset in range(segment_days):
        forecast_date = start_date + timedelta(days=offset)
        try:
            date_index = daily.time.index(forecast_date)
            high = float(daily.temperature_2m_max[date_index])
            low = float(daily.temperature_2m_min[date_index])
        except (ValueError, IndexError, TypeError) as exc:
            raise WeatherServiceError(
                f"Open-Meteo returned no complete Dhaka forecast for {forecast_date.isoformat()}."
            ) from exc

        if high < low:
            raise WeatherServiceError("Open-Meteo returned a daily high below the daily low.")

        mean_temperature = (high + low) / 2.0
        try:
            results.append(
                TemperatureInfo(
                    daily_temperature_c=round(mean_temperature, 2),
                    source=source,
                    collected_from_api=True,
                    daily_high_c=round(high, 2),
                    daily_low_c=round(low, 2),
                )
            )
        except ValidationError as exc:
            raise WeatherServiceError(
                "Open-Meteo returned temperatures outside valid bounds."
            ) from exc
    return results


async def get_dhaka_daily_temperature(
    forecast_date: date,
    client: httpx.AsyncClient | None = None,
) -> TemperatureInfo:
    """Return (daily maximum + daily minimum) / 2 for the requested date."""

    temperatures = await get_dhaka_daily_temperatures(
        forecast_date,
        days=1,
        client=client,
    )
    return temperatures[0]


async def get_dhaka_daily_temperatures(
    start_date: date,
    days: int = 7,
    client: httpx.AsyncClient | None = None,
) -> list[TemperatureInfo]:
    """Return validated daily mean temperatures for a consecutive Dhaka horizon."""

    if days < 1 or days > MAX_WEATHER_RANGE_DAYS:
        raise WeatherServiceError(
            f"Weather horizon must contain between 1 and {MAX_WEATHER_RANGE_DAYS} days."
        )

    end_date = start_date + timedelta(days=days - 1)
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
    try:
        results: list[TemperatureInfo] = []
        for segment in _weather_segments(start_date, end_date, get_dhaka_today()):
            results.extend(
                await _fetch_temperature_segment(*segment, client=active_client)
            )
    finally:
        if owns_client:
            await active_client.aclose()
    return results
