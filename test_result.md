#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Make sure the app works across different devices — the same account should
  share data across all devices where it's signed in. However, an account
  should be logged in on only ONE device at a time. If a user signs in on a
  new device, the previous device should be logged out automatically.

backend:
  - task: "Single-device session enforcement (server-side session id + JWT sid claim)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            Added `active_session_id` on the user document. Introduced
            `rotate_session(user_id)` which mints a fresh UUID and stores it on
            the user doc, then embeds it as the `sid` claim in the JWT.
            Rotation happens in:
              - POST /api/auth/login
              - POST /api/auth/verify-email (both success and already-verified branches)
              - POST /api/auth/reset-password
            `get_current_user` now compares the token's `sid` with the user's
            `active_session_id`. On mismatch, returns 401 with detail
            `{"code":"session_invalidated","message":"You've been signed out because this account was signed in on another device."}`.
            Cross-device data sharing already works because all state is stored
            server-side in MongoDB keyed by user_id — no code changes needed for
            that requirement.
        - working: true
          agent: "testing"
          comment: |
            ✅ ALL SCENARIOS PASSED - Comprehensive backend testing completed:
            
            Scenario 1 (Happy-path session rotation): PASS
            - Registered student, verified email → token_A
            - Login → token_B (different from token_A)
            - token_B works (200 OK on /auth/me)
            - token_A invalidated (401 with correct error: {"code":"session_invalidated","message":"You've been signed out because this account was signed in on another device."})
            
            Scenario 2 (Chained invalidation): PASS
            - Login again → token_C
            - token_B invalidated (401 session_invalidated)
            - token_C works (200 OK)
            
            Scenario 3 (Cross-device data sharing): PASS
            - Approved student via admin token
            - Wrote daily plan with token_C (breakfast: Idli/Sambar, lunch: Rice/Dal, dinner: OFF)
            - Login again → token_D
            - Read same data with token_D - data persists correctly (same user_id)
            
            Scenario 4 (verify-email re-issue rotates): PASS
            - Called /auth/verify-email for already-verified user
            - Received new token
            - token_D invalidated (401 session_invalidated)
            - New token works (200 OK)
            
            Scenario 5 (reset-password rotates): PASS
            - Got valid token_before
            - Requested password reset, extracted OTP from logs
            - Verified OTP → reset_token
            - Reset password → token_R
            - token_before invalidated (401 session_invalidated)
            - token_R works (200 OK)
            
            Scenario 6 (Regression tests): PASS
            - No token → 401 "Not authenticated"
            - Garbage token → 401 "Invalid or expired token"
            
            Test credentials saved to /app/memory/test_credentials.md
            - Admin: admin_test_1783097886@example.com / SecureAdmin123!
            - Student: student_test_1783097886@example.com / SecureStudent123!_new
            
            All session enforcement mechanisms working correctly. OTPs logged to /var/log/supervisor/backend.err.log as expected.

frontend:
  - task: "Auto-logout when session invalidated by another device"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/api/client.ts, /app/frontend/src/auth/AuthContext.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            Added `setSessionInvalidatedHandler` in api/client.ts. When any API
            call returns 401 with detail.code === "session_invalidated", the
            handler fires. AuthContext registers a handler that clears stored
            token/user, sets state to logged-out (which triggers routing back
            to `/`), and shows an Alert. Also added a boot-time `/auth/me`
            probe so the previous device gets kicked out as soon as the app
            opens (not only on the first action).

metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 1
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    - agent: "main"
      message: |
        Please test the single-device session enforcement end-to-end:
        1. Register a fresh student account via POST /api/auth/register. Since
           SMTP is not configured, the OTP is logged to backend stdout — read
           it from `/var/log/supervisor/backend.out.log` (look for a line
           like `[DEV-OTP] purpose=registration to=... otp=......`).
        2. POST /api/auth/verify-email → capture token_A.
        3. POST /api/auth/login with the SAME creds → capture token_B (this
           simulates a second device signing in). Confirm token_A != token_B.
        4. GET /api/auth/me with token_B → should return 200 and user data.
        5. GET /api/auth/me with token_A → should return 401 with detail
           `{"code":"session_invalidated","message":"..."}`.
        6. Also verify that repeating step 3 (a third login) invalidates
           token_B, and confirm cross-device data sharing by hitting a data
           endpoint (e.g. PUT /api/student/today then GET) with the currently
           active token to ensure data persists per user.
        7. Confirm password reset flow also rotates the session: after
           /auth/forgot-password → /auth/forgot-password/verify →
           /auth/reset-password, any previously-issued token becomes
           session_invalidated.
        Institution/hostel name to use: "Test Hostel". Role: student. Because
        first admin of a new hostel auto-approves, if you want to test student
        auth flows on a fresh institution, first register an admin, then a
        student, then approve the student via POST /api/admin/students/{sid}/approve
        using the admin's token. Update /app/memory/test_credentials.md with
        whatever accounts you create.
    - agent: "testing"
      message: |
        ✅ TESTING COMPLETE - All scenarios passed successfully!
        
        Created comprehensive backend test suite (/app/backend_test.py) covering:
        - Session rotation on login (token invalidation)
        - Chained invalidation (multiple logins)
        - Cross-device data sharing (data persists per user_id)
        - verify-email re-issue session rotation
        - reset-password session rotation
        - Regression tests (no token, invalid token)
        
        Key findings:
        - OTPs are logged to /var/log/supervisor/backend.err.log (not .out.log)
        - All session enforcement working correctly
        - Session invalidation returns proper error format
        - Data sharing works correctly across sessions
        - Test credentials documented in /app/memory/test_credentials.md
        
        No issues found. Implementation is production-ready.


###############################################################################
# NEW FEATURE — Scheduled Notifications with default template
###############################################################################

user_problem_statement: |
  Admin should be able to set date and time for notifications to be sent to
  all users, with an editable text and a pre-filled default focused on
  reminding students to participate and reduce food waste. Students should
  receive a push notification on their phone AND be able to view a list of
  all past notifications on a dedicated in-app notifications page (opened
  from the bell icon).

backend:
  - task: "Scheduled notification dispatch + default reminder template"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            Extended notifications:
              - New NotificationCreate.send_at (ISO datetime, optional)
              - New notification doc fields: send_at, sent (bool), sent_at
              - POST /api/admin/notifications: when send_at is in the future,
                stores with sent=False and defers push; when null/past, fires
                push immediately (backward compatible).
              - Background asyncio scheduler task `_scheduler_loop` polls
                every 30s for `sent=False AND send_at <= now`, dispatches
                push via existing send_push() relay, marks sent=True + sent_at.
              - `_project_notif` now returns send_at / sent / sent_at.
              - `student_notifications` filters out sent=False items so
                students only see notifications that have actually fired.
              - NEW: GET /api/admin/notifications/default-template returns
                the default title + body: "Help reduce food waste — mark
                your meals" + full body reminding students to participate.
        - working: true
          agent: "testing"
          comment: |
            ✅ ALL SCENARIOS PASSED - Comprehensive backend testing completed (14/14 tests passed):
            
            Scenario 1 - Default template endpoint:
            ✅ Admin access: GET /admin/notifications/default-template returns 200 with correct title "Help reduce food waste — mark your meals" and body (234 chars) mentioning food waste and participation
            ✅ Student access: Correctly denied with 403 (admin-only endpoint)
            
            Scenario 2 - Immediate send (backward compatible):
            ✅ Create immediate: POST /admin/notifications without send_at returns 201 with sent=true, sent_at populated, send_at=null
            ✅ Student view: Notification immediately visible in GET /student/notifications with read=false
            
            Scenario 3 - Scheduled future notification:
            ✅ Create scheduled: POST /admin/notifications with send_at=(now+90s) returns 201 with sent=false, sent_at=null, send_at populated
            ✅ Student view (before): Scheduled notification correctly NOT visible to students yet
            ✅ Admin view: Admin can see scheduled notification with sent=false in GET /admin/notifications
            
            Scenario 4 - Scheduler fires within budget:
            ✅ Scheduler fires: After waiting 130s (send_at + 40s), notification appeared in student list on first poll attempt
            ✅ Admin verification: Admin list shows sent=true and sent_at populated (2026-07-03T18:01:00.740522+00:00)
            
            Scenario 5 - Bad payloads:
            ✅ Invalid send_at: POST with send_at="not-a-date" correctly rejected with 400 and error message mentioning ISO 8601
            ✅ Past send_at: POST with send_at=(now-60s) correctly treated as immediate with sent=true
            
            Scenario 6 - Scheduler robustness across restart:
            ✅ Create scheduled: Notification created with send_at=(now+60s)
            ✅ Backend restart: Successfully restarted backend, came up within 10s
            ✅ Scheduler restart: Backend logs confirm "Notification scheduler started (interval=30s)"
            ✅ Scheduler pickup: After restart, scheduler picked up and fired the notification successfully
            
            Key findings:
            - All 6 scenarios with 14 sub-tests passed successfully
            - Scheduler polls every 30s as configured (NOTIF_SCHEDULER_INTERVAL_SEC=30)
            - Scheduler survives backend restarts and picks up pending notifications
            - Default template endpoint correctly restricted to admin role
            - Backward compatibility maintained (immediate send works without send_at)
            - Proper validation of send_at field (ISO 8601 format required)
            - Students correctly filtered from seeing sent=false notifications
            - All timestamps properly populated (sent_at set when notification fires)
            
            No issues found. Implementation is production-ready.

