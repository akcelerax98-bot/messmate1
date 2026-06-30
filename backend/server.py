"""MessMate backend — Auth + Student + Admin + Notifications.

Multi-tenant: every domain doc is scoped by `hostel` (institution_or_hostel_name).
Two-step login with mocked OTP. In-app notifications + push token capture.
"""

import asyncio
import logging
import os
import secrets
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx
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

# SMTP Email
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASS = os.environ.get("SMTP_PASS", "").strip()
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER).strip()
FROM_NAME = os.environ.get("FROM_NAME", "MessMate").strip() or "MessMate"
SMTP_CONFIGURED = all([SMTP_HOST, SMTP_USER, SMTP_PASS, FROM_EMAIL])

# OTP config
OTP_LENGTH = int(os.environ.get("OTP_LENGTH", "6"))
OTP_EXPIRY_MIN = int(os.environ.get("OTP_EXPIRY_MIN", "5"))
OTP_RESEND_INTERVAL_SEC = int(os.environ.get("OTP_RESEND_INTERVAL_SEC", "60"))
OTP_MAX_VERIFY_ATTEMPTS = int(os.environ.get("OTP_MAX_VERIFY_ATTEMPTS", "5"))
RESET_TOKEN_EXPIRY_MIN = int(os.environ.get("RESET_TOKEN_EXPIRY_MIN", "10"))

# Emergent Push Notifications
EMERGENT_PUSH_BASE_URL = "https://integrations.emergentagent.com"
EMERGENT_PUSH_KEY = os.environ.get("EMERGENT_PUSH_KEY", "placeholder")

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
email_otps_col = db["email_otps"]
push_tokens_col = db["push_tokens"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Shared async HTTP client (push relay).
_push_client: Optional[httpx.AsyncClient] = None


def get_push_client() -> httpx.AsyncClient:
    global _push_client
    if _push_client is None:
        _push_client = httpx.AsyncClient(
            base_url=EMERGENT_PUSH_BASE_URL,
            headers={"X-Push-Key": EMERGENT_PUSH_KEY},
            timeout=10.0,
        )
    return _push_client

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
    """LEGACY \u2014 still accepted to keep old endpoints alive. Prefer /auth/register."""
    full_name: str = Field(..., min_length=1, max_length=120)
    mobile_or_user_id: str = Field(..., min_length=3, max_length=60)
    institution_or_hostel_name: str = Field(..., min_length=1, max_length=120)
    room_number: Optional[str] = Field(default=None, max_length=40)
    password: str = Field(..., min_length=6, max_length=128)
    email: Optional[str] = None


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=4, max_length=200)
    password: str = Field(..., min_length=6, max_length=128)
    confirm_password: Optional[str] = None
    institution_or_hostel_name: str = Field(..., min_length=1, max_length=120)
    role: Optional[Literal["student", "admin"]] = "student"


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=4, max_length=200)
    password: str = Field(..., min_length=1)


class VerifyEmailRequest(BaseModel):
    email: str
    otp: str = Field(..., min_length=4, max_length=10)


class ResendOtpEmailRequest(BaseModel):
    email: str
    purpose: Literal["registration", "forgot_password"] = "registration"


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=4, max_length=200)


class ForgotPasswordVerifyRequest(BaseModel):
    email: str
    otp: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(..., min_length=6, max_length=128)
    confirm_password: Optional[str] = None


class UserPublic(BaseModel):
    id: str
    full_name: str
    email: str
    mobile_or_user_id: Optional[str] = None  # legacy passthrough
    institution_or_hostel_name: str
    room_number: Optional[str] = None
    role: Role
    approval_status: ApprovalStatus
    email_verified: bool = False
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
    reminder_times: Optional[List[str]] = None  # e.g. ["07:00", "11:30", "18:00"]


class PushTokenInput(BaseModel):
    push_token: str = Field(..., min_length=1, max_length=600)
    platform: Optional[Literal["ios", "android", "web"]] = None


class RegisterPushBody(BaseModel):
    user_id: str
    platform: Literal["ios", "android", "web"]
    device_token: str = Field(..., min_length=4, max_length=600)


