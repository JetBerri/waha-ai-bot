# waha-ai-bot

Autonomous WhatsApp assistant. Runs on [WAHA](https://waha.devlike.pro), understands
text, voice notes and images, answers from your own documents, and keeps a separate
memory for every contact.

- **Hybrid retrieval** over Qdrant: dense embeddings for meaning, sparse BM25 for exact
  terms like model names, plates or prices.
- **Per-contact memory**, isolated by chat id and recalled semantically.
- **Replies in the contact's language**, detected per message.
- **Debounced**, so three quick messages get one answer instead of three.

## Requirements

Docker, an OpenAI API key, and a phone with WhatsApp.

## Quick start

**1. Clone and configure**

```bash
git clone git@github.com:JetBerri/waha-ai-bot.git
cd waha-ai-bot
cp .env.example .env
```

Set these three in `.env`:

```bash
OPENAI_API_KEY=sk-...
WAHA_API_KEY=$(openssl rand -hex 32)
WEBHOOK_SECRET=$(openssl rand -hex 32)
```

`WEBHOOK_SECRET` signs the webhook. An empty value makes the bot accept any unsigned
POST, so never deploy without it.

**2. Start the stack**

```bash
docker compose up -d --build
```

Three containers come up: `waha`, `qdrant` and `bot`. Check the bot is alive:

```bash
curl http://localhost:8000/health
```

**3. Link WhatsApp**

Create the session, then download and scan the QR. Only needed once.

```bash
source .env

curl -X POST http://localhost:3000/api/sessions \
  -H "X-Api-Key: $WAHA_API_KEY" -H "Content-Type: application/json" \
  -d '{"name":"default","start":true}'

curl -s http://localhost:3000/api/default/auth/qr \
  -H "X-Api-Key: $WAHA_API_KEY" -o qr.png && open qr.png
```

Scan it from WhatsApp, Settings, Linked devices. The first QR lasts 60 seconds; re-run
the second command to get a fresh one.

The QR endpoint requires the `X-Api-Key` header, so opening that URL straight in a
browser returns 401.

**4. Confirm the session is live**

```bash
curl -s http://localhost:3000/api/sessions/default -H "X-Api-Key: $WAHA_API_KEY"
```

Status must be `WORKING`. Anything else and the bot can neither send nor receive.

**5. Load your documents**

The bot only answers from what you give it.

```bash
cp your-docs/*.pdf app/rag/data/
docker compose exec bot python -m app.rag.ingest app/rag/data
```

Accepts `.txt`, `.md` and `.pdf`. Re-run whenever the documents change.

**Done.** Message the linked number from another phone. Follow along with
`docker compose logs -f bot`.

## Configuration

Every variable is documented in `.env.example`. The ones worth tuning:

| Variable | Default | Purpose |
|---|---|---|
| `DEBOUNCE_SECONDS` | `6` | Wait before replying, so a burst gets one answer |
| `OPENAI_MODEL` | `gpt-5.6-terra` | Must accept image input |
| `KNOWLEDGE_TOP_K` | `6` | Documents retrieved per question |
| `MEMORY_TOP_K` | `6` | Older messages recalled for this contact |
| `MEMORY_RECENT_TURNS` | `10` | Recent messages always replayed |
| `BUSINESS_NAME` | empty | Name the bot introduces itself with |
| `FALLBACK_LANGUAGE` | `Spanish` | Used only when the contact's language is unclear |

`OPENAI_TEMPERATURE` is deliberately unset: `gpt-5.6-terra` rejects it. Only set it for
models that accept the parameter.

The system prompt lives in `app/bot/agent.py`. It is written in English, but the bot
always replies in whatever language the contact writes in.

If 8000, 3000 or 6333 are taken on the host, override `BOT_PORT`, `WAHA_PORT` or
`QDRANT_PORT`. Containers keep talking on their internal ports regardless.

## Operating

```bash
docker compose logs -f bot     # follow
docker compose restart bot     # reload after editing .env
docker compose down            # stop, volumes survive
```

State lives in two git-ignored directories:

- `.waha_sessions/` the linked session. Delete it and you must scan the QR again.
- `qdrant_storage/` the knowledge base and every conversation memory.

Changing `OPENAI_EMBEDDING_MODEL` invalidates the knowledge collection. Drop it and
re-ingest:

```bash
curl -X DELETE http://localhost:6333/collections/knowledge
```

## Development

```bash
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn main:app --reload --port 8000
```

Running outside Docker means pointing `WAHA_URL` and `QDRANT_URL` at `localhost`, and
setting the WAHA hook to `http://host.docker.internal:8000/webhook`, because inside the
container `localhost` is the container itself.

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
