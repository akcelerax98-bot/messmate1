#!/usr/bin/env python3
"""
Backend test for PATCH + DELETE /api/admin/notifications/{id}
Tests all 11 scenarios from the review request.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

import httpx

# Base URL from frontend/.env
BASE_URL = "https://repo-preview-86.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin_test_1783097886@example.com"
ADMIN_PASSWORD = "SecureAdmin123!"
STUDENT_EMAIL = "student_test_1783097886@example.com"
STUDENT_PASSWORD = "SecureStudent123!_new"

# Global tokens
ADMIN_TOKEN = None
STUDENT_TOKEN = None
OTHER_ADMIN_TOKEN = None


def log(msg: str):
    """Print with timestamp."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def iso_future(seconds: int) -> str:
    """Return ISO datetime N seconds in the future."""
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def iso_past(seconds: int) -> str:
    """Return ISO datetime N seconds in the past."""
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


async def login(email: str, password: str) -> str:
    """Login and return access token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
        )
        if resp.status_code != 200:
            log(f"❌ Login failed for {email}: {resp.status_code} {resp.text}")
            sys.exit(1)
        data = resp.json()
        token = data["access_token"]
        log(f"✅ Logged in as {email}")
        return token


async def register_and_verify_admin(
    email: str, password: str, institution: str
) -> str:
    """Register a new admin, extract OTP from logs, verify, and return token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Register
        resp = await client.post(
            f"{BASE_URL}/auth/register",
            json={
                "full_name": "Other Admin",
                "email": email,
                "password": password,
                "confirm_password": password,
                "institution_or_hostel_name": institution,
                "role": "admin",
            },
        )
        if resp.status_code not in (200, 201):
            log(f"❌ Registration failed: {resp.status_code} {resp.text}")
            sys.exit(1)
        log(f"✅ Registered {email}")

        # Extract OTP from backend logs
        import subprocess
        result = subprocess.run(
            ["tail", "-n", "100", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
        )
        lines = result.stdout.split("\n")
        otp = None
        for line in reversed(lines):
            if "[DEV-OTP]" in line and f"to={email}" in line:
                parts = line.split("otp=")
                if len(parts) > 1:
                    otp = parts[1].split()[0].strip()
                    break
        if not otp:
            log(f"❌ Could not extract OTP for {email}")
            sys.exit(1)
        log(f"✅ Extracted OTP: {otp}")

        # Verify email
        resp = await client.post(
            f"{BASE_URL}/auth/verify-email",
            json={"email": email, "otp": otp},
        )
        if resp.status_code != 200:
            log(f"❌ Email verification failed: {resp.status_code} {resp.text}")
            sys.exit(1)
        data = resp.json()
        token = data["access_token"]
        log(f"✅ Verified email for {email}")
        return token


async def create_notification(
    token: str, title: str, body: str, send_at: Optional[str] = None
) -> Dict[str, Any]:
    """Create a notification and return the response."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "title": title,
            "body": body,
            "audience": "all",
        }
        if send_at:
            payload["send_at"] = send_at
        resp = await client.post(
            f"{BASE_URL}/admin/notifications",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        return {"status": resp.status_code, "data": resp.json() if resp.status_code < 500 else None, "text": resp.text}


async def patch_notification(
    token: str, nid: str, updates: Dict[str, Any]
) -> Dict[str, Any]:
    """PATCH a notification and return the response."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(
            f"{BASE_URL}/admin/notifications/{nid}",
            json=updates,
            headers={"Authorization": f"Bearer {token}"},
        )
        return {"status": resp.status_code, "data": resp.json() if resp.status_code < 500 else None, "text": resp.text}


async def delete_notification(token: str, nid: str) -> int:
    """DELETE a notification and return status code."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(
            f"{BASE_URL}/admin/notifications/{nid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.status_code


async def get_admin_notifications(token: str) -> Dict[str, Any]:
    """GET admin notifications list."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BASE_URL}/admin/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.json() if resp.status_code == 200 else {}


