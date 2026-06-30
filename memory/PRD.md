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

## Backend API (Part 1)
- `GET  /api/` — health
- `POST /api/auth/register-student` — creates student with `approval_status=pending`
- `POST /api/auth/login` — returns `access_token` + user (including `role` & `approval_status`)
- `GET  /api/auth/me` — current user (Bearer)
- `POST /api/auth/request-otp` — MOCKED
- `POST /api/auth/verify-otp` — MOCKED (accepts only `123456`)

## Data Model (`users` collection)
`id`, `full_name`, `mobile_or_user_id` (unique), `institution_or_hostel_name`, `room_number`, `password_hash`, `role` (`student|admin`), `approval_status` (`pending|approved|rejected_or_blocked`), `created_at`, `updated_at`.

## Build Progress

### ✅ Part 1 — Authentication & Role-Based Entry (DONE)
- Welcome page with two role cards
- Student login + Student registration (with OTP placeholder block)
- Admin login (institution + user ID + password)
- Pending approval screen + Blocked screen
- 4 placeholder student tabs + 5 placeholder admin tabs
- JWT auth, demo seed accounts, idempotent on startup
- Session persistence + role-based routing
- All flows verified by testing subagent (14/14 backend + full frontend pass)

### ⏳ Upcoming parts (awaiting instructions)
- Part 2+: Today's Plan (ON/OFF + preferences + feedback), Menu management, Wastage transparency, Admin Dashboard math, Necessary Info, Settings, Wastage & Calculation, real SMS OTP integration.
