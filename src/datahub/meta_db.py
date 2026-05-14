from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


class MetaDB:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS job_status (
            job_name TEXT PRIMARY KEY,
            table_name TEXT NOT NULL,
            last_trade_date TEXT,
            last_ts_code TEXT,
            status TEXT NOT NULL,
            last_run_time TEXT,
            message TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS task_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            run_time TEXT NOT NULL,
            status TEXT NOT NULL,
            rows_written INTEGER DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            error_message TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS data_version (
            table_name TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            field_hash TEXT,
            updated_at TEXT NOT NULL,
            note TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS asset_universe (
            ts_code TEXT PRIMARY KEY,
            symbol TEXT,
            name TEXT,
            exchange TEXT,
            market TEXT,
            list_status TEXT,
            list_date TEXT,
            delist_date TEXT,
            is_active INTEGER DEFAULT 1,
            updated_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS factor_registry (
            factor_name TEXT PRIMARY KEY,
            source_tables TEXT NOT NULL,
            frequency TEXT NOT NULL,
            formula_desc TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
        """)

        self.conn.commit()

    def get_last_trade_date(self, job_name: str) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT last_trade_date FROM job_status WHERE job_name = ?", (job_name,))
        row = cur.fetchone()
        return row[0] if row and row[0] else None

    def upsert_job_status(
        self,
        job_name: str,
        table_name: str,
        last_trade_date: str | None,
        status: str,
        last_run_time: str,
        message: str = "",
        last_ts_code: str | None = None
    ):
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO job_status (job_name, table_name, last_trade_date, last_ts_code, status, last_run_time, message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_name) DO UPDATE SET
            table_name=excluded.table_name,
            last_trade_date=excluded.last_trade_date,
            last_ts_code=excluded.last_ts_code,
            status=excluded.status,
            last_run_time=excluded.last_run_time,
            message=excluded.message
        """, (job_name, table_name, last_trade_date, last_ts_code, status, last_run_time, message))
        self.conn.commit()

    def insert_task_log(
        self,
        job_name: str,
        table_name: str,
        run_time: str,
        status: str,
        rows_written: int = 0,
        start_date: str | None = None,
        end_date: str | None = None,
        error_message: str | None = None
    ):
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO task_log (job_name, table_name, run_time, status, rows_written, start_date, end_date, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_name, table_name, run_time, status, rows_written, start_date, end_date, error_message))
        self.conn.commit()

    def replace_asset_universe(self, df):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM asset_universe")
        rows = df.to_dict("records")
        cur.executemany("""
        INSERT INTO asset_universe
        (ts_code, symbol, name, exchange, market, list_status, list_date, delist_date, is_active, updated_at)
        VALUES (:ts_code, :symbol, :name, :exchange, :market, :list_status, :list_date, :delist_date, :is_active, :updated_at)
        """, rows)
        self.conn.commit()

    def get_active_ts_codes(self) -> list[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT ts_code FROM asset_universe WHERE is_active = 1")
        return [row[0] for row in cur.fetchall()]