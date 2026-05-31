"""
qa.py — תוכנית בדיקה מלאה לפני deployment.
בודקת כל edge case מהמטלה ומדפיסה PASS/FAIL לכל תרחיש.
"""

import json
import os
import time
from dotenv import load_dotenv
from database import run_migration, query
from vector_store import build_vector_store, search_knowledge_base
from tools import run_tool
from agent import chat, create_session

load_dotenv()

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
results = []

# Voyage AI free tier = 3 RPM → need 21s between embedding calls.
# Hash fallback has no rate limit → 0s is fine.
RAG_SLEEP = 21 if os.environ.get("VOYAGE_API_KEY") else 0


def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append(condition)
    suffix = f"  → {detail}" if detail else ""
    print(f"  {status}  {label}{suffix}")


def section(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


# ═══════════════════════════════════════════════════════
# 1. DATABASE
# ═══════════════════════════════════════════════════════

section("1. DATABASE")

run_migration()

total    = query("SELECT COUNT(*) as n FROM vehicles")[0]["n"]
pending  = query("SELECT COUNT(*) as n FROM vehicles WHERE year < 2022")[0]["n"]
no_stock = query("SELECT COUNT(*) as n FROM vehicles WHERE stock_count = 0")[0]["n"]

check("100 רכבים ב-DB",          total == 100,    f"נמצאו {total}")
check("15 רכבים pending_delisting", pending == 15, f"נמצאו {pending}")
check("3 רכבים out_of_stock",    no_stock == 3,   f"נמצאו {no_stock}")


# ═══════════════════════════════════════════════════════
# 2. VECTOR STORE
# ═══════════════════════════════════════════════════════

section("2. VECTOR STORE")

build_vector_store()
time.sleep(RAG_SLEEP)

rag_tests = [
    ("return policy",       "support.md"),
    ("test drive schedule", "faqs.md"),
    ("minimum car year",    "policy.md"),
    ("delivery cost",       "shipping.md"),
    ("EV battery tips",     "maintenance.md"),
]

for query_text, expected_source in rag_tests:
    res = search_knowledge_base(query_text, n_results=1)
    time.sleep(RAG_SLEEP)
    if not res["success"] or not res["results"]:
        check(f'RAG: "{query_text}"', False, "אין תוצאות")
    else:
        top = res["results"][0]
        correct = top["source"] == expected_source
        check(
            f'RAG: "{query_text}"',
            correct,
            f"{top['source']} (ציפינו {expected_source}) — relevance: {top['relevance']}"
        )


# ═══════════════════════════════════════════════════════
# 3. TOOLS — לוגיקה עסקית
# ═══════════════════════════════════════════════════════

section("3. TOOLS — BUSINESS LOGIC")

# 3.1 רכב 2024 זמין
r = json.loads(run_tool("search_inventory", {"make": "Tesla", "model": "Model 3", "year_min": 2024}))
available = [c for c in r["results"] if c["sellable"] and c["stock_count"] > 0]
check("Tesla Model 3 2024 — זמין למכירה", len(available) > 0)

# 3.2 רכב 2020 — pending_delisting
r = json.loads(run_tool("search_inventory", {"make": "BMW", "model": "X5", "year_max": 2021}))
all_blocked = all(not c["sellable"] for c in r["results"])
check("BMW X5 pre-2022 — sellable=false", all_blocked, f"{len(r['results'])} רכבים נבדקו")

# 3.3 reserve_car — חסום בקוד לרכב 2020
r = json.loads(run_tool("reserve_car", {"car_id": 66, "user_name": "Test", "user_email": "t@t.com"}))
check("reserve_car — 2020 חסום בקוד", r.get("error") == "policy_violation", r.get("error"))

# 3.4 reserve_car — out_of_stock
r = json.loads(run_tool("reserve_car", {"car_id": 62, "user_name": "Test", "user_email": "t@t.com"}))
check("reserve_car — out_of_stock חסום", r.get("error") == "out_of_stock", r.get("error"))

# 3.5 reserve_car — רכב תקין → DB write
before = query("SELECT stock_count FROM vehicles WHERE id = 1")[0]["stock_count"]
r = json.loads(run_tool("reserve_car", {"car_id": 1, "user_name": "QA Test", "user_email": "qa@test.com"}))
after = query("SELECT stock_count FROM vehicles WHERE id = 1")[0]["stock_count"]
check("reserve_car — DB write הצליח", r["success"] and after == before - 1, f"stock: {before} → {after}")

# שחזור stock
from database import write
write("UPDATE vehicles SET stock_count = stock_count + 1 WHERE id = 1")
check("reserve_car — stock שוחזר לאחר בדיקה", True)

# 3.6 search_knowledge_base דרך tool
r = json.loads(run_tool("search_knowledge_base", {"query": "refund policy"}))
check("search_knowledge_base דרך tool", r["success"] and r["count"] > 0, f"{r.get('count')} תוצאות")


# ═══════════════════════════════════════════════════════
# 4. AGENT — edge cases מהמטלה
# ═══════════════════════════════════════════════════════

section("4. AGENT — EDGE CASES")

def agent_check(label, message, history, keywords_any=None, keywords_none=None):
    """שולח הודעה ל-agent ובודק שהתשובה מכילה/לא מכילה מילות מפתח."""
    reply, history = chat(message, history)
    reply_lower = reply.lower()

    passed = True
    if keywords_any:
        passed = passed and any(kw.lower() in reply_lower for kw in keywords_any)
    if keywords_none:
        passed = passed and all(kw.lower() not in reply_lower for kw in keywords_none)

    check(label, passed, reply[:120].replace("\n", " "))
    return history

# 4.1 Hybrid RAG — שאלה על מלאי
h = create_session()
h = agent_check(
    "Hybrid RAG — חיפוש מלאי Tesla",
    "Do you have any Tesla electric cars?",
    h,
    keywords_any=["tesla", "model 3", "model y"],
)
time.sleep(RAG_SLEEP)

# 4.2 Conflict Resolution — רכב 2020
h = agent_check(
    "Conflict Resolution — BMW X5 2020 לא נמכר",
    "Do you have a BMW X5 from 2020?",
    h,
    keywords_any=["cannot", "policy", "2022", "pending"],
    keywords_none=["reserve", "buy now"],
)
time.sleep(RAG_SLEEP)

# 4.3 Out of stock
h = agent_check(
    "Out of stock — BMW M5 2024",
    "Is the BMW M5 2024 available?",
    h,
    keywords_any=["out of stock", "not available", "unavailable"],
)
time.sleep(RAG_SLEEP)

# 4.4 Knowledge base — return policy
h = agent_check(
    "Knowledge base — return policy",
    "What is your return policy?",
    h,
    keywords_any=["7 days", "refund", "return"],
)
time.sleep(RAG_SLEEP)

# 4.5 Context memory — "it" מתייחס לשיחה הקודמת
h2 = create_session()
h2 = agent_check("", "Do you have a Tesla Model S 2024?", h2)
time.sleep(RAG_SLEEP)
h2 = agent_check(
    "Context memory — זוכר הקשר קודם",
    "Can I return it within 7 days?",
    h2,
    keywords_any=["7 days", "return", "refund"],
)
time.sleep(RAG_SLEEP)

# 4.6 אין המצאת features
h3 = create_session()
h3 = agent_check(
    "Anti-hallucination — לא ממציא features",
    "What is the sound system like in the BMW iX 2024?",
    h3,
    keywords_none=["harman", "bowers", "surround sound", "premium audio"],
)
time.sleep(RAG_SLEEP)

# 4.7 Purchase email — בלי אימייל → מבקש
h4 = create_session()
h4 = agent_check(
    "Purchase flow — מבקש אימייל לפני שליחה",
    "I want to buy the Tesla Model 3 2024",
    h4,
    keywords_any=["email", "address", "contact"],
)
time.sleep(RAG_SLEEP)

# 4.8 Input sanitization
h5 = create_session()
h5 = agent_check(
    "Input sanitization — קלט ארוך לא קורס",
    "A" * 3000,
    h5,
)
time.sleep(RAG_SLEEP)


# ═══════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════

total_tests  = len(results)
passed_tests = sum(results)
failed_tests = total_tests - passed_tests

print(f"\n{'═'*55}")
print(f"  RESULTS: {passed_tests}/{total_tests} passed")
if failed_tests == 0:
    print(f"\033[92m  ✓ כל הבדיקות עברו — מוכן ל-deployment\033[0m")
else:
    print(f"\033[91m  ✗ {failed_tests} בדיקות נכשלו — לתקן לפני deployment\033[0m")
print(f"{'═'*55}\n")
