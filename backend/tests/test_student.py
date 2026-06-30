"""MessMate backend student-side tests (Part 2)."""
import os
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


def _login(s, uid, pwd, inst=None):
    body = {"mobile_or_user_id": uid, "password": pwd}
    if inst:
        body["institution_or_hostel_name"] = inst
    r = s.post(f"{API}/auth/login", json=body)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def student_token(session):
    return _login(session, "student", "student123")


@pytest.fixture(scope="module")
def pending_token(session):
    return _login(session, "pending", "pending123")


@pytest.fixture(scope="module")
def blocked_token(session):
    return _login(session, "blocked", "blocked123")


@pytest.fixture(scope="module")
def admin_token(session):
    return _login(session, "admin", "admin123", "Demo Hostel")


def H(t):
    return {"Authorization": f"Bearer {t}"}


# --- Module: meta + today ---
class TestMetaAndToday:
    def test_meta(self, session, student_token):
        r = session.get(f"{API}/student/meta", headers=H(student_token))
        assert r.status_code == 200
        j = r.json()
        assert len(j["reasons"]) == 7
        assert "Going home" in j["reasons"]
        assert "Other" in j["reasons"]
        assert j["days"] == ["monday", "tuesday", "wednesday", "thursday",
                             "friday", "saturday", "sunday"]

    def test_today_returns_shape(self, session, student_token):
        r = session.get(f"{API}/student/today", headers=H(student_token))
        assert r.status_code == 200
        j = r.json()
        assert "date" in j and "day" in j
        assert j["day"] in ["monday", "tuesday", "wednesday", "thursday",
                            "friday", "saturday", "sunday"]
        assert j["menu"] is not None
        # menu has items lists
        assert isinstance(j["menu"]["breakfast_items"], list)
        assert isinstance(j["menu"]["lunch_items"], list)
        assert isinstance(j["menu"]["dinner_items"], list)


# --- Module: upsert today plan (idempotency) ---
class TestUpsertPlan:
    def test_upsert_then_update_same_doc(self, session, student_token):
        body1 = {
            "breakfast": {"status": "ON", "selected_items": ["Idly", "Dosa"],
                          "custom_answer": "Yes"},
            "lunch": {"status": "OFF", "reason_if_off": "Going home"},
            "dinner": {"status": "ON", "selected_items": ["Chapati"]},
        }
        r = session.put(f"{API}/student/today", json=body1, headers=H(student_token))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert j["plan"]["breakfast"]["status"] == "ON"
        assert j["plan"]["breakfast"]["selected_items"] == ["Idly", "Dosa"]
        assert j["plan"]["lunch"]["status"] == "OFF"
        assert j["plan"]["lunch"]["reason_if_off"] == "Going home"

        # 2nd PUT same date with different values - must update, not insert
        body2 = {
            "breakfast": {"status": "OFF", "reason_if_off": "Sick"},
            "lunch": {"status": "ON", "selected_items": ["Rice"]},
            "dinner": {"status": "OFF", "reason_if_off": "Other: Trip"},
        }
        r2 = session.put(f"{API}/student/today", json=body2, headers=H(student_token))
        assert r2.status_code == 200
        j2 = r2.json()
        assert j2["plan"]["breakfast"]["status"] == "OFF"
        assert j2["plan"]["dinner"]["reason_if_off"] == "Other: Trip"

        # Verify via GET /today reflects last write
        r3 = session.get(f"{API}/student/today", headers=H(student_token))
        plan = r3.json()["plan"]
        assert plan is not None
        assert plan["breakfast"]["status"] == "OFF"
        assert plan["lunch"]["selected_items"] == ["Rice"]


# --- Module: feedback ---
class TestFeedback:
    def test_post_feedback(self, session, student_token):
        r = session.post(f"{API}/student/feedback",
                         json={"feedback_text": "TEST_feedback OK"},
                         headers=H(student_token))
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        assert "id" in j

    def test_feedback_empty_rejected(self, session, student_token):
        r = session.post(f"{API}/student/feedback",
                         json={"feedback_text": ""},
                         headers=H(student_token))
        assert r.status_code == 422


