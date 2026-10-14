"""Reproducible synthetic passenger and railway datasets."""

import random
from datetime import UTC, datetime, timedelta
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field

DataRecord: TypeAlias = dict[str, str | int | float | bool | None]

_BASE_DATE = datetime(2026, 1, 1, tzinfo=UTC)
_ROUTES = (
    ("PUNE", "DELHI"),
    ("MUMBAI", "BENGALURU"),
    ("CHENNAI", "HYDERABAD"),
    ("KOLKATA", "AHMEDABAD"),
    ("JAIPUR", "LUCKNOW"),
)
_CLASSES = ("SL", "3A", "2A", "1A", "CC")
_FARES = {"SL": 420, "3A": 980, "2A": 1460, "1A": 2480, "CC": 610}


class GenerationOptions(BaseModel):
    """Seed, size, and bounded drift/anomaly controls shared by all generators."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int = Field(default=100, ge=1, le=100_000)
    seed: int = 42
    drift_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    drift_start_fraction: float = Field(default=0.5, ge=0.0, le=1.0)
    anomaly_rate: float = Field(default=0.0, ge=0.0, le=1.0)


def _rng(options: GenerationOptions) -> random.Random:
    return random.Random(options.seed)


def _timestamp(value: datetime) -> str:
    return value.isoformat()


def _apply_effects(
    records: list[DataRecord],
    options: GenerationOptions,
    rng: random.Random,
    numeric_fields: tuple[str, ...],
) -> list[DataRecord]:
    output: list[DataRecord] = []
    count = len(records)
    drift_start = min(count, int(count * options.drift_start_fraction))
    drifted_count = count - drift_start
    anomaly_count = min(count, int(count * options.anomaly_rate + 0.5))
    anomalous_indices = set(rng.sample(range(count), anomaly_count)) if anomaly_count else set()

    for index, source in enumerate(records):
        record = dict(source)
        is_drifted = options.drift_strength > 0 and index >= drift_start
        record["is_drifted"] = is_drifted
        record["is_anomaly"] = index in anomalous_indices

        if is_drifted:
            drift_position = index - drift_start + 1
            multiplier = 1 + options.drift_strength * drift_position / max(1, drifted_count)
            for field in numeric_fields:
                value = record[field]
                if isinstance(value, bool) or not isinstance(value, int | float):
                    continue
                changed = value * multiplier
                record[field] = round(changed) if isinstance(value, int) else round(changed, 4)

        if index in anomalous_indices:
            field = numeric_fields[index % len(numeric_fields)]
            value = record[field]
            if isinstance(value, int | float) and not isinstance(value, bool):
                changed = max(value * 4, value + 10)
                record[field] = round(changed) if isinstance(value, int) else round(changed, 4)
        output.append(record)
    return output


def generate_train_schedules(options: GenerationOptions) -> list[DataRecord]:
    rng = _rng(options)
    records: list[DataRecord] = []
    for index in range(options.count):
        origin, destination = _ROUTES[index % len(_ROUTES)]
        duration = rng.randint(360, 1_200)
        departure = _BASE_DATE + timedelta(days=index, hours=rng.randrange(24))
        arrival = departure + timedelta(minutes=duration)
        records.append(
            {
                "id": f"SCH-{index + 1:06d}",
                "train_number": f"TRN-{1001 + index % 500:04d}",
                "train_name": f"Synthetic Express {index % 40 + 1}",
                "origin": origin,
                "destination": destination,
                "departure_at": _timestamp(departure),
                "arrival_at": _timestamp(arrival),
                "duration_minutes": duration,
            }
        )
    return _apply_effects(records, options, rng, ("duration_minutes",))


def generate_bookings(options: GenerationOptions) -> list[DataRecord]:
    rng = _rng(options)
    records: list[DataRecord] = []
    for index in range(options.count):
        travel_class = rng.choice(_CLASSES)
        status = rng.choices(("WL", "RAC", "CNF"), weights=(0.35, 0.2, 0.45), k=1)[0]
        travel_date = _BASE_DATE + timedelta(days=30 + index % 180)
        if status == "WL":
            waitlist = rng.randint(1, 80)
        elif status == "RAC":
            waitlist = rng.randint(1, 10)
        else:
            waitlist = None
        records.append(
            {
                "id": f"BKG-{index + 1:06d}",
                "user_id": f"USR-{index % 1_000 + 1:06d}",
                "schedule_id": f"SCH-{index % options.count + 1:06d}",
                "booked_at": _timestamp(travel_date - timedelta(days=rng.randint(1, 120))),
                "travel_class": travel_class,
                "status": status,
                "waitlist_position": waitlist,
                "fare_amount": _FARES[travel_class],
            }
        )
    return _apply_effects(records, options, rng, ("fare_amount",))


def generate_cancellations(options: GenerationOptions) -> list[DataRecord]:
    rng = _rng(options)
    records: list[DataRecord] = []
    for index in range(options.count):
        status = rng.choice(("WL", "RAC", "CNF"))
        days_before = rng.randint(0, 60)
        departure = _BASE_DATE + timedelta(days=30 + index % 180)
        records.append(
            {
                "id": f"CAN-{index + 1:06d}",
                "booking_id": f"BKG-{index + 1:06d}",
                "cancelled_at": _timestamp(departure - timedelta(days=days_before)),
                "days_before_departure": days_before,
                "status_at_cancellation": status,
                "seats_released": status == "CNF" or rng.random() < 0.35,
            }
        )
    return _apply_effects(records, options, rng, ("days_before_departure",))


def generate_train_delays(options: GenerationOptions) -> list[DataRecord]:
    rng = _rng(options)
    records: list[DataRecord] = []
    for index in range(options.count):
        schedule_id = f"SCH-{index % options.count + 1:06d}"
        records.append(
            {
                "id": f"DLY-{index + 1:06d}",
                "schedule_id": schedule_id,
                "observed_at": _timestamp(_BASE_DATE + timedelta(days=index, hours=12)),
                "station_code": rng.choice(_ROUTES[index % len(_ROUTES)]),
                "delay_minutes": max(0, int(rng.gauss(18, 16))),
                "congestion_level": round(rng.random(), 4),
            }
        )
    return _apply_effects(records, options, rng, ("delay_minutes",))


def generate_fares(options: GenerationOptions) -> list[DataRecord]:
    rng = _rng(options)
    records: list[DataRecord] = []
    for index in range(options.count):
        travel_class = rng.choice(_CLASSES)
        base_fare = _FARES[travel_class]
        demand_index = round(rng.uniform(0.2, 1.0), 4)
        records.append(
            {
                "id": f"FAR-{index + 1:06d}",
                "schedule_id": f"SCH-{index % options.count + 1:06d}",
                "observed_at": _timestamp(_BASE_DATE + timedelta(days=index)),
                "travel_class": travel_class,
                "base_fare": base_fare,
                "fare_amount": round(base_fare * (1 + demand_index * 0.2), 2),
                "demand_index": demand_index,
            }
        )
    return _apply_effects(records, options, rng, ("base_fare", "fare_amount", "demand_index"))


def generate_user_behavior(options: GenerationOptions) -> list[DataRecord]:
    rng = _rng(options)
    records: list[DataRecord] = []
    for index in range(options.count):
        searches = rng.randint(1, 40)
        bookings = min(searches, rng.randint(0, 5))
        records.append(
            {
                "id": f"UBE-{index + 1:06d}",
                "user_id": f"USR-{index % 1_000 + 1:06d}",
                "observed_at": _timestamp(_BASE_DATE + timedelta(days=index)),
                "search_count": searches,
                "booking_count": bookings,
                "cancellation_count": rng.randint(0, bookings),
                "session_duration_seconds": rng.randint(30, 3_600),
                "bot_score": round(rng.random(), 4),
            }
        )
    return _apply_effects(
        records,
        options,
        rng,
        ("search_count", "booking_count", "cancellation_count", "session_duration_seconds"),
    )


def generate_support_conversations(options: GenerationOptions) -> list[DataRecord]:
    rng = _rng(options)
    messages = {
        "en": "Please share the status of my synthetic journey.",
        "hi": "कृपया मेरी यात्रा की स्थिति बताएं।",
        "mr": "कृपया माझ्या प्रवासाची स्थिती सांगा.",
        "kn": "ದಯವಿಟ್ಟು ನನ್ನ ಪ್ರಯಾಣದ ಸ್ಥಿತಿಯನ್ನು ತಿಳಿಸಿ.",
    }
    intents = ("pnr_status", "refund", "cancellation_policy", "booking_help", "journey_info")
    locales = tuple(messages)
    records: list[DataRecord] = []
    for index in range(options.count):
        locale = rng.choice(locales)
        records.append(
            {
                "id": f"SUP-{index + 1:06d}",
                "user_id": f"USR-{index % 1_000 + 1:06d}",
                "locale": locale,
                "intent": rng.choice(intents),
                "message": messages[locale],
                "satisfaction_score": round(rng.uniform(0.2, 1.0), 4),
                "created_at": _timestamp(_BASE_DATE + timedelta(minutes=index * 15)),
            }
        )
    return _apply_effects(records, options, rng, ("satisfaction_score",))


def generate_fraud_events(options: GenerationOptions) -> list[DataRecord]:
    rng = _rng(options)
    event_types = ("booking_attempt", "payment_retry", "rapid_search", "account_login")
    records: list[DataRecord] = []
    for index in range(options.count):
        request_rate = rng.randint(1, 90)
        payment_attempts = rng.randint(0, 6)
        records.append(
            {
                "id": f"FRD-{index + 1:06d}",
                "user_id": f"USR-{index % 1_000 + 1:06d}",
                "event_type": rng.choice(event_types),
                "happened_at": _timestamp(_BASE_DATE + timedelta(minutes=index * 3)),
                "requests_per_minute": request_rate,
                "payment_attempts": payment_attempts,
                "risk_score": round(min(1.0, request_rate / 100 + payment_attempts / 20), 4),
                "is_bot": request_rate >= 70 or payment_attempts >= 5,
            }
        )
    return _apply_effects(records, options, rng, ("requests_per_minute", "payment_attempts"))
