import sqlite3
import json
import threading
from datetime import datetime, timezone

# --- SQLITE PRAGMAS ---
def optimize_sqlite_conn(conn):
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-64000;")  # 64MB cache
    conn.execute("PRAGMA mmap_size=30000000000;")  # memory-mapped I/O
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn

class AliiSQLiteMemory:
    def __init__(self, db_path=None):
        if db_path is None:
            from config import DB_PATH
            db_path = str(DB_PATH)
        self.db_path = db_path
        self._conn = None
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = optimize_sqlite_conn(
                sqlite3.connect(self.db_path, check_same_thread=False)
            )
        return self._conn

    def _reset_conn(self):
        """Close and discard a broken connection so the next call rebuilds it."""
        try:
            if self._conn is not None:
                self._conn.close()
        except sqlite3.Error:
            pass
        self._conn = None

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS system_state (key TEXT PRIMARY KEY, value TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, content TEXT, metadata TEXT, timestamp TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS upgrades (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, version TEXT, data TEXT, checksum TEXT, timestamp TEXT)")
            # Indexes for faster category lookups and range queries
            c.execute("CREATE INDEX IF NOT EXISTS idx_memories_category  ON memories (category)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories (timestamp)")
            conn.commit()

    def add_memory(self, category, content, metadata=None):
        with self._lock:
            try:
                conn = self._get_conn()
                c = conn.cursor()
                c.execute(
                    "INSERT INTO memories (category, content, metadata, timestamp) VALUES (?, ?, ?, ?)",
                    (category, json.dumps(content), json.dumps(metadata or {}), datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
            except sqlite3.OperationalError:
                self._reset_conn()
                raise

    def search_memory(self, query):
        with self._lock:
            try:
                conn = self._get_conn()
                c = conn.cursor()
                c.execute(
                    "SELECT category, content, metadata, timestamp FROM memories WHERE content LIKE ?",
                    ("%" + query + "%",),
                )
                return c.fetchall()
            except sqlite3.OperationalError:
                self._reset_conn()
                raise

    def get_memory_count(self):
        with self._lock:
            try:
                conn = self._get_conn()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM memories")
                return c.fetchone()[0]
            except sqlite3.OperationalError:
                self._reset_conn()
                raise
