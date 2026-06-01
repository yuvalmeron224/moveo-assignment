"""
database.py — Postgres (Supabase) DB layer.
Requires DATABASE_URL environment variable.
"""
import os
import psycopg2
import psycopg2.extras
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL    = os.environ["DATABASE_URL"]
SQL_PATH        = Path(__file__).parent / "data" / "inventory.sql"
POLICY_MIN_YEAR = 2022


def get_connection():
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


def execute_query(sql: str, params: list = None) -> list[dict]:
    params = params or []
    conn   = get_connection()
    try:
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql.replace('?', '%s'), params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows
    finally:
        conn.close()


def execute_write(sql: str, params: list = None) -> int:
    params = params or []
    conn   = get_connection()
    try:
        cur   = conn.cursor()
        cur.execute(sql.replace('?', '%s'), params)
        count = cur.rowcount
        conn.commit()
        cur.close()
        return count
    finally:
        conn.close()


def query(sql: str, params: list = None) -> list[dict]:
    return execute_query(sql, params)


def write(sql: str, params: list = None) -> int:
    return execute_write(sql, params)


def ensure_reservations_table():
    write("""
        CREATE TABLE IF NOT EXISTS reservations (
            id          SERIAL PRIMARY KEY,
            car_id      INTEGER   NOT NULL,
            user_name   TEXT      NOT NULL,
            user_email  TEXT      NOT NULL,
            reserved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at  TIMESTAMP NOT NULL
        )
    """)


def run_migration():
    print("Running Postgres migration...")
    sql_text = SQL_PATH.read_text().replace(
        "INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY"
    )
    conn = get_connection()
    try:
        cur = conn.cursor()
        for stmt in [s.strip() for s in sql_text.split(';') if s.strip()]:
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
    finally:
        conn.close()
    print("✓ Migration complete")


def verify_db():
    total    = query("SELECT COUNT(*) as n FROM vehicles")[0]["n"]
    pending  = query("SELECT COUNT(*) as n FROM vehicles WHERE year < %s", [POLICY_MIN_YEAR])[0]["n"]
    no_stock = query("SELECT COUNT(*) as n FROM vehicles WHERE stock_count = 0")[0]["n"]
    print(f"  Total       : {total}")
    print(f"  Pending     : {pending}")
    print(f"  Out-of-stock: {no_stock}")


if __name__ == "__main__":
    run_migration()
    verify_db()
