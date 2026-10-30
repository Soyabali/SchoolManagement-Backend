"""Integration tests run against a disposable PostgreSQL 18 database, never Neon.

Set TEST_DATABASE_URL to point elsewhere; the schema is dropped and rebuilt with Alembic.
"""

import argparse
import os
from pathlib import Path

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:55432/sms_test")
if "neon.tech" in TEST_DATABASE_URL:
    raise RuntimeError("Refusing to run tests against a Neon database: the schema is dropped first.")

# Must be set before the app (and its engine) is imported.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DATABASE_URL_UNPOOLED"] = TEST_DATABASE_URL
os.environ["LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
SA_URL = TEST_DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
PASSWORD = "Passw0rd!x"


@pytest.fixture(scope="session", autouse=True)
def database():
    try:
        engine = create_engine(SA_URL)
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        engine.dispose()
    except OperationalError as exc:
        pytest.exit(f"Test database not reachable ({exc.orig}). Start it or set TEST_DATABASE_URL.")
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.cmd_opts = argparse.Namespace(x=[f"db_url={SA_URL}"])
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def client(database):
    from app.main import app

    with TestClient(app) as c:
        yield c


class Api:
    """Small helper: call an endpoint and assert the status code."""

    def __init__(self, client: TestClient, token: str | None = None) -> None:
        self.client, self.token = client, token

    def __call__(self, method: str, url: str, expected: int = 200, **kwargs):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = self.client.request(method, f"/api/v1{url}", headers=headers, **kwargs)
        assert response.status_code == expected, f"{method} {url}: {response.status_code} {response.text}"
        return response.json() if response.content else None


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict:
    return Api(client)("POST", "/auth/login", json={"email": email, "password": password})


@pytest.fixture(scope="session")
def admin(client) -> Api:
    Api(client)("POST", "/auth/register", 201,
                json={"email": "admin@demoschool.com", "password": PASSWORD, "full_name": "Admin User"})
    return Api(client, login(client, "admin@demoschool.com")["access_token"])


@pytest.fixture(scope="session")
def make_user(client, admin):
    def _make(email: str, role: str) -> tuple[Api, dict]:
        user = admin("POST", "/users", 201,
                     json={"email": email, "password": PASSWORD, "full_name": email.split("@")[0], "roles": [role]})
        return Api(client, login(client, email)["access_token"]), user
    return _make


@pytest.fixture(scope="session")
def school(admin) -> dict:
    """A session, a class with one section, two subjects and three enrolled students."""
    session = admin("POST", "/academic-sessions", 201,
                    json={"name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31", "is_current": True})
    cls = admin("POST", "/classes", 201, json={"name": "Grade 5", "numeric_level": 5})
    section = admin("POST", "/sections", 201, json={"class_id": cls["id"], "name": "A", "capacity": 40})
    math = admin("POST", "/subjects", 201, json={"name": "Mathematics", "code": "MATH5"})
    science = admin("POST", "/subjects", 201, json={"name": "Science", "code": "SCI5"})
    students = []
    for i, (first, last) in enumerate([("Aisha", "Khan"), ("Bilal", "Shaikh"), ("Chen", "Li")], start=1):
        students.append(admin("POST", "/students", 201, json={
            "admission_number": f"ADM-{i:03d}", "first_name": first, "last_name": last,
            "date_of_birth": "2016-05-10", "gender": "female" if i % 2 else "male",
            "admission": {"academic_session_id": session["id"], "section_id": section["id"], "roll_number": str(i)},
        }))
    return {"session": session, "class": cls, "section": section, "math": math, "science": science,
            "students": students}