class ReminderDispatchInput(BaseModel):
    audience: Literal["student", "admin", "all"] = "student"
    title: Optional[str] = None
    body: Optional[str] = None


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
        email=d.get("email") or d.get("mobile_or_user_id", ""),
        mobile_or_user_id=d.get("mobile_or_user_id"),
        institution_or_hostel_name=d["institution_or_hostel_name"],
        room_number=d.get("room_number"),
        role=d["role"],
        approval_status=d["approval_status"],
        email_verified=bool(d.get("email_verified", False)),
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
# SMTP — Email OTP delivery
# ---------------------------------------------------------------------------
import re as _re
import smtplib as _smtplib
from email.message import EmailMessage as _EmailMessage
from email.utils import formataddr as _formataddr
from fastapi.concurrency import run_in_threadpool as _run_in_threadpool

EMAIL_RE = _re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def is_valid_email(s: str) -> bool:
    return bool(s) and bool(EMAIL_RE.match(s.strip()))


def normalize_email(s: str) -> str:
    return (s or "").strip().lower()


def gen_otp() -> str:
    """Cryptographically secure N-digit OTP."""
    n = max(4, OTP_LENGTH)
    upper = 10 ** n
    return f"{secrets.randbelow(upper):0{n}d}"


def _build_registration_email(user_name: str, otp: str) -> _EmailMessage:
    msg = _EmailMessage()
    msg["Subject"] = "Verify Your Email Address"
    msg["From"] = _formataddr((FROM_NAME, FROM_EMAIL))
    # `To` is set by send_email_otp
    text = (
        f"Hello {user_name},\n\n"
        f"Welcome to MessMate.\n\n"
        f"Your verification code is:\n\n"
        f"{otp}\n\n"
        f"This code is valid for {OTP_EXPIRY_MIN} minutes.\n\n"
        f"If you did not request this account, please ignore this email.\n\n"
        f"Thank you."
    )
    html = (
        f"<div style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
        f"max-width:520px;margin:auto;padding:32px;color:#0B1220\">"
        f"<h2 style=\"margin:0 0 16px\">Verify your email</h2>"
        f"<p>Hello <strong>{user_name}</strong>,</p>"
        f"<p>Welcome to <strong>MessMate</strong>. Your verification code is:</p>"
        f"<div style=\"font-size:32px;font-weight:700;letter-spacing:8px;"
        f"background:#EAFBF0;color:#15803D;padding:16px 24px;border-radius:12px;"
        f"text-align:center;margin:24px 0\">{otp}</div>"
        f"<p style=\"color:#5B6675\">This code is valid for {OTP_EXPIRY_MIN} minutes.</p>"
        f"<p style=\"color:#5B6675;font-size:13px\">If you did not request this account, "
        f"please ignore this email.</p>"
        f"<hr style=\"border:none;border-top:1px solid #E5E7EB;margin:24px 0\" />"
        f"<p style=\"color:#9CA3AF;font-size:12px\">— MessMate</p>"
        f"</div>"
    )
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def _build_forgot_email(user_name: str, otp: str) -> _EmailMessage:
    msg = _EmailMessage()
    msg["Subject"] = "Password Reset Verification Code"
    msg["From"] = _formataddr((FROM_NAME, FROM_EMAIL))
    text = (
        f"Hello {user_name},\n\n"
        f"Your password reset code is:\n\n"
        f"{otp}\n\n"
        f"This code is valid for {OTP_EXPIRY_MIN} minutes.\n\n"
        f"If you did not request this password reset, please ignore this email.\n\n"
        f"Thank you."
    )
    html = (
        f"<div style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
        f"max-width:520px;margin:auto;padding:32px;color:#0B1220\">"
        f"<h2 style=\"margin:0 0 16px\">Password reset</h2>"
        f"<p>Hello <strong>{user_name}</strong>,</p>"
        f"<p>Your password reset code is:</p>"
        f"<div style=\"font-size:32px;font-weight:700;letter-spacing:8px;"
        f"background:#FEF2F2;color:#B91C1C;padding:16px 24px;border-radius:12px;"
        f"text-align:center;margin:24px 0\">{otp}</div>"
        f"<p style=\"color:#5B6675\">This code is valid for {OTP_EXPIRY_MIN} minutes.</p>"
        f"<p style=\"color:#5B6675;font-size:13px\">If you did not request a password reset, "
        f"please ignore this email.</p>"
        f"<hr style=\"border:none;border-top:1px solid #E5E7EB;margin:24px 0\" />"
        f"<p style=\"color:#9CA3AF;font-size:12px\">— MessMate</p>"
        f"</div>"
    )
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def _smtp_send_sync(to: str, msg: _EmailMessage) -> None:
    msg["To"] = to
    # Use STARTTLS on 587 (Gmail). Use SSL on 465.
    if SMTP_PORT == 465:
        with _smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
    else:
        with _smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)


