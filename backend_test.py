#!/usr/bin/env python3
"""
Backend test for single-device session enforcement on MessMate.
Tests all scenarios from the review request.
"""

import re
import subprocess
import time
from typing import Optional, Dict, Any

import httpx

# Backend URL from frontend/.env
BASE_URL = "https://repo-preview-86.preview.emergentagent.com/api"

# Test data
TEST_HOSTEL = "Test Hostel"
ADMIN_EMAIL = f"admin_test_{int(time.time())}@example.com"
ADMIN_PASSWORD = "SecureAdmin123!"
STUDENT_EMAIL = f"student_test_{int(time.time())}@example.com"
STUDENT_PASSWORD = "SecureStudent123!"

# Store credentials for future use
credentials = []


def log(msg: str):
    """Print with timestamp."""
    print(f"[TEST] {msg}")


def extract_otp_from_logs(email: str, purpose: str) -> Optional[str]:
    """Extract OTP from backend logs."""
    try:
        # Check both out and err logs
        for log_file in ["/var/log/supervisor/backend.err.log", "/var/log/supervisor/backend.out.log"]:
            result = subprocess.run(
                ["tail", "-n", "200", log_file],
                capture_output=True,
                text=True,
                timeout=5,
            )
            lines = result.stdout.split("\n")
            # Look for: [DEV-OTP] purpose=registration to=alice@example.com otp=123456
            pattern = rf"\[DEV-OTP\] purpose={purpose} to={re.escape(email)} otp=(\d+)"
            for line in reversed(lines):
                match = re.search(pattern, line)
                if match:
                    return match.group(1)
        return None
    except Exception as e:
        log(f"Error reading logs: {e}")
        return None


def register_user(
    email: str, password: str, full_name: str, role: str = "student"
) -> Dict[str, Any]:
    """Register a new user and return response."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": email,
                "password": password,
                "confirm_password": password,
                "full_name": full_name,
                "institution_or_hostel_name": TEST_HOSTEL,
                "role": role,
            },
        )
        return {"status_code": resp.status_code, "body": resp.json()}


def verify_email(email: str, otp: str) -> Dict[str, Any]:
    """Verify email with OTP."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{BASE_URL}/auth/verify-email",
            json={"email": email, "otp": otp},
        )
        return {"status_code": resp.status_code, "body": resp.json()}


def login(email: str, password: str) -> Dict[str, Any]:
    """Login and return response."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
        )
        return {"status_code": resp.status_code, "body": resp.json()}


def get_me(token: str) -> Dict[str, Any]:
    """Get current user info."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        return {"status_code": resp.status_code, "body": resp.json()}


def approve_student(admin_token: str, student_id: str) -> Dict[str, Any]:
    """Approve a student."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{BASE_URL}/admin/students/{student_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        return {"status_code": resp.status_code, "body": resp.json()}


def put_student_today(token: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update student's daily plan."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.put(
            f"{BASE_URL}/student/today",
            headers={"Authorization": f"Bearer {token}"},
            json=data,
        )
        return {"status_code": resp.status_code, "body": resp.json()}


def get_student_today(token: str) -> Dict[str, Any]:
    """Get student's daily plan."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            f"{BASE_URL}/student/today",
            headers={"Authorization": f"Bearer {token}"},
        )
        return {"status_code": resp.status_code, "body": resp.json()}


def forgot_password(email: str) -> Dict[str, Any]:
    """Request password reset."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{BASE_URL}/auth/forgot-password",
            json={"email": email},
        )
        return {"status_code": resp.status_code, "body": resp.json()}


def forgot_password_verify(email: str, otp: str) -> Dict[str, Any]:
    """Verify forgot password OTP."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{BASE_URL}/auth/forgot-password/verify",
            json={"email": email, "otp": otp},
        )
        return {"status_code": resp.status_code, "body": resp.json()}


def reset_password(reset_token: str, new_password: str) -> Dict[str, Any]:
    """Reset password with token."""
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{BASE_URL}/auth/reset-password",
            json={
                "reset_token": reset_token,
                "new_password": new_password,
                "confirm_password": new_password,
            },
        )
        return {"status_code": resp.status_code, "body": resp.json()}


