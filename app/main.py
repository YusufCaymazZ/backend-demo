import os
import sys
import time
import json
import hmac
import hashlib
import base64
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional, List
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Header, Depends, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, Column, Integer, String, DateTime, event, text, Index
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy.pool import StaticPool

# Context variable for request tracking (thread-safe)
request_id_var: ContextVar[str] = ContextVar('request_id', default='N/A')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)


# Add custom filter for request IDs using contextvars (thread-safe, no factory recreation)
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


logger = logging.getLogger(__name__)
logger.addFilter(RequestIdFilter())

DATA_DIR = os.getenv("DATA_DIR", "data")
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(DATA_DIR, 'app.db')}")
JWT_SECRET = os.getenv("JWT_SECRET", "test_secret")
JWT_TTL_MIN = int(os.getenv("JWT_TTL_MIN", "120"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# --- DB setup
os.makedirs(DATA_DIR, exist_ok=True)
# Connection pooling for better performance
engine_config = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "pool_pre_ping": True,  # Verify connections before use
}
if DB_URL.startswith("sqlite"):
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DB_URL, **engine_config)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    balance = Column(Integer, default=0)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True, nullable=False)
    event_type = Column(String, index=True, nullable=False)
    ts_utc = Column(DateTime, index=True, nullable=False)
    meta = Column(String, nullable=True)

    # Composite indexes for common query patterns
    __table_args__ = (
        Index('idx_user_time', 'user_id', 'ts_utc'),  # For events by user ordered by time
        Index('idx_type_time', 'event_type', 'ts_utc'),  # For events by type ordered by time
        Index('idx_user_type_time', 'user_id', 'event_type', 'ts_utc'),  # For filtered queries
    )


Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Commit any pending transactions
    except Exception:
        db.rollback()  # Rollback on any exception
        raise
    finally:
        db.close()  # Always close the session


# --- Tiny JWT (HS256) helpers
def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("utf-8")


def _b64urldecode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def create_jwt(sub: str) -> str:
    header = _b64url(b'{"alg":"HS256","typ":"JWT"}')
    exp = int(time.time()) + JWT_TTL_MIN * 60
    payload = _b64url(f'{{"sub":"{sub}","exp":{exp}}}'.encode())
    signing_input = f"{header}.{payload}".encode()
    sig = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url(sig)}"


def verify_jwt(token: str) -> str:
    try:
        header, payload, sig = token.split(".")
        signing_input = f"{header}.{payload}".encode()
        expected = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64urldecode(sig)):
            raise ValueError("bad sig")

        pl = json.loads(_b64urldecode(payload))
        if int(time.time()) > int(pl["exp"]):
            raise ValueError("expired")

        return pl["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="invalid_token")


# Security scheme for Swagger UI
security_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="Enter JWT token obtained from /login endpoint"
)


def current_user_id(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> str:
    """
    Validates JWT token and returns user ID.
    Used by Swagger UI for authentication.
    """
    return verify_jwt(credentials.credentials)


# --- Schemas
class LoginIn(BaseModel):
    userId: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique user identifier",
        examples=["player_12345", "user_abc"]
    )

    @field_validator('userId')
    def validate_user_id(v):
        if not v or not v.strip():
            raise ValueError('userId cannot be empty or whitespace')
        # Remove dangerous characters for security
        if any(char in v for char in ['<', '>', '"', "'"]):
            raise ValueError('userId contains invalid characters')
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "userId": "player_12345"
                }
            ]
        }
    }


class EarnIn(BaseModel):
    amount: int = Field(
        ...,
        ge=1,
        le=100000,
        description="Amount of currency to add to user balance",
        examples=[100, 500, 1000]
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for earning currency (for analytics)",
        examples=["daily_login", "quest_complete", "level_up"]
    )

    @field_validator('reason')
    def validate_reason(v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "amount": 500,
                    "reason": "daily_login_bonus"
                }
            ]
        }
    }


class EventIn(BaseModel):
    eventType: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Event type identifier",
        examples=["level_complete", "purchase", "game_start"]
    )
    meta: Optional[str] = Field(
        None,
        max_length=5000,
        description="Optional JSON metadata for the event",
        examples=['{"level": 10, "score": 9999}', '{"item_id": "sword_01"}']
    )
    timestampUtc: Optional[str] = Field(
        None,
        description="ISO 8601 UTC timestamp (defaults to current time if not provided)",
        examples=["2025-11-07T10:30:00Z", "2025-11-07T14:45:30.123Z"]
    )

    @field_validator('eventType')
    def validate_event_type(v):
        if not v or not v.strip():
            raise ValueError('eventType cannot be empty or whitespace')
        # Alphanumeric, underscore, dash only for security
        if not all(c.isalnum() or c in ['_', '-', '.'] for c in v):
            raise ValueError('eventType can only contain alphanumeric characters, underscores, dashes, and dots')
        return v.strip()

    @field_validator('timestampUtc')
    def validate_timestamp(v):
        if v is None:
            return v
        # Basic validation - will be fully validated in endpoint
        if not isinstance(v, str) or len(v) < 10:
            raise ValueError('Invalid timestamp format')
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "eventType": "level_complete",
                    "meta": '{"level": 42, "score": 9999, "time_seconds": 145}',
                    "timestampUtc": "2025-11-07T10:30:00Z"
                }
            ]
        }
    }


