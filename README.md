# AI-Powered Intelligent Railway Travel & Autonomous AI Governance Platform

Phase 0 established the project scaffold, quality tooling, CI, and local development dependencies. Phase 1 adds shared configuration, logging, JWT/RBAC, database models and migrations, plus reproducible synthetic datasets. Phase 2 adds ticket confirmation, train delay/disruption, and dynamic fare prediction services.

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

The local stack exposes PostgreSQL on port 5432, Redis on port 6379, and MLflow on port 5000. Starting Compose also builds and starts the Phase 2 services on ports 8001-8003. MLflow's tracking UI is available at <http://localhost:5000>. These services are for local development only; MLflow is not configured with authentication.

## Quality checks

```bash
make check
pre-commit run --all-files
```

Individual commands are available through `make lint`, `make typecheck`, and `make test`. Run `make help` to see the available targets. Model and service tests run with `pytest`.

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

## Phase 2 prediction services

Each service trains a seeded model from the Phase 1 synthetic data, logs training parameters and metrics to MLflow, and registers the fitted model before starting its API container. Configure `MLFLOW_TRACKING_URI` for local model training; Docker Compose points each service at the internal MLflow endpoint. The default synthetic training size is 1,200 rows and can be changed with `MODEL_TRAINING_ROWS`.

| Service | Local URL | Prediction endpoint |
| --- | --- | --- |
| Ticket confirmation | <http://localhost:8001> | `POST /v1/ticket/predict` |
| Delay and disruption | <http://localhost:8002> | `POST /v1/delay/predict` |
| Dynamic fare | <http://localhost:8003> | `POST /v1/fare/predict` |

All services expose `GET /health` and `GET /metrics`. Successful predictions include the registered model version, confidence, and SHAP feature contributions. The ticket request takes `ticket_status` (`WL` or `RAC`), `waitlist_position`, `days_until_departure`, and `travel_class`. The delay request takes `train_number`, `station_code`, `historical_delay_minutes`, and `observation_hour`. The fare request takes `travel_class`, `base_fare`, `current_fare`, `demand_index`, and `days_until_departure`. Example:

```bash
curl -X POST http://localhost:8001/v1/ticket/predict \
  -H 'Content-Type: application/json' \
  -d '{"ticket_status":"WL","waitlist_position":8,"days_until_departure":12,"travel_class":"3A"}'
```

Model-registration, model-load, and prediction governance events are written to the shared hash-chained JSONL audit volume (`data/audit/events.jsonl` for local non-container runs). Delay alternatives are generic suggestions, not live timetable options; fare windows are model estimates, not guaranteed prices. Models train on synthetic labels and are demonstration baselines, not production forecasts.

## Project references

- [Problem statement](docs/problem_statement.md)
- [Architecture](ARCHITECTURE.md)
- [Phase plan and repository conventions](.github/copilot-instructions.md)

## Current scope

This repository currently contains Phase 0-2 foundations and prediction services. Recommendation and fraud models, the full governance workflows, agents, and passenger-facing applications remain future-phase work.
