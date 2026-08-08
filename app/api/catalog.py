"""Dataset-backed values exposed as API choices."""

from __future__ import annotations

import csv
import re
from enum import StrEnum
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEATURE_DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "historical"
    / "energy_consumption_feature_engineered.csv"
)
MODEL_TRAINING_SPLITS = frozenset({"train", "validation"})


def _enum_member_name(value: str) -> str:
    name = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    if not name or name[0].isdigit():
        name = f"VALUE_{name}"
    return name


def _load_holiday_names() -> tuple[str, ...]:
    """Read real holiday labels from the full dataset for validation and OpenAPI."""

    if not FEATURE_DATA_PATH.is_file():
        raise RuntimeError(f"Feature dataset was not found: {FEATURE_DATA_PATH}")

    names: set[str] = set()
    with FEATURE_DATA_PATH.open("r", encoding="utf-8", newline="") as file_handle:
        for row in csv.DictReader(file_handle):
            if row.get("Holiday") == "1" and row.get("Holiday_Name"):
                names.add(row["Holiday_Name"].strip())

    if not names:
        raise RuntimeError("The feature dataset does not contain any named holidays.")
    return tuple(sorted(names))


HOLIDAY_NAMES = _load_holiday_names()


def _load_training_temperature_range() -> tuple[float, float]:
    """Return the exact temperature range represented during model fitting."""

    temperatures: list[float] = []
    with FEATURE_DATA_PATH.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        temperature_columns = [
            column for column in (reader.fieldnames or []) if column.startswith("Temp (")
        ]
        if len(temperature_columns) != 1:
            raise RuntimeError(
                f"Expected one temperature column in feature data, found {temperature_columns}"
            )
        temperature_column = temperature_columns[0]
        for row in reader:
            if row.get("Split") in MODEL_TRAINING_SPLITS and row.get(temperature_column):
                temperatures.append(float(row[temperature_column]))

    if not temperatures:
        raise RuntimeError("No model-training temperatures were found in the feature dataset.")
    return min(temperatures), max(temperatures)


TEMPERATURE_MIN_C, TEMPERATURE_MAX_C = _load_training_temperature_range()
TEMPERATURE_STEP_C = 0.1

# A string enum makes the dataset's holiday values appear as a dropdown in the
# generated OpenAPI/Swagger documentation while still enforcing exact values.
HolidayName = StrEnum(
    "HolidayName",
    {_enum_member_name(value): value for value in HOLIDAY_NAMES},
    module=__name__,
)
