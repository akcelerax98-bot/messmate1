"""MessMate backend — Auth + Student + Admin + Notifications.

Multi-tenant: every domain doc is scoped by `hostel` (institution_or_hostel_name).
Two-step login with mocked OTP. In-app notifications + push token capture.
"""

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
MOCK_OTP = "123456"

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
notifications_col = db["notifications"]

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
    institution_or_hostel_name: str = Field(..., min_length=1)


class VerifyLoginOtpRequest(BaseModel):
    challenge: str
    otp: str


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


class ChallengeResponse(BaseModel):
    challenge: str
    user_preview: Dict[str, Any]
    mock_otp: str  # dev only — would be omitted in real SMS flow


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
    price_unit: Unit


class WastageItemInput(BaseModel):
    item_name: str = Field(..., min_length=1, max_length=80)
    quantity: float = Field(..., ge=0)
    unit: Unit
    price_per_unit: Optional[float] = None
    price_unit: Optional[Unit] = None


class WastageUpsert(BaseModel):
    breakfast_items: List[WastageItemInput] = Field(default_factory=list)
    lunch_items: List[WastageItemInput] = Field(default_factory=list)
    dinner_items: List[WastageItemInput] = Field(default_factory=list)
    manual_total_cost: Optional[float] = None  # admin-typed daily cost (₹)


class AppSettingsInput(BaseModel):
    default_meal_state: Optional[Literal["ON", "OFF"]] = None
    default_like_dislike_state: Optional[Reaction] = None
    default_preference_state: Optional[Literal["none", "all", "previous"]] = None
    notifications_enabled: Optional[bool] = None
    language: Optional[str] = None


class PushTokenInput(BaseModel):
    push_token: str = Field(..., min_length=1, max_length=400)


class NotificationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=140)
    body: str = Field(..., min_length=1, max_length=600)
    audience: Literal["all", "student"] = "all"
    recipient_id: Optional[str] = None
    type: Literal["announcement", "menu_reminder", "system"] = "announcement"
    scheduled_for: Optional[str] = None  # ISO date (when it should "fire")


class MenuReminderCreate(BaseModel):
    """Schedules tomorrow's menu reminder for all students in the hostel."""
    custom_body: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
REASONS = [
    "Going home", "Eating outside", "Not hungry", "Class/Event",
    "Sick", "Don't like today's menu", "Other",
]
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DEFAULT_HOSTEL = "Demo Hostel"


def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_token(payload: dict, minutes: int = JWT_EXPIRE_MINUTES) -> str:
    to_encode = payload.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def to_public(d: dict) -> UserPublic:
    return UserPublic(
        id=d["id"],
        full_name=d["full_name"],
        mobile_or_user_id=d["mobile_or_user_id"],
        institution_or_hostel_name=d["institution_or_hostel_name"],
        room_number=d.get("room_number"),
        role=d["role"],
        approval_status=d["approval_status"],
        created_at=d["created_at"],
        updated_at=d["updated_at"],
    )


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def day_of_week(d: date) -> str:
    return DAYS[d.weekday()]


def to_kg_equiv(q: float, u: str) -> float:
    return {"pieces": q * 0.05, "grams": q / 1000.0, "kg": q,
            "ml": q / 1000.0, "litres": q}.get(u, q)


def normalize_to_price_unit(q: float, qu: str, pu: str) -> float:
    if qu == pu:
        return float(q)
    pairs = {("grams", "kg"): q / 1000.0, ("kg", "grams"): q * 1000.0,
             ("ml", "litres"): q / 1000.0, ("litres", "ml"): q * 1000.0}
    return pairs.get((qu, pu), float(q))


def display_quantity(v: float, u: str) -> Dict[str, Any]:
    if u == "grams" and v >= 1000:
        return {"value": round(v / 1000.0, 2), "unit": "kg"}
    if u == "ml" and v >= 1000:
        return {"value": round(v / 1000.0, 2), "unit": "litres"}
    return {"value": round(v, 2), "unit": u}


def hostel_of(user: dict) -> str:
    return user["institution_or_hostel_name"]


