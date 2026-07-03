#!/usr/bin/env python3
"""
Backend test for scheduled notifications feature.
Tests all scenarios from the review request.
"""
import time
import requests
from datetime import datetime, timedelta, timezone

# Configuration
BASE_URL = "https://repo-preview-86.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin_test_1783097886@example.com"
ADMIN_PASSWORD = "SecureAdmin123!"
STUDENT_EMAIL = "student_test_1783097886@example.com"
STUDENT_PASSWORD = "SecureStudent123!_new"

# Test state
admin_token = None
student_token = None
test_results = []


def log_result(scenario, status, details):
    """Log test result."""
    result = {
        "scenario": scenario,
        "status": status,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    test_results.append(result)
    status_icon = "✅" if status == "PASS" else "❌"
    print(f"\n{status_icon} {scenario}: {status}")
    print(f"   {details}")


def login_admin():
    """Login as admin and get token."""
    global admin_token
    print("\n🔐 Logging in as admin...")
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if resp.status_code != 200:
        print(f"❌ Admin login failed: {resp.status_code} {resp.text}")
        return False
    admin_token = resp.json()["access_token"]
    print(f"✅ Admin logged in successfully")
    return True


def login_student():
    """Login as student and get token."""
    global student_token
    print("\n🔐 Logging in as student...")
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": STUDENT_EMAIL, "password": STUDENT_PASSWORD}
    )
    if resp.status_code != 200:
        print(f"❌ Student login failed: {resp.status_code} {resp.text}")
        return False
    student_token = resp.json()["access_token"]
    print(f"✅ Student logged in successfully")
    return True


def test_scenario_1_default_template():
    """Test 1: Default template endpoint."""
    print("\n" + "="*80)
    print("SCENARIO 1: Default template endpoint")
    print("="*80)
    
    # Test with admin token
    print("\n📝 Testing GET /admin/notifications/default-template with admin token...")
    resp = requests.get(
        f"{BASE_URL}/admin/notifications/default-template",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if resp.status_code != 200:
        log_result(
            "Scenario 1 - Admin access",
            "FAIL",
            f"Expected 200, got {resp.status_code}. Response: {resp.text}"
        )
        return False
    
    data = resp.json()
    expected_title = "Help reduce food waste — mark your meals"
    
    if data.get("title") != expected_title:
        log_result(
            "Scenario 1 - Admin access",
            "FAIL",
            f"Expected title '{expected_title}', got '{data.get('title')}'"
        )
        return False
    
    if not data.get("body") or "food waste" not in data.get("body", "").lower():
        log_result(
            "Scenario 1 - Admin access",
            "FAIL",
            f"Body should mention 'food waste'. Got: {data.get('body')}"
        )
        return False
    
    log_result(
        "Scenario 1 - Admin access",
        "PASS",
        f"Admin can access default template. Title: '{data['title']}', Body length: {len(data['body'])} chars"
    )
    
    # Test with student token (should fail)
    print("\n📝 Testing GET /admin/notifications/default-template with student token...")
    resp = requests.get(
        f"{BASE_URL}/admin/notifications/default-template",
        headers={"Authorization": f"Bearer {student_token}"}
    )
    
    if resp.status_code != 403:
        log_result(
            "Scenario 1 - Student access",
            "FAIL",
            f"Expected 403 for student, got {resp.status_code}. Response: {resp.text}"
        )
        return False
    
    log_result(
        "Scenario 1 - Student access",
        "PASS",
        "Student correctly denied access (403)"
    )
    
    return True


def test_scenario_2_immediate_send():
    """Test 2: Immediate send (backward compatible)."""
    print("\n" + "="*80)
    print("SCENARIO 2: Immediate send (backward compatible)")
    print("="*80)
    
    print("\n📝 Creating immediate notification...")
    resp = requests.post(
        f"{BASE_URL}/admin/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Immediate test",
            "body": "hello now",
            "audience": "all",
            "type": "announcement"
        }
    )
    
    if resp.status_code != 201:
        log_result(
            "Scenario 2 - Create immediate",
            "FAIL",
            f"Expected 201, got {resp.status_code}. Response: {resp.text}"
        )
        return False
    
    data = resp.json()
    notif_id = data.get("id")
    
    # Verify sent=true, sent_at populated, send_at=null
    if not data.get("sent"):
        log_result(
            "Scenario 2 - Create immediate",
            "FAIL",
            f"Expected sent=true, got sent={data.get('sent')}"
        )
        return False
    
    if not data.get("sent_at"):
        log_result(
            "Scenario 2 - Create immediate",
            "FAIL",
            f"Expected sent_at to be populated, got {data.get('sent_at')}"
        )
        return False
    
    if data.get("send_at") is not None:
        log_result(
            "Scenario 2 - Create immediate",
            "FAIL",
            f"Expected send_at=null, got {data.get('send_at')}"
        )
        return False
    
    log_result(
        "Scenario 2 - Create immediate",
        "PASS",
        f"Notification created with sent=true, sent_at={data['sent_at']}, send_at=null"
    )
    
    # Verify student can see it
    print("\n📝 Checking student notifications...")
    time.sleep(2)  # Brief wait for consistency
    resp = requests.get(
        f"{BASE_URL}/student/notifications",
        headers={"Authorization": f"Bearer {student_token}"}
    )
    
    if resp.status_code != 200:
        log_result(
            "Scenario 2 - Student view",
            "FAIL",
            f"Expected 200, got {resp.status_code}. Response: {resp.text}"
        )
        return False
    
    data = resp.json()
    items = data.get("items", [])
    found = any(item.get("id") == notif_id for item in items)
    
    if not found:
        log_result(
            "Scenario 2 - Student view",
            "FAIL",
            f"Notification {notif_id} not found in student notifications. Items: {len(items)}"
        )
        return False
    
    # Find the notification and verify read=false
    notif = next((item for item in items if item.get("id") == notif_id), None)
    if notif.get("read") != False:
        log_result(
            "Scenario 2 - Student view",
            "FAIL",
            f"Expected read=false, got read={notif.get('read')}"
        )
        return False
    
    log_result(
        "Scenario 2 - Student view",
        "PASS",
        f"Student can see immediate notification with read=false"
    )
    
    return True