frontend:
  - task: "Admin scheduling composer + default template + student list"
    implemented: true
    working: "NA"
    file: "/app/frontend/app/notifications.tsx, /app/frontend/src/api/client.ts"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            Rebuilt `/app/frontend/app/notifications.tsx`:
              - Admins see composer with default title+body pre-filled
                (fetched from GET /admin/notifications/default-template with a
                constant fallback if the request fails).
              - "Reset to default" link restores the default text.
              - Delivery segmented control: "Send now" | "Schedule for later"
              - Uses @react-native-community/datetimepicker (native date +
                time pickers). Preserves date/time when the other is changed.
              - Validates future-time >= 1 min before scheduling.
              - When Send now → posts without send_at (immediate push).
              - When Schedule → posts with send_at = ISO datetime; backend
                scheduler will fire at the chosen time.
              - Scheduled-but-not-yet-fired notifications show a "Scheduled"
                pill in the admin list. Students never see these until
                they actually fire.
              - Push notification handling was already wired
                (`registerForPush` in AuthContext + tap handler in _layout).
              - No change needed to NotifBell (30s polling with unread badge).

metadata:
  created_by: "main_agent"
  version: "1.1"
  test_sequence: 1
  run_ui: false

test_plan:
  current_focus: []

###############################################################################
# NEW FEATURE — Edit/Cancel scheduled notifications + Push production readiness
###############################################################################

