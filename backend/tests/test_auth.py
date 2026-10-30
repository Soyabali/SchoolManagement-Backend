from tests.conftest import PASSWORD, Api, login


def test_health(client):
    assert Api(client)("GET", "/health") == {"status": "ok", "database": "connected"}


def test_first_user_is_admin_then_registration_closes(client, admin):
    me = admin("GET", "/auth/me")
    assert me["roles"] == ["admin"]
    assert "students:write" in me["permissions"]
    assert "password_hash" not in me

    Api(client)("POST", "/auth/register", 401,
                json={"email": "intruder@demoschool.com", "password": PASSWORD, "full_name": "Intruder"})


def test_login_failures_do_not_reveal_accounts(client, admin):
    wrong_pw = Api(client)("POST", "/auth/login", 401, json={"email": "admin@demoschool.com", "password": "nope12345"})
    no_user = Api(client)("POST", "/auth/login", 401, json={"email": "ghost@demoschool.com", "password": "nope12345"})
    assert wrong_pw == no_user


def test_email_is_case_insensitive(client, admin):
    assert login(client, "ADMIN@DemoSchool.COM")["token_type"] == "bearer"
    admin("POST", "/users", 409, json={"email": "Admin@demoschool.com", "password": PASSWORD,
                                       "full_name": "Dup", "roles": ["teacher"]})


def test_refresh_rotation_and_reuse_detection(client, admin):
    tokens = login(client, "admin@demoschool.com")
    api = Api(client)
    rotated = api("POST", "/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert rotated["refresh_token"] != tokens["refresh_token"]

    # Re-using the old token revokes every session, including the rotated one.
    api("POST", "/auth/refresh", 401, json={"refresh_token": tokens["refresh_token"]})
    api("POST", "/auth/refresh", 401, json={"refresh_token": rotated["refresh_token"]})


def test_logout_revokes_refresh_token(client, admin):
    tokens = login(client, "admin@demoschool.com")
    Api(client)("POST", "/auth/logout", 204, json={"refresh_token": tokens["refresh_token"]})
    Api(client)("POST", "/auth/refresh", 401, json={"refresh_token": tokens["refresh_token"]})


def test_swagger_form_login(client, admin):
    r = client.post("/api/v1/auth/token", data={"username": "admin@demoschool.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["access_token"]


def test_bad_and_missing_tokens(client):
    Api(client)("GET", "/auth/me", 401)
    Api(client, "not-a-jwt")("GET", "/auth/me", 401)


def test_rbac(make_user, admin):
    accountant, _ = make_user("accountant@demoschool.com", "accountant")
    accountant("GET", "/fees/pending")
    accountant("GET", "/students")
    accountant("POST", "/classes", 403, json={"name": "Nope"})
    accountant("GET", "/audit-logs", 403)

    parent, _ = make_user("parent@demoschool.com", "parent")
    parent("GET", "/students", 403)
    parent("GET", "/announcements")

    # Only an admin can create admins.
    principal, _ = make_user("principal@demoschool.com", "principal")
    principal("POST", "/users", 403, json={"email": "p2@demoschool.com", "password": PASSWORD,
                                           "full_name": "P2", "roles": ["admin"]})


def test_deactivated_user_is_locked_out(client, make_user, admin):
    api, user = make_user("leaver@demoschool.com", "teacher")
    admin("PATCH", f"/users/{user['id']}", json={"is_active": False})
    api("GET", "/auth/me", 401)
    Api(client)("POST", "/auth/login", 401, json={"email": "leaver@demoschool.com", "password": PASSWORD})


def test_change_password(client, make_user):
    api, _ = make_user("changer@demoschool.com", "teacher")
    api("POST", "/auth/change-password", 400, json={"current_password": "wrong", "new_password": "NewPassw0rd"})
    api("POST", "/auth/change-password", 204, json={"current_password": PASSWORD, "new_password": "NewPassw0rd"})
    login(client, "changer@demoschool.com", "NewPassw0rd")


def test_audit_log_never_contains_secrets(admin):
    entries = admin("GET", "/audit-logs", params={"entity_type": "users", "size": 100})["items"]
    assert entries
    text = str(entries)
    assert PASSWORD not in text and "password_hash" not in text
