"""MessMate backend admin tests (Part 3)."""
import os
import uuid
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break
API = f"{BASE_URL}/api"


# ---------------- shared session + tokens ----------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={
        "mobile_or_user_id": "admin",
        "password": "admin123",
        "institution_or_hostel_name": "Demo Hostel",
    })
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def student_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={
        "mobile_or_user_id": "student", "password": "student123",
    })
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def anon_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- Students Status ----------------
class TestStudentsStatus:
    def test_summary_returns_numeric_counts(self, admin_session):
        r = admin_session.get(f"{API}/admin/students/summary")
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ("total_students", "approved", "pending", "blocked"):
            assert isinstance(j.get(k), int), f"{k} is not int: {j}"
        # sanity: counts sum >= each individual
        assert j["total_students"] >= j["approved"] + j["pending"] + j["blocked"] - 1

    def test_list_status_pending_filter(self, admin_session):
        r = admin_session.get(f"{API}/admin/students?status=pending")
        assert r.status_code == 200
        j = r.json()
        assert "students" in j and "count" in j
        for s in j["students"]:
            assert s["approval_status"] == "pending"
            assert "password_hash" not in s
            assert "_id" not in s

    def test_list_status_approved_filter(self, admin_session):
        r = admin_session.get(f"{API}/admin/students?status=approved")
        assert r.status_code == 200
        for s in r.json()["students"]:
            assert s["approval_status"] == "approved"

    def test_list_status_blocked_filter(self, admin_session):
        r = admin_session.get(f"{API}/admin/students?status=blocked")
        assert r.status_code == 200
        for s in r.json()["students"]:
            assert s["approval_status"] == "rejected_or_blocked"

    def test_list_status_all(self, admin_session):
        r = admin_session.get(f"{API}/admin/students?status=all")
        assert r.status_code == 200
        statuses = {s["approval_status"] for s in r.json()["students"]}
        assert statuses.issubset({"pending", "approved", "rejected_or_blocked"})

    def test_approve_then_reject_flow(self, admin_session):
        # find a pending student (seeded pending001..pending004 are demo)
        r = admin_session.get(f"{API}/admin/students?status=pending")
        pending = r.json()["students"]
        assert pending, "Need at least 1 pending student for this test"
        # Prefer one of the demo cohort (pending00x) so as not to disturb 'pending' login user
        candidate = next(
            (s for s in pending if s["mobile_or_user_id"].startswith("pending0")),
            pending[0],
        )
        sid = candidate["id"]

        # Approve
        r = admin_session.post(f"{API}/admin/students/{sid}/approve")
        assert r.status_code == 200, r.text
        assert r.json()["approval_status"] == "approved"

        # GET verify
        r = admin_session.get(f"{API}/admin/students?status=approved")
        approved_ids = [s["id"] for s in r.json()["students"]]
        assert sid in approved_ids

        # Reject (flip back so subsequent test runs find pending students)
        r = admin_session.post(f"{API}/admin/students/{sid}/reject")
        assert r.status_code == 200
        assert r.json()["approval_status"] == "rejected_or_blocked"

        # GET verify
        r = admin_session.get(f"{API}/admin/students?status=blocked")
        blocked_ids = [s["id"] for s in r.json()["students"]]
        assert sid in blocked_ids

        # Restore to pending for next run (direct endpoint to "pending" doesn't exist;
        # we leave as blocked since 4 demo pending users exist).

    def test_approve_unknown_id_404(self, admin_session):
        r = admin_session.post(f"{API}/admin/students/{uuid.uuid4()}/approve")
        assert r.status_code == 404

    def test_reject_unknown_id_404(self, admin_session):
        r = admin_session.post(f"{API}/admin/students/{uuid.uuid4()}/reject")
        assert r.status_code == 404


# ---------------- Admin Today ----------------
class TestAdminToday:
    def test_today_structure(self, admin_session):
        r = admin_session.get(f"{API}/admin/today")
        assert r.status_code == 200, r.text
        j = r.json()
        assert "date" in j and "day" in j and "total_responses" in j
        assert isinstance(j["total_responses"], int)
        for meal in ("breakfast", "lunch", "dinner"):
            m = j[meal]
            for key in (
                "eating_count", "not_eating_count", "item_counts",
                "reason_counts", "custom_answer_counts", "like_pct", "dislike_pct",
            ):
                assert key in m, f"missing {key} in {meal}"
            # likes/dislikes are percentages
            assert 0 <= m["like_pct"] <= 100
            assert 0 <= m["dislike_pct"] <= 100

    def test_today_has_responses(self, admin_session):
        r = admin_session.get(f"{API}/admin/today")
        j = r.json()
        # Seeded data: total responses should be >0 since today's plans are seeded
        assert j["total_responses"] > 0, "today's plans not seeded?"


# ---------------- Feedback anonymity ----------------
class TestFeedback:
    def test_feedback_anonymous(self, admin_session):
        r = admin_session.get(f"{API}/admin/feedback?days=7")
        assert r.status_code == 200
        j = r.json()
        for item in j["items"]:
            assert "feedback_text" in item
            assert "date" in item
            # MUST be anonymous - no identifier exposed
            for forbidden in ("student_id", "user_id", "mobile_or_user_id", "full_name"):
                assert forbidden not in item, f"feedback leaked {forbidden}: {item}"


