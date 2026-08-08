"""Pydantic request and response contracts for the forecasting API."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StrictBool,
    field_validator,
    model_validator,
)

from .catalog import (
    HolidayName,
    TEMPERATURE_MAX_C,
    TEMPERATURE_MIN_C,
    TEMPERATURE_STEP_C,
)
from .model_registry import ModelId


MODEL_ID_MIN = min(int(model_id) for model_id in ModelId)
MODEL_ID_MAX = max(int(model_id) for model_id in ModelId)
FORECAST_HORIZON_DAYS = 7
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

TemperatureC = Annotated[
    float,
    Field(
        ge=TEMPERATURE_MIN_C,
        le=TEMPERATURE_MAX_C,
        description=(
            "Daily mean temperature in degrees Celsius, restricted to the range represented "
            "during model training."
        ),
        examples=[30.5],
    ),
]
ModelSelector = Literal["all"] | ModelId


class ForecastRequest(BaseModel):
    """Inputs for a rolling one-day-ahead demand forecast."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "forecast_date": "2025-10-26",
                    "daily_temperature_c": 30.5,
                    "is_holiday": False,
                    "holiday_name": None,
                    "model": "all",
                    "collect_temperature_from_api": False,
                }
            ]
        },
    )

    forecast_date: date = Field(
        description=(
            "ISO date (YYYY-MM-DD). Must be the day immediately after the latest known demand date."
        ),
        examples=["2025-10-26"],
    )
    daily_temperature_c: TemperatureC | None = Field(
        default=None,
        description=(
            "Required when collect_temperature_from_api is false; omit it when weather lookup is enabled."
        ),
    )
    is_holiday: StrictBool = Field(
        default=False,
        description="Whether the forecast date is a holiday.",
    )
    holiday_name: HolidayName | None = Field(
        default=None,
        description="Required only when is_holiday is true; choices come from the project dataset.",
    )
    model: ModelSelector = Field(
        default="all",
        description=(
            f"A stable integer model number from {MODEL_ID_MIN} to {MODEL_ID_MAX}, "
            "or the exact lowercase string 'all'."
        ),
        examples=["all", 7],
    )

    @field_validator("forecast_date", mode="before")
    @classmethod
    def require_iso_calendar_date(cls, value):
        if type(value) is date:
            return value
        if not isinstance(value, str) or not ISO_DATE_PATTERN.fullmatch(value):
            raise ValueError("forecast_date must use the exact YYYY-MM-DD format")
        return value
    collect_temperature_from_api: StrictBool = Field(
        default=False,
        description=(
            "When true, obtain Dhaka's daily high and low from Open-Meteo and use their mean."
        ),
    )

    @field_validator("daily_temperature_c", mode="before")
    @classmethod
    def reject_non_numeric_temperature(cls, value):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError("daily_temperature_c must be a JSON number")
        return value

    @field_validator("model", mode="before")
    @classmethod
    def require_numeric_model_id_or_all(cls, value):
        if value == "all":
            return value
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("model must be the string 'all' or an integer model number")
        return value

    @model_validator(mode="after")
    def validate_conditional_fields(self) -> "ForecastRequest":
        if self.is_holiday and self.holiday_name is None:
            raise ValueError("holiday_name is required when is_holiday is true")
        if not self.is_holiday and self.holiday_name is not None:
            raise ValueError("holiday_name must be omitted when is_holiday is false")
        if self.collect_temperature_from_api and self.daily_temperature_c is not None:
            raise ValueError(
                "daily_temperature_c must be omitted when collect_temperature_from_api is true"
            )
        if not self.collect_temperature_from_api and self.daily_temperature_c is None:
            raise ValueError(
                "daily_temperature_c is required when collect_temperature_from_api is false"
            )
        return self


class ModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[int, Field(ge=MODEL_ID_MIN, le=MODEL_ID_MAX)]
    name: str
    family: str
    description: str


class TemperatureConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_c: float
    maximum_c: float
    step_c: float
    unit: Literal["°C"] = "°C"
    range_basis: Literal["model_training_data"] = "model_training_data"
    required_when: str
    omitted_when: str


class HolidayConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_enabled_when: str
    name_required_when: str
    non_holiday_name_value: None = None


class ModelSelectorConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    single_model_type: Literal["integer"] = "integer"
    minimum_id: int
    maximum_id: int
    all_models_value: Literal["all"] = "all"
    default: Literal["all"] = "all"


class ApiMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latest_known_demand_date: date
    latest_recursive_history_date: date
    allowed_forecast_date: date
    forecast_horizon_end_date: date
    forecast_horizon_days: Literal[7] = 7
    forecast_date_rule: str
    holiday_names: list[str]
    models: list[ModelInfo]
    temperature_constraints: TemperatureConstraints
    holiday_constraints: HolidayConstraints
    model_selector: ModelSelectorConstraints
    dhaka_weather_available: bool = True


class ModelCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    all_models_value: Literal["all"] = "all"
    default: Literal["all"] = "all"
    models: list[ModelInfo]


class TemperatureInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_temperature_c: TemperatureC
    source: Literal["manual", "open_meteo_forecast", "open_meteo_archive"]
    collected_from_api: bool
    daily_high_c: FiniteFloat | None = None
    daily_low_c: FiniteFloat | None = None


class ModelPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: Annotated[int, Field(ge=MODEL_ID_MIN, le=MODEL_ID_MAX)]
    model_name: str
    family: str
    forecast_demand_mw: Annotated[float, Field(ge=0)]


class ForecastResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast_date: date
    is_holiday: bool
    holiday_name: str | None
    temperature: TemperatureInfo
    predictions: list[ModelPrediction]
    model_count: Annotated[int, Field(ge=1, le=MODEL_ID_MAX)]
    generated_at: datetime

    @model_validator(mode="after")
    def validate_prediction_count(self) -> "ForecastResponse":
        if self.model_count != len(self.predictions):
            raise ValueError("model_count must equal the number of predictions")
        return self


class ForecastDayInput(BaseModel):
    """Weather and calendar inputs for one day in a recursive horizon."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    forecast_date: date
    daily_temperature_c: TemperatureC | None = None
    is_holiday: StrictBool = False
    holiday_name: HolidayName | None = None

    @field_validator("forecast_date", mode="before")
    @classmethod
    def require_iso_calendar_date(cls, value):
        if type(value) is date:
            return value
        if not isinstance(value, str) or not ISO_DATE_PATTERN.fullmatch(value):
            raise ValueError("forecast_date must use the exact YYYY-MM-DD format")
        return value

    @field_validator("daily_temperature_c", mode="before")
    @classmethod
    def reject_non_numeric_temperature(cls, value):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            raise ValueError("daily_temperature_c must be a JSON number")
        return value

    @model_validator(mode="after")
    def validate_holiday(self) -> "ForecastDayInput":
        if self.is_holiday and self.holiday_name is None:
            raise ValueError("holiday_name is required when is_holiday is true")
        if not self.is_holiday and self.holiday_name is not None:
            raise ValueError("holiday_name must be omitted when is_holiday is false")
        return self


class SevenDayForecastRequest(BaseModel):
    """Seven consecutive recursive demand forecasts."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "days": [
                        {
                            "forecast_date": f"2026-08-{day:02d}",
                            "daily_temperature_c": 30.0,
                            "is_holiday": False,
                            "holiday_name": None,
                        }
                        for day in range(7, 14)
                    ],
                    "model": 1,
                    "collect_temperature_from_api": False,
                }
            ]
        },
    )

    days: Annotated[
        list[ForecastDayInput],
        Field(min_length=FORECAST_HORIZON_DAYS, max_length=FORECAST_HORIZON_DAYS),
    ]
    model: ModelSelector = "all"
    collect_temperature_from_api: StrictBool = True

    @field_validator("model", mode="before")
    @classmethod
    def require_numeric_model_id_or_all(cls, value):
        if value == "all":
            return value
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("model must be the string 'all' or an integer model number")
        return value

    @model_validator(mode="after")
    def validate_horizon(self) -> "SevenDayForecastRequest":
        dates = [item.forecast_date for item in self.days]
        if any(
            current != previous + timedelta(days=1)
            for previous, current in zip(dates, dates[1:])
        ):
            raise ValueError("days must contain seven consecutive forecast dates")
        if self.collect_temperature_from_api:
            if any(item.daily_temperature_c is not None for item in self.days):
                raise ValueError(
                    "daily_temperature_c must be omitted when weather lookup is enabled"
                )
        elif any(item.daily_temperature_c is None for item in self.days):
            raise ValueError(
                "daily_temperature_c is required for every day in manual mode"
            )
        return self


class SevenDayForecastDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast_date: date
    is_holiday: bool
    holiday_name: str | None
    temperature: TemperatureInfo
    predictions: list[ModelPrediction]
    recursive_history_demand_mw: Annotated[float, Field(ge=0)]


class SevenDayForecastResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date
    days: Annotated[
        list[SevenDayForecastDay],
        Field(min_length=FORECAST_HORIZON_DAYS, max_length=FORECAST_HORIZON_DAYS),
    ]
    model_count: Annotated[int, Field(ge=1, le=MODEL_ID_MAX)]
    recursive_strategy: Literal["selected_model_or_consensus_mean"] = (
        "selected_model_or_consensus_mean"
    )
    generated_at: datetime


class WeatherHorizonDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast_date: date
    temperature: TemperatureInfo


class WeatherHorizonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date
    days: Annotated[
        list[WeatherHorizonDay],
        Field(min_length=FORECAST_HORIZON_DAYS, max_length=FORECAST_HORIZON_DAYS),
    ]


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    models_configured: int
    artifacts_available: int
    latest_known_demand_date: date
    latest_recursive_history_date: date


class OpenMeteoDailyPayload(BaseModel):
    """Validated subset of the external Open-Meteo response."""

    model_config = ConfigDict(extra="ignore")

    time: list[date]
    temperature_2m_max: list[FiniteFloat]
    temperature_2m_min: list[FiniteFloat]


class OpenMeteoPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    daily: OpenMeteoDailyPayload


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    message: str
    type: str


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: list[ValidationIssue] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ApiError
