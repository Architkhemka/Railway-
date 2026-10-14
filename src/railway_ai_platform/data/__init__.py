"""Seeded synthetic datasets and interchangeable data loaders."""

from railway_ai_platform.data.generators import (
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
from railway_ai_platform.data.loader import CsvDataLoader, DataLoader, SyntheticDataLoader

__all__ = [
    "CsvDataLoader",
    "DataLoader",
    "GenerationOptions",
    "SyntheticDataLoader",
    "generate_bookings",
    "generate_cancellations",
    "generate_fares",
    "generate_fraud_events",
    "generate_support_conversations",
    "generate_train_delays",
    "generate_train_schedules",
    "generate_user_behavior",
]
