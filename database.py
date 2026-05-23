import os

DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import asyncpg
else:
    import aiosqlite

_pool = None
_sqlite_path = "albion.db"


async def init_db():
    global _pool
    if USE_POSTGRES:
        ssl = "require" if "supabase" in DATABASE_URL else None
        _pool = await asyncpg.create_pool(DATABASE_URL, ssl=ssl)
        async with _pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_players (
                    id SERIAL PRIMARY KEY,
                    discord_id BIGINT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    role TEXT DEFAULT 'Flex',
                    joined_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_events (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    date_time TEXT NOT NULL,
                    created_by BIGINT NOT NULL,
                    channel_id BIGINT,
                    message_id BIGINT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_attendance (
                    id SERIAL PRIMARY KEY,
                    event_id INTEGER NOT NULL,
                    player_id BIGINT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    UNIQUE(event_id, player_id)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_custom_roles (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    role_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    emoji TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    UNIQUE(guild_id, role_key)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_voice_settings (
                    guild_id BIGINT PRIMARY KEY,
                    creation_channel_id BIGINT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_comp_posts (
                    message_id BIGINT PRIMARY KEY,
                    channel_id BIGINT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_comp_signups (
                    message_id BIGINT NOT NULL,
                    role_key TEXT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username TEXT NOT NULL,
                    UNIQUE(message_id, user_id)
                )
            """)
    else:
        async with aiosqlite.connect(_sqlite_path) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id INTEGER UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    role TEXT DEFAULT 'Flex',
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    date_time TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    channel_id INTEGER,
                    message_id INTEGER
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    UNIQUE(event_id, player_id)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_custom_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    role_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    emoji TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    UNIQUE(guild_id, role_key)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_voice_settings (
                    guild_id INTEGER PRIMARY KEY,
                    creation_channel_id INTEGER NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_comp_posts (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS albion_comp_signups (
                    message_id INTEGER NOT NULL,
                    role_key TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    UNIQUE(message_id, user_id)
                )
            """)
            await conn.commit()


# ── helpers ──────────────────────────────────────────────────────────────────

async def _pg_fetchrow(query, *args):
    async with _pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def _pg_fetch(query, *args):
    async with _pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def _pg_execute(query, *args):
    async with _pool.acquire() as conn:
        await conn.execute(query, *args)


def _pg_to_sqlite(query):
    """Convert $1,$2,... placeholders to ? for SQLite."""
    import re
    return re.sub(r'\$\d+', '?', query)


async def _sq_fetchrow(query, *args):
    q = _pg_to_sqlite(query)
    async with aiosqlite.connect(_sqlite_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(q, args) as cur:
            return await cur.fetchone()

async def _sq_fetch(query, *args):
    q = _pg_to_sqlite(query)
    async with aiosqlite.connect(_sqlite_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(q, args) as cur:
            return await cur.fetchall()

async def _sq_execute(query, *args):
    q = _pg_to_sqlite(query)
    async with aiosqlite.connect(_sqlite_path) as conn:
        await conn.execute(q, args)
        await conn.commit()

async def _sq_fetchrow_returning(query, *args):
    """Handle INSERT ... RETURNING id for SQLite using lastrowid."""
    import re
    # Strip the RETURNING clause and use lastrowid instead
    base = re.sub(r'\s+RETURNING\s+\w+', '', query, flags=re.IGNORECASE)
    q = _pg_to_sqlite(base)
    async with aiosqlite.connect(_sqlite_path) as conn:
        async with conn.execute(q, args) as cur:
            await conn.commit()
            return {"id": cur.lastrowid}


def fetchrow(query, *args):
    return _pg_fetchrow(query, *args) if USE_POSTGRES else _sq_fetchrow(query, *args)

def fetch(query, *args):
    return _pg_fetch(query, *args) if USE_POSTGRES else _sq_fetch(query, *args)

def execute(query, *args):
    return _pg_execute(query, *args) if USE_POSTGRES else _sq_execute(query, *args)

def fetchrow_returning(query, *args):
    return _pg_fetchrow(query, *args) if USE_POSTGRES else _sq_fetchrow_returning(query, *args)


# --- Voice Settings ---

async def get_voice_creation_channel(guild_id: int):
    row = await fetchrow(
        "SELECT creation_channel_id FROM albion_voice_settings WHERE guild_id = $1",
        guild_id,
    )
    return row["creation_channel_id"] if row else None


async def set_voice_creation_channel(guild_id: int, channel_id: int):
    await execute(
        """INSERT INTO albion_voice_settings (guild_id, creation_channel_id)
           VALUES ($1, $2)
           ON CONFLICT (guild_id) DO UPDATE SET creation_channel_id = $2""",
        guild_id, channel_id,
    )


# --- Custom Roles ---

async def add_custom_role(guild_id: int, role_key: str, name: str, emoji: str, description: str = ""):
    await execute(
        """INSERT INTO albion_custom_roles (guild_id, role_key, name, emoji, description)
           VALUES ($1, $2, $3, $4, $5)
           ON CONFLICT (guild_id, role_key) DO UPDATE SET name = $3, emoji = $4, description = $5""",
        guild_id, role_key, name, emoji, description,
    )


async def remove_custom_role(guild_id: int, role_key: str):
    await execute(
        "DELETE FROM albion_custom_roles WHERE guild_id = $1 AND role_key = $2",
        guild_id, role_key,
    )


async def get_custom_roles(guild_id: int):
    return await fetch(
        "SELECT * FROM albion_custom_roles WHERE guild_id = $1 ORDER BY id",
        guild_id,
    )


# --- Players ---

async def add_player(discord_id: int, username: str, role: str = "Flex"):
    await execute(
        "INSERT INTO albion_players (discord_id, username, role) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
        discord_id, username, role,
    )


async def set_player_role(discord_id: int, role: str):
    await execute(
        "UPDATE albion_players SET role = $1 WHERE discord_id = $2",
        role, discord_id,
    )


async def get_player(discord_id: int):
    return await fetchrow(
        "SELECT * FROM albion_players WHERE discord_id = $1", discord_id
    )


async def get_all_players():
    return await fetch("SELECT * FROM albion_players ORDER BY role")


# --- Events ---

async def create_event(name: str, event_type: str, date_time: str, created_by: int):
    row = await fetchrow_returning(
        "INSERT INTO albion_events (name, event_type, date_time, created_by) VALUES ($1, $2, $3, $4) RETURNING id",
        name, event_type, date_time, created_by,
    )
    return row["id"]


async def update_event_message(event_id: int, channel_id: int, message_id: int):
    await execute(
        "UPDATE albion_events SET channel_id = $1, message_id = $2 WHERE id = $3",
        channel_id, message_id, event_id,
    )


async def get_event(event_id: int):
    return await fetchrow(
        "SELECT * FROM albion_events WHERE id = $1", event_id
    )


async def get_upcoming_events():
    if USE_POSTGRES:
        return await fetch(
            "SELECT * FROM albion_events WHERE date_time >= NOW()::text ORDER BY date_time"
        )
    else:
        return await fetch(
            "SELECT * FROM albion_events WHERE date_time >= datetime('now') ORDER BY date_time"
        )


async def get_all_events():
    return await fetch(
        "SELECT * FROM albion_events ORDER BY date_time DESC"
    )


async def delete_event(event_id: int):
    await execute("DELETE FROM albion_attendance WHERE event_id = $1", event_id)
    await execute("DELETE FROM albion_events WHERE id = $1", event_id)


# --- Attendance ---

async def set_attendance(event_id: int, player_id: int, status: str):
    await execute(
        """INSERT INTO albion_attendance (event_id, player_id, status)
           VALUES ($1, $2, $3)
           ON CONFLICT (event_id, player_id) DO UPDATE SET status = $3""",
        event_id, player_id, status,
    )


async def get_event_attendance(event_id: int):
    return await fetch(
        """SELECT a.*, p.username, p.role FROM albion_attendance a
           JOIN albion_players p ON a.player_id = p.discord_id
           WHERE a.event_id = $1""",
        event_id,
    )


async def get_player_stats(discord_id: int):
    return await fetchrow(
        """SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present,
            SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent
           FROM albion_attendance WHERE player_id = $1""",
        discord_id,
    )


async def get_all_player_stats():
    return await fetch(
        """SELECT p.username, p.role,
            COUNT(a.id) as total,
            SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present,
            SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) as absent
           FROM albion_players p
           LEFT JOIN albion_attendance a ON p.discord_id = a.player_id
           GROUP BY p.discord_id, p.username, p.role
           ORDER BY present DESC"""
    )


# --- Comp Posts ---

async def create_comp_post(message_id: int, channel_id: int, title: str):
    await execute(
        "INSERT INTO albion_comp_posts (message_id, channel_id, title) VALUES ($1, $2, $3)",
        message_id, channel_id, title,
    )


async def get_comp_post(message_id: int):
    return await fetchrow(
        "SELECT * FROM albion_comp_posts WHERE message_id = $1", message_id
    )


async def get_all_comp_posts():
    return await fetch("SELECT * FROM albion_comp_posts ORDER BY created_at DESC")


async def set_comp_signup(message_id: int, role_key: str, user_id: int, username: str):
    await execute(
        """INSERT INTO albion_comp_signups (message_id, role_key, user_id, username)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (message_id, user_id) DO UPDATE SET role_key = EXCLUDED.role_key, username = EXCLUDED.username""",
        message_id, role_key, user_id, username,
    )


async def remove_comp_signup(message_id: int, user_id: int):
    await execute(
        "DELETE FROM albion_comp_signups WHERE message_id = $1 AND user_id = $2",
        message_id, user_id,
    )


async def get_comp_signup_role(message_id: int, user_id: int):
    row = await fetchrow(
        "SELECT role_key FROM albion_comp_signups WHERE message_id = $1 AND user_id = $2",
        message_id, user_id,
    )
    return row["role_key"] if row else None


async def get_comp_signups(message_id: int) -> dict:
    rows = await fetch(
        "SELECT role_key, user_id, username FROM albion_comp_signups WHERE message_id = $1",
        message_id,
    )
    result = {}
    for row in rows:
        result.setdefault(row["role_key"], []).append((row["user_id"], row["username"]))
    return result
