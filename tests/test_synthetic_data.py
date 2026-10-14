import csv
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from railway_ai_platform.data.cli import main
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
from railway_ai_platform.data.loader import (
    DATASET_NAMES,
    CsvDataLoader,
    DatasetName,
    SyntheticDataLoader,
)

_GENERATORS: tuple[Callable[[GenerationOptions], list[DataRecord]], ...] = (
    generate_train_schedules,
    generate_bookings,
    generate_cancellations,
    generate_train_delays,
    generate_fares,
    generate_user_behavior,
    generate_support_conversations,
    generate_fraud_events,
)


def _number(record: DataRecord, field: str) -> int | float:
    value = record[field]
    assert isinstance(value, int | float) and not isinstance(value, bool)
    return value


@pytest.mark.parametrize("generator", _GENERATORS)
def test_generators_are_seeded_and_emit_requested_count(
    generator: Callable[[GenerationOptions], list[DataRecord]],
) -> None:
    options = GenerationOptions(count=12, seed=81)

    first = generator(options)
    second = generator(options)

    assert len(first) == 12
    assert first == second
    assert all("is_drifted" in row and "is_anomaly" in row for row in first)


def test_bookings_and_cancellations_cover_confirmation_statuses() -> None:
    options = GenerationOptions(count=100, seed=2)

    booking_statuses = {row["status"] for row in generate_bookings(options)}
    cancellation_statuses = {
        row["status_at_cancellation"] for row in generate_cancellations(options)
    }

    assert booking_statuses == {"WL", "RAC", "CNF"}
    assert cancellation_statuses == {"WL", "RAC", "CNF"}


def test_drift_and_anomalies_are_controllable_and_marked() -> None:
    baseline = generate_fares(GenerationOptions(count=20, seed=19))
    drifted = generate_fares(
        GenerationOptions(
            count=20,
            seed=19,
            drift_strength=1.0,
            drift_start_fraction=0.5,
        )
    )
    anomalous = generate_fares(GenerationOptions(count=20, seed=19, anomaly_rate=0.25))

    assert [_number(row, "fare_amount") for row in drifted[:10]] == [
        _number(row, "fare_amount") for row in baseline[:10]
    ]
    assert _number(drifted[10], "fare_amount") > _number(baseline[10], "fare_amount")
    assert sum(row["is_drifted"] is True for row in drifted) == 10
    assert sum(row["is_anomaly"] is True for row in anomalous) == 5
    assert any(
        anomalous[index][field] != baseline[index][field]
        for index in range(len(baseline))
        if anomalous[index]["is_anomaly"]
        for field in ("base_fare", "fare_amount", "demand_index")
    )


def test_generation_options_reject_out_of_range_effects() -> None:
    with pytest.raises(ValidationError):
        GenerationOptions(count=0)
    with pytest.raises(ValidationError):
        GenerationOptions(anomaly_rate=1.1)


def test_loader_protocol_supports_all_named_datasets() -> None:
    loader = SyntheticDataLoader(GenerationOptions(count=3, seed=5))

    assert len(DATASET_NAMES) == 8
    assert all(len(loader.load(dataset)) == 3 for dataset in DATASET_NAMES)


def test_cli_exports_csv_and_csv_loader_reads_it(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"

    assert main(["--output-dir", str(output_dir), "--count", "4", "--seed", "9"]) == 0
    rows = CsvDataLoader(output_dir).load("bookings")

    assert len(rows) == 4
    assert isinstance(rows[0]["fare_amount"], int)
    with (output_dir / "schedules.csv").open(encoding="utf-8", newline="") as source:
        assert len(list(csv.DictReader(source))) == 4


def test_csv_loader_rejects_unknown_dataset(tmp_path: Path) -> None:
    loader = CsvDataLoader(tmp_path)

    with pytest.raises(ValueError, match="unsupported dataset"):
        loader.load(cast(DatasetName, "../../etc/passwd"))


def test_cli_rejects_invalid_generation_options(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--output-dir", str(tmp_path), "--count", "0"])
