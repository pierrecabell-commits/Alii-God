import sqlite3
n
# --- PERPLEXITY AUTO-OPTIMIZATION: SQLITE PRAGMAS ---
def optimize_sqlite_conn(conn):
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-64000;") # 64MB cache
    conn.execute("PRAGMA mmap_size=30000000000;") # Use memory mapped I/O
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn
# ----------------------------------------------------
import json
from datetime import datetime

class AliiSQLiteMemory:
    def __init__(self, db_path="/home/avalii/moltbot/memory/alii_core.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = optimize_sqlite_conn(sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS system_state (key TEXT PRIMARY KEY, value TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, content TEXT, metadata TEXT, timestamp TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS upgrades (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, version TEXT, data TEXT, checksum TEXT, timestamp TEXT)')
        conn.commit()
        conn.close()

    def add_memory(self, category, content, metadata=None):
        conn = optimize_sqlite_conn(sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT INTO memories (category, content, metadata, timestamp) VALUES (?, ?, ?, ?)',
                  (category, json.dumps(content), json.dumps(metadata or {}), datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def search_memory(self, query):
        conn = optimize_sqlite_conn(sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT category, content, metadata, timestamp FROM memories WHERE content LIKE ?', ('%' + query + '%',))
        rows = c.fetchall()
        conn.close()
        return rows

    def get_memory_count(self):
        conn = optimize_sqlite_conn(sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM memories')
        count = c.fetchone()[0]
        conn.close()
        return count