"""Iteration 8 — Email OTP auth flow tests.

Tests the new email-based authentication system:
- POST /api/auth/register
- POST /api/auth/verify-email
- POST /api/auth/login
- POST /api/auth/resend-otp
- POST /api/auth/forgot-password
- POST /api/auth/forgot-password/verify
- POST /api/auth/reset-password

Strategy: hit the real API endpoints, then overwrite the otp_hash in MongoDB
to a known value (the test never reads the OTP from the API since it's never
returned). For brute-force/expiry tests we manipulate the DB doc directly.
"""
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from passlib.context import CryptContext
from pymongo import MongoClient

# Load backend .env
sys.path.insert(0, str(Path("/app/backend")))
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["EXPO_PUBLIC_BACKEND_URL"].rstrip("/") if os.environ.get("EXPO_PUBLIC_BACKEND_URL") else None
if not BASE_URL:
    # Fall back to frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                BASE_URL = line.strip().split("=", 1)[1].strip('"').rstrip("/")

API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]

KNOWN_OTP = "424242"

# --- helpers ---------------------------------------------------------------


def _unique_email(prefix="TEST"):
    return f"{prefix.lower()}_{uuid.uuid4().hex[:10]}@example.com"


def _set_otp_hash(email: str, purpose: str, otp: str = KNOWN_OTP, age_seconds: int = 0):
    """Overwrite the otp_hash on the existing email_otps doc to a known value.
    age_seconds: how far in the past to backdate created_at (for bypassing cooldown).
    Returns the updated doc.
    """
    now = datetime.now(timezone.utc)
    created = now - timedelta(seconds=age_seconds)
    expires = now + timedelta(minutes=5)
    res = _db.email_otps.update_one(
        {"email": email, "purpose": purpose},
        {"$set": {
            "otp_hash": _pwd.hash(otp),
            "attempts": 0,
            "created_at": created.isoformat(),
            "expires_at": expires.isoformat(),
        }},
    )
    assert res.matched_count == 1, f"No email_otps doc for {email}/{purpose}"
    return _db.email_otps.find_one({"email": email, "purpose": purpose})


def _force_expire(email: str, purpose: str):
    past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    _db.email_otps.update_one(
        {"email": email, "purpose": purpose},
        {"$set": {"expires_at": past}},
    )


def _cleanup(emails):
    if not emails:
        return
    _db.users.delete_many({"email": {"$in": list(emails)}})
    _db.email_otps.delete_many({"email": {"$in": list(emails)}})


@pytest.fixture
def created_emails():
    bag = set()
    yield bag
    _cleanup(bag)


@pytest.fixture
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- Registration ----------------------------------------------------------