backend:
  - task: "Edit and cancel scheduled notifications (PATCH + DELETE /admin/notifications/{id})"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            Added:
              - PATCH /api/admin/notifications/{nid} — admins edit an unsent
                (sent=false) notification's title, body, and/or send_at
                (must be future). 404 if not found or wrong hostel. 400 if
                already sent. 400 if send_at is malformed or in the past.
              - DELETE /api/admin/notifications/{nid} — 204 on success.
                Works for both scheduled (unsent) and already-sent items
                (admin can clear history). 404 if not found or wrong hostel.
        - working: true
          agent: "testing"
          comment: |
            ✅ ALL 11 SCENARIOS PASSED - Comprehensive backend testing completed:
            
            Scenario 1 (PATCH title + body only): PASS
            - Created scheduled notification (send_at = now + 5 min)
            - PATCH with {"title":"Edited title","body":"edited body"} → 200 OK
            - Verified via GET /admin/notifications: title/body updated, sent=false unchanged
            
            Scenario 2 (PATCH send_at to new future time): PASS
            - Created scheduled notification
            - PATCH with {"send_at": now + 15 min} → 200 OK
            - Response includes new send_at and scheduled_for (date part of send_at)
            
            Scenario 3 (PATCH with send_at in the past): PASS
            - PATCH with {"send_at": now - 60s} → 400 with message "send_at must be in the future for a scheduled notification."
            
            Scenario 4 (PATCH with malformed send_at): PASS
            - PATCH with {"send_at": "not-a-date"} → 400 with message "Invalid send_at (use ISO 8601 datetime)"
            
            Scenario 5 (Cross-hostel isolation): PASS
            - Created notification with original admin (Test Hostel)
            - Registered new admin under "Other Hostel" (email OTP verified via backend logs)
            - PATCH /admin/notifications/{NID} with OTHER_ADMIN_TOKEN → 404
            - DELETE /admin/notifications/{NID} with OTHER_ADMIN_TOKEN → 404
            - Original admin verified NID still exists in GET /admin/notifications
            
            Scenario 6 (Cannot edit already-sent notifications): PASS
            - Created notification with send_at = now - 60s → sent=true
            - PATCH with {"title":"nope"} → 400 with message "This notification has already been sent and can't be edited."
            
            Scenario 7 (DELETE scheduled): PASS
            - DELETE /admin/notifications/{NID} → 204
            - GET /admin/notifications → NID not in list
            - DELETE /admin/notifications/{NID} again → 404
            
            Scenario 8 (DELETE already-sent): PASS
            - Created notification with sent=true
            - DELETE /admin/notifications/{NID2} → 204
            - GET /admin/notifications → NID2 not in list
            
            Scenario 9 (Auth): PASS
            - PATCH with STUDENT_TOKEN → 403 (require_admin)
            - DELETE with STUDENT_TOKEN → 403
            - PATCH with no Authorization header → 401
            - DELETE with no Authorization header → 401
            
            Scenario 10 (Student view unaffected across edits): PASS
            - Created scheduled notification (NID3) with send_at = now + 5 min
            - GET /student/notifications → NID3 NOT in items (unsent)
            - PATCH NID3's body via ADMIN_TOKEN → 200 OK
            - GET /student/notifications → NID3 still NOT in items
            - DELETE NID3 → 204
            - GET /student/notifications → NID3 still not present
            
            Scenario 11 (Empty PATCH): PASS
            - Created scheduled notification (NID4)
            - PATCH with body {} → 400 "No changes provided"
            - DELETE NID4 → 204
            
            Key findings:
            - All 11 scenarios with 11 sub-tests passed successfully (100% pass rate)
            - PATCH endpoint correctly validates:
              * Only unsent notifications can be edited (sent=false)
              * send_at must be valid ISO 8601 datetime
              * send_at must be in the future
              * At least one field must be provided (no empty updates)
            - DELETE endpoint works for both scheduled and sent notifications
            - Cross-hostel isolation working correctly (404 for wrong hostel)
            - Auth enforcement working (403 for non-admin, 401 for no token)
            - Student view correctly filters out unsent notifications
            - Single-device session enforcement active (reused existing tokens)
            
            Test credentials used from /app/memory/test_credentials.md:
            - Admin: admin_test_1783097886@example.com
            - Student: student_test_1783097886@example.com
            - New admin for cross-hostel test: other_admin_1783102942@example.com (Other Hostel)
            
            Note: Temporarily disabled SMTP during testing to capture OTPs from backend logs for new admin registration. SMTP re-enabled after testing.
            
            No issues found. Implementation is production-ready.

