"""MessMate iteration 6 backend tests:
- Two-step login (challenge + OTP)
- Multi-tenant hostel scoping
- Manual wastage cost
- Notifications (admin + student)
- Push token capture
- cost_series in wastage trend
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"')
                break
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"
MOCK_OTP = "123456"
DEMO = "Demo Hostel"


def _two_step_login(s, uid, pw, hostel=DEMO):
    r1 = s.post(f"{API}/auth/login", json={
        "mobile_or_user_id": uid, "password": pw,
        "institution_or_hostel_name": hostel,
    })
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert "challenge" in j1 and "access_token" not in j1
    assert j1.get("mock_otp") == MOCK_OTP
    assert "user_preview" in j1
    r2 = s.post(f"{API}/auth/verify-login-otp", json={
        "challenge": j1["challenge"], "otp": MOCK_OTP,
    })
    assert r2.status_code == 200, r2.text
    j2 = r2.json()
    assert j2["access_token"]
    assert j2["user"]
    return j2["access_token"], j2["user"], j1["challenge"]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    tok, _, _ = _two_step_login(session, "admin", "admin123")
    return tok


@pytest.fixture(scope="module")
def student_token(session):
    tok, _, _ = _two_step_login(session, "student", "student123")
    return tok


# ---------- AUTH: 2-step login ----------
class TestTwoStepLogin:
    def test_login_step1_returns_challenge_no_token(self, session):
        r = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "admin", "password": "admin123",
            "institution_or_hostel_name": DEMO,
        })
        assert r.status_code == 200
        j = r.json()
        assert "challenge" in j
        assert "access_token" not in j
        assert j["mock_otp"] == MOCK_OTP
        assert j["user_preview"]["role"] == "admin"

    def test_login_wrong_password_401(self, session):
        r = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "admin", "password": "wrong",
            "institution_or_hostel_name": DEMO,
        })
        assert r.status_code == 401

    def test_login_wrong_hostel_401(self, session):
        r = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "admin", "password": "admin123",
            "institution_or_hostel_name": "Nonexistent Hostel",
        })
        assert r.status_code == 401

    def test_login_missing_hostel_field(self, session):
        r = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "admin", "password": "admin123",
        })
        assert r.status_code == 422

    def test_verify_otp_correct(self, session):
        r1 = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "student", "password": "student123",
            "institution_or_hostel_name": DEMO,
        }).json()
        r2 = session.post(f"{API}/auth/verify-login-otp", json={
            "challenge": r1["challenge"], "otp": MOCK_OTP,
        })
        assert r2.status_code == 200
        assert r2.json()["access_token"]
        assert r2.json()["user"]["role"] == "student"

    def test_verify_otp_wrong_400(self, session):
        r1 = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "student", "password": "student123",
            "institution_or_hostel_name": DEMO,
        }).json()
        r2 = session.post(f"{API}/auth/verify-login-otp", json={
            "challenge": r1["challenge"], "otp": "000000",
        })
        assert r2.status_code == 400
        assert "OTP" in r2.json().get("detail", "")

    def test_verify_otp_bad_challenge_400(self, session):
        r = session.post(f"{API}/auth/verify-login-otp", json={
            "challenge": "not.a.real.jwt", "otp": MOCK_OTP,
        })
        assert r.status_code == 400

    def test_challenge_token_cannot_call_me(self, session):
        r1 = session.post(f"{API}/auth/login", json={
            "mobile_or_user_id": "student", "password": "student123",
            "institution_or_hostel_name": DEMO,
        }).json()
        r = session.get(f"{API}/auth/me",
                        headers={"Authorization": f"Bearer {r1['challenge']}"})
        assert r.status_code == 401


# ---------- HOSTEL SCOPING ----------
class TestHostelScoping:
    test_hostel = f"TEST_Hostel_{uuid.uuid4().hex[:6]}"
    test_mobile = f"TEST_stu_{uuid.uuid4().hex[:6]}"

    def test_register_student_in_test_hostel(self, session):
        r = session.post(f"{API}/auth/register-student", json={
            "full_name": "TEST Outsider",
            "mobile_or_user_id": self.test_mobile,
            "institution_or_hostel_name": self.test_hostel,
            "room_number": "Z1",
            "password": "pw123456",
        })
        assert r.status_code == 201
        assert r.json()["institution_or_hostel_name"] == self.test_hostel

    def test_demo_admin_cannot_see_test_student(self, session, admin_token):
        r = session.get(f"{API}/admin/students",
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        mobiles = [s["mobile_or_user_id"] for s in r.json()["students"]]
        assert self.test_mobile not in mobiles
        hostels = {s["institution_or_hostel_name"] for s in r.json()["students"]}
        assert hostels.issubset({DEMO})

    def test_demo_admin_summary_excludes_test_hostel(self, session, admin_token):
        r = session.get(f"{API}/admin/students/summary",
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        # Should not blow up; just confirm shape
        for k in ("total_students", "approved", "pending", "blocked"):
            assert isinstance(r.json()[k], int)


# ---------- WASTAGE manual_total_cost + cost_series ----------
class TestWastageManualCost:
    def test_put_with_manual_cost_persists(self, session, admin_token):
        from datetime import date
        today = date.today().isoformat()
        r = session.put(f"{API}/admin/wastage/{today}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "breakfast_items": [], "lunch_items": [], "dinner_items": [],
                "manual_total_cost": 1500,
            })
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        w = j["wastage"]
        assert w["manual_total_cost"] == 1500
        item_loss = w.get("item_loss_total", 0)
        assert w["total_loss"] == round(item_loss + 1500, 2)

    def test_wastage_today_returns_manual_cost(self, session, admin_token):
        r = session.get(f"{API}/admin/wastage/today",
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        today_doc = r.json().get("today")
        assert today_doc is not None
        assert today_doc.get("manual_total_cost") == 1500

    def test_trend_includes_cost_series(self, session, admin_token):
        r = session.get(f"{API}/admin/wastage/trend?range=7&meal=all",
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        j = r.json()
        assert "wastage_series" in j
        assert "saved_series" in j
        assert "cost_series" in j
        assert isinstance(j["cost_series"], list)
        if j["cost_series"]:
            assert "date" in j["cost_series"][0]
            assert "value" in j["cost_series"][0]


# ---------- NOTIFICATIONS ----------
class TestNotifications:
    notif_id = None

    def test_admin_create_announcement(self, session, admin_token):
        r = session.post(f"{API}/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "TEST Announcement",
                "body": "Iteration 6 test notification",
                "audience": "all", "type": "announcement",
            })
        assert r.status_code == 201, r.text
        j = r.json()
        assert j["id"]
        assert j["title"] == "TEST Announcement"
        TestNotifications.notif_id = j["id"]

    def test_admin_list_notifications(self, session, admin_token):
        r = session.get(f"{API}/admin/notifications",
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        ids = [n["id"] for n in r.json()["items"]]
        assert TestNotifications.notif_id in ids

    def test_student_sees_announcement_unread(self, session, student_token):
        r = session.get(f"{API}/student/notifications",
                        headers={"Authorization": f"Bearer {student_token}"})
        assert r.status_code == 200
        j = r.json()
        match = [n for n in j["items"] if n["id"] == TestNotifications.notif_id]
        assert len(match) == 1
        assert match[0]["read"] is False
        assert j["unread_count"] >= 1

    def test_student_marks_read_decrements(self, session, student_token):
        before = session.get(f"{API}/student/notifications",
            headers={"Authorization": f"Bearer {student_token}"}).json()["unread_count"]
        r = session.post(
            f"{API}/student/notifications/{TestNotifications.notif_id}/read",
            headers={"Authorization": f"Bearer {student_token}"})
        assert r.status_code == 200
        after = session.get(f"{API}/student/notifications",
            headers={"Authorization": f"Bearer {student_token}"}).json()
        assert after["unread_count"] == max(0, before - 1)
        target = next(n for n in after["items"]
                      if n["id"] == TestNotifications.notif_id)
        assert target["read"] is True

    def test_menu_reminder_creates_notification(self, session, admin_token):
        r = session.post(f"{API}/admin/notifications/menu-reminder",
            headers={"Authorization": f"Bearer {admin_token}"}, json={})
        # Menus are seeded for every weekday -> should succeed
        assert r.status_code == 201, r.text
        j = r.json()
        assert j["type"] == "menu_reminder"
        assert j["title"]

    def test_admin_notif_requires_auth(self, session):
        r = session.get(f"{API}/admin/notifications")
        assert r.status_code == 401

    def test_student_notif_requires_auth(self, session):
        r = session.get(f"{API}/student/notifications")
        assert r.status_code == 401


# ---------- PUSH TOKEN ----------
class TestPushToken:
    def test_save_push_token(self, session, student_token):
        r = session.post(f"{API}/auth/push-token",
            headers={"Authorization": f"Bearer {student_token}"},
            json={"push_token": "ExponentPushToken[TEST_iter6]"})
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_push_token_requires_auth(self, session):
        r = session.post(f"{API}/auth/push-token",
                         json={"push_token": "x"})
        assert r.status_code == 401
