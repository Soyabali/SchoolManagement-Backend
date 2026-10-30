import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import InputSchema, Money, ReadSchema, Schema, Str


class VehicleIn(InputSchema):
    registration_number: Str(20)
    vehicle_type: Literal["bus", "van", "car", "other"]
    capacity: int = Field(ge=1, le=200)
    model: Str(100) | None = None
    insurance_expiry: date | None = None
    fitness_expiry: date | None = None
    is_active: bool = True


class VehicleRead(VehicleIn, ReadSchema):
    pass


class DriverIn(InputSchema):
    staff_id: uuid.UUID = Field(description="Drivers are staff members; create the staff record first")
    license_number: Str(30)
    license_expiry: date
    is_active: bool = True


class DriverRead(DriverIn, ReadSchema):
    pass


class RouteStop(Schema):
    name: Str(150)
    pickup_time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["07:30"])


class TransportRouteIn(InputSchema):
    name: Str(100)
    start_point: Str(150)
    end_point: Str(150)
    stops: list[RouteStop] = Field(default_factory=list, max_length=100)
    fare: Money = Decimal("0")
    vehicle_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    is_active: bool = True


class TransportRouteRead(TransportRouteIn, ReadSchema):
    pass


class StudentTransportAssignmentIn(InputSchema):
    student_id: uuid.UUID
    route_id: uuid.UUID
    academic_session_id: uuid.UUID
    start_date: date
    end_date: date | None = None
    pickup_stop: Str(150) | None = None

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class StudentTransportAssignmentRead(StudentTransportAssignmentIn, ReadSchema):
    pass
