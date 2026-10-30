from datetime import date, timedelta


def test_validation_errors_do_not_echo_input(admin):
    body = admin("POST", "/students", 422, json={
        "admission_number": "X1", "first_name": "A", "last_name": "B", "date_of_birth": "2999-01-01",
        "gender": "male", "secret_field": "s3cr3t"})
    assert body["error"]["code"] == "validation_error"
    fields = {d["field"] for d in body["error"]["details"]}
    assert "body.date_of_birth" in fields and "body.secret_field" in fields
    assert "s3cr3t" not in str(body)


def test_students_crud_filter_search_and_archive(admin, school):
    section_id = school["section"]["id"]
    listed = admin("GET", "/students", params={"section_id": section_id})
    assert listed["total"] == 3 and listed["pages"] == 1

    assert admin("GET", "/students", params={"search": "shai"})["items"][0]["last_name"] == "Shaikh"
    assert admin("GET", "/students", params={"sort": "first_name"})["items"][0]["first_name"] == "Aisha"
    admin("GET", "/students", 400, params={"sort": "nope"})

    extra = admin("POST", "/students", 201, json={"admission_number": "ADM-900", "first_name": "Temp",
                                                  "last_name": "Kid", "date_of_birth": "2017-01-01",
                                                  "gender": "other"})
    assert extra["full_name"] == "Temp Kid"
    admin("POST", "/students", 409, json={"admission_number": "ADM-900", "first_name": "Dup", "last_name": "X",
                                          "date_of_birth": "2017-01-01", "gender": "male"})
    assert admin("PUT", f"/students/{extra['id']}", json={"first_name": "Tempo"})["first_name"] == "Tempo"
    assert admin("PATCH", f"/students/{extra['id']}", json={"blood_group": "O+"})["blood_group"] == "O+"
    admin("DELETE", f"/students/{extra['id']}", 204)
    admin("GET", f"/students/{extra['id']}", 404)


def test_guardians(admin, school):
    student = school["students"][0]
    guardian = admin("POST", "/guardians", 201, json={"first_name": "Sara", "last_name": "Khan", "phone": "+919800000001"})
    link = admin("PUT", f"/students/{student['id']}/guardians/{guardian['id']}",
                 json={"relation": "mother", "is_primary": True})
    assert link["guardian"]["first_name"] == "Sara"
    assert len(admin("GET", f"/students/{student['id']}/guardians")) == 1
    admin("DELETE", f"/students/{student['id']}/guardians/{guardian['id']}", 204)


def test_foreign_key_restrict_returns_409(admin, school):
    admin("POST", "/class-subjects", 201, json={"class_id": school["class"]["id"],
                                                "subject_id": school["math"]["id"],
                                                "academic_session_id": school["session"]["id"]})
    body = admin("DELETE", f"/subjects/{school['math']['id']}", 409)
    assert body["error"]["code"] == "constraint_violation"


def test_teachers_crud(admin, school):
    teacher = admin("POST", "/teachers", 201, json={
        "staff": {"employee_code": "EMP-001", "first_name": "Ravi", "last_name": "Kumar",
                  "joining_date": "2024-06-01", "department": "Science"},
        "qualification": "M.Sc", "subject_ids": [school["science"]["id"]]})
    assert teacher["staff"]["staff_type"] == "teaching"
    assert [s["code"] for s in teacher["subjects"]] == ["SCI5"]

    assert admin("GET", "/teachers", params={"search": "ravi"})["total"] == 1
    assert admin("GET", "/teachers", params={"subject_id": school["science"]["id"]})["total"] == 1
    updated = admin("PATCH", f"/teachers/{teacher['id']}",
                    json={"staff": {"designation": "Senior Teacher"}, "subject_ids": []})
    assert updated["staff"]["designation"] == "Senior Teacher" and updated["subjects"] == []

    admin("POST", "/teacher-class-assignments", 201, json={
        "teacher_id": teacher["id"], "section_id": school["section"]["id"],
        "subject_id": school["science"]["id"], "academic_session_id": school["session"]["id"]})
    admin("DELETE", f"/teachers/{teacher['id']}", 204)
    admin("GET", f"/teachers/{teacher['id']}", 404)