async def send_email_otp(
    *, to: str, user_name: str, otp: str, purpose: str
) -> bool:
    """Send an OTP via SMTP. Returns True on success, False on failure.

    When SMTP is NOT configured, we log the OTP to backend stdout (dev mode).
    """
    if not SMTP_CONFIGURED:
        logger.warning(
            "[DEV-OTP] purpose=%s to=%s otp=%s (SMTP not configured — set SMTP_HOST/USER/PASS)",
            purpose, to, otp,
        )
        return True
    builder = _build_forgot_email if purpose == "forgot_password" else _build_registration_email
    msg = builder(user_name, otp)
    try:
        await _run_in_threadpool(_smtp_send_sync, to, msg)
        return True
    except Exception as e:
        logger.error("SMTP send failed to=%s purpose=%s err=%s", to, purpose, e)
        return False


# ---------------------------------------------------------------------------
# Email OTP store
# ---------------------------------------------------------------------------
async def store_email_otp(*, email: str, purpose: str, otp: str) -> None:
    """Hash + upsert. ALWAYS replaces any existing OTP for this (email, purpose)."""
    now_dt = datetime.now(timezone.utc)
    await email_otps_col.update_one(
        {"email": email, "purpose": purpose},
        {"$set": {
            "email": email,
            "purpose": purpose,
            "otp_hash": pwd_context.hash(otp),
            "created_at": now_dt.isoformat(),
            "expires_at": (now_dt + timedelta(minutes=OTP_EXPIRY_MIN)).isoformat(),
            "verified": False,
            "attempts": 0,
        }},
        upsert=True,
    )


async def consume_email_otp(*, email: str, purpose: str, submitted: str) -> Dict[str, Any]:
    """Returns {ok, error?, doc?}.

    - ok=True only on exact match + not expired + not over-attempted.
    - Side effects: increments attempts on miss; deletes on success.
    """
    doc = await email_otps_col.find_one({"email": email, "purpose": purpose})
    if not doc:
        return {"ok": False, "error": "Invalid OTP"}
    # Expiry
    try:
        exp = datetime.fromisoformat(doc["expires_at"])
    except Exception:
        exp = datetime.now(timezone.utc) - timedelta(seconds=1)
    if exp <= datetime.now(timezone.utc):
        await email_otps_col.delete_one({"_id": doc["_id"]})
        return {"ok": False, "error": "OTP expired"}
    # Attempts
    if doc.get("attempts", 0) >= OTP_MAX_VERIFY_ATTEMPTS:
        await email_otps_col.delete_one({"_id": doc["_id"]})
        return {"ok": False, "error": "Too many attempts. Please request a new OTP."}
    # Match
    try:
        match = pwd_context.verify(submitted.strip(), doc["otp_hash"])
    except Exception:
        match = False
    if not match:
        await email_otps_col.update_one({"_id": doc["_id"]}, {"$inc": {"attempts": 1}})
        return {"ok": False, "error": "Invalid OTP"}
    # Success — delete it immediately
    await email_otps_col.delete_one({"_id": doc["_id"]})
    return {"ok": True, "doc": doc}


