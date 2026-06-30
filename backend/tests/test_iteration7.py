"""Iteration 7 backend tests — empty DB, MSG91 dev OTP, Push relay, dispatch-reminder.

Covers all items from the iteration 7 review request:
  - Empty DB invariants (no seed/demo data)
  - register-student → pending
  - login (dev mode) → {challenge, delivery=dev, dev_otp=123456, masked_mobile, user_preview}
  - verify-login-otp success / wrong OTP 400 / reuse 400 / 5-attempt lockout 429
  - resend-otp issues fresh OTP and resets attempts
  - /auth/push-token persists to users.push_token AND upserts push_tokens
  - /api/register-push relays gracefully (placeholder key → still 201)
  - /admin/notifications create + push (non-blocking)
  - /admin/notifications/dispatch-reminder student/admin defaults + recipients count
  - /admin/notifications/menu-reminder still works
  - Existing endpoints (/admin/dashboard, /admin/students, /admin/wastage/today,
    /student/today, /student/menu/week, /student/notifications) still 200
  - Indexes for otp_attempts + push_tokens created on startup
"""

import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

# Direct mongo handle for state assertions + admin promotion (no admin signup API).
_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME = os.environ.get("DB_NAME", "messmate")
_mongo = MongoClient(_MONGO_URL)
_db = _mongo[_DB_NAME]

HOSTEL = f"TEST_Hostel_{uuid.uuid4().hex[:6]}"
STUDENT_MOBILE = "9" + uuid.uuid4().hex[:9]  # 10-digit-ish
ADMIN_USERID = f"TEST_admin_{uuid.uuid4().hex[:6]}"
PASSWORD = "Passw0rd!"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


def _register_student(s, mobile, hostel=HOSTEL, name="TEST_Student"):
    r = s.post(f"{API}/auth/register-student", json={
        "full_name": name,
        "mobile_or_user_id": mobile,
        "institution_or_hostel_name": hostel,
        "room_number": "101",
        "password": PASSWORD,
    })
    return r


def _approve_in_db(mobile, hostel=HOSTEL):
    _db.users.update_one(
        {"mobile_or_user_id": mobile, "institution_or_hostel_name": hostel},
        {"$set": {"approval_status": "approved"}},
    )


def _promote_admin_in_db(userid, hostel=HOSTEL):
    _db.users.update_one(
        {"mobile_or_user_id": userid, "institution_or_hostel_name": hostel},
        {"$set": {"role": "admin", "approval_status": "approved"}},
    )


def _login(s, mobile, password=PASSWORD, hostel=HOSTEL):
    """Step1+Step2 in dev mode → returns (token, user_dict)."""
    r1 = s.post(f"{API}/auth/login", json={
        "mobile_or_user_id": mobile,
        "password": password,
        "institution_or_hostel_name": hostel,
    })
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["delivery"] == "dev"
    assert body["dev_otp"] == "123456"
    r2 = s.post(f"{API}/auth/verify-login-otp",
                json={"challenge": body["challenge"], "otp": body["dev_otp"]})
    assert r2.status_code == 200, r2.text
    return r2.json()["access_token"], r2.json()["user"]


def _auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# 1. DB is initially empty (no seed/demo data created on startup)
# ---------------------------------------------------------------------------
def test_db_has_no_seed_demo_accounts():
    """No preset 'Demo Hostel' users/menus/necessary_info/wastage_records exist."""
    # Demo content must not exist
    assert _db.users.count_documents({"institution_or_hostel_name": "Demo Hostel"}) == 0
    assert _db.menus.count_documents({"hostel": "Demo Hostel"}) == 0
    assert _db.necessary_info.count_documents({"hostel": "Demo Hostel"}) == 0
    assert _db.wastage_records.count_documents({"hostel": "Demo Hostel"}) == 0