def test_attendance_flow(admin, school, make_user):
    a, b, c = (s["id"] for s in school["students"])
    section_id = school["section"]["id"]
    today = date.today().isoformat()
    teacher, _ = make_user("teacher.att@demoschool.com", "teacher")

    result = teacher("POST", "/attendance/mark", json={"section_id": section_id, "attendance_date": today,
        "entries": [{"student_id": a, "status": "P"}, {"student_id": b, "status": "A"}, {"student_id": c, "status": "L"}]})
    assert (result["present"], result["absent"]) == (2, 1)

    # Re-marking the same day updates instead of duplicating.
    again = teacher("POST", "/attendance/mark", json={"section_id": section_id, "attendance_date": today,
                                                       "entries": [{"student_id": b, "status": "p"}]})
    assert again["attendance_record_id"] == result["attendance_record_id"]

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    teacher("POST", "/attendance/mark", json={"section_id": section_id, "attendance_date": yesterday,
        "entries": [{"student_id": a, "status": "A"}, {"student_id": b, "status": "P"}, {"student_id": c, "status": "P"}]})

    assert admin("GET", "/attendance", params={"section_id": section_id, "attendance_date": today})["total"] == 3
    assert admin("GET", "/attendance", params={"student_id": a})["total"] == 2
    summary = admin("GET", "/attendance/summary", params={"section_id": section_id})
    by_id = {s["student_id"]: s for s in summary["students"]}
    assert by_id[a]["attendance_percentage"] == "50.00"
    assert by_id[b]["present_days"] == 2
    assert summary["overall_percentage"] == "83.33"

    admin("POST", "/attendance/mark", 400, json={"section_id": section_id,
                                                  "entries": [{"student_id": a, "status": "ZZ"}]})
    outsider = admin("POST", "/students", 201, json={"admission_number": "ADM-777", "first_name": "Out",
                                                     "last_name": "Sider", "date_of_birth": "2016-01-01",
                                                     "gender": "male"})
    admin("POST", "/attendance/mark", 400, json={"section_id": section_id,
                                                  "entries": [{"student_id": outsider["id"], "status": "P"}]})
    admin("POST", "/attendance/mark", 422, json={"section_id": section_id, "attendance_date": "2999-01-01",
                                                  "entries": [{"student_id": a, "status": "P"}]})


def test_exam_flow(admin, school):
    for name, lo, hi in [("A", 80, 100), ("B", 60, 79.99), ("C", 33, 59.99), ("F", 0, 32.99)]:
        admin("POST", "/grades", 201, json={"name": name, "min_percentage": lo, "max_percentage": hi})
    exam = admin("POST", "/exams", 201, json={"academic_session_id": school["session"]["id"], "name": "Mid-Term",
                                              "exam_type": "midterm", "start_date": "2026-09-01",
                                              "end_date": "2026-09-10"})
    papers = {}
    for key in ("math", "science"):
        papers[key] = admin("POST", "/exam-subjects", 201, json={
            "exam_id": exam["id"], "class_id": school["class"]["id"], "subject_id": school[key]["id"],
            "max_marks": 100, "pass_marks": 33})
    a, b, c = (s["id"] for s in school["students"])

    admin("POST", f"/exams/{exam['id']}/marks", 400, json={"exam_subject_id": papers["math"]["id"],
                                                           "entries": [{"student_id": a, "marks_obtained": 101}]})
    admin("POST", f"/exams/{exam['id']}/marks", json={"exam_subject_id": papers["math"]["id"], "entries": [
        {"student_id": a, "marks_obtained": 95}, {"student_id": b, "marks_obtained": 70},
        {"student_id": c, "is_absent": True}]})
    saved = admin("POST", f"/exams/{exam['id']}/marks", json={"exam_subject_id": papers["science"]["id"], "entries": [
        {"student_id": a, "marks_obtained": 85}, {"student_id": b, "marks_obtained": 20},
        {"student_id": c, "marks_obtained": 50}]})
    assert saved["saved"] == 3

    results = admin("GET", f"/exams/{exam['id']}/results")["students"]
    first = results[0]
    assert (first["student_id"], first["rank"], first["percentage"], first["grade"], first["result"]) == \
        (a, 1, "90.00", "A", "pass")
    by_id = {r["student_id"]: r for r in results}
    assert by_id[b]["result"] == "fail"  # science below pass marks
    assert by_id[c]["result"] == "fail"  # absent in math
    assert admin("GET", "/exam-results", params={"student_id": a})["total"] == 2


def test_fee_flow(admin, school):
    category = admin("POST", "/fee-categories", 201, json={"name": "Tuition"})
    structure = admin("POST", "/fee-structures", 201, json={
        "academic_session_id": school["session"]["id"], "class_id": school["class"]["id"],
        "fee_category_id": category["id"], "amount": "1000.00", "frequency": "monthly", "due_day": 10})
    discount = admin("POST", "/discounts", 201, json={"name": "Sibling", "discount_type": "percentage", "value": 10})

    past_due = (date.today() - timedelta(days=5)).isoformat()
    assigned = admin("POST", "/student-fees/assign", 201, json={
        "fee_structure_id": structure["id"], "due_date": past_due, "discount_id": discount["id"]})
    assert (assigned["created"], assigned["net_amount"]) == (3, "900.00")
    assert admin("POST", "/student-fees/assign", 201,
                 json={"fee_structure_id": structure["id"], "due_date": past_due})["skipped_existing"] == 3

    a = school["students"][0]["id"]
    fee = admin("GET", "/student-fees", params={"student_id": a})["items"][0]
    assert fee["net_amount"] == "900.00"

    part = admin("POST", "/fee-payments", 201, json={"student_fee_id": fee["id"], "amount": "400", "payment_method": "upi"})
    assert (part["fee_status"], part["balance_remaining"]) == ("partial", "500.00")
    assert part["receipt_number"].startswith("RCP-")
    admin("POST", "/fee-payments", 400, json={"student_fee_id": fee["id"], "amount": "600", "payment_method": "cash"})
    paid = admin("POST", "/fee-payments", 201, json={"student_fee_id": fee["id"], "amount": "500", "payment_method": "cash"})
    assert paid["fee_status"] == "paid"
    admin("POST", "/fee-payments", 409, json={"student_fee_id": fee["id"], "amount": "1", "payment_method": "cash"})

    assert admin("GET", "/fee-payments", params={"student_id": a})["total"] == 2
    pending = admin("GET", "/fees/pending", params={"overdue_only": True})
    assert pending["total"] == 2 and pending["total_outstanding"] == "1800.00"
    assert all(row["is_overdue"] for row in pending["items"])
    admin("DELETE", f"/student-fees/{fee['id']}", 409)  # has payments


