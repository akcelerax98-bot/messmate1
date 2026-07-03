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