def test_scenario_3_scheduled_future():
    """Test 3: Scheduled future notification."""
    print("\n" + "="*80)
    print("SCENARIO 3: Scheduled future notification")
    print("="*80)
    
    # Calculate send_at = now + 90 seconds
    send_at_dt = datetime.now(timezone.utc) + timedelta(seconds=90)
    send_at_iso = send_at_dt.isoformat()
    
    print(f"\n📝 Creating scheduled notification for {send_at_iso}...")
    resp = requests.post(
        f"{BASE_URL}/admin/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Scheduled test",
            "body": "scheduled body",
            "audience": "all",
            "type": "announcement",
            "send_at": send_at_iso
        }
    )
    
    if resp.status_code != 201:
        log_result(
            "Scenario 3 - Create scheduled",
            "FAIL",
            f"Expected 201, got {resp.status_code}. Response: {resp.text}"
        )
        return None
    
    data = resp.json()
    notif_id = data.get("id")
    
    # Verify sent=false, sent_at=null, send_at populated
    if data.get("sent") != False:
        log_result(
            "Scenario 3 - Create scheduled",
            "FAIL",
            f"Expected sent=false, got sent={data.get('sent')}"
        )
        return None
    
    if data.get("sent_at") is not None:
        log_result(
            "Scenario 3 - Create scheduled",
            "FAIL",
            f"Expected sent_at=null, got {data.get('sent_at')}"
        )
        return None
    
    if not data.get("send_at"):
        log_result(
            "Scenario 3 - Create scheduled",
            "FAIL",
            f"Expected send_at to be populated, got {data.get('send_at')}"
        )
        return None
    
    log_result(
        "Scenario 3 - Create scheduled",
        "PASS",
        f"Scheduled notification created with sent=false, send_at={data['send_at']}"
    )
    
    # Verify student CANNOT see it yet
    print("\n📝 Verifying student cannot see scheduled notification yet...")
    resp = requests.get(
        f"{BASE_URL}/student/notifications",
        headers={"Authorization": f"Bearer {student_token}"}
    )
    
    if resp.status_code != 200:
        log_result(
            "Scenario 3 - Student view (before)",
            "FAIL",
            f"Expected 200, got {resp.status_code}. Response: {resp.text}"
        )
        return None
    
    data = resp.json()
    items = data.get("items", [])
    found = any(item.get("id") == notif_id for item in items)
    
    if found:
        log_result(
            "Scenario 3 - Student view (before)",
            "FAIL",
            f"Student should NOT see scheduled notification yet, but found it"
        )
        return None
    
    log_result(
        "Scenario 3 - Student view (before)",
        "PASS",
        "Student correctly cannot see scheduled notification yet"
    )
    
    # Verify admin CAN see it
    print("\n📝 Verifying admin can see scheduled notification...")
    resp = requests.get(
        f"{BASE_URL}/admin/notifications",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if resp.status_code != 200:
        log_result(
            "Scenario 3 - Admin view",
            "FAIL",
            f"Expected 200, got {resp.status_code}. Response: {resp.text}"
        )
        return None
    
    data = resp.json()
    items = data.get("items", [])
    found = any(item.get("id") == notif_id and item.get("sent") == False for item in items)
    
    if not found:
        log_result(
            "Scenario 3 - Admin view",
            "FAIL",
            f"Admin should see scheduled notification with sent=false"
        )
        return None
    
    log_result(
        "Scenario 3 - Admin view",
        "PASS",
        "Admin can see scheduled notification with sent=false"
    )
    
    return {"notif_id": notif_id, "send_at": send_at_dt}


def test_scenario_4_scheduler_fires(scheduled_info):
    """Test 4: Scheduler fires within budget."""
    if not scheduled_info:
        print("\n⚠️  Skipping scenario 4 - no scheduled notification from scenario 3")
        return False
    
    print("\n" + "="*80)
    print("SCENARIO 4: Scheduler fires within budget")
    print("="*80)
    
    notif_id = scheduled_info["notif_id"]
    send_at = scheduled_info["send_at"]
    
    # Wait until send_at + 40s (to give scheduler a full cycle)
    now = datetime.now(timezone.utc)
    wait_until = send_at + timedelta(seconds=40)
    wait_seconds = (wait_until - now).total_seconds()
    
    if wait_seconds > 0:
        print(f"\n⏳ Waiting {wait_seconds:.0f} seconds for scheduler to fire...")
        time.sleep(wait_seconds)
    
    # Poll student notifications up to 3 times with 15s waits
    print("\n📝 Polling student notifications (up to 3 attempts)...")
    max_attempts = 3
    found = False
    
    for attempt in range(1, max_attempts + 1):
        print(f"   Attempt {attempt}/{max_attempts}...")
        resp = requests.get(
            f"{BASE_URL}/student/notifications",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        if resp.status_code != 200:
            print(f"   ⚠️  Got {resp.status_code}: {resp.text}")
            time.sleep(15)
            continue
        
        data = resp.json()
        items = data.get("items", [])
        notif = next((item for item in items if item.get("id") == notif_id), None)
        
        if notif:
            found = True
            print(f"   ✅ Found notification!")
            break
        
        if attempt < max_attempts:
            print(f"   Not found yet, waiting 15s...")
            time.sleep(15)
    
    if not found:
        log_result(
            "Scenario 4 - Scheduler fires",
            "FAIL",
            f"Notification {notif_id} not found in student notifications after {max_attempts} attempts"
        )
        return False
    
    # Verify admin list shows sent=true
    print("\n📝 Verifying admin list shows sent=true...")
    resp = requests.get(
        f"{BASE_URL}/admin/notifications",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    if resp.status_code != 200:
        log_result(
            "Scenario 4 - Admin verification",
            "FAIL",
            f"Expected 200, got {resp.status_code}. Response: {resp.text}"
        )
        return False
    
    data = resp.json()
    items = data.get("items", [])
    notif = next((item for item in items if item.get("id") == notif_id), None)
    
    if not notif:
        log_result(
            "Scenario 4 - Admin verification",
            "FAIL",
            f"Notification {notif_id} not found in admin list"
        )
        return False
    
    if not notif.get("sent"):
        log_result(
            "Scenario 4 - Admin verification",
            "FAIL",
            f"Expected sent=true, got sent={notif.get('sent')}"
        )
        return False
    
    if not notif.get("sent_at"):
        log_result(
            "Scenario 4 - Admin verification",
            "FAIL",
            f"Expected sent_at to be populated, got {notif.get('sent_at')}"
        )
        return False
    
    log_result(
        "Scenario 4 - Scheduler fires",
        "PASS",
        f"Scheduler fired successfully. Notification visible to student, sent=true, sent_at={notif['sent_at']}"
    )
    
    return True


def test_scenario_5_bad_payloads():
    """Test 5: Bad payloads."""
    print("\n" + "="*80)
    print("SCENARIO 5: Bad payloads")
    print("="*80)
    
    # Test invalid send_at
    print("\n📝 Testing invalid send_at format...")
    resp = requests.post(
        f"{BASE_URL}/admin/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Bad date test",
            "body": "test body",
            "audience": "all",
            "type": "announcement",
            "send_at": "not-a-date"
        }
    )
    
    if resp.status_code != 400:
        log_result(
            "Scenario 5 - Invalid send_at",
            "FAIL",
            f"Expected 400, got {resp.status_code}. Response: {resp.text}"
        )
        return False
    
    if "ISO" not in resp.text:
        log_result(
            "Scenario 5 - Invalid send_at",
            "FAIL",
            f"Error message should mention ISO format. Got: {resp.text}"
        )
        return False
    
    log_result(
        "Scenario 5 - Invalid send_at",
        "PASS",
        f"Invalid send_at correctly rejected with 400: {resp.json().get('detail')}"
    )
    
    # Test past send_at (should be treated as immediate)
    print("\n📝 Testing past send_at (should be immediate)...")
    past_dt = datetime.now(timezone.utc) - timedelta(seconds=60)
    past_iso = past_dt.isoformat()
    
    resp = requests.post(
        f"{BASE_URL}/admin/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Past date test",
            "body": "test body",
            "audience": "all",
            "type": "announcement",
            "send_at": past_iso
        }
    )
    
    if resp.status_code != 201:
        log_result(
            "Scenario 5 - Past send_at",
            "FAIL",
            f"Expected 201, got {resp.status_code}. Response: {resp.text}"
        )
        return False
    
    data = resp.json()
    
    if not data.get("sent"):
        log_result(
            "Scenario 5 - Past send_at",
            "FAIL",
            f"Past send_at should be treated as immediate (sent=true), got sent={data.get('sent')}"
        )
        return False
    
    log_result(
        "Scenario 5 - Past send_at",
        "PASS",
        f"Past send_at correctly treated as immediate: sent=true, sent_at={data['sent_at']}"
    )
    
    return True


def test_scenario_6_scheduler_restart():
    """Test 6: Scheduler robustness across restart."""
    print("\n" + "="*80)
    print("SCENARIO 6: Scheduler robustness across restart")
    print("="*80)
    
    # Create scheduled notification with send_at = now + 60s
    send_at_dt = datetime.now(timezone.utc) + timedelta(seconds=60)
    send_at_iso = send_at_dt.isoformat()
    
    print(f"\n📝 Creating scheduled notification for {send_at_iso}...")
    resp = requests.post(
        f"{BASE_URL}/admin/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Restart test",
            "body": "restart body",
            "audience": "all",
            "type": "announcement",
            "send_at": send_at_iso
        }
    )
    
    if resp.status_code != 201:
        log_result(
            "Scenario 6 - Create scheduled",
            "FAIL",
            f"Expected 201, got {resp.status_code}. Response: {resp.text}"
        )
        return False
    
    data = resp.json()
    notif_id = data.get("id")
    
    log_result(
        "Scenario 6 - Create scheduled",
        "PASS",
        f"Scheduled notification created: {notif_id}"
    )
    
    # Restart backend
    print("\n📝 Restarting backend...")
    import subprocess
    result = subprocess.run(
        ["sudo", "supervisorctl", "restart", "backend"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        log_result(
            "Scenario 6 - Restart backend",
            "FAIL",
            f"Failed to restart backend: {result.stderr}"
        )
        return False
    
    print("   Backend restart initiated, waiting 10s...")
    time.sleep(10)
    
    # Verify backend is up
    print("\n📝 Verifying backend is up...")
    max_attempts = 5
    backend_up = False
    
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.get(f"{BASE_URL.replace('/api', '')}/api/", timeout=5)
            if resp.status_code == 200:
                backend_up = True
                print(f"   ✅ Backend is up (attempt {attempt})")
                break
        except Exception as e:
            print(f"   Attempt {attempt}: {e}")
        
        if attempt < max_attempts:
            time.sleep(3)
    
    if not backend_up:
        log_result(
            "Scenario 6 - Backend health",
            "FAIL",
            "Backend did not come up after restart"
        )
        return False
    
    log_result(
        "Scenario 6 - Backend health",
        "PASS",
        "Backend is up and responding"
    )
    
    # Check logs for scheduler start message
    print("\n📝 Checking backend logs for scheduler start...")
    result = subprocess.run(
        ["tail", "-n", "50", "/var/log/supervisor/backend.err.log"],
        capture_output=True,
        text=True
    )
    
    if "Notification scheduler started" not in result.stdout:
        log_result(
            "Scenario 6 - Scheduler restart",
            "FAIL",
            "Scheduler start message not found in logs"
        )
        return False
    
    log_result(
        "Scenario 6 - Scheduler restart",
        "PASS",
        "Scheduler started after backend restart"
    )
    
    # Wait until send_at + 40s
    now = datetime.now(timezone.utc)
    wait_until = send_at_dt + timedelta(seconds=40)
    wait_seconds = (wait_until - now).total_seconds()
    
    if wait_seconds > 0:
        print(f"\n⏳ Waiting {wait_seconds:.0f} seconds for scheduler to fire...")
        time.sleep(wait_seconds)
    
    # Poll student notifications
    print("\n📝 Polling student notifications (up to 3 attempts)...")
    max_attempts = 3
    found = False
    
    for attempt in range(1, max_attempts + 1):
        print(f"   Attempt {attempt}/{max_attempts}...")
        resp = requests.get(
            f"{BASE_URL}/student/notifications",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        if resp.status_code != 200:
            print(f"   ⚠️  Got {resp.status_code}: {resp.text}")
            time.sleep(15)
            continue
        
        data = resp.json()
        items = data.get("items", [])
        notif = next((item for item in items if item.get("id") == notif_id), None)
        
        if notif:
            found = True
            print(f"   ✅ Found notification!")
            break
        
        if attempt < max_attempts:
            print(f"   Not found yet, waiting 15s...")
            time.sleep(15)
    
    if not found:
        log_result(
            "Scenario 6 - Scheduler pickup",
            "FAIL",
            f"Notification {notif_id} not found after restart"
        )
        return False
    
    log_result(
        "Scenario 6 - Scheduler pickup",
        "PASS",
        "Scheduler picked up notification after restart"
    )
    
    return True


def print_summary():
    """Print test summary."""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in test_results if r["status"] == "PASS")
    failed = sum(1 for r in test_results if r["status"] == "FAIL")
    total = len(test_results)
    
    print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")
    
    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for r in test_results:
            if r["status"] == "FAIL":
                print(f"   - {r['scenario']}")
                print(f"     {r['details']}")
    
    print("\n" + "="*80)
    
    return failed == 0


def main():
    """Run all tests."""
    print("="*80)
    print("SCHEDULED NOTIFICATIONS BACKEND TEST")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Admin: {ADMIN_EMAIL}")
    print(f"Student: {STUDENT_EMAIL}")
    
    # Login
    if not login_admin():
        print("\n❌ Failed to login as admin. Aborting tests.")
        return False
    
    if not login_student():
        print("\n❌ Failed to login as student. Aborting tests.")
        return False
    
    # Run tests
    test_scenario_1_default_template()
    test_scenario_2_immediate_send()
    scheduled_info = test_scenario_3_scheduled_future()
    test_scenario_4_scheduler_fires(scheduled_info)
    test_scenario_5_bad_payloads()
    test_scenario_6_scheduler_restart()
    
    # Print summary
    success = print_summary()
    
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
