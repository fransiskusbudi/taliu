# Session Persistence, Message Limit & Conversation Logging — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PostgreSQL-backed session persistence, per-session message limits, conversation logging, and Nginx rate limiting to taliu.

**Architecture:** PostgreSQL stores sessions and messages server-side. The backend owns conversation history — the frontend no longer sends it. On each request, the backend upserts the session, checks the message count against `MESSAGE_LIMIT`, loads history from DB, streams the response, then saves both messages with metadata. Nginx blocks spam at the network layer before FastAPI sees the request.

**Tech Stack:** asyncpg, PostgreSQL 16, Docker, FastAPI lifespan, React state

---

## File Map

**Create:**
- `backend/app/db/__init__.py`
- `backend/app/db/connection.py` — asyncpg pool init/close
- `backend/app/db/session.py` — session CRUD functions
- `backend/app/db/schema.sql` — CREATE TABLE IF NOT EXISTS statements

**Modify:**
- `backend/requirements.txt` — add asyncpg
- `backend/app/config.py` — add database_url, message_limit
- `backend/app/main.py` — add lifespan for DB init/close
- `backend/app/models/chat.py` — remove conversation_history from ChatRequest
- `backend/app/api/routes/chat.py` — use DB for history, limit check, save messages
- `docker-compose.yml` — add postgres service
- `backend/.env.example` — add new env vars
- `nginx/api.atoue.io.conf` — add rate limit directive
- `frontend/src/types/chat.ts` — remove conversation_history from ChatRequest
- `frontend/src/services/api.ts` — remove history from request, handle limit_reached 429
- `frontend/src/hooks/useChat.ts` — add isLimitReached state
- `frontend/src/components/ChatWindow.tsx` — show contact banner when limit reached
- `frontend/src/components/InputBar.tsx` — accept isLimitReached prop

---

## Task 1: Add PostgreSQL to docker-compose

**Files:**
- Modify: `docker-compose.yml`
- Modify: `backend/.env.example`

- [ ] **Step 1: Update docker-compose.yml**

Replace the full file content:

```yaml
services:
  api:
    build: ./backend
    container_name: taliu-api
    ports:
      - "8100:8000"
    env_file:
      - ./backend/.env
    depends_on:
      - qdrant
      - postgres
    restart: unless-stopped
    networks:
      - agent-network

  qdrant:
    image: qdrant/qdrant:latest
    container_name: taliu-qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped
    networks:
      - agent-network

  postgres:
    image: postgres:16
    container_name: taliu-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - agent-network

volumes:
  qdrant_data:
  postgres_data:

networks:
  agent-network:
    driver: bridge
```

- [ ] **Step 2: Update backend/.env.example**

Add these lines to `backend/.env.example`:

```
DATABASE_URL=postgresql://taliu:taliu@postgres:5432/taliu
POSTGRES_USER=taliu
POSTGRES_PASSWORD=taliu
POSTGRES_DB=taliu
MESSAGE_LIMIT=2
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml backend/.env.example
git commit -m "infra: add PostgreSQL service to docker-compose"
```

---

## Task 2: Add asyncpg to requirements and update config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add asyncpg to requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic-settings==2.7.1
llama-index==0.14.20
llama-index-vector-stores-qdrant==0.10.0
qdrant-client==1.17.1
python-dotenv==1.0.1
sse-starlette==2.2.1
asyncpg==0.30.0
```

- [ ] **Step 2: Update app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "resume_chunks"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "info"
    database_url: str = "postgresql://taliu:taliu@postgres:5432/taliu"
    message_limit: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt backend/app/config.py
git commit -m "config: add database_url and message_limit settings"
```

---

## Task 3: Create database schema and connection module

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/schema.sql`
- Create: `backend/app/db/connection.py`

- [ ] **Step 1: Create `backend/app/db/__init__.py`**

```python
```
(empty file)

- [ ] **Step 2: Create `backend/app/db/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    user_agent TEXT,
    ip_address VARCHAR
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR REFERENCES sessions(id),
    role VARCHAR NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    latency_ms INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    model VARCHAR
);
```

- [ ] **Step 3: Create `backend/app/db/connection.py`**

```python
"""asyncpg connection pool management."""

