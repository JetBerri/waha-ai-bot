# waha-ai-bot

WhatsApp assistant that answers on its own. It runs on [WAHA](https://waha.devlike.pro),
understands text, voice notes and images, answers with an LLM grounded in your own
documents, and keeps a separate memory for every contact.

## Requirements

- Docker and Docker Compose
- An OpenAI API key
- A phone number with WhatsApp, to link the session once

## Install

```bash
git clone git@github.com:JetBerri/waha-ai-bot.git
cd waha-ai-bot
cp .env.example .env
```

Edit `.env`. The two that matter before the first run:

```bash
OPENAI_API_KEY=sk-...
WEBHOOK_SECRET=$(openssl rand -hex 32)
```

`WEBHOOK_SECRET` signs the webhook. Leaving it empty makes the bot accept any unsigned
POST to `/webhook`, so set it before exposing anything.

If 8000, 3000 or 6333 are already taken on the host, override the host ports. The
containers keep talking to each other on their internal ports regardless:

```bash
BOT_PORT=8001
WAHA_PORT=3001
QDRANT_PORT=6333
```

## Run

```bash
docker compose up -d --build
docker compose logs -f bot
```

Three containers come up: `waha`, `qdrant` and `bot`.

## Link WhatsApp

Only needed once. The session is stored in `./.waha_sessions` and survives restarts.

```bash
source .env

curl -X POST http://localhost:3000/api/sessions/default/start \
  -H "X-Api-Key: $WAHA_API_KEY"

open http://localhost:3000/api/default/auth/qr
```

Scan the QR from WhatsApp, Settings, Linked devices. The first QR expires in 60 seconds.

Check it worked:

```bash
curl -s http://localhost:3000/api/sessions/default -H "X-Api-Key: $WAHA_API_KEY"
```

The status must be `WORKING`. Anything else means the bot cannot send or receive.

## Load the knowledge base

The bot only answers from documents you give it.

```bash
cp your-docs/*.pdf app/rag/data/
docker compose exec bot python -m app.rag.ingest app/rag/data
```

Supported: `.txt`, `.md`, `.pdf`. Re-run after changing the documents.

Changing `OPENAI_EMBEDDING_MODEL` later invalidates the collection. Delete it and ingest
again:

```bash
curl -X DELETE http://localhost:6333/collections/knowledge
```

## Verify

```bash
curl http://localhost:8000/health   # or $BOT_PORT
```

Then send a WhatsApp message to the linked number from another phone. Watch `docker
compose logs -f bot`. A reply should arrive within a few seconds of the debounce window.

## Configuration

Every variable is documented in `.env.example`. The ones worth tuning:

| Variable | Default | What it does |
|---|---|---|
| `DEBOUNCE_SECONDS` | `6` | Wait before replying, so three quick messages get one answer |
| `OPENAI_MODEL` | `gpt-5.6-terra` | Must accept image input, the bot reads photos |
| `OPENAI_TEMPERATURE` | unset | Left out on purpose, newer models reject it |
| `KNOWLEDGE_TOP_K` | `6` | Documents retrieved per question |
| `MEMORY_TOP_K` | `6` | Older messages recalled for this contact |
| `MEMORY_RECENT_TURNS` | `10` | Recent messages always replayed |
| `BUSINESS_NAME` | `Innovacar` | Name the bot introduces itself with |
| `FALLBACK_LANGUAGE` | `Spanish` | Only used when the contact's language is unclear |

The system prompt lives in `app/bot/agent.py`. It is written in English, but the bot
always replies in whatever language the contact writes in.

## Operating

```bash
docker compose logs -f bot          # follow the bot
docker compose restart bot          # reload after changing .env
docker compose down                 # stop everything, keeps volumes
```

State lives in two directories, both git ignored:

- `.waha_sessions/` the linked WhatsApp session. Delete it and you must scan the QR again.
- `qdrant_storage/` the knowledge base and every conversation memory.

## Running without Docker

```bash
python -m venv venv && source venv/bin/activate
pip install -e .
uvicorn main:app --reload --port 8000
```

Point `WAHA_URL` and `QDRANT_URL` at `localhost`, and set the hook on the WAHA container
to `http://host.docker.internal:8000/webhook`, because inside the container `localhost`
is the container itself.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Layout

```
app/routers/webhook.py   signature check, filtering, fast acknowledgement
app/bot/pipeline.py      debounce, per chat locking, deduplication
app/bot/agent.py         prompt and langchain chain
app/rag/hybrid.py        hybrid search over the knowledge base
app/rag/memory.py        per contact conversation memory
app/rag/messages.py      text, voice note and image understanding
app/rag/ingest.py        load documents into the knowledge base
app/services/waha.py     waha http client
```