def test_startup_indexes_present_for_new_collections():
    """otp_attempts and push_tokens get their indexes at startup."""
    otp_idx = list(_db.otp_attempts.index_information().keys())
    push_idx = list(_db.push_tokens.index_information().keys())
    assert "id_1" in otp_idx
    assert "expires_at_1" in otp_idx
    assert "user_id_1_device_token_1" in push_idx
    assert "hostel_1_role_1" in push_idx


# ---------------------------------------------------------------------------
# 2. Register student → pending
# ---------------------------------------------------------------------------
class TestRegister:
    def test_register_student_pending(self, s):
        r = _register_student(s, STUDENT_MOBILE)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["role"] == "student"
        assert body["approval_status"] == "pending"
        assert body["mobile_or_user_id"] == STUDENT_MOBILE
        # GET-verify persistence via mongo
        doc = _db.users.find_one({"mobile_or_user_id": STUDENT_MOBILE,
                                   "institution_or_hostel_name": HOSTEL})
        assert doc is not None
        assert doc["approval_status"] == "pending"

    def test_register_duplicate_400(self, s):
        r = _register_student(s, STUDENT_MOBILE)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# 3. Login (dev mode) — challenge + dev_otp + masked_mobile + user_preview
# ---------------------------------------------------------------------------
class TestLoginDev:
    def test_login_wrong_password_401(self, s):
        r = s.post(f"{API}/auth/login", json={
            "mobile_or_user_id": STUDENT_MOBILE,
            "password": "wrongPass",
            "institution_or_hostel_name": HOSTEL,
        })
        assert r.status_code == 401

    def test_login_dev_returns_challenge_and_dev_otp(self, s):
        # student is currently pending, but login still issues challenge
        r = s.post(f"{API}/auth/login", json={
            "mobile_or_user_id": STUDENT_MOBILE,
            "password": PASSWORD,
            "institution_or_hostel_name": HOSTEL,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["delivery"] == "dev"
        assert body["dev_otp"] == "123456"
        assert "challenge" in body and isinstance(body["challenge"], str)
        assert "user_preview" in body
        up = body["user_preview"]
        assert up["full_name"] == "TEST_Student"
        assert up["mobile_or_user_id"] == STUDENT_MOBILE
        assert up["institution_or_hostel_name"] == HOSTEL
        assert "masked_mobile" in body and isinstance(body["masked_mobile"], str)


# ---------------------------------------------------------------------------
# 4. verify-login-otp: success / wrong / reuse / brute-force
# ---------------------------------------------------------------------------
class TestVerifyOtp:
    def _fresh_challenge(self, s, mobile=STUDENT_MOBILE):
        r = s.post(f"{API}/auth/login", json={
            "mobile_or_user_id": mobile,
            "password": PASSWORD,
            "institution_or_hostel_name": HOSTEL,
        })
        assert r.status_code == 200
        return r.json()["challenge"]

    def test_wrong_otp_400(self, s):
        ch = self._fresh_challenge(s)
        r = s.post(f"{API}/auth/verify-login-otp", json={"challenge": ch, "otp": "999999"})
        assert r.status_code == 400
        assert "Invalid OTP" in r.text

    def test_correct_otp_returns_token(self, s):
        ch = self._fresh_challenge(s)
        r = s.post(f"{API}/auth/verify-login-otp", json={"challenge": ch, "otp": "123456"})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body and body["user"]["mobile_or_user_id"] == STUDENT_MOBILE

    def test_reuse_consumed_otp_returns_400(self, s):
        ch = self._fresh_challenge(s)
        r1 = s.post(f"{API}/auth/verify-login-otp", json={"challenge": ch, "otp": "123456"})
        assert r1.status_code == 200
        r2 = s.post(f"{API}/auth/verify-login-otp", json={"challenge": ch, "otp": "123456"})
        assert r2.status_code == 400
        assert "already used" in r2.text.lower()

    def test_brute_force_lockout_429_after_5_attempts(self, s):
        ch = self._fresh_challenge(s)
        # 5 wrong attempts
        statuses = []
        for _ in range(5):
            r = s.post(f"{API}/auth/verify-login-otp", json={"challenge": ch, "otp": "000000"})
            statuses.append(r.status_code)
        # First 5 should be 400 (incrementing attempts each time)
        assert all(c == 400 for c in statuses), statuses
        # 6th attempt: attempts>=5 → 429
        r6 = s.post(f"{API}/auth/verify-login-otp", json={"challenge": ch, "otp": "000000"})
        assert r6.status_code == 429, r6.text


# ---------------------------------------------------------------------------
# 5. resend-otp — new OTP + reset attempts (dev mode returns dev_otp)
# ---------------------------------------------------------------------------
class TestResendOtp:
    def test_resend_resets_attempts(self, s):
        # Get a challenge and burn 1 wrong attempt
        r = s.post(f"{API}/auth/login", json={
            "mobile_or_user_id": STUDENT_MOBILE,
            "password": PASSWORD,
            "institution_or_hostel_name": HOSTEL,
        })
        ch = r.json()["challenge"]
        s.post(f"{API}/auth/verify-login-otp", json={"challenge": ch, "otp": "111111"})
        # Resend
        rr = s.post(f"{API}/auth/resend-otp", json={"challenge": ch})
        assert rr.status_code == 200, rr.text
        body = rr.json()
        assert body["delivery"] == "dev"
        assert body["dev_otp"] == "123456"
        # Verify with new OTP works (attempts reset)
        rv = s.post(f"{API}/auth/verify-login-otp", json={"challenge": ch, "otp": "123456"})
        assert rv.status_code == 200


# ---------------------------------------------------------------------------
# 6. push-token + register-push
# ---------------------------------------------------------------------------
class TestPushTokens:
    @pytest.fixture(scope="class")
    def student_token(self, s):
        # ensure approved
        _approve_in_db(STUDENT_MOBILE)
        tok, user = _login(s, STUDENT_MOBILE)
        return tok, user

    def test_push_token_persists_in_users_and_push_tokens(self, s, student_token):
        token, user = student_token
        push = f"ExponentPushToken[{uuid.uuid4().hex}]"
        r = s.post(f"{API}/auth/push-token",
                   json={"push_token": push, "platform": "android"},
                   headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}
        u = _db.users.find_one({"id": user["id"]})
        assert u["push_token"] == push
        pt = _db.push_tokens.find_one({"user_id": user["id"], "device_token": push})
        assert pt is not None and pt["platform"] == "android"

    def test_register_push_relay_returns_201_even_with_placeholder_key(self, s, student_token):
        token, user = student_token
        push = f"ExponentPushToken[{uuid.uuid4().hex}]"
        r = s.post(f"{API}/register-push", json={
            "user_id": user["id"], "platform": "ios", "device_token": push,
        }, headers=_auth(token))
        # Must NOT 5xx with placeholder key — gracefully returns 201
        assert r.status_code == 201, r.text
        assert r.json() == {"status": "registered"}
        pt = _db.push_tokens.find_one({"user_id": user["id"], "device_token": push})
        assert pt is not None and pt["platform"] == "ios"

    def test_register_push_user_id_mismatch_403(self, s, student_token):
        token, _user = student_token
        r = s.post(f"{API}/register-push", json={
            "user_id": "someone-else", "platform": "android", "device_token": "tok123",
        }, headers=_auth(token))
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 7. Admin notifications: create + dispatch-reminder + menu-reminder
# ---------------------------------------------------------------------------
class TestAdminNotifications:
    @pytest.fixture(scope="class")
    def admin_token(self, s):
        # Register admin-as-student then promote in DB (no signup API for admin)
        _register_student(s, ADMIN_USERID, name="TEST_Admin")
        _promote_admin_in_db(ADMIN_USERID)
        tok, user = _login(s, ADMIN_USERID)
        assert user["role"] == "admin"
        return tok, user

    @pytest.fixture(scope="class")
    def student_token(self, s):
        _approve_in_db(STUDENT_MOBILE)
        tok, user = _login(s, STUDENT_MOBILE)
        return tok, user

    def test_create_announcement_does_not_block_on_push(self, s, admin_token):
        token, _ = admin_token
        r = s.post(f"{API}/admin/notifications", json={
            "title": "TEST_announcement", "body": "hello", "audience": "all",
        }, headers=_auth(token))
        assert r.status_code == 201, r.text
        assert r.json()["title"] == "TEST_announcement"

    def test_dispatch_reminder_student_default_text(self, s, admin_token, student_token):
        token, _ = admin_token
        r = s.post(f"{API}/admin/notifications/dispatch-reminder", json={
            "audience": "student",
        }, headers=_auth(token))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["audience"] == "student"
        assert body["recipients"] >= 1  # approved student exists
        assert body["notification"]["title"] == "Submit your meal preferences"

    def test_dispatch_reminder_admin_default_text(self, s, admin_token):
        token, _ = admin_token
        r = s.post(f"{API}/admin/notifications/dispatch-reminder", json={
            "audience": "admin",
        }, headers=_auth(token))
        assert r.status_code == 201
        body = r.json()
        assert body["notification"]["title"] == "Review today's plan"
        assert body["recipients"] >= 1  # the admin itself

    def test_menu_reminder_requires_tomorrow_menu_then_works(self, s, admin_token):
        token, admin = admin_token
        # Insert a menu for tomorrow's weekday so menu-reminder succeeds
        import datetime as dt
        DAYS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        tomorrow = dt.date.today() + dt.timedelta(days=1)
        day = DAYS[tomorrow.weekday()]
        _db.menus.update_one(
            {"hostel": HOSTEL, "day": day},
            {"$set": {
                "hostel": HOSTEL, "day": day,
                "breakfast_items": ["Idli"], "lunch_items": ["Rice"], "dinner_items": ["Chapati"],
                "breakfast_custom_question": None, "lunch_custom_question": None,
                "dinner_custom_question": None,
                "updated_at": "now",
            }, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": "now"}},
            upsert=True,
        )
        r = s.post(f"{API}/admin/notifications/menu-reminder", json={},
                   headers=_auth(token))
        assert r.status_code == 201, r.text
        assert r.json()["type"] == "menu_reminder"


# ---------------------------------------------------------------------------
# 8. Regression — existing endpoints still 200 after refactor
# ---------------------------------------------------------------------------
class TestRegression:
    @pytest.fixture(scope="class")
    def tokens(self, s):
        _approve_in_db(STUDENT_MOBILE)
        _register_student(s, ADMIN_USERID, name="TEST_Admin")
        _promote_admin_in_db(ADMIN_USERID)
        stu_tok, _ = _login(s, STUDENT_MOBILE)
        adm_tok, _ = _login(s, ADMIN_USERID)
        return stu_tok, adm_tok

    def test_admin_dashboard(self, s, tokens):
        _, adm = tokens
        r = s.get(f"{API}/admin/dashboard", headers=_auth(adm))
        assert r.status_code == 200
        assert "meals" in r.json() and "summary" in r.json()

    def test_admin_students(self, s, tokens):
        _, adm = tokens
        r = s.get(f"{API}/admin/students", headers=_auth(adm))
        assert r.status_code == 200
        assert "students" in r.json()

    def test_admin_wastage_today(self, s, tokens):
        _, adm = tokens
        r = s.get(f"{API}/admin/wastage/today", headers=_auth(adm))
        assert r.status_code == 200
        assert "date" in r.json()

    def test_student_today(self, s, tokens):
        stu, _ = tokens
        r = s.get(f"{API}/student/today", headers=_auth(stu))
        assert r.status_code == 200
        assert "date" in r.json()

    def test_student_menu_week(self, s, tokens):
        stu, _ = tokens
        r = s.get(f"{API}/student/menu/week", headers=_auth(stu))
        assert r.status_code == 200
        assert "days" in r.json() and len(r.json()["days"]) == 7

    def test_student_notifications(self, s, tokens):
        stu, _ = tokens
        r = s.get(f"{API}/student/notifications", headers=_auth(stu))
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and "unread_count" in body