class EventOut(BaseModel):
    id: int
    type: str
    ts: str
    meta: Optional[str] = None


# --- App
app = FastAPI(title="Global Backend Test — Core API + Data Pipeline", version="3.0")

# CORS Configuration - Secure by default
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


# Startup validation
@app.on_event("startup")
async def validate_environment():
    logger.info(f"Starting application in {ENVIRONMENT} mode")

    # Validate JWT_SECRET
    if not JWT_SECRET or JWT_SECRET == "test_secret":
        if ENVIRONMENT == "production":
            logger.error("FATAL: Using default or missing JWT_SECRET in production!")
            raise ValueError("JWT_SECRET must be set to a secure value in production")
        else:
            logger.warning("WARNING: Using default JWT_SECRET - NOT SAFE FOR PRODUCTION!")

    if len(JWT_SECRET) < 32:
        logger.error(f"FATAL: JWT_SECRET is too short ({len(JWT_SECRET)} chars, minimum 32)")
        raise ValueError("JWT_SECRET must be at least 32 characters")

    # Log CORS configuration
    logger.info(f"CORS allowed origins: {ALLOWED_ORIGINS}")

    # Verify database connection
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    logger.info("Environment validation complete")


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Request tracking middleware - optimized with contextvars (no factory recreation)
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Set request ID in context variable (thread-safe, no performance overhead)
    request_id_var.set(request_id)

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": request_id})


# Global exception handlers
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    request_id = getattr(request.state, 'request_id', 'N/A')
    logger.error(f"Database error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Database operation failed", "request_id": request_id, "error_type": "database_error"})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    request_id = getattr(request.state, 'request_id', 'N/A')
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(status_code=400, content={"detail": str(exc), "request_id": request_id, "error_type": "validation_error"})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, 'request_id', 'N/A')
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred", "request_id": request_id, "error_type": "server_error"})