async def get_user_by_id(uid: str) -> Optional[dict]:
    return await users_col.find_one({"id": uid}, {"_id": 0})


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") == "challenge":
            raise HTTPException(status_code=401, detail="Challenge token not allowed here")
        uid = payload.get("sub")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await get_user_by_id(uid)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_approved_student(u: dict = Depends(get_current_user)) -> dict:
    if u["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    if u["approval_status"] != "approved":
        raise HTTPException(status_code=403, detail="Student is not approved")
    return u


async def require_admin(u: dict = Depends(get_current_user)) -> dict:
    if u["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return u


def project_menu(d: dict) -> dict:
    return {
        "day": d["day"],
        "breakfast_items": d.get("breakfast_items", []),
        "lunch_items": d.get("lunch_items", []),
        "dinner_items": d.get("dinner_items", []),
        "breakfast_custom_question": d.get("breakfast_custom_question"),
        "lunch_custom_question": d.get("lunch_custom_question"),
        "dinner_custom_question": d.get("dinner_custom_question"),
    }


def project_plan(d: Optional[dict]) -> Optional[dict]:
    if not d:
        return None
    return {
        "date": d["date"],
        "breakfast": d.get("breakfast", {}),
        "lunch": d.get("lunch", {}),
        "dinner": d.get("dinner", {}),
        "updated_at": d.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"app": "MessMate", "status": "ok"}


@api.post("/auth/register-student", response_model=UserPublic, status_code=201)
async def register_student(payload: StudentRegisterRequest):
    existing = await users_col.find_one(
        {"mobile_or_user_id": payload.mobile_or_user_id,
         "institution_or_hostel_name": payload.institution_or_hostel_name},
        {"_id": 0},
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An account with this mobile number already exists in this hostel",
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


@api.post("/auth/login", response_model=ChallengeResponse)
async def login_step1(payload: LoginRequest):
    """Step 1: validate credentials, issue OTP challenge.

    OTP is MOCKED — real SMS provider will be wired before deploy.
    """
    user = await users_col.find_one(
        {
            "mobile_or_user_id": payload.mobile_or_user_id.strip(),
            "institution_or_hostel_name": payload.institution_or_hostel_name.strip(),
        },
        {"_id": 0},
    )
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    challenge = create_token(
        {"sub": user["id"], "type": "challenge"}, minutes=10,
    )
    return ChallengeResponse(
        challenge=challenge,
        user_preview={
            "full_name": user["full_name"],
            "role": user["role"],
            "mobile_or_user_id": user["mobile_or_user_id"],
            "institution_or_hostel_name": user["institution_or_hostel_name"],
        },
        mock_otp=MOCK_OTP,
    )


@api.post("/auth/verify-login-otp", response_model=TokenResponse)
async def login_step2(payload: VerifyLoginOtpRequest):
    """Step 2: verify OTP for the challenge → issue access token."""
    try:
        decoded = jwt.decode(payload.challenge, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=400, detail="Challenge expired — please log in again")

    if decoded.get("type") != "challenge":
        raise HTTPException(status_code=400, detail="Invalid challenge")

    if payload.otp.strip() != MOCK_OTP:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user = await get_user_by_id(decoded["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    token = create_token({
        "sub": user["id"], "role": user["role"], "status": user["approval_status"],
    })
    return TokenResponse(access_token=token, user=to_public(user))


@api.get("/auth/me", response_model=UserPublic)
async def me(u: dict = Depends(get_current_user)):
    return to_public(u)


@api.post("/auth/request-otp")
async def request_otp_placeholder(mobile_or_user_id: str):
    return {"message": "OTP placeholder", "mock_otp": MOCK_OTP}


@api.post("/auth/verify-otp")
async def verify_otp_placeholder(mobile_or_user_id: str, otp: str):
    if otp != MOCK_OTP:
        raise HTTPException(status_code=400, detail="Invalid OTP (mock)")
    return {"message": "OTP verified (mock)"}


@api.post("/auth/push-token")
async def save_push_token(payload: PushTokenInput, u: dict = Depends(get_current_user)):
    """Capture an Expo/FCM push token. MOCKED dispatch — real push wired at deploy."""
    await users_col.update_one(
        {"id": u["id"]},
        {"$set": {"push_token": payload.push_token.strip(), "updated_at": now_iso()}},
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Student routes
# ---------------------------------------------------------------------------
@api.get("/student/meta")
async def student_meta(_: dict = Depends(require_approved_student)):
    return {"reasons": REASONS, "days": DAYS}


@api.get("/student/today")
async def student_today(u: dict = Depends(require_approved_student)):
    today = today_iso()
    day = day_of_week(date.fromisoformat(today))
    h = hostel_of(u)
    menu_doc = await menus_col.find_one({"hostel": h, "day": day}, {"_id": 0})
    plan_doc = await daily_plans_col.find_one(
        {"student_id": u["id"], "date": today}, {"_id": 0}
    )
    return {
        "date": today, "day": day,
        "menu": project_menu(menu_doc) if menu_doc else None,
        "plan": project_plan(plan_doc),
    }


@api.put("/student/today")
async def upsert_today_plan(
    payload: DailyPlanUpsert, u: dict = Depends(require_approved_student)
):
    target = payload.date or today_iso()
    try:
        date.fromisoformat(target)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")

    now = now_iso()
    set_doc = {
        "student_id": u["id"], "date": target,
        "hostel": hostel_of(u),
        "breakfast": payload.breakfast.model_dump(),
        "lunch": payload.lunch.model_dump(),
        "dinner": payload.dinner.model_dump(),
        "updated_at": now,
    }
    await daily_plans_col.update_one(
        {"student_id": u["id"], "date": target},
        {"$set": set_doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
        upsert=True,
    )
    saved = await daily_plans_col.find_one(
        {"student_id": u["id"], "date": target}, {"_id": 0}
    )
    return {"ok": True, "plan": project_plan(saved)}


@api.post("/student/feedback")
async def post_feedback(
    payload: FeedbackInput, u: dict = Depends(require_approved_student)
):
    now = now_iso()
    await feedback_col.insert_one({
        "id": str(uuid.uuid4()),
        "student_id": u["id"], "hostel": hostel_of(u),
        "date": today_iso(),
        "feedback_text": payload.feedback_text.strip(),
        "anonymous": True, "created_at": now,
    })
    return {"ok": True, "created_at": now}


@api.get("/student/menu/week")
async def student_menu_week(u: dict = Depends(require_approved_student)):
    h = hostel_of(u)
    docs = []
    for d in DAYS:
        m = await menus_col.find_one({"hostel": h, "day": d}, {"_id": 0})
        docs.append(project_menu(m) if m else {
            "day": d, "breakfast_items": [], "lunch_items": [], "dinner_items": [],
            "breakfast_custom_question": None, "lunch_custom_question": None,
            "dinner_custom_question": None,
        })
    reactions: Dict[str, str] = {}
    async for r in menu_reactions_col.find(
        {"student_id": u["id"]}, {"_id": 0, "day": 1, "meal_type": 1, "reaction": 1}
    ):
        reactions[f"{r['day']}:{r['meal_type']}"] = r["reaction"]
    for d in docs:
        d["reactions"] = {
            "breakfast": reactions.get(f"{d['day']}:breakfast", "no_response"),
            "lunch": reactions.get(f"{d['day']}:lunch", "no_response"),
            "dinner": reactions.get(f"{d['day']}:dinner", "no_response"),
        }
    return {"days": docs}


@api.get("/student/menu/month")
async def student_menu_month(u: dict = Depends(require_approved_student)):
    week = await student_menu_week(u)  # type: ignore[arg-type]
    return {"weeks": [{"label": f"Week {i + 1}", "days": week["days"]} for i in range(4)]}


@api.put("/student/menu/reaction")
async def upsert_reaction(
    payload: ReactionUpsert, u: dict = Depends(require_approved_student)
):
    if payload.day not in DAYS:
        raise HTTPException(status_code=400, detail="Invalid day")
    now = now_iso()
    await menu_reactions_col.update_one(
        {"student_id": u["id"], "day": payload.day, "meal_type": payload.meal_type},
        {
            "$set": {"reaction": payload.reaction, "hostel": hostel_of(u), "updated_at": now},
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "student_id": u["id"], "day": payload.day,
                "meal_type": payload.meal_type, "created_at": now,
            },
        },
        upsert=True,
    )
    return {"ok": True, "reaction": payload.reaction}


@api.get("/student/wastage")
async def student_wastage(
    u: dict = Depends(require_approved_student),
    range: int = Query(7, ge=1, le=365),
    meal: Literal["all", "breakfast", "lunch", "dinner"] = Query("all"),
):
    h = hostel_of(u)
    today = date.fromisoformat(today_iso())
    start = today - timedelta(days=range - 1)
    rows = [r async for r in wastage_col.find(
        {"hostel": h, "date": {"$gte": start.isoformat(), "$lte": today.isoformat()}},
        {"_id": 0},
    ).sort("date", 1)]
    series = []
    for r in rows:
        v = (r.get("breakfast_wastage_kg", 0) + r.get("lunch_wastage_kg", 0) +
             r.get("dinner_wastage_kg", 0)) if meal == "all" else r.get(f"{meal}_wastage_kg", 0)
        series.append({"date": r["date"], "value": round(v, 2)})

    def row(d: date) -> Optional[dict]:
        for r in rows:
            if r["date"] == d.isoformat():
                return r
        return None

    async def fallback(d: date) -> Optional[dict]:
        return row(d) or await wastage_col.find_one(
            {"hostel": h, "date": d.isoformat()}, {"_id": 0}
        )

    today_row = await fallback(today)
    yesterday_row = await fallback(today - timedelta(days=1))
    last_week_row = await fallback(today - timedelta(days=7))

    def total(r: Optional[dict]) -> Optional[float]:
        if not r:
            return None
        return round(r.get("breakfast_wastage_kg", 0) + r.get("lunch_wastage_kg", 0)
                     + r.get("dinner_wastage_kg", 0), 2)

    return {
        "range": range, "meal": meal, "series": series,
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
# Notifications (student + admin)
# ---------------------------------------------------------------------------
def _project_notif(doc: dict, viewer_id: Optional[str] = None) -> dict:
    out = {
        "id": doc["id"], "title": doc["title"], "body": doc["body"],
        "type": doc.get("type", "announcement"),
        "audience": doc.get("audience", "all"),
        "scheduled_for": doc.get("scheduled_for"),
        "created_at": doc["created_at"],
        "read_by_count": len(doc.get("read_by", [])),
    }
    if viewer_id is not None:
        out["read"] = viewer_id in (doc.get("read_by") or [])
    return out


@api.get("/student/notifications")
async def student_notifications(u: dict = Depends(require_approved_student)):
    h = hostel_of(u)
    items = []
    cursor = notifications_col.find(
        {
            "hostel": h,
            "$or": [{"audience": "all"}, {"audience": "student", "recipient_id": u["id"]}],
        },
        {"_id": 0},
    ).sort("created_at", -1).limit(50)
    async for d in cursor:
        items.append(_project_notif(d, viewer_id=u["id"]))
    unread = sum(1 for i in items if not i.get("read"))
    return {"items": items, "unread_count": unread}


@api.post("/student/notifications/{notif_id}/read")
async def mark_notif_read(notif_id: str, u: dict = Depends(require_approved_student)):
    res = await notifications_col.update_one(
        {"id": notif_id, "hostel": hostel_of(u)},
        {"$addToSet": {"read_by": u["id"]}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@api.get("/admin/notifications")
async def admin_notifications(u: dict = Depends(require_admin)):
    items = []
    cursor = notifications_col.find(
        {"hostel": hostel_of(u)}, {"_id": 0}
    ).sort("created_at", -1).limit(100)
    async for d in cursor:
        items.append(_project_notif(d))
    return {"items": items}


@api.post("/admin/notifications", status_code=201)
async def admin_create_notification(
    payload: NotificationCreate, u: dict = Depends(require_admin)
):
    now = now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "hostel": hostel_of(u),
        "title": payload.title.strip(),
        "body": payload.body.strip(),
        "audience": payload.audience,
        "recipient_id": payload.recipient_id,
        "type": payload.type,
        "scheduled_for": payload.scheduled_for or today_iso(),
        "created_by": u["id"],
        "read_by": [],
        "created_at": now,
    }
    await notifications_col.insert_one(doc)
    doc.pop("_id", None)
    return _project_notif(doc)


@api.post("/admin/notifications/menu-reminder", status_code=201)
async def admin_menu_reminder(
    payload: MenuReminderCreate, u: dict = Depends(require_admin)
):
    """Sends a 'tomorrow's menu' reminder to all students of the hostel."""
    h = hostel_of(u)
    tomorrow = (date.fromisoformat(today_iso()) + timedelta(days=1)).isoformat()
    tomorrow_day = day_of_week(date.fromisoformat(tomorrow))
    menu = await menus_col.find_one({"hostel": h, "day": tomorrow_day}, {"_id": 0})
    if not menu:
        raise HTTPException(
            status_code=400,
            detail=f"No menu set for {tomorrow_day}. Add it in Necessary Info first.",
        )
    body = payload.custom_body or (
        f"Tomorrow ({tomorrow_day.capitalize()})\n"
        f"Breakfast: {', '.join(menu.get('breakfast_items', [])) or '—'}\n"
        f"Lunch: {', '.join(menu.get('lunch_items', [])) or '—'}\n"
        f"Dinner: {', '.join(menu.get('dinner_items', [])) or '—'}\n"
        "Mark your meals to help us plan the right quantity."
    )
    doc = {
        "id": str(uuid.uuid4()),
        "hostel": h,
        "title": "Tomorrow's menu",
        "body": body,
        "audience": "all",
        "recipient_id": None,
        "type": "menu_reminder",
        "scheduled_for": tomorrow,
        "created_by": u["id"],
        "read_by": [],
        "created_at": now_iso(),
    }
    await notifications_col.insert_one(doc)
    doc.pop("_id", None)
    return _project_notif(doc)


# ---------------------------------------------------------------------------
# ADMIN: Students
# ---------------------------------------------------------------------------
@api.get("/admin/students/summary")
async def admin_students_summary(u: dict = Depends(require_admin)):
    h = hostel_of(u)
    base = {"role": "student", "institution_or_hostel_name": h}
    return {
        "total_students": await users_col.count_documents(base),
        "approved": await users_col.count_documents({**base, "approval_status": "approved"}),
        "pending": await users_col.count_documents({**base, "approval_status": "pending"}),
        "blocked": await users_col.count_documents({**base, "approval_status": "rejected_or_blocked"}),
    }


@api.get("/admin/students")
async def admin_students_list(
    u: dict = Depends(require_admin),
    status: Literal["all", "pending", "approved", "blocked"] = Query("all"),
):
    q: dict = {"role": "student", "institution_or_hostel_name": hostel_of(u)}
    if status == "pending":
        q["approval_status"] = "pending"
    elif status == "approved":
        q["approval_status"] = "approved"
    elif status == "blocked":
        q["approval_status"] = "rejected_or_blocked"
    items = [s async for s in users_col.find(
        q, {"_id": 0, "password_hash": 0, "push_token": 0}
    ).sort("created_at", -1)]
    return {"students": items, "count": len(items)}


@api.post("/admin/students/{sid}/approve")
async def admin_approve(sid: str, u: dict = Depends(require_admin)):
    res = await users_col.update_one(
        {"id": sid, "role": "student", "institution_or_hostel_name": hostel_of(u)},
        {"$set": {"approval_status": "approved", "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"ok": True}


@api.post("/admin/students/{sid}/reject")
async def admin_reject(sid: str, u: dict = Depends(require_admin)):
    res = await users_col.update_one(
        {"id": sid, "role": "student", "institution_or_hostel_name": hostel_of(u)},
        {"$set": {"approval_status": "rejected_or_blocked", "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"ok": True}


async def _aggregate_meal(hostel: str, meal: MealType, target_date: str, menu: dict) -> dict:
    eating = 0
    not_eating = 0
    item_counts: Dict[str, int] = defaultdict(int)
    reason_counts: Dict[str, int] = defaultdict(int)
    custom_counts: Dict[str, int] = defaultdict(int)
    async for p in daily_plans_col.find(
        {"hostel": hostel, "date": target_date},
        {"_id": 0, meal: 1, "student_id": 1},
    ):
        mp = p.get(meal) or {}
        st = mp.get("status")
        if st == "ON":
            eating += 1
            for it in mp.get("selected_items") or []:
                item_counts[it] += 1
        elif st == "OFF":
            not_eating += 1
            r = (mp.get("reason_if_off") or "").strip()
            if r:
                reason_counts["Other" if r.lower().startswith("other") else r] += 1
        ca = mp.get("custom_answer")
        if ca:
            custom_counts[ca] += 1

    day = day_of_week(date.fromisoformat(target_date))
    like = await menu_reactions_col.count_documents(
        {"hostel": hostel, "day": day, "meal_type": meal, "reaction": "like"}
    )
    dislike = await menu_reactions_col.count_documents(
        {"hostel": hostel, "day": day, "meal_type": meal, "reaction": "dislike"}
    )
    tot = like + dislike
    items_rows = []
    seen = set()
    for it in (menu.get(f"{meal}_items", []) if menu else []):
        items_rows.append({"item_name": it, "count": item_counts.get(it, 0)})
        seen.add(it)
    for k, v in item_counts.items():
        if k not in seen:
            items_rows.append({"item_name": k, "count": v})
    return {
        "menu_items": menu.get(f"{meal}_items", []) if menu else [],
        "custom_question": menu.get(f"{meal}_custom_question") if menu else None,
        "eating_count": eating, "not_eating_count": not_eating,
        "like_count": like, "dislike_count": dislike,
        "like_pct": round(like / tot * 100, 1) if tot else None,
        "dislike_pct": round(dislike / tot * 100, 1) if tot else None,
        "item_counts": items_rows,
        "reason_counts": [{"reason": k, "count": v} for k, v in
                          sorted(reason_counts.items(), key=lambda kv: -kv[1])],
        "custom_answer_counts": [{"answer": k, "count": v} for k, v in
                                 sorted(custom_counts.items(), key=lambda kv: -kv[1])],
    }


@api.get("/admin/today")
async def admin_today(u: dict = Depends(require_admin)):
    h = hostel_of(u)
    today = today_iso()
    day = day_of_week(date.fromisoformat(today))
    menu = await menus_col.find_one({"hostel": h, "day": day}, {"_id": 0}) or {}
    return {
        "date": today, "day": day,
        "total_responses": await daily_plans_col.count_documents(
            {"hostel": h, "date": today}
        ),
        "breakfast": await _aggregate_meal(h, "breakfast", today, menu),
        "lunch": await _aggregate_meal(h, "lunch", today, menu),
        "dinner": await _aggregate_meal(h, "dinner", today, menu),
    }


@api.get("/admin/feedback")
async def admin_feedback(
    u: dict = Depends(require_admin), days: int = Query(7, ge=1, le=90)
):
    since = (date.fromisoformat(today_iso()) - timedelta(days=days - 1)).isoformat()
    items = [r async for r in feedback_col.find(
        {"hostel": hostel_of(u), "date": {"$gte": since}},
        {"_id": 0, "id": 1, "date": 1, "feedback_text": 1, "created_at": 1},
    ).sort("created_at", -1)]
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# ADMIN: Necessary Info
# ---------------------------------------------------------------------------
def _proj_ni(d: dict) -> dict:
    return {
        "id": d["id"], "item_name": d["item_name"], "meal_type": d["meal_type"],
        "quantity_per_person": d["quantity_per_person"], "unit": d["unit"],
        "price_per_unit": d["price_per_unit"], "price_unit": d["price_unit"],
        "updated_at": d.get("updated_at"),
    }


@api.get("/admin/necessary-info")
async def admin_ni_list(u: dict = Depends(require_admin)):
    items = [_proj_ni(r) async for r in necessary_info_col.find(
        {"hostel": hostel_of(u)}, {"_id": 0}
    ).sort("item_name", 1)]
    return {"items": items, "count": len(items)}


@api.post("/admin/necessary-info", status_code=201)
async def admin_ni_create(payload: NecessaryItemInput, u: dict = Depends(require_admin)):
    h = hostel_of(u)
    if await necessary_info_col.find_one(
        {"hostel": h, "item_name": payload.item_name, "meal_type": payload.meal_type},
        {"_id": 0, "id": 1},
    ):
        raise HTTPException(status_code=400, detail="Item already exists for this meal")
    now = now_iso()
    doc = {"id": str(uuid.uuid4()), "hostel": h, **payload.model_dump(),
           "created_at": now, "updated_at": now}
    await necessary_info_col.insert_one(doc)
    doc.pop("_id", None)
    return _proj_ni(doc)


@api.put("/admin/necessary-info/{iid}")
async def admin_ni_update(iid: str, payload: NecessaryItemInput, u: dict = Depends(require_admin)):
    res = await necessary_info_col.update_one(
        {"id": iid, "hostel": hostel_of(u)},
        {"$set": {**payload.model_dump(), "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    doc = await necessary_info_col.find_one({"id": iid}, {"_id": 0})
    return _proj_ni(doc) if doc else {"ok": True}


@api.delete("/admin/necessary-info/{iid}")
async def admin_ni_delete(iid: str, u: dict = Depends(require_admin)):
    res = await necessary_info_col.delete_one({"id": iid, "hostel": hostel_of(u)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# ADMIN: Menus
# ---------------------------------------------------------------------------
@api.get("/admin/menus")
async def admin_menu_list(u: dict = Depends(require_admin)):
    h = hostel_of(u)
    rows = []
    for d in DAYS:
        m = await menus_col.find_one({"hostel": h, "day": d}, {"_id": 0})
        rows.append(project_menu(m) if m else {
            "day": d, "breakfast_items": [], "lunch_items": [], "dinner_items": [],
            "breakfast_custom_question": None, "lunch_custom_question": None,
            "dinner_custom_question": None,
        })
    return {"days": rows}


@api.put("/admin/menus/{day}")
async def admin_menu_upsert(day: str, payload: MenuUpsert, u: dict = Depends(require_admin)):
    if day not in DAYS:
        raise HTTPException(status_code=400, detail="Invalid day")
    h = hostel_of(u)
    now = now_iso()
    body = payload.model_dump()
    await menus_col.update_one(
        {"hostel": h, "day": day},
        {
            "$set": {**body, "updated_at": now, "day": day, "hostel": h},
            "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now},
        },
        upsert=True,
    )
    saved = await menus_col.find_one({"hostel": h, "day": day}, {"_id": 0})
    return project_menu(saved) if saved else {"ok": True}


# ---------------------------------------------------------------------------
# ADMIN: Dashboard
# ---------------------------------------------------------------------------
@api.get("/admin/dashboard")
async def admin_dashboard(u: dict = Depends(require_admin)):
    h = hostel_of(u)
    today = today_iso()
    day = day_of_week(date.fromisoformat(today))
    menu = await menus_col.find_one({"hostel": h, "day": day}, {"_id": 0}) or {}

    ni_lookup: Dict[str, dict] = {}
    async for r in necessary_info_col.find({"hostel": h}, {"_id": 0}):
        ni_lookup[f"{r['meal_type']}:{r['item_name'].lower()}"] = r

    out: Dict[str, Any] = {"date": today, "day": day, "meals": {}}
    most = {"item": None, "count": -1}
    least = {"item": None, "count": 10**9}

    for meal in ("breakfast", "lunch", "dinner"):
        agg = await _aggregate_meal(h, meal, today, menu)  # type: ignore[arg-type]
        items_out, warnings = [], []
        menu_items = menu.get(f"{meal}_items", []) if menu else []
        if not menu_items:
            warnings.append(f"Menu not added for {meal}. Add menu in Necessary Info.")
        for row in agg["item_counts"]:
            ni = ni_lookup.get(f"{meal}:{row['item_name'].lower()}")
            if not ni:
                warnings.append(
                    f"Quantity per person not added for {row['item_name']}."
                )
                items_out.append({
                    "item_name": row["item_name"], "preference_count": row["count"],
                    "quantity_per_person": None, "unit": None,
                    "suggested": None, "display": None,
                })
            else:
                raw = row["count"] * float(ni["quantity_per_person"])
                items_out.append({
                    "item_name": row["item_name"], "preference_count": row["count"],
                    "quantity_per_person": ni["quantity_per_person"], "unit": ni["unit"],
                    "suggested": round(raw, 2), "display": display_quantity(raw, ni["unit"]),
                })
            if row["count"] > most["count"]:
                most = {"item": row["item_name"], "count": row["count"]}
            if 0 < row["count"] < least["count"]:
                least = {"item": row["item_name"], "count": row["count"]}

        if not agg["item_counts"] and not warnings:
            warnings.append("No student responses yet.")

        out["meals"][meal] = {
            "menu_items": menu_items, "eating_count": agg["eating_count"],
            "not_eating_count": agg["not_eating_count"],
            "items": items_out, "warnings": warnings,
        }

    if least["count"] == 10**9:
        least = {"item": None, "count": 0}

    out["summary"] = {
        "breakfast_eating": out["meals"]["breakfast"]["eating_count"],
        "lunch_eating": out["meals"]["lunch"]["eating_count"],
        "dinner_eating": out["meals"]["dinner"]["eating_count"],
        "total_responses": await daily_plans_col.count_documents(
            {"hostel": h, "date": today}
        ),
        "most_demanded": most if most["item"] else None,
        "least_demanded": least if least["item"] else None,
    }
    return out


# ---------------------------------------------------------------------------
# ADMIN: Wastage
# ---------------------------------------------------------------------------
async def _price_for(hostel: str, item_name: str, meal: str) -> Optional[dict]:
    return await necessary_info_col.find_one(
        {"hostel": hostel, "item_name": item_name, "meal_type": meal}, {"_id": 0}
    )


async def _compute_wastage_doc(hostel: str, target_date: str, payload: WastageUpsert) -> dict:
    out: Dict[str, Any] = {
        "hostel": hostel, "date": target_date,
        "breakfast_items": [], "lunch_items": [], "dinner_items": [],
        "breakfast_wastage_kg": 0.0, "lunch_wastage_kg": 0.0, "dinner_wastage_kg": 0.0,
        "breakfast_loss": 0.0, "lunch_loss": 0.0, "dinner_loss": 0.0,
    }
    for meal, items in (("breakfast", payload.breakfast_items),
                       ("lunch", payload.lunch_items),
                       ("dinner", payload.dinner_items)):
        kg = 0.0
        loss = 0.0
        rich = []
        for it in items:
            price = it.price_per_unit
            pu = it.price_unit
            if price is None or pu is None:
                ni = await _price_for(hostel, it.item_name, meal)
                if ni:
                    price = float(ni["price_per_unit"])
                    pu = ni["price_unit"]
            loss_item = 0.0
            if price is not None and pu is not None:
                loss_item = round(normalize_to_price_unit(it.quantity, it.unit, pu) * price, 2)
            kg += to_kg_equiv(it.quantity, it.unit)
            loss += loss_item
            rich.append({
                "item_name": it.item_name, "quantity": float(it.quantity), "unit": it.unit,
                "price_per_unit": price, "price_unit": pu, "loss": loss_item,
            })
        out[f"{meal}_items"] = rich
        out[f"{meal}_wastage_kg"] = round(kg, 2)
        out[f"{meal}_loss"] = round(loss, 2)
    item_loss_total = out["breakfast_loss"] + out["lunch_loss"] + out["dinner_loss"]
    if payload.manual_total_cost is not None:
        out["manual_total_cost"] = round(float(payload.manual_total_cost), 2)
        out["total_loss"] = round(item_loss_total + float(payload.manual_total_cost), 2)
    else:
        out["total_loss"] = round(item_loss_total, 2)
    out["item_loss_total"] = round(item_loss_total, 2)
    return out


@api.put("/admin/wastage/{target_date}")
async def admin_wastage_upsert(
    target_date: str, payload: WastageUpsert, u: dict = Depends(require_admin)
):
    try:
        date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")
    h = hostel_of(u)
    body = await _compute_wastage_doc(h, target_date, payload)
    now = now_iso()
    await wastage_col.update_one(
        {"hostel": h, "date": target_date},
        {"$set": {**body, "updated_at": now},
         "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
        upsert=True,
    )
    saved = await wastage_col.find_one({"hostel": h, "date": target_date}, {"_id": 0})
    return {"ok": True, "wastage": saved}


@api.get("/admin/wastage/today")
async def admin_wastage_today(u: dict = Depends(require_admin)):
    h = hostel_of(u)
    today = today_iso()
    td = date.fromisoformat(today)
    today_doc = await wastage_col.find_one({"hostel": h, "date": today}, {"_id": 0})
    yesterday_doc = await wastage_col.find_one(
        {"hostel": h, "date": (td - timedelta(days=1)).isoformat()}, {"_id": 0}
    )
    last_week_doc = await wastage_col.find_one(
        {"hostel": h, "date": (td - timedelta(days=7)).isoformat()}, {"_id": 0}
    )
    start = (td - timedelta(days=30)).isoformat()
    losses = [r["total_loss"] async for r in wastage_col.find(
        {"hostel": h, "date": {"$gte": start, "$lt": today},
         "total_loss": {"$exists": True, "$gt": 0}},
        {"_id": 0, "total_loss": 1},
    )]
    avg = round(sum(losses) / len(losses), 2) if losses else None
    today_loss = (today_doc or {}).get("total_loss")
    saved = round(avg - today_loss, 2) if avg is not None and today_loss is not None else None
    return {
        "date": today,
        "today": today_doc, "yesterday": yesterday_doc, "last_week_same_day": last_week_doc,
        "average_loss_30d": avg, "saved_amount_vs_avg": saved,
    }


@api.get("/admin/wastage/trend")
async def admin_wastage_trend(
    u: dict = Depends(require_admin),
    range: int = Query(7, ge=1, le=365),
    meal: Literal["all", "breakfast", "lunch", "dinner"] = Query("all"),
):
    h = hostel_of(u)
    today = date.fromisoformat(today_iso())
    start = today - timedelta(days=range - 1)
    rows = [r async for r in wastage_col.find(
        {"hostel": h, "date": {"$gte": start.isoformat(), "$lte": today.isoformat()}},
        {"_id": 0},
    ).sort("date", 1)]
    w_series, s_series, c_series = [], [], []
    losses: List[float] = []
    for r in rows:
        if meal == "all":
            wv = round(r.get("breakfast_wastage_kg", 0) + r.get("lunch_wastage_kg", 0)
                       + r.get("dinner_wastage_kg", 0), 2)
            ls = r.get("total_loss") or (r.get("breakfast_loss", 0) + r.get("lunch_loss", 0)
                                          + r.get("dinner_loss", 0))
        else:
            wv = r.get(f"{meal}_wastage_kg", 0)
            ls = r.get(f"{meal}_loss", 0)
        w_series.append({"date": r["date"], "value": wv})
        c_series.append({"date": r["date"], "value": round(float(ls or 0), 2)})
        if losses:
            saved = round(sum(losses) / len(losses) - float(ls or 0), 2)
        else:
            saved = 0.0
        s_series.append({"date": r["date"], "value": saved})
        if ls:
            losses.append(float(ls))
    return {
        "range": range, "meal": meal,
        "wastage_series": w_series,
        "saved_series": s_series,
        "cost_series": c_series,
    }


# ---------------------------------------------------------------------------
# ADMIN: Settings (per hostel)
# ---------------------------------------------------------------------------
SETTINGS_DEFAULTS = {
    "default_meal_state": "ON",
    "default_like_dislike_state": "no_response",
    "default_preference_state": "none",
    "notifications_enabled": True,
    "language": "English",
}


@api.get("/admin/settings")
async def admin_settings_get(u: dict = Depends(require_admin)):
    h = hostel_of(u)
    doc = await settings_col.find_one({"hostel": h}, {"_id": 0})
    if not doc:
        doc = {"id": h, "hostel": h, **SETTINGS_DEFAULTS, "updated_at": now_iso()}
        await settings_col.insert_one(doc)
        doc.pop("_id", None)
    return doc


@api.put("/admin/settings")
async def admin_settings_put(payload: AppSettingsInput, u: dict = Depends(require_admin)):
    h = hostel_of(u)
    body = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not body:
        raise HTTPException(status_code=400, detail="No fields to update")
    body["updated_at"] = now_iso()
    body["hostel"] = h
    await settings_col.update_one(
        {"hostel": h},
        {"$set": body, "$setOnInsert": {"id": h, **{k: v for k, v in SETTINGS_DEFAULTS.items() if k not in body}}},
        upsert=True,
    )
    return await settings_col.find_one({"hostel": h}, {"_id": 0})


# ---------------------------------------------------------------------------
# Seeding (idempotent)
# ---------------------------------------------------------------------------
SEED_USERS = [
    {"full_name": "Demo Admin", "mobile_or_user_id": "admin", "institution_or_hostel_name": "Demo Hostel", "room_number": None, "password": "admin123", "role": "admin", "approval_status": "approved"},
    {"full_name": "Demo Student", "mobile_or_user_id": "student", "institution_or_hostel_name": "Demo Hostel", "room_number": "A101", "password": "student123", "role": "student", "approval_status": "approved"},
    {"full_name": "Pending Student", "mobile_or_user_id": "pending", "institution_or_hostel_name": "Demo Hostel", "room_number": "B202", "password": "pending123", "role": "student", "approval_status": "pending"},
    {"full_name": "Blocked Student", "mobile_or_user_id": "blocked", "institution_or_hostel_name": "Demo Hostel", "room_number": "C303", "password": "blocked123", "role": "student", "approval_status": "rejected_or_blocked"},
]

SEED_MENUS = [
    {"day": "monday", "breakfast_items": ["Idly", "Dosa", "Sambar", "Chutney"], "lunch_items": ["Rice", "Sambar", "Rasam", "Curd", "Poriyal"], "dinner_items": ["Chapati", "Kurma", "Rice"], "breakfast_custom_question": {"text": "Do you want extra chutney?", "options": ["Yes", "No"]}, "lunch_custom_question": {"text": "Do you want curd rice today?", "options": ["Yes", "No"]}, "dinner_custom_question": {"text": "Which side dish do you prefer?", "options": ["Kurma", "Chutney", "Both"]}},
    {"day": "tuesday", "breakfast_items": ["Pongal", "Vada", "Chutney"], "lunch_items": ["Lemon Rice", "Curd Rice", "Potato Fry"], "dinner_items": ["Dosa", "Sambar", "Chutney"], "breakfast_custom_question": {"text": "Do you want extra chutney?", "options": ["Yes", "No"]}, "lunch_custom_question": None, "dinner_custom_question": None},
    {"day": "wednesday", "breakfast_items": ["Poori", "Masala"], "lunch_items": ["Rice", "Dal", "Rasam", "Curd"], "dinner_items": ["Chapati", "Veg Kurma"], "breakfast_custom_question": None, "lunch_custom_question": {"text": "Do you want curd rice today?", "options": ["Yes", "No"]}, "dinner_custom_question": None},
    {"day": "thursday", "breakfast_items": ["Upma", "Chutney"], "lunch_items": ["Tomato Rice", "Curd", "Poriyal"], "dinner_items": ["Idiyappam", "Kurma"], "breakfast_custom_question": None, "lunch_custom_question": None, "dinner_custom_question": {"text": "Which side dish do you prefer?", "options": ["Kurma", "Chutney", "Both"]}},
    {"day": "friday", "breakfast_items": ["Idly", "Sambar"], "lunch_items": ["Veg Biryani", "Raita"], "dinner_items": ["Parotta", "Kurma"], "breakfast_custom_question": None, "lunch_custom_question": None, "dinner_custom_question": None},
    {"day": "saturday", "breakfast_items": ["Dosa", "Chutney"], "lunch_items": ["Rice", "Sambar", "Appalam", "Curd"], "dinner_items": ["Fried Rice", "Gobi"], "breakfast_custom_question": None, "lunch_custom_question": None, "dinner_custom_question": None},
    {"day": "sunday", "breakfast_items": ["Pongal", "Vada"], "lunch_items": ["Special Meals"], "dinner_items": ["Chapati", "Paneer Gravy"], "breakfast_custom_question": None, "lunch_custom_question": None, "dinner_custom_question": None},
]

SEED_NI = [
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


async def _ensure_indexes_and_migrate():
    """Drop legacy indexes & rebuild as hostel-scoped, then backfill hostel field."""
    # users
    await users_col.create_index("id", unique=True)
    await users_col.create_index(
        [("mobile_or_user_id", 1), ("institution_or_hostel_name", 1)], unique=True
    )
    # menus
    try:
        idxs = await menus_col.index_information()
        if "day_1" in idxs:
            await menus_col.drop_index("day_1")
    except Exception:
        pass
    await menus_col.create_index(
        [("hostel", 1), ("day", 1)], unique=True
    )
    # daily_plans
    await daily_plans_col.create_index(
        [("student_id", 1), ("date", 1)], unique=True
    )
    await daily_plans_col.create_index([("hostel", 1), ("date", 1)])
    # menu_reactions
    await menu_reactions_col.create_index(
        [("student_id", 1), ("day", 1), ("meal_type", 1)], unique=True
    )
    # feedback
    await feedback_col.create_index([("hostel", 1), ("date", -1)])
    # wastage
    try:
        idxs = await wastage_col.index_information()
        if "date_1" in idxs:
            await wastage_col.drop_index("date_1")
    except Exception:
        pass
    await wastage_col.create_index([("hostel", 1), ("date", 1)], unique=True)
    # necessary_info
    try:
        idxs = await necessary_info_col.index_information()
        if "item_name_1_meal_type_1" in idxs:
            await necessary_info_col.drop_index("item_name_1_meal_type_1")
    except Exception:
        pass
    await necessary_info_col.create_index(
        [("hostel", 1), ("item_name", 1), ("meal_type", 1)], unique=True
    )
    # app_settings
    try:
        idxs = await settings_col.index_information()
        if "id_1" in idxs:
            await settings_col.drop_index("id_1")
    except Exception:
        pass
    await settings_col.create_index("hostel", unique=True)
    # notifications
    await notifications_col.create_index([("hostel", 1), ("created_at", -1)])

    # Drop legacy users unique-on-mobile-only if present
    try:
        idxs = await users_col.index_information()
        if "mobile_or_user_id_1" in idxs:
            await users_col.drop_index("mobile_or_user_id_1")
    except Exception:
        pass

    # Backfill hostel field on legacy docs
    for col in (menus_col, daily_plans_col, menu_reactions_col,
                feedback_col, wastage_col, necessary_info_col):
        await col.update_many({"hostel": {"$exists": False}},
                              {"$set": {"hostel": DEFAULT_HOSTEL}})
    # Settings legacy id="app"
    legacy = await settings_col.find_one({"id": "app", "hostel": {"$exists": False}}, {"_id": 0})
    if legacy:
        await settings_col.update_one(
            {"id": "app"},
            {"$set": {"hostel": DEFAULT_HOSTEL, "id": DEFAULT_HOSTEL}},
        )


async def seed_demo_users():
    now = now_iso()
    for u in SEED_USERS:
        if await users_col.find_one(
            {"mobile_or_user_id": u["mobile_or_user_id"],
             "institution_or_hostel_name": u["institution_or_hostel_name"]},
            {"_id": 0, "id": 1},
        ):
            continue
        await users_col.insert_one({
            "id": str(uuid.uuid4()),
            **{k: u[k] for k in ("full_name", "mobile_or_user_id",
                                  "institution_or_hostel_name", "room_number",
                                  "role", "approval_status")},
            "password_hash": hash_password(u["password"]),
            "created_at": now, "updated_at": now,
        })


async def seed_extra_students():
    now = now_iso()
    pwd = hash_password("demopass")
    for tag, n, prefix, status in (
        ("approved", 28, "DemoStudent", "approved"),
        ("pending", 4, "DemoPending", "pending"),
        ("blocked", 4, "DemoBlocked", "rejected_or_blocked"),
    ):
        for i in range(1, n + 1):
            mobile = f"{tag}{i:03d}"
            if await users_col.find_one(
                {"mobile_or_user_id": mobile, "institution_or_hostel_name": DEFAULT_HOSTEL},
                {"_id": 0, "id": 1},
            ):
                continue
            await users_col.insert_one({
                "id": str(uuid.uuid4()), "full_name": f"{prefix} {i}",
                "mobile_or_user_id": mobile, "institution_or_hostel_name": DEFAULT_HOSTEL,
                "room_number": f"{chr(ord('A') + (i % 5))}{100 + i}",
                "password_hash": pwd, "role": "student", "approval_status": status,
                "created_at": now, "updated_at": now,
            })


async def seed_today_plans():
    today = today_iso()
    day = day_of_week(date.fromisoformat(today))
    menu = await menus_col.find_one({"hostel": DEFAULT_HOSTEL, "day": day}, {"_id": 0})
    if not menu:
        return
    rnd = random.Random(today)
    sids = [u["id"] async for u in users_col.find(
        {"role": "student", "approval_status": "approved",
         "institution_or_hostel_name": DEFAULT_HOSTEL}, {"_id": 0, "id": 1}
    )]
    def pick(items: List[str]) -> List[str]:
        return [] if not items else rnd.sample(items, rnd.randint(1, len(items)))
    for sid in sids:
        if await daily_plans_col.find_one(
            {"student_id": sid, "date": today}, {"_id": 0, "id": 1}
        ):
            continue
        plan: Dict[str, Any] = {
            "id": str(uuid.uuid4()), "student_id": sid, "hostel": DEFAULT_HOSTEL,
            "date": today, "created_at": now_iso(), "updated_at": now_iso(),
        }
        for meal in ("breakfast", "lunch", "dinner"):
            on = rnd.random() > 0.25
            items = menu.get(f"{meal}_items", [])
            cq = menu.get(f"{meal}_custom_question")
            plan[meal] = {
                "status": "ON" if on else "OFF",
                "selected_items": pick(items) if on else [],
                "reason_if_off": None if on else rnd.choice(REASONS[:6]),
                "custom_answer": (rnd.choice(cq["options"]) if (cq and on) else None),
            }
        await daily_plans_col.insert_one(plan)


async def seed_reactions():
    today = today_iso()
    day = day_of_week(date.fromisoformat(today))
    rnd = random.Random(day)
    sids = [u["id"] async for u in users_col.find(
        {"role": "student", "approval_status": "approved",
         "institution_or_hostel_name": DEFAULT_HOSTEL}, {"_id": 0, "id": 1}
    )]
    for sid in sids:
        for meal in ("breakfast", "lunch", "dinner"):
            if await menu_reactions_col.find_one(
                {"student_id": sid, "day": day, "meal_type": meal},
                {"_id": 0, "id": 1},
            ):
                continue
            roll = rnd.random()
            reaction = "no_response" if roll < 0.10 else ("dislike" if roll < 0.30 else "like")
            await menu_reactions_col.insert_one({
                "id": str(uuid.uuid4()), "student_id": sid, "hostel": DEFAULT_HOSTEL,
                "day": day, "meal_type": meal, "reaction": reaction,
                "created_at": now_iso(), "updated_at": now_iso(),
            })


async def seed_feedback():
    today = today_iso()
    if await feedback_col.count_documents({"hostel": DEFAULT_HOSTEL, "date": today}) >= 7:
        return
    sids = [u["id"] async for u in users_col.find(
        {"role": "student", "approval_status": "approved",
         "institution_or_hostel_name": DEFAULT_HOSTEL}, {"_id": 0, "id": 1}
    )]
    if not sids:
        return
    rnd = random.Random("fb-" + today)
    for text in [
        "Lunch was too spicy today", "Please add curd rice twice a week",
        "Breakfast quantity was low", "Dinner was really good today, thanks!",
        "Sambar could be a bit less salty", "Loved the parotta on Friday",
        "Please serve hot chapatis",
    ]:
        await feedback_col.insert_one({
            "id": str(uuid.uuid4()), "student_id": rnd.choice(sids),
            "hostel": DEFAULT_HOSTEL, "date": today,
            "feedback_text": text, "anonymous": True, "created_at": now_iso(),
        })


async def seed_menus():
    now = now_iso()
    for m in SEED_MENUS:
        await menus_col.update_one(
            {"hostel": DEFAULT_HOSTEL, "day": m["day"]},
            {
                "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now,
                                 "day": m["day"], "hostel": DEFAULT_HOSTEL},
                "$set": {k: m[k] for k in (
                    "breakfast_items", "lunch_items", "dinner_items",
                    "breakfast_custom_question", "lunch_custom_question",
                    "dinner_custom_question",
                )} | {"updated_at": now},
            },
            upsert=True,
        )


async def seed_necessary_info():
    now = now_iso()
    for item in SEED_NI:
        if await necessary_info_col.find_one(
            {"hostel": DEFAULT_HOSTEL, "item_name": item["item_name"],
             "meal_type": item["meal_type"]}, {"_id": 0, "id": 1},
        ):
            continue
        await necessary_info_col.insert_one({
            "id": str(uuid.uuid4()), "hostel": DEFAULT_HOSTEL, **item,
            "created_at": now, "updated_at": now,
        })


async def seed_wastage():
    today = date.fromisoformat(today_iso())
    rnd = random.Random(42)
    bulk = []
    for off in range(95):
        d = today - timedelta(days=off)
        if await wastage_col.find_one({"hostel": DEFAULT_HOSTEL, "date": d.isoformat()}, {"_id": 0}):
            continue
        p = off / 95.0
        b = round(max(0.5, 2.5 + p * 3.0 + rnd.uniform(-0.6, 0.6)), 2)
        lun = round(max(0.5, 4.5 + p * 3.5 + rnd.uniform(-0.7, 0.7)), 2)
        dn = round(max(0.5, 3.5 + p * 3.0 + rnd.uniform(-0.6, 0.6)), 2)
        bl = round(max(0.0, b * 60 + rnd.uniform(-30, 30)), 2)
        ll = round(max(0.0, lun * 60 + rnd.uniform(-30, 30)), 2)
        dl = round(max(0.0, dn * 60 + rnd.uniform(-30, 30)), 2)
        item_total = bl + ll + dl
        manual = round(rnd.uniform(50, 250), 2) if off < 30 else None
        bulk.append({
            "id": str(uuid.uuid4()), "hostel": DEFAULT_HOSTEL, "date": d.isoformat(),
            "breakfast_items": [], "lunch_items": [], "dinner_items": [],
            "breakfast_wastage_kg": b, "lunch_wastage_kg": lun, "dinner_wastage_kg": dn,
            "breakfast_loss": bl, "lunch_loss": ll, "dinner_loss": dl,
            "item_loss_total": round(item_total, 2),
            "manual_total_cost": manual,
            "total_loss": round(item_total + (manual or 0.0), 2),
            "created_at": now_iso(),
        })
    if bulk:
        await wastage_col.insert_many(bulk)


async def seed_settings():
    if not await settings_col.find_one({"hostel": DEFAULT_HOSTEL}, {"_id": 0}):
        await settings_col.insert_one({
            "id": DEFAULT_HOSTEL, "hostel": DEFAULT_HOSTEL,
            **SETTINGS_DEFAULTS, "created_at": now_iso(), "updated_at": now_iso(),
        })


async def seed_notifications():
    h = DEFAULT_HOSTEL
    if await notifications_col.count_documents({"hostel": h}) >= 2:
        return
    today = today_iso()
    samples = [
        {"title": "Welcome to MessMate", "body": "Mark your meals each day to help the mess prepare the right quantity.", "type": "system"},
        {"title": "Tomorrow's menu", "body": "Tomorrow's menu has been published. Tap to view and mark your preferences.", "type": "menu_reminder"},
    ]
    for s in samples:
        await notifications_col.insert_one({
            "id": str(uuid.uuid4()), "hostel": h, **s,
            "audience": "all", "recipient_id": None,
            "scheduled_for": today, "read_by": [],
            "created_by": "system", "created_at": now_iso(),
        })


@app.on_event("startup")
async def on_startup():
    await _ensure_indexes_and_migrate()
    await seed_demo_users()
    await seed_extra_students()
    await seed_menus()
    await seed_necessary_info()
    await seed_today_plans()
    await seed_reactions()
    await seed_feedback()
    await seed_wastage()
    await seed_settings()
    await seed_notifications()
    logger.info("MessMate API ready (multi-tenant)")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# ---------------------------------------------------------------------------
# Mount + CORS
# ---------------------------------------------------------------------------
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