def test_library_flow(admin, school):
    book = admin("POST", "/books", 201, json={"title": "Wings of Fire", "author": "A. P. J. Abdul Kalam",
                                              "total_copies": 1})
    assert book["available_copies"] == 1
    a, b = school["students"][0]["id"], school["students"][1]["id"]
    issue = admin("POST", "/library/issues", 201, json={"book_id": book["id"], "student_id": a,
                                                        "due_date": (date.today() + timedelta(days=14)).isoformat()})
    admin("POST", "/library/issues", 409, json={"book_id": book["id"], "student_id": b,
                                                "due_date": (date.today() + timedelta(days=14)).isoformat()})
    assert admin("GET", f"/books/{book['id']}")["available_copies"] == 0
    admin("PATCH", f"/books/{book['id']}", 409, json={"total_copies": 0})

    returned = admin("POST", f"/library/issues/{issue['id']}/return", json={"condition": "good"})
    assert returned["issue"]["status"] == "returned" and returned["overdue_days"] == 0
    admin("POST", f"/library/issues/{issue['id']}/return", 409, json={})
    assert admin("GET", f"/books/{book['id']}")["available_copies"] == 1


def test_transport(admin, school):
    vehicle = admin("POST", "/vehicles", 201, json={"registration_number": "MH01AB1234", "vehicle_type": "bus",
                                                    "capacity": 40})
    route = admin("POST", "/transport-routes", 201, json={
        "name": "Route 1", "start_point": "Depot", "end_point": "School", "vehicle_id": vehicle["id"],
        "fare": "800", "stops": [{"name": "Market", "pickup_time": "07:15"}]})
    assert route["stops"][0]["pickup_time"] == "07:15"
    admin("POST", "/student-transport-assignments", 201, json={
        "student_id": school["students"][0]["id"], "route_id": route["id"],
        "academic_session_id": school["session"]["id"], "start_date": "2026-04-01"})


def test_messages_and_notifications(admin, make_user, client):
    teacher, teacher_user = make_user("teacher.msg@demoschool.com", "teacher")
    sent = admin("POST", "/messages", 201, json={"recipient_id": teacher_user["id"], "body": "Staff meeting at 3pm"})
    inbox = teacher("GET", "/messages", params={"box": "inbox", "unread_only": True})
    assert inbox["total"] == 1
    assert teacher("POST", f"/messages/{sent['id']}/read")["read_at"]
    admin("POST", f"/messages/{sent['id']}/read", 403)  # only the recipient

    admin("POST", "/notifications", 201, json={"user_id": teacher_user["id"], "notification_type": "info",
                                               "title": "Welcome"})
    assert teacher("GET", "/notifications/me", params={"unread_only": True})["total"] == 1
    assert teacher("POST", "/notifications/me/read-all")["updated"] == 1


def test_announcements_and_settings(admin, make_user, client):
    admin("POST", "/announcements", 422, json={"title": "X", "body": "Y", "audience": "class"})
    ann = admin("POST", "/announcements", 201, json={"title": "Holiday", "body": "School closed Friday",
                                                     "is_published": True})
    assert ann["created_by"]
    admin("POST", "/system-settings", 201, json={"key": "school.motto", "value": {"text": "Learn"}, "is_public": True})
    admin("POST", "/system-settings", 201, json={"key": "sms.api_key", "value": {"key": "hidden"}})
    public = client.get("/api/v1/system-settings/public").json()
    assert [s["key"] for s in public] == ["school.motto"]


def test_dashboard(admin, school):
    data = admin("GET", "/dashboard/summary")
    assert data["total_students"] >= 3
    assert data["today_attendance"]["students_marked"] == 3
    assert data["fees"]["pending_count"] == 2
    assert data["fees"]["total_collected"] == "900.00"
    assert data["upcoming_exams"] == [] or data["upcoming_exams"][0]["name"]


def test_other_users_data_is_staff_only(make_user):
    parent, _ = make_user("parent2@demoschool.com", "parent")
    parent("GET", "/notifications", 403)
    parent("GET", "/parent-teacher-threads", 403)
    parent("GET", "/notifications/me")  # own notifications are fine


def test_money_always_has_two_decimals(admin, school):
    zero_paid = [row["paid_amount"] for row in admin("GET", "/fees/pending")["items"]]
    assert zero_paid and all(v == "0.00" for v in zero_paid)