@app.get("/health")
def health(db: Session = Depends(get_db)):
    health_status = {
        "status": "healthy",
        "version": "3.0",
        "environment": ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": "disconnected",
            "type": "sqlite" if DB_URL.startswith("sqlite") else "postgresql"
        },
        "checks": {}
    }

    try:
        # Check database connectivity
        db.execute(text("SELECT 1"))
        health_status["database"]["status"] = "connected"

        # Check if tables are accessible
        try:
            user_count = db.query(User).count()
            event_count = db.query(Event).count()
            health_status["database"]["tables"] = "accessible"
            health_status["checks"]["users"] = user_count
            health_status["checks"]["events"] = event_count
        except Exception as e:
            health_status["database"]["tables"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        logger.info("Health check passed")
        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status["status"] = "unhealthy"
        health_status["database"]["error"] = str(e)
        raise HTTPException(status_code=503, detail=health_status)


@app.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    try:
        logger.info(f"Login attempt for user: {body.userId}")
        u = db.query(User).filter_by(user_id=body.userId).first()
        if not u:
            logger.info(f"Creating new user: {body.userId}")
            u = User(user_id=body.userId, balance=0)
            db.add(u)
            db.commit()
            db.refresh(u)
        token = create_jwt(body.userId)
        logger.info(f"Login successful for user: {body.userId}")
        return {"token": token, "userId": body.userId}
    except SQLAlchemyError as e:
        logger.error(f"Database error during login for {body.userId}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to process login")
    except Exception as e:
        logger.error(f"Unexpected error during login for {body.userId}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Login failed")


@app.post(
    "/earn",
    responses={
        200: {"description": "Currency added successfully"},
        401: {"description": "Invalid or missing authentication token"},
        403: {"description": "Forbidden - No authentication provided"},
        500: {"description": "Server error"}
    }
)
def earn(body: EarnIn, uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    try:
        logger.info(f"Earn request for user {uid}: amount={body.amount}, reason={body.reason}")
        # Use with_for_update() to lock the row and prevent race conditions on balance updates
        u = db.query(User).filter_by(user_id=uid).with_for_update().first()
        if not u:
            logger.warning(f"User {uid} not found, creating new user")
            u = User(user_id=uid, balance=0)
            db.add(u)
            db.flush()

        u.balance += body.amount
        db.add(Event(user_id=uid, event_type="earn", ts_utc=datetime.now(timezone.utc), meta=(body.reason or "")))
        db.commit()
        logger.info(f"Earn successful for user {uid}: new balance={u.balance}")
        return {"ok": True, "balance": u.balance}
    except SQLAlchemyError as e:
        logger.error(f"Database error during earn for {uid}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to process earn request")
    except Exception as e:
        logger.error(f"Unexpected error during earn for {uid}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Earn request failed")


@app.get("/balance")
def balance(uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    try:
        logger.info(f"Balance request for user {uid}")
        u = db.query(User).filter_by(user_id=uid).first()
        if not u:
            logger.warning(f"User {uid} not found")
            raise HTTPException(status_code=404, detail="user_not_found")
        logger.info(f"Balance retrieved for user {uid}: {u.balance}")
        return {"userId": uid, "balance": u.balance}
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching balance for {uid}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch balance")
    except Exception as e:
        logger.error(f"Unexpected error fetching balance for {uid}: {e}")
        raise HTTPException(status_code=500, detail="Balance request failed")


@app.post("/event")
def post_event(body: EventIn, uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    try:
        logger.info(f"Event request for user {uid}: type={body.eventType}")

        # Parse timestamp with error handling
        if not body.timestampUtc:
            ts = datetime.now(timezone.utc)
        else:
            try:
                ts = datetime.fromisoformat(body.timestampUtc.replace("Z", "+00:00"))
            except ValueError as e:
                # Log the caught exception so the variable is used and we keep useful debug info
                logger.warning(f"Invalid timestamp format: {body.timestampUtc} - {e}")
                raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {body.timestampUtc}. Use ISO 8601 format.")

        ev = Event(user_id=uid, event_type=body.eventType, ts_utc=ts, meta=(body.meta or ""))
        db.add(ev)
        db.commit()
        db.refresh(ev)
        logger.info(f"Event created for user {uid}: event_id={ev.id}")
        return {"ok": True, "eventId": ev.id}
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error creating event for {uid}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create event")
    except Exception as e:
        logger.error(f"Unexpected error creating event for {uid}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Event creation failed")


@app.get("/events", response_model=List[EventOut])
def list_events(uid: str = Depends(current_user_id), db: Session = Depends(get_db)):
    try:
        logger.info(f"Fetching events for user {uid}")
        rows = db.query(Event).filter_by(user_id=uid).order_by(Event.ts_utc.desc()).limit(100).all()
        logger.info(f"Retrieved {len(rows)} events for user {uid}")
        return [{"id": r.id, "type": r.event_type, "ts": r.ts_utc.isoformat(), "meta": r.meta} for r in rows]
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching events for {uid}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch events")
    except Exception as e:
        logger.error(f"Unexpected error fetching events for {uid}: {e}")
        raise HTTPException(status_code=500, detail="Event listing failed")


@app.get("/stats")
def stats(uid: Optional[str] = None, db: Session = Depends(get_db)):
    # If uid is provided, filter by that user; else global counts
    try:
        from sqlalchemy import func

        logger.info(f"Stats request for {'user ' + uid if uid else 'all users'}")
        q = db.query(Event.event_type, func.count().label("cnt"))
        if uid:
            q = q.filter(Event.user_id == uid)
        q = q.group_by(Event.event_type).all()
        result = [{"eventType": et, "count": int(c)} for et, c in q]
        logger.info(f"Stats retrieved: {len(result)} event types")
        return result
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")
    except Exception as e:
        logger.error(f"Unexpected error fetching stats: {e}")
        raise HTTPException(status_code=500, detail="Statistics request failed")


# Bonus: deeplink tracking
@app.get("/track")
def track(character: Optional[str] = None, campaign: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        logger.info(f"Deeplink tracking: character={character}, campaign={campaign}")
        ev = Event(user_id="anon", event_type="deeplink_open", ts_utc=datetime.now(timezone.utc), meta=json.dumps({"character": character, "campaign": campaign}))
        db.add(ev)
        db.commit()
        db.refresh(ev)
        logger.info(f"Deeplink tracked successfully: event_id={ev.id}")
        return {"ok": True, "logged": {"character": character, "campaign": campaign}}
    except SQLAlchemyError as e:
        logger.error(f"Database error during deeplink tracking: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to track deeplink")
    except Exception as e:
        logger.error(f"Unexpected error during deeplink tracking: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Tracking failed")


# Trigger data pipeline (CSV -> reports)
@app.post("/run-pipeline")
def run_pipeline():
    import subprocess

    try:
        logger.info("Starting data pipeline execution")
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "process_data.py")

        if not os.path.exists(script_path):
            logger.error(f"Pipeline script not found: {script_path}")
            raise HTTPException(status_code=500, detail="Pipeline script not found")

        cmd = [sys.executable, script_path]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # 5 min timeout

        if res.returncode == 0:
            logger.info("Pipeline execution completed successfully")
        else:
            logger.error(f"Pipeline execution failed with return code {res.returncode}")

        return {"ok": res.returncode == 0, "returncode": res.returncode, "stdout": res.stdout[-2000:] if res.stdout else "", "stderr": res.stderr[-2000:] if res.stderr else ""}
    except subprocess.TimeoutExpired:
        logger.error("Pipeline execution timed out")
        raise HTTPException(status_code=504, detail="Pipeline execution timed out")
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute pipeline: {str(e)}")