async def can_resend_otp(*, email: str, purpose: str) -> Optional[int]:
    """If still within cooldown, returns seconds remaining; else None."""
    doc = await email_otps_col.find_one({"email": email, "purpose": purpose})
    if not doc:
        return None
    try:
        created = datetime.fromisoformat(doc["created_at"])
    except Exception:
        return None
    elapsed = (datetime.now(timezone.utc) - created).total_seconds()
    if elapsed < OTP_RESEND_INTERVAL_SEC:
        return int(OTP_RESEND_INTERVAL_SEC - elapsed)
    return None


async def purge_expired_otps() -> int:
    cutoff = datetime.now(timezone.utc).isoformat()
    res = await email_otps_col.delete_many({"expires_at": {"$lt": cutoff}})
    return getattr(res, "deleted_count", 0)


# ---------------------------------------------------------------------------
# Emergent Push helper
# ---------------------------------------------------------------------------
async def send_push(
    recipients: List[str],
    data: Dict[str, Any],
    idempotency_key: Optional[str] = None,
) -> None:
    """Fire a push notification via the Emergent relay. Safe to call w/ empty list."""
    if not recipients:
        return
    if "title" not in data or "message" not in data:
        raise ValueError("push data must include title and message")
    cli = get_push_client()
    for i in range(0, len(recipients), 100):
        chunk = recipients[i:i + 100]
        payload: Dict[str, Any] = {"recipients": chunk, "data": data}
        if idempotency_key:
            payload["$idempotency_key"] = f"{idempotency_key}-{i // 100}"
        try:
            resp = await cli.post("/api/v1/push/trigger", json=payload)
            if resp.status_code == 401:
                logger.warning("EMERGENT_PUSH_KEY missing or invalid (push skipped)")
                return
            if resp.status_code >= 400:
                logger.warning("push trigger %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("push trigger failed (non-blocking): %s", e)


# ---------------------------------------------------------------------------
# Auth — Email OTP
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"app": "MessMate", "status": "ok"}


@api.post("/auth/register", response_model=Dict[str, Any], status_code=201)
async def register(payload: RegisterRequest):
    """Create unverified account + send email OTP."""
    email = normalize_email(payload.email)
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if payload.confirm_password is not None and payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    await purge_expired_otps()

    existing = await users_col.find_one({"email": email}, {"_id": 0})
    if existing:
        if existing.get("email_verified"):
            raise HTTPException(status_code=400, detail="Email already registered")
        # Unverified: refresh details + resend OTP (don't fail)
        now = now_iso()
        await users_col.update_one(
            {"id": existing["id"]},
            {"$set": {
                "full_name": payload.full_name.strip(),
                "institution_or_hostel_name": payload.institution_or_hostel_name.strip(),
                "password_hash": hash_password(payload.password),
                "updated_at": now,
            }},
        )
        user_doc = await users_col.find_one({"id": existing["id"]}, {"_id": 0})
    else:
        now = now_iso()
        role = payload.role or "student"
        # First admin to register for a brand-new institution auto-approves; otherwise pending.
        is_first_admin = False
        if role == "admin":
            count = await users_col.count_documents({
                "role": "admin",
                "institution_or_hostel_name": payload.institution_or_hostel_name.strip(),
            })
            is_first_admin = count == 0
        user_doc = {
            "id": str(uuid.uuid4()),
            "full_name": payload.full_name.strip(),
            "email": email,
            # legacy: keep mobile_or_user_id as a duplicate of email for downstream code
            "mobile_or_user_id": email,
            "institution_or_hostel_name": payload.institution_or_hostel_name.strip(),
            "password_hash": hash_password(payload.password),
            "role": role,
            "approval_status": "approved" if (role == "admin" and is_first_admin) else ("pending" if role == "student" else "approved"),
            "email_verified": False,
            "created_at": now,
            "updated_at": now,
        }
        await users_col.insert_one(user_doc)

    # Throttle: only mint a new OTP if cooldown elapsed
    wait_s = await can_resend_otp(email=email, purpose="registration")
    if wait_s is not None:
        # Don't reveal the OTP; ask user to wait
        return {
            "status": "verification_required",
            "email": email,
            "resend_available_in": wait_s,
            "message": "Verification code already sent. Check your inbox.",
        }

    otp = gen_otp()
    await store_email_otp(email=email, purpose="registration", otp=otp)
    ok = await send_email_otp(
        to=email, user_name=user_doc["full_name"], otp=otp, purpose="registration",
    )
    if not ok and SMTP_CONFIGURED:
        # roll back OTP record so user can retry
        await email_otps_col.delete_one({"email": email, "purpose": "registration"})
        raise HTTPException(status_code=502, detail="Could not send verification email. Please try again.")
    return {
        "status": "verification_required",
        "email": email,
        "resend_available_in": OTP_RESEND_INTERVAL_SEC,
        "expires_in": OTP_EXPIRY_MIN * 60,
    }


