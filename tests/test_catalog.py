"""Checks for dataset-backed choices and the public model registry."""

from app.api.catalog import (
    HOLIDAY_NAMES,
    TEMPERATURE_MAX_C,
    TEMPERATURE_MIN_C,
)
from app.api.model_registry import MODEL_REGISTRY, ModelId, model_definitions


def test_catalog_exposes_sorted_holidays_and_temperature_bounds() -> None:
    assert HOLIDAY_NAMES
    assert tuple(sorted(HOLIDAY_NAMES)) == HOLIDAY_NAMES
    assert "Not a Holiday" not in HOLIDAY_NAMES
    assert 15 < TEMPERATURE_MIN_C < TEMPERATURE_MAX_C < 45


def test_model_numbers_are_stable_and_complete() -> None:
    definitions = model_definitions()

    assert len(definitions) == 11
    assert [int(item.id) for item in definitions] == list(range(1, 12))
    assert set(MODEL_REGISTRY) == set(ModelId)
    assert len({item.artifact_filename for item in definitions}) == 11


def test_every_registered_model_artifact_exists() -> None:
    missing = [
        definition.artifact_path
        for definition in model_definitions()
        if not definition.artifact_path.is_file()
    ]

    assert missing == []
