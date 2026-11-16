
import secrets
import jwt

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from database import (
    User,
    Meeting,
    RevokedToken,
    get_db
)

from security import SECRET_KEY, ALGORITHM


router = APIRouter(
    prefix="/api/meetings",
    tags=["Meetings"]
)

bearer = HTTPBearer()


# AUTHENTICATION
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
):

    try:

        payload = jwt.decode(
            credentials.credentials,
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

    user = db.query(User).filter_by(
        id=user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user


# REQUEST MODELS
class CreateMeetingRequest(BaseModel):

    meeting_name: str = Field(
        min_length=1,
        max_length=100
    )

    description: str = Field(
        default="",
        max_length=500
    )


class JoinMeetingRequest(BaseModel):

    meeting_code: str = Field(
        min_length=1,
        max_length=20
    )


# CREATE MEETING
@router.post("/")
def create_meeting(
    data: CreateMeetingRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    meeting_name = data.meeting_name.strip()

    if not meeting_name:
        raise HTTPException(
            status_code=400,
            detail="Meeting name is required"
        )

    # Generate unique meeting code
    for _ in range(5):

        code = "SC-" + secrets.token_hex(4).upper()

        existing = db.query(Meeting).filter_by(
            meeting_code=code
        ).first()

        if not existing:
            break

    else:
        raise HTTPException(
            status_code=500,
            detail="Unable to generate meeting code"
        )

    meeting = Meeting(
        meeting_code=code,
        meeting_name=meeting_name,
        description=data.description.strip(),
        host_user_id=user.id,
        is_active=True
    )

    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return {
        "meeting_code": meeting.meeting_code,
        "meeting_name": meeting.meeting_name,
        "meeting_link": f"room.html?code={meeting.meeting_code}",
        "message": "Meeting created successfully"
    }


# JOIN / VALIDATE MEETING
@router.post("/join")
def join_meeting(
    data: JoinMeetingRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    code = data.meeting_code.strip().upper()

    meeting = db.query(Meeting).filter_by(
        meeting_code=code,
        is_active=True
    ).first()

    if not meeting:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found or unavailable"
        )

    return {
        "meeting_code": meeting.meeting_code,
        "meeting_name": meeting.meeting_name,
        "status": "active"
    }
