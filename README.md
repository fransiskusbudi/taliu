# taliu

An AI agent that answers questions about Frans — work history, projects, skills, and philosophy. Built under the [atoue](https://atoue.io) brand as a portfolio piece, with both text chat and live voice call.

**Live:** [taliu.atoue.io](https://taliu.atoue.io)

## What it does

- **Chat** — ask anything; answers grounded in a curated knowledge base (resume, projects, stories, FAQ, philosophy) via hybrid retrieval.
- **Voice call** — same agent, voice in / voice out. Real-time STT and TTS over WebSocket.
- **Sessions persist** — chat history is restored across reloads; a per-session message limit caps usage.

## Stack

**Backend** — FastAPI · LlamaIndex · Qdrant · PostgreSQL · OpenAI · Deepgram (STT)

**Frontend** — Vite · React 19 · TypeScript

**Infra** — Docker Compose · Nginx · Cloudflare Pages (frontend) · Hetzner VPS (backend)

## Architecture

```
browser  →  Cloudflare Pages (React)  →  api.atoue.io / Nginx  →  FastAPI
                                                                    │
                                       ┌────────────────────────────┼────────────────────────┐
                                       ▼                            ▼                        ▼
                                    Qdrant                       Postgres            OpenAI / Deepgram
                              (semantic index)              (sessions, history)    (LLM, embeddings, STT/TTS)
```

The RAG pipeline retrieves from a curated knowledge base (`backend/app/ingestion/data/`) using a hybrid retriever — BM25 for lexical matches and semantic search via Qdrant — fused with LlamaIndex's `QueryFusionRetriever`. Responses stream back over SSE for chat and WebSocket for voice.

## Repo layout

```
taliu/
├── backend/          FastAPI app — RAG pipeline, chat & voice routes, ingestion
│   └── app/
│       ├── api/      route handlers (chat, voice, health)
│       ├── rag/      hybrid retrieval engine + system prompt
│       ├── voice/    STT/TTS pipeline
│       ├── ingestion/  knowledge base files + ingestion script
│       ├── db/       async Postgres
│       └── models/   SQLAlchemy models
├── frontend/         Vite + React UI
├── nginx/            reverse proxy + rate limit config
├── docker-compose.yml
└── README.md
```

## Run locally

Requires Docker, an OpenAI API key, and a Deepgram API key (for voice).

```bash
cp backend/.env.example backend/.env
# fill in OPENAI_API_KEY, DEEPGRAM_API_KEY, etc.

docker compose up -d --build
```

Then ingest the knowledge base into Qdrant:

```bash
docker exec taliu-api python app/ingestion/ingest.py
```

Frontend dev (separate process, hot reload):

```bash
cd frontend
npm install
npm run dev
```

## Deploy

The frontend auto-deploys to Cloudflare Pages on push to `main`. The backend runs on a Hetzner VPS:

```bash
ssh root@<vps>
cd /opt/taliu
git pull
docker compose stop api && docker compose rm -f api && docker compose up -d --build api
```

## Knowledge base

The agent's answers are grounded in markdown files under `backend/app/ingestion/data/`:

- `resume.md` — work experience, education, skills
- `projects.md` — selected work
- `stories.md` — narrative context behind decisions
- `faq.md` — common questions
- `philosophy.md` — how Frans thinks about building
- `status.md` — current focus

Re-ingest after editing any of these to refresh the index.

---

Part of [atoue](https://atoue.io).
