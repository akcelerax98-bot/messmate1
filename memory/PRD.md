# MessMate — Product Requirements Document

## Overview
MessMate is a food-waste reduction and meal-planning app for hostel/college/PG messes. Multi-tenant by hostel — each hostel's admin only sees their own students' data.

## Roles
1. Student / User
2. Admin (mess manager / warden)

## Tabs (fixed)
- Student (4): Today / Menu / Wastage / Settings
- Admin (5): Students Status / Dashboard / Wastage & Calculation / Necessary Info / Settings

## Tech
- **Backend:** FastAPI + Motor (MongoDB) + bcrypt + JWT
- **Frontend:** Expo Router + react-native-safe-area-context + @expo/vector-icons
- **Theme:** Light + Dark + System, Apple-style premium, green sustainability accent (#22C55E), floating glass tab bar

## Authentication (2-step)
1. `POST /api/auth/login` with `{mobile, password, institution_or_hostel_name}` → returns `challenge + mock_otp + user_preview`.
2. `POST /api/auth/verify-login-otp` with `{challenge, otp}` → returns access_token.
- OTP is MOCKED at `123456`. Real SMS (Twilio / MSG91) will be wired before publish.
- Push notification token capture is implemented; dispatch is MOCKED — needs deploy + google-services.json.

## Multi-tenant (hostel scoping)
Every domain doc (`menus`, `daily_plans`, `menu_reactions`, `feedback`, `wastage_records`, `necessary_info`, `app_settings`, `notifications`) carries `hostel: <institution_or_hostel_name>`. Indexes are unique per `(hostel, ...)`. Admin queries and student reads are scoped by the JWT user's hostel. Verified by 23-test isolation suite (iteration 6).

## Data Model summary
- **users** — id, full_name, mobile_or_user_id, institution_or_hostel_name (uniq pair with mobile), room_number, password_hash, push_token, role, approval_status, timestamps
- **menus** — `(hostel, day)` unique; B/L/D items + custom_question per slot
- **daily_plans** — `(student_id, date)` unique; hostel; per-meal status/items/reason/custom_answer
- **menu_reactions** — `(student_id, day, meal_type)` unique; hostel; like/dislike/no_response
- **feedback** — anonymous; admin projection excludes student_id
- **wastage_records** — `(hostel, date)` unique; per-meal item arrays + aggregate kg + per-meal loss + item_loss_total + **manual_total_cost** + total_loss
- **necessary_info** — `(hostel, item_name, meal_type)` unique; qty/person + price/unit
- **app_settings** — `hostel` unique; defaults
- **notifications** — hostel; title/body/type/audience/recipient_id/scheduled_for/read_by

## Notifications
- Admin can send (a) custom announcements to all students of the hostel, (b) tomorrow's menu reminder (auto-generated from the next-day weekday menu).
- Students see in-app feed (modal route `/notifications`) with bell in home + settings; unread badge auto-refreshes every 30s.
- Real push dispatch deferred to post-deploy (token already captured server-side).

## UI System (iteration 6)
- `ThemeProvider` exposes `useTheme()` with light + dark palettes (mode persists per device); 3-way toggle (Light / Dark / System) lives in both Settings tabs.
- Floating glass pill tab bar at the bottom, theme-aware.
- Apple-inspired typography hierarchy (largeTitle / title1-2 / headline / body / caption).

## Build Progress
- ✅ Part 1 — Auth & role-based entry
- ✅ Part 2 — Student side (Today / Menu / Wastage / Settings)
- ✅ Part 3 — Admin side (Students / Dashboard / Wastage & Calculation / Necessary Info / Settings)
- ✅ Iteration 6 — Hostel scoping (multi-tenant), manual wastage cost, in-app notifications, 2-step OTP login, theme system (light + dark + system) + floating glass tab bar
- Tests: 23/23 new pytest pass; iteration 6 frontend flows verified

## Open / Next
- Real SMS provider integration (Twilio/MSG91) before publish
- Push notifications full dispatch (after `google-services.json` + deploy)
- Migrate legacy `test_auth.py` / `test_student.py` to 2-step login helper
- Optional: address React Native Web `shadow*` deprecation warnings
- Optional: expected wastage prediction (after ≥30 days of real data)
