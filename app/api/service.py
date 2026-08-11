"""Model loading and forecasting orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache

import joblib
import numpy as np
from catboost import CatBoostRegressor

from .catalog import (
    HOLIDAY_NAMES,
    TEMPERATURE_MAX_C,
    TEMPERATURE_MIN_C,
    TEMPERATURE_STEP_C,
)
from .features import KNOWN_FUTURE_HOLIDAYS, FeatureRepository
from .model_registry import MODEL_REGISTRY, ModelDefinition, ModelId, model_definitions
from .schemas import (
    ApiMetadata,
    ForecastRequest,
    ForecastResponse,
    HealthResponse,
    HolidayConstraints,
    ModelCatalogResponse,
    ModelInfo,
    ModelPrediction,
    ModelSelectorConstraints,
    SevenDayForecastDay,
    SevenDayForecastRequest,
    SevenDayForecastResponse,
    TemperatureConstraints,
    TemperatureInfo,
    WeatherHorizonDay,
    WeatherHorizonResponse,
)
from .weather import (
    get_dhaka_daily_temperature,
    get_dhaka_daily_temperatures,
    get_dhaka_today,
)


class ModelPredictionError(RuntimeError):
    """Raised if an artifact cannot return a valid finite prediction."""


@lru_cache(maxsize=len(MODEL_REGISTRY))
def _load_model(model_id: ModelId):
    definition = MODEL_REGISTRY[model_id]
    if not definition.artifact_path.is_file():
        raise ModelPredictionError(f"Model artifact is missing for model {int(model_id)}.")

    if definition.artifact_format == "catboost":
        model = CatBoostRegressor()
        model.load_model(definition.artifact_path, format="cbm")
        return model
    return joblib.load(definition.artifact_path)


class ForecastService:
    def __init__(
        self,
        repository: FeatureRepository | None = None,
        weather_provider: Callable = get_dhaka_daily_temperature,
        weather_range_provider: Callable = get_dhaka_daily_temperatures,
        current_date_provider: Callable[[], date] = get_dhaka_today,
    ) -> None:
        self.repository = repository or FeatureRepository()
        self.weather_provider = weather_provider
        self.weather_range_provider = weather_range_provider
        self.current_date_provider = current_date_provider

    def _visible_forecast_window(self) -> tuple[date, date]:
        start_date = max(
            self.current_date_provider(),
            self.repository.allowed_forecast_date,
        )
        return start_date, start_date + timedelta(days=6)

    def metadata(self) -> ApiMetadata:
        start_date, end_date = self._visible_forecast_window()
        return ApiMetadata(
            latest_known_demand_date=self.repository.latest_known_demand_date,
            latest_recursive_history_date=self.repository.latest_recursive_history_date,
            allowed_forecast_date=start_date,
            forecast_horizon_end_date=end_date,
            forecast_date_rule=(
                "Seven consecutive visible days beginning on the current Asia/Dhaka "
                "date. Missing dates after latest_recursive_history_date are calculated "
                "silently in the backend."
            ),
            holiday_names=list(HOLIDAY_NAMES),
            models=self._model_infos(),
            temperature_constraints=TemperatureConstraints(
                minimum_c=TEMPERATURE_MIN_C,
                maximum_c=TEMPERATURE_MAX_C,
                step_c=TEMPERATURE_STEP_C,
                required_when="collect_temperature_from_api is false",
                omitted_when="collect_temperature_from_api is true",
            ),
            holiday_constraints=HolidayConstraints(
                name_enabled_when="is_holiday is true",
                name_required_when="is_holiday is true",
            ),
            model_selector=ModelSelectorConstraints(
                minimum_id=min(int(model_id) for model_id in ModelId),
                maximum_id=max(int(model_id) for model_id in ModelId),
            ),
        )

    def model_catalog(self) -> ModelCatalogResponse:
        return ModelCatalogResponse(models=self._model_infos())

    @staticmethod
    def _model_infos() -> list[ModelInfo]:
        return [
            ModelInfo(
                id=int(item.id),
                name=item.name,
                family=item.family,
                description=item.description,
            )
            for item in model_definitions()
        ]

    def health(self) -> HealthResponse:
        definitions = model_definitions()
        return HealthResponse(
            models_configured=len(definitions),
            artifacts_available=sum(item.artifact_path.is_file() for item in definitions),
            latest_known_demand_date=self.repository.latest_known_demand_date,
            latest_recursive_history_date=self.repository.latest_recursive_history_date,
        )

    async def weather_horizon(self) -> WeatherHorizonResponse:
        start_date, end_date = self._visible_forecast_window()
        temperatures = await self.weather_range_provider(start_date, 7)
        if len(temperatures) != 7:
            raise ModelPredictionError("Weather provider did not return seven forecast days.")
        return WeatherHorizonResponse(
            start_date=start_date,
            end_date=end_date,
            days=[
                WeatherHorizonDay(
                    forecast_date=start_date + timedelta(days=index),
                    temperature=temperature,
                )
                for index, temperature in enumerate(temperatures)
            ],
        )

    async def forecast(self, request: ForecastRequest) -> ForecastResponse:
        self.repository.validate_forecast_date(request.forecast_date)

        if request.collect_temperature_from_api:
            temperature = await self.weather_provider(request.forecast_date)
        else:
            temperature = TemperatureInfo(
                daily_temperature_c=float(request.daily_temperature_c),
                source="manual",
                collected_from_api=False,
            )

        feature_row = self.repository.build_feature_row(
            forecast_date=request.forecast_date,
            daily_temperature_c=temperature.daily_temperature_c,
            is_holiday=request.is_holiday,
            holiday_name=request.holiday_name.value if request.holiday_name else None,
        )

        selected = (
            model_definitions()
            if request.model == "all"
            else (MODEL_REGISTRY[ModelId(request.model)],)
        )
        # Artifact deserialization and inference are blocking CPU/file operations;
        # keep them off FastAPI's event loop so concurrent HTTP requests stay responsive.
        predictions = await asyncio.to_thread(
            lambda: [self._predict(definition, feature_row) for definition in selected]
        )

        return ForecastResponse(
            forecast_date=request.forecast_date,
            is_holiday=request.is_holiday,
            holiday_name=request.holiday_name.value if request.holiday_name else None,
            temperature=temperature,
            predictions=predictions,
            model_count=len(predictions),
            generated_at=datetime.now(UTC),
        )

    async def forecast_horizon(
        self,
        request: SevenDayForecastRequest,
    ) -> SevenDayForecastResponse:
        visible_start, visible_end = self._visible_forecast_window()
        dates = self.repository.validate_horizon_dates(
            (item.forecast_date for item in request.days),
            expected_start=visible_start,
            maximum_days=7,
        )
        if len(dates) != 7:
            raise ModelPredictionError("Seven-day forecasts require exactly seven dates.")

        recursive_start = self.repository.allowed_forecast_date
        recursive_dates = tuple(
            recursive_start + timedelta(days=offset)
            for offset in range((visible_end - recursive_start).days + 1)
        )
        hidden_count = (visible_start - recursive_start).days

        if request.collect_temperature_from_api:
            all_temperatures = await self.weather_range_provider(
                recursive_start,
                len(recursive_dates),
            )
            temperatures = all_temperatures[hidden_count:]
        else:
            hidden_temperatures = (
                await self.weather_range_provider(recursive_start, hidden_count)
                if hidden_count
                else []
            )
            temperatures = [
                TemperatureInfo(
                    daily_temperature_c=float(item.daily_temperature_c),
                    source="manual",
                    collected_from_api=False,
                )
                for item in request.days
            ]
            all_temperatures = hidden_temperatures + temperatures
        if len(temperatures) != 7:
            raise ModelPredictionError("Weather provider did not return seven forecast days.")
        if len(all_temperatures) != len(recursive_dates):
            raise ModelPredictionError(
                "Weather provider did not return the complete hidden and visible timeline."
            )

        visible_inputs = {item.forecast_date: item for item in request.days}
        contexts = []
        for forecast_date, temperature in zip(recursive_dates, all_temperatures, strict=False):
            item = visible_inputs.get(forecast_date)
            if item is None:
                holiday_name = KNOWN_FUTURE_HOLIDAYS.get(forecast_date)
                contexts.append(
                    (
                        forecast_date,
                        temperature.daily_temperature_c,
                        holiday_name is not None,
                        holiday_name,
                    )
                )
            else:
                contexts.append(
                    (
                        forecast_date,
                        temperature.daily_temperature_c,
                        item.is_holiday,
                        item.holiday_name.value if item.holiday_name else None,
                    )
                )
        frame = self.repository.prepare_recursive_frame(contexts)
        selected = self._selected_definitions(request.model)
        response_days: list[SevenDayForecastDay] = []

        for forecast_date, temperature in zip(recursive_dates, all_temperatures, strict=False):
            feature_row = self.repository.build_recursive_feature_row(
                frame,
                forecast_date,
            )
            predictions = await asyncio.to_thread(
                lambda row=feature_row: [self._predict(definition, row) for definition in selected]
            )
            recursive_value = float(
                np.mean([prediction.forecast_demand_mw for prediction in predictions])
            )
            self.repository.record_recursive_prediction(
                frame,
                forecast_date,
                recursive_value,
            )
            item = visible_inputs.get(forecast_date)
            if item is None:
                continue
            response_days.append(
                SevenDayForecastDay(
                    forecast_date=forecast_date,
                    is_holiday=item.is_holiday,
                    holiday_name=item.holiday_name.value if item.holiday_name else None,
                    temperature=temperature,
                    predictions=predictions,
                    recursive_history_demand_mw=round(recursive_value, 2),
                )
            )

        return SevenDayForecastResponse(
            start_date=visible_start,
            end_date=visible_end,
            days=response_days,
            model_count=len(selected),
            generated_at=datetime.now(UTC),
        )

    @staticmethod
    def _selected_definitions(model_selector):
        return (
            model_definitions()
            if model_selector == "all"
            else (MODEL_REGISTRY[ModelId(model_selector)],)
        )

    def _predict(self, definition: ModelDefinition, feature_row) -> ModelPrediction:
        try:
            model = _load_model(definition.id)
            value = float(np.asarray(model.predict(feature_row), dtype=float).reshape(-1)[0])
        except Exception as exc:
            if isinstance(exc, ModelPredictionError):
                raise
            raise ModelPredictionError(
                f"Model {int(definition.id)} ({definition.name}) could not generate a forecast."
            ) from exc

        if not np.isfinite(value) or value < 0:
            raise ModelPredictionError(
                f"Model {int(definition.id)} ({definition.name}) returned an invalid forecast."
            )
        return ModelPrediction(
            model_id=int(definition.id),
            model_name=definition.name,
            family=definition.family,
            forecast_demand_mw=round(value, 2),
        )
