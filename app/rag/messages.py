import base64

from app.config import settings
from app.services.openai_client import get_openai
from app.services.waha import Waha

# Prompt used to turn an image into text the rest of the pipeline can use.
image_prompt = (
    "Describe esta imagen en español, de forma breve y factual. "
    "Si contiene texto, matrículas, precios o documentos, transcríbelos literalmente."
)


def media_of(payload: dict) -> dict:
    """Return the media block of a WAHA message, empty when there is none."""

    return payload.get("media") or {}


def kind_of(payload: dict) -> str:
    """Classify a message as text, audio, image or unsupported."""

    mimetype = media_of(payload).get("mimetype", "")

    if not mimetype:
        return "text"

    if mimetype.startswith("audio"):
        return "audio"

    if mimetype.startswith("image"):
        return "image"

    return "unsupported"


async def transcribe(audio: bytes, filename: str = "voice.ogg") -> str:
    """Turn a voice note into text with the configured speech model."""

    response = await get_openai().audio.transcriptions.create(
        model=settings.openai_transcription_model,
        file=(filename, audio),
    )

    return (response.text or "").strip()


async def describe(image: bytes, mimetype: str) -> str:
    """Turn an image into a textual description with the vision model."""

    encoded = base64.b64encode(image).decode()

    response = await get_openai().chat.completions.create(
        model=settings.openai_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": image_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mimetype};base64,{encoded}"},
                    },
                ],
            }
        ],
    )

    return (response.choices[0].message.content or "").strip()


async def extract_text(payload: dict, waha: Waha) -> str:
    """Normalise any supported WhatsApp message into plain text."""

    kind = kind_of(payload)
    body = (payload.get("body") or "").strip()

    if kind == "text":
        return body

    media = media_of(payload)
    url = media.get("url")

    if not url:
        return body

    content = await waha.download_media(url)

    if kind == "audio":
        return await transcribe(content)

    if kind == "image":

        description = await describe(content, media.get("mimetype", "image/jpeg"))

        # Keep the caption, it often carries the real question.
        return f"{body}\n\n[imagen recibida] {description}".strip()

    return body or "[mensaje no soportado]"
