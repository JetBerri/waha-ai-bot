import hashlib
import hmac

import pytest
from fastapi import HTTPException

from app.bot import pipeline
from app.config import settings
from app.rag import messages
from app.routers import webhook


def sign(body: bytes, secret: str) -> str:
    """Build the signature WAHA would send for a body."""

    return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()


def test_valid_signature_passes(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "shh")
    webhook.verify_signature(b"payload", sign(b"payload", "shh"))


def test_wrong_signature_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "shh")

    with pytest.raises(HTTPException) as error:
        webhook.verify_signature(b"payload", sign(b"payload", "other"))

    assert error.value.status_code == 401


def test_missing_signature_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "shh")

    with pytest.raises(HTTPException):
        webhook.verify_signature(b"payload", None)


def test_signature_skipped_when_no_secret(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "")
    webhook.verify_signature(b"payload", None)


def test_tampered_body_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "shh")

    with pytest.raises(HTTPException):
        webhook.verify_signature(b"tampered", sign(b"original", "shh"))


def test_group_detection():
    assert webhook.is_group("1234-5678@g.us")
    assert not webhook.is_group("34600111222@c.us")


def test_duplicates_are_detected():
    pipeline.handled.clear()

    assert not pipeline.already_handled("id-1")
    assert pipeline.already_handled("id-1")
    assert not pipeline.already_handled("id-2")


def test_empty_id_is_never_a_duplicate():
    pipeline.handled.clear()

    assert not pipeline.already_handled("")
    assert not pipeline.already_handled("")


def test_handled_set_stays_bounded():
    pipeline.handled.clear()

    for index in range(pipeline.handled_limit + 50):
        pipeline.already_handled(f"id-{index}")

    assert len(pipeline.handled) <= pipeline.handled_limit


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"body": "hola"}, "text"),
        ({"media": {"mimetype": "audio/ogg; codecs=opus"}}, "audio"),
        ({"media": {"mimetype": "image/jpeg"}}, "image"),
        ({"media": {"mimetype": "application/pdf"}}, "unsupported"),
    ],
)
def test_message_kinds(payload, expected):
    assert messages.kind_of(payload) == expected