import asyncpg
from pathlib import Path


async def init_db(app) -> None:
    """Create connection pool and apply schema on startup."""
    pool = await asyncpg.create_pool(app.state.settings.database_url)
    app.state.db = pool

    schema_path = Path(__file__).parent / "schema.sql"
    schema_sql = schema_path.read_text()
    async with pool.acquire() as conn:
        await conn.execute(schema_sql)


async def close_db(app) -> None:
    """Close connection pool on shutdown."""
    await app.state.db.close()
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/
git commit -m "feat: add DB schema and asyncpg connection pool"
```

---

## Task 4: Create session CRUD functions

**Files:**
- Create: `backend/app/db/session.py`

- [ ] **Step 1: Create `backend/app/db/session.py`**

```python
"""Session and message persistence functions."""

from app.models.chat import ChatMessage


async def get_or_create_session(
    pool,
    session_id: str,
    ip_address: str,
    user_agent: str,
) -> None:
    """Upsert session row and update last_active_at."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sessions (id, ip_address, user_agent)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE
            SET last_active_at = NOW()
            """,
            session_id,
            ip_address,
            user_agent,
        )


async def check_limit(pool, session_id: str, limit: int) -> bool:
    """Return True if session has reached or exceeded the message limit."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT message_count FROM sessions WHERE id = $1",
            session_id,
        )
        if row is None:
            return False
        return row["message_count"] >= limit


async def get_history(pool, session_id: str) -> list[ChatMessage]:
    """Load all messages for a session ordered by created_at."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM messages WHERE session_id = $1 ORDER BY created_at ASC",
            session_id,
        )
        return [ChatMessage(role=row["role"], content=row["content"]) for row in rows]


async def save_messages(
    pool,
    session_id: str,
    user_content: str,
    assistant_content: str,
    latency_ms: int | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    model: str | None,
) -> None:
    """Save user and assistant messages and increment message_count."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO messages (session_id, role, content)
                VALUES ($1, 'user', $2)
                """,
                session_id,
                user_content,
            )
            await conn.execute(
                """
                INSERT INTO messages (session_id, role, content, latency_ms, prompt_tokens, completion_tokens, model)
                VALUES ($1, 'assistant', $2, $3, $4, $5, $6)
                """,
                session_id,
                assistant_content,
                latency_ms,
                prompt_tokens,
                completion_tokens,
                model,
            )
            await conn.execute(
                "UPDATE sessions SET message_count = message_count + 1 WHERE id = $1",
                session_id,
            )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/db/session.py
git commit -m "feat: add session CRUD functions"
```

---

## Task 5: Wire DB into FastAPI lifespan

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Update main.py with lifespan**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, health
from app.config import settings
from app.db.connection import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    await init_db(app)
    yield
    await close_db(app)


app = FastAPI(
    title="Taliu Resume Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: wire asyncpg pool into FastAPI lifespan"
```

---

## Task 6: Update ChatRequest model

**Files:**
- Modify: `backend/app/models/chat.py`

- [ ] **Step 1: Simplify ChatRequest**

```python
"""Pydantic models for chat request and response."""

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., min_length=1)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/models/chat.py
git commit -m "refactor: remove conversation_history from ChatRequest"
```

---

## Task 7: Update chat route to use DB

**Files:**
- Modify: `backend/app/api/routes/chat.py`

- [ ] **Step 1: Rewrite chat.py**