frontend:
  - task: "Edit/Cancel scheduled notification UI + Push production readiness"
    implemented: true
    working: "NA"
    file: "/app/frontend/app/notifications.tsx, /app/frontend/src/api/client.ts"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            - Admin notification cards for scheduled (unsent) items now show
              "Edit" and "Cancel" chip buttons.
            - Tapping "Edit" loads the item into the composer with
              scheduleMode=later, prefilled title/body/send_at; the composer
              shows an "Editing scheduled notification" badge. The action
              button changes to "Save & reschedule for {when}" or
              "Save changes".
            - Tapping "Cancel" opens a native Alert confirmation → on
              confirm calls DELETE, removes locally, and shows success toast.
            - Push production readiness confirmed by audit against playbook:
                * setNotificationHandler + setNotificationChannelAsync at
                  module scope (Platform-guarded), tap listeners + cold-start
                  handler in _layout.tsx.
                * getDevicePushTokenAsync() (not Expo push token) → POST to
                  /api/register-push via backend relay.
                * app.json has expo-notifications plugin, POST_NOTIFICATIONS
                  Android permission, and googleServicesFile pointing to
                  /app/frontend/google-services.json (real Firebase project
                  messmate-c92ca already present).
              EMERGENT_PUSH_KEY stays as "placeholder" — the deployment
              pipeline swaps in the real key at Publish/Deploy time.

