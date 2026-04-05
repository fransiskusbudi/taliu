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
