"""All database query functions used across handlers."""
from __future__ import annotations
from typing import Optional
import aiosqlite
from database.db import get_db, DB_PATH
from config import FREE_QUOTA


# ══════════════════════════════════════════════════════════
#  USER FUNCTIONS
# ══════════════════════════════════════════════════════════

async def get_or_create_user(user_id: int, username: str, full_name: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
        """, (user_id, username, full_name))
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}


async def get_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_username(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET username=?, full_name=? WHERE user_id=?",
            (username, full_name, user_id)
        )
        await db.commit()


async def can_use(user_id: int) -> tuple[bool, str]:
    """Returns (allowed, reason)."""
    user = await get_user(user_id)
    if not user:
        return False, "User not found. Send /start first."
    if user["is_banned"]:
        return False, "⛔ You are banned from using this bot."
    if user["is_premium"]:
        return True, "premium"
    if user["free_uses"] > 0:
        return True, "free"
    return False, "quota_exceeded"


async def decrement_free_uses(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET free_uses  = MAX(free_uses - 1, 0),
                total_uses = total_uses + 1
            WHERE user_id = ? AND is_premium = 0
        """, (user_id,))
        await db.commit()


async def increment_total_uses(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET total_uses = total_uses + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def grant_premium(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET is_premium = 1,
                premium_since = datetime('now')
            WHERE user_id = ?
        """, (user_id,))
        await db.commit()


async def revoke_premium(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET is_premium = 0,
                premium_since = NULL
            WHERE user_id = ?
        """, (user_id,))
        await db.commit()


async def add_free_quota(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET free_uses = free_uses + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


# ══════════════════════════════════════════════════════════
#  DOWNLOAD LOG FUNCTIONS
# ══════════════════════════════════════════════════════════

async def log_download(user_id: int, link: str, title: str,
                        quality: str, action: str, file_size: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO downloads (user_id, link, title, quality, action, file_size)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, link, title, quality, action, file_size))
        await db.commit()


# ══════════════════════════════════════════════════════════
#  PAYMENT FUNCTIONS
# ══════════════════════════════════════════════════════════

async def create_payment_record(user_id: int, order_id: str,
                                 payment_link_id: str, amount_paise: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO payments (user_id, order_id, payment_link_id, amount_paise)
            VALUES (?, ?, ?, ?)
        """, (user_id, order_id, payment_link_id, amount_paise))
        await db.commit()


async def mark_payment_paid(order_id: str, payment_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE payments
            SET status = 'paid',
                payment_id = ?,
                paid_at = datetime('now')
            WHERE order_id = ?
        """, (payment_id, order_id))
        await db.commit()


async def get_user_by_order(order_id: str) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM payments WHERE order_id = ?", (order_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


# ══════════════════════════════════════════════════════════
#  ADMIN STATS FUNCTIONS
# ══════════════════════════════════════════════════════════

async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        total = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        premium = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE is_premium=1")).fetchone())[0]
        banned = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE is_banned=1")).fetchone())[0]
        today_dl = (await (await db.execute(
            "SELECT COUNT(*) FROM downloads WHERE date(timestamp)=date('now')")).fetchone())[0]
        total_dl = (await (await db.execute("SELECT COUNT(*) FROM downloads")).fetchone())[0]
        total_paid = (await (await db.execute(
            "SELECT COUNT(*) FROM payments WHERE status='paid'")).fetchone())[0]
        return {
            "total_users": total,
            "premium_users": premium,
            "banned_users": banned,
            "downloads_today": today_dl,
            "total_downloads": total_dl,
            "total_paid": total_paid,
        }


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE is_banned=0"
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def search_user(username: str) -> Optional[dict]:
    """Search by username (without @)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE username = ?", (username.lstrip("@"),)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ══════════════════════════════════════════════════════════
#  AUTO-DELETE SCHEDULE FUNCTIONS
# ══════════════════════════════════════════════════════════

async def schedule_message_deletion(chat_id: int, message_id: int, delay_seconds: int = 1800):
    """Schedule a message to be deleted after delay_seconds (default 30 min)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO scheduled_deletions (chat_id, message_id, delete_at)
            VALUES (?, ?, datetime('now', '+' || ? || ' seconds'))
        """, (chat_id, message_id, delay_seconds))
        await db.commit()


async def get_due_deletions() -> list[dict]:
    """Fetch all messages whose deletion time has passed."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM scheduled_deletions
            WHERE delete_at <= datetime('now')
            LIMIT 50
        """)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def remove_scheduled_deletion(record_id: int):
    """Remove a processed deletion record."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM scheduled_deletions WHERE id = ?", (record_id,)
        )
        await db.commit()


# ══════════════════════════════════════════════════════════
#  TELEGRAM VIDEO FILE_ID CACHE FUNCTIONS
# ══════════════════════════════════════════════════════════

async def get_cached_video(file_key: str) -> Optional[dict]:
    """Retrieve cached Telegram file_id for instant zero-download playback."""
    if not file_key:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM video_cache WHERE file_key = ? LIMIT 1", (file_key,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def save_cached_video(
    file_key: str,
    file_id: str,
    title: str = "",
    file_size: int = 0,
    duration: int = 0,
    quality: str = "",
):
    """Store Telegram file_id in cache for instant future retrieval."""
    if not file_key or not file_id:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO video_cache (file_key, file_id, title, file_size, duration, quality)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_key) DO UPDATE SET
                file_id = excluded.file_id,
                title = excluded.title,
                file_size = excluded.file_size,
                duration = excluded.duration,
                quality = excluded.quality,
                cached_at = datetime('now')
        """, (file_key, file_id, title, file_size, duration, quality))
        await db.commit()
