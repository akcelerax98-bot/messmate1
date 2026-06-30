"""MessMate backend — Auth + Student side + Admin side."""

import logging
import os
import random
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
users_col = db["users"]
menus_col = db["menus"]
daily_plans_col = db["daily_plans"]
menu_reactions_col = db["menu_reactions"]
feedback_col = db["feedback"]
wastage_col = db["wastage_records"]
necessary_info_col = db["necessary_info"]
settings_col = db["app_settings"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

app = FastAPI(title="MessMate API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("messmate")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
Role = Literal["student", "admin"]
ApprovalStatus = Literal["pending", "approved", "rejected_or_blocked"]
MealStatus = Literal["ON", "OFF"]
MealType = Literal["breakfast", "lunch", "dinner"]
Reaction = Literal["like", "dislike", "no_response"]
Unit = Literal["pieces", "grams", "kg", "ml", "litres"]


class StudentRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    mobile_or_user_id: str = Field(..., min_length=3, max_length=60)
    institution_or_hostel_name: str = Field(..., min_length=1, max_length=120)
    room_number: str = Field(..., min_length=1, max_length=40)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    mobile_or_user_id: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    institution_or_hostel_name: Optional[str] = None


class UserPublic(BaseModel):
    id: str
    full_name: str
    mobile_or_user_id: str
    institution_or_hostel_name: str
    room_number: Optional[str] = None
    role: Role
    approval_status: ApprovalStatus
    created_at: str
    updated_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class CustomQuestion(BaseModel):
    text: str
    options: List[str]


class MealPlanInput(BaseModel):
    status: Optional[MealStatus] = None
    selected_items: List[str] = Field(default_factory=list)
    reason_if_off: Optional[str] = None
    custom_answer: Optional[str] = None


class DailyPlanUpsert(BaseModel):
    date: Optional[str] = None
    breakfast: MealPlanInput = Field(default_factory=MealPlanInput)
    lunch: MealPlanInput = Field(default_factory=MealPlanInput)
    dinner: MealPlanInput = Field(default_factory=MealPlanInput)


class ReactionUpsert(BaseModel):
    day: str
    meal_type: MealType
    reaction: Reaction


class FeedbackInput(BaseModel):
    feedback_text: str = Field(..., min_length=1, max_length=2000)


class MenuUpsert(BaseModel):
    breakfast_items: List[str] = Field(default_factory=list)
    lunch_items: List[str] = Field(default_factory=list)
    dinner_items: List[str] = Field(default_factory=list)
    breakfast_custom_question: Optional[CustomQuestion] = None
    lunch_custom_question: Optional[CustomQuestion] = None
    dinner_custom_question: Optional[CustomQuestion] = None


class NecessaryItemInput(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=80)
    meal_type: MealType
    quantity_per_person: float = Field(..., ge=0)
    unit: Unit
    price_per_unit: float = Field(..., ge=0)
    price_unit: Unit  # the unit corresponding to price_per_unit (e.g., kg if price is ₹50/kg)


class WastageItemInput(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=80)
    quantity: float = Field(..., ge=0)
    unit: Unit
    price_per_unit: Optional[float] = None  # override; else looked up from necessary_info
    price_unit: Optional[Unit] = None


class WastageUpsert(BaseModel):
    breakfast_items: List[WastageItemInput] = Field(default_factory=list)
    lunch_items: List[WastageItemInput] = Field(default_factory=list)
    dinner_items: List[WastageItemInput] = Field(default_factory=list)


class AppSettingsInput(BaseModel):
    default_meal_state: Optional[Literal["ON", "OFF"]] = None
    default_like_dislike_state: Optional[Reaction] = None
    default_preference_state: Optional[
        Literal["none", "all", "previous"]
    ] = None
    notifications_enabled: Optional[bool] = None
    language: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
REASONS = [
    "Going home",
    "Eating outside",
    "Not hungry",
    "Class/Event",
    "Sick",
    "Don't like today's menu",
    "Other",
]

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(payload: dict) -> str:
    to_encode = payload.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def to_public(doc: dict) -> UserPublic:
    return UserPublic(
        id=doc["id"],
        full_name=doc["full_name"],
        mobile_or_user_id=doc["mobile_or_user_id"],
        institution_or_hostel_name=doc["institution_or_hostel_name"],
        room_number=doc.get("room_number"),
        role=doc["role"],
        approval_status=doc["approval_status"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def day_of_week(d: date) -> str:
    return DAYS[d.weekday()]


def to_kg_equiv(quantity: float, unit: str) -> float:
    """Approximate weight in kg for a wastage display aggregate."""
    if unit == "pieces":
        return quantity * 0.05  # rough 50g per piece
    if unit == "grams":
        return quantity / 1000.0
    if unit == "kg":
        return float(quantity)
    if unit == "ml":
        return quantity / 1000.0
    if unit == "litres":
        return float(quantity)
    return float(quantity)


def normalize_to_price_unit(quantity: float, qty_unit: str, price_unit: str) -> float:
    """Convert a wastage quantity into the unit the price is denominated in."""
    if qty_unit == price_unit:
        return float(quantity)
    pairs = {
        ("grams", "kg"): quantity / 1000.0,
        ("kg", "grams"): quantity * 1000.0,
        ("ml", "litres"): quantity / 1000.0,
        ("litres", "ml"): quantity * 1000.0,
    }
    return pairs.get((qty_unit, price_unit), float(quantity))


def display_quantity(value: float, unit: str) -> Dict[str, Any]:
    """Convert g→kg and ml→l when value is large enough for cleaner display."""
    if unit == "grams" and value >= 1000:
        return {"value": round(value / 1000.0, 2), "unit": "kg"}
    if unit == "ml" and value >= 1000:
        return {"value": round(value / 1000.0, 2), "unit": "litres"}
    return {"value": round(value, 2), "unit": unit}


async def get_user_by_id(user_id: str) -> Optional[dict]:
    return await users_col.find_one({"id": user_id}, {"_id": 0})


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_approved_student(current: dict = Depends(get_current_user)) -> dict:
    if current["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    if current["approval_status"] != "approved":
        raise HTTPException(status_code=403, detail="Student is not approved")
    return current


async def require_admin(current: dict = Depends(get_current_user)) -> dict:
    if current["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current


def project_menu(doc: dict) -> dict:
    return {
        "day": doc["day"],
        "breakfast_items": doc.get("breakfast_items", []),
        "lunch_items": doc.get("lunch_items", []),
        "dinner_items": doc.get("dinner_items", []),
        "breakfast_custom_question": doc.get("breakfast_custom_question"),
        "lunch_custom_question": doc.get("lunch_custom_question"),
        "dinner_custom_question": doc.get("dinner_custom_question"),
    }


def project_plan(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return None
    return {
        "date": doc["date"],
        "breakfast": doc.get("breakfast", {}),
        "lunch": doc.get("lunch", {}),
        "dinner": doc.get("dinner", {}),
        "updated_at": doc.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"app": "MessMate", "status": "ok"}


@api.post("/auth/register-student", response_model=UserPublic, status_code=201)
async def register_student(payload: StudentRegisterRequest):
    existing = await users_col.find_one(
        {"mobile_or_user_id": payload.mobile_or_user_id}, {"_id": 0}
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An account with this mobile number / user ID already exists",
        )

    now = now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "full_name": payload.full_name.strip(),
        "mobile_or_user_id": payload.mobile_or_user_id.strip(),
        "institution_or_hostel_name": payload.institution_or_hostel_name.strip(),
        "room_number": payload.room_number.strip(),
        "password_hash": hash_password(payload.password),
        "role": "student",
        "approval_status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    await users_col.insert_one(doc)
    doc.pop("_id", None)
    return to_public(doc)


@api.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    query: dict = {"mobile_or_user_id": payload.mobile_or_user_id.strip()}
    if payload.institution_or_hostel_name:
        query["institution_or_hostel_name"] = payload.institution_or_hostel_name.strip()

    user = await users_col.find_one(query, {"_id": 0})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        {"sub": user["id"], "role": user["role"], "status": user["approval_status"]}
    )
    return TokenResponse(access_token=token, user=to_public(user))


@api.get("/auth/me", response_model=UserPublic)
async def me(current: dict = Depends(get_current_user)):
    return to_public(current)


@api.post("/auth/request-otp")
async def request_otp_placeholder(mobile_or_user_id: str):
    return {"message": "OTP placeholder — real SMS not sent", "mock_otp": "123456"}


@api.post("/auth/verify-otp")
async def verify_otp_placeholder(mobile_or_user_id: str, otp: str):
    if otp != "123456":
        raise HTTPException(status_code=400, detail="Invalid OTP (mock)")
    return {"message": "OTP verified (mock)"}


# ---------------------------------------------------------------------------
# Student routes
# ---------------------------------------------------------------------------
@api.get("/student/meta")
async def student_meta(_: dict = Depends(require_approved_student)):
    return {"reasons": REASONS, "days": DAYS}


@api.get("/student/today")
async def student_today(current: dict = Depends(require_approved_student)):
    today = today_iso()
    day = day_of_week(date.fromisoformat(today))
    menu_doc = await menus_col.find_one({"day": day}, {"_id": 0})
    plan_doc = await daily_plans_col.find_one(
        {"student_id": current["id"], "date": today}, {"_id": 0}
    )
    return {
        "date": today,
        "day": day,
        "menu": project_menu(menu_doc) if menu_doc else None,
        "plan": project_plan(plan_doc),
    }


@api.put("/student/today")
async def upsert_today_plan(
    payload: DailyPlanUpsert,
    current: dict = Depends(require_approved_student),
):
    target_date = payload.date or today_iso()
    try:
        date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")

    now = now_iso()
    set_doc = {
        "student_id": current["id"],
        "date": target_date,
        "breakfast": payload.breakfast.model_dump(),
        "lunch": payload.lunch.model_dump(),
        "dinner": payload.dinner.model_dump(),
        "updated_at": now,
    }
    insert_doc = {"id": str(uuid.uuid4()), "created_at": now}
    await daily_plans_col.update_one(
        {"student_id": current["id"], "date": target_date},
        {"$set": set_doc, "$setOnInsert": insert_doc},
        upsert=True,
    )
    saved = await daily_plans_col.find_one(
        {"student_id": current["id"], "date": target_date}, {"_id": 0}
    )
    return {"ok": True, "plan": project_plan(saved)}


@api.post("/student/feedback")
async def post_feedback(
    payload: FeedbackInput, current: dict = Depends(require_approved_student)
):
    now = now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "student_id": current["id"],
        "date": today_iso(),
        "feedback_text": payload.feedback_text.strip(),
        "anonymous": True,
        "created_at": now,
    }
    await feedback_col.insert_one(doc)
    return {"ok": True, "id": doc["id"], "created_at": now}


@api.get("/student/menu/week")
async def student_menu_week(current: dict = Depends(require_approved_student)):
    docs = []
    for d in DAYS:
        m = await menus_col.find_one({"day": d}, {"_id": 0})
        docs.append(
            project_menu(m)
            if m
            else {
                "day": d,
                "breakfast_items": [],
                "lunch_items": [],
                "dinner_items": [],
                "breakfast_custom_question": None,
                "lunch_custom_question": None,
                "dinner_custom_question": None,
            }
        )

    reactions_map: Dict[str, str] = {}
    cursor = menu_reactions_col.find(
        {"student_id": current["id"]},
        {"_id": 0, "day": 1, "meal_type": 1, "reaction": 1},
    )
    async for r in cursor:
        reactions_map[f"{r['day']}:{r['meal_type']}"] = r["reaction"]

    for d in docs:
        d["reactions"] = {
            "breakfast": reactions_map.get(f"{d['day']}:breakfast", "no_response"),
            "lunch": reactions_map.get(f"{d['day']}:lunch", "no_response"),
            "dinner": reactions_map.get(f"{d['day']}:dinner", "no_response"),
        }
    return {"days": docs}


@api.get("/student/menu/month")
async def student_menu_month(current: dict = Depends(require_approved_student)):
    week = await student_menu_week(current)  # type: ignore[arg-type]
    return {"weeks": [{"label": f"Week {i + 1}", "days": week["days"]} for i in range(4)]}


@api.put("/student/menu/reaction")
async def upsert_reaction(
    payload: ReactionUpsert, current: dict = Depends(require_approved_student)
):
    if payload.day not in DAYS:
        raise HTTPException(status_code=400, detail="Invalid day")
    now = now_iso()
    await menu_reactions_col.update_one(
        {
            "student_id": current["id"],
            "day": payload.day,
            "meal_type": payload.meal_type,
        },
        {
            "$set": {"reaction": payload.reaction, "updated_at": now},
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "student_id": current["id"],
                "day": payload.day,
                "meal_type": payload.meal_type,
                "created_at": now,
            },
        },
        upsert=True,
    )
    return {"ok": True, "reaction": payload.reaction}


@api.get("/student/wastage")
async def student_wastage(
    _: dict = Depends(require_approved_student),
    range: int = Query(7, ge=1, le=365),
    meal: Literal["all", "breakfast", "lunch", "dinner"] = Query("all"),
):
    today = date.fromisoformat(today_iso())
    start = today - timedelta(days=range - 1)

    cursor = wastage_col.find(
        {"date": {"$gte": start.isoformat(), "$lte": today.isoformat()}},
        {"_id": 0},
    ).sort("date", 1)
    rows = [r async for r in cursor]

    series = []
    for r in rows:
        if meal == "all":
            value = round(
                r.get("breakfast_wastage_kg", 0)
                + r.get("lunch_wastage_kg", 0)
                + r.get("dinner_wastage_kg", 0),
                2,
            )
        else:
            value = r.get(f"{meal}_wastage_kg", 0)
        series.append({"date": r["date"], "value": value})

    today_iso_str = today.isoformat()
    yesterday_iso_str = (today - timedelta(days=1)).isoformat()
    last_week_iso_str = (today - timedelta(days=7)).isoformat()
    by_date = {r["date"]: r for r in rows}
    today_row = by_date.get(today_iso_str) or await wastage_col.find_one(
        {"date": today_iso_str}, {"_id": 0}
    )
    yesterday_row = by_date.get(yesterday_iso_str) or await wastage_col.find_one(
        {"date": yesterday_iso_str}, {"_id": 0}
    )
    last_week_row = by_date.get(last_week_iso_str) or await wastage_col.find_one(
        {"date": last_week_iso_str}, {"_id": 0}
    )

    def total(row: Optional[dict]) -> Optional[float]:
        if not row:
            return None
        return round(
            row.get("breakfast_wastage_kg", 0)
            + row.get("lunch_wastage_kg", 0)
            + row.get("dinner_wastage_kg", 0),
            2,
        )

    return {
        "range": range,
        "meal": meal,
        "series": series,
        "summary": {
            "today": {
                "breakfast": today_row.get("breakfast_wastage_kg") if today_row else None,
                "lunch": today_row.get("lunch_wastage_kg") if today_row else None,
                "dinner": today_row.get("dinner_wastage_kg") if today_row else None,
                "total": total(today_row),
            },
            "yesterday_total": total(yesterday_row),
            "last_week_same_day_total": total(last_week_row),
        },
    }


# ---------------------------------------------------------------------------
# ADMIN: Students Status
# ---------------------------------------------------------------------------
@api.get("/admin/students/summary")
async def admin_students_summary(_: dict = Depends(require_admin)):
    total_students = await users_col.count_documents({"role": "student"})
    approved = await users_col.count_documents(
        {"role": "student", "approval_status": "approved"}
    )
    pending = await users_col.count_documents(
        {"role": "student", "approval_status": "pending"}
    )
    blocked = await users_col.count_documents(
        {"role": "student", "approval_status": "rejected_or_blocked"}
    )
    return {
        "total_students": total_students,
        "approved": approved,
        "pending": pending,
        "blocked": blocked,
    }


@api.get("/admin/students")
async def admin_students_list(
    _: dict = Depends(require_admin),
    status: Literal["all", "pending", "approved", "blocked"] = Query("all"),
):
    query: dict = {"role": "student"}
    if status == "pending":
        query["approval_status"] = "pending"
    elif status == "approved":
        query["approval_status"] = "approved"
    elif status == "blocked":
        query["approval_status"] = "rejected_or_blocked"

    cursor = users_col.find(
        query, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1)
    items = [u async for u in cursor]
    return {"students": items, "count": len(items)}


@api.post("/admin/students/{student_id}/approve")
async def admin_approve_student(student_id: str, _: dict = Depends(require_admin)):
    res = await users_col.update_one(
        {"id": student_id, "role": "student"},
        {"$set": {"approval_status": "approved", "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"ok": True, "id": student_id, "approval_status": "approved"}


@api.post("/admin/students/{student_id}/reject")
async def admin_reject_student(student_id: str, _: dict = Depends(require_admin)):
    res = await users_col.update_one(
        {"id": student_id, "role": "student"},
        {"$set": {"approval_status": "rejected_or_blocked", "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"ok": True, "id": student_id, "approval_status": "rejected_or_blocked"}


async def _aggregate_meal(meal: MealType, target_date: str, menu: dict) -> dict:
    """Aggregate eating/not-eating/items/reasons/custom answers + like-dislike % for a meal."""
    # 1. From daily_plans for the date
    plans_cursor = daily_plans_col.find(
        {"date": target_date}, {"_id": 0, meal: 1, "student_id": 1}
    )
    eating = 0
    not_eating = 0
    item_counts: Dict[str, int] = defaultdict(int)
    reason_counts: Dict[str, int] = defaultdict(int)
    custom_counts: Dict[str, int] = defaultdict(int)
    async for p in plans_cursor:
        mp = (p.get(meal) or {})
        st = mp.get("status")
        if st == "ON":
            eating += 1
        elif st == "OFF":
            not_eating += 1
        # item preference counts (only consider ON-eating students)
        if st == "ON":
            for it in mp.get("selected_items") or []:
                item_counts[it] += 1
        # reason summary (only for OFF)
        if st == "OFF":
            r = (mp.get("reason_if_off") or "").strip()
            if r:
                # collapse "Other: text" to just "Other"
                key = "Other" if r.lower().startswith("other") else r
                reason_counts[key] += 1
        # custom answer summary (any status)
        ca = mp.get("custom_answer")
        if ca:
            custom_counts[ca] += 1

    # 2. like/dislike for today's day-of-week (reactions are keyed by day-of-week)
    day = day_of_week(date.fromisoformat(target_date))
    like = await menu_reactions_col.count_documents(
        {"day": day, "meal_type": meal, "reaction": "like"}
    )
    dislike = await menu_reactions_col.count_documents(
        {"day": day, "meal_type": meal, "reaction": "dislike"}
    )
    total_reactions = like + dislike
    like_pct = round((like / total_reactions) * 100, 1) if total_reactions else None
    dislike_pct = (
        round((dislike / total_reactions) * 100, 1) if total_reactions else None
    )

    menu_items: List[str] = menu.get(f"{meal}_items", []) if menu else []
    custom_question = menu.get(f"{meal}_custom_question") if menu else None

    # Make sure each menu item appears in item_counts (with 0) so the UI lists every item
    items_rows = []
    seen = set()
    for it in menu_items:
        items_rows.append({"item_name": it, "count": item_counts.get(it, 0)})
        seen.add(it)
    # include any selected items not in menu (rare)
    for it, c in item_counts.items():
        if it not in seen:
            items_rows.append({"item_name": it, "count": c})

    return {
        "menu_items": menu_items,
        "custom_question": custom_question,
        "eating_count": eating,
        "not_eating_count": not_eating,
        "like_count": like,
        "dislike_count": dislike,
        "like_pct": like_pct,
        "dislike_pct": dislike_pct,
        "item_counts": items_rows,
        "reason_counts": [
            {"reason": k, "count": v}
            for k, v in sorted(reason_counts.items(), key=lambda kv: -kv[1])
        ],
        "custom_answer_counts": [
            {"answer": k, "count": v}
            for k, v in sorted(custom_counts.items(), key=lambda kv: -kv[1])
        ],
    }


@api.get("/admin/today")
async def admin_today(_: dict = Depends(require_admin)):
    today = today_iso()
    day = day_of_week(date.fromisoformat(today))
    menu_doc = await menus_col.find_one({"day": day}, {"_id": 0}) or {}

    breakfast = await _aggregate_meal("breakfast", today, menu_doc)
    lunch = await _aggregate_meal("lunch", today, menu_doc)
    dinner = await _aggregate_meal("dinner", today, menu_doc)

    total_responses = await daily_plans_col.count_documents({"date": today})

    return {
        "date": today,
        "day": day,
        "total_responses": total_responses,
        "breakfast": breakfast,
        "lunch": lunch,
        "dinner": dinner,
    }


@api.get("/admin/feedback")
async def admin_feedback(
    _: dict = Depends(require_admin), days: int = Query(7, ge=1, le=90)
):
    since = (date.fromisoformat(today_iso()) - timedelta(days=days - 1)).isoformat()
    cursor = feedback_col.find(
        {"date": {"$gte": since}},
        # ANONYMOUS — never project student_id
        {"_id": 0, "id": 1, "date": 1, "feedback_text": 1, "created_at": 1},
    ).sort("created_at", -1)
    items = [r async for r in cursor]
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# ADMIN: Necessary Info
# ---------------------------------------------------------------------------
def _project_ni(doc: dict) -> dict:
    return {
        "id": doc["id"],
        "item_name": doc["item_name"],
        "meal_type": doc["meal_type"],
        "quantity_per_person": doc["quantity_per_person"],
        "unit": doc["unit"],
        "price_per_unit": doc["price_per_unit"],
        "price_unit": doc["price_unit"],
        "updated_at": doc.get("updated_at"),
    }


@api.get("/admin/necessary-info")
async def admin_ni_list(_: dict = Depends(require_admin)):
    cursor = necessary_info_col.find({}, {"_id": 0}).sort("item_name", 1)
    items = [_project_ni(r) async for r in cursor]
    return {"items": items, "count": len(items)}


@api.post("/admin/necessary-info", status_code=201)
async def admin_ni_create(
    payload: NecessaryItemInput, _: dict = Depends(require_admin)
):
    existing = await necessary_info_col.find_one(
        {"item_name": payload.item_name, "meal_type": payload.meal_type},
        {"_id": 0, "id": 1},
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Item already exists for this meal — use update instead",
        )
    now = now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        **payload.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    await necessary_info_col.insert_one(doc)
    doc.pop("_id", None)
    return _project_ni(doc)


@api.put("/admin/necessary-info/{item_id}")
async def admin_ni_update(
    item_id: str, payload: NecessaryItemInput, _: dict = Depends(require_admin)
):
    res = await necessary_info_col.update_one(
        {"id": item_id},
        {"$set": {**payload.model_dump(), "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    doc = await necessary_info_col.find_one({"id": item_id}, {"_id": 0})
    return _project_ni(doc) if doc else {"ok": True}


@api.delete("/admin/necessary-info/{item_id}")
async def admin_ni_delete(item_id: str, _: dict = Depends(require_admin)):
    res = await necessary_info_col.delete_one({"id": item_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# ADMIN: Menus
# ---------------------------------------------------------------------------
@api.get("/admin/menus")
async def admin_menu_list(_: dict = Depends(require_admin)):
    rows = []
    for d in DAYS:
        m = await menus_col.find_one({"day": d}, {"_id": 0})
        rows.append(
            project_menu(m)
            if m
            else {
                "day": d,
                "breakfast_items": [],
                "lunch_items": [],
                "dinner_items": [],
                "breakfast_custom_question": None,
                "lunch_custom_question": None,
                "dinner_custom_question": None,
            }
        )
    return {"days": rows}


@api.put("/admin/menus/{day}")
async def admin_menu_upsert(
    day: str, payload: MenuUpsert, _: dict = Depends(require_admin)
):
    if day not in DAYS:
        raise HTTPException(status_code=400, detail="Invalid day")
    now = now_iso()
    body = payload.model_dump()
    await menus_col.update_one(
        {"day": day},
        {
            "$set": {**body, "updated_at": now, "day": day},
            "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now},
        },
        upsert=True,
    )
    saved = await menus_col.find_one({"day": day}, {"_id": 0})
    return project_menu(saved) if saved else {"ok": True}


# ---------------------------------------------------------------------------
# ADMIN: Dashboard
# ---------------------------------------------------------------------------
@api.get("/admin/dashboard")
async def admin_dashboard(_: dict = Depends(require_admin)):
    today = today_iso()
    day = day_of_week(date.fromisoformat(today))
    menu_doc = await menus_col.find_one({"day": day}, {"_id": 0}) or {}

    # Load all necessary info into lookup
    ni_cursor = necessary_info_col.find({}, {"_id": 0})
    ni_lookup: Dict[str, dict] = {}
    async for r in ni_cursor:
        ni_lookup[f"{r['meal_type']}:{r['item_name'].lower()}"] = r

    out: Dict[str, Any] = {"date": today, "day": day, "meals": {}}
    most_demanded = {"item": None, "count": -1}
    least_demanded = {"item": None, "count": 10**9}

    for meal in ("breakfast", "lunch", "dinner"):
        agg = await _aggregate_meal(meal, today, menu_doc)  # type: ignore[arg-type]
        items_out = []
        warnings: List[str] = []
        menu_items: List[str] = menu_doc.get(f"{meal}_items", []) if menu_doc else []
        if not menu_items:
            warnings.append(f"Menu not added for {meal}. Add menu in Necessary Info.")

        for row in agg["item_counts"]:
            ni = ni_lookup.get(f"{meal}:{row['item_name'].lower()}")
            if not ni:
                warnings.append(
                    f"Quantity per person not added for {row['item_name']}. "
                    f"Add it in Necessary Info."
                )
                items_out.append(
                    {
                        "item_name": row["item_name"],
                        "preference_count": row["count"],
                        "quantity_per_person": None,
                        "unit": None,
                        "suggested": None,
                        "display": None,
                    }
                )
            else:
                raw_total = row["count"] * float(ni["quantity_per_person"])
                disp = display_quantity(raw_total, ni["unit"])
                items_out.append(
                    {
                        "item_name": row["item_name"],
                        "preference_count": row["count"],
                        "quantity_per_person": ni["quantity_per_person"],
                        "unit": ni["unit"],
                        "suggested": round(raw_total, 2),
                        "display": disp,
                    }
                )
            # track most/least demanded across all meals
            if row["count"] > most_demanded["count"]:
                most_demanded = {"item": row["item_name"], "count": row["count"]}
            if 0 < row["count"] < least_demanded["count"]:
                least_demanded = {"item": row["item_name"], "count": row["count"]}

        if not agg["item_counts"] and not warnings:
            warnings.append(
                "No student responses yet. Quantity suggestion will appear after "
                "students submit today's plan."
            )

        out["meals"][meal] = {
            "menu_items": menu_items,
            "eating_count": agg["eating_count"],
            "not_eating_count": agg["not_eating_count"],
            "items": items_out,
            "warnings": warnings,
        }

    if least_demanded["count"] == 10**9:
        least_demanded = {"item": None, "count": 0}

    out["summary"] = {
        "breakfast_eating": out["meals"]["breakfast"]["eating_count"],
        "lunch_eating": out["meals"]["lunch"]["eating_count"],
        "dinner_eating": out["meals"]["dinner"]["eating_count"],
        "total_responses": await daily_plans_col.count_documents({"date": today}),
        "most_demanded": most_demanded if most_demanded["item"] else None,
        "least_demanded": (
            least_demanded if least_demanded["item"] else None
        ),
    }
    return out


# ---------------------------------------------------------------------------
# ADMIN: Wastage & Calculation
# ---------------------------------------------------------------------------
async def _price_for(item_name: str, meal_type: str) -> Optional[dict]:
    return await necessary_info_col.find_one(
        {"item_name": item_name, "meal_type": meal_type}, {"_id": 0}
    )


async def _compute_wastage_doc(target_date: str, payload: WastageUpsert) -> dict:
    """Compute aggregates + per-item loss from raw wastage entries."""
    out: Dict[str, Any] = {
        "date": target_date,
        "breakfast_items": [],
        "lunch_items": [],
        "dinner_items": [],
        "breakfast_wastage_kg": 0.0,
        "lunch_wastage_kg": 0.0,
        "dinner_wastage_kg": 0.0,
        "breakfast_loss": 0.0,
        "lunch_loss": 0.0,
        "dinner_loss": 0.0,
    }
    pairs = (
        ("breakfast", payload.breakfast_items),
        ("lunch", payload.lunch_items),
        ("dinner", payload.dinner_items),
    )
    for meal, items in pairs:
        agg_kg = 0.0
        agg_loss = 0.0
        rich_items = []
        for it in items:
            price = it.price_per_unit
            price_unit = it.price_unit
            if price is None or price_unit is None:
                ni = await _price_for(it.item_name, meal)
                if ni:
                    price = float(ni["price_per_unit"])
                    price_unit = ni["price_unit"]
            loss = 0.0
            if price is not None and price_unit is not None:
                qty_in_price_unit = normalize_to_price_unit(
                    it.quantity, it.unit, price_unit
                )
                loss = round(qty_in_price_unit * price, 2)
            kg = to_kg_equiv(it.quantity, it.unit)
            agg_kg += kg
            agg_loss += loss
            rich_items.append(
                {
                    "item_name": it.item_name,
                    "quantity": float(it.quantity),
                    "unit": it.unit,
                    "price_per_unit": price,
                    "price_unit": price_unit,
                    "loss": loss,
                }
            )
        out[f"{meal}_items"] = rich_items
        out[f"{meal}_wastage_kg"] = round(agg_kg, 2)
        out[f"{meal}_loss"] = round(agg_loss, 2)
    out["total_loss"] = round(
        out["breakfast_loss"] + out["lunch_loss"] + out["dinner_loss"], 2
    )
    return out


@api.put("/admin/wastage/{target_date}")
async def admin_wastage_upsert(
    target_date: str, payload: WastageUpsert, _: dict = Depends(require_admin)
):
    try:
        date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")

    body = await _compute_wastage_doc(target_date, payload)
    now = now_iso()
    await wastage_col.update_one(
        {"date": target_date},
        {
            "$set": {**body, "updated_at": now},
            "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now},
        },
        upsert=True,
    )
    saved = await wastage_col.find_one({"date": target_date}, {"_id": 0})
    return {"ok": True, "wastage": saved}


@api.get("/admin/wastage/today")
async def admin_wastage_today(_: dict = Depends(require_admin)):
    today = today_iso()
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    last_week = (date.fromisoformat(today) - timedelta(days=7)).isoformat()
    today_doc = await wastage_col.find_one({"date": today}, {"_id": 0})
    yesterday_doc = await wastage_col.find_one({"date": yesterday}, {"_id": 0})
    last_week_doc = await wastage_col.find_one({"date": last_week}, {"_id": 0})

    # 30-day average loss (only days that have a total_loss)
    today_d = date.fromisoformat(today)
    start = (today_d - timedelta(days=30)).isoformat()
    avg_cursor = wastage_col.find(
        {
            "date": {"$gte": start, "$lt": today},
            "total_loss": {"$exists": True, "$gt": 0},
        },
        {"_id": 0, "total_loss": 1},
    )
    losses = [r["total_loss"] async for r in avg_cursor]
    average_loss = round(sum(losses) / len(losses), 2) if losses else None
    today_total_loss = (today_doc or {}).get("total_loss")
    saved_amount = (
        round(average_loss - today_total_loss, 2)
        if average_loss is not None and today_total_loss is not None
        else None
    )

    return {
        "date": today,
        "today": today_doc,
        "yesterday": yesterday_doc,
        "last_week_same_day": last_week_doc,
        "average_loss_30d": average_loss,
        "saved_amount_vs_avg": saved_amount,
    }


@api.get("/admin/wastage/trend")
async def admin_wastage_trend(
    _: dict = Depends(require_admin),
    range: int = Query(7, ge=1, le=365),
    meal: Literal["all", "breakfast", "lunch", "dinner"] = Query("all"),
):
    today = date.fromisoformat(today_iso())
    start = today - timedelta(days=range - 1)
    cursor = wastage_col.find(
        {"date": {"$gte": start.isoformat(), "$lte": today.isoformat()}},
        {"_id": 0},
    ).sort("date", 1)
    rows = [r async for r in cursor]

    wastage_series = []
    saved_series = []
    losses_so_far: List[float] = []

    for r in rows:
        if meal == "all":
            wastage_value = round(
                r.get("breakfast_wastage_kg", 0)
                + r.get("lunch_wastage_kg", 0)
                + r.get("dinner_wastage_kg", 0),
                2,
            )
            loss = r.get("total_loss") or (
                r.get("breakfast_loss", 0)
                + r.get("lunch_loss", 0)
                + r.get("dinner_loss", 0)
            )
        else:
            wastage_value = r.get(f"{meal}_wastage_kg", 0)
            loss = r.get(f"{meal}_loss", 0)

        wastage_series.append({"date": r["date"], "value": wastage_value})

        # Running savings: avg of prior losses minus today's loss
        if losses_so_far:
            avg = sum(losses_so_far) / len(losses_so_far)
            saved = round(avg - float(loss or 0), 2)
        else:
            saved = 0.0
        saved_series.append({"date": r["date"], "value": saved})
        if loss:
            losses_so_far.append(float(loss))

    return {
        "range": range,
        "meal": meal,
        "wastage_series": wastage_series,
        "saved_series": saved_series,
    }


# ---------------------------------------------------------------------------
# ADMIN: Settings
# ---------------------------------------------------------------------------
SETTINGS_DEFAULTS = {
    "default_meal_state": "ON",
    "default_like_dislike_state": "no_response",
    "default_preference_state": "none",
    "notifications_enabled": True,
    "language": "English",
}


@api.get("/admin/settings")
async def admin_settings_get(_: dict = Depends(require_admin)):
    doc = await settings_col.find_one({"id": "app"}, {"_id": 0})
    if not doc:
        doc = {"id": "app", **SETTINGS_DEFAULTS, "updated_at": now_iso()}
        await settings_col.insert_one(doc)
        doc.pop("_id", None)
    return doc


@api.put("/admin/settings")
async def admin_settings_put(
    payload: AppSettingsInput, _: dict = Depends(require_admin)
):
    body = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not body:
        raise HTTPException(status_code=400, detail="No fields to update")
    body["updated_at"] = now_iso()
    # Avoid $set / $setOnInsert path conflict: only set defaults for fields the
    # caller didn't supply.
    set_on_insert = {"id": "app", **{k: v for k, v in SETTINGS_DEFAULTS.items() if k not in body}}
    await settings_col.update_one(
        {"id": "app"},
        {"$set": body, "$setOnInsert": set_on_insert},
        upsert=True,
    )
    doc = await settings_col.find_one({"id": "app"}, {"_id": 0})
    return doc


# ---------------------------------------------------------------------------
# Seeding (idempotent)
# ---------------------------------------------------------------------------
SEED_USERS = [
    {
        "full_name": "Demo Admin",
        "mobile_or_user_id": "admin",
        "institution_or_hostel_name": "Demo Hostel",
        "room_number": None,
        "password": "admin123",
        "role": "admin",
        "approval_status": "approved",
    },
    {
        "full_name": "Demo Student",
        "mobile_or_user_id": "student",
        "institution_or_hostel_name": "Demo Hostel",
        "room_number": "A101",
        "password": "student123",
        "role": "student",
        "approval_status": "approved",
    },
    {
        "full_name": "Pending Student",
        "mobile_or_user_id": "pending",
        "institution_or_hostel_name": "Demo Hostel",
        "room_number": "B202",
        "password": "pending123",
        "role": "student",
        "approval_status": "pending",
    },
    {
        "full_name": "Blocked Student",
        "mobile_or_user_id": "blocked",
        "institution_or_hostel_name": "Demo Hostel",
        "room_number": "C303",
        "password": "blocked123",
        "role": "student",
        "approval_status": "rejected_or_blocked",
    },
]

SEED_MENUS = [
    {
        "day": "monday",
        "breakfast_items": ["Idly", "Dosa", "Sambar", "Chutney"],
        "lunch_items": ["Rice", "Sambar", "Rasam", "Curd", "Poriyal"],
        "dinner_items": ["Chapati", "Kurma", "Rice"],
        "breakfast_custom_question": {
            "text": "Do you want extra chutney?",
            "options": ["Yes", "No"],
        },
        "lunch_custom_question": {
            "text": "Do you want curd rice today?",
            "options": ["Yes", "No"],
        },
        "dinner_custom_question": {
            "text": "Which side dish do you prefer?",
            "options": ["Kurma", "Chutney", "Both"],
        },
    },
    {
        "day": "tuesday",
        "breakfast_items": ["Pongal", "Vada", "Chutney"],
        "lunch_items": ["Lemon Rice", "Curd Rice", "Potato Fry"],
        "dinner_items": ["Dosa", "Sambar", "Chutney"],
        "breakfast_custom_question": {"text": "Do you want extra chutney?", "options": ["Yes", "No"]},
        "lunch_custom_question": None,
        "dinner_custom_question": None,
    },
    {
        "day": "wednesday",
        "breakfast_items": ["Poori", "Masala"],
        "lunch_items": ["Rice", "Dal", "Rasam", "Curd"],
        "dinner_items": ["Chapati", "Veg Kurma"],
        "breakfast_custom_question": None,
        "lunch_custom_question": {"text": "Do you want curd rice today?", "options": ["Yes", "No"]},
        "dinner_custom_question": None,
    },
    {
        "day": "thursday",
        "breakfast_items": ["Upma", "Chutney"],
        "lunch_items": ["Tomato Rice", "Curd", "Poriyal"],
        "dinner_items": ["Idiyappam", "Kurma"],
        "breakfast_custom_question": None,
        "lunch_custom_question": None,
        "dinner_custom_question": {"text": "Which side dish do you prefer?", "options": ["Kurma", "Chutney", "Both"]},
    },
    {
        "day": "friday",
        "breakfast_items": ["Idly", "Sambar"],
        "lunch_items": ["Veg Biryani", "Raita"],
        "dinner_items": ["Parotta", "Kurma"],
        "breakfast_custom_question": None,
        "lunch_custom_question": None,
        "dinner_custom_question": None,
    },
    {
        "day": "saturday",
        "breakfast_items": ["Dosa", "Chutney"],
        "lunch_items": ["Rice", "Sambar", "Appalam", "Curd"],
        "dinner_items": ["Fried Rice", "Gobi"],
        "breakfast_custom_question": None,
        "lunch_custom_question": None,
        "dinner_custom_question": None,
    },
    {
        "day": "sunday",
        "breakfast_items": ["Pongal", "Vada"],
        "lunch_items": ["Special Meals"],
        "dinner_items": ["Chapati", "Paneer Gravy"],
        "breakfast_custom_question": None,
        "lunch_custom_question": None,
        "dinner_custom_question": None,
    },
]

SEED_NECESSARY_INFO = [
    {"item_name": "Idly", "meal_type": "breakfast", "quantity_per_person": 4, "unit": "pieces", "price_per_unit": 5, "price_unit": "pieces"},
    {"item_name": "Dosa", "meal_type": "breakfast", "quantity_per_person": 2, "unit": "pieces", "price_per_unit": 8, "price_unit": "pieces"},
    {"item_name": "Sambar", "meal_type": "breakfast", "quantity_per_person": 100, "unit": "ml", "price_per_unit": 40, "price_unit": "litres"},
    {"item_name": "Chutney", "meal_type": "breakfast", "quantity_per_person": 50, "unit": "ml", "price_per_unit": 60, "price_unit": "litres"},
    {"item_name": "Pongal", "meal_type": "breakfast", "quantity_per_person": 120, "unit": "grams", "price_per_unit": 60, "price_unit": "kg"},
    {"item_name": "Vada", "meal_type": "breakfast", "quantity_per_person": 2, "unit": "pieces", "price_per_unit": 6, "price_unit": "pieces"},

    {"item_name": "Rice", "meal_type": "lunch", "quantity_per_person": 150, "unit": "grams", "price_per_unit": 50, "price_unit": "kg"},
    {"item_name": "Sambar", "meal_type": "lunch", "quantity_per_person": 100, "unit": "ml", "price_per_unit": 40, "price_unit": "litres"},
    {"item_name": "Rasam", "meal_type": "lunch", "quantity_per_person": 80, "unit": "ml", "price_per_unit": 30, "price_unit": "litres"},
    {"item_name": "Curd", "meal_type": "lunch", "quantity_per_person": 80, "unit": "ml", "price_per_unit": 60, "price_unit": "litres"},
    {"item_name": "Poriyal", "meal_type": "lunch", "quantity_per_person": 70, "unit": "grams", "price_per_unit": 40, "price_unit": "kg"},
    {"item_name": "Lemon Rice", "meal_type": "lunch", "quantity_per_person": 180, "unit": "grams", "price_per_unit": 70, "price_unit": "kg"},
    {"item_name": "Curd Rice", "meal_type": "lunch", "quantity_per_person": 150, "unit": "grams", "price_per_unit": 80, "price_unit": "kg"},

    {"item_name": "Chapati", "meal_type": "dinner", "quantity_per_person": 3, "unit": "pieces", "price_per_unit": 4, "price_unit": "pieces"},
    {"item_name": "Kurma", "meal_type": "dinner", "quantity_per_person": 100, "unit": "ml", "price_per_unit": 45, "price_unit": "litres"},
    {"item_name": "Rice", "meal_type": "dinner", "quantity_per_person": 150, "unit": "grams", "price_per_unit": 50, "price_unit": "kg"},
    {"item_name": "Dosa", "meal_type": "dinner", "quantity_per_person": 3, "unit": "pieces", "price_per_unit": 8, "price_unit": "pieces"},
    {"item_name": "Sambar", "meal_type": "dinner", "quantity_per_person": 100, "unit": "ml", "price_per_unit": 40, "price_unit": "litres"},
    {"item_name": "Chutney", "meal_type": "dinner", "quantity_per_person": 50, "unit": "ml", "price_per_unit": 60, "price_unit": "litres"},
]

SEED_FEEDBACK = [
    "Lunch was too spicy today",
    "Please add curd rice twice a week",
    "Breakfast quantity was low",
    "Dinner was really good today, thanks!",
    "Sambar could be a bit less salty",
    "Loved the parotta on Friday",
    "Please serve hot chapatis",
]

# Bulk demo students for stat depth
SEED_EXTRA_STUDENTS_COUNT = 28
SEED_EXTRA_PENDING_COUNT = 4
SEED_EXTRA_BLOCKED_COUNT = 4


async def seed_demo_users():
    now = now_iso()
    for u in SEED_USERS:
        existing = await users_col.find_one(
            {"mobile_or_user_id": u["mobile_or_user_id"]}, {"_id": 0}
        )
        if existing:
            continue
        doc = {
            "id": str(uuid.uuid4()),
            "full_name": u["full_name"],
            "mobile_or_user_id": u["mobile_or_user_id"],
            "institution_or_hostel_name": u["institution_or_hostel_name"],
            "room_number": u["room_number"],
            "password_hash": hash_password(u["password"]),
            "role": u["role"],
            "approval_status": u["approval_status"],
            "created_at": now,
            "updated_at": now,
        }
        await users_col.insert_one(doc)
        logger.info("Seeded demo user: %s (%s)", u["mobile_or_user_id"], u["role"])


async def seed_extra_students():
    """Seed additional demo students for stat depth (idempotent by mobile id)."""
    now = now_iso()
    pwd = hash_password("demopass")  # shared password (these are demo accounts)

    cohorts = [
        ("approved", SEED_EXTRA_STUDENTS_COUNT, "DemoStudent", "approved"),
        ("pending", SEED_EXTRA_PENDING_COUNT, "DemoPending", "pending"),
        ("blocked", SEED_EXTRA_BLOCKED_COUNT, "DemoBlocked", "rejected_or_blocked"),
    ]
    for tag, n, prefix, status in cohorts:
        for i in range(1, n + 1):
            mobile = f"{tag}{i:03d}"
            existing = await users_col.find_one(
                {"mobile_or_user_id": mobile}, {"_id": 0, "id": 1}
            )
            if existing:
                continue
            await users_col.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "full_name": f"{prefix} {i}",
                    "mobile_or_user_id": mobile,
                    "institution_or_hostel_name": "Demo Hostel",
                    "room_number": f"{chr(ord('A') + (i % 5))}{100 + i}",
                    "password_hash": pwd,
                    "role": "student",
                    "approval_status": status,
                    "created_at": now,
                    "updated_at": now,
                }
            )


async def seed_today_plans():
    """Seed today's daily plans for all approved students (idempotent)."""
    today = today_iso()
    day = day_of_week(date.fromisoformat(today))
    menu = await menus_col.find_one({"day": day}, {"_id": 0})
    if not menu:
        return
    rnd = random.Random(today)  # vary across days

    cursor = users_col.find(
        {"role": "student", "approval_status": "approved"},
        {"_id": 0, "id": 1},
    )
    approved_ids = [u["id"] async for u in cursor]

    def pick_items(items: List[str]) -> List[str]:
        if not items:
            return []
        k = rnd.randint(1, len(items))
        return rnd.sample(items, k)

    def pick_reason() -> str:
        return rnd.choice(REASONS[:6])  # avoid "Other" in seed

    def pick_custom(q: Optional[dict]) -> Optional[str]:
        if not q:
            return None
        return rnd.choice(q["options"])

    for sid in approved_ids:
        existing = await daily_plans_col.find_one(
            {"student_id": sid, "date": today}, {"_id": 0, "id": 1}
        )
        if existing:
            continue
        plan: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "student_id": sid,
            "date": today,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        for meal in ("breakfast", "lunch", "dinner"):
            is_on = rnd.random() > 0.25  # ~75% eat
            items = menu.get(f"{meal}_items", []) if menu else []
            cq = menu.get(f"{meal}_custom_question") if menu else None
            plan[meal] = {
                "status": "ON" if is_on else "OFF",
                "selected_items": pick_items(items) if is_on else [],
                "reason_if_off": None if is_on else pick_reason(),
                "custom_answer": pick_custom(cq) if is_on else None,
            }
        await daily_plans_col.insert_one(plan)


async def seed_reactions():
    """Seed sample like/dislike reactions across students × today's day-of-week."""
    today = today_iso()
    day = day_of_week(date.fromisoformat(today))
    rnd = random.Random(day)
    cursor = users_col.find(
        {"role": "student", "approval_status": "approved"},
        {"_id": 0, "id": 1},
    )
    sids = [u["id"] async for u in cursor]
    for sid in sids:
        for meal in ("breakfast", "lunch", "dinner"):
            existing = await menu_reactions_col.find_one(
                {"student_id": sid, "day": day, "meal_type": meal},
                {"_id": 0, "id": 1},
            )
            if existing:
                continue
            # ~70% like, ~20% dislike, ~10% no response
            roll = rnd.random()
            if roll < 0.10:
                reaction = "no_response"
            elif roll < 0.30:
                reaction = "dislike"
            else:
                reaction = "like"
            await menu_reactions_col.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "student_id": sid,
                    "day": day,
                    "meal_type": meal,
                    "reaction": reaction,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )


async def seed_feedback():
    """Seed some anonymous feedback rows for today."""
    today = today_iso()
    existing = await feedback_col.count_documents({"date": today})
    if existing >= len(SEED_FEEDBACK):
        return
    cursor = users_col.find(
        {"role": "student", "approval_status": "approved"},
        {"_id": 0, "id": 1},
    )
    sids = [u["id"] async for u in cursor]
    if not sids:
        return
    rnd = random.Random("fb-" + today)
    for text in SEED_FEEDBACK[existing:]:
        await feedback_col.insert_one(
            {
                "id": str(uuid.uuid4()),
                "student_id": rnd.choice(sids),
                "date": today,
                "feedback_text": text,
                "anonymous": True,
                "created_at": now_iso(),
            }
        )


async def seed_menus():
    now = now_iso()
    for m in SEED_MENUS:
        await menus_col.update_one(
            {"day": m["day"]},
            {
                "$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "created_at": now,
                    "day": m["day"],
                },
                "$set": {
                    "breakfast_items": m["breakfast_items"],
                    "lunch_items": m["lunch_items"],
                    "dinner_items": m["dinner_items"],
                    "breakfast_custom_question": m["breakfast_custom_question"],
                    "lunch_custom_question": m["lunch_custom_question"],
                    "dinner_custom_question": m["dinner_custom_question"],
                    "updated_at": now,
                },
            },
            upsert=True,
        )


async def seed_necessary_info():
    now = now_iso()
    for item in SEED_NECESSARY_INFO:
        existing = await necessary_info_col.find_one(
            {"item_name": item["item_name"], "meal_type": item["meal_type"]},
            {"_id": 0, "id": 1},
        )
        if existing:
            continue
        await necessary_info_col.insert_one(
            {
                "id": str(uuid.uuid4()),
                **item,
                "created_at": now,
                "updated_at": now,
            }
        )


async def seed_wastage():
    today = date.fromisoformat(today_iso())
    rnd = random.Random(42)
    bulk_inserts = []
    for offset in range(95):
        d = today - timedelta(days=offset)
        existing = await wastage_col.find_one({"date": d.isoformat()}, {"_id": 0})
        if existing:
            continue
        progress = offset / 95.0
        base_b = 2.5 + progress * 3.0 + rnd.uniform(-0.6, 0.6)
        base_l = 4.5 + progress * 3.5 + rnd.uniform(-0.7, 0.7)
        base_d = 3.5 + progress * 3.0 + rnd.uniform(-0.6, 0.6)
        b_kg = round(max(0.5, base_b), 2)
        l_kg = round(max(0.5, base_l), 2)
        d_kg = round(max(0.5, base_d), 2)
        # rough loss values for chart: ~₹60/kg average
        b_loss = round(b_kg * 60 + rnd.uniform(-30, 30), 2)
        l_loss = round(l_kg * 60 + rnd.uniform(-30, 30), 2)
        d_loss = round(d_kg * 60 + rnd.uniform(-30, 30), 2)
        bulk_inserts.append(
            {
                "id": str(uuid.uuid4()),
                "date": d.isoformat(),
                "breakfast_items": [],
                "lunch_items": [],
                "dinner_items": [],
                "breakfast_wastage_kg": b_kg,
                "lunch_wastage_kg": l_kg,
                "dinner_wastage_kg": d_kg,
                "breakfast_loss": max(0.0, b_loss),
                "lunch_loss": max(0.0, l_loss),
                "dinner_loss": max(0.0, d_loss),
                "total_loss": round(
                    max(0.0, b_loss) + max(0.0, l_loss) + max(0.0, d_loss), 2
                ),
                "created_at": now_iso(),
            }
        )
    if bulk_inserts:
        await wastage_col.insert_many(bulk_inserts)
        logger.info("Seeded %d wastage rows", len(bulk_inserts))


async def seed_settings():
    existing = await settings_col.find_one({"id": "app"}, {"_id": 0})
    if existing:
        return
    await settings_col.insert_one(
        {"id": "app", **SETTINGS_DEFAULTS, "created_at": now_iso(), "updated_at": now_iso()}
    )


@app.on_event("startup")
async def on_startup():
    await users_col.create_index("mobile_or_user_id", unique=True)
    await users_col.create_index("id", unique=True)
    await menus_col.create_index("day", unique=True)
    await daily_plans_col.create_index(
        [("student_id", 1), ("date", 1)], unique=True
    )
    await menu_reactions_col.create_index(
        [("student_id", 1), ("day", 1), ("meal_type", 1)], unique=True
    )
    await wastage_col.create_index("date", unique=True)
    await necessary_info_col.create_index(
        [("item_name", 1), ("meal_type", 1)], unique=True
    )
    await settings_col.create_index("id", unique=True)

    await seed_demo_users()
    await seed_extra_students()
    await seed_menus()
    await seed_necessary_info()
    await seed_today_plans()
    await seed_reactions()
    await seed_feedback()
    await seed_wastage()
    await seed_settings()
    logger.info("MessMate API ready")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# ---------------------------------------------------------------------------
# Mount + CORS
# ---------------------------------------------------------------------------
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