```python
"""POST /api/chat — main chat endpoint with SSE streaming."""

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.llms import ChatMessage as LlamaChatMessage, MessageRole
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import get_chat_engine
from app.config import settings
from app.db.session import (
    get_or_create_session,
    check_limit,
    get_history,
    save_messages,
)
from app.models.chat import ChatRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    http_request: Request,
    chat_engine: CondensePlusContextChatEngine = Depends(get_chat_engine),
):
    pool = http_request.app.state.db
    ip = http_request.client.host if http_request.client else "unknown"
    user_agent = http_request.headers.get("user-agent", "")

    await get_or_create_session(pool, request.session_id, ip, user_agent)

    if await check_limit(pool, request.session_id, settings.message_limit):
        raise HTTPException(status_code=429, detail="limit_reached")

    history = await get_history(pool, request.session_id)

    # Load history into chat engine memory
    chat_engine.reset()
    for msg in history:
        role = MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT
        chat_engine._memory.put(LlamaChatMessage(role=role, content=msg.content))

    async def event_generator():
        start_time = time.monotonic()
        full_response = ""

        try:
            streaming_response = await chat_engine.astream_chat(request.message)

            async for token in streaming_response.async_response_gen():
                full_response += token
                yield {"data": json.dumps({"token": token})}

            latency_ms = int((time.monotonic() - start_time) * 1000)

            # Extract token counts if available
            prompt_tokens = None
            completion_tokens = None
            if hasattr(streaming_response, "response_metadata"):
                meta = streaming_response.response_metadata
                prompt_tokens = meta.get("prompt_tokens")
                completion_tokens = meta.get("completion_tokens")

            await save_messages(
                pool=pool,
                session_id=request.session_id,
                user_content=request.message,
                assistant_content=full_response,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=settings.openai_model,
            )

            # Signal completion with source metadata
            source_nodes = streaming_response.source_nodes
            sources = []
            for node in source_nodes:
                meta = node.metadata
                company = meta.get("company", "")
                role_name = meta.get("role", "")
                section = meta.get("section", "")
                if company and role_name:
                    sources.append(f"{company} - {role_name}")
                elif section:
                    sources.append(section)

            yield {"data": json.dumps({"done": True, "sources": sources})}

        except Exception as e:
            logger.error(f"Chat streaming error: {e}")
            yield {"data": json.dumps({"error": "Something went wrong. Please try again."})}

    return EventSourceResponse(event_generator())
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/routes/chat.py
git commit -m "feat: load history from DB and save messages after streaming"
```

---

## Task 8: Update frontend types and API service

**Files:**
- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: Update types/chat.ts — remove conversation_history**

```typescript
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  message: string;
  session_id: string;
}

export interface SSETokenEvent {
  token: string;
}

export interface SSEDoneEvent {
  done: true;
  sources: string[];
}

export interface SSEErrorEvent {
  error: string;
}

export type SSEEvent = SSETokenEvent | SSEDoneEvent | SSEErrorEvent;
```

- [ ] **Step 2: Update services/api.ts — remove history, handle limit_reached**

```typescript
import type { ChatRequest, SSEEvent } from "../types/chat";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8100";

export async function streamChat(
  request: ChatRequest,
  onToken: (token: string) => void,
  onDone: (sources: string[]) => void,
  onError: (error: string) => void,
  onLimitReached: () => void
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    onError("unable to reach the server. please check your connection and try again.");
    return;
  }

  if (response.status === 429) {
    try {
      const body = await response.json();
      if (body.detail === "limit_reached") {
        onLimitReached();
        return;
      }
    } catch {
      // Nginx rate limit — no JSON body
    }
    onError("too many requests. please wait a moment and try again.");
    return;
  }

  if (response.status >= 500) {
    onError("the server encountered an error. please try again later.");
    return;
  }

  if (!response.ok) {
    onError("something went wrong. please try again.");
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    onError("Streaming not supported in this browser.");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;

      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;

      try {
        const event: SSEEvent = JSON.parse(jsonStr);

        if ("error" in event) {
          onError(event.error);
          return;
        }

        if ("done" in event) {
          onDone(event.sources);
          return;
        }

        if ("token" in event) {
          onToken(event.token);
        }
      } catch {
        // Skip malformed JSON
      }
    }
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/chat.ts frontend/src/services/api.ts
git commit -m "feat: remove conversation_history from frontend, handle limit_reached"
```

---

## Task 9: Update useChat hook

**Files:**
- Modify: `frontend/src/hooks/useChat.ts`

- [ ] **Step 1: Add isLimitReached state**

