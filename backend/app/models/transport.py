import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, choice_check


class Vehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="capacity_positive"),
        choice_check("vehicle_type", ("bus", "van", "car", "other")),
    )

    registration_number: Mapped[str] = mapped_column(String(20), unique=True)
    vehicle_type: Mapped[str] = mapped_column(String(20))
    model: Mapped[str | None] = mapped_column(String(100))
    capacity: Mapped[int] = mapped_column(SmallInteger)
    insurance_expiry: Mapped[date | None]
    fitness_expiry: Mapped[date | None]
    is_active: Mapped[bool] = mapped_column(server_default=true())


class Driver(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "drivers"

    staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="RESTRICT"), unique=True
    )
    license_number: Mapped[str] = mapped_column(String(30), unique=True)
    license_expiry: Mapped[date]
    is_active: Mapped[bool] = mapped_column(server_default=true())


class TransportRoute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transport_routes"
    __table_args__ = (CheckConstraint("fare >= 0", name="fare_non_negative"),)

    name: Mapped[str] = mapped_column(String(100), unique=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), index=True
    )
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("drivers.id", ondelete="SET NULL"), index=True
    )
    start_point: Mapped[str] = mapped_column(String(150))
    end_point: Mapped[str] = mapped_column(String(150))
    # Ordered list of {"name": str, "pickup_time": "HH:MM"}.
    stops: Mapped[list[Any]] = mapped_column(server_default=text("'[]'::jsonb"))
    fare: Mapped[Decimal] = mapped_column(server_default="0")
    is_active: Mapped[bool] = mapped_column(server_default=true())


class StudentTransportAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_transport_assignments"
    __table_args__ = (
        UniqueConstraint("student_id", "academic_session_id"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="dates_ordered"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    route_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transport_routes.id", ondelete="RESTRICT"), index=True
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"), index=True
    )
    pickup_stop: Mapped[str | None] = mapped_column(String(150))
    start_date: Mapped[date]
    end_date: Mapped[date | None]
