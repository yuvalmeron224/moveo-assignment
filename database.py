"""
database.py — DB layer.
Production: Supabase (Postgres) via DATABASE_URL env var.
Development: SQLite fallback (no DATABASE_URL set).
"""
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL    = os.environ.get("DATABASE_URL")
DB_PATH         = Path(__file__).parent / "data" / "inventory.db"
SQL_PATH        = Path(__file__).parent / "data" / "inventory.sql"
POLICY_MIN_YEAR = 2022


def is_postgres() -> bool:
    return DATABASE_URL is not None


def get_connection():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        from urllib.parse import urlparse
        p = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            host=p.hostname,
            port=p.port or 5432,
            dbname=p.path.lstrip("/"),
            user=p.username,
            password=p.password,
            connect_timeout=10,
        )
        conn.autocommit = False
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


def execute_query(query: str, params: list = None) -> list[dict]:
    params = params or []
    conn   = get_connection()
    try:
        if is_postgres():
            import psycopg2.extras
            cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
        else:
            rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        return rows
    finally:
        conn.close()


def execute_write(query: str, params: list = None) -> int:
    params = params or []
    conn   = get_connection()
    try:
        if is_postgres():
            cur   = conn.cursor()
            cur.execute(query, params)
            count = cur.rowcount
            conn.commit()
            cur.close()
        else:
            cur   = conn.execute(query, params)
            conn.commit()
            count = cur.rowcount
        return count
    finally:
        conn.close()


def _pg_placeholder(query: str) -> str:
    """ממיר ? ל-%s לpsycopg2."""
    return query.replace('?', '%s')


def query(sql: str, params: list = None) -> list[dict]:
    """Universal query — מטפל בהבדל ב-placeholders אוטומטית."""
    if is_postgres():
        sql = _pg_placeholder(sql)
    return execute_query(sql, params)


def write(sql: str, params: list = None) -> int:
    """Universal write."""
    if is_postgres():
        sql = _pg_placeholder(sql)
    return execute_write(sql, params)


def run_migration():
    if not is_postgres() and DB_PATH.exists():
        print("✓ SQLite DB קיים")
        return

    print(f"מריץ migration ({'Postgres' if is_postgres() else 'SQLite'})...")
    sql_text = Path(SQL_PATH).read_text()

    if is_postgres():
        sql_text = sql_text.replace(
            "INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY"
        ).replace(
            "CREATE TABLE IF NOT EXISTS", "CREATE TABLE IF NOT EXISTS"
        )

    conn = get_connection()
    try:
        if is_postgres():
            import psycopg2
            cur        = conn.cursor()
            statements = [s.strip() for s in sql_text.split(';') if s.strip()]
            for stmt in statements:
                try:
                    cur.execute(stmt)
                    conn.commit()
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
                except Exception as e:
                    conn.rollback()
                    if 'already exists' not in str(e):
                        print(f"  Warning: {e}")
            cur.close()
        else:
            conn.executescript(sql_text)
    finally:
        conn.close()

    print("✓ Migration הושלם")


def verify_db():
    total    = query("SELECT COUNT(*) as n FROM vehicles")[0]["n"]
    pending  = query("SELECT COUNT(*) as n FROM vehicles WHERE year < ?", [POLICY_MIN_YEAR])[0]["n"]
    no_stock = query("SELECT COUNT(*) as n FROM vehicles WHERE stock_count = 0")[0]["n"]

    print(f"  סה״כ        : {total}")
    print(f"  Pending     : {pending}")
    print(f"  Out-of-stock: {no_stock}")
    assert total   == 100, f"צפוי 100, קיבלנו {total}"
    assert pending == 15,  f"צפוי 15, קיבלנו {pending}"
    assert no_stock == 3,  f"צפוי 3, קיבלנו {no_stock}"
    print("  ✓ הכל תקין")


if __name__ == "__main__":
    run_migration()
    verify_db()
