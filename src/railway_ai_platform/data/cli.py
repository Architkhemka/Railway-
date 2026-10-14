"""Command-line interface for reproducible synthetic CSV generation."""

import argparse
import csv
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from railway_ai_platform.data.generators import GenerationOptions
from railway_ai_platform.data.loader import DATASET_NAMES, SyntheticDataLoader


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/generated"))
    parser.add_argument("--count", type=int, default=100, help="rows per dataset")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--drift-strength", type=float, default=0.0)
    parser.add_argument("--drift-start-fraction", type=float, default=0.5)
    parser.add_argument("--anomaly-rate", type=float, default=0.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        options = GenerationOptions(
            count=arguments.count,
            seed=arguments.seed,
            drift_strength=arguments.drift_strength,
            drift_start_fraction=arguments.drift_start_fraction,
            anomaly_rate=arguments.anomaly_rate,
        )
    except ValidationError as error:
        parser.error(str(error))

    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    loader = SyntheticDataLoader(options)
    for dataset in DATASET_NAMES:
        records = loader.load(dataset)
        output_path = arguments.output_dir / f"{dataset}.csv"
        with output_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
        print(f"Wrote {len(records)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