@api.post("/auth/verify-email", response_model=TokenResponse)
async def verify_email(payload: VerifyEmailRequest):
    """Verify the registration OTP → mark verified → auto-login."""
    email = normalize_email(payload.email)
    user = await users_col.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    if user.get("email_verified"):
        # Re-issue access token rather than failing.
        token = create_token({"sub": user["id"], "role": user["role"],
                              "status": user["approval_status"]})
        return TokenResponse(access_token=token, user=to_public(user))

    result = await consume_email_otp(email=email, purpose="registration", submitted=payload.otp)
    if not result["ok"]:
        err = result.get("error") or "Invalid OTP"
        code = 410 if err == "OTP expired" else 400
        raise HTTPException(status_code=code, detail=err)

    now = now_iso()
    await users_col.update_one(
        {"id": user["id"]},
        {"$set": {"email_verified": True, "updated_at": now}},
    )
    user["email_verified"] = True
    user["updated_at"] = now
    token = create_token({"sub": user["id"], "role": user["role"],
                          "status": user["approval_status"]})
    return TokenResponse(access_token=token, user=to_public(user))


@api.post("/auth/login", response_model=TokenResponse)
async def login_email(payload: LoginRequest):
    """Single-step email + password login. Verified accounts get a token."""
    email = normalize_email(payload.email)
    user = await users_col.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("email_verified"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "email_not_verified",
                "message": "Please verify your email to continue.",
                "email": email,
            },
        )
    token = create_token({"sub": user["id"], "role": user["role"],
                          "status": user["approval_status"]})
    return TokenResponse(access_token=token, user=to_public(user))


@api.post("/auth/resend-otp")
async def resend_otp(payload: ResendOtpEmailRequest):
    """Resend OTP for registration or forgot_password. 60-second cooldown."""
    email = normalize_email(payload.email)
    purpose = payload.purpose
    user = await users_col.find_one({"email": email}, {"_id": 0})
    if not user:
        # Don't leak existence for forgot password
        if purpose == "forgot_password":
            return {"status": "ok", "resend_available_in": OTP_RESEND_INTERVAL_SEC}
        raise HTTPException(status_code=404, detail="Account not found")

    if purpose == "registration" and user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email already verified. Please log in.")

    wait_s = await can_resend_otp(email=email, purpose=purpose)
    if wait_s is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {wait_s}s before requesting another code.",
        )

    otp = gen_otp()
    await store_email_otp(email=email, purpose=purpose, otp=otp)
    ok = await send_email_otp(
        to=email, user_name=user["full_name"], otp=otp, purpose=purpose,
    )
    if not ok and SMTP_CONFIGURED:
        await email_otps_col.delete_one({"email": email, "purpose": purpose})
        raise HTTPException(status_code=502, detail="Could not send email")
    return {"status": "ok", "resend_available_in": OTP_RESEND_INTERVAL_SEC,
            "expires_in": OTP_EXPIRY_MIN * 60}