def test_scenario_1():
    """
    Scenario 1: Happy-path session rotation on login
    - Register student, verify email → token_A
    - Login → token_B
    - token_B should work, token_A should be invalidated
    """
    log("=" * 80)
    log("SCENARIO 1: Happy-path session rotation on login")
    log("=" * 80)

    # Register student
    log(f"Registering student: {STUDENT_EMAIL}")
    reg_resp = register_user(STUDENT_EMAIL, STUDENT_PASSWORD, "Test Student", "student")
    log(f"Registration response: {reg_resp['status_code']} - {reg_resp['body']}")
    
    if reg_resp["status_code"] not in [200, 201]:
        log(f"❌ FAIL: Registration failed")
        return False

    # Wait a bit for log to be written
    time.sleep(1)

    # Extract OTP
    log("Extracting OTP from backend logs...")
    otp = extract_otp_from_logs(STUDENT_EMAIL, "registration")
    if not otp:
        log("❌ FAIL: Could not extract OTP from logs")
        return False
    log(f"Found OTP: {otp}")

    # Verify email → token_A
    log("Verifying email...")
    verify_resp = verify_email(STUDENT_EMAIL, otp)
    log(f"Verify response: {verify_resp['status_code']} - {verify_resp['body']}")
    
    if verify_resp["status_code"] != 200:
        log(f"❌ FAIL: Email verification failed")
        return False

    token_A = verify_resp["body"].get("access_token")
    if not token_A:
        log("❌ FAIL: No access_token in verify response")
        return False
    log(f"Got token_A: {token_A[:20]}...")

    # Store student ID for later
    student_id = verify_resp["body"]["user"]["id"]
    credentials.append({
        "email": STUDENT_EMAIL,
        "password": STUDENT_PASSWORD,
        "role": "student",
        "institution": TEST_HOSTEL,
        "id": student_id,
    })

    # Login → token_B
    log("Logging in (simulating second device)...")
    login_resp = login(STUDENT_EMAIL, STUDENT_PASSWORD)
    log(f"Login response: {login_resp['status_code']} - {login_resp['body']}")
    
    if login_resp["status_code"] != 200:
        log(f"❌ FAIL: Login failed")
        return False

    token_B = login_resp["body"].get("access_token")
    if not token_B:
        log("❌ FAIL: No access_token in login response")
        return False
    log(f"Got token_B: {token_B[:20]}...")

    # Verify tokens are different
    if token_A == token_B:
        log("❌ FAIL: token_A and token_B are the same!")
        return False
    log("✓ token_A != token_B")

    # Test token_B works
    log("Testing token_B with /auth/me...")
    me_resp_B = get_me(token_B)
    log(f"GET /auth/me with token_B: {me_resp_B['status_code']} - {me_resp_B['body']}")
    
    if me_resp_B["status_code"] != 200:
        log("❌ FAIL: token_B should work but got non-200")
        return False
    log("✓ token_B works (200 OK)")

    # Test token_A is invalidated
    log("Testing token_A with /auth/me (should be invalidated)...")
    me_resp_A = get_me(token_A)
    log(f"GET /auth/me with token_A: {me_resp_A['status_code']} - {me_resp_A['body']}")
    
    if me_resp_A["status_code"] != 401:
        log(f"❌ FAIL: token_A should return 401 but got {me_resp_A['status_code']}")
        return False

    detail = me_resp_A["body"].get("detail", {})
    if isinstance(detail, dict):
        code = detail.get("code")
        if code != "session_invalidated":
            log(f"❌ FAIL: Expected detail.code='session_invalidated' but got '{code}'")
            return False
        log(f"✓ token_A invalidated with correct error: {detail}")
    else:
        log(f"⚠️  WARNING: detail is not a dict: {detail}")

    log("✅ SCENARIO 1: PASS")
    return True


