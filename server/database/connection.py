import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_path() -> str:
    return os.getenv("DATABASE_PATH", "./dcpi.db")


def get_db() -> sqlite3.Connection:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA cache_size=-64000")     # 64MB page cache for bulk ops
    conn.execute("PRAGMA mmap_size=268435456")   # 256MB memory-mapped I/O
    conn.execute("PRAGMA temp_store=MEMORY")     # Temp tables in memory
    return conn