@api.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    """Start the password-reset flow. Always returns 200 — never leak existence."""
    email = normalize_email(payload.email)
    user = await users_col.find_one({"email": email}, {"_id": 0})
    if not user:
        # Silent OK (anti-enumeration)
        return {"status": "ok", "resend_available_in": OTP_RESEND_INTERVAL_SEC,
                "expires_in": OTP_EXPIRY_MIN * 60}

    wait_s = await can_resend_otp(email=email, purpose="forgot_password")
    if wait_s is not None:
        return {"status": "ok", "resend_available_in": wait_s,
                "expires_in": OTP_EXPIRY_MIN * 60}

    otp = gen_otp()
    await store_email_otp(email=email, purpose="forgot_password", otp=otp)
    await send_email_otp(
        to=email, user_name=user["full_name"], otp=otp, purpose="forgot_password",
    )
    return {"status": "ok", "resend_available_in": OTP_RESEND_INTERVAL_SEC,
            "expires_in": OTP_EXPIRY_MIN * 60}


@api.post("/auth/forgot-password/verify")
async def forgot_password_verify(payload: ForgotPasswordVerifyRequest):
    """Verify forgot-password OTP → mint a short-lived reset token (not deleted yet)."""
    email = normalize_email(payload.email)
    user = await users_col.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    result = await consume_email_otp(
        email=email, purpose="forgot_password", submitted=payload.otp,
    )
    if not result["ok"]:
        err = result.get("error") or "Invalid OTP"
        code = 410 if err == "OTP expired" else 400
        raise HTTPException(status_code=code, detail=err)

    reset_token = create_token(
        {"sub": user["id"], "email": email, "type": "reset"},
        minutes=RESET_TOKEN_EXPIRY_MIN,
    )
    return {"reset_token": reset_token, "expires_in": RESET_TOKEN_EXPIRY_MIN * 60}


@api.post("/auth/reset-password", response_model=TokenResponse)
async def reset_password(payload: ResetPasswordRequest):
    """Use the reset_token to set a new password + auto-login."""
    if payload.confirm_password is not None and payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    try:
        decoded = jwt.decode(payload.reset_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=400, detail="Reset link expired. Please start over.")
    if decoded.get("type") != "reset":
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user = await users_col.find_one({"id": decoded.get("sub")}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    now = now_iso()
    new_hash = hash_password(payload.new_password)
    await users_col.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": new_hash, "updated_at": now}},
    )
    user["password_hash"] = new_hash
    user["updated_at"] = now
    token = create_token({"sub": user["id"], "role": user["role"],
                          "status": user["approval_status"]})
    return TokenResponse(access_token=token, user=to_public(user))


@api.get("/auth/me", response_model=UserPublic)
async def me(u: dict = Depends(get_current_user)):
    return to_public(u)


@api.post("/auth/push-token")
async def save_push_token(payload: PushTokenInput, u: dict = Depends(get_current_user)):
    """Capture an Expo/FCM push token. Also registers with the Emergent relay."""
    await users_col.update_one(
        {"id": u["id"]},
        {"$set": {"push_token": payload.push_token.strip(),
                   "push_platform": payload.platform,
                   "updated_at": now_iso()}},
    )
    # Upsert into push_tokens collection (one doc per user/device combo)
    await push_tokens_col.update_one(
        {"user_id": u["id"], "device_token": payload.push_token.strip()},
        {"$set": {
            "user_id": u["id"], "device_token": payload.push_token.strip(),
            "platform": payload.platform or "android", "hostel": hostel_of(u),
            "role": u["role"], "updated_at": now_iso(),
        }, "$setOnInsert": {"created_at": now_iso()}},
        upsert=True,
    )
    return {"ok": True}


@api.post("/register-push", status_code=201)
async def register_push(body: RegisterPushBody, u: dict = Depends(get_current_user)):
    """Relay device token registration to the Emergent push provider.

    The auth dep ensures we're tying it to the right user.
    """
    if body.user_id != u["id"]:
        raise HTTPException(status_code=403, detail="user_id mismatch")
    # Store locally too
    await push_tokens_col.update_one(
        {"user_id": u["id"], "device_token": body.device_token.strip()},
        {"$set": {
            "user_id": u["id"], "device_token": body.device_token.strip(),
            "platform": body.platform, "hostel": hostel_of(u),
            "role": u["role"], "updated_at": now_iso(),
        }, "$setOnInsert": {"created_at": now_iso()}},
        upsert=True,
    )
    # Relay
    cli = get_push_client()
    try:
        resp = await cli.post("/api/v1/push/users/register", json={
            "user_id": body.user_id,
            "platform": body.platform,
            "device_token": body.device_token,
        })
        if resp.status_code == 401:
            logger.warning("EMERGENT_PUSH_KEY missing or invalid")
        elif resp.status_code >= 500:
            logger.warning("Push provider 5xx: %s", resp.text[:200])
    except Exception as e:
        logger.warning("Push register relay failed (non-blocking): %s", e)
    return {"status": "registered"}


