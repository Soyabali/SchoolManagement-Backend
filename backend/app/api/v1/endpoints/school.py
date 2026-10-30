import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.v1.crud import Resource, crud_router
from app.core.dependencies import CurrentUser, DbSession, require_permission
from app.core.exceptions import NotFoundError
from app.models import Classroom, School, SchoolClass, Section, Subject
from app.schemas.school import (
    AcademicSessionIn,
    AcademicSessionRead,
    ClassIn,
    ClassroomIn,
    ClassroomRead,
    ClassRead,
    SchoolIn,
    SchoolRead,
    SectionIn,
    SectionRead,
    SubjectIn,
    SubjectRead,
)
from app.services import audit
from app.services.base import CRUDService
from app.services.people import AcademicSessionService

TAG = "School Setup"
router = APIRouter()
session_service = AcademicSessionService()


@router.get("/school", response_model=SchoolRead, tags=[TAG], summary="Get the school profile",
            dependencies=[require_permission("school:read")])
def get_school(db: DbSession):
    school = db.scalar(select(School).limit(1))
    if school is None:
        raise NotFoundError("School profile has not been set up yet. Use PUT /school.")
    return SchoolRead.model_validate(school)


@router.put("/school", response_model=SchoolRead, tags=[TAG], summary="Create or update the school profile",
            dependencies=[require_permission("school:write")])
def put_school(payload: SchoolIn, db: DbSession, user: CurrentUser):
    school = db.scalar(select(School).limit(1).with_for_update())
    if school is None:
        school = School(**payload.model_dump())
        db.add(school)
    else:
        for key, value in payload.model_dump().items():
            setattr(school, key, value)
    db.flush()
    audit.record(db, user, "upsert", "schools", school.id, payload.model_dump())
    db.commit()
    return SchoolRead.model_validate(school)


@router.post("/academic-sessions/{session_id}/activate", response_model=AcademicSessionRead, tags=[TAG],
             summary="Make this the current academic session",
             description="Exactly one session is current; attendance and other defaults use it.",
             dependencies=[require_permission("school:write")])
def activate_session(session_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return AcademicSessionRead.model_validate(session_service.activate(db, session_id, user))


for resource in (
    Resource("/academic-sessions", TAG, "academic session", "school", session_service,
             AcademicSessionIn, AcademicSessionRead, filters={"is_current": bool},
             description="School years, e.g. 2026-27."),
    Resource("/classes", TAG, "class", "school",
             CRUDService(SchoolClass, label="Class", search_fields=("name",)),
             ClassIn, ClassRead, filters={"numeric_level": int}),
    Resource("/sections", TAG, "section", "school",
             CRUDService(Section, label="Section", search_fields=("name",)),
             SectionIn, SectionRead, filters={"class_id": uuid.UUID, "class_teacher_id": uuid.UUID}),
    Resource("/subjects", TAG, "subject", "school",
             CRUDService(Subject, label="Subject", search_fields=("name", "code")),
             SubjectIn, SubjectRead, filters={"subject_type": str}),
    Resource("/classrooms", TAG, "classroom", "school",
             CRUDService(Classroom, label="Classroom", search_fields=("room_number", "building")),
             ClassroomIn, ClassroomRead, filters={"building": str}),
):
    router.include_router(crud_router(resource))
