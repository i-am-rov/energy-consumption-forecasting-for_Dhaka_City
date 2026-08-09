"""Tests for leakage-safe recursive feature construction."""

from datetime import timedelta

import pytest

from app.api.features import TARGET_COLUMN, FeatureRepository, FeatureValidationError


@pytest.fixture(scope="module")
def repository() -> FeatureRepository:
    return FeatureRepository()


def test_forecast_window_starts_after_recursive_history(
    repository: FeatureRepository,
) -> None:
    assert repository.allowed_forecast_date == (
        repository.latest_recursive_history_date + timedelta(days=1)
    )
    assert repository.forecast_horizon_end_date == (
        repository.allowed_forecast_date + timedelta(days=6)
    )


def test_feature_row_matches_saved_model_manifest(
    repository: FeatureRepository,
) -> None:
    row = repository.build_feature_row(
        repository.allowed_forecast_date,
        daily_temperature_c=30.0,
        is_holiday=False,
        holiday_name=None,
    )

    assert row.shape == (1, len(repository.feature_columns))
    assert tuple(row.columns) == repository.feature_columns
    assert TARGET_COLUMN not in row.columns
    assert not row.isna().any().any()


def test_repository_rejects_non_next_forecast_date(
    repository: FeatureRepository,
) -> None:
    invalid_date = repository.allowed_forecast_date + timedelta(days=1)

    with pytest.raises(FeatureValidationError, match="first forecast date"):
        repository.validate_forecast_date(invalid_date)
