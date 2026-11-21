"""
Speech-to-text route for SignConnect.

POST /api/stt/transcribe
    multipart/form-data:
        file      - a short audio clip (webm/ogg/mp4/wav/mp3...), recorded in the browser
        language  - optional ISO-639-1 code, e.g. "en", "hi" (omit to auto-detect)
    returns: {"text": "..."}

The Groq API key is read from the GROQ_API_KEY environment variable (BackEnd/.env).
It never leaves the server: the browser only talks to this endpoint.
"""

import os
import re

from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from groq import APIConnectionError, APIStatusError, AsyncGroq, RateLimitError

load_dotenv()

router = APIRouter(prefix="/api/stt", tags=["speech-to-text"])

# whisper-large-v3-turbo: faster, slightly less accurate (Groq lists 12% WER).
# whisper-large-v3: slower, more accurate (10.3% WER). Both are on the free plan.
GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")

# Microphone chunks are tiny (15 s of Opus is roughly 30-60 KB). Groq's free plan accepts
# up to 25 MB, but there is no reason to let anyone upload that much to this endpoint.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Groq detects the format from the file extension, so map the browser's MIME type to one.
EXTENSIONS = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/flac": "flac",
}

# Whisper sometimes "hears" these phrases in near-silence. Drop them if they are the whole result.
_HALLUCINATIONS = {
    "you", "thank you", "thanks", "thank you for watching", "thanks for watching",
    "please subscribe", "bye",
}

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="Speech-to-text is not configured on the server.")
        _client = AsyncGroq(api_key=api_key, timeout=20.0, max_retries=1)
    return _client


def _is_hallucination(text: str) -> bool:
    normalised = re.sub(r"[^\w\s]", "", text).strip().lower()
    return normalised in _HALLUCINATIONS


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Form(default=None),
):
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    ext = EXTENSIONS.get(content_type)
    if ext is None:
        raise HTTPException(status_code=415, detail=f"Unsupported audio type: {content_type or 'unknown'}")

    if language is not None and not re.fullmatch(r"[a-z]{2}", language):
        raise HTTPException(status_code=422, detail="language must be a 2-letter ISO-639-1 code, e.g. 'en'.")

    audio = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(audio) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio clip too large; send shorter chunks.")
    if len(audio) < 1000:  # an empty/aborted recording
        return {"text": ""}

    params = {
        "file": (f"chunk.{ext}", audio),
        "model": GROQ_STT_MODEL,
        "response_format": "json",
        "temperature": 0.0,
    }
    if language:
        params["language"] = language

    try:
        result = await _get_client().audio.transcriptions.create(**params)
    except RateLimitError as e:
        retry_after = e.response.headers.get("retry-after", "60")
        raise HTTPException(
            status_code=429,
            detail="Free speech-to-text quota reached; try again shortly.",
            headers={"Retry-After": retry_after},
        )
    except APIConnectionError:
        raise HTTPException(status_code=502, detail="Could not reach the speech-to-text service.")
    except APIStatusError as e:
        # 401 here means the server's key is wrong/revoked - don't leak details to the browser.
        raise HTTPException(status_code=502, detail=f"Speech-to-text service error ({e.status_code}).")

    text = (result.text or "").strip()
    if _is_hallucination(text):
        text = ""
    return {"text": text}