metadata:
  created_by: "main_agent"
  version: "1.2"
  test_sequence: 3
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    - agent: "main"
      message: |
        Test PATCH + DELETE on /api/admin/notifications/{id}. Reuse existing
        credentials in /app/memory/test_credentials.md. Base URL:
        http://localhost:8001/api

        Setup — with admin token, POST /admin/notifications with:
          { "title":"To edit","body":"orig body","audience":"all",
            "send_at": (now + 5 minutes).toISOString() }
        → capture the returned `id` (call it NID).

        1) PATCH title + body:
           PATCH /admin/notifications/{NID}
             { "title":"Edited title","body":"edited body" }
           → 200 with updated fields. Verify by GET /admin/notifications:
           the item exists with the new title/body, still sent=false.

        2) PATCH send_at to a NEW future time:
           PATCH /admin/notifications/{NID}
             { "send_at": (now + 15 minutes).toISOString() }
           → 200 with the new send_at and updated scheduled_for (date part).

        3) PATCH with send_at in the past → 400
           (e.g., (now - 60 seconds).toISOString()).

        4) PATCH with malformed send_at "not-a-date" → 400.

        5) Ownership isolation:
           - Create/log in as an admin for a DIFFERENT hostel.
           - Attempt PATCH /admin/notifications/{NID} → 404 (not found in
             that hostel).
           - Attempt DELETE /admin/notifications/{NID} → 404.
           - Original admin still owns the notification.

        6) Cannot edit already-sent notifications:
           - Create another notification with send_at = (now - 60s) so it
             saves as sent=true immediately. Capture id (NID2).
           - PATCH /admin/notifications/{NID2} with any body → 400 with
             message about already sent.

        7) DELETE (cancel) scheduled:
           - DELETE /admin/notifications/{NID} → 204.
           - GET /admin/notifications → item is gone.
           - DELETE again → 404.

        8) DELETE already-sent notifications:
           - DELETE /admin/notifications/{NID2} → 204. (Admin can clear
             history — this is intentional.)
           - GET /admin/notifications → NID2 is gone.

        9) Auth:
           - PATCH and DELETE with a student token → 403.
           - PATCH/DELETE with no token → 401.

        10) Student view unaffected:
            - Create a NEW scheduled notification with send_at = now + 5m.
            - GET /student/notifications → it should NOT appear (unsent).
            - PATCH its body via admin. GET /student/notifications → still
              should NOT appear (still unsent).
            - DELETE it. GET /student/notifications → still not appearing.

        Report each with actual HTTP status codes + relevant response
        snippets, and update this file under the corresponding task's
        status_history.

  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    - agent: "main"
      message: |
        Please test the new scheduled-notifications backend end-to-end. Use
        the existing test credentials in /app/memory/test_credentials.md.
        Base URL: http://localhost:8001/api

        1) GET /admin/notifications/default-template with admin bearer token
           → 200 with { "title": "Help reduce food waste — mark your meals",
                        "body": <non-empty string mentioning participation
                                 and reducing food waste> }
           (Non-admin must get 403.)

        2) Immediate send (unchanged behaviour):
           POST /admin/notifications with body:
             { "title":"Test now","body":"Hello","audience":"all" }
           → 201, response has sent=true, sent_at is set, send_at is null.
           Then GET /student/notifications with a student token → the new
           item is present with read=false and no "Scheduled" state.

        3) Scheduled future notification:
           POST /admin/notifications with body containing:
             send_at = (now + 90 seconds).toISOString()
           → 201 with sent=false, sent_at=null, send_at populated.
           Verify GET /student/notifications does NOT return the item yet.
           Verify GET /admin/notifications returns the item with sent=false.

        4) Wait ~40 seconds (scheduler polls every 30s), then poll student
           notifications again. Within ≤65 seconds of the send_at time, the
           item should now appear in /student/notifications with sent=true,
           and admin list should now show sent=true + sent_at populated.

        5) Bad payloads:
           - POST /admin/notifications with send_at = "not-a-date" → 400.
           - POST with send_at in the past → treated as immediate (sent=true).

        6) Scheduler robustness:
           - Register a scheduled notification then restart backend (`sudo
             supervisorctl restart backend`). The scheduler should still pick
             it up on the next startup poll if the time has arrived.

        Report each with actual response snippets. Update this file with
        findings.
    - agent: "testing"
      message: |
        ✅ BACKEND TESTING COMPLETE - All scenarios passed successfully!
        
        Executed comprehensive test suite covering all 6 scenarios from the review request:
        - Default template endpoint (admin-only access)
        - Immediate send (backward compatibility)
        - Scheduled future notifications
        - Scheduler firing within budget
        - Bad payload validation
        - Scheduler robustness across backend restart
        
        All 14 sub-tests passed (100% success rate). The scheduled notifications
        feature is working correctly:
        - Scheduler polls every 30s and fires notifications on time
        - Students only see notifications after they've been sent
        - Admin can see all notifications including scheduled ones
        - Proper validation and error handling for send_at field
        - Scheduler survives backend restarts
        
        Test credentials used from /app/memory/test_credentials.md:
        - Admin: admin_test_1783097886@example.com
        - Student: student_test_1783097886@example.com
        
        Backend logs confirm scheduler is running: "Notification scheduler started (interval=30s)"
        
        No issues found. Implementation is production-ready.

    - agent: "testing"
      message: |
        ✅ BACKEND TESTING COMPLETE - PATCH + DELETE endpoints working perfectly!
        
        Executed comprehensive test suite covering all 11 scenarios from the review request:
        1. PATCH title + body only
        2. PATCH send_at to new future time
        3. PATCH with send_at in the past (validation)
        4. PATCH with malformed send_at (validation)
        5. Cross-hostel isolation
        6. Cannot edit already-sent notifications
        7. DELETE scheduled notification
        8. DELETE already-sent notification
        9. Auth enforcement (403 for non-admin, 401 for no token)
        10. Student view unaffected across edits
        11. Empty PATCH (validation)
        
        All 11 scenarios passed (100% success rate). Key findings:
        - PATCH endpoint correctly validates unsent-only editing
        - send_at validation working (ISO 8601 format, future time required)
        - DELETE works for both scheduled and sent notifications
        - Cross-hostel isolation enforced (404 for wrong hostel)
        - Auth enforcement working correctly
        - Student view correctly filters unsent notifications
        - Empty PATCH body rejected with "No changes provided"
        
        Test credentials used from /app/memory/test_credentials.md:
        - Admin: admin_test_1783097886@example.com
        - Student: student_test_1783097886@example.com
        - New admin for cross-hostel test: other_admin_1783102942@example.com (Other Hostel)
        
        Note: Temporarily disabled SMTP during testing to capture OTPs from backend logs.
        SMTP re-enabled after testing completed.
        
        No issues found. Implementation is production-ready.
