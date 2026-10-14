# AI-Powered Intelligent Railway Travel & Autonomous AI Governance Platform

Phase 0 established the project scaffold, quality tooling, CI, and local development dependencies. Phase 1 adds shared configuration, logging, JWT/RBAC, database models and migrations, plus reproducible synthetic datasets. Passenger-facing and governance services remain future-phase work.

## Prerequisites

- Python 3.11
- Docker Engine with the Compose plugin
- GNU Make (optional; the commands below can also be run directly)

## Local setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
make services-up
```

The local dependency stack exposes PostgreSQL on port 5432, Redis on port 6379, and MLflow on port 5000. The MLflow tracking UI is available at <http://localhost:5000>. These services are for local development only; MLflow is not configured with authentication.

## Quality checks

```bash
make check
pre-commit run --all-files
```

Individual commands are available through `make lint`, `make typecheck`, and `make test`. Run `make help` to see the available targets.

## Synthetic data

Generate all eight seeded datasets as CSV files (schedules, bookings, cancellations, delays, fares, user behavior, support conversations, and fraud events):

```bash
railway-generate-data --output-dir data/generated --count 500 --seed 42
```

The same command is available as `python -m railway_ai_platform.data.cli`. To demonstrate controlled drift and anomalies, choose a drift magnitude from `0` to `1`, the fraction of each dataset where drift starts, and an anomaly fraction:

```bash
railway-generate-data \
	--output-dir data/generated/drifted \
	--count 500 \
	--seed 42 \
	--drift-strength 0.6 \
	--drift-start-fraction 0.7 \
	--anomaly-rate 0.03
```

The seed makes each dataset reproducible. Every row contains `is_drifted` and `is_anomaly` flags. The `DataLoader` protocol allows consumers to use `SyntheticDataLoader` or substitute `CsvDataLoader` pointed at a generated or externally prepared CSV directory. Generator outputs use synthetic identifiers and templated support text, not real passenger data.

## Shared libraries and database

`railway_ai_platform.config.Settings` reads connection URLs and runtime settings from environment variables or `.env`. JWT signing is disabled until `JWT_SECRET` is explicitly configured to a random value of at least 32 characters. Roles are `passenger`, `analyst`, `governance-admin`, and `auditor`.

With the local PostgreSQL service running and `.env` configured, apply the initial schema using `make db-upgrade` (or `alembic upgrade head`). The Phase 1 schema covers schedules, bookings, cancellations, delays, fares, user behavior, support conversations, and fraud events.

## Project references

- [Problem statement](docs/problem_statement.md)
- [Architecture](ARCHITECTURE.md)
- [Phase plan and repository conventions](.github/copilot-instructions.md)

## Current scope

This repository currently contains Phase 0 and Phase 1 foundations. Model services, governance workflows, and passenger-facing applications are planned work and are not available yet.
