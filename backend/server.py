"""MessMate backend — Part 1: Authentication & Role-Based Entry."""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
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


class StudentRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    mobile_or_user_id: str = Field(..., min_length=3, max_length=60)
    institution_or_hostel_name: str = Field(..., min_length=1, max_length=120)
    room_number: str = Field(..., min_length=1, max_length=40)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    mobile_or_user_id: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    institution_or_hostel_name: Optional[str] = None  # supplied by admin login


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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


async def get_user_by_id(user_id: str) -> Optional[dict]:
    return await users_col.find_one({"id": user_id}, {"_id": 0})


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
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


# ---------------------------------------------------------------------------
# Routes
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

    now = datetime.now(timezone.utc).isoformat()
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


# OTP placeholder endpoints — MOCKED: real SMS provider will be integrated later
@api.post("/auth/request-otp")
async def request_otp_placeholder(mobile_or_user_id: str):
    return {"message": "OTP placeholder — real SMS not sent", "mock_otp": "123456"}


@api.post("/auth/verify-otp")
async def verify_otp_placeholder(mobile_or_user_id: str, otp: str):
    if otp != "123456":
        raise HTTPException(status_code=400, detail="Invalid OTP (mock)")
    return {"message": "OTP verified (mock)"}


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


async def seed_demo_users():
    now = datetime.now(timezone.utc).isoformat()
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


@app.on_event("startup")
async def on_startup():
    await users_col.create_index("mobile_or_user_id", unique=True)
    await users_col.create_index("id", unique=True)
    await seed_demo_users()
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