```typescript
import { useCallback, useRef, useState } from "react";
import { streamChat } from "../services/api";
import type { ChatMessage } from "../types/chat";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLimitReached, setIsLimitReached] = useState(false);
  const sessionId = useRef(crypto.randomUUID());

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming || isLimitReached) return;

      setError(null);

      const userMessage: ChatMessage = { role: "user", content };
      setMessages((prev) => [...prev, userMessage]);

      const assistantMessage: ChatMessage = { role: "assistant", content: "" };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsStreaming(true);

      await streamChat(
        {
          message: content,
          session_id: sessionId.current,
        },
        // onToken
        (token) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                content: last.content + token,
              };
            }
            return updated;
          });
        },
        // onDone
        () => {
          setIsStreaming(false);
        },
        // onError
        (errorMsg) => {
          setError(errorMsg);
          setIsStreaming(false);
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant" && last.content === "") {
              updated.pop();
            }
            return updated;
          });
        },
        // onLimitReached
        () => {
          setIsLimitReached(true);
          setIsStreaming(false);
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last.role === "assistant" && last.content === "") {
              updated.pop();
            }
            return updated;
          });
        }
      );
    },
    [isStreaming, isLimitReached]  // messages removed — history now owned by backend
  );

  const resetChat = useCallback(() => {
    setMessages([]);
    setError(null);
    sessionId.current = crypto.randomUUID();
  }, []);

  return { messages, isStreaming, error, isLimitReached, sendMessage, resetChat };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useChat.ts
git commit -m "feat: add isLimitReached state to useChat"
```

---

## Task 10: Update ChatWindow and InputBar components

**Files:**
- Modify: `frontend/src/components/ChatWindow.tsx`
- Modify: `frontend/src/components/InputBar.tsx`

- [ ] **Step 1: Update InputBar to accept isLimitReached**

```typescript
import { useState, type FormEvent, type KeyboardEvent } from "react";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
  isLimitReached: boolean;
}

export function InputBar({ onSend, disabled, isLimitReached }: Props) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || disabled || isLimitReached) return;
    onSend(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form className="input-bar" onSubmit={handleSubmit}>
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about Frans's experience..."
        disabled={disabled || isLimitReached}
        rows={1}
      />
      <button type="submit" disabled={disabled || isLimitReached || !input.trim()}>
        Send
      </button>
    </form>
  );
}
```

- [ ] **Step 2: Update ChatWindow to show contact banner**

```typescript
import { useEffect, useRef } from "react";
import { useChat } from "../hooks/useChat";
import { useTheme } from "../hooks/useTheme";
import { InputBar } from "./InputBar";
import { MessageBubble } from "./MessageBubble";

const SUGGESTED_QUESTIONS = [
  "What is Frans currently working on?",
  "What are Frans's technical skills?",
  "Tell me about his experience at Jet Commerce",
  "What is Frans's educational background?",
];

export function ChatWindow() {
  const { messages, isStreaming, error, isLimitReached, sendMessage, resetChat } = useChat();
  const { theme, toggleTheme } = useTheme();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-container">
      <header className="chat-header">
        <div className="chat-header-left">
          <h1>taliu</h1>
          <p>get to know Frans — ask me anything</p>
        </div>
        <div className="chat-header-actions">
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
          {messages.length > 0 && (
            <button className="reset-button" onClick={resetChat}>
              new chat
            </button>
          )}
        </div>
      </header>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-section">
            <div className="welcome-text">
              <h2>hi, i'm taliu — Frans's ai agent</h2>
              <p>
                ask me anything about Frans — his work, skills, background, and more. try one of these:
              </p>
            </div>
            <div className="suggested-questions">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  className="suggestion-chip"
                  onClick={() => sendMessage(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {error && <div className="error-message">{error}</div>}

        <div ref={messagesEndRef} />
      </div>

      {isLimitReached && (
        <div className="limit-banner">
          enjoyed talking? let's connect directly →{" "}
          <a href="mailto:hi@atoue.io">hi@atoue.io</a>
          {" · "}
          <a href="https://linkedin.com/in/fransiskusbudi/" target="_blank" rel="noopener noreferrer">
            linkedin
          </a>
        </div>
      )}

      <InputBar onSend={sendMessage} disabled={isStreaming} isLimitReached={isLimitReached} />
    </div>
  );
}
```