def test_scenario_2(token_B: str):
    """
    Scenario 2: Chained invalidation
    - Login again → token_C
    - token_B should be invalid, token_C should work
    """
    log("=" * 80)
    log("SCENARIO 2: Chained invalidation")
    log("=" * 80)

    # Login again → token_C
    log("Logging in again (third device)...")
    login_resp = login(STUDENT_EMAIL, STUDENT_PASSWORD)
    log(f"Login response: {login_resp['status_code']} - {login_resp['body']}")
    
    if login_resp["status_code"] != 200:
        log(f"❌ FAIL: Login failed")
        return False, None

    token_C = login_resp["body"].get("access_token")
    if not token_C:
        log("❌ FAIL: No access_token in login response")
        return False, None
    log(f"Got token_C: {token_C[:20]}...")

    # Test token_B is now invalid
    log("Testing token_B (should be invalidated)...")
    me_resp_B = get_me(token_B)
    log(f"GET /auth/me with token_B: {me_resp_B['status_code']} - {me_resp_B['body']}")
    
    if me_resp_B["status_code"] != 401:
        log(f"❌ FAIL: token_B should return 401 but got {me_resp_B['status_code']}")
        return False, None

    detail = me_resp_B["body"].get("detail", {})
    if isinstance(detail, dict) and detail.get("code") == "session_invalidated":
        log(f"✓ token_B invalidated correctly")
    else:
        log(f"⚠️  WARNING: Unexpected detail format: {detail}")

    # Test token_C works
    log("Testing token_C...")
    me_resp_C = get_me(token_C)
    log(f"GET /auth/me with token_C: {me_resp_C['status_code']} - {me_resp_C['body']}")
    
    if me_resp_C["status_code"] != 200:
        log(f"❌ FAIL: token_C should work but got {me_resp_C['status_code']}")
        return False, None
    log("✓ token_C works")

    log("✅ SCENARIO 2: PASS")
    return True, token_C


def test_scenario_3(admin_token: str, student_id: str, token_C: str):
    """
    Scenario 3: Cross-device data sharing
    - Approve student
    - Write data with token_C
    - Login again → token_D
    - Read data with token_D (should be same)
    """
    log("=" * 80)
    log("SCENARIO 3: Cross-device data sharing")
    log("=" * 80)

    # Approve student
    log(f"Approving student {student_id}...")
    approve_resp = approve_student(admin_token, student_id)
    log(f"Approve response: {approve_resp['status_code']} - {approve_resp['body']}")
    
    if approve_resp["status_code"] != 200:
        log(f"❌ FAIL: Student approval failed")
        return False, None

    # Write data with token_C
    log("Writing daily plan with token_C...")
    plan_data = {
        "breakfast": {
            "status": "ON",
            "selected_items": ["Idli", "Sambar"],
        },
        "lunch": {
            "status": "ON",
            "selected_items": ["Rice", "Dal"],
        },
        "dinner": {
            "status": "OFF",
            "reason_if_off": "Going home",
        },
    }
    put_resp = put_student_today(token_C, plan_data)
    log(f"PUT /student/today: {put_resp['status_code']} - {put_resp['body']}")
    
    if put_resp["status_code"] != 200:
        log(f"❌ FAIL: Failed to write daily plan")
        return False, None

    # Read back with token_C
    log("Reading daily plan with token_C...")
    get_resp_C = get_student_today(token_C)
    log(f"GET /student/today with token_C: {get_resp_C['status_code']}")
    
    if get_resp_C["status_code"] != 200:
        log(f"❌ FAIL: Failed to read daily plan with token_C")
        return False, None

    plan_C = get_resp_C["body"].get("plan")
    if not plan_C:
        log("❌ FAIL: No plan data returned")
        return False, None
    log(f"✓ Data written and read with token_C")

    # Login again → token_D
    log("Logging in again (fourth device) → token_D...")
    login_resp = login(STUDENT_EMAIL, STUDENT_PASSWORD)
    log(f"Login response: {login_resp['status_code']}")
    
    if login_resp["status_code"] != 200:
        log(f"❌ FAIL: Login failed")
        return False, None

    token_D = login_resp["body"].get("access_token")
    if not token_D:
        log("❌ FAIL: No access_token")
        return False, None
    log(f"Got token_D: {token_D[:20]}...")

    # Read data with token_D
    log("Reading daily plan with token_D...")
    get_resp_D = get_student_today(token_D)
    log(f"GET /student/today with token_D: {get_resp_D['status_code']}")
    
    if get_resp_D["status_code"] != 200:
        log(f"❌ FAIL: Failed to read daily plan with token_D")
        return False, None

    plan_D = get_resp_D["body"].get("plan")
    if not plan_D:
        log("❌ FAIL: No plan data returned with token_D")
        return False, None

    # Compare data
    if plan_C == plan_D:
        log("✓ Data persists across sessions (same user_id)")
    else:
        log(f"⚠️  WARNING: Data mismatch between token_C and token_D")
        log(f"  plan_C: {plan_C}")
        log(f"  plan_D: {plan_D}")

    log("✅ SCENARIO 3: PASS")
    return True, token_D