# --- Module: menu week/month + reactions ---
class TestMenuAndReactions:
    def test_menu_week(self, session, student_token):
        r = session.get(f"{API}/student/menu/week", headers=H(student_token))
        assert r.status_code == 200
        j = r.json()
        assert len(j["days"]) == 7
        for d in j["days"]:
            assert d["day"] in ["monday", "tuesday", "wednesday", "thursday",
                                "friday", "saturday", "sunday"]
            assert "reactions" in d
            assert d["reactions"]["breakfast"] in ["like", "dislike", "no_response"]

    def test_menu_month(self, session, student_token):
        r = session.get(f"{API}/student/menu/month", headers=H(student_token))
        assert r.status_code == 200
        j = r.json()
        assert len(j["weeks"]) == 4
        for w in j["weeks"]:
            assert len(w["days"]) == 7

    def test_reaction_upsert_and_idempotent(self, session, student_token):
        # First like
        r = session.put(f"{API}/student/menu/reaction",
                        json={"day": "monday", "meal_type": "lunch", "reaction": "like"},
                        headers=H(student_token))
        assert r.status_code == 200
        assert r.json()["reaction"] == "like"

        # Verify in week
        r2 = session.get(f"{API}/student/menu/week", headers=H(student_token))
        monday = next(d for d in r2.json()["days"] if d["day"] == "monday")
        assert monday["reactions"]["lunch"] == "like"

        # Update to dislike (same key) - should update not duplicate
        r3 = session.put(f"{API}/student/menu/reaction",
                         json={"day": "monday", "meal_type": "lunch",
                               "reaction": "dislike"},
                         headers=H(student_token))
        assert r3.status_code == 200
        assert r3.json()["reaction"] == "dislike"

        r4 = session.get(f"{API}/student/menu/week", headers=H(student_token))
        monday2 = next(d for d in r4.json()["days"] if d["day"] == "monday")
        assert monday2["reactions"]["lunch"] == "dislike"

    def test_reaction_invalid_day(self, session, student_token):
        r = session.put(f"{API}/student/menu/reaction",
                        json={"day": "funday", "meal_type": "lunch",
                              "reaction": "like"},
                        headers=H(student_token))
        assert r.status_code in (400, 422)


# --- Module: wastage ---
class TestWastage:
    def test_wastage_default_7(self, session, student_token):
        r = session.get(f"{API}/student/wastage?range=7&meal=all",
                        headers=H(student_token))
        assert r.status_code == 200
        j = r.json()
        assert j["range"] == 7
        assert j["meal"] == "all"
        assert len(j["series"]) == 7
        # summary keys
        assert "today" in j["summary"]
        assert j["summary"]["today"]["total"] is not None
        assert j["summary"]["yesterday_total"] is not None
        assert j["summary"]["last_week_same_day_total"] is not None
        for s in j["series"]:
            assert "date" in s and "value" in s

    def test_wastage_30(self, session, student_token):
        r = session.get(f"{API}/student/wastage?range=30&meal=all",
                        headers=H(student_token))
        assert r.status_code == 200
        assert len(r.json()["series"]) == 30

    def test_wastage_90(self, session, student_token):
        r = session.get(f"{API}/student/wastage?range=90&meal=all",
                        headers=H(student_token))
        assert r.status_code == 200
        assert len(r.json()["series"]) == 90

    def test_wastage_per_meal(self, session, student_token):
        for meal in ["breakfast", "lunch", "dinner"]:
            r = session.get(f"{API}/student/wastage?range=7&meal={meal}",
                            headers=H(student_token))
            assert r.status_code == 200
            j = r.json()
            assert j["meal"] == meal
            assert len(j["series"]) == 7
            # Values should be reasonable floats
            for s in j["series"]:
                assert isinstance(s["value"], (int, float))


# --- Module: Authorization guards (403/401) ---
class TestAuthGuards:
    endpoints = [
        ("GET", "/student/today"),
        ("GET", "/student/meta"),
        ("GET", "/student/menu/week"),
        ("GET", "/student/menu/month"),
        ("GET", "/student/wastage?range=7&meal=all"),
    ]

    def test_no_token_returns_401(self, session):
        for method, ep in self.endpoints:
            r = requests.request(method, f"{API}{ep}")
            assert r.status_code == 401, f"{ep} expected 401, got {r.status_code}"

    def test_invalid_token_returns_401(self, session):
        for method, ep in self.endpoints:
            r = requests.request(method, f"{API}{ep}",
                                 headers={"Authorization": "Bearer bad.token"})
            assert r.status_code == 401, f"{ep} expected 401, got {r.status_code}"

    def test_admin_forbidden(self, session, admin_token):
        for method, ep in self.endpoints:
            r = requests.request(method, f"{API}{ep}", headers=H(admin_token))
            assert r.status_code == 403, f"{ep} admin expected 403, got {r.status_code}"

    def test_pending_forbidden(self, session, pending_token):
        for method, ep in self.endpoints:
            r = requests.request(method, f"{API}{ep}", headers=H(pending_token))
            assert r.status_code == 403, f"{ep} pending expected 403, got {r.status_code}"

    def test_blocked_forbidden(self, session, blocked_token):
        for method, ep in self.endpoints:
            r = requests.request(method, f"{API}{ep}", headers=H(blocked_token))
            assert r.status_code == 403, f"{ep} blocked expected 403, got {r.status_code}"

    def test_admin_forbidden_put_today(self, session, admin_token):
        r = requests.put(f"{API}/student/today", json={}, headers=H(admin_token))
        assert r.status_code == 403

    def test_admin_forbidden_feedback(self, session, admin_token):
        r = requests.post(f"{API}/student/feedback",
                          json={"feedback_text": "x"}, headers=H(admin_token))
        assert r.status_code == 403

    def test_admin_forbidden_reaction(self, session, admin_token):
        r = requests.put(f"{API}/student/menu/reaction",
                         json={"day": "monday", "meal_type": "lunch",
                               "reaction": "like"},
                         headers=H(admin_token))
        assert r.status_code == 403
