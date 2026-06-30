# MessMate — Product Requirements Document

## Overview
**MessMate** is a food-waste reduction and meal-planning app for hostel/college/PG messes, canteens, and institutional dining. It collects reliable student meal data and converts it into actionable planning info for the admin (mess manager / warden), reducing food waste, calculating loss/savings, and improving transparency.

## Roles (only two)
1. **Student / User** — marks meals, picks preferences, sees wastage transparency, gives anonymous feedback.
2. **Admin** — approves students, plans cook quantity, records actual wastage, configures defaults.

## Tab structure
**Student (4):** Today / Menu / Wastage / Settings
**Admin (5):** Students Status / Dashboard / Wastage & Calculation / Necessary Info / Settings

## Core concepts
- **ON / OFF** — student tells whether they will eat B/L/D today.
- **Preference** — student multi-selects menu items they prefer (chip tap).
- **Like / Dislike** — menu satisfaction, independent from ON/OFF, shown to admin as %.
- **Anonymous feedback** — at end of Home tab; admin sees only feedback_text + date.
- **Approval flow** — new student accounts default to `pending`; admin approves/rejects.
- **Admin Dashboard** — `Suggested Quantity = item preference count × qty/person` (g→kg, ml→litres auto-conversion). Warnings when menu / necessary_info is missing.
- **Wastage & Calculation** — admin enters per-item wastage. `Loss = Quantity × Price/unit`. `Saved = Avg 30d loss − Current loss`.
- **Ignored for now** — Expected/predicted wastage prediction (later).

## Tech Stack
- **Frontend:** Expo Router (React Native) + react-native-safe-area-context + @expo/vector-icons
- **Backend:** FastAPI + Motor (MongoDB) + Passlib (bcrypt) + python-jose (JWT)
- **Storage:** MongoDB + `@/src/utils/storage` on device for JWT
- **Design:** Apple-style premium, green sustainability theme (`#248243`)

## Authentication
- Mobile/User ID + Password (JWT Bearer).
- **OTP MOCKED** — `/api/auth/request-otp` returns `mock_otp: 123456`. Real SMS provider to be integrated before deploy.
- Demo accounts seeded under "Demo Hostel" (see `/app/memory/test_credentials.md`).

## Backend API
### Auth
- `GET  /api/`, `POST /auth/register-student`, `POST /auth/login`, `GET /auth/me`, `POST /auth/request-otp` MOCKED, `POST /auth/verify-otp` MOCKED

### Student (approved-student JWT)
- `GET /student/meta` · `GET/PUT /student/today` · `POST /student/feedback`
- `GET /student/menu/week` · `GET /student/menu/month` · `PUT /student/menu/reaction`
- `GET /student/wastage?range=&meal=`

### Admin (admin JWT)
- Students: `GET /admin/students/summary` · `GET /admin/students?status=` · `POST /admin/students/:id/approve` · `POST /admin/students/:id/reject`
- Today/Feedback: `GET /admin/today` · `GET /admin/feedback?days=`
- Dashboard: `GET /admin/dashboard`
- Necessary Info CRUD: `GET/POST /admin/necessary-info` · `PUT/DELETE /admin/necessary-info/:id`
- Menus: `GET /admin/menus` · `PUT /admin/menus/:day`
- Wastage: `GET /admin/wastage/today` · `GET /admin/wastage/trend?range=&meal=` · `PUT /admin/wastage/:date`
- Settings: `GET/PUT /admin/settings`

## Data Model
- `users` — id, full_name, mobile_or_user_id (unique), institution_or_hostel_name, room_number, password_hash, role, approval_status, timestamps
- `menus` — day (unique Mon..Sun), breakfast/lunch/dinner items + custom_question per slot
- `daily_plans` — unique (student_id, date); per-meal status/items/reason/custom_answer
- `menu_reactions` — unique (student_id, day, meal_type); like/dislike/no_response
- `feedback` — anonymous=true; admin projection excludes student_id
- `wastage_records` — unique date; per-meal item arrays + aggregate kg + per-meal loss + total_loss
- `necessary_info` — unique (item_name, meal_type); qty/person + price/unit
- `app_settings` — singleton id="app"; default_meal_state, default_like_dislike_state, default_preference_state, notifications_enabled, language

## Build Progress
- ✅ **Part 1** — Auth & role-based entry (welcome, login, register, pending/blocked, role tabs)
- ✅ **Part 2** — Complete Student side (Today's Plan with ON/OFF + preference chips + reasons + custom Qs + anonymous feedback; Menu weekly/monthly with Like/Dislike; Wastage transparency with range/meal filters; Settings with profile + sign out)
- ✅ **Part 3** — Complete Admin side
  - **Students Status** — summary tiles, pending approval list with Approve/Reject, today's eating tiles, meal switcher (B/L/D) with eating/not-eating numbers, like/dislike bar, item-pref demand bars, reason counts, custom-answer counts, anonymous feedback (7 days)
  - **Dashboard** — per-meal blocks with eating count + items (item, preference_count, qty/person, suggested quantity with g→kg / ml→litres conversion), missing-info warnings, most/least demanded highlights
  - **Wastage & Calculation** — today tiles (wastage kg + loss + 30d avg + saved-vs-avg), B/L/D breakdown, yesterday & last-week cards, item-level entry editor per meal (server computes loss using necessary_info prices), trend chart with wastage/saved toggle + range (7/30/90) + meal filter
  - **Necessary Info** — Menu / Qty&Price / Questions sub-tabs with day picker; weekday menu items editor, item CRUD (qty/person + unit + price/unit + price_unit), custom-question editor per meal slot
  - **Settings** — admin profile, 3 default-state Segmented controls (meal/like-dislike/preference) — save-on-change, notifications toggle, language placeholder, Sign out

**Seed coverage** (idempotent on startup): 1 admin + 3 demo students (incl. pending, blocked) + 28 extra approved + 4 pending + 4 blocked (demopass); 7 weekday menus; today's daily_plans for all approved students with realistic distribution; today's menu reactions; 7 anonymous feedback rows; 95 days of wastage records with computed loss; ~20 necessary_info items per spec.

**Testing**
- 84/84 backend pytest pass (Parts 1+2+3 combined)
- Frontend flows verified by testing_agent for every admin screen
- Bug fixed during testing: `PUT /admin/settings` MongoDB `$set/$setOnInsert` path conflict — fixed + regression test added

## Next Steps (future)
- Real SMS OTP provider (Twilio / MSG91) before publish
- Expected wastage prediction (after collecting ≥30 days of real wastage data)
- Optional: silence RN Web deprecation warnings (`shadow*` → `boxShadow`)
