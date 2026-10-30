import uuid

from fastapi import APIRouter

from app.api.v1.crud import Resource, crud_router
from app.models import Driver, StudentTransportAssignment, TransportRoute, Vehicle
from app.schemas.transport import (
    DriverIn,
    DriverRead,
    StudentTransportAssignmentIn,
    StudentTransportAssignmentRead,
    TransportRouteIn,
    TransportRouteRead,
    VehicleIn,
    VehicleRead,
)
from app.services.base import CRUDService

TAG = "Transport"
router = APIRouter()

for resource in (
    Resource("/vehicles", TAG, "vehicle", "transport",
             CRUDService(Vehicle, label="Vehicle", search_fields=("registration_number", "model")),
             VehicleIn, VehicleRead, filters={"vehicle_type": str, "is_active": bool}),
    Resource("/drivers", TAG, "driver", "transport",
             CRUDService(Driver, label="Driver", search_fields=("license_number",)), DriverIn, DriverRead,
             filters={"is_active": bool}),
    Resource("/transport-routes", TAG, "transport route", "transport",
             CRUDService(TransportRoute, label="Route", search_fields=("name", "start_point", "end_point")),
             TransportRouteIn, TransportRouteRead,
             filters={"vehicle_id": uuid.UUID, "driver_id": uuid.UUID, "is_active": bool}),
    Resource("/student-transport-assignments", TAG, "student transport assignment", "transport",
             CRUDService(StudentTransportAssignment, label="Transport assignment"),
             StudentTransportAssignmentIn, StudentTransportAssignmentRead,
             filters={"student_id": uuid.UUID, "route_id": uuid.UUID, "academic_session_id": uuid.UUID},
             description="One route per student per session."),
):
    router.include_router(crud_router(resource))
