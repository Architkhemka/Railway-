"""Create Phase 1 railway operational data tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_phase_one_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "train_schedules",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("train_number", sa.String(length=20), nullable=False),
        sa.Column("train_name", sa.String(length=120), nullable=False),
        sa.Column("origin", sa.String(length=12), nullable=False),
        sa.Column("destination", sa.String(length=12), nullable=False),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("origin <> destination", name="ck_schedule_distinct_stations"),
        sa.CheckConstraint("duration_minutes > 0", name="ck_schedule_positive_duration"),
        sa.UniqueConstraint("train_number", "departure_at", name="uq_schedule_train_departure"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_train_schedules_train_number", "train_schedules", ["train_number"])

    op.create_table(
        "bookings",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("schedule_id", sa.String(length=40), nullable=False),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("travel_class", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=3), nullable=False),
        sa.Column("waitlist_position", sa.Integer(), nullable=True),
        sa.Column("fare_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('WL', 'RAC', 'CNF')", name="ck_booking_status"),
        sa.CheckConstraint(
            "waitlist_position IS NULL OR waitlist_position >= 0",
            name="ck_booking_waitlist",
        ),
        sa.CheckConstraint("fare_amount >= 0", name="ck_booking_nonnegative_fare"),
        sa.ForeignKeyConstraint(["schedule_id"], ["train_schedules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])

    op.create_table(
        "cancellations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("booking_id", sa.String(length=40), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("days_before_departure", sa.Integer(), nullable=False),
        sa.Column("status_at_cancellation", sa.String(length=3), nullable=False),
        sa.Column("seats_released", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status_at_cancellation IN ('WL', 'RAC', 'CNF')",
            name="ck_cancellation_status",
        ),
        sa.CheckConstraint("days_before_departure >= 0", name="ck_cancellation_days_before"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id"),
    )

    op.create_table(
        "train_delays",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("schedule_id", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("station_code", sa.String(length=12), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), nullable=False),
        sa.Column("congestion_level", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("delay_minutes >= 0", name="ck_delay_nonnegative_minutes"),
        sa.CheckConstraint(
            "congestion_level >= 0 AND congestion_level <= 1",
            name="ck_delay_congestion_range",
        ),
        sa.ForeignKeyConstraint(["schedule_id"], ["train_schedules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "fare_records",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("schedule_id", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("travel_class", sa.String(length=8), nullable=False),
        sa.Column("base_fare", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("fare_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("demand_index", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("base_fare >= 0 AND fare_amount >= 0", name="ck_fare_nonnegative"),
        sa.CheckConstraint("demand_index >= 0", name="ck_fare_demand_nonnegative"),
        sa.ForeignKeyConstraint(["schedule_id"], ["train_schedules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user_behavior",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("search_count", sa.Integer(), nullable=False),
        sa.Column("booking_count", sa.Integer(), nullable=False),
        sa.Column("cancellation_count", sa.Integer(), nullable=False),
        sa.Column("session_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("bot_score", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "search_count >= 0 AND booking_count >= 0 AND cancellation_count >= 0",
            name="ck_behavior_counts",
        ),
        sa.CheckConstraint("session_duration_seconds >= 0", name="ck_behavior_duration"),
        sa.CheckConstraint("bot_score >= 0 AND bot_score <= 1", name="ck_behavior_bot_score"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_behavior_user_id", "user_behavior", ["user_id"])

    op.create_table(
        "support_conversations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("locale", sa.String(length=2), nullable=False),
        sa.Column("intent", sa.String(length=40), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("satisfaction_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("locale IN ('en', 'hi', 'mr', 'kn')", name="ck_support_locale"),
        sa.CheckConstraint(
            "satisfaction_score IS NULL OR (satisfaction_score >= 0 AND satisfaction_score <= 1)",
            name="ck_support_satisfaction",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_conversations_user_id", "support_conversations", ["user_id"])

    op.create_table(
        "fraud_events",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("happened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requests_per_minute", sa.Integer(), nullable=False),
        sa.Column("payment_attempts", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("is_bot", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "requests_per_minute >= 0 AND payment_attempts >= 0",
            name="ck_fraud_nonnegative_counts",
        ),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="ck_fraud_risk_score"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fraud_events_user_id", "fraud_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_fraud_events_user_id", table_name="fraud_events")
    op.drop_table("fraud_events")
    op.drop_index("ix_support_conversations_user_id", table_name="support_conversations")
    op.drop_table("support_conversations")
    op.drop_index("ix_user_behavior_user_id", table_name="user_behavior")
    op.drop_table("user_behavior")
    op.drop_table("fare_records")
    op.drop_table("train_delays")
    op.drop_table("cancellations")
    op.drop_index("ix_bookings_user_id", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_train_schedules_train_number", table_name="train_schedules")
    op.drop_table("train_schedules")
