"""
Base Repository & Transaction Manager
Ensures atomic database operations, foreign keys, and query parameterization.
"""

import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from config import DB_PATH

class BaseRepository:

    @staticmethod
    def get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    @classmethod
    @contextmanager
    def transaction(cls):
        """Context manager for atomic multi-statement database transactions with rollback."""
        conn = cls.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @classmethod
    def fetch_one(cls, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    @classmethod
    def fetch_all(cls, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    @classmethod
    def execute(cls, query: str, params: tuple = ()) -> int:
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return cur.rowcount

    @classmethod
    def insert(cls, query: str, params: tuple = ()) -> int:
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return cur.lastrowid
