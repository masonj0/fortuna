import asyncio
import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from zoneinfo import ZoneInfo

import structlog

EASTERN = ZoneInfo("America/New_York")

def is_frozen() -> bool:
    import sys
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def get_db_path() -> str:
    import sys
    if os.environ.get("FORTUNA_DB_PATH"):
        return os.environ.get("FORTUNA_DB_PATH")

    if is_frozen() and sys.platform == "win32":
        appdata = os.getenv('APPDATA')
        if appdata:
            db_dir = Path(appdata) / "Fortuna"
            db_dir.mkdir(parents=True, exist_ok=True)
            return str(db_dir / "fortuna.db")
    return "fortuna.db"

def ensure_eastern(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=EASTERN)
    return dt.astimezone(EASTERN)

class FortunaDB:
    """
    Thread-safe SQLite backend for Fortuna using the standard library.
    Handles persistence for tips, predictions, and audit outcomes.
    """
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._conn = None
        self._conn_lock = threading.Lock()

        self._initialized = False
        self.logger = structlog.get_logger(self.__class__.__name__)

    def _get_conn(self):
        with self._conn_lock:
            if not self._conn:
                self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    @asynccontextmanager
    async def get_connection(self):
        """Returns an async context manager for a database connection."""
        try:
            import aiosqlite
        except ImportError:
            self.logger.error("aiosqlite not installed. Async database features will fail.")
            raise

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    async def _run_in_executor(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    async def initialize(self):
        """Creates the database schema if it doesn't exist."""
        if self._initialized: return

        def _init():
            conn = self._get_conn()
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS harvest_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        region TEXT,
                        adapter_name TEXT NOT NULL,
                        race_count INTEGER NOT NULL,
                        max_odds REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tips (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        race_id TEXT NOT NULL,
                        venue TEXT NOT NULL,
                        race_number INTEGER NOT NULL,
                        discipline TEXT,
                        start_time TEXT NOT NULL,
                        report_date TEXT NOT NULL,
                        is_goldmine INTEGER NOT NULL,
                        gap12 TEXT,
                        top_five TEXT,
                        selection_number INTEGER,
                        selection_name TEXT,
                        audit_completed INTEGER DEFAULT 0,
                        verdict TEXT,
                        net_profit REAL,
                        selection_position INTEGER,
                        actual_top_5 TEXT,
                        actual_2nd_fav_odds REAL,
                        trifecta_payout REAL,
                        trifecta_combination TEXT,
                        superfecta_payout REAL,
                        superfecta_combination TEXT,
                        top1_place_payout REAL,
                        top2_place_payout REAL,
                        predicted_2nd_fav_odds REAL,
                        audit_timestamp TEXT
                    )
                """)
                # Cleanup potential duplicates
                try:
                    conn.execute("DROP INDEX IF EXISTS idx_race_report")
                    conn.execute("""
                        DELETE FROM tips
                        WHERE id NOT IN (
                            SELECT MAX(id)
                            FROM tips
                            GROUP BY race_id
                        )
                    """)
                    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_race_id ON tips (race_id)")
                except Exception as e:
                    self.logger.error("Failed to cleanup or create unique index", error=str(e))

                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON tips (audit_completed, start_time)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_venue ON tips (venue)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_discipline ON tips (discipline)")

                # Add missing columns
                cursor = conn.execute("PRAGMA table_info(tips)")
                columns = [column[1] for column in cursor.fetchall()]
                for col in ["superfecta_payout", "superfecta_combination", "top1_place_payout", "top2_place_payout",
                            "discipline", "predicted_2nd_fav_odds", "actual_2nd_fav_odds", "selection_name"]:
                    if col not in columns:
                        conn.execute(f"ALTER TABLE tips ADD COLUMN {col} {'REAL' if 'payout' in col or 'odds' in col else 'TEXT'}")

        await self._run_in_executor(_init)

        def _get_version():
            cursor = self._get_conn().execute("SELECT MAX(version) FROM schema_version")
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else 0

        current_version = await self._run_in_executor(_get_version)

        if current_version < 2:
            await self.migrate_utc_to_eastern()
            def _update_version():
                with self._get_conn() as conn:
                    conn.execute("INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (2, ?)", (datetime.now(EASTERN).isoformat(),))
            await self._run_in_executor(_update_version)

        self._initialized = True
        self.logger.info("Database initialized", path=self.db_path)

    async def migrate_utc_to_eastern(self) -> None:
        """Migrates existing database records from UTC to US Eastern Time."""
        def _migrate():
            conn = self._get_conn()
            cursor = conn.execute("""
                SELECT id, start_time, report_date, audit_timestamp FROM tips
                WHERE start_time LIKE '%+00:00' OR start_time LIKE '%Z'
                OR report_date LIKE '%+00:00' OR report_date LIKE '%Z'
                OR audit_timestamp LIKE '%+00:00' OR audit_timestamp LIKE '%Z'
            """)
            rows = cursor.fetchall()
            if not rows: return
            for row in rows:
                updates = {}
                for col in ["start_time", "report_date", "audit_timestamp"]:
                    if col not in row.keys(): continue
                    val = row[col]
                    if val:
                        try:
                            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                            updates[col] = ensure_eastern(dt).isoformat()
                        except Exception: pass
                if updates:
                    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
                    conn.execute(f"UPDATE tips SET {set_clause} WHERE id = ?", (*updates.values(), row["id"]))
        await self._run_in_executor(_migrate)

    async def log_harvest(self, harvest_summary: Dict[str, Any], region: Optional[str] = None):
        if not self._initialized: await self.initialize()
        def _log():
            conn = self._get_conn()
            now = datetime.now(EASTERN).isoformat()
            to_insert = []
            for adapter, data in harvest_summary.items():
                count = data.get("count", 0) if isinstance(data, dict) else data
                max_odds = data.get("max_odds", 0.0) if isinstance(data, dict) else 0.0
                to_insert.append((now, region, adapter, count, max_odds))
            if to_insert:
                with conn:
                    conn.executemany("INSERT INTO harvest_logs (timestamp, region, adapter_name, race_count, max_odds) VALUES (?, ?, ?, ?, ?)", to_insert)
        await self._run_in_executor(_log)

    async def get_adapter_scores(self, days: int = 30) -> Dict[str, float]:
        if not self._initialized: await self.initialize()
        def _get():
            conn = self._get_conn()
            cutoff = (datetime.now(EASTERN) - timedelta(days=days)).isoformat()
            cursor = conn.execute("""
                SELECT adapter_name, AVG(race_count) as avg_count, AVG(max_odds) as avg_max_odds
                FROM harvest_logs WHERE timestamp > ? GROUP BY adapter_name
            """, (cutoff,))
            scores = {}
            for row in cursor.fetchall():
                scores[row["adapter_name"]] = (row["avg_count"] or 0) + ((row["avg_max_odds"] or 0) * 2)
            return scores
        return await self._run_in_executor(_get)

    async def log_tips(self, tips: List[Dict[str, Any]]):
        if not self._initialized: await self.initialize()
        def _log():
            conn = self._get_conn()
            race_ids = [t.get("race_id") for t in tips if t.get("race_id")]
            if not race_ids: return
            placeholders = ",".join(["?"] * len(race_ids))
            cursor = conn.execute(f"SELECT race_id FROM tips WHERE race_id IN ({placeholders})", (*race_ids,))
            already_logged = {row["race_id"] for row in cursor.fetchall()}
            to_insert = []
            for tip in tips:
                rid = tip.get("race_id")
                if rid and rid not in already_logged:
                    to_insert.append((
                        rid, tip.get("venue"), tip.get("race_number"),
                        tip.get("discipline"), tip.get("start_time"), tip.get("report_date") or datetime.now(EASTERN).isoformat(),
                        1 if tip.get("is_goldmine") else 0, str(tip.get("1Gap2", 0.0)),
                        tip.get("top_five"), tip.get("selection_number"), tip.get("selection_name"),
                        float(tip.get("predicted_2nd_fav_odds")) if tip.get("predicted_2nd_fav_odds") is not None else None
                    ))
                    already_logged.add(rid)
            if to_insert:
                with conn:
                    conn.executemany("""
                        INSERT OR IGNORE INTO tips (
                            race_id, venue, race_number, discipline, start_time, report_date,
                            is_goldmine, gap12, top_five, selection_number, selection_name, predicted_2nd_fav_odds
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, to_insert)
        await self._run_in_executor(_log)

    async def get_unverified_tips(self, lookback_hours: int = 48) -> List[Dict[str, Any]]:
        if not self._initialized: await self.initialize()
        def _get():
            conn = self._get_conn()
            now = datetime.now(EASTERN)
            cutoff = (now - timedelta(hours=lookback_hours)).isoformat()
            cursor = conn.execute("SELECT * FROM tips WHERE audit_completed = 0 AND report_date > ? AND start_time < ?", (cutoff, now.isoformat()))
            return [dict(row) for row in cursor.fetchall()]
        return await self._run_in_executor(_get)

    async def get_all_audited_tips(self) -> List[Dict[str, Any]]:
        if not self._initialized: await self.initialize()
        def _get():
            cursor = self._get_conn().execute("SELECT * FROM tips WHERE audit_completed = 1 ORDER BY start_time DESC")
            return [dict(row) for row in cursor.fetchall()]
        return await self._run_in_executor(_get)

    async def get_recent_audited_goldmines(self, limit: int = 15) -> List[Dict[str, Any]]:
        if not self._initialized: await self.initialize()
        def _get():
            cursor = self._get_conn().execute(
                "SELECT * FROM tips WHERE audit_completed = 1 AND is_goldmine = 1 ORDER BY start_time DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
        return await self._run_in_executor(_get)

    async def get_recent_tips(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not self._initialized: await self.initialize()
        def _get():
            cursor = self._get_conn().execute("SELECT * FROM tips ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
        return await self._run_in_executor(_get)

    async def update_audit_result(self, race_id: str, outcome: Dict[str, Any]):
        if not self._initialized: await self.initialize()
        def _update():
            conn = self._get_conn()
            with conn:
                conn.execute("""
                    UPDATE tips SET
                        audit_completed = 1, verdict = ?, net_profit = ?, selection_position = ?,
                        actual_top_5 = ?, actual_2nd_fav_odds = ?, trifecta_payout = ?, trifecta_combination = ?,
                        superfecta_payout = ?, superfecta_combination = ?, top1_place_payout = ?, top2_place_payout = ?,
                        audit_timestamp = ?
                    WHERE id = (SELECT id FROM tips WHERE race_id = ? AND audit_completed = 0 LIMIT 1)
                """, (
                    outcome.get("verdict"), outcome.get("net_profit"), outcome.get("selection_position"),
                    outcome.get("actual_top_5"), outcome.get("actual_2nd_fav_odds"), outcome.get("trifecta_payout"),
                    outcome.get("trifecta_combination"), outcome.get("superfecta_payout"), outcome.get("superfecta_combination"),
                    outcome.get("top1_place_payout"), outcome.get("top2_place_payout"), datetime.now(EASTERN).isoformat(), race_id
                ))
        await self._run_in_executor(_update)

    async def update_audit_results_batch(self, outcomes: List[Tuple[str, Dict[str, Any]]]):
        if not outcomes: return
        if not self._initialized: await self.initialize()
        def _update():
            conn = self._get_conn()
            with conn:
                for race_id, outcome in outcomes:
                    conn.execute("""
                        UPDATE tips SET
                            audit_completed = 1, verdict = ?, net_profit = ?, selection_position = ?,
                            actual_top_5 = ?, actual_2nd_fav_odds = ?, trifecta_payout = ?, trifecta_combination = ?,
                            superfecta_payout = ?, superfecta_combination = ?, top1_place_payout = ?, top2_place_payout = ?,
                            audit_timestamp = ?
                        WHERE id = (SELECT id FROM tips WHERE race_id = ? AND audit_completed = 0 LIMIT 1)
                    """, (
                        outcome.get("verdict"), outcome.get("net_profit"), outcome.get("selection_position"),
                        outcome.get("actual_top_5"), outcome.get("actual_2nd_fav_odds"), outcome.get("trifecta_payout"),
                        outcome.get("trifecta_combination"), outcome.get("superfecta_payout"), outcome.get("superfecta_combination"),
                        outcome.get("top1_place_payout"), outcome.get("top2_place_payout"), outcome.get("audit_timestamp") or datetime.now(EASTERN).isoformat(), race_id
                    ))
        await self._run_in_executor(_update)

    async def clear_all_tips(self):
        if not self._initialized: await self.initialize()
        def _clear():
            conn = self._get_conn()
            with conn:
                conn.execute("DELETE FROM tips")
            conn.execute("VACUUM")
        await self._run_in_executor(_clear)

    async def close(self) -> None:
        def _close():
            with self._conn_lock:
                if self._conn:
                    self._conn.close()
                    self._conn = None
        await self._run_in_executor(_close)
        self._executor.shutdown(wait=True)

    async def migrate_from_json(self, json_path: str = "hot_tips_db.json"):
        path = Path(json_path)
        if not path.exists(): return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if not isinstance(data, list): return
            if not self._initialized: await self.initialize()
            def _migrate():
                conn = self._get_conn()
                for entry in data:
                    with conn:
                        conn.execute("""
                            INSERT OR IGNORE INTO tips (
                                race_id, venue, race_number, discipline, start_time, report_date,
                                is_goldmine, audit_completed, verdict, net_profit
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            entry.get("race_id"), entry.get("venue"), entry.get("race_number"),
                            entry.get("discipline"), entry.get("start_time"), entry.get("report_date"),
                            1 if entry.get("is_goldmine") else 0, 1 if entry.get("verdict") else 0,
                            entry.get("verdict"), entry.get("net_profit")
                        ))
            await self._run_in_executor(_migrate)
        except Exception as e:
            self.logger.error("JSON migration failed", error=str(e))
