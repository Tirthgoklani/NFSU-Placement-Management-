import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from config import DB_PATH, BASE_DIR, BACKUP_DIR

def get_db():
    """Return a connection to the SQLite database with row factory and foreign keys enabled."""
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    """Execute schema.sql to initialize or ensure schema tables exist."""
    schema_path = BASE_DIR / "models" / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    with get_db() as conn:
        conn.executescript(schema_sql)
        conn.commit()

def query_db(query, args=(), one=False):
    """Safe parameterized query execution returning dict-like Row objects."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(query, args)
        rv = cur.fetchall()
        return (rv[0] if rv else None) if one else rv
    finally:
        conn.close()

def execute_db(query, args=()):
    """Execute a parameterized DML query (UPDATE, DELETE)."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(query, args)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()

def execute_insert(query, args=()):
    """Execute a parameterized INSERT query and return last inserted row id."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(query, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def backup_database():
    """Creates a timestamped snapshot backup of the current database file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"nfsu_placement_backup_{timestamp}.db"
    
    # Use SQLite's online backup API for safe, concurrent-safe backup
    source_conn = get_db()
    dest_conn = sqlite3.connect(str(backup_file))
    try:
        source_conn.backup(dest_conn)
    finally:
        source_conn.close()
        dest_conn.close()
        
    return str(backup_file)

def restore_database(backup_path):
    """Restores database from a verified backup file."""
    if not Path(backup_path).exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
    source_conn = sqlite3.connect(str(backup_path))
    dest_conn = get_db()
    try:
        source_conn.backup(dest_conn)
    finally:
        source_conn.close()
        dest_conn.close()
    return True
