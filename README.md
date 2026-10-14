# AI-Powered Intelligent Railway Travel & Autonomous AI Governance Platform

Phase 0 establishes the project scaffold, quality tooling, CI, and local development dependencies. Passenger services and governance capabilities are described in the architecture but are not implemented in this phase.

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

## Project references

- [Problem statement](docs/problem_statement.md)
- [Architecture](ARCHITECTURE.md)
- [Phase plan and repository conventions](.github/copilot-instructions.md)

## Current scope

This repository currently contains Phase 0 setup only. Model services, governance workflows, data generators, and passenger-facing applications are planned work and are not available yet.