- [ ] **Step 3: Add limit-banner CSS to App.css**

Find the `/* ===== Error ===== */` section in `frontend/src/App.css` and add after the `.error-message` block:

```css
/* ===== Limit Banner ===== */
.limit-banner {
  text-align: center;
  font-size: 0.8rem;
  font-weight: 300;
  padding: 10px 16px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  color: var(--text-secondary);
}

.limit-banner a {
  color: var(--text-primary);
  text-decoration: underline;
  text-underline-offset: 3px;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ChatWindow.tsx frontend/src/components/InputBar.tsx frontend/src/App.css
git commit -m "feat: show contact banner when message limit reached"
```

---

## Task 11: Update Nginx config for rate limiting

**Files:**
- Modify: `nginx/api.atoue.io.conf`

- [ ] **Step 1: Add rate limit directive to location block**

```nginx
server {
    listen 80;
    server_name api.atoue.io;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name api.atoue.io;

    ssl_certificate /etc/letsencrypt/live/api.atoue.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.atoue.io/privkey.pem;

    location / {
        limit_req zone=taliu_api burst=5 nodelay;

        proxy_pass http://localhost:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

- [ ] **Step 2: Add rate limit zone to VPS nginx.conf (manual step on VPS)**

SSH into VPS and add to the `http` block in `/etc/nginx/nginx.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=taliu_api:10m rate=10r/m;
limit_req_status 429;
```

Then:
```bash
cp /opt/taliu/nginx/api.atoue.io.conf /etc/nginx/sites-available/api.atoue.io.conf
nginx -t
systemctl reload nginx
```

- [ ] **Step 3: Commit**

```bash
git add nginx/api.atoue.io.conf
git commit -m "feat: add Nginx rate limiting to api config"
```

---

## Task 12: Deploy to VPS

- [ ] **Step 1: Push all commits**

```bash
git push origin main
```

- [ ] **Step 2: SSH into VPS and pull**

```bash
ssh root@204.168.190.33
cd /opt/taliu
git pull origin main
```

- [ ] **Step 3: Copy updated .env.example and add new vars**

```bash
# Add these to /opt/taliu/backend/.env
DATABASE_URL=postgresql://taliu:taliu@postgres:5432/taliu
POSTGRES_USER=taliu
POSTGRES_PASSWORD=taliu
POSTGRES_DB=taliu
MESSAGE_LIMIT=2
```

- [ ] **Step 4: Rebuild and restart**

```bash
docker-compose down
docker rm -f taliu-api 2>/dev/null || true
docker-compose up -d --build
```

- [ ] **Step 5: Re-run ingestion**

```bash
docker-compose exec api python -m app.ingestion.ingest
```

- [ ] **Step 6: Apply Nginx rate limit zone**

Add to `http` block in `/etc/nginx/nginx.conf`:
```nginx
limit_req_zone $binary_remote_addr zone=taliu_api:10m rate=10r/m;
limit_req_status 429;
```

Then:
```bash
cp /opt/taliu/nginx/api.atoue.io.conf /etc/nginx/sites-available/api.atoue.io.conf
nginx -t
systemctl reload nginx
```

- [ ] **Step 7: Verify health**

```bash
curl https://api.atoue.io/api/health
```

Expected: `{"status":"healthy","qdrant":"connected"}`

- [ ] **Step 8: Verify PostgreSQL tables created**

```bash
docker-compose exec postgres psql -U taliu -d taliu -c "\dt"
```

Expected: tables `sessions` and `messages` listed.

- [ ] **Step 9: Test limit enforcement**

Send 3 messages to `https://api.atoue.io/api/chat` (limit is 2). Third message should return 429 with `{"detail": "limit_reached"}`.

```bash
curl -s -X POST https://api.atoue.io/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "session_id": "test-session-123"}' | head -5
```

Run this 3 times with the same `session_id`. Third response should be:
```json
{"detail": "limit_reached"}
```