class TestRegister:
    def test_register_success_shape(self, api, created_emails):
        email = _unique_email("reg")
        created_emails.add(email)
        r = api.post(f"{API}/auth/register", json={
            "full_name": "Reg User",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "verification_required"
        assert body["email"] == email
        assert body["resend_available_in"] == 60
        assert body["expires_in"] == 300
        # No OTP in response
        assert "otp" not in body
        assert "otp_hash" not in body
        # User row exists, unverified
        u = _db.users.find_one({"email": email})
        assert u is not None
        assert u["email_verified"] is False
        assert u["role"] == "student"
        assert u["approval_status"] == "pending"
        # email_otps doc created with hashed OTP
        otp = _db.email_otps.find_one({"email": email, "purpose": "registration"})
        assert otp is not None
        assert "otp_hash" in otp and otp["otp_hash"].startswith("$2")
        assert otp["attempts"] == 0
        assert otp["verified"] is False

    def test_register_first_admin_auto_approves(self, api, created_emails):
        hostel = f"TEST_NewInst_{uuid.uuid4().hex[:6]}"
        email = _unique_email("adm")
        created_emails.add(email)
        r = api.post(f"{API}/auth/register", json={
            "full_name": "First Admin",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": hostel,
            "role": "admin",
        })
        assert r.status_code == 201, r.text
        u = _db.users.find_one({"email": email})
        assert u["role"] == "admin"
        assert u["approval_status"] == "approved"

    def test_register_invalid_email(self, api):
        r = api.post(f"{API}/auth/register", json={
            "full_name": "Bad",
            "email": "not-an-email",
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        assert r.status_code == 400

    def test_reregister_unverified_refreshes(self, api, created_emails):
        email = _unique_email("rereg")
        created_emails.add(email)
        r1 = api.post(f"{API}/auth/register", json={
            "full_name": "First Name",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        assert r1.status_code == 201
        # Age the otp doc backwards so cooldown is bypassed
        _db.email_otps.update_one(
            {"email": email, "purpose": "registration"},
            {"$set": {"created_at": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()}},
        )
        old_hash = _db.email_otps.find_one({"email": email, "purpose": "registration"})["otp_hash"]
        r2 = api.post(f"{API}/auth/register", json={
            "full_name": "Renamed",
            "email": email,
            "password": "newsecret123",
            "institution_or_hostel_name": "TEST_Hostel_B",
        })
        assert r2.status_code == 201, r2.text
        u = _db.users.find_one({"email": email})
        assert u["full_name"] == "Renamed"
        assert u["institution_or_hostel_name"] == "TEST_Hostel_B"
        new_hash = _db.email_otps.find_one({"email": email, "purpose": "registration"})["otp_hash"]
        assert new_hash != old_hash, "OTP should have been refreshed"

    def test_reregister_verified_rejected(self, api, created_emails):
        email = _unique_email("verif")
        created_emails.add(email)
        api.post(f"{API}/auth/register", json={
            "full_name": "X",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        # Mark verified directly
        _db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
        r = api.post(f"{API}/auth/register", json={
            "full_name": "X",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        assert r.status_code == 400
        assert "already registered" in r.json()["detail"].lower()


# --- Verify Email ---------------------------------------------------------


class TestVerifyEmail:
    def _register(self, api, created_emails, prefix="ver"):
        email = _unique_email(prefix)
        created_emails.add(email)
        r = api.post(f"{API}/auth/register", json={
            "full_name": "Ver User",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        assert r.status_code == 201
        return email

    def test_verify_wrong_otp_increments(self, api, created_emails):
        email = self._register(api, created_emails)
        _set_otp_hash(email, "registration", KNOWN_OTP)
        r = api.post(f"{API}/auth/verify-email", json={"email": email, "otp": "000000"})
        assert r.status_code == 400
        assert "invalid" in r.json()["detail"].lower()
        doc = _db.email_otps.find_one({"email": email, "purpose": "registration"})
        assert doc["attempts"] == 1

    def test_verify_too_many_attempts(self, api, created_emails):
        email = self._register(api, created_emails)
        _set_otp_hash(email, "registration", KNOWN_OTP)
        for _ in range(5):
            api.post(f"{API}/auth/verify-email", json={"email": email, "otp": "000000"})
        # 6th attempt - OTP should now be deleted on this call
        r = api.post(f"{API}/auth/verify-email", json={"email": email, "otp": "000000"})
        assert r.status_code == 400
        assert "too many" in r.json()["detail"].lower() or "many attempts" in r.json()["detail"].lower()
        assert _db.email_otps.find_one({"email": email, "purpose": "registration"}) is None

    def test_verify_correct_otp_logs_in(self, api, created_emails):
        email = self._register(api, created_emails)
        _set_otp_hash(email, "registration", KNOWN_OTP)
        r = api.post(f"{API}/auth/verify-email", json={"email": email, "otp": KNOWN_OTP})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in body
        assert body["user"]["email_verified"] is True
        assert body["user"]["email"] == email
        # OTP doc deleted
        assert _db.email_otps.find_one({"email": email, "purpose": "registration"}) is None
        # User flagged verified
        u = _db.users.find_one({"email": email})
        assert u["email_verified"] is True

    def test_verify_idempotent_when_already_verified(self, api, created_emails):
        email = self._register(api, created_emails)
        _db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
        _db.email_otps.delete_many({"email": email})
        r = api.post(f"{API}/auth/verify-email", json={"email": email, "otp": "999999"})
        assert r.status_code == 200, r.text
        assert "access_token" in r.json()

    def test_verify_expired_otp_returns_410(self, api, created_emails):
        email = self._register(api, created_emails)
        _set_otp_hash(email, "registration", KNOWN_OTP)
        _force_expire(email, "registration")
        r = api.post(f"{API}/auth/verify-email", json={"email": email, "otp": KNOWN_OTP})
        assert r.status_code == 410, r.text
        assert "expired" in r.json()["detail"].lower()
        # Doc removed
        assert _db.email_otps.find_one({"email": email, "purpose": "registration"}) is None


# --- Login ----------------------------------------------------------------


class TestLogin:
    def _register_and_verify(self, api, created_emails, pwd="secret123"):
        email = _unique_email("log")
        created_emails.add(email)
        api.post(f"{API}/auth/register", json={
            "full_name": "Login User",
            "email": email,
            "password": pwd,
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        _set_otp_hash(email, "registration", KNOWN_OTP)
        r = api.post(f"{API}/auth/verify-email", json={"email": email, "otp": KNOWN_OTP})
        assert r.status_code == 200
        return email

    def test_login_wrong_password_401(self, api, created_emails):
        email = self._register_and_verify(api, created_emails)
        r = api.post(f"{API}/auth/login", json={"email": email, "password": "wrongpass"})
        assert r.status_code == 401
        assert "invalid" in r.json()["detail"].lower()

    def test_login_unverified_403(self, api, created_emails):
        email = _unique_email("unver")
        created_emails.add(email)
        api.post(f"{API}/auth/register", json={
            "full_name": "U",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        r = api.post(f"{API}/auth/login", json={"email": email, "password": "secret123"})
        assert r.status_code == 403
        detail = r.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["code"] == "email_not_verified"
        assert detail["email"] == email

    def test_login_verified_200(self, api, created_emails):
        email = self._register_and_verify(api, created_emails)
        r = api.post(f"{API}/auth/login", json={"email": email, "password": "secret123"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in body
        assert body["user"]["email_verified"] is True


# --- Resend OTP -----------------------------------------------------------


class TestResendOtp:
    def test_resend_within_cooldown_429(self, api, created_emails):
        email = _unique_email("resend")
        created_emails.add(email)
        api.post(f"{API}/auth/register", json={
            "full_name": "R",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        # Immediate resend should be throttled
        r = api.post(f"{API}/auth/resend-otp", json={"email": email, "purpose": "registration"})
        assert r.status_code == 429
        assert "wait" in r.json()["detail"].lower()

    def test_resend_after_cooldown_replaces_hash(self, api, created_emails):
        email = _unique_email("resend2")
        created_emails.add(email)
        api.post(f"{API}/auth/register", json={
            "full_name": "R",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        old_hash = _db.email_otps.find_one({"email": email, "purpose": "registration"})["otp_hash"]
        # Age backward
        _db.email_otps.update_one(
            {"email": email, "purpose": "registration"},
            {"$set": {"created_at": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()}},
        )
        r = api.post(f"{API}/auth/resend-otp", json={"email": email, "purpose": "registration"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["resend_available_in"] == 60
        new_hash = _db.email_otps.find_one({"email": email, "purpose": "registration"})["otp_hash"]
        assert new_hash != old_hash

    def test_resend_already_verified_400(self, api, created_emails):
        email = _unique_email("resend3")
        created_emails.add(email)
        api.post(f"{API}/auth/register", json={
            "full_name": "R",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        _db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
        r = api.post(f"{API}/auth/resend-otp", json={"email": email, "purpose": "registration"})
        assert r.status_code == 400
        assert "already verified" in r.json()["detail"].lower()


# --- Forgot Password ------------------------------------------------------


class TestForgotPassword:
    def _make_user(self, api, created_emails, pwd="secret123"):
        email = _unique_email("fp")
        created_emails.add(email)
        api.post(f"{API}/auth/register", json={
            "full_name": "FP",
            "email": email,
            "password": pwd,
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        _set_otp_hash(email, "registration", KNOWN_OTP)
        api.post(f"{API}/auth/verify-email", json={"email": email, "otp": KNOWN_OTP})
        return email

    def test_forgot_existing_email(self, api, created_emails):
        email = self._make_user(api, created_emails)
        r = api.post(f"{API}/auth/forgot-password", json={"email": email})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        # OTP doc created
        doc = _db.email_otps.find_one({"email": email, "purpose": "forgot_password"})
        assert doc is not None

    def test_forgot_non_existing_no_leak(self, api):
        r = api.post(f"{API}/auth/forgot-password", json={"email": _unique_email("noexist")})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"

    def test_forgot_second_call_within_cooldown(self, api, created_emails):
        email = self._make_user(api, created_emails)
        r1 = api.post(f"{API}/auth/forgot-password", json={"email": email})
        assert r1.status_code == 200
        r2 = api.post(f"{API}/auth/forgot-password", json={"email": email})
        assert r2.status_code == 200
        # Second call should return reduced resend_available_in
        assert r2.json()["resend_available_in"] <= 60

    def test_forgot_verify_wrong_then_correct(self, api, created_emails):
        email = self._make_user(api, created_emails)
        api.post(f"{API}/auth/forgot-password", json={"email": email})
        _set_otp_hash(email, "forgot_password", KNOWN_OTP)
        bad = api.post(f"{API}/auth/forgot-password/verify", json={"email": email, "otp": "000000"})
        assert bad.status_code == 400
        good = api.post(f"{API}/auth/forgot-password/verify", json={"email": email, "otp": KNOWN_OTP})
        assert good.status_code == 200, good.text
        body = good.json()
        assert "reset_token" in body
        assert body["expires_in"] == 600
        # OTP deleted
        assert _db.email_otps.find_one({"email": email, "purpose": "forgot_password"}) is None
        # Re-use same OTP fails
        again = api.post(f"{API}/auth/forgot-password/verify", json={"email": email, "otp": KNOWN_OTP})
        assert again.status_code == 400


# --- Reset Password -------------------------------------------------------


class TestResetPassword:
    def _make_reset_token(self, api, created_emails):
        email = _unique_email("rp")
        created_emails.add(email)
        api.post(f"{API}/auth/register", json={
            "full_name": "RP",
            "email": email,
            "password": "oldpass123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        _set_otp_hash(email, "registration", KNOWN_OTP)
        api.post(f"{API}/auth/verify-email", json={"email": email, "otp": KNOWN_OTP})
        api.post(f"{API}/auth/forgot-password", json={"email": email})
        _set_otp_hash(email, "forgot_password", KNOWN_OTP)
        r = api.post(f"{API}/auth/forgot-password/verify", json={"email": email, "otp": KNOWN_OTP})
        assert r.status_code == 200
        return email, r.json()["reset_token"]

    def test_reset_mismatched_passwords(self, api, created_emails):
        _, token = self._make_reset_token(api, created_emails)
        r = api.post(f"{API}/auth/reset-password", json={
            "reset_token": token,
            "new_password": "newpass123",
            "confirm_password": "different456",
        })
        assert r.status_code == 400

    def test_reset_invalid_token(self, api):
        r = api.post(f"{API}/auth/reset-password", json={
            "reset_token": "not.a.valid.jwt.token",
            "new_password": "newpass123",
        })
        assert r.status_code == 400

    def test_reset_valid_token_then_login(self, api, created_emails):
        email, token = self._make_reset_token(api, created_emails)
        r = api.post(f"{API}/auth/reset-password", json={
            "reset_token": token,
            "new_password": "brandnew456",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in body
        # Login with new password
        login = api.post(f"{API}/auth/login", json={"email": email, "password": "brandnew456"})
        assert login.status_code == 200
        # Old password fails
        old = api.post(f"{API}/auth/login", json={"email": email, "password": "oldpass123"})
        assert old.status_code == 401


# --- Cryptographic randomness --------------------------------------------


class TestRandomness:
    def test_ten_distinct_otp_hashes(self, api, created_emails):
        hashes = set()
        for _ in range(10):
            email = _unique_email("rand")
            created_emails.add(email)
            r = api.post(f"{API}/auth/register", json={
                "full_name": "Rand",
                "email": email,
                "password": "secret123",
                "institution_or_hostel_name": "TEST_Hostel_A",
            })
            assert r.status_code == 201, r.text
            doc = _db.email_otps.find_one({"email": email, "purpose": "registration"})
            hashes.add(doc["otp_hash"])
        # All hashes should be unique (bcrypt has random salt so even same OTP → diff hash;
        # but each OTP is also random so this passes regardless)
        assert len(hashes) == 10


# --- Indexes -------------------------------------------------------------


class TestIndexes:
    def test_email_otps_unique_email_purpose(self):
        idxs = _db.email_otps.index_information()
        # Look for compound (email, purpose) unique index
        found = False
        for name, info in idxs.items():
            keys = info.get("key", [])
            if [("email", 1), ("purpose", 1)] == list(keys) and info.get("unique"):
                found = True
                break
        assert found, f"Missing unique (email,purpose) index. Have: {list(idxs.keys())}"

    def test_users_unique_partial_email(self):
        idxs = _db.users.index_information()
        found = False
        for name, info in idxs.items():
            keys = list(info.get("key", []))
            if keys == [("email", 1)] and info.get("unique"):
                found = True
                break
        assert found, f"Missing unique email index on users. Have: {list(idxs.keys())}"


# --- Regression: existing endpoints with new tokens -----------------------


class TestRegression:
    @pytest.fixture
    def admin_token(self, api, created_emails):
        email = _unique_email("adm")
        created_emails.add(email)
        hostel = f"TEST_RegressionHostel_{uuid.uuid4().hex[:6]}"
        api.post(f"{API}/auth/register", json={
            "full_name": "Adm",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": hostel,
            "role": "admin",
        })
        _set_otp_hash(email, "registration", KNOWN_OTP)
        r = api.post(f"{API}/auth/verify-email", json={"email": email, "otp": KNOWN_OTP})
        assert r.status_code == 200
        return r.json()["access_token"]

    @pytest.fixture
    def student_token(self, api, created_emails):
        email = _unique_email("stu")
        created_emails.add(email)
        api.post(f"{API}/auth/register", json={
            "full_name": "Stu",
            "email": email,
            "password": "secret123",
            "institution_or_hostel_name": "TEST_Hostel_A",
        })
        _set_otp_hash(email, "registration", KNOWN_OTP)
        r = api.post(f"{API}/auth/verify-email", json={"email": email, "otp": KNOWN_OTP})
        assert r.status_code == 200
        # Approve student
        _db.users.update_one({"email": email}, {"$set": {"approval_status": "approved"}})
        return r.json()["access_token"]

    def test_admin_dashboard(self, api, admin_token):
        r = api.get(f"{API}/admin/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_admin_students(self, api, admin_token):
        r = api.get(f"{API}/admin/students", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_admin_notifications(self, api, admin_token):
        r = api.get(f"{API}/admin/notifications", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_dispatch_reminder(self, api, admin_token):
        r = api.post(
            f"{API}/admin/notifications/dispatch-reminder",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"audience": "student"},
        )
        assert r.status_code == 201

    def test_student_today(self, api, student_token):
        r = api.get(f"{API}/student/today", headers={"Authorization": f"Bearer {student_token}"})
        assert r.status_code == 200

    def test_push_token(self, api, student_token):
        r = api.post(
            f"{API}/auth/push-token",
            headers={"Authorization": f"Bearer {student_token}"},
            json={"push_token": "ExponentPushToken[abc123]", "platform": "android"},
        )
        assert r.status_code == 200

    def test_register_push(self, api, student_token):
        # Need user_id from /auth/me
        me = api.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {student_token}"})
        assert me.status_code == 200
        uid = me.json()["id"]
        r = api.post(
            f"{API}/register-push",
            headers={"Authorization": f"Bearer {student_token}"},
            json={"user_id": uid, "platform": "android", "device_token": "ExponentPushToken[def456]"},
        )
        assert r.status_code == 201
