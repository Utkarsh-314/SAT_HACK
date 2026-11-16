
import jwt

from datetime import datetime, timezone

from fastapi import (
    FastAPI,
    Depends,
    HTTPException
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from pydantic import BaseModel, Field, ConfigDict

from database import (
    User,
    RevokedToken,
    get_db,
    create_tables
)

from security import (
    hash_password,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM
)


# Initialize application
app = FastAPI(title="SignConnect API")


# Allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Create database tables
create_tables()


# Authentication scheme
bearer = HTTPBearer()


# Request models
class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    user_id: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    user_id: str
    password: str


# User response
class UserResponse(BaseModel):
    id: int
    name: str
    user_id: str

    model_config = ConfigDict(from_attributes=True)


# Generate response
def token_response(user):
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "user_id": user.user_id
        }
    }


# Verify logged-in user
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
):

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = int(payload["sub"])
        jti = payload["jti"]

    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    revoked = db.query(RevokedToken).filter_by(
        jti=jti
    ).first()

    if revoked:
        raise HTTPException(
            status_code=401,
            detail="You have been logged out"
        )

    user = db.query(User).filter_by(id=user_id).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user


# HOME ROUTE
@app.get("/")
def home():
    return {"message": "SignConnect backend is running"}


# SIGNUP ROUTE
@app.post("/api/auth/signup")
def signup(
    data: SignupRequest,
    db: Session = Depends(get_db)
):

    name = data.name.strip()
    user_id = data.user_id.strip()

    if len(name) < 2 or len(user_id) < 3:
        raise HTTPException(
            status_code=400,
            detail="Please enter valid account details"
        )

    if db.query(User).filter_by(user_id=user_id).first():
        raise HTTPException(
            status_code=409,
            detail="User ID already exists"
        )

    new_user = User(
        name=name,
        user_id=user_id,
        password_hash=hash_password(data.password)
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="User ID already exists"
        )

    return token_response(new_user)


# LOGIN ROUTE
@app.post("/api/auth/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter_by(
        user_id=data.user_id.strip()
    ).first()

    if not user or not verify_password(
        data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect User ID or password"
        )

    return token_response(user)


# CURRENT USER ROUTE
@app.get("/api/auth/me", response_model=UserResponse)
def get_me(
    user: User = Depends(get_current_user)
):
    return user


# LOGOUT ROUTE
@app.post("/api/auth/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
):

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    existing = db.query(RevokedToken).filter_by(
        jti=payload["jti"]
    ).first()

    if not existing:

        expires_at = datetime.fromtimestamp(
            payload["exp"],
            tz=timezone.utc
        ).replace(tzinfo=None)

        revoked_token = RevokedToken(
            jti=payload["jti"],
            expires_at=expires_at
        )

        db.add(revoked_token)
        db.commit()

    return {
        "message": "Successfully logged out"
    }