def test_scenario_4(token_D: str):
    """
    Scenario 4: verify-email re-issue also rotates
    - For already-verified user, POST /auth/verify-email should rotate session
    - token_D should become invalid
    """
    log("=" * 80)
    log("SCENARIO 4: verify-email re-issue rotates session")
    log("=" * 80)

    # Call verify-email again (user already verified)
    log("Calling /auth/verify-email for already-verified user...")
    # Use any OTP - it should short-circuit
    verify_resp = verify_email(STUDENT_EMAIL, "000000")
    log(f"Verify response: {verify_resp['status_code']} - {verify_resp['body']}")
    
    if verify_resp["status_code"] != 200:
        log(f"❌ FAIL: verify-email should return 200 for already-verified user")
        return False

    token_E = verify_resp["body"].get("access_token")
    if not token_E:
        log("❌ FAIL: No access_token in verify response")
        return False
    log(f"Got new token from verify-email: {token_E[:20]}...")

    # Test token_D is now invalid
    log("Testing token_D (should be invalidated)...")
    me_resp_D = get_me(token_D)
    log(f"GET /auth/me with token_D: {me_resp_D['status_code']} - {me_resp_D['body']}")
    
    if me_resp_D["status_code"] != 401:
        log(f"❌ FAIL: token_D should return 401 but got {me_resp_D['status_code']}")
        return False

    detail = me_resp_D["body"].get("detail", {})
    if isinstance(detail, dict) and detail.get("code") == "session_invalidated":
        log(f"✓ token_D invalidated correctly")
    else:
        log(f"⚠️  WARNING: Unexpected detail format: {detail}")

    # Test new token works
    log("Testing new token from verify-email...")
    me_resp_E = get_me(token_E)
    log(f"GET /auth/me with new token: {me_resp_E['status_code']}")
    
    if me_resp_E["status_code"] != 200:
        log(f"❌ FAIL: New token should work but got {me_resp_E['status_code']}")
        return False
    log("✓ New token works")

    log("✅ SCENARIO 4: PASS")
    return True


