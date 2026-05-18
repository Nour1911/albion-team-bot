import asyncpg
import os

_pool = None


async def init_db():
    global _pool
    db_url = os.getenv("DATABASE_URL", "")
    ssl = "require" if "supabase" in db_url else None
    _pool = await asyncpg.create_pool(db_url, ssl=ssl)
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


# --- Voice Settings ---

async def get_voice_creation_channel(guild_id: int):
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT creation_channel_id FROM albion_voice_settings WHERE guild_id = $1",
            guild_id,
        )
        return row["creation_channel_id"] if row else None


async def set_voice_creation_channel(guild_id: int, channel_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO albion_voice_settings (guild_id, creation_channel_id)
               VALUES ($1, $2)
               ON CONFLICT (guild_id) DO UPDATE SET creation_channel_id = $2""",
            guild_id, channel_id,
        )


# --- Custom Roles ---

async def add_custom_role(guild_id: int, role_key: str, name: str, emoji: str, description: str = ""):
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO albion_custom_roles (guild_id, role_key, name, emoji, description)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (guild_id, role_key) DO UPDATE SET name = $3, emoji = $4, description = $5""",
            guild_id, role_key, name, emoji, description,
        )


async def remove_custom_role(guild_id: int, role_key: str):
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM albion_custom_roles WHERE guild_id = $1 AND role_key = $2",
            guild_id, role_key,
        )


async def get_custom_roles(guild_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM albion_custom_roles WHERE guild_id = $1 ORDER BY id",
            guild_id,
        )


# --- Players ---

async def add_player(discord_id: int, username: str, role: str = "Flex"):
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO albion_players (discord_id, username, role) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            discord_id, username, role,
        )


async def set_player_role(discord_id: int, role: str):
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE albion_players SET role = $1 WHERE discord_id = $2",
            role, discord_id,
        )


async def get_player(discord_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM albion_players WHERE discord_id = $1", discord_id
        )


async def get_all_players():
    async with _pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM albion_players ORDER BY role")


# --- Events ---

async def create_event(name: str, event_type: str, date_time: str, created_by: int):
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO albion_events (name, event_type, date_time, created_by) VALUES ($1, $2, $3, $4) RETURNING id",
            name, event_type, date_time, created_by,
        )
        return row["id"]


async def update_event_message(event_id: int, channel_id: int, message_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE albion_events SET channel_id = $1, message_id = $2 WHERE id = $3",
            channel_id, message_id, event_id,
        )


async def get_event(event_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM albion_events WHERE id = $1", event_id
        )


async def get_upcoming_events():
    async with _pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM albion_events WHERE date_time >= NOW()::text ORDER BY date_time"
        )


async def get_all_events():
    async with _pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM albion_events ORDER BY date_time DESC"
        )


async def delete_event(event_id: int):
    async with _pool.acquire() as conn:
        await conn.execute("DELETE FROM albion_attendance WHERE event_id = $1", event_id)
        await conn.execute("DELETE FROM albion_events WHERE id = $1", event_id)


# --- Attendance ---

async def set_attendance(event_id: int, player_id: int, status: str):
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO albion_attendance (event_id, player_id, status)
               VALUES ($1, $2, $3)
               ON CONFLICT (event_id, player_id) DO UPDATE SET status = $3""",
            event_id, player_id, status,
        )


async def get_event_attendance(event_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetch(
            """SELECT a.*, p.username, p.role FROM albion_attendance a
               JOIN albion_players p ON a.player_id = p.discord_id
               WHERE a.event_id = $1""",
            event_id,
        )


async def get_player_stats(discord_id: int):
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent
               FROM albion_attendance WHERE player_id = $1""",
            discord_id,
        )


async def get_all_player_stats():
    async with _pool.acquire() as conn:
        return await conn.fetch(
            """SELECT p.username, p.role,
                COUNT(a.id) as total,
                SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) as absent
               FROM albion_players p
               LEFT JOIN albion_attendance a ON p.discord_id = a.player_id
               GROUP BY p.discord_id, p.username, p.role
               ORDER BY present DESC"""
        )
