import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.bot import pipeline
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhook"])

# Headers WAHA sends with every delivery.
signature_header = "x-webhook-hmac"
request_id_header = "x-webhook-request-id"


def verify_signature(raw_body: bytes, signature: str | None) -> None:
    """Reject the request unless it carries a valid hmac from WAHA."""

    if not settings.webhook_secret:
        return

    if not signature:
        raise HTTPException(status_code=401, detail="missing signature")

    expected = hmac.new(
        settings.webhook_secret.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()

    # Constant time comparison, a plain == leaks the signature byte by byte.
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="invalid signature")


def is_group(chat_id: str) -> bool:
    """Group chats end in @g.us, the bot only answers direct conversations."""

    return chat_id.endswith("@g.us")


@router.post("/webhook")
async def receive(request: Request, background: BackgroundTasks) -> dict:
    """Accept a WAHA event, acknowledge immediately and answer in the background."""

    # Read the raw body first, the signature covers these exact bytes.
    raw_body = await request.body()

    verify_signature(raw_body, request.headers.get(signature_header))

    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="body is not json")

    if event.get("event") != "message":
        return {"status": "ignored", "reason": "not a message event"}

    payload = event.get("payload") or {}
    chat_id = payload.get("from", "")

    if payload.get("fromMe"):
        return {"status": "ignored", "reason": "own message"}

    if is_group(chat_id):
        return {"status": "ignored", "reason": "group chat"}

    if pipeline.already_handled(payload.get("id", "")):
        return {"status": "ignored", "reason": "duplicate delivery"}

    # Answer outside the request so WAHA gets its 200 before the model runs.
    background.add_task(pipeline.schedule, payload)

    return {"status": "accepted"}