# ---------------- Dashboard ----------------
class TestDashboard:
    def test_dashboard_returns_meals(self, admin_session):
        r = admin_session.get(f"{API}/admin/dashboard")
        assert r.status_code == 200, r.text
        j = r.json()
        assert "meals" in j and "summary" in j
        for meal in ("breakfast", "lunch", "dinner"):
            m = j["meals"][meal]
            assert "items" in m and "warnings" in m
            for it in m["items"]:
                assert "preference_count" in it and "item_name" in it
                # if quantity_per_person is set, suggested must be count*qpp
                if it.get("quantity_per_person") is not None:
                    expected = round(it["preference_count"] * float(it["quantity_per_person"]), 2)
                    assert abs(it["suggested"] - expected) < 0.011
                    assert "display" in it and it["display"]
                else:
                    assert it["suggested"] is None


# ---------------- Necessary Info CRUD ----------------
class TestNecessaryInfo:
    created_id = None

    def test_list_returns_seeded(self, admin_session):
        r = admin_session.get(f"{API}/admin/necessary-info")
        assert r.status_code == 200
        j = r.json()
        assert j["count"] >= 1
        assert j["items"]

    def test_create_then_update_then_delete(self, admin_session):
        unique = f"TEST_Item_{uuid.uuid4().hex[:6]}"
        payload = {
            "item_name": unique, "meal_type": "breakfast",
            "quantity_per_person": 100, "unit": "grams",
            "price_per_unit": 200, "price_unit": "kg",
        }
        r = admin_session.post(f"{API}/admin/necessary-info", json=payload)
        assert r.status_code == 201, r.text
        item_id = r.json()["id"]

        # Duplicate -> 400
        r2 = admin_session.post(f"{API}/admin/necessary-info", json=payload)
        assert r2.status_code == 400

        # Update
        payload["quantity_per_person"] = 150
        r = admin_session.put(f"{API}/admin/necessary-info/{item_id}", json=payload)
        assert r.status_code == 200
        assert r.json()["quantity_per_person"] == 150

        # GET verify
        r = admin_session.get(f"{API}/admin/necessary-info")
        found = next((x for x in r.json()["items"] if x["id"] == item_id), None)
        assert found and found["quantity_per_person"] == 150

        # Delete
        r = admin_session.delete(f"{API}/admin/necessary-info/{item_id}")
        assert r.status_code == 200

        # GET verify gone
        r = admin_session.get(f"{API}/admin/necessary-info")
        ids = [x["id"] for x in r.json()["items"]]
        assert item_id not in ids


# ---------------- Menus ----------------
class TestMenus:
    def test_list_returns_7_days(self, admin_session):
        r = admin_session.get(f"{API}/admin/menus")
        assert r.status_code == 200
        days = r.json()["days"]
        assert len(days) == 7
        assert {d["day"] for d in days} == {
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
        }

    def test_upsert_monday_persists(self, admin_session):
        # snapshot current monday
        r = admin_session.get(f"{API}/admin/menus")
        mon = next(d for d in r.json()["days"] if d["day"] == "monday")
        original_breakfast = mon.get("breakfast_items", [])

        new_items = original_breakfast + ["TEST_AdminItem"]
        body = {
            "breakfast_items": new_items,
            "lunch_items": mon.get("lunch_items", []),
            "dinner_items": mon.get("dinner_items", []),
            "breakfast_custom_question": mon.get("breakfast_custom_question"),
            "lunch_custom_question": mon.get("lunch_custom_question"),
            "dinner_custom_question": mon.get("dinner_custom_question"),
        }
        r = admin_session.put(f"{API}/admin/menus/monday", json=body)
        assert r.status_code == 200, r.text
        assert "TEST_AdminItem" in r.json()["breakfast_items"]

        # GET verify
        r = admin_session.get(f"{API}/admin/menus")
        mon = next(d for d in r.json()["days"] if d["day"] == "monday")
        assert "TEST_AdminItem" in mon["breakfast_items"]

        # cleanup
        body["breakfast_items"] = original_breakfast
        admin_session.put(f"{API}/admin/menus/monday", json=body)


