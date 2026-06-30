"""MessMate backend — Part 1: Auth & Role-Based Entry + Part 2: Student Side."""

import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
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
    reason_if_off: Optional[str] = None  # one of REASONS or "Other: <text>"
    custom_answer: Optional[str] = None


class DailyPlanUpsert(BaseModel):
    date: Optional[str] = None  # ISO yyyy-mm-dd; defaults to today (server)
    breakfast: MealPlanInput = Field(default_factory=MealPlanInput)
    lunch: MealPlanInput = Field(default_factory=MealPlanInput)
    dinner: MealPlanInput = Field(default_factory=MealPlanInput)


class ReactionUpsert(BaseModel):
    day: str  # "monday".."sunday"
    meal_type: MealType
    reaction: Reaction


class FeedbackInput(BaseModel):
    feedback_text: str = Field(..., min_length=1, max_length=2000)


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
    # Validate date format
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
    insert_doc = {
        "id": str(uuid.uuid4()),
        "created_at": now,
    }
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
        if m:
            docs.append(project_menu(m))
        else:
            docs.append(
                {
                    "day": d,
                    "breakfast_items": [],
                    "lunch_items": [],
                    "dinner_items": [],
                    "breakfast_custom_question": None,
                    "lunch_custom_question": None,
                    "dinner_custom_question": None,
                }
            )

    # Attach student's reactions per (day, meal_type)
    cursor = menu_reactions_col.find(
        {"student_id": current["id"]},
        {"_id": 0, "day": 1, "meal_type": 1, "reaction": 1},
    )
    reactions_map: Dict[str, str] = {}
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
    # Placeholder: weekly menu repeated as 4 weeks (real per-date menus arrive later).
    week = await student_menu_week(current)  # type: ignore[arg-type]
    return {"weeks": [{"label": f"Week {i + 1}", "days": week["days"]} for i in range(4)]}


@api.put("/student/menu/reaction")
async def upsert_reaction(
    payload: ReactionUpsert,
    current: dict = Depends(require_approved_student),
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
            "$set": {
                "reaction": payload.reaction,
                "updated_at": now,
            },
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

    # Summary cards
    by_date = {r["date"]: r for r in rows}
    today_row = by_date.get(today.isoformat())
    yesterday_row = by_date.get((today - timedelta(days=1)).isoformat())
    last_week_row = by_date.get((today - timedelta(days=7)).isoformat())

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
        "breakfast_custom_question": {
            "text": "Do you want extra chutney?",
            "options": ["Yes", "No"],
        },
        "lunch_custom_question": None,
        "dinner_custom_question": None,
    },
    {
        "day": "wednesday",
        "breakfast_items": ["Poori", "Masala"],
        "lunch_items": ["Rice", "Dal", "Rasam", "Curd"],
        "dinner_items": ["Chapati", "Veg Kurma"],
        "breakfast_custom_question": None,
        "lunch_custom_question": {
            "text": "Do you want curd rice today?",
            "options": ["Yes", "No"],
        },
        "dinner_custom_question": None,
    },
    {
        "day": "thursday",
        "breakfast_items": ["Upma", "Chutney"],
        "lunch_items": ["Tomato Rice", "Curd", "Poriyal"],
        "dinner_items": ["Idiyappam", "Kurma"],
        "breakfast_custom_question": None,
        "lunch_custom_question": None,
        "dinner_custom_question": {
            "text": "Which side dish do you prefer?",
            "options": ["Kurma", "Chutney", "Both"],
        },
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


async def seed_wastage():
    """Seed last 95 days of synthetic wastage so the chart has data."""
    today = date.fromisoformat(today_iso())
    rnd = random.Random(42)  # deterministic
    bulk_inserts = []
    for offset in range(95):
        d = today - timedelta(days=offset)
        existing = await wastage_col.find_one({"date": d.isoformat()}, {"_id": 0})
        if existing:
            continue
        # Slight downward trend over 95 days (lower = more recent) with jitter.
        progress = offset / 95.0  # 0 today, 1 oldest
        base_b = 2.5 + progress * 3.0 + rnd.uniform(-0.6, 0.6)
        base_l = 4.5 + progress * 3.5 + rnd.uniform(-0.7, 0.7)
        base_d = 3.5 + progress * 3.0 + rnd.uniform(-0.6, 0.6)
        bulk_inserts.append(
            {
                "id": str(uuid.uuid4()),
                "date": d.isoformat(),
                "breakfast_wastage_kg": round(max(0.5, base_b), 2),
                "lunch_wastage_kg": round(max(0.5, base_l), 2),
                "dinner_wastage_kg": round(max(0.5, base_d), 2),
                "created_at": now_iso(),
            }
        )
    if bulk_inserts:
        await wastage_col.insert_many(bulk_inserts)
        logger.info("Seeded %d wastage rows", len(bulk_inserts))


@app.on_event("startup")
async def on_startup():
    await users_col.create_index("mobile_or_user_id", unique=True)
    await users_col.create_index("id", unique=True)
    await menus_col.create_index("day", unique=True)
    await daily_plans_col.create_index([("student_id", 1), ("date", 1)], unique=True)
    await menu_reactions_col.create_index(
        [("student_id", 1), ("day", 1), ("meal_type", 1)], unique=True
    )
    await wastage_col.create_index("date", unique=True)
    await seed_demo_users()
    await seed_menus()
    await seed_wastage()
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
