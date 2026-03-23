import aiosqlite
import json
from pathlib import Path
from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT UNIQUE NOT NULL,
    account_name TEXT,
    real_name TEXT DEFAULT '',
    win_loss REAL DEFAULT 0,
    balance REAL DEFAULT 0,
    action REAL DEFAULT 0,
    raw_data TEXT DEFAULT '{}',
    last_scraped_at TEXT
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_message_id TEXT UNIQUE NOT NULL,
    sender TEXT,
    subject TEXT,
    amount REAL,
    payment_method TEXT,
    date TEXT,
    linked_agent_id INTEGER,
    match_status TEXT DEFAULT 'unmatched',
    FOREIGN KEY (linked_agent_id) REFERENCES agents(id)
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    records_affected INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


async def get_db() -> aiosqlite.Connection:
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()


# --- Agent CRUD ---

async def upsert_agents(agents_data: list[dict]):
    db = await get_db()
    try:
        for agent in agents_data:
            await db.execute("""
                INSERT INTO agents (account_id, account_name, win_loss, balance, action, raw_data, last_scraped_at)
                VALUES (:account_id, :account_name, :win_loss, :balance, :action, :raw_data, datetime('now'))
                ON CONFLICT(account_id) DO UPDATE SET
                    account_name = excluded.account_name,
                    win_loss = excluded.win_loss,
                    balance = excluded.balance,
                    action = excluded.action,
                    raw_data = excluded.raw_data,
                    last_scraped_at = excluded.last_scraped_at
            """, {
                "account_id": agent.get("account_id", ""),
                "account_name": agent.get("account_name", ""),
                "win_loss": agent.get("win_loss", 0),
                "balance": agent.get("balance", 0),
                "action": agent.get("action", 0),
                "raw_data": json.dumps(agent.get("raw_data", {})),
            })
        await db.commit()
        return len(agents_data)
    finally:
        await db.close()


async def get_all_agents():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM agents ORDER BY account_name")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def update_agent_real_name(agent_id: int, real_name: str):
    db = await get_db()
    try:
        await db.execute("UPDATE agents SET real_name = ? WHERE id = ?", (real_name, agent_id))
        await db.commit()
    finally:
        await db.close()


# --- Payment CRUD ---

async def insert_payments(payments_data: list[dict]):
    db = await get_db()
    try:
        inserted = 0
        for p in payments_data:
            try:
                await db.execute("""
                    INSERT INTO payments (gmail_message_id, sender, subject, amount, payment_method, date)
                    VALUES (:gmail_message_id, :sender, :subject, :amount, :payment_method, :date)
                """, p)
                inserted += 1
            except aiosqlite.IntegrityError:
                pass  # duplicate gmail_message_id
        await db.commit()
        return inserted
    finally:
        await db.close()


async def get_all_payments():
    db = await get_db()
    try:
        cursor = await db.execute("""
            SELECT p.*, a.account_name as linked_agent_name
            FROM payments p
            LEFT JOIN agents a ON p.linked_agent_id = a.id
            ORDER BY p.date DESC
        """)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def link_payment(payment_id: int, agent_id: int | None, match_status: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE payments SET linked_agent_id = ?, match_status = ? WHERE id = ?",
            (agent_id, match_status, payment_id)
        )
        await db.commit()
    finally:
        await db.close()


# --- Dashboard ---

async def get_dashboard_summary():
    db = await get_db()
    try:
        agents_cursor = await db.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(action),0) as total_action, COALESCE(SUM(win_loss),0) as total_wl FROM agents")
        agents_row = await agents_cursor.fetchone()

        payments_cursor = await db.execute("SELECT COUNT(*) as cnt FROM payments WHERE match_status = 'unmatched'")
        payments_row = await payments_cursor.fetchone()

        return {
            "total_agents": agents_row["cnt"],
            "total_action": agents_row["total_action"],
            "net_win_loss": agents_row["total_wl"],
            "unmatched_payments": payments_row["cnt"],
        }
    finally:
        await db.close()


# --- Scrape Log ---

async def log_scrape(run_type: str, status: str, message: str = "", records_affected: int = 0):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO scrape_log (run_type, status, message, records_affected) VALUES (?, ?, ?, ?)",
            (run_type, status, message, records_affected)
        )
        await db.commit()
    finally:
        await db.close()


async def get_last_scrape(run_type: str):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM scrape_log WHERE run_type = ? ORDER BY created_at DESC LIMIT 1",
            (run_type,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()
