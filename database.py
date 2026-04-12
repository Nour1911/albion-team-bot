import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER UNIQUE NOT NULL,
                username TEXT NOT NULL,
                role TEXT DEFAULT 'Flex',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                date_time TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                channel_id INTEGER,
                message_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (event_id) REFERENCES events(id),
                FOREIGN KEY (player_id) REFERENCES players(discord_id),
                UNIQUE(event_id, player_id)
            )
        """)
        await db.commit()


# --- Players ---

async def add_player(discord_id: int, username: str, role: str = "Flex"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO players (discord_id, username, role) VALUES (?, ?, ?)",
            (discord_id, username, role),
        )
        await db.commit()


async def set_player_role(discord_id: int, role: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE players SET role = ? WHERE discord_id = ?",
            (role, discord_id),
        )
        await db.commit()


async def get_player(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM players WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            return await cursor.fetchone()


async def get_all_players():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM players ORDER BY role") as cursor:
            return await cursor.fetchall()


# --- Events ---

async def create_event(name: str, event_type: str, date_time: str, created_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO events (name, event_type, date_time, created_by) VALUES (?, ?, ?, ?)",
            (name, event_type, date_time, created_by),
        )
        await db.commit()
        return cursor.lastrowid


async def update_event_message(event_id: int, channel_id: int, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE events SET channel_id = ?, message_id = ? WHERE id = ?",
            (channel_id, message_id, event_id),
        )
        await db.commit()


async def get_event(event_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ) as cursor:
            return await cursor.fetchone()


async def get_upcoming_events():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM events WHERE date_time >= datetime('now') ORDER BY date_time"
        ) as cursor:
            return await cursor.fetchall()


async def get_all_events():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM events ORDER BY date_time DESC"
        ) as cursor:
            return await cursor.fetchall()


async def delete_event(event_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM attendance WHERE event_id = ?", (event_id,))
        await db.execute("DELETE FROM events WHERE id = ?", (event_id,))
        await db.commit()


# --- Attendance ---

async def set_attendance(event_id: int, player_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO attendance (event_id, player_id, status)
               VALUES (?, ?, ?)
               ON CONFLICT(event_id, player_id) DO UPDATE SET status = ?""",
            (event_id, player_id, status, status),
        )
        await db.commit()


async def get_event_attendance(event_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT a.*, p.username, p.role FROM attendance a
               JOIN players p ON a.player_id = p.discord_id
               WHERE a.event_id = ?""",
            (event_id,),
        ) as cursor:
            return await cursor.fetchall()


async def get_player_stats(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent
               FROM attendance WHERE player_id = ?""",
            (discord_id,),
        ) as cursor:
            return await cursor.fetchone()


async def get_all_player_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT p.username, p.role,
                COUNT(a.id) as total,
                SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) as absent
               FROM players p
               LEFT JOIN attendance a ON p.discord_id = a.player_id
               GROUP BY p.discord_id
               ORDER BY present DESC"""
        ) as cursor:
            return await cursor.fetchall()
