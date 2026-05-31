"""
analytics.py — Router confidence tracking.
Every classification is logged to the DB so you can see in real-time
how confident the router is and catch systematic misclassifications.
"""

import logging
from datetime import datetime
from database import query, write

logger = logging.getLogger(__name__)

# ─── Schema ──────────────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS router_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT    NOT NULL,
    message_preview TEXT    NOT NULL,
    intent          TEXT    NOT NULL,
    confidence      TEXT    NOT NULL,
    overridden      INTEGER NOT NULL DEFAULT 0,
    needs_clarify   INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_TABLE_PG = """
CREATE TABLE IF NOT EXISTS router_log (
    id              SERIAL PRIMARY KEY,
    ts              TEXT    NOT NULL,
    message_preview TEXT    NOT NULL,
    intent          TEXT    NOT NULL,
    confidence      TEXT    NOT NULL,
    overridden      INTEGER NOT NULL DEFAULT 0,
    needs_clarify   INTEGER NOT NULL DEFAULT 0
)
"""


def ensure_table():
    """Create router_log table if it doesn't exist yet."""
    from database import is_postgres, get_connection
    conn = get_connection()
    try:
        if is_postgres():
            cur = conn.cursor()
            cur.execute(_CREATE_TABLE_PG)
            conn.commit()
            cur.close()
        else:
            conn.executescript(_CREATE_TABLE)
    except Exception as e:
        logger.warning(f"analytics.ensure_table failed: {e}")
    finally:
        conn.close()


# ─── Write ───────────────────────────────────────────────────────────────────

def log_classification(
    message: str,
    intent: str,
    confidence: str,
    overridden: bool = False,
    needs_clarify: bool = False,
) -> None:
    """Persist one router decision. Never raises — logging must not crash the app."""
    try:
        write(
            """INSERT INTO router_log
               (ts, message_preview, intent, confidence, overridden, needs_clarify)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                datetime.utcnow().isoformat(timespec="seconds"),
                message[:120],
                intent,
                confidence,
                int(overridden),
                int(needs_clarify),
            ],
        )
    except Exception as e:
        logger.warning(f"analytics.log_classification failed: {e}")


# ─── Read ────────────────────────────────────────────────────────────────────

def get_confidence_stats() -> dict:
    """
    Returns:
        {
            "total": int,
            "by_confidence": {"high": int, "medium": int, "low": int},
            "by_intent":     {"search_inventory": int, ...},
            "overrides":     int,   # times keywords overrode LLM
            "clarifications": int,  # times we asked user to clarify
        }
    """
    try:
        rows = query("SELECT confidence, intent, overridden, needs_clarify FROM router_log")
    except Exception:
        return {}

    if not rows:
        return {"total": 0, "by_confidence": {}, "by_intent": {}, "overrides": 0, "clarifications": 0}

    by_conf   = {"high": 0, "medium": 0, "low": 0}
    by_intent = {}
    overrides = 0
    clarifs   = 0

    for r in rows:
        conf = r["confidence"]
        if conf in by_conf:
            by_conf[conf] += 1

        intent = r["intent"]
        by_intent[intent] = by_intent.get(intent, 0) + 1

        if r["overridden"]:
            overrides += 1
        if r["needs_clarify"]:
            clarifs += 1

    return {
        "total":          len(rows),
        "by_confidence":  by_conf,
        "by_intent":      by_intent,
        "overrides":      overrides,
        "clarifications": clarifs,
    }


def get_recent_low_confidence(limit: int = 10) -> list[dict]:
    """Return the most recent low-confidence classifications for manual review."""
    try:
        return query(
            """SELECT ts, message_preview, intent, overridden, needs_clarify
               FROM router_log
               WHERE confidence = 'low'
               ORDER BY id DESC
               LIMIT ?""",
            [limit],
        )
    except Exception:
        return []
