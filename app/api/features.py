"""Leakage-safe features for one-day and seven-day recursive forecasts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import FEATURE_DATA_PATH

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_MANIFEST_PATH = PROJECT_ROOT / "models" / "model_manifest.json"
RECURSIVE_HISTORY_PATH = (
    PROJECT_ROOT / "data" / "forecast_history" / "recursive_forecast_history.csv"
)
TARGET_COLUMN = "Demand (MW)"
DATE_COLUMN = "Date"
COOLING_THRESHOLD_C = 24.0
FORECAST_HORIZON_DAYS = 7

# Public holidays after the persisted recursive history. User-provided horizon
# inputs override these values for the seven dates being forecast.
KNOWN_FUTURE_HOLIDAYS: dict[date, str] = {
    date(2026, 8, 26): "Eid-e-Miladunnabi",
    date(2026, 9, 4): "Janmashtami",
    date(2026, 10, 20): "Durga Puja",
    date(2026, 10, 21): "Durga Puja",
    date(2026, 12, 16): "Victory Day",
    date(2026, 12, 25): "Christmas Day",
}


class FeatureValidationError(ValueError):
    """Raised when a request cannot produce valid trained-model features."""


def _season_for_month(month: int) -> str:
    if month in {11, 12, 1, 2}:
        return "Winter"
    if month in {3, 4, 5}:
        return "Summer"
    return "Monsoon"


class FeatureRepository:
    """Combine actual and persisted recursive history for future inference."""

    def __init__(
        self,
        data_path: Path = FEATURE_DATA_PATH,
        manifest_path: Path = MODEL_MANIFEST_PATH,
        recursive_history_path: Path | None = RECURSIVE_HISTORY_PATH,
    ) -> None:
        self.data_path = Path(data_path)
        self.manifest_path = Path(manifest_path)
        self.recursive_history_path = (
            Path(recursive_history_path) if recursive_history_path is not None else None
        )

        source = pd.read_csv(self.data_path)
        source[DATE_COLUMN] = pd.to_datetime(source[DATE_COLUMN], errors="raise")
        source = source.sort_values(DATE_COLUMN).reset_index(drop=True)
        with self.manifest_path.open("r", encoding="utf-8") as file_handle:
            manifest = json.load(file_handle)
        self.feature_columns = tuple(manifest["feature_columns"])
        self.categorical_columns = tuple(manifest["categorical_columns"])

        temperature_columns = [column for column in source.columns if column.startswith("Temp (")]
        if len(temperature_columns) != 1:
            raise RuntimeError(
                f"Expected one temperature column in feature data, found {temperature_columns}"
            )
        self.temperature_column = temperature_columns[0]

        actual = source.loc[source[TARGET_COLUMN].notna()].copy()
        if actual.empty:
            raise RuntimeError("Feature data does not contain known demand values.")
        self.latest_known_demand_date = actual[DATE_COLUMN].max().date()
        raw_columns = [
            DATE_COLUMN,
            TARGET_COLUMN,
            self.temperature_column,
            "Holiday",
            "Holiday_Name",
        ]
        history_parts = [actual[raw_columns].copy()]

        if self.recursive_history_path is not None and self.recursive_history_path.is_file():
            recursive = pd.read_csv(self.recursive_history_path)
            recursive[DATE_COLUMN] = pd.to_datetime(recursive[DATE_COLUMN], errors="raise")
            recursive_temperature = [
                column for column in recursive.columns if column.startswith("Temp (")
            ]
            if len(recursive_temperature) != 1:
                raise RuntimeError("Recursive history must contain exactly one temperature column.")
            if recursive_temperature[0] != self.temperature_column:
                recursive = recursive.rename(
                    columns={recursive_temperature[0]: self.temperature_column}
                )
            recursive = recursive.loc[
                recursive[DATE_COLUMN].dt.date > self.latest_known_demand_date,
                raw_columns,
            ].copy()
            if recursive[[TARGET_COLUMN, self.temperature_column]].isna().any().any():
                raise RuntimeError(
                    "Recursive history contains missing demand or temperature values."
                )
            if not recursive.empty:
                expected_start = self.latest_known_demand_date + timedelta(days=1)
                if recursive.iloc[0][DATE_COLUMN].date() != expected_start:
                    raise RuntimeError(
                        f"Recursive history must start on {expected_start.isoformat()}."
                    )
                history_parts.append(recursive)

        self.frame = (
            pd.concat(history_parts, ignore_index=True)
            .sort_values(DATE_COLUMN)
            .reset_index(drop=True)
        )
        if self.frame[DATE_COLUMN].duplicated().any():
            raise RuntimeError("Combined demand history contains duplicate dates.")
        gaps = self.frame[DATE_COLUMN].diff().dropna()
        if not gaps.eq(pd.Timedelta(days=1)).all():
            raise RuntimeError("Combined demand history must have an uninterrupted daily index.")

        self.latest_recursive_history_date = self.frame[DATE_COLUMN].max().date()
        self.allowed_forecast_date = self.latest_recursive_history_date + timedelta(days=1)
        self.forecast_horizon_end_date = self.allowed_forecast_date + timedelta(
            days=FORECAST_HORIZON_DAYS - 1
        )

    def validate_forecast_date(self, forecast_date: date) -> None:
        self.validate_horizon_dates([forecast_date])

    def validate_horizon_dates(
        self,
        dates: Iterable[date],
        *,
        expected_start: date | None = None,
        maximum_days: int | None = FORECAST_HORIZON_DAYS,
    ) -> tuple[date, ...]:
        normalized = tuple(dates)
        if not normalized:
            raise FeatureValidationError("Forecast requests must contain at least one day.")
        if maximum_days is not None and len(normalized) > maximum_days:
            raise FeatureValidationError(
                f"Forecast requests must contain between 1 and {maximum_days} days."
            )
        required_start = expected_start or self.allowed_forecast_date
        if normalized[0] != required_start:
            raise FeatureValidationError(
                f"The first forecast date must be exactly {required_start.isoformat()}."
            )
        for previous, current in zip(normalized, normalized[1:], strict=False):
            if current != previous + timedelta(days=1):
                raise FeatureValidationError("Forecast dates must be consecutive without gaps.")
        return normalized

    def prepare_recursive_frame(
        self,
        contexts: Iterable[tuple[date, float, bool, str | None]],
    ) -> pd.DataFrame:
        normalized = tuple(contexts)
        dates = self.validate_horizon_dates(
            (item[0] for item in normalized),
            expected_start=self.allowed_forecast_date,
            maximum_days=None,
        )
        if len(normalized) != len(dates):
            raise FeatureValidationError("Forecast contexts and dates do not match.")

        buffer_end = pd.Timestamp(dates[-1] + timedelta(days=31))
        full_dates = pd.date_range(
            self.frame[DATE_COLUMN].min(),
            buffer_end,
            freq="D",
        )
        frame = pd.DataFrame({DATE_COLUMN: full_dates}).merge(
            self.frame,
            on=DATE_COLUMN,
            how="left",
        )
        future_mask = frame[DATE_COLUMN].dt.date > self.latest_recursive_history_date
        frame.loc[future_mask, "Holiday"] = 0
        frame.loc[future_mask, "Holiday_Name"] = "Not a Holiday"
        for holiday_date, holiday_name in KNOWN_FUTURE_HOLIDAYS.items():
            mask = frame[DATE_COLUMN].dt.date == holiday_date
            frame.loc[mask, "Holiday"] = 1
            frame.loc[mask, "Holiday_Name"] = holiday_name

        for forecast_date, temperature, is_holiday, holiday_name in normalized:
            mask = frame[DATE_COLUMN].dt.date == forecast_date
            frame.loc[mask, self.temperature_column] = float(temperature)
            frame.loc[mask, "Holiday"] = int(is_holiday)
            frame.loc[mask, "Holiday_Name"] = holiday_name or "Not a Holiday"

        frame["Holiday"] = frame["Holiday"].fillna(0).astype(int)
        frame["Holiday_Name"] = frame["Holiday_Name"].fillna("Not a Holiday").astype(str)
        self._compute_exogenous_features(frame)
        return frame

    def build_recursive_feature_row(
        self,
        frame: pd.DataFrame,
        forecast_date: date,
    ) -> pd.DataFrame:
        self._compute_demand_features(frame)
        result = frame.loc[
            frame[DATE_COLUMN].dt.date == forecast_date,
            self.feature_columns,
        ].copy()
        if len(result) != 1:
            raise FeatureValidationError(
                f"Forecast frame does not contain exactly one row for {forecast_date.isoformat()}."
            )
        missing = result.columns[result.isna().any()].tolist()
        if missing:
            raise FeatureValidationError(
                f"Cannot forecast {forecast_date.isoformat()} because these model features "
                f"are unavailable: {missing}"
            )
        return result

    @staticmethod
    def record_recursive_prediction(
        frame: pd.DataFrame,
        forecast_date: date,
        prediction_mw: float,
    ) -> None:
        mask = frame[DATE_COLUMN].dt.date == forecast_date
        if mask.sum() != 1:
            raise FeatureValidationError(
                f"Cannot record recursive prediction for {forecast_date.isoformat()}."
            )
        frame.loc[mask, TARGET_COLUMN] = float(prediction_mw)

    def build_feature_row(
        self,
        forecast_date: date,
        daily_temperature_c: float,
        is_holiday: bool,
        holiday_name: str | None,
    ) -> pd.DataFrame:
        """Backward-compatible one-day feature builder."""

        frame = self.prepare_recursive_frame(
            [(forecast_date, daily_temperature_c, is_holiday, holiday_name)]
        )
        return self.build_recursive_feature_row(frame, forecast_date)

    def _compute_exogenous_features(self, frame: pd.DataFrame) -> None:
        dates = frame[DATE_COLUMN]
        frame["Month"] = dates.dt.month
        frame["Day"] = dates.dt.day
        frame["Year"] = dates.dt.year
        frame["Weekday"] = dates.dt.day_name()
        frame["Weekend"] = dates.dt.dayofweek.isin([4, 5]).astype(int)
        frame["Season"] = frame["Month"].map(_season_for_month)
        frame["DayOfYear"] = dates.dt.dayofyear
        frame["WeekOfYear"] = dates.dt.isocalendar().week.astype(int)
        frame["Quarter"] = dates.dt.quarter
        frame["IsMonthStart"] = dates.dt.is_month_start.astype(int)
        frame["IsMonthEnd"] = dates.dt.is_month_end.astype(int)
        frame["IsYearStart"] = dates.dt.is_year_start.astype(int)
        frame["IsYearEnd"] = dates.dt.is_year_end.astype(int)
        frame["Weekday_Number"] = dates.dt.dayofweek
        frame["Time_Index"] = np.arange(len(frame), dtype=int)
        frame["Month_Sin"] = np.sin(2 * np.pi * frame["Month"] / 12)
        frame["Month_Cos"] = np.cos(2 * np.pi * frame["Month"] / 12)
        frame["Weekday_Sin"] = np.sin(2 * np.pi * frame["Weekday_Number"] / 7)
        frame["Weekday_Cos"] = np.cos(2 * np.pi * frame["Weekday_Number"] / 7)
        frame["DayOfYear_Sin"] = np.sin(2 * np.pi * frame["DayOfYear"] / 365.25)
        frame["DayOfYear_Cos"] = np.cos(2 * np.pi * frame["DayOfYear"] / 365.25)

        temperature = frame[self.temperature_column].astype(float)
        frame["Temp_Squared"] = temperature**2
        frame["Cooling_Degree_24"] = (temperature - COOLING_THRESHOLD_C).clip(lower=0)
        frame["Temp_Lag_1"] = temperature.shift(1)
        frame["Temp_Lag_7"] = temperature.shift(7)
        frame["Temp_Change_1"] = temperature - frame["Temp_Lag_1"]
        past_temperature = temperature.shift(1)
        frame["Temp_Rolling_Mean_3"] = past_temperature.rolling(3, min_periods=3).mean()
        frame["Temp_Rolling_Mean_7"] = past_temperature.rolling(7, min_periods=7).mean()
        frame["Temp_Rolling_Std_7"] = past_temperature.rolling(7, min_periods=7).std()
        frame["Temp_Weekend"] = temperature * frame["Weekend"]
        frame["Temp_Holiday"] = temperature * frame["Holiday"]

        frame["Day_Before_Holiday"] = frame["Holiday"].shift(-1, fill_value=0).astype(int)
        frame["Day_After_Holiday"] = frame["Holiday"].shift(1, fill_value=0).astype(int)
        frame["Holiday_Weekend"] = (frame["Holiday"] * frame["Weekend"]).astype(int)
        holiday_dates = dates.where(frame["Holiday"].eq(1))
        days_since_holiday = (dates - holiday_dates.ffill()).dt.days
        days_until_holiday = (holiday_dates.bfill() - dates).dt.days
        frame["Days_Since_Holiday_Capped"] = (
            days_since_holiday.clip(upper=30).fillna(31).astype(int)
        )
        frame["Days_Until_Holiday_Capped"] = (
            days_until_holiday.clip(upper=30).fillna(31).astype(int)
        )

    @staticmethod
    def _compute_demand_features(frame: pd.DataFrame) -> None:
        demand = frame[TARGET_COLUMN].astype(float)
        for lag in [1, 2, 7, 14, 28, 364, 365, 371]:
            frame[f"Demand_Lag_{lag}"] = demand.shift(lag)
        past_demand = demand.shift(1)
        for window in [7, 14, 28]:
            frame[f"Demand_Rolling_Mean_{window}"] = past_demand.rolling(
                window, min_periods=window
            ).mean()
        for window in [7, 28]:
            frame[f"Demand_Rolling_Std_{window}"] = past_demand.rolling(
                window, min_periods=window
            ).std()
        frame["Demand_Rolling_Min_7"] = past_demand.rolling(7, min_periods=7).min()
        frame["Demand_Rolling_Max_7"] = past_demand.rolling(7, min_periods=7).max()
        frame["Demand_EWM_7"] = (
            past_demand.ewm(span=7, adjust=False).mean().where(past_demand.notna())
        )
        frame["Demand_EWM_28"] = (
            past_demand.ewm(span=28, adjust=False).mean().where(past_demand.notna())
        )
        frame["Demand_Change_1"] = frame["Demand_Lag_1"] - frame["Demand_Lag_2"]
        frame["Demand_Change_7"] = frame["Demand_Lag_1"] - frame["Demand_Lag_7"]
        frame["Demand_Trend_7_28"] = (
            frame["Demand_Rolling_Mean_7"] - frame["Demand_Rolling_Mean_28"]
        )
