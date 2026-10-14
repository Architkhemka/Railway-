import json
import logging
import sys
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, inspect

from railway_ai_platform.auth import (
    AuthenticationError,
    AuthorizationError,
    JWTAuth,
    Principal,
    Role,
    authorize,
)
from railway_ai_platform.config import Settings
from railway_ai_platform.db import Base
from railway_ai_platform.logging import JSONFormatter, configure_logging


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "database_url": "postgresql+psycopg://localhost/railway",
        "redis_url": "redis://localhost:6379/0",
    }
    values.update(overrides)
    return Settings(**values)


def test_settings_load_required_connections_and_optional_secret() -> None:
    settings = make_settings()

    assert settings.database_url == "postgresql+psycopg://localhost/railway"
    assert settings.jwt_secret is None


def test_settings_reject_nonpositive_jwt_expiration() -> None:
    with pytest.raises(ValidationError):
        make_settings(jwt_access_token_expire_minutes=0)


def test_jwt_round_trip_and_role_authorization() -> None:
    auth = JWTAuth(make_settings(jwt_secret=SecretStr("s" * 32)))
    token = auth.issue_token("synthetic-user-1", Role.ANALYST)

    principal = auth.verify_token(token)
    authorize(principal, Role.ANALYST, Role.GOVERNANCE_ADMIN)

    assert principal == Principal(subject="synthetic-user-1", role=Role.ANALYST)


def test_jwt_rejects_invalid_token_and_unconfigured_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        JWTAuth(make_settings())
    with pytest.raises(ValueError, match="at least 32"):
        JWTAuth(make_settings(jwt_secret="short"))

    auth = JWTAuth(make_settings(jwt_secret="s" * 32))
    with pytest.raises(AuthenticationError):
        auth.verify_token("not-a-jwt")
    with pytest.raises(ValueError, match="subject"):
        auth.issue_token("  ", Role.PASSENGER)


def test_authorize_rejects_roles_outside_allowlist() -> None:
    with pytest.raises(AuthorizationError):
        authorize(Principal("synthetic-user-2", Role.PASSENGER), Role.AUDITOR)


def test_json_formatter_structures_fields_and_redacts_secrets() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "event", (), None)
    record.request_id = "req-1"
    record.authorization = "Bearer sensitive"

    payload = json.loads(JSONFormatter().format(record))

    assert payload["message"] == "event"
    assert payload["request_id"] == "req-1"
    assert payload["authorization"] == "[REDACTED]"
    assert "timestamp" in payload


def test_json_formatter_redacts_nested_fields_and_formats_exceptions() -> None:
    try:
        raise RuntimeError("synthetic failure")
    except RuntimeError:
        record = logging.LogRecord("test", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    record.context = {
        "email": "synthetic@example.invalid",
        "items": [{"jwt": "synthetic-token"}],
    }

    payload = json.loads(JSONFormatter().format(record))

    assert payload["context"]["email"] == "[REDACTED]"
    assert payload["context"]["items"][0]["jwt"] == "[REDACTED]"
    assert "RuntimeError: synthetic failure" in payload["exception"]


def test_configure_logging_installs_json_formatter(monkeypatch: pytest.MonkeyPatch) -> None:
    root_logger = logging.getLogger()
    monkeypatch.setattr(root_logger, "handlers", [])

    configure_logging("DEBUG")

    assert root_logger.level == logging.DEBUG
    assert len(root_logger.handlers) == 1
    assert isinstance(root_logger.handlers[0].formatter, JSONFormatter)


def test_models_register_all_phase_one_tables() -> None:
    expected = {
        "train_schedules",
        "bookings",
        "cancellations",
        "train_delays",
        "fare_records",
        "user_behavior",
        "support_conversations",
        "fraud_events",
    }

    assert set(Base.metadata.tables) == expected


def test_models_create_database_schema() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables)