# ---------------- Wastage ----------------
class TestWastage:
    def test_upsert_today_computes_loss(self, admin_session):
        today = date.today().isoformat()
        # First fetch necessary-info to get a real (item_name, meal_type) so price lookup works
        r = admin_session.get(f"{API}/admin/necessary-info")
        items = r.json()["items"]
        # pick a breakfast item
        b_item = next((i for i in items if i["meal_type"] == "breakfast"), None)
        l_item = next((i for i in items if i["meal_type"] == "lunch"), None)
        d_item = next((i for i in items if i["meal_type"] == "dinner"), None)
        assert b_item and l_item and d_item

        payload = {
            "breakfast_items": [{
                "item_name": b_item["item_name"], "quantity": 1.0, "unit": "kg",
            }],
            "lunch_items": [{
                "item_name": l_item["item_name"], "quantity": 0.5, "unit": "kg",
            }],
            "dinner_items": [{
                "item_name": d_item["item_name"], "quantity": 0.25, "unit": "kg",
            }],
        }
        r = admin_session.put(f"{API}/admin/wastage/{today}", json=payload)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] is True
        w = j["wastage"]
        assert w["date"] == today
        for k in ("breakfast_loss", "lunch_loss", "dinner_loss", "total_loss"):
            assert isinstance(w[k], (int, float)), f"{k} not numeric"
        # total_loss = sum
        assert abs(w["total_loss"] - round(w["breakfast_loss"]+w["lunch_loss"]+w["dinner_loss"], 2)) < 0.011
        for k in ("breakfast_wastage_kg", "lunch_wastage_kg", "dinner_wastage_kg"):
            assert isinstance(w[k], (int, float))

    def test_wastage_today_endpoint(self, admin_session):
        r = admin_session.get(f"{API}/admin/wastage/today")
        assert r.status_code == 200
        j = r.json()
        for k in ("today", "yesterday", "last_week_same_day", "average_loss_30d", "saved_amount_vs_avg"):
            assert k in j

    def test_wastage_trend_7(self, admin_session):
        r = admin_session.get(f"{API}/admin/wastage/trend?range=7&meal=all")
        assert r.status_code == 200
        j = r.json()
        assert len(j["wastage_series"]) == 7
        assert len(j["saved_series"]) == 7

    def test_wastage_trend_30_breakfast(self, admin_session):
        r = admin_session.get(f"{API}/admin/wastage/trend?range=30&meal=breakfast")
        assert r.status_code == 200
        j = r.json()
        assert j["meal"] == "breakfast"
        assert len(j["wastage_series"]) == 30

    def test_wastage_trend_90_lunch(self, admin_session):
        r = admin_session.get(f"{API}/admin/wastage/trend?range=90&meal=lunch")
        assert r.status_code == 200
        assert len(r.json()["wastage_series"]) == 90

    def test_wastage_trend_dinner(self, admin_session):
        r = admin_session.get(f"{API}/admin/wastage/trend?range=7&meal=dinner")
        assert r.status_code == 200
        assert r.json()["meal"] == "dinner"


# ---------------- Settings ----------------
class TestSettings:
    def test_get_returns_singleton(self, admin_session):
        r = admin_session.get(f"{API}/admin/settings")
        assert r.status_code == 200
        j = r.json()
        for k in ("default_meal_state", "default_like_dislike_state",
                  "default_preference_state", "notifications_enabled"):
            assert k in j

    def test_put_updates_meal_state(self, admin_session):
        # snapshot
        original = admin_session.get(f"{API}/admin/settings").json()
        r = admin_session.put(f"{API}/admin/settings", json={"default_meal_state": "OFF"})
        assert r.status_code == 200
        assert r.json()["default_meal_state"] == "OFF"
        # GET verify
        r = admin_session.get(f"{API}/admin/settings")
        assert r.json()["default_meal_state"] == "OFF"
        # restore
        admin_session.put(f"{API}/admin/settings", json={
            "default_meal_state": original.get("default_meal_state", "ON")
        })


# ---------------- Auth Guard (403/401) ----------------
ADMIN_GET_ENDPOINTS = [
    "/admin/students/summary",
    "/admin/students",
    "/admin/today",
    "/admin/feedback",
    "/admin/necessary-info",
    "/admin/menus",
    "/admin/dashboard",
    "/admin/wastage/today",
    "/admin/wastage/trend",
    "/admin/settings",
]


class TestAuthGuards:
    @pytest.mark.parametrize("path", ADMIN_GET_ENDPOINTS)
    def test_student_gets_403(self, student_session, path):
        r = student_session.get(f"{API}{path}")
        assert r.status_code == 403, f"{path}: expected 403, got {r.status_code}"

    @pytest.mark.parametrize("path", ADMIN_GET_ENDPOINTS)
    def test_anon_gets_401(self, anon_session, path):
        r = anon_session.get(f"{API}{path}")
        assert r.status_code == 401, f"{path}: expected 401, got {r.status_code}"

    def test_student_cannot_approve(self, student_session):
        r = student_session.post(f"{API}/admin/students/{uuid.uuid4()}/approve")
        assert r.status_code == 403

    def test_student_cannot_put_wastage(self, student_session):
        today = date.today().isoformat()
        r = student_session.put(
            f"{API}/admin/wastage/{today}",
            json={"breakfast_items": [], "lunch_items": [], "dinner_items": []},
        )
        assert r.status_code == 403

    def test_student_cannot_put_settings(self, student_session):
        r = student_session.put(f"{API}/admin/settings", json={"default_meal_state": "OFF"})
        assert r.status_code == 403

    def test_invalid_token_401(self, anon_session):
        r = anon_session.get(
            f"{API}/admin/students/summary",
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
        assert r.status_code == 401
