from fastapi import APIRouter

from app.api.v1.endpoints import (
    academics,
    attendance,
    auth,
    communication,
    fees,
    health,
    library,
    school,
    staff,
    students,
    system,
    transport,
    users,
)

api_router = APIRouter()
for module in (health, auth, users, school, students, staff, academics, attendance, fees,
               library, transport, communication, system):
    api_router.include_router(module.router)
