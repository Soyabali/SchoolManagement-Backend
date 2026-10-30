import uuid
from datetime import date
from typing import Literal

from pydantic import EmailStr, Field, computed_field, field_validator

from app.schemas.common import InputSchema, Phone, ReadSchema, Schema, Str, Url, partial

Gender = Literal["male", "female", "other"]
BloodGroup = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
StudentStatus = Literal["active", "graduated", "transferred", "withdrawn", "suspended"]
AdmissionStatus = Literal["enrolled", "promoted", "detained", "transferred", "withdrawn"]
Relation = Literal["father", "mother", "guardian", "grandparent", "sibling", "other"]


class StudentIn(InputSchema):
    admission_number: Str(30) = Field(examples=["ADM-2026-001"])
    first_name: Str(100)
    last_name: Str(100)
    date_of_birth: date
    gender: Gender
    blood_group: BloodGroup | None = None
    address: str | None = Field(None, max_length=1000)
    phone: Phone | None = None
    email: EmailStr | None = None
    photo_url: Url | None = None
    status: StudentStatus = "active"
    user_id: uuid.UUID | None = Field(None, description="Login account (role 'student'), optional")

    @field_validator("date_of_birth")
    @classmethod
    def _not_future(cls, value: date) -> date:
        if value >= date.today():
            raise ValueError("date_of_birth must be in the past")
        return value


class AdmissionInline(InputSchema):
    academic_session_id: uuid.UUID
    section_id: uuid.UUID
    roll_number: Str(10) | None = None
    admission_date: date = Field(default_factory=date.today)


class StudentCreate(StudentIn):
    admission: AdmissionInline | None = Field(
        None, description="Optionally enrol the student in a section in the same request"
    )


StudentUpdate = partial(StudentIn, "StudentUpdate")


class StudentRead(StudentIn, ReadSchema):
    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class StudentAdmissionIn(InputSchema):
    student_id: uuid.UUID
    academic_session_id: uuid.UUID
    section_id: uuid.UUID
    roll_number: Str(10) | None = None
    admission_date: date = Field(default_factory=date.today)
    status: AdmissionStatus = "enrolled"


class StudentAdmissionRead(StudentAdmissionIn, ReadSchema):
    pass


class GuardianIn(InputSchema):
    first_name: Str(100)
    last_name: Str(100)
    phone: Phone
    email: EmailStr | None = None
    occupation: Str(100) | None = None
    address: str | None = Field(None, max_length=1000)
    user_id: uuid.UUID | None = Field(None, description="Login account (role 'parent'), optional")


class GuardianRead(GuardianIn, ReadSchema):
    pass


class StudentGuardianIn(InputSchema):
    relation: Relation
    is_primary: bool = False
    can_pickup: bool = False


class StudentGuardianRead(Schema):
    guardian: GuardianRead
    relation: Relation
    is_primary: bool
    can_pickup: bool


class StudentDocumentIn(InputSchema):
    student_id: uuid.UUID
    document_type: Str(50) = Field(examples=["birth_certificate"])
    file_name: Str(255)
    file_url: Url
    mime_type: Str(100) | None = None
    file_size: int | None = Field(None, ge=0)


class StudentDocumentRead(StudentDocumentIn, ReadSchema):
    uploaded_by: uuid.UUID | None
