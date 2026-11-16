
import os
import secrets
import jwt

from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from pwdlib import PasswordHash

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

TOKEN_EXPIRE_MINUTES = 30

if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError("Set a secure SECRET_KEY in your .env file")


# Password hashing
password_hasher = PasswordHash.recommended()


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(password, hashed_password):
    return password_hasher.verify(password, hashed_password)


# Generate JWT token
def create_access_token(user_id):

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "jti": secrets.token_urlsafe(24),
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token
