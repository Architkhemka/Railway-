.PHONY: help install lint format typecheck test check data-generate db-upgrade services-up services-down services-logs

help:
	@printf '%s\n' \
	  'install        Install the package and development tools' \
	  'lint           Run Ruff lint checks' \
	  'format         Format Python files with Ruff' \
	  'typecheck      Run mypy' \
	  'test           Run pytest with coverage' \
	  'check          Run lint, formatting, type checks, and tests' \
	  'data-generate  Generate seeded synthetic CSV datasets' \
	  'db-upgrade     Apply Alembic migrations to the configured database' \
	  'services-up    Start PostgreSQL, Redis, and MLflow' \
	  'services-down  Stop local dependency services' \
	  'services-logs  Follow local dependency service logs'

install:
	python -m pip install -e '.[dev]'

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src services

test:
	pytest

data-generate:
	railway-generate-data

db-upgrade:
	alembic upgrade head

check: lint
	ruff format --check .
	mypy src services
	pytest

services-up:
	@test -f .env || (printf '%s\n' 'Copy .env.example to .env before starting services.'; exit 1)
	docker compose --env-file .env up -d --build

services-down:
	docker compose down

services-logs:
	docker compose logs -f