async def get_student_notifications(token: str) -> Dict[str, Any]:
    """GET student notifications list."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BASE_URL}/student/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.json() if resp.status_code == 200 else {}


async def setup():
    """Setup: login admin and student."""
    global ADMIN_TOKEN, STUDENT_TOKEN
    log("=== SETUP ===")
    ADMIN_TOKEN = await login(ADMIN_EMAIL, ADMIN_PASSWORD)
    STUDENT_TOKEN = await login(STUDENT_EMAIL, STUDENT_PASSWORD)
    log("")


async def scenario_1():
    """Scenario 1: PATCH title + body only."""
    log("=== Scenario 1: PATCH title + body only ===")
    # Create scheduled notification
    send_at = iso_future(300)  # 5 minutes
    result = await create_notification(ADMIN_TOKEN, "To edit", "orig body", send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']} {result['text']}")
        return False
    nid = result["data"]["id"]
    log(f"✅ Created notification {nid} with sent={result['data']['sent']}")

    # PATCH title + body
    patch_result = await patch_notification(
        ADMIN_TOKEN, nid, {"title": "Edited title", "body": "edited body"}
    )
    if patch_result["status"] != 200:
        log(f"❌ PATCH failed: {patch_result['status']} {patch_result['text']}")
        return False
    log(f"✅ PATCH returned 200: title={patch_result['data']['title']}, body={patch_result['data']['body']}")

    # Verify via GET
    admin_list = await get_admin_notifications(ADMIN_TOKEN)
    notif = next((n for n in admin_list.get("items", []) if n["id"] == nid), None)
    if not notif:
        log(f"❌ Notification {nid} not found in admin list")
        return False
    if notif["title"] != "Edited title" or notif["body"] != "edited body":
        log(f"❌ Title/body mismatch: {notif['title']}, {notif['body']}")
        return False
    if notif["sent"] is not False:
        log(f"❌ sent should be False, got {notif['sent']}")
        return False
    log(f"✅ Verified: title={notif['title']}, body={notif['body']}, sent={notif['sent']}")
    log("✅ Scenario 1: PASS\n")
    return True


async def scenario_2():
    """Scenario 2: PATCH send_at to a new future time."""
    log("=== Scenario 2: PATCH send_at to a new future time ===")
    # Create scheduled notification
    send_at = iso_future(300)
    result = await create_notification(ADMIN_TOKEN, "To reschedule", "body", send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']}")
        return False
    nid = result["data"]["id"]
    log(f"✅ Created notification {nid}")

    # PATCH send_at to new time
    new_send_at = iso_future(900)  # 15 minutes
    patch_result = await patch_notification(ADMIN_TOKEN, nid, {"send_at": new_send_at})
    if patch_result["status"] != 200:
        log(f"❌ PATCH failed: {patch_result['status']} {patch_result['text']}")
        return False
    log(f"✅ PATCH returned 200: send_at={patch_result['data']['send_at']}, scheduled_for={patch_result['data']['scheduled_for']}")

    # Verify new send_at
    if patch_result["data"]["send_at"] != new_send_at:
        log(f"❌ send_at mismatch: expected {new_send_at}, got {patch_result['data']['send_at']}")
        return False
    log("✅ Scenario 2: PASS\n")
    return True


async def scenario_3():
    """Scenario 3: PATCH with send_at in the past."""
    log("=== Scenario 3: PATCH with send_at in the past ===")
    # Create scheduled notification
    send_at = iso_future(300)
    result = await create_notification(ADMIN_TOKEN, "Past test", "body", send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']}")
        return False
    nid = result["data"]["id"]
    log(f"✅ Created notification {nid}")

    # PATCH with past send_at
    past_send_at = iso_past(60)
    patch_result = await patch_notification(ADMIN_TOKEN, nid, {"send_at": past_send_at})
    if patch_result["status"] != 400:
        log(f"❌ Expected 400, got {patch_result['status']}")
        return False
    if "future" not in patch_result["data"].get("detail", "").lower():
        log(f"❌ Expected 'future' in error message, got: {patch_result['data'].get('detail')}")
        return False
    log(f"✅ PATCH returned 400 with message: {patch_result['data']['detail']}")
    log("✅ Scenario 3: PASS\n")
    return True


async def scenario_4():
    """Scenario 4: PATCH with malformed send_at."""
    log("=== Scenario 4: PATCH with malformed send_at ===")
    # Create scheduled notification
    send_at = iso_future(300)
    result = await create_notification(ADMIN_TOKEN, "Malformed test", "body", send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']}")
        return False
    nid = result["data"]["id"]
    log(f"✅ Created notification {nid}")

    # PATCH with malformed send_at
    patch_result = await patch_notification(ADMIN_TOKEN, nid, {"send_at": "not-a-date"})
    if patch_result["status"] != 400:
        log(f"❌ Expected 400, got {patch_result['status']}")
        return False
    if "iso" not in patch_result["data"].get("detail", "").lower():
        log(f"❌ Expected 'ISO' in error message, got: {patch_result['data'].get('detail')}")
        return False
    log(f"✅ PATCH returned 400 with message: {patch_result['data']['detail']}")
    log("✅ Scenario 4: PASS\n")
    return True


async def scenario_5():
    """Scenario 5: Cross-hostel isolation."""
    global OTHER_ADMIN_TOKEN
    log("=== Scenario 5: Cross-hostel isolation ===")
    
    # Create notification with original admin
    send_at = iso_future(300)
    result = await create_notification(ADMIN_TOKEN, "Cross-hostel test", "body", send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']}")
        return False
    nid = result["data"]["id"]
    log(f"✅ Created notification {nid} with original admin")

    # Register and verify another admin under different institution
    other_email = f"other_admin_{int(datetime.now().timestamp())}@example.com"
    OTHER_ADMIN_TOKEN = await register_and_verify_admin(
        other_email, "SecureAdmin123!", "Other Hostel"
    )

    # Try PATCH with other admin token
    patch_result = await patch_notification(
        OTHER_ADMIN_TOKEN, nid, {"title": "Should fail"}
    )
    if patch_result["status"] != 404:
        log(f"❌ Expected 404, got {patch_result['status']}")
        return False
    log(f"✅ PATCH with OTHER_ADMIN_TOKEN returned 404")

    # Try DELETE with other admin token
    delete_status = await delete_notification(OTHER_ADMIN_TOKEN, nid)
    if delete_status != 404:
        log(f"❌ Expected 404, got {delete_status}")
        return False
    log(f"✅ DELETE with OTHER_ADMIN_TOKEN returned 404")

    # Verify original admin still owns the notification
    admin_list = await get_admin_notifications(ADMIN_TOKEN)
    notif = next((n for n in admin_list.get("items", []) if n["id"] == nid), None)
    if not notif:
        log(f"❌ Notification {nid} not found in original admin list")
        return False
    log(f"✅ Original admin still owns notification {nid}")
    log("✅ Scenario 5: PASS\n")
    return True


async def scenario_6():
    """Scenario 6: Cannot edit already-sent notifications."""
    log("=== Scenario 6: Cannot edit already-sent notifications ===")
    # Create notification with past send_at (immediate send)
    past_send_at = iso_past(60)
    result = await create_notification(ADMIN_TOKEN, "Now item", "now body", past_send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']}")
        return False
    nid2 = result["data"]["id"]
    if result["data"]["sent"] is not True:
        log(f"❌ Expected sent=True, got {result['data']['sent']}")
        return False
    log(f"✅ Created notification {nid2} with sent={result['data']['sent']}")

    # Try to PATCH
    patch_result = await patch_notification(ADMIN_TOKEN, nid2, {"title": "nope"})
    if patch_result["status"] != 400:
        log(f"❌ Expected 400, got {patch_result['status']}")
        return False
    if "already" not in patch_result["data"].get("detail", "").lower():
        log(f"❌ Expected 'already' in error message, got: {patch_result['data'].get('detail')}")
        return False
    log(f"✅ PATCH returned 400 with message: {patch_result['data']['detail']}")
    log("✅ Scenario 6: PASS\n")
    return True


async def scenario_7():
    """Scenario 7: DELETE scheduled."""
    log("=== Scenario 7: DELETE scheduled ===")
    # Create scheduled notification
    send_at = iso_future(300)
    result = await create_notification(ADMIN_TOKEN, "To delete", "body", send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']}")
        return False
    nid = result["data"]["id"]
    log(f"✅ Created notification {nid}")

    # DELETE
    delete_status = await delete_notification(ADMIN_TOKEN, nid)
    if delete_status != 204:
        log(f"❌ Expected 204, got {delete_status}")
        return False
    log(f"✅ DELETE returned 204")

    # Verify not in list
    admin_list = await get_admin_notifications(ADMIN_TOKEN)
    notif = next((n for n in admin_list.get("items", []) if n["id"] == nid), None)
    if notif:
        log(f"❌ Notification {nid} still in admin list")
        return False
    log(f"✅ Notification {nid} not in admin list")

    # DELETE again
    delete_status = await delete_notification(ADMIN_TOKEN, nid)
    if delete_status != 404:
        log(f"❌ Expected 404, got {delete_status}")
        return False
    log(f"✅ DELETE again returned 404")
    log("✅ Scenario 7: PASS\n")
    return True


async def scenario_8():
    """Scenario 8: DELETE already-sent."""
    log("=== Scenario 8: DELETE already-sent ===")
    # Create immediate notification
    past_send_at = iso_past(60)
    result = await create_notification(ADMIN_TOKEN, "Sent item", "body", past_send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']}")
        return False
    nid2 = result["data"]["id"]
    if result["data"]["sent"] is not True:
        log(f"❌ Expected sent=True, got {result['data']['sent']}")
        return False
    log(f"✅ Created notification {nid2} with sent={result['data']['sent']}")

    # DELETE
    delete_status = await delete_notification(ADMIN_TOKEN, nid2)
    if delete_status != 204:
        log(f"❌ Expected 204, got {delete_status}")
        return False
    log(f"✅ DELETE returned 204")

    # Verify not in list
    admin_list = await get_admin_notifications(ADMIN_TOKEN)
    notif = next((n for n in admin_list.get("items", []) if n["id"] == nid2), None)
    if notif:
        log(f"❌ Notification {nid2} still in admin list")
        return False
    log(f"✅ Notification {nid2} not in admin list")
    log("✅ Scenario 8: PASS\n")
    return True


async def scenario_9():
    """Scenario 9: Auth."""
    log("=== Scenario 9: Auth ===")
    # Create notification
    send_at = iso_future(300)
    result = await create_notification(ADMIN_TOKEN, "Auth test", "body", send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']}")
        return False
    nid = result["data"]["id"]
    log(f"✅ Created notification {nid}")

    # PATCH with student token
    patch_result = await patch_notification(STUDENT_TOKEN, nid, {"title": "nope"})
    if patch_result["status"] != 403:
        log(f"❌ Expected 403, got {patch_result['status']}")
        return False
    log(f"✅ PATCH with STUDENT_TOKEN returned 403")

    # DELETE with student token
    delete_status = await delete_notification(STUDENT_TOKEN, nid)
    if delete_status != 403:
        log(f"❌ Expected 403, got {delete_status}")
        return False
    log(f"✅ DELETE with STUDENT_TOKEN returned 403")

    # PATCH with no token
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(
            f"{BASE_URL}/admin/notifications/{nid}",
            json={"title": "nope"},
        )
        if resp.status_code != 401:
            log(f"❌ Expected 401, got {resp.status_code}")
            return False
        log(f"✅ PATCH with no token returned 401")

    # DELETE with no token
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(f"{BASE_URL}/admin/notifications/{nid}")
        if resp.status_code != 401:
            log(f"❌ Expected 401, got {resp.status_code}")
            return False
        log(f"✅ DELETE with no token returned 401")

    log("✅ Scenario 9: PASS\n")
    return True


async def scenario_10():
    """Scenario 10: Student view unaffected across edits."""
    log("=== Scenario 10: Student view unaffected across edits ===")
    # Create scheduled notification
    send_at = iso_future(300)
    result = await create_notification(ADMIN_TOKEN, "Student view test", "body", send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']}")
        return False
    nid3 = result["data"]["id"]
    log(f"✅ Created notification {nid3}")

    # GET student notifications
    student_list = await get_student_notifications(STUDENT_TOKEN)
    notif = next((n for n in student_list.get("items", []) if n["id"] == nid3), None)
    if notif:
        log(f"❌ Notification {nid3} should NOT be in student list (unsent)")
        return False
    log(f"✅ Notification {nid3} NOT in student list (unsent)")

    # PATCH body
    patch_result = await patch_notification(ADMIN_TOKEN, nid3, {"body": "edited body"})
    if patch_result["status"] != 200:
        log(f"❌ PATCH failed: {patch_result['status']}")
        return False
    log(f"✅ PATCH returned 200")

    # GET student notifications again
    student_list = await get_student_notifications(STUDENT_TOKEN)
    notif = next((n for n in student_list.get("items", []) if n["id"] == nid3), None)
    if notif:
        log(f"❌ Notification {nid3} should still NOT be in student list")
        return False
    log(f"✅ Notification {nid3} still NOT in student list")

    # DELETE
    delete_status = await delete_notification(ADMIN_TOKEN, nid3)
    if delete_status != 204:
        log(f"❌ Expected 204, got {delete_status}")
        return False
    log(f"✅ DELETE returned 204")

    # GET student notifications again
    student_list = await get_student_notifications(STUDENT_TOKEN)
    notif = next((n for n in student_list.get("items", []) if n["id"] == nid3), None)
    if notif:
        log(f"❌ Notification {nid3} should still NOT be in student list")
        return False
    log(f"✅ Notification {nid3} still NOT in student list")
    log("✅ Scenario 10: PASS\n")
    return True


async def scenario_11():
    """Scenario 11: Empty PATCH."""
    log("=== Scenario 11: Empty PATCH ===")
    # Create scheduled notification
    send_at = iso_future(300)
    result = await create_notification(ADMIN_TOKEN, "Empty patch test", "body", send_at)
    if result["status"] != 201:
        log(f"❌ Failed to create notification: {result['status']}")
        return False
    nid4 = result["data"]["id"]
    log(f"✅ Created notification {nid4}")

    # PATCH with empty body
    patch_result = await patch_notification(ADMIN_TOKEN, nid4, {})
    if patch_result["status"] != 400:
        log(f"❌ Expected 400, got {patch_result['status']}")
        return False
    if "no changes" not in patch_result["data"].get("detail", "").lower():
        log(f"❌ Expected 'No changes' in error message, got: {patch_result['data'].get('detail')}")
        return False
    log(f"✅ PATCH returned 400 with message: {patch_result['data']['detail']}")

    # Cleanup
    delete_status = await delete_notification(ADMIN_TOKEN, nid4)
    if delete_status != 204:
        log(f"❌ Expected 204, got {delete_status}")
        return False
    log(f"✅ DELETE returned 204")
    log("✅ Scenario 11: PASS\n")
    return True


async def main():
    """Run all scenarios."""
    log("=" * 80)
    log("BACKEND TEST: PATCH + DELETE /api/admin/notifications/{id}")
    log("=" * 80)
    log("")

    await setup()

    results = []
    results.append(("Scenario 1: PATCH title + body", await scenario_1()))
    results.append(("Scenario 2: PATCH send_at", await scenario_2()))
    results.append(("Scenario 3: PATCH past send_at", await scenario_3()))
    results.append(("Scenario 4: PATCH malformed send_at", await scenario_4()))
    results.append(("Scenario 5: Cross-hostel isolation", await scenario_5()))
    results.append(("Scenario 6: Cannot edit sent", await scenario_6()))
    results.append(("Scenario 7: DELETE scheduled", await scenario_7()))
    results.append(("Scenario 8: DELETE sent", await scenario_8()))
    results.append(("Scenario 9: Auth", await scenario_9()))
    results.append(("Scenario 10: Student view unaffected", await scenario_10()))
    results.append(("Scenario 11: Empty PATCH", await scenario_11()))

    log("=" * 80)
    log("SUMMARY")
    log("=" * 80)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"{status} - {name}")
    log("")
    log(f"Total: {passed}/{total} passed")
    log("=" * 80)

    if passed == total:
        log("🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        log("❌ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
