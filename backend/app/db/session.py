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
