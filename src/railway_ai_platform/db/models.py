"""Relational models shared across passenger and governance services."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from railway_ai_platform.db.base import Base, TimestampMixin


class TrainSchedule(TimestampMixin, Base):
    __tablename__ = "train_schedules"
    __table_args__ = (
        UniqueConstraint("train_number", "departure_at", name="uq_schedule_train_departure"),
        CheckConstraint("origin <> destination", name="ck_schedule_distinct_stations"),
        CheckConstraint("duration_minutes > 0", name="ck_schedule_positive_duration"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    train_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    train_name: Mapped[str] = mapped_column(String(120), nullable=False)
    origin: Mapped[str] = mapped_column(String(12), nullable=False)
    destination: Mapped[str] = mapped_column(String(12), nullable=False)
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)


class Booking(TimestampMixin, Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("status IN ('WL', 'RAC', 'CNF')", name="ck_booking_status"),
        CheckConstraint(
            "waitlist_position IS NULL OR waitlist_position >= 0",
            name="ck_booking_waitlist",
        ),
        CheckConstraint("fare_amount >= 0", name="ck_booking_nonnegative_fare"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    schedule_id: Mapped[str] = mapped_column(ForeignKey("train_schedules.id"), nullable=False)
    booked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    travel_class: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(3), nullable=False)
    waitlist_position: Mapped[int | None] = mapped_column(Integer)
    fare_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)


class Cancellation(TimestampMixin, Base):
    __tablename__ = "cancellations"
    __table_args__ = (
        CheckConstraint(
            "status_at_cancellation IN ('WL', 'RAC', 'CNF')",
            name="ck_cancellation_status",
        ),
        CheckConstraint("days_before_departure >= 0", name="ck_cancellation_days_before"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False, unique=True)
    cancelled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    days_before_departure: Mapped[int] = mapped_column(Integer, nullable=False)
    status_at_cancellation: Mapped[str] = mapped_column(String(3), nullable=False)
    seats_released: Mapped[bool] = mapped_column(Boolean, nullable=False)


class TrainDelay(TimestampMixin, Base):
    __tablename__ = "train_delays"
    __table_args__ = (
        CheckConstraint("delay_minutes >= 0", name="ck_delay_nonnegative_minutes"),
        CheckConstraint(
            "congestion_level >= 0 AND congestion_level <= 1",
            name="ck_delay_congestion_range",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(ForeignKey("train_schedules.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    station_code: Mapped[str] = mapped_column(String(12), nullable=False)
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    congestion_level: Mapped[float] = mapped_column(Float, nullable=False)


class FareRecord(TimestampMixin, Base):
    __tablename__ = "fare_records"
    __table_args__ = (
        CheckConstraint("base_fare >= 0 AND fare_amount >= 0", name="ck_fare_nonnegative"),
        CheckConstraint("demand_index >= 0", name="ck_fare_demand_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(ForeignKey("train_schedules.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    travel_class: Mapped[str] = mapped_column(String(8), nullable=False)
    base_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fare_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    demand_index: Mapped[float] = mapped_column(Float, nullable=False)


class UserBehavior(TimestampMixin, Base):
    __tablename__ = "user_behavior"
    __table_args__ = (
        CheckConstraint(
            "search_count >= 0 AND booking_count >= 0 AND cancellation_count >= 0",
            name="ck_behavior_counts",
        ),
        CheckConstraint("session_duration_seconds >= 0", name="ck_behavior_duration"),
        CheckConstraint("bot_score >= 0 AND bot_score <= 1", name="ck_behavior_bot_score"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    search_count: Mapped[int] = mapped_column(Integer, nullable=False)
    booking_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cancellation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    session_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    bot_score: Mapped[float] = mapped_column(Float, nullable=False)


class SupportConversation(TimestampMixin, Base):
    __tablename__ = "support_conversations"
    __table_args__ = (
        CheckConstraint("locale IN ('en', 'hi', 'mr', 'kn')", name="ck_support_locale"),
        CheckConstraint(
            "satisfaction_score IS NULL OR (satisfaction_score >= 0 AND satisfaction_score <= 1)",
            name="ck_support_satisfaction",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(2), nullable=False)
    intent: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    satisfaction_score: Mapped[float | None] = mapped_column(Float)


class FraudEvent(TimestampMixin, Base):
    __tablename__ = "fraud_events"
    __table_args__ = (
        CheckConstraint(
            "requests_per_minute >= 0 AND payment_attempts >= 0",
            name="ck_fraud_nonnegative_counts",
        ),
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="ck_fraud_risk_score"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requests_per_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False)
