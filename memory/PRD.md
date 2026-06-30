# MessMate — Product Requirements Document

## Overview
**MessMate** is a food-waste reduction and meal-planning app for hostel messes, college messes, PG messes, canteens, and institutional dining. It collects reliable student meal data and converts it into actionable planning information for the admin (mess manager / warden), reducing food waste, calculating loss/savings, and improving transparency.

## Roles (only two)
1. **Student / User** — marks meals, picks preferences, sees wastage transparency, gives anonymous feedback.
2. **Admin** — mess manager / warden / planner. Approves students, plans cook quantity, records actual wastage.

## Tab structure
**Student (4 tabs):** Today / Menu / Wastage / Settings
**Admin (5 tabs):** Students Status / Dashboard / Wastage & Calculation / Necessary Info / Settings

## Core concepts
- **ON / OFF** — student tells whether they will eat breakfast / lunch / dinner today.
- **Preference** — student taps any number of menu items to mark them as preferred (multi-select chips).
- **Like / Dislike** — feedback on menu satisfaction only (independent from ON/OFF). Shown to admin as %.
- **Anonymous feedback** — placed at end of Home tab; admin never sees the student's name.
- **Approval flow** — new student accounts default to `pending` and must be approved by admin.
- **Admin Dashboard** — uses (eating count) × (item-preference share) × (qty-per-person from Necessary Info) to suggest cook quantity per item.
- **Wastage & Calculation** — admin enters actual wastage. `Loss = Wastage qty × Price/unit`. `Saved = Avg Loss − Current Loss`.
- **Ignored for now** — Expected/predicted wastage (added later once historical data exists).

## Tech Stack
- **Frontend:** Expo Router (React Native) + react-native-safe-area-context + @expo/vector-icons (Feather)
- **Backend:** FastAPI + Motor (MongoDB async) + Passlib (bcrypt) + python-jose (JWT)
- **Storage:** MongoDB + `@/src/utils/storage` on device for JWT
- **Design:** Apple-style premium, green sustainability theme (`#248243`)

## Authentication
- Mobile/User ID + Password with JWT (Bearer).
- **OTP is MOCKED** — `/api/auth/request-otp` returns `mock_otp: 123456`. Real SMS provider (Twilio/MSG91) will be integrated before deploy.
- 4 demo accounts seeded under "Demo Hostel" (see `/app/memory/test_credentials.md`).

## Backend API
### Auth
- `GET  /api/`
- `POST /api/auth/register-student`
- `POST /api/auth/login`
- `GET  /api/auth/me`
- `POST /api/auth/request-otp` — MOCKED
- `POST /api/auth/verify-otp` — MOCKED

### Student (requires approved-student JWT — admin/pending/blocked get 403)
- `GET  /api/student/meta` — reasons list + day names
- `GET  /api/student/today` — today's menu + the student's existing daily plan (if any)
- `PUT  /api/student/today` — upsert today's plan (status + items + reason + custom answer per meal)
- `POST /api/student/feedback` — anonymous feedback (`anonymous=true`)
- `GET  /api/student/menu/week` — weekly menu with student's reactions
- `GET  /api/student/menu/month` — placeholder: weekly menu × 4 weeks
- `PUT  /api/student/menu/reaction` — upsert like/dislike for (day, meal_type)
- `GET  /api/student/wastage?range=7|30|90&meal=all|breakfast|lunch|dinner` — series + summary (today / yesterday / last week same day)

## Data Model
### `users`
`id, full_name, mobile_or_user_id (unique), institution_or_hostel_name, room_number, password_hash, role (student|admin), approval_status (pending|approved|rejected_or_blocked), created_at, updated_at`

### `menus`  (one doc per weekday — seeded recurring weekly menu)
`day (unique), breakfast_items[], lunch_items[], dinner_items[], breakfast_custom_question, lunch_custom_question, dinner_custom_question, created_at, updated_at`

### `daily_plans`  (unique on student_id + date)
`id, student_id, date, breakfast{status, selected_items, reason_if_off, custom_answer}, lunch{...}, dinner{...}, created_at, updated_at`
→ admin will aggregate eating-count, item-wise demand, reason counts, custom-answer counts.

### `menu_reactions`  (unique on student_id + day + meal_type)
`id, student_id, day, meal_type, reaction (like|dislike|no_response), created_at, updated_at`
→ admin will compute like/dislike % per meal.

### `feedback`
`id, student_id, date, feedback_text, anonymous=true, created_at`
→ admin sees only `feedback_text` + `date` (never `student_id`).

### `wastage_records`  (unique on date — seeded with 95 days of synthetic data)
`id, date, breakfast_wastage_kg, lunch_wastage_kg, dinner_wastage_kg, created_at`
→ later edited by admin Wastage & Calculation.

## Build Progress

### ✅ Part 1 — Auth & Role-Based Entry (DONE)
- Welcome / Student login + register / Admin login
- Pending + Blocked screens
- 4 student / 5 admin placeholder tabs
- JWT, demo seed accounts, idempotent on startup
- Session persistence + role-based routing

### ✅ Part 2 — Complete Student Side (DONE)
- **Home / Today's Plan** — greeting, date, menu summary, B/L/D cards with ON/OFF + multi-select preference chips + reason picker (OFF) with "Other" text input + custom question chips. Anonymous feedback at the bottom. Save button persists per-day via upsert.
- **Menu tab** — Weekly / Monthly segmented view, day cards with B/L/D items and round Like/Dislike buttons (optimistic UI, persists per student+day+meal).
- **Wastage tab** — today total + B/L/D breakdown, yesterday card, last-week-same-day card, bar chart with range (7/30/90) and meal (all/B/L/D) filters.
- **Settings tab** — profile card (avatar + name + institution + room badge), profile rows, placeholders for change password / notifications / language, sign out.
- All endpoints role-guarded (approved students only). Tests: 36/36 backend pass (15 auth + 22 student incl. wastage summary regression guard). Frontend flows verified.

### ⏳ Part 3+ (awaiting instructions)
- Admin Students Status (approve/reject, see eating counts, reasons, anonymous feedback, like/dislike %)
- Admin Necessary Info (menu plan editor, qty-per-person, price-per-unit, custom Qs CRUD)
- Admin Dashboard (suggested cook quantity calculations)
- Admin Wastage & Calculation (record real wastage, loss/savings math)
- Admin Settings
- Real SMS OTP integration before deploy
