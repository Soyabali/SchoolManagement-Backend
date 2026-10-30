# School Management System — API Guide

How to use every endpoint of the backend: what to send, what you get back, and in which order to set things up.
Everything here was checked against the running code. For live, clickable docs, open **Swagger UI** at
<http://127.0.0.1:8000/docs>.

---

## Contents

1. [Start the server](#1-start-the-server)
2. [First login (create the admin)](#2-first-login-create-the-admin)
3. [Rules that apply to every endpoint](#3-rules-that-apply-to-every-endpoint)
4. [Roles and permissions](#4-roles-and-permissions)
5. [Setup order for a new school](#5-setup-order-for-a-new-school)
6. [Authentication](#6-authentication)
7. [Users and roles](#7-users-and-roles)
8. [School setup](#8-school-setup)
9. [Students](#9-students)
10. [Teachers and staff](#10-teachers-and-staff)
11. [Academics (curriculum and timetable)](#11-academics-curriculum-and-timetable)
12. [Examinations](#12-examinations)
13. [Attendance](#13-attendance)
14. [Fees](#14-fees)
15. [Library](#15-library)
16. [Transport](#16-transport)
17. [Communication](#17-communication)
18. [Dashboard](#18-dashboard)
19. [System settings and audit log](#19-system-settings-and-audit-log)
20. [Using the API from Flutter and React](#20-using-the-api-from-flutter-and-react)

---

## 1. Start the server

```bash
cd ~/Desktop/Neon/backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

| What | URL |
|---|---|
| Swagger UI (try every endpoint in the browser) | <http://127.0.0.1:8000/docs> |
| ReDoc (read-only reference) | <http://127.0.0.1:8000/redoc> |
| OpenAPI JSON (for code generators) | <http://127.0.0.1:8000/api/v1/openapi.json> |
| Health check | <http://127.0.0.1:8000/api/v1/health> |

Every endpoint below starts with **`/api/v1`**. Example: `/students` means `http://127.0.0.1:8000/api/v1/students`.

---

## 2. First login (create the admin)

Your database starts with **no users**. The **first** user who registers automatically becomes the **admin**.
After that, registration is closed: only a logged-in user can create other users.

### In Swagger UI (easiest)

1. Open <http://127.0.0.1:8000/docs>, find **POST /api/v1/auth/register**, click **Try it out**, send:
   ```json
   { "email": "you@yourschool.com", "password": "ChooseAStrongPass1", "full_name": "Your Name" }
   ```
2. Click the green **Authorize** button (top right). Enter your **email** in `username` and your password. Click **Authorize**.
3. Every request you try in Swagger is now sent with your token. Try **GET /api/v1/auth/me**.

### With curl

```bash
API=http://127.0.0.1:8000/api/v1

curl -X POST $API/auth/register -H "Content-Type: application/json" \
  -d '{"email":"you@yourschool.com","password":"ChooseAStrongPass1","full_name":"Your Name"}'

TOKEN=$(curl -s -X POST $API/auth/login -H "Content-Type: application/json" \
  -d '{"email":"you@yourschool.com","password":"ChooseAStrongPass1"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl $API/auth/me -H "Authorization: Bearer $TOKEN"
```

The curl examples in the rest of this guide assume `API` and `TOKEN` are set like this.

> **Password rules:** 8–128 characters, at least one letter and one digit.

---

## 3. Rules that apply to every endpoint

### 3.1 Authentication header

Every endpoint except `/health`, `/auth/register` (first user), `/auth/login`, `/auth/token`, `/auth/refresh`,
`/auth/logout` and `/system-settings/public` needs:

```
Authorization: Bearer <access_token>
```

### 3.2 Data formats

| Type | Format | Example |
|---|---|---|
| IDs | UUID string | `"01a18e5e-df87-7abc-a2b8-02219b6ca48f"` |
| Date | `YYYY-MM-DD` | `"2026-04-01"` |
| Time | `HH:MM` or `HH:MM:SS` | `"08:30"` |
| Date-time | ISO 8601 with timezone | `"2026-10-31T09:15:00Z"` |
| **Money and marks** | **string** with 2 decimals in responses; send a number or a string | `"1000.00"` |

Money comes back as a **string** so no precision is lost. In Dart use `Decimal.parse` or `double.parse`;
in JavaScript use `Number(value)` or a decimal library for sums.

Requests with **unknown fields are rejected** (422). This catches typos such as `fist_name`.

### 3.3 The 5 standard operations (CRUD)

Most resources (classes, subjects, books, vehicles, …) have the same five endpoints.
`/classes` is the example here:

| Action | Method and path | Success | Body |
|---|---|---|---|
| List (paginated) | `GET /classes` | 200 | — |
| Get one | `GET /classes/{id}` | 200 | — |
| Create | `POST /classes` | **201** | all required fields |
| Update | `PATCH /classes/{id}` (or `PUT`) | 200 | **only the fields you want to change** |
| Delete | `DELETE /classes/{id}` | **204** (empty) | — |

- **PUT and PATCH behave the same here:** both accept a partial body. Fields you leave out are not changed.
- **Delete vs archive:** `users`, `students`, `staff` and `teachers` are **archived**. They disappear from lists
  and `GET` returns 404, but they stay in the database so fees, marks and attendance history stay intact.
  Everything else is deleted. A delete fails with **409** if other records still point at the row.

### 3.4 Lists: pagination, search, sort, filters

Every list endpoint accepts:

| Query param | Meaning | Default |
|---|---|---|
| `page` | Page number, starting at 1 | `1` |
| `size` | Items per page (1–100) | `20` |
| `search` | Case-insensitive text search (the fields are listed in Swagger for each endpoint) | — |
| `sort` | Column to sort by. Prefix with `-` for descending: `sort=-created_at` | newest first |
| *filters* | Exact-match filters, different for each resource (listed in each section below) | — |

Example: `GET /students?section_id=<id>&search=khan&sort=first_name&page=1&size=50`

Every list response has the same shape:

```json
{
  "items": [ { "...": "..." } ],
  "total": 134,
  "page": 1,
  "size": 20,
  "pages": 7
}
```

### 3.5 Errors

Every error has the same shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid request",
    "details": [ { "field": "body.date_of_birth", "message": "Value error, date_of_birth must be in the past" } ]
  }
}
```

| HTTP status | `code` | When |
|---|---|---|
| 400 | `bad_request` | A business rule was broken (e.g. payment bigger than the balance, student not enrolled in that section) |
| 401 | `unauthorized` | Missing, invalid or expired token; wrong email or password |
| 403 | `forbidden` | You are logged in, but your role lacks the permission |
| 404 | `not_found` | ID does not exist (or was archived) |
| 409 | `conflict` / `constraint_violation` | Duplicate (same email, admission number …), or the record is still in use |
| 422 | `validation_error` | Request body or query is invalid. `details` lists each bad field |
| 500 | `internal_error` | Bug on the server (details are logged, never sent to the client) |
| 503 | `database_unavailable` | Database cannot be reached |

Error responses never include the values you sent, so passwords are never echoed back.

---

## 4. Roles and permissions

Each endpoint needs one permission. **GET** endpoints need `<module>:read`; **POST, PATCH, PUT and DELETE**
need `<module>:write`.

| Module | admin | principal | teacher | accountant | student | parent |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `users` | RW | R | – | – | – | – |
| `school` (sessions, classes, sections, subjects, rooms) | RW | RW | R | R | – | – |
| `students` | RW | RW | R | R | – | – |
| `staff` (teachers, staff, assignments) | RW | RW | R | – | – | – |
| `academics` (curriculum, timetable) | RW | RW | R | – | – | – |
| `exams` | RW | RW | **RW** | – | – | – |
| `attendance` | RW | RW | **RW** | – | – | – |
| `fees` | RW | R | – | **RW** | – | – |
| `library` | RW | RW | R | – | – | – |
| `transport` | RW | RW | R | – | – | – |
| `communication` | RW | RW | RW | R | R | R |
| `settings` | RW | R | – | – | – | – |
| `audit` | R | R | – | – | – | – |
| `dashboard` | R | R | – | R | – | – |

R = read, W = write. **Admin always has everything.** These defaults can be changed with
`PUT /roles/{role_id}/permissions` (needs `settings:write`).

Endpoints that only need you to be **logged in**, with no specific permission: `/auth/me`, `/auth/change-password`,
`/notifications/me…`.

---

## 5. Setup order for a new school

Records point to each other, so create them in this order:

```
 1. PUT  /school                       school profile
 2. POST /academic-sessions            "2026-27" with is_current = true
 3. POST /classes                      Grade 1 … Grade 10
 4. POST /classrooms                   (optional) rooms
 5. POST /subjects                     Mathematics, Science …
 6. POST /teachers                     creates staff + teacher in one call
 7. POST /sections                     Grade 5 - A (can set class_teacher_id, classroom_id)
 8. POST /class-subjects               which subjects each class studies
 9. POST /teacher-class-assignments    who teaches what to which section
10. POST /students                     with "admission" to enrol them in a section
11. POST /guardians + PUT /students/{id}/guardians/{guardian_id}
12. POST /grades                       grading scale (A, B, C …)
13. POST /fee-categories → /fee-structures → /student-fees/assign
14. POST /timetables                   weekly timetable
15. POST /users                        logins for teachers, accountants, parents
```

Then day-to-day: **mark attendance**, **enter marks**, **record payments**, **issue books**, **send announcements**.

---

## 6. Authentication

| Method | Path | Who | What it does |
|---|---|---|---|
| POST | `/auth/register` | first user: anyone; afterwards: `users:write` | Create a user |
| POST | `/auth/login` | anyone | Log in with JSON → tokens |
| POST | `/auth/token` | anyone | Same, but form fields (used by Swagger's Authorize button) |
| POST | `/auth/refresh` | anyone with a refresh token | Swap a refresh token for a new pair |
| POST | `/auth/logout` | anyone with a refresh token | Revoke that refresh token |
| GET | `/auth/me` | logged in | Your profile, roles and permission codes |
| POST | `/auth/change-password` | logged in | Change password (signs out all your sessions) |

### POST /auth/login

```json
{ "email": "you@yourschool.com", "password": "ChooseAStrongPass1" }
```

Response `200`:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "kq3V3m1q0...",
  "token_type": "bearer",
  "expires_in": 900
}
```

- **Access token:** sent on every request. Valid for **15 minutes**.
- **Refresh token:** valid for **7 days** and **single use**. Every `/auth/refresh` returns a **new** pair; keep the new refresh token.
  If an old refresh token is ever used again, the server assumes it was stolen and **signs that user out everywhere**.

### POST /auth/refresh and POST /auth/logout

```json
{ "refresh_token": "kq3V3m1q0..." }
```

`/auth/refresh` → `200` with a new token pair. `/auth/logout` → `204` (no body).

### GET /auth/me

```json
{
  "id": "01a18e5e-...",
  "email": "you@yourschool.com",
  "full_name": "Your Name",
  "phone": null,
  "is_active": true,
  "is_verified": false,
  "last_login_at": "2026-10-31T09:15:00Z",
  "roles": ["admin"],
  "permissions": ["academics:read", "academics:write", "attendance:read", "..."],
  "created_at": "...", "updated_at": "..."
}
```

Use `permissions` in the React dashboard and the Flutter app to hide buttons the user can't use.

### POST /auth/change-password

```json
{ "current_password": "ChooseAStrongPass1", "new_password": "AnotherStrongPass2" }
```

`204` on success, `400` if the current password is wrong.

---

## 7. Users and roles

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/users` | users:read | search: email, full_name, phone · filters: `role`, `is_active` |
| POST | `/users` | users:write | Body like `/auth/register`, **`roles` required** |
| GET | `/users/{id}` | users:read | |
| PATCH | `/users/{id}` | users:write | `full_name`, `phone`, `is_active` (false = locked out immediately) |
| DELETE | `/users/{id}` | users:write | Archives and signs the user out |
| PUT | `/users/{id}/roles` | users:write | Replace roles. Only an admin can grant or remove `admin` |
| GET | `/roles` | users:read | Every role with its permission codes |
| PUT | `/roles/{id}/permissions` | settings:write | Replace a role's permissions (not allowed for admin) |
| GET | `/permissions` | users:read | All 26 permission codes |

### Create a teacher login

```bash
curl -X POST $API/users -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
  "email": "ravi.kumar@yourschool.com",
  "password": "TempPass123",
  "full_name": "Ravi Kumar",
  "phone": "+919800000010",
  "roles": ["teacher"]
}'
```

Roles: `admin`, `principal`, `teacher`, `accountant`, `student`, `parent`.

To connect a login to a person, put the returned user `id` into `user_id` on the matching
**staff**, **student** or **guardian** record.

### Change roles / permissions

```json
PUT /users/{id}/roles
{ "roles": ["teacher", "accountant"] }

PUT /roles/{role_id}/permissions
{ "permissions": ["students:read", "attendance:read", "attendance:write"] }
```

---

## 8. School setup

Permission: `school:read` / `school:write`.

### School profile (one per system)

| Method | Path | |
|---|---|---|
| GET | `/school` | 404 until it is created |
| PUT | `/school` | Create or replace |

```json
PUT /school
{
  "name": "Green Valley Public School",
  "code": "GVPS",
  "address": "12 Park Road, Pune",
  "phone": "+912012345678",
  "email": "office@greenvalley.edu.in",
  "website": "https://greenvalley.edu.in",
  "timezone": "Asia/Kolkata",
  "established_year": 1998
}
```

### Academic sessions

Standard CRUD on `/academic-sessions` (filter: `is_current`) plus:

| Method | Path | |
|---|---|---|
| POST | `/academic-sessions/{id}/activate` | Make it the current session (all others are switched off) |

```json
POST /academic-sessions
{ "name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31", "is_current": true }
```

Only **one** session can be current. Attendance marking uses the current session by default.

### Classes, sections, subjects, classrooms (standard CRUD)

| Resource | Path | Required fields | Optional | Filters |
|---|---|---|---|---|
| Class | `/classes` | `name` | `numeric_level` (0–20), `description` | `numeric_level` |
| Section | `/sections` | `class_id`, `name` | `capacity`, `class_teacher_id` (a **teacher** id), `classroom_id` | `class_id`, `class_teacher_id` |
| Subject | `/subjects` | `name`, `code` (unique) | `subject_type` (`theory`/`practical`/`both`), `description` | `subject_type` |
| Classroom | `/classrooms` | `room_number` (unique) | `building`, `floor`, `capacity` | `building` |

```json
POST /classes      { "name": "Grade 5", "numeric_level": 5 }
POST /sections     { "class_id": "<class_id>", "name": "A", "capacity": 40 }
POST /subjects     { "name": "Mathematics", "code": "MATH5" }
POST /classrooms   { "room_number": "101", "building": "Main", "floor": 1, "capacity": 40 }
```

Deleting a class also deletes its sections, but only if no student is enrolled in them (otherwise 409).

---

## 9. Students

Permission: `students:read` / `students:write`.

### Students: `/students`

| Method | Path | Notes |
|---|---|---|
| GET | `/students` | search: first_name, last_name, admission_number, phone, email · filters: `status`, `gender`, **`section_id`, `class_id`, `academic_session_id`** |
| POST | `/students` | Can enrol the student in a section in the same call |
| GET | `/students/{id}` | |
| PATCH/PUT | `/students/{id}` | Partial update |
| DELETE | `/students/{id}` | Archives |

**Create and enrol in one call:**

```json
POST /students
{
  "admission_number": "ADM-2026-001",
  "first_name": "Aisha",
  "last_name": "Khan",
  "date_of_birth": "2016-05-10",
  "gender": "female",
  "blood_group": "B+",
  "phone": "+919800000001",
  "address": "45 Lake View, Pune",
  "admission": {
    "academic_session_id": "<session_id>",
    "section_id": "<section_id>",
    "roll_number": "1",
    "admission_date": "2026-04-01"
  }
}
```

Response `201` includes the student plus `full_name` (e.g. `"Aisha Khan"`).

| Field | Allowed values |
|---|---|
| `gender` | `male`, `female`, `other` |
| `blood_group` | `A+ A- B+ B- AB+ AB- O+ O-` |
| `status` | `active` (default), `graduated`, `transferred`, `withdrawn`, `suspended` |

**List a section's students:** `GET /students?section_id=<section_id>&sort=first_name&size=100`

### Admissions (enrolments): `/student-admissions`

One row per student **per academic session**. Use it to promote students to a new class each year.

```json
POST /student-admissions
{
  "student_id": "<student_id>",
  "academic_session_id": "<2027-28 session_id>",
  "section_id": "<Grade 6 A section_id>",
  "roll_number": "4",
  "status": "enrolled"
}
```

Filters: `student_id`, `section_id`, `academic_session_id`, `status`. A student can only have **one** admission per
session, and a roll number is unique within a section for a session.

### Guardians: `/guardians` + linking

```json
POST /guardians
{ "first_name": "Sara", "last_name": "Khan", "phone": "+919800000002", "email": "sara@example.com",
  "occupation": "Engineer" }
```

| Method | Path | Body |
|---|---|---|
| PUT | `/students/{student_id}/guardians/{guardian_id}` | `{ "relation": "mother", "is_primary": true, "can_pickup": true }` |
| GET | `/students/{student_id}/guardians` | — returns each guardian with relation |
| DELETE | `/students/{student_id}/guardians/{guardian_id}` | — |

`relation`: `father`, `mother`, `guardian`, `grandparent`, `sibling`, `other`.
One guardian can be linked to several children (siblings). Only one guardian per student can be primary.

### Documents: `/student-documents`

Stores **metadata only**. Upload the file to your storage (S3, Firebase Storage, …) first, then save the URL:

```json
POST /student-documents
{ "student_id": "<id>", "document_type": "birth_certificate", "file_name": "birth.pdf",
  "file_url": "https://storage.example.com/docs/birth.pdf", "mime_type": "application/pdf", "file_size": 120400 }
```

Filters: `student_id`, `document_type`. `uploaded_by` is filled in automatically.

---

## 10. Teachers and staff

Permission: `staff:read` / `staff:write` (staff attendance uses `attendance:*`).

### Teachers: `/teachers`

Creating a teacher also creates their **staff** record. Send the staff details under `staff`.

```json
POST /teachers
{
  "staff": {
    "employee_code": "EMP-001",
    "first_name": "Ravi",
    "last_name": "Kumar",
    "joining_date": "2024-06-01",
    "department": "Science",
    "phone": "+919800000010",
    "email": "ravi.kumar@yourschool.com",
    "user_id": "<login user id, optional>"
  },
  "qualification": "M.Sc, B.Ed",
  "specialization": "Physics",
  "experience_years": 8,
  "subject_ids": ["<science_subject_id>"]
}
```

Response:

```json
{
  "id": "<teacher_id>",
  "staff": { "id": "<staff_id>", "employee_code": "EMP-001", "full_name": "Ravi Kumar",
             "staff_type": "teaching", "designation": "Teacher", "status": "active", "...": "..." },
  "qualification": "M.Sc, B.Ed",
  "specialization": "Physics",
  "experience_years": 8,
  "subjects": [ { "id": "...", "name": "Science", "code": "SCI5" } ],
  "created_at": "...", "updated_at": "..."
}
```

- **List filters:** `department`, `status`, `subject_id` · **search:** first name, last name, employee code, email.
- **Update:** `PATCH /teachers/{id}` with any of `staff` (partial), `qualification`, `specialization`,
  `experience_years`, `subject_ids` (replaces the whole list).
  ```json
  { "staff": { "designation": "Senior Teacher" }, "subject_ids": ["<math_id>", "<science_id>"] }
  ```
- **Delete** archives the teacher's staff record.

> Use the **teacher `id`** (not the staff id) for `class_teacher_id`, `teacher_id` in timetables, assignments and
> parent-teacher threads.

### Staff: `/staff`

Every employee: teachers, office staff, drivers, peons. Required: `employee_code`, `first_name`, `last_name`,
`designation`, `staff_type` (`teaching`, `non_teaching`, `administrative`, `support`), `joining_date`.
Filters: `staff_type`, `department`, `status`. Delete = archive.

### Teacher class assignments: `/teacher-class-assignments`

Who teaches which subject to which section, for a session. One teacher per subject per section per session.

```json
POST /teacher-class-assignments
{ "teacher_id": "<teacher_id>", "section_id": "<section_id>", "subject_id": "<subject_id>",
  "academic_session_id": "<session_id>" }
```

Filters: `teacher_id`, `section_id`, `subject_id`, `academic_session_id`.

### Staff attendance: `/staff-attendance`

```json
POST /staff-attendance
{ "staff_id": "<staff_id>", "attendance_date": "2026-10-31", "attendance_type_id": "<id of 'P'>",
  "check_in_time": "08:05", "check_out_time": "15:30" }
```

Get the `attendance_type_id` values from `GET /attendance-types`. One record per staff member per day.
Filters: `staff_id`, `attendance_date`.

---

## 11. Academics (curriculum and timetable)

Permission: `academics:read` / `academics:write`.

### Class subjects: `/class-subjects` (assign subjects to classes)

```json
POST /class-subjects
{ "class_id": "<class_id>", "subject_id": "<subject_id>", "academic_session_id": "<session_id>",
  "is_mandatory": true, "periods_per_week": 6 }
```

Filters: `class_id`, `subject_id`, `academic_session_id`.

### Timetables: `/timetables`

One row per period.

```json
POST /timetables
{
  "section_id": "<section_id>",
  "academic_session_id": "<session_id>",
  "day_of_week": 1,
  "period_number": 1,
  "start_time": "08:00",
  "end_time": "08:45",
  "subject_id": "<subject_id>",
  "teacher_id": "<teacher_id>",
  "classroom_id": "<classroom_id>"
}
```

- `day_of_week`: **1 = Monday … 7 = Sunday**.
- 409 if the section already has that period, or the **teacher is already booked** in that slot.
- **A section's weekly timetable:** `GET /timetables?section_id=<id>&size=100&sort=day_of_week`
- **A teacher's timetable:** `GET /timetables?teacher_id=<id>&size=100`

---

## 12. Examinations

Permission: `exams:read` / `exams:write` (teachers have both).

### Step 1 — Grading scale: `/grades`

```json
POST /grades  { "name": "A+", "min_percentage": 90, "max_percentage": 100, "grade_point": 10 }
POST /grades  { "name": "A",  "min_percentage": 80, "max_percentage": 89.99, "grade_point": 9 }
POST /grades  { "name": "B",  "min_percentage": 60, "max_percentage": 79.99, "grade_point": 7 }
POST /grades  { "name": "C",  "min_percentage": 33, "max_percentage": 59.99, "grade_point": 5 }
POST /grades  { "name": "F",  "min_percentage": 0,  "max_percentage": 32.99, "grade_point": 0 }
```

### Step 2 — Exam: `/exams`

```json
POST /exams
{ "academic_session_id": "<session_id>", "name": "Mid-Term 2026", "exam_type": "midterm",
  "start_date": "2026-09-01", "end_date": "2026-09-10" }
```

`exam_type`: `unit_test`, `quarterly`, `midterm`, `half_yearly`, `final`, `annual`, `other`.
Filters: `academic_session_id`, `exam_type`, `is_published`.

### Step 3 — Papers: `/exam-subjects` (one per class per subject)

```json
POST /exam-subjects
{ "exam_id": "<exam_id>", "class_id": "<class_id>", "subject_id": "<math_id>",
  "max_marks": 100, "pass_marks": 33, "exam_date": "2026-09-02", "start_time": "09:00", "duration_minutes": 180 }
```

Filters: `exam_id`, `class_id`, `subject_id`.

### Step 4 — Enter marks: `POST /exams/{exam_id}/marks`

Saves a whole class's marks for one paper in one call. Sending it again **updates** the marks.

```json
POST /exams/<exam_id>/marks
{
  "exam_subject_id": "<math paper id>",
  "entries": [
    { "student_id": "<aisha>", "marks_obtained": 95 },
    { "student_id": "<bilal>", "marks_obtained": 70, "remarks": "Good improvement" },
    { "student_id": "<chen>",  "is_absent": true }
  ]
}
```

Response: `{ "exam_subject_id": "...", "saved": 3 }`

Checks: marks ≤ `max_marks` (400 otherwise), students must be enrolled in that class for the exam's session,
each student at most once, and `marks_obtained` is required unless `is_absent` is true.
The grade for each paper is calculated automatically from `/grades`.

### Step 5 — Results: `GET /exams/{exam_id}/results`

Optional filters: `class_id`, `section_id`, `student_id` (use `student_id` for one report card).

```json
{
  "exam_id": "...",
  "exam_name": "Mid-Term 2026",
  "students": [
    {
      "rank": 1,
      "student_id": "...",
      "admission_number": "ADM-001",
      "student_name": "Aisha Khan",
      "subjects": [
        { "subject_name": "Mathematics", "subject_code": "MATH5", "max_marks": "100.00", "pass_marks": "33.00",
          "marks_obtained": "95.00", "is_absent": false, "grade": "A+", "passed": true, "...": "..." },
        { "subject_name": "Science", "marks_obtained": "85.00", "grade": "A", "passed": true, "...": "..." }
      ],
      "total_obtained": "180.00",
      "total_max": "200.00",
      "percentage": "90.00",
      "grade": "A+",
      "result": "pass"
    }
  ]
}
```

- **Pass** means every paper is at or above its `pass_marks`. Absent in any paper means **fail**.
- **Rank:** students with the same percentage share a rank (1, 2, 2, 4).

### Raw marks: `/exam-results`

`GET` (filters `exam_subject_id`, `student_id`), `GET /{id}`, `DELETE /{id}`. Enter or change marks only with
`POST /exams/{exam_id}/marks`.

---

## 13. Attendance

Permission: `attendance:read` / `attendance:write` (teachers have both).

### Status codes (`/attendance-types`)

Created for you:

| Code | Name | Counts as present |
|---|---|:-:|
| `P` | Present | ✔ |
| `A` | Absent | |
| `L` | Late | ✔ |
| `HD` | Half Day | ✔ |
| `LV` | On Leave | |

You can add more with `POST /attendance-types` (`code`, `name`, `counts_as_present`).

### Mark attendance: `POST /attendance/mark`

```json
{
  "section_id": "<section_id>",
  "attendance_date": "2026-10-31",
  "entries": [
    { "student_id": "<aisha>", "status": "P" },
    { "student_id": "<bilal>", "status": "A", "remarks": "Fever" },
    { "student_id": "<chen>",  "status": "L" }
  ]
}
```

Response:

```json
{ "attendance_record_id": "...", "section_id": "...", "attendance_date": "2026-10-31",
  "period_number": null, "total": 3, "present": 2, "absent": 1 }
```

- `attendance_date` defaults to today and cannot be in the future.
- Leave out `period_number` for **daily** attendance. Send `1`, `2`, … for **per-period** attendance.
- `academic_session_id` defaults to the **current** session.
- **Marking the same section/date/period again updates it.** Use this to correct mistakes or mark late arrivals.
- 400 if a student is not enrolled in that section for the session, or a status code is unknown.

### Read attendance: `GET /attendance`

| Query | Example |
|---|---|
| By section and date | `?section_id=<id>&attendance_date=2026-10-31` |
| By student | `?student_id=<id>&date_from=2026-10-01&date_to=2026-10-31` |
| Only absentees today | `?section_id=<id>&attendance_date=2026-10-31&status=A` |
| Search by name | `?search=khan` |

Each item has `attendance_date`, `period_number`, `student_name`, `admission_number`, `status` (code),
`status_name`, `counts_as_present`, `remarks`.

### Summary: `GET /attendance/summary`

`?section_id=<id>` (whole class) **or** `?student_id=<id>`, plus optional `date_from`, `date_to`.

```json
{
  "date_from": "2026-10-01",
  "date_to": "2026-10-31",
  "students": [
    { "student_id": "...", "admission_number": "ADM-001", "student_name": "Aisha Khan",
      "total_days": 22, "present_days": 21, "absent_days": 1, "attendance_percentage": "95.45" }
  ],
  "overall_percentage": "91.20"
}
```

Only daily roll calls are counted, not per-period ones.

### Other attendance resources

| Path | Operations | Notes |
|---|---|---|
| `/attendance-records` | list, get, delete | One row per roll call (filters: `section_id`, `attendance_date`, `academic_session_id`). Deleting removes its entries |
| `/attendance-notifications` | CRUD | Log of SMS/email/push alerts to guardians (`channel`: sms, email, push, whatsapp) |
| `/staff-attendance` | CRUD | See [section 10](#10-teachers-and-staff) |

---

## 14. Fees

Permission: `fees:read` / `fees:write` (accountant and admin).

### How it fits together

```
fee_category (Tuition)  ─┐
                         ├─► fee_structure (Grade 5, 2026-27, Tuition, ₹1000 monthly)
class + session  ────────┘          │
                                    ▼  POST /student-fees/assign
                            student_fee (Aisha, due 2026-05-10, ₹1000 − ₹100 discount = ₹900)
                                    │
                                    ▼  POST /fee-payments (one or more)
                            fee_payment (₹400 UPI)  → status "partial"
                            fee_payment (₹500 cash) → status "paid"
```

### Step 1 — Categories and structures

```json
POST /fee-categories   { "name": "Tuition", "description": "Monthly tuition fee" }

POST /fee-structures
{ "academic_session_id": "<session_id>", "class_id": "<class_id>", "fee_category_id": "<tuition_id>",
  "amount": "1000.00", "frequency": "monthly", "due_day": 10 }
```

`frequency`: `one_time`, `monthly`, `quarterly`, `half_yearly`, `annual`.

### Step 2 (optional) — Discounts and scholarships

```json
POST /discounts     { "name": "Sibling discount", "discount_type": "percentage", "value": 10 }
POST /scholarships  { "name": "Merit 2026", "discount_type": "fixed", "value": 500,
                      "academic_session_id": "<session_id>", "criteria": "Above 90% in finals" }
```

`discount_type`: `percentage` (value 0–100) or `fixed` (an amount).

### Step 3 — Charge students: `POST /student-fees/assign`

```json
{
  "fee_structure_id": "<structure_id>",
  "due_date": "2026-05-10",
  "discount_id": "<optional>",
  "scholarship_id": "<optional>",
  "section_id": "<optional: only one section>",
  "student_ids": ["<optional: only these students>"]
}
```

Response:

```json
{ "fee_structure_id": "...", "due_date": "2026-05-10", "amount": "1000.00", "discount_amount": "100.00",
  "net_amount": "900.00", "created": 38, "skipped_existing": 2 }
```

Without `student_ids`, every student enrolled in the structure's class for its session is charged.
Running it twice is safe: students already charged for that due date are skipped. For monthly fees, call it
once per month with that month's `due_date`.

Single charges can also be created or edited directly with `/student-fees`
(filters: `student_id`, `fee_structure_id`, `status`, `due_date`). The response includes `net_amount`.
A fee that has payments cannot be deleted (409). Set `status: "waived"` or `"cancelled"` instead.

### Step 4 — Record a payment: `POST /fee-payments`

```json
{ "student_fee_id": "<student_fee_id>", "amount": "400.00", "payment_method": "upi",
  "reference_number": "UPI-4513890" }
```

Response `201`, which is the receipt:

```json
{
  "id": "...",
  "receipt_number": "RCP-20261031-9F2A11C4",
  "student_fee_id": "...",
  "amount": "400.00",
  "payment_method": "upi",
  "payment_date": "2026-10-31T09:41:12Z",
  "reference_number": "UPI-4513890",
  "received_by": "<your user id>",
  "fee_status": "partial",
  "balance_remaining": "500.00",
  "...": "..."
}
```

- `payment_method`: `cash`, `card`, `upi`, `bank_transfer`, `cheque`, `online`.
- Partial payments are allowed. **Paying more than the balance → 400** (the response includes the balance).
- Paying a fee that is already `paid`, `waived` or `cancelled` → 409.
- Payments cannot be edited or deleted. This keeps the financial record trustworthy.

### Payment history: `GET /fee-payments`

Filters: `student_id`, `date_from`, `date_to`, `payment_method`. Search: receipt number, admission number, name.
Each row includes the student's name, admission number, fee category and due date.
A single receipt: `GET /fee-payments/{id}`.

### Pending fees report: `GET /fees/pending`

Filters: `class_id`, `section_id`, `student_id`, `overdue_only=true`, `search`.

```json
{
  "items": [
    { "student_fee_id": "...", "student_id": "...", "admission_number": "ADM-002", "student_name": "Bilal Shaikh",
      "class_name": "Grade 5", "fee_category": "Tuition", "due_date": "2026-05-10",
      "net_amount": "900.00", "paid_amount": "0.00", "balance": "900.00", "status": "pending", "is_overdue": true }
  ],
  "total": 2, "page": 1, "size": 20, "pages": 1,
  "total_outstanding": "1800.00"
}
```

`total_outstanding` is the sum over **all** matching rows, not just the current page.
**One student's dues:** `GET /fees/pending?student_id=<id>`.

### Payment gateway transactions: `/payment-transactions`

Read-only (list, get). Filters: `student_id`, `status`, `provider`. The raw gateway payload is never returned.

---

## 15. Library

Permission: `library:read` / `library:write`.

### Books

```json
POST /book-categories  { "name": "Biography" }

POST /books
{ "title": "Wings of Fire", "author": "A. P. J. Abdul Kalam", "isbn": "978-8173711466",
  "category_id": "<category_id>", "publisher": "Universities Press", "total_copies": 3, "shelf_location": "B-2" }
```

`available_copies` is set to `total_copies` and then updated automatically by issues and returns.
Reducing `total_copies` below the number on loan → 409. Filters: `category_id`, `author`; search: title, author, isbn, publisher.

### Issue a book: `POST /library/issues`

```json
{ "book_id": "<book_id>", "student_id": "<student_id>", "due_date": "2026-11-14" }
```

Send **either** `student_id` **or** `staff_id`. `issue_date` defaults to today. 409 if no copy is available.

### Return a book: `POST /library/issues/{issue_id}/return`

```json
{ "condition": "good", "fine_amount": "0", "remarks": "On time" }
```

Response: `{ "issue": {..., "status": "returned"}, "book_return": {...}, "overdue_days": 0 }`

- `condition`: `good`, `damaged`, or `lost`. **Lost** removes the copy from `total_copies`.
- `return_date` defaults to today. `overdue_days` helps you work out the `fine_amount`.
- Returning the same issue twice → 409.

### List issues: `GET /library/issues`

Filters: `status` (`issued`, `returned`, `lost`), `student_id`, `staff_id`, `book_id`, **`overdue=true`**
(still out after the due date). Each item has `is_overdue`.

---

## 16. Transport

Permission: `transport:read` / `transport:write`. All four are standard CRUD.

```json
POST /vehicles
{ "registration_number": "MH12AB1234", "vehicle_type": "bus", "capacity": 40, "model": "Tata Starbus",
  "insurance_expiry": "2027-03-31", "fitness_expiry": "2027-01-15" }

POST /drivers            (create the driver as /staff first)
{ "staff_id": "<staff_id>", "license_number": "MH1220190012345", "license_expiry": "2029-06-30" }

POST /transport-routes
{ "name": "Route 1 - Kothrud", "start_point": "Kothrud Depot", "end_point": "School",
  "vehicle_id": "<vehicle_id>", "driver_id": "<driver_id>", "fare": "800.00",
  "stops": [ { "name": "Kothrud Depot", "pickup_time": "07:00" }, { "name": "Paud Phata", "pickup_time": "07:15" } ] }

POST /student-transport-assignments
{ "student_id": "<student_id>", "route_id": "<route_id>", "academic_session_id": "<session_id>",
  "start_date": "2026-04-01", "pickup_stop": "Paud Phata" }
```

| Resource | Filters | Search |
|---|---|---|
| `/vehicles` | `vehicle_type` (bus, van, car, other), `is_active` | registration number, model |
| `/drivers` | `is_active` | license number |
| `/transport-routes` | `vehicle_id`, `driver_id`, `is_active` | name, start point, end point |
| `/student-transport-assignments` | `student_id`, `route_id`, `academic_session_id` | — |

A student can have one route per session. **Everyone on a route:** `GET /student-transport-assignments?route_id=<id>`.

---

## 17. Communication

### Announcements: `/announcements` (standard CRUD)

Read: `communication:read` (every role). Write: `communication:write` (admin, principal, teacher).

```json
POST /announcements
{ "title": "Diwali holidays", "body": "School will remain closed from 1st to 5th November.",
  "audience": "all", "is_published": true, "published_at": "2026-10-28T09:00:00Z",
  "expires_at": "2026-11-06T00:00:00Z" }
```

`audience`: `all`, `students`, `parents`, `teachers`, `staff`, `class` (needs `class_id`), `section` (needs `section_id`).
Filters: `audience`, `is_published`, `class_id`, `section_id`. Search: title, body. `created_by` is filled in automatically.

### Messages (between users)

Needs `communication:read`. You only ever see **your own** messages.

| Method | Path | |
|---|---|---|
| POST | `/messages` | `{ "recipient_id": "<user_id>", "body": "Hello", "thread_id": "<optional>" }` |
| GET | `/messages?box=inbox` | Received (`unread_only=true` for unread). `box=sent` for sent |
| GET | `/messages/{id}` | One message (sender or recipient only) |
| POST | `/messages/{id}/read` | Mark as read (recipient only) |

`recipient_id` is a **user id** (from `/users` or the `user_id` on a staff, guardian or student record).

### Parent–teacher threads: `/parent-teacher-threads`

A conversation about one student between a guardian and a teacher. Staff create, list and manage threads
(`communication:write` for all operations, because the list contains every family's conversations):

```json
POST /parent-teacher-threads
{ "guardian_id": "<guardian_id>", "teacher_id": "<teacher_id>", "student_id": "<student_id>",
  "subject": "Maths homework" }
```

Then the guardian's user and the teacher's user exchange messages with `POST /messages` and `thread_id`.
Both must have login accounts linked through `user_id`.
`GET /parent-teacher-threads/{id}/messages` lists the conversation. The guardian and teacher in the thread can
read it; so can staff with `communication:write`. A closed thread (`status: "closed"`) accepts no new messages.

### Notifications

| Method | Path | Who | |
|---|---|---|---|
| GET | `/notifications/me` | any logged-in user | Your notifications (`unread_only=true`) |
| POST | `/notifications/{id}/read` | owner | Mark one as read |
| POST | `/notifications/me/read-all` | any logged-in user | Mark all as read → `{ "updated": 3 }` |
| POST | `/notifications` | communication:write | Send one: `{ "user_id", "notification_type", "title", "body", "data" }` |
| GET / DELETE | `/notifications` | communication:write | Staff view of everyone's notifications (filters `user_id`, `notification_type`) |

`data` is free-form JSON. For example, `{ "screen": "fees", "student_fee_id": "..." }` can tell the Flutter app which page to open.

---

## 18. Dashboard

`GET /dashboard/summary`, permission `dashboard:read` (admin, principal, accountant).

```json
{
  "total_students": 412,
  "total_teachers": 28,
  "total_staff": 41,
  "total_classes": 12,
  "total_sections": 24,
  "today_attendance": { "date": "2026-10-31", "students_marked": 398, "present": 377, "absent": 21,
                        "attendance_percentage": "94.72" },
  "fees": { "total_collected": "1840500.00", "collected_this_month": "212000.00",
            "pending_count": 57, "pending_amount": "51300.00", "overdue_count": 19 },
  "upcoming_exams": [ { "id": "...", "name": "Mid-Term 2026", "exam_type": "midterm",
                        "start_date": "2026-11-10", "end_date": "2026-11-20" } ]
}
```

All the numbers come from one database query, so it is fast enough for a dashboard home screen.
"Today" uses the server's date. `attendance_percentage` is `null` if no attendance has been marked today.

---

## 19. System settings and audit log

### Settings: `/system-settings` (permission `settings:*`)

Key–value store for configuration. `value` is always a JSON object.

```json
POST /system-settings
{ "key": "library.fine_per_day", "value": { "amount": 5 }, "description": "Late fine per day (INR)" }

POST /system-settings
{ "key": "school.motto", "value": { "text": "Learn, Lead, Serve" }, "is_public": true }
```

`key`: lowercase letters, digits, `_` and `.` only. **`GET /system-settings/public`** needs no login and returns only
settings with `is_public: true`. Use it for the app's splash and login screens.

### Audit log: `/audit-logs` (permission `audit:read`, read-only)

Every create, update, delete, login, payment, marks entry and attendance marking is recorded with **who**, **what**,
**when**, IP address and changed values. Passwords and tokens are always masked as `***`.

Filters: `user_id`, `entity_type` (table name, e.g. `students`, `fee_payments`), `entity_id`, `action`
(e.g. `create`, `update`, `archive`, `login`, `record_payment`, `enter_marks`, `mark_attendance`).

**History of one student:** `GET /audit-logs?entity_type=students&entity_id=<id>`

---

## 20. Using the API from Flutter and React

### Token handling (both apps)

1. `POST /auth/login` → store `access_token` and `refresh_token`.
   - Flutter: `flutter_secure_storage`.
   - React: keep the access token in memory. Store the refresh token carefully (an httpOnly cookie through your own proxy is safest).
2. Send `Authorization: Bearer <access_token>` on every request.
3. On a **401**, call `POST /auth/refresh` **once**, save **both** new tokens, and retry the request.
   If refresh also fails → go to the login screen.
4. Make sure only **one** refresh runs at a time. Two parallel refreshes with the same token trigger reuse detection and sign the user out.
5. On logout: `POST /auth/logout` with the refresh token, then clear storage.

### Flutter (Dio) sketch

```dart
final dio = Dio(BaseOptions(baseUrl: 'http://10.0.2.2:8000/api/v1')); // Android emulator → your Mac

dio.interceptors.add(InterceptorsWrapper(
  onRequest: (options, handler) async {
    final token = await storage.read(key: 'access_token');
    if (token != null) options.headers['Authorization'] = 'Bearer $token';
    handler.next(options);
  },
  onError: (e, handler) async {
    if (e.response?.statusCode == 401 && e.requestOptions.extra['retried'] != true) {
      final refreshed = await refreshTokens(); // POST /auth/refresh, save both tokens
      if (refreshed) {
        e.requestOptions.extra['retried'] = true;
        return handler.resolve(await dio.fetch(e.requestOptions));
      }
    }
    handler.next(e);
  },
));

// Error message for a SnackBar:
String apiMessage(DioException e) => e.response?.data?['error']?['message'] ?? 'Something went wrong';
```

From a **physical phone**, use your Mac's LAN IP (e.g. `http://192.168.1.20:8000`) and start the server with
`uvicorn app.main:app --host 0.0.0.0 --port 8000`.

### React (fetch) sketch

```js
const API = 'http://127.0.0.1:8000/api/v1';

export async function api(path, { method = 'GET', body, params } = {}) {
  const url = new URL(API + path);
  if (params) Object.entries(params).forEach(([k, v]) => v != null && url.searchParams.set(k, v));
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAccessToken()}` },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw Object.assign(new Error(data.error.message), { status: res.status, details: data.error.details });
  return data;
}

// A paginated table:
const { items, total, pages } = await api('/students', { params: { section_id, search, page, size: 20 } });
```

**CORS:** the API accepts browser requests from `http://localhost:3000` and `http://localhost:5173`. Add your
dashboard's URL to `CORS_ORIGINS` in `.env` when you deploy it.

### Generate a typed client automatically

The OpenAPI file describes every endpoint and model:

- **React/TypeScript:** `npx openapi-typescript http://127.0.0.1:8000/api/v1/openapi.json -o src/api/schema.d.ts`
- **Flutter:** the `openapi_generator` package (dart-dio) can build a full client from the same URL.