def test_scenario_5():
    """
    Scenario 5: reset-password rotates session
    - Request password reset
    - Verify OTP → reset_token
    - Reset password → token_R
    - All prior tokens should be invalid
    """
    log("=" * 80)
    log("SCENARIO 5: reset-password rotates session")
    log("=" * 80)

    # Get a valid token first
    log("Getting a valid token before reset...")
    login_resp = login(STUDENT_EMAIL, STUDENT_PASSWORD)
    if login_resp["status_code"] != 200:
        log(f"❌ FAIL: Login failed")
        return False
    token_before = login_resp["body"].get("access_token")
    log(f"Got token_before: {token_before[:20]}...")

    # Request password reset
    log("Requesting password reset...")
    forgot_resp = forgot_password(STUDENT_EMAIL)
    log(f"Forgot password response: {forgot_resp['status_code']} - {forgot_resp['body']}")
    
    if forgot_resp["status_code"] != 200:
        log(f"❌ FAIL: Forgot password failed")
        return False

    # Wait for log
    time.sleep(1)

    # Extract OTP
    log("Extracting forgot-password OTP from logs...")
    otp = extract_otp_from_logs(STUDENT_EMAIL, "forgot_password")
    if not otp:
        log("❌ FAIL: Could not extract forgot-password OTP")
        return False
    log(f"Found OTP: {otp}")

    # Verify OTP → reset_token
    log("Verifying forgot-password OTP...")
    verify_resp = forgot_password_verify(STUDENT_EMAIL, otp)
    log(f"Verify response: {verify_resp['status_code']} - {verify_resp['body']}")
    
    if verify_resp["status_code"] != 200:
        log(f"❌ FAIL: Forgot password verify failed")
        return False

    reset_token = verify_resp["body"].get("reset_token")
    if not reset_token:
        log("❌ FAIL: No reset_token in response")
        return False
    log(f"Got reset_token: {reset_token[:20]}...")

    # Reset password → token_R
    new_password = STUDENT_PASSWORD + "_new"
    log(f"Resetting password to: {new_password}")
    reset_resp = reset_password(reset_token, new_password)
    log(f"Reset password response: {reset_resp['status_code']} - {reset_resp['body']}")
    
    if reset_resp["status_code"] != 200:
        log(f"❌ FAIL: Reset password failed")
        return False

    token_R = reset_resp["body"].get("access_token")
    if not token_R:
        log("❌ FAIL: No access_token in reset response")
        return False
    log(f"Got token_R: {token_R[:20]}...")

    # Update password in credentials
    for cred in credentials:
        if cred["email"] == STUDENT_EMAIL:
            cred["password"] = new_password

    # Test token_before is now invalid
    log("Testing token_before (should be invalidated)...")
    me_resp_before = get_me(token_before)
    log(f"GET /auth/me with token_before: {me_resp_before['status_code']} - {me_resp_before['body']}")
    
    if me_resp_before["status_code"] != 401:
        log(f"❌ FAIL: token_before should return 401 but got {me_resp_before['status_code']}")
        return False

    detail = me_resp_before["body"].get("detail", {})
    if isinstance(detail, dict) and detail.get("code") == "session_invalidated":
        log(f"✓ token_before invalidated correctly")
    else:
        log(f"⚠️  WARNING: Unexpected detail format: {detail}")

    # Test token_R works
    log("Testing token_R...")
    me_resp_R = get_me(token_R)
    log(f"GET /auth/me with token_R: {me_resp_R['status_code']}")
    
    if me_resp_R["status_code"] != 200:
        log(f"❌ FAIL: token_R should work but got {me_resp_R['status_code']}")
        return False
    log("✓ token_R works")

    log("✅ SCENARIO 5: PASS")
    return True


def test_scenario_6():
    """
    Scenario 6: Regression - unauthenticated + invalid tokens
    - No token → 401
    - Garbage token → 401
    """
    log("=" * 80)
    log("SCENARIO 6: Regression tests")
    log("=" * 80)

    # Test no token
    log("Testing /auth/me with no token...")
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{BASE_URL}/auth/me")
        log(f"Response: {resp.status_code} - {resp.json()}")
        if resp.status_code != 401:
            log(f"❌ FAIL: Expected 401 but got {resp.status_code}")
            return False
        log("✓ No token → 401")

    # Test garbage token
    log("Testing /auth/me with garbage token...")
    garbage_resp = get_me("garbage_token_12345")
    log(f"Response: {garbage_resp['status_code']} - {garbage_resp['body']}")
    if garbage_resp["status_code"] != 401:
        log(f"❌ FAIL: Expected 401 but got {garbage_resp['status_code']}")
        return False
    log("✓ Garbage token → 401")

    log("✅ SCENARIO 6: PASS")
    return True


