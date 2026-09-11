import asyncio
import logging
from collections import OrderedDict

from app.bot import agent
from app.config import settings
from app.rag import memory, messages
from app.services.waha import Waha

logger = logging.getLogger(__name__)

# Text waiting to be answered, keyed by chat so users never mix.
buffers: dict[str, list[str]] = {}

# Pending debounce task per chat, cancelled when a new message arrives.
timers: dict[str, asyncio.Task] = {}

# One lock per chat so two replies to the same user never overlap.
locks: dict[str, asyncio.Lock] = {}

# Bounded set of handled message ids, webhooks are retried up to 15 times.
handled: OrderedDict[str, None] = OrderedDict()
handled_limit = 2000


def already_handled(message_id: str) -> bool:
    """Return True when this message id was seen before, and record it otherwise."""

    if not message_id:
        return False

    if message_id in handled:
        return True

    handled[message_id] = None

    while len(handled) > handled_limit:
        handled.popitem(last=False)

    return False


def lock_for(chat_id: str) -> asyncio.Lock:
    """Return the lock guarding one conversation."""

    if chat_id not in locks:
        locks[chat_id] = asyncio.Lock()

    return locks[chat_id]


async def schedule(payload: dict) -> None:
    """Turn a message into text, buffer it and restart the debounce window."""

    chat_id = payload.get("from", "")
    waha = Waha()

    try:
        text = await messages.extract_text(payload, waha)
    except Exception:
        logger.exception("could not read message from %s", chat_id)
        return

    if not text:
        return

    buffers.setdefault(chat_id, []).append(text)

    try:
        await waha.send_seen(chat_id, payload.get("id"))
    except Exception:
        logger.warning("send_seen failed for %s", chat_id)

    if chat_id in timers:
        timers[chat_id].cancel()

    timers[chat_id] = asyncio.create_task(reply_after_debounce(chat_id))


async def reply_after_debounce(chat_id: str) -> None:
    """Wait for the user to stop typing, then answer everything at once."""

    try:
        await asyncio.sleep(settings.debounce_seconds)
    except asyncio.CancelledError:
        return

    async with lock_for(chat_id):

        question = "\n".join(buffers.pop(chat_id, [])).strip()
        timers.pop(chat_id, None)

        if not question:
            return

        await reply(chat_id, question)


async def show_typing(waha: Waha, chat_id: str, active: bool) -> None:
    """Toggle the typing indicator, never letting it break the actual reply."""

    try:
        await (waha.start_typing(chat_id) if active else waha.stop_typing(chat_id))
    except Exception:
        logger.warning("typing indicator failed for %s", chat_id)


async def reply(chat_id: str, question: str) -> None:
    """Answer one user and store both sides of the exchange in memory."""

    waha = Waha()

    await show_typing(waha, chat_id, True)

    try:
        answer = await agent.answer(chat_id, question)

        await memory.remember(chat_id, "user", question)
        await memory.remember(chat_id, "assistant", answer)

        await waha.send_message(chat_id, answer)

    except Exception:
        logger.exception("failed to answer %s", chat_id)

    finally:
        await show_typing(waha, chat_id, False)