# ---------------------------------------------------------------------------
# Student routes
# ---------------------------------------------------------------------------
@api.get("/student/meta")
async def student_meta(_: dict = Depends(require_approved_student)):
    return {"reasons": REASONS, "days": DAYS}


@api.get("/student/today")
async def student_today(
    u: dict = Depends(require_approved_student),
    for_: Literal["today", "tomorrow"] = Query("today", alias="for"),
):
    base = date.fromisoformat(today_iso())
    target_date = (base + timedelta(days=1)).isoformat() if for_ == "tomorrow" else base.isoformat()
    day = day_of_week(date.fromisoformat(target_date))
    h = hostel_of(u)
    menu_doc = await menus_col.find_one({"hostel": h, "day": day}, {"_id": 0})
    plan_doc = await daily_plans_col.find_one(
        {"student_id": u["id"], "date": target_date}, {"_id": 0}
    )
    return {
        "date": target_date,
        "day": day,
        "for": for_,
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
    # Fire push
    recipients = await _recipients_for(u, payload.audience, payload.recipient_id)
    try:
        await send_push(
            recipients,
            {"title": payload.title.strip(), "message": payload.body.strip(),
             "subtext": "MessMate", "action_url": "/notifications"},
            idempotency_key=doc["id"],
        )
    except Exception as e:
        logger.warning("push send failed (non-blocking): %s", e)
    return _project_notif(doc)


async def _recipients_for(
    admin: dict,
    audience: str,
    recipient_id: Optional[str] = None,
) -> List[str]:
    h = hostel_of(admin)
    if audience == "student":
        if recipient_id:
            return [recipient_id]
        return [u["id"] async for u in users_col.find(
            {"role": "student", "approval_status": "approved",
             "institution_or_hostel_name": h}, {"_id": 0, "id": 1})]
    if audience == "admin":
        return [u["id"] async for u in users_col.find(
            {"role": "admin", "institution_or_hostel_name": h}, {"_id": 0, "id": 1})]
    # "all" — students + admins of this hostel
    return [u["id"] async for u in users_col.find(
        {"institution_or_hostel_name": h,
         "$or": [{"role": "admin"}, {"approval_status": "approved"}]},
        {"_id": 0, "id": 1})]


@api.post("/admin/notifications/dispatch-reminder", status_code=201)
async def admin_dispatch_reminder(
    payload: ReminderDispatchInput, u: dict = Depends(require_admin)
):
    """Push a role-specific reminder right now. Defaults to students."""
    audience = payload.audience or "student"
    if audience == "student":
        title = payload.title or "Submit your meal preferences"
        body = payload.body or (
            "Help us cook the right quantity — mark today's meals in MessMate."
        )
    elif audience == "admin":
        title = payload.title or "Review today's plan"
        body = payload.body or (
            "Check the dashboard to confirm cooking quantities before service."
        )
    else:
        title = payload.title or "MessMate update"
        body = payload.body or "Open MessMate for the latest update."
    now = now_iso()
    doc = {
        "id": str(uuid.uuid4()), "hostel": hostel_of(u),
        "title": title, "body": body,
        "audience": "all" if audience == "all" else "student" if audience == "student" else "all",
        "recipient_id": None,
        "type": "menu_reminder" if audience == "student" else "system",
        "scheduled_for": today_iso(),
        "created_by": u["id"], "read_by": [], "created_at": now,
    }
    await notifications_col.insert_one(doc)
    doc.pop("_id", None)
    recipients = await _recipients_for(u, audience)
    try:
        await send_push(recipients, {
            "title": title, "message": body,
            "subtext": "MessMate", "action_url": "/notifications",
        }, idempotency_key=doc["id"])
    except Exception as e:
        logger.warning("reminder push failed: %s", e)
    return {"ok": True, "audience": audience, "recipients": len(recipients),
             "notification": _project_notif(doc)}


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
    recipients = await _recipients_for(u, "student")
    try:
        await send_push(recipients, {
            "title": doc["title"], "message": body,
            "subtext": "MessMate", "action_url": "/notifications",
        }, idempotency_key=doc["id"])
    except Exception as e:
        logger.warning("menu-reminder push failed: %s", e)
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
async def admin_dashboard(
    u: dict = Depends(require_admin),
    for_: Literal["today", "tomorrow"] = Query("today", alias="for"),
):
    h = hostel_of(u)
    base = date.fromisoformat(today_iso())
    target_date = (base + timedelta(days=1)).isoformat() if for_ == "tomorrow" else base.isoformat()
    day = day_of_week(date.fromisoformat(target_date))
    menu = await menus_col.find_one({"hostel": h, "day": day}, {"_id": 0}) or {}

    ni_lookup: Dict[str, dict] = {}
    async for r in necessary_info_col.find({"hostel": h}, {"_id": 0}):
        ni_lookup[f"{r['meal_type']}:{r['item_name'].lower()}"] = r

    out: Dict[str, Any] = {"date": target_date, "day": day, "for": for_, "meals": {}}
    most = {"item": None, "count": -1}
    least = {"item": None, "count": 10**9}

    for meal in ("breakfast", "lunch", "dinner"):
        agg = await _aggregate_meal(h, meal, target_date, menu)  # type: ignore[arg-type]
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
            warnings.append(
                "No student responses yet." if for_ == "today"
                else "No preferences submitted for tomorrow yet."
            )

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
            {"hostel": h, "date": target_date}
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
    "reminder_times": ["07:00", "11:30", "18:00"],
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
# Startup: indexes & migrations only — NO seed data (production-ready)
# ---------------------------------------------------------------------------
async def _ensure_indexes_and_migrate():
    """Create indexes for hostel-scoped collections. Idempotent."""
    await users_col.create_index("id", unique=True)
    # New: email is the global unique identifier.
    # Use a partial filter so legacy/no-email rows don't conflict.
    try:
        idxs = await users_col.index_information()
        if "mobile_or_user_id_1_institution_or_hostel_name_1" in idxs:
            await users_col.drop_index("mobile_or_user_id_1_institution_or_hostel_name_1")
        if "email_1" not in idxs:
            await users_col.create_index(
                "email",
                unique=True,
                partialFilterExpression={"email": {"$exists": True, "$type": "string"}},
                name="email_1",
            )
    except Exception:
        pass
    # menus
    try:
        idxs = await menus_col.index_information()
        if "day_1" in idxs:
            await menus_col.drop_index("day_1")
    except Exception:
        pass
    await menus_col.create_index([("hostel", 1), ("day", 1)], unique=True)
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
    # email otps
    await email_otps_col.create_index(
        [("email", 1), ("purpose", 1)], unique=True
    )
    await email_otps_col.create_index("expires_at")
    # push tokens
    await push_tokens_col.create_index(
        [("user_id", 1), ("device_token", 1)], unique=True
    )
    await push_tokens_col.create_index([("hostel", 1), ("role", 1)])

    # Drop legacy users unique-on-mobile-only if present
    try:
        idxs = await users_col.index_information()
        if "mobile_or_user_id_1" in idxs:
            await users_col.drop_index("mobile_or_user_id_1")
    except Exception:
        pass


@app.on_event("startup")
async def on_startup():
    await _ensure_indexes_and_migrate()
    if SMTP_CONFIGURED:
        logger.info("MessMate API ready — SMTP email OTP active (%s)", SMTP_HOST)
    else:
        logger.info("MessMate API ready — SMTP NOT configured. OTPs are logged to console (dev mode).")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
    try:
        if _push_client is not None:
            await _push_client.aclose()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Mount + CORS
# ---------------------------------------------------------------------------
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
