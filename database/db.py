import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "videobot.db")

# Ensure parent directory exists for DB_PATH (e.g. mounted persistent volume /data)
_db_dir = os.path.dirname(DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    await db.execute("PRAGMA temp_store=MEMORY")
    return db


async def init_db():
    """Initialize all tables and high-speed indexes on first run."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA temp_store=MEMORY")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id          INTEGER PRIMARY KEY,
                username         TEXT,
                full_name        TEXT,
                is_premium       INTEGER DEFAULT 0,
                free_uses        INTEGER DEFAULT 5,
                total_uses       INTEGER DEFAULT 0,
                joined_at        TEXT    DEFAULT (datetime('now')),
                premium_since    TEXT,
                premium_until    TEXT,
                is_banned        INTEGER DEFAULT 0
            )
        """)

        # Migration: add premium_until if upgrading existing DB
        try:
            await db.execute("ALTER TABLE users ADD COLUMN premium_until TEXT")
        except Exception:
            pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                link      TEXT,
                title     TEXT,
                quality   TEXT,
                action    TEXT,           -- 'play' | 'download'
                file_size INTEGER,
                timestamp TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                order_id       TEXT    UNIQUE,
                payment_link_id TEXT,
                payment_id     TEXT,
                amount_paise   INTEGER,
                status         TEXT    DEFAULT 'pending',  -- pending | paid | failed
                created_at     TEXT    DEFAULT (datetime('now')),
                paid_at        TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_deletions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                delete_at  TEXT    NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS video_cache (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                file_key    TEXT UNIQUE,
                file_id     TEXT NOT NULL,
                title       TEXT,
                file_size   INTEGER,
                duration    INTEGER,
                quality     TEXT,
                cached_at   TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_video_cache_key ON video_cache(file_key)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_downloads_user_id ON downloads(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_deletions_delete_at ON scheduled_deletions(delete_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)")
        await db.commit()


async def checkpoint_db():
    """Flush WAL journal to ensure videobot.db is 100% synchronized for backup."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
