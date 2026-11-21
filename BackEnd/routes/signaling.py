
import jwt

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect
)

from sqlalchemy.orm import Session

from database import (
    SessionLocal,
    User,
    Meeting,
    RevokedToken
)

from security import SECRET_KEY, ALGORITHM

from services.connection_manager import manager


router = APIRouter(tags=["WebRTC Signaling"])


# VERIFY WEBSOCKET TOKEN
def authenticate_websocket(token):

    db: Session = SessionLocal()

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = int(payload["sub"])
        jti = payload["jti"]

        revoked = db.query(RevokedToken).filter_by(
            jti=jti
        ).first()

        if revoked:
            return None

        user = db.query(User).filter_by(
            id=user_id
        ).first()

        return user

    except Exception:
        return None

    finally:
        db.close()


# CHECK MEETING
def meeting_exists(meeting_code):

    db = SessionLocal()

    try:

        return db.query(Meeting).filter_by(
            meeting_code=meeting_code,
            is_active=True
        ).first() is not None

    finally:
        db.close()


# WEBSOCKET SIGNALING
@router.websocket("/ws/signaling/{meeting_code}")
async def signaling(
    websocket: WebSocket,
    meeting_code: str,
    token: str = None
):

    # Validate token
    if not token:

        await websocket.close(code=1008)
        return

    user = authenticate_websocket(token)

    if not user:

        await websocket.close(code=1008)
        return

    # Validate meeting
    meeting_code = meeting_code.upper()

    if not meeting_exists(meeting_code):

        await websocket.close(code=1008)
        return

    user_id = user.id

    await websocket.accept()

    connected, existing_connections = await manager.connect(
        meeting_code,
        user_id,
        websocket
    )

    if not connected:

        await websocket.send_json({
            "type": "error",
            "message": "Meeting is full or this user is already connected"
        })

        await websocket.close(code=1008)
        return

    try:

        # Tell this participant that connection succeeded
        await websocket.send_json({
            "type": "joined",
            "user_id": user_id
        })

        # Tell the existing participant to initiate WebRTC
        if existing_connections:

            await manager.broadcast_except(
                meeting_code,
                user_id,
                {
                    "type": "peer_joined",
                    "user_id": user_id
                }
            )

            # Tell the new participant someone is already present
            await websocket.send_json({
                "type": "peer_present"
            })

        while True:

            message = await websocket.receive_json()

            message_type = message.get("type")

            # Only allow expected WebRTC signaling messages (+ live captions)
            if message_type not in (
                "offer",
                "answer",
                "ice_candidate",
                "caption"
            ):
                continue

            payload = message.get("payload")

            if not isinstance(payload, dict):
                continue

            # Captions: forward only a short, plain-text string
            if message_type == "caption":

                text = payload.get("text")

                if not isinstance(text, str) or not text.strip():
                    continue

                payload = {"text": text.strip()[:500]}

            await manager.broadcast_except(
                meeting_code,
                user_id,
                {
                    "type": message_type,
                    "payload": payload,
                    "sender_id": user_id
                }
            )

    except WebSocketDisconnect:
        pass

    except Exception as error:
        print("Signaling error:", error)

    finally:

        remaining_connections = await manager.disconnect(
            meeting_code,
            user_id
        )

        for connection in remaining_connections:

            await manager.send_to_connection(
                connection,
                {
                    "type": "peer_left",
                    "user_id": user_id
                }
            )
