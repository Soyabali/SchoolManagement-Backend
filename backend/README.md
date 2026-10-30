# School Management System — Backend

REST API for a single school: students, staff, academics, exams, attendance, fees, library, transport and
communication. Built for a Flutter mobile app and a React admin dashboard.

**➡ How to call every endpoint: [API_GUIDE.md](API_GUIDE.md)**

## Technology

| Layer | Choice |
|---|---|
| API | FastAPI (Python 3.13), Swagger UI at `/docs` |
| Validation | Pydantic v2 |
| ORM / migrations | SQLAlchemy 2 (sync) + Alembic |
| Database | PostgreSQL 18 on Neon (psycopg 3 driver, SSL + channel binding) |
| Auth | JWT access tokens (15 min) + rotating, hashed refresh tokens (7 days); Argon2id password hashing |
| Authorization | Role-based (admin, principal, teacher, accountant, student, parent), 26 permission codes |

## Architecture

```
app/
  main.py                 app, CORS, request logging middleware
  core/                   config (.env), security (JWT, Argon2), dependencies (auth, RBAC), errors, logging
  database/               engine + session (connection.py), declarative Base and mixins (base.py)
  models/                 53 SQLAlchemy tables, one file per module
  schemas/                Pydantic request/response models
  repositories/base.py    generic data access: get, paginated list (search/sort/filter), create, update
  services/               business rules (auth, fees, exams, attendance, library …) + audit log
  api/v1/crud.py          builds the 5 standard endpoints for a resource from a short declaration
  api/v1/endpoints/       one router per module
alembic/versions/         schema migration + seed data (roles, attendance types, permissions)
tests/                    integration tests (run against a throwaway database)
```

A request goes **endpoint → service → repository → database**. Every change runs in a single transaction
and writes an audit log row in that same transaction.

## Database schema overview

53 tables in 11 modules. Every table has a time-ordered UUID primary key (`uuidv7()`), plus `created_at` and
`updated_at`. Status fields use CHECK constraints, and money is `NUMERIC(12,2)`.

| Module | Tables |
|---|---|
| Auth | users, roles, permissions, role_permissions, user_roles, refresh_tokens |
| School | schools, academic_sessions, classes, sections, subjects, classrooms |
| Students | students, student_admissions, guardians, student_guardians, student_documents |
| Staff | staff, teachers (extends staff), teacher_subjects, teacher_class_assignments, staff_attendance |
| Academics | class_subjects, timetables, exams, exam_subjects, student_exam_results, grades |
| Fees | fee_categories, fee_structures, discounts, scholarships, student_fees, fee_payments, payment_transactions |
| Attendance | attendance_types, attendance_records (roll call), student_attendance (entries), attendance_notifications |
| Library | book_categories, books, book_issues, book_returns |
| Transport | vehicles, drivers (extends staff), transport_routes, student_transport_assignments |
| Communication | announcements, notifications, parent_teacher_messages (threads), messages |
| System | audit_logs, system_settings |

**What happens on delete:** history tables (fees, payments, marks, attendance) use **RESTRICT**, so they can't be
orphaned. Pure child rows use **CASCADE**. "Who did it" columns use **SET NULL**. Users, students and staff are
**archived** (`deleted_at`) instead of deleted.

## Setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the values below
```

### Environment (`.env`)

| Variable | What |
|---|---|
| `DATABASE_URL` | Neon **pooled** connection string (host contains `-pooler`). Used by the API |
| `DATABASE_URL_UNPOOLED` | Same string **without** `-pooler`. Used by Alembic (migrations need a direct connection) |
| `JWT_SECRET_KEY` | Long random string: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes (15 / 7) |
| `CORS_ORIGINS` | JSON list of browser origins allowed to call the API |
| `LOG_LEVEL` | `INFO` by default |

`.env` is git-ignored. Credentials are never logged: settings hold them as `SecretStr`, and SQL parameter
logging is off.

### Neon connection

In the Neon Console, open your project → **Connect**. Pick the branch, then copy the connection string with
**connection pooling on** (→ `DATABASE_URL`) and **off** (→ `DATABASE_URL_UNPOOLED`). Keep `?sslmode=require&channel_binding=require`.
The app adds the `postgresql+psycopg://` driver prefix itself.

## Migrations

```bash
alembic upgrade head                                  # apply all migrations
alembic current                                       # show the applied revision
alembic revision --autogenerate -m "add xyz column"   # after changing a model
alembic check                                         # verify models and database match
alembic downgrade -1                                  # undo the last migration
```

Always review an autogenerated migration before applying it. Try it on a Neon **development branch** before production.

## Run the server

```bash
uvicorn app.main:app --reload                       # http://127.0.0.1:8000
uvicorn app.main:app --host 0.0.0.0 --port 8000     # reachable from a phone on the same Wi-Fi
```

- Swagger UI: <http://127.0.0.1:8000/docs> · ReDoc: <http://127.0.0.1:8000/redoc>
- The **first** user to call `POST /api/v1/auth/register` becomes the admin. See [API_GUIDE.md §2](API_GUIDE.md#2-first-login-create-the-admin).

## API endpoints

264 operations across 14 groups. Full documentation with examples is in **[API_GUIDE.md](API_GUIDE.md)**.

| Group | Highlights |
|---|---|
| Authentication | register, login, token (Swagger), refresh, logout, me, change-password |
| Users & Roles | users CRUD, set roles, list roles/permissions, edit role permissions |
| School Setup | school profile, academic sessions (+ activate), classes, sections, subjects, classrooms |
| Students | students (+ enrol in one call), admissions, guardians (+ link/unlink), documents |
| Teachers & Staff | teachers (with staff record + subjects), staff, class assignments, staff attendance |
| Academics | class subjects (curriculum), timetables (clash-checked) |
| Examinations | exams, exam subjects, grades, bulk marks entry, calculated results with rank |
| Attendance | bulk mark, query by student/section/date, percentage summaries |
| Fees | categories, structures, discounts, scholarships, bulk assign, payments + receipts, history, pending report |
| Library | books, categories, issue, return, overdue list |
| Transport | vehicles, drivers, routes (stops), student assignments |
| Communication | announcements, notifications, direct messages, parent-teacher threads |
| Dashboard | totals, today's attendance, fee collection and dues, upcoming exams |
| System | settings (+ public), audit log |

## Testing

The tests build a fresh schema with Alembic on a **disposable** PostgreSQL database and call the API end to end.
They refuse to run against a `neon.tech` URL, because the schema is dropped first.

```bash
# Default target: postgresql://postgres@localhost:55432/sms_test
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/sms_test pytest -q
```

They cover auth (bootstrap admin, refresh rotation and reuse detection, logout, deactivation, password change),
RBAC, validation, every module's main workflow, foreign-key conflicts, and that secrets never reach the audit log.

## Security notes

- Passwords: Argon2id. Hashes and refresh tokens are never returned or logged. Refresh tokens are stored as SHA-256 hashes.
- Login errors are identical for "no such user" and "wrong password" and take the same time.
- Re-using a rotated refresh token revokes all of that user's sessions.
- Validation errors never echo submitted values. Database errors expose only the constraint name.
- Each request is logged as JSON with method, path, status and duration. Query strings and bodies are not logged.
- Not included yet: rate limiting on `/auth/login`, email verification, password reset by email.
