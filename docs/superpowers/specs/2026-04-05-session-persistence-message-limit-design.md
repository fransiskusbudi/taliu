# Session Persistence, Message Limit & Conversation Logging — Design Spec

**Date:** 2026-04-05
**Project:** taliu — AI resume agent
**Status:** Approved

---

## Overview

Add server-side session persistence using PostgreSQL to:
1. Enforce a per-session message limit (to encourage contact)
2. Persist conversation history across browser refreshes
3. Log all conversations for review (inputs to S7 cost/latency tracking)
4. Rate-limit at Nginx level to block spam/bots

---

## Goals

- Users get a fixed number of messages per session (configurable, default 10, set to 2 for testing)
- Once the limit is hit, a contact banner replaces the input — never resets even on refresh
- History is owned by the backend — frontend no longer manages or sends it
- Every conversation is stored in PostgreSQL for Frans to review
- Bots/spammers are blocked at Nginx before hitting FastAPI

---

## Infrastructure Changes

### docker-compose.yml
- Add `postgres` service: `postgres:16` image, `postgres_data` Docker volume, same `agent-network`
- `api` service depends on both `qdrant` and `postgres`
- Add `DATABASE_URL` and `MESSAGE_LIMIT` to `api` env vars

### .env additions
```
DATABASE_URL=postgresql://taliu:taliu@postgres:5432/taliu
POSTGRES_USER=taliu
POSTGRES_PASSWORD=taliu
POSTGRES_DB=taliu
MESSAGE_LIMIT=2
```

---

## Database Schema

```sql
CREATE TABLE sessions (
    id VARCHAR PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    user_agent TEXT,
    ip_address VARCHAR
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR REFERENCES sessions(id),
    role VARCHAR NOT NULL,          -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    latency_ms INTEGER,             -- response time in ms
    prompt_tokens INTEGER,          -- OpenAI input tokens
    completion_tokens INTEGER,      -- OpenAI output tokens
    model VARCHAR                   -- model used e.g. gpt-5.4-mini
);
```

Schema is applied via `app/db/schema.sql` on first startup (CREATE TABLE IF NOT EXISTS).

---

## Backend Changes

### New module: `app/db/`

**`app/db/connection.py`**
- asyncpg connection pool
- `init_db(app)` — creates pool on startup, runs schema.sql, stored on `app.state.db`
- `close_db(app)` — closes pool on shutdown
- Registered in `main.py` lifespan

**`app/db/session.py`**
- `get_or_create_session(pool, session_id, ip, user_agent)` — upserts session row, updates `last_active_at`
- `check_limit(pool, session_id, limit)` — returns `True` if `message_count >= limit`
- `get_history(pool, session_id)` — returns all messages ordered by `created_at` as list of `ChatMessage`
- `save_messages(pool, session_id, user_content, assistant_content, latency_ms, prompt_tokens, completion_tokens, model)` — inserts both messages, increments `message_count`

### Updated: `app/api/routes/chat.py`
Request flow:
1. Extract `session_id`, `ip` (from `Request`), `user_agent` from headers
2. `get_or_create_session()` — upsert session
3. `check_limit()` — if True, raise `HTTPException(status_code=429, detail="limit_reached")` — this returns HTTP 429 with JSON body `{"detail": "limit_reached"}` before the SSE stream starts. Note: Nginx rate limit also returns 429 but with no JSON body — frontend distinguishes by checking for the `detail` field.
4. `get_history()` — load messages from DB, load into chat engine memory
5. Stream response, track `start_time`
6. After streaming: calculate `latency_ms`, get token counts from response metadata
7. `save_messages()` — persist both messages with all metadata

### Updated: `app/models/chat.py`
- Remove `conversation_history` field from `ChatRequest`
- `ChatRequest` now: `message: str`, `session_id: str`

### Updated: `app/config.py`
- Add `database_url: str`
- Add `message_limit: int = 10`

### Updated: `requirements.txt`
- Add `asyncpg`

---

## Frontend Changes

### `frontend/src/services/api.ts`
- Remove `conversation_history` from request body
- Handle `limit_reached` error specifically: on 429 response, parse JSON body — if `detail === "limit_reached"` trigger `isLimitReached`, otherwise show generic rate limit message

### `frontend/src/hooks/useChat.ts`
- Add `isLimitReached: boolean` state
- When `onError` receives `limit_reached`, set `isLimitReached = true` (not generic `error`)
- `isLimitReached` persists for the session lifetime (no reset on new chat since backend enforces it)

### `frontend/src/types/chat.ts`
- Remove `conversation_history` from `ChatRequest` interface

### `frontend/src/components/ChatWindow.tsx`
- Pass `isLimitReached` to `InputBar`
- When `isLimitReached`, show contact banner above input:
  > "enjoyed talking? let's connect directly → hi@atoue.io · linkedin.com/in/fransiskusbudi"
- Input bar remains visible but disabled

### `frontend/src/components/InputBar.tsx`
- Accept `isLimitReached` prop
- Disable input when `isLimitReached` is true

---

## Nginx Rate Limiting

### `/etc/nginx/nginx.conf` (on VPS, not in repo)
Add to `http` block:
```nginx
limit_req_zone $binary_remote_addr zone=taliu_api:10m rate=10r/m;
limit_req_status 429;
```

### `nginx/api.atoue.io.conf` (in repo)
Add to `location /` block:
```nginx
limit_req zone=taliu_api burst=5 nodelay;
```

Applied manually on VPS after deploy. Rate: 10 requests/minute per IP, burst of 5.

---

## Data Flow (updated)

```
Browser (session_id in localStorage)
  → POST /api/chat { message, session_id }
  → Nginx rate check (10r/m per IP)
  → FastAPI: get_or_create_session → check_limit → get_history
  → Chat engine streams response
  → save_messages (user + assistant + metadata)
  → SSE stream to browser
  → Browser renders tokens, shows limit banner if 429
```

---

## Out of Scope

- Admin dashboard for conversation review (query PostgreSQL directly for now)
- Per-IP message limits (Nginx handles abuse; session limit handles normal users)
- LangGraph / multi-agent routing (Phase 2)
- Voice interface (Phase 2)