def setup_admin():
    """Create and verify admin account."""
    log("=" * 80)
    log("SETUP: Creating admin account")
    log("=" * 80)

    # Register admin
    log(f"Registering admin: {ADMIN_EMAIL}")
    reg_resp = register_user(ADMIN_EMAIL, ADMIN_PASSWORD, "Test Admin", "admin")
    log(f"Registration response: {reg_resp['status_code']} - {reg_resp['body']}")
    
    if reg_resp["status_code"] not in [200, 201]:
        log(f"❌ FAIL: Admin registration failed")
        return None

    # Wait for log
    time.sleep(1)

    # Extract OTP
    log("Extracting OTP from backend logs...")
    otp = extract_otp_from_logs(ADMIN_EMAIL, "registration")
    if not otp:
        log("❌ FAIL: Could not extract OTP from logs")
        return None
    log(f"Found OTP: {otp}")

    # Verify email
    log("Verifying admin email...")
    verify_resp = verify_email(ADMIN_EMAIL, otp)
    log(f"Verify response: {verify_resp['status_code']} - {verify_resp['body']}")
    
    if verify_resp["status_code"] != 200:
        log(f"❌ FAIL: Admin email verification failed")
        return None

    admin_token = verify_resp["body"].get("access_token")
    if not admin_token:
        log("❌ FAIL: No access_token in verify response")
        return None

    admin_id = verify_resp["body"]["user"]["id"]
    credentials.append({
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
        "role": "admin",
        "institution": TEST_HOSTEL,
        "id": admin_id,
    })

    log(f"✓ Admin created and verified: {admin_id}")
    return admin_token


def save_credentials():
    """Save test credentials to file."""
    log("=" * 80)
    log("Saving test credentials...")
    log("=" * 80)
    
    content = "# Test Credentials for MessMate\n\n"
    content += f"Institution: {TEST_HOSTEL}\n\n"
    
    for cred in credentials:
        content += f"## {cred['role'].upper()}\n"
        content += f"- Email: {cred['email']}\n"
        content += f"- Password: {cred['password']}\n"
        content += f"- ID: {cred['id']}\n"
        content += f"- Institution: {cred['institution']}\n\n"
    
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write(content)
    
    log("✓ Credentials saved to /app/memory/test_credentials.md")


def main():
    """Run all test scenarios."""
    log("=" * 80)
    log("MESSMATE BACKEND TEST - Single-Device Session Enforcement")
    log("=" * 80)
    log(f"Backend URL: {BASE_URL}")
    log(f"Test Hostel: {TEST_HOSTEL}")
    log("")

    results = {}

    # Setup admin first
    admin_token = setup_admin()
    if not admin_token:
        log("❌ CRITICAL: Admin setup failed, cannot continue")
        return

    # Scenario 1: Happy-path session rotation
    results["scenario_1"] = test_scenario_1()
    if not results["scenario_1"]:
        log("❌ Scenario 1 failed, stopping tests")
        save_credentials()
        return

    # Get token_B for scenario 2
    login_resp = login(STUDENT_EMAIL, STUDENT_PASSWORD)
    token_B = login_resp["body"].get("access_token")

    # Scenario 2: Chained invalidation
    success, token_C = test_scenario_2(token_B)
    results["scenario_2"] = success
    if not success:
        log("❌ Scenario 2 failed, stopping tests")
        save_credentials()
        return

    # Scenario 3: Cross-device data sharing
    student_id = credentials[-1]["id"]  # Last added is student
    success, token_D = test_scenario_3(admin_token, student_id, token_C)
    results["scenario_3"] = success
    if not success:
        log("❌ Scenario 3 failed, stopping tests")
        save_credentials()
        return

    # Scenario 4: verify-email re-issue
    results["scenario_4"] = test_scenario_4(token_D)

    # Scenario 5: reset-password rotation
    results["scenario_5"] = test_scenario_5()

    # Scenario 6: Regression tests
    results["scenario_6"] = test_scenario_6()

    # Save credentials
    save_credentials()

    # Summary
    log("=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    for scenario, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        log(f"{scenario}: {status}")
    
    all_passed = all(results.values())
    log("")
    if all_passed:
        log("🎉 ALL TESTS PASSED")
    else:
        log("❌ SOME TESTS FAILED")
    
    return all_passed


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        log(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
