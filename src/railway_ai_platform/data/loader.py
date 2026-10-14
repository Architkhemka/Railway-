"""Common data-loader interface for synthetic and file-backed datasets."""

import csv
from pathlib import Path
from typing import Literal, Protocol

from railway_ai_platform.data.generators import (
    DataRecord,
    GenerationOptions,
    generate_bookings,
    generate_cancellations,
    generate_fares,
    generate_fraud_events,
    generate_support_conversations,
    generate_train_delays,
    generate_train_schedules,
    generate_user_behavior,
)

DatasetName = Literal[
    "schedules",
    "bookings",
    "cancellations",
    "delays",
    "fares",
    "user_behavior",
    "support_conversations",
    "fraud_events",
]

DATASET_NAMES: tuple[DatasetName, ...] = (
    "schedules",
    "bookings",
    "cancellations",
    "delays",
    "fares",
    "user_behavior",
    "support_conversations",
    "fraud_events",
)

_GENERATORS = {
    "schedules": generate_train_schedules,
    "bookings": generate_bookings,
    "cancellations": generate_cancellations,
    "delays": generate_train_delays,
    "fares": generate_fares,
    "user_behavior": generate_user_behavior,
    "support_conversations": generate_support_conversations,
    "fraud_events": generate_fraud_events,
}


class DataLoader(Protocol):
    """Contract used by services that consume railway datasets."""

    def load(self, dataset: DatasetName) -> list[DataRecord]:
        """Load one named dataset as a list of typed records."""


class SyntheticDataLoader:
    """Generate one of the supported synthetic datasets on demand."""

    def __init__(self, options: GenerationOptions | None = None) -> None:
        self.options = options or GenerationOptions()

    def load(self, dataset: DatasetName) -> list[DataRecord]:
        try:
            generator = _GENERATORS[dataset]
        except KeyError as error:
            raise ValueError(f"unsupported dataset: {dataset}") from error
        return generator(self.options)


class CsvDataLoader:
    """Load externally supplied CSV datasets using the shared loader contract."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()

    def load(self, dataset: DatasetName) -> list[DataRecord]:
        if dataset not in DATASET_NAMES:
            raise ValueError(f"unsupported dataset: {dataset}")
        path = (self.directory / f"{dataset}.csv").resolve()
        if path.parent != self.directory:
            raise ValueError("dataset path must remain inside the configured directory")
        with path.open(newline="", encoding="utf-8") as csv_file:
            return [
                {key: _parse_value(value) for key, value in row.items() if key is not None}
                for row in csv.DictReader(csv_file)
            ]


def _parse_value(value: str | None) -> str | int | float | bool | None:
    if value is None or value == "":
        return None
    if value == "True":
        return True
    if value == "False":
        return False
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value
