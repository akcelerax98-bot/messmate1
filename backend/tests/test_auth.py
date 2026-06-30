"""MessMate backend auth tests (Part 1)."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") if os.environ.get("EXPO_PUBLIC_BACKEND_URL") else None
# Fallback: read frontend/.env
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- Module: root health ---
class TestHealth:
    def test_root_status(self, session):
        r = session.get(f"{API}/")
        assert r.status_code == 200
        j = r.json()
        assert j.get("app") == "MessMate"
        assert j.get("status") == "ok"


# --- Module: login (all four seed accounts + bad creds) ---
class TestLogin:
    def test_admin_login(self, session):
        r = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "admin",
            "password": "admin123",
            "institution_or_hostel_name": "Demo Hostel",
        })
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["access_token"]
        assert j["user"]["role"] == "admin"
        assert j["user"]["approval_status"] == "approved"

    def test_student_approved_login(self, session):
        r = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "student", "password": "student123",
        })
        assert r.status_code == 200
        j = r.json()
        assert j["user"]["role"] == "student"
        assert j["user"]["approval_status"] == "approved"

    def test_pending_login(self, session):
        r = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "pending", "password": "pending123",
        })
        assert r.status_code == 200
        j = r.json()
        assert j["access_token"]
        assert j["user"]["approval_status"] == "pending"

    def test_blocked_login(self, session):
        r = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "blocked", "password": "blocked123",
        })
        assert r.status_code == 200
        j = r.json()
        assert j["access_token"]
        assert j["user"]["approval_status"] == "rejected_or_blocked"

    def test_wrong_password(self, session):
        r = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "student", "password": "wrong",
        })
        assert r.status_code == 401
        assert r.json().get("detail") == "Invalid credentials"


# --- Module: register-student ---
class TestRegister:
    new_mobile = f"TEST_{uuid.uuid4().hex[:10]}"

    def test_register_success(self, session):
        r = session.post(f"{API}/auth/register-student", json={
            "full_name": "TEST User",
            "mobile_or_user_id": self.new_mobile,
            "institution_or_hostel_name": "TEST Hostel",
            "room_number": "Z999",
            "password": "secret123",
        })
        assert r.status_code == 201, r.text
        j = r.json()
        assert j["approval_status"] == "pending"
        assert j["role"] == "student"
        assert j["mobile_or_user_id"] == self.new_mobile

    def test_register_duplicate(self, session):
        r = session.post(f"{API}/auth/register-student", json={
            "full_name": "Dup",
            "mobile_or_user_id": "student",
            "institution_or_hostel_name": "Demo Hostel",
            "room_number": "X1",
            "password": "secret123",
        })
        assert r.status_code == 400


# --- Module: /auth/me + token guards ---
class TestMe:
    def test_me_with_valid_token(self, session):
        login = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "student", "password": "student123",
        }).json()
        token = login["access_token"]
        r = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["mobile_or_user_id"] == "student"

    def test_me_without_token(self, session):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_invalid_token(self, session):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401


# --- Module: MOCKED OTP endpoints ---
class TestOtp:
    def test_request_otp(self, session):
        r = session.post(f"{API}/auth/request-otp?mobile_or_user_id=student")
        assert r.status_code == 200
        assert r.json().get("mock_otp") == "123456"

    def test_verify_otp_success(self, session):
        r = session.post(f"{API}/auth/verify-otp?mobile_or_user_id=student&otp=123456")
        assert r.status_code == 200

    def test_verify_otp_invalid(self, session):
        r = session.post(f"{API}/auth/verify-otp?mobile_or_user_id=student&otp=000000")
        assert r.status_code == 400
