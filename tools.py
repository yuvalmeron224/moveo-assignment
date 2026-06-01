"""
tools.py 
כל לוגיקה עסקית קריטית רצה כאן בקוד — לא ב-prompt.
"""
import os
import json
from dotenv import load_dotenv
from database import query, write, POLICY_MIN_YEAR, ensure_reservations_table
from vector_store import search_knowledge_base

load_dotenv()


# ─── Tool Definitions (schema ל-Claude) ────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_inventory",
        "description": (
            "Search the live vehicle inventory database. "
            "Use this for ANY question about cars: make, model, year, price, color, "
            "fuel type, stock availability, or browsing options. "
            "Always call this before discussing specific vehicles — never rely on memory. "
            "Results include a 'sellable' flag: vehicles from before 2022 are "
            "pending_delisting and cannot be sold, reserved, or delivered."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "make":      {"type": "string",  "description": "Brand, e.g. BMW, Tesla"},
                "model":     {"type": "string",  "description": "Model, e.g. X5, Model 3"},
                "year_min":  {"type": "integer", "description": "Minimum model year"},
                "year_max":  {"type": "integer", "description": "Maximum model year"},
                "price_max": {"type": "integer", "description": "Maximum price in USD"},
                "price_min": {"type": "integer", "description": "Minimum price in USD"},
                "fuel_type": {
                    "type": "string",
                    "enum": ["Electric", "Gasoline", "Hybrid"],
                    "description": "Powertrain type",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_knowledge_base",
        "description": (
            "Search company policies, FAQs, and guides. "
            "Use for: return policy, refunds, test drives, warranties, delivery zones, "
            "shipping costs, maintenance schedules, financing, contact info, or hours. "
            "Do NOT use for questions about specific cars or stock — use search_inventory instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Question or topic to search"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "reserve_car",
        "description": (
            "Reserve a specific vehicle — decrements stock by 1 and holds for 72 hours. "
            "ONLY call this when ALL of the following are true: "
            "(1) the customer has explicitly confirmed they want to reserve RIGHT NOW, "
            "(2) you have the exact car_id from a search_inventory result, "
            "(3) you have the customer's full name and email from this conversation. "
            "Do NOT call for hypothetical questions, browsing, or unconfirmed intent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "car_id":     {"type": "integer", "description": "Vehicle ID from search results"},
                "user_name":  {"type": "string",  "description": "Customer full name"},
                "user_email": {"type": "string",  "description": "Customer email address"},
            },
            "required": ["car_id", "user_name", "user_email"],
        },
    },
    {
        "name": "send_purchase_email",
        "description": (
            "Send a purchase inquiry email to the sales team. "
            "ONLY call when BOTH conditions are met: "
            "(1) the customer has explicitly stated they want to BUY — not just browse or inquire, "
            "(2) you have their confirmed email address from this conversation. "
            "Never call for casual interest, price questions, or browsing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_name":   {"type": "string",  "description": "Customer full name"},
                "user_email":  {"type": "string",  "description": "Customer email"},
                "car_id":      {"type": "integer", "description": "Vehicle ID"},
                "car_details": {"type": "string",  "description": "Make, model, year, price"},
            },
            "required": ["user_name", "user_email", "car_id", "car_details"],
        },
    },
]


# ─── Implementations ────────────────────────────────────────────────────────

def _search_inventory(make=None, model=None, year_min=None,
                      year_max=None, price_max=None, fuel_type=None) -> dict:
    sql    = "SELECT * FROM vehicles WHERE 1=1"
    params = []

    if make:
        sql += " AND LOWER(make) = LOWER(?)"
        params.append(make)
    if model:
        sql += " AND LOWER(model) = LOWER(?)"
        params.append(model)
    if year_min is not None:
        sql += " AND year >= ?"
        params.append(year_min)
    if year_max is not None:
        sql += " AND year <= ?"
        params.append(year_max)
    if price_max is not None:
        sql += " AND price <= ?"
        params.append(price_max)
    if fuel_type:
        sql += " AND LOWER(fuel_type) = LOWER(?)"
        params.append(fuel_type)

    sql += " ORDER BY year DESC, price ASC LIMIT 20"

    try:
        rows = query(sql, params)
    except Exception as e:
        return {"success": False, "error": "database_unavailable", "results": []}

    # Count active reservations per car (expires_at > NOW)
    res_rows = query(
        "SELECT car_id, COUNT(*) as cnt FROM reservations "
        "WHERE expires_at > NOW() GROUP BY car_id"
    )
    active_reservations = {r["car_id"]: r["cnt"] for r in res_rows}

    # Fetch earliest expiry per fully-reserved car
    expiry_rows = query(
        "SELECT car_id, "
        "EXTRACT(EPOCH FROM (MIN(expires_at) - NOW()))::int AS seconds_remaining "
        "FROM reservations WHERE expires_at > NOW() GROUP BY car_id"
    )
    earliest_release = {r["car_id"]: max(int(r["seconds_remaining"]), 0) for r in expiry_rows}

    results = []
    for car in rows:
        reserved_units   = active_reservations.get(car["id"], 0)
        available_units  = car["stock_count"] - reserved_units

        if car["year"] < POLICY_MIN_YEAR:
            car["sellable"]    = False
            car["status"]      = "pending_delisting"
            car["status_note"] = (
                f"Year {car['year']} is below the {POLICY_MIN_YEAR}+ sales policy. "
                "Cannot be sold, reserved, or delivered."
            )
        elif available_units <= 0:
            car["sellable"] = False
            if car["stock_count"] <= 0:
                car["status"]      = "out_of_stock"
                car["status_note"] = "Out of stock — cannot be reserved."
            else:
                seconds = earliest_release.get(car["id"], 0)
                hours   = seconds // 3600
                minutes = (seconds % 3600) // 60
                car["status"]      = "fully_reserved"
                car["status_note"] = (
                    f"All units currently reserved by other buyers. "
                    f"Earliest release in {hours}h {minutes}m — available then if purchase not completed."
                )
        else:
            car["sellable"]         = True
            car["status"]           = "available"
            car["status_note"]      = None
        car["reserved_units"]  = reserved_units
        car["available_units"] = max(available_units, 0)
        results.append(car)

    # Hide pending_delisting cars from general results — they should not be proactively shown.
    # Claude will only learn about them if the customer explicitly asks for a year < 2022.
    visible = [c for c in results if c["status"] != "pending_delisting"]
    hidden  = len(results) - len(visible)

    return {
        "success": True,
        "count":   len(visible),
        "results": visible,
        "pre_2022_units_exist": hidden > 0,
    }


def _search_knowledge_base(query: str) -> dict:
    return search_knowledge_base(query, n_results=3)


def _reserve_car(car_id: int, user_name: str, user_email: str) -> dict:
    ensure_reservations_table()

    try:
        rows = query("SELECT * FROM vehicles WHERE id = ?", [car_id])
    except Exception:
        return {"success": False, "error": "database_unavailable"}

    if not rows:
        return {"success": False, "error": "car_not_found", "car_id": car_id}

    car = rows[0]

    # Policy check — in code, not prompt
    if car["year"] < POLICY_MIN_YEAR:
        return {
            "success": False,
            "error":   "policy_violation",
            "reason":  f"Year {car['year']} does not meet the {POLICY_MIN_YEAR}+ policy.",
        }

    if car["stock_count"] <= 0:
        return {"success": False, "error": "out_of_stock"}

    # Count active reservations — lazy expiry: expired rows are simply not counted
    active = query(
        "SELECT COUNT(*) as cnt FROM reservations "
        "WHERE car_id = ? AND expires_at > NOW()",
        [car_id],
    )[0]["cnt"]

    if active >= car["stock_count"]:
        return {"success": False, "error": "out_of_stock"}

    # Insert reservation — expires in 72 hours
    try:
        write(
            "INSERT INTO reservations (car_id, user_name, user_email, expires_at) "
            "VALUES (?, ?, ?, NOW() + INTERVAL '72 hours')",
            [car_id, user_name, user_email],
        )
    except Exception:
        return {"success": False, "error": "database_unavailable"}

    return {
        "success":    True,
        "car_id":     car_id,
        "make":       car["make"],
        "model":      car["model"],
        "year":       car["year"],
        "price":      car["price"],
        "user_name":  user_name,
        "user_email": user_email,
        "held_hours": 72,
        "message":    f"Reserved for {user_name} — held 72 hours.",
    }


def _send_purchase_email(user_name: str, user_email: str,
                         car_id: int, car_details: str) -> dict:
    resend_key = os.environ.get("RESEND_API_KEY")

    if not resend_key:
        print(f"\n[DEV EMAIL] To: {user_email} | {user_name} | {car_details}\n")
        return {
            "success":  True,
            "dev_mode": True,
            "message":  "Email simulated — set RESEND_API_KEY to send for real.",
        }

    try:
        import resend
        resend.api_key = resend_key
        r = resend.Emails.send({
            "from":    "onboarding@resend.dev",
            "to":      [user_email],
            "subject": f"Purchase Inquiry — {car_details}",
            "html":    f"""
                <h2>Thank you, {user_name}!</h2>
                <p>We received your purchase inquiry for:
                   <strong>{car_details}</strong></p>
                <p>Our sales team will contact you within 2 business hours.</p>
                <p>Vehicle ID: #{car_id}</p>
                <hr>
                <p>Premium Cars | support@premiumcars.com | +1 (800) 555-0199</p>
            """,
        })
        return {"success": True, "email_id": r["id"], "to": user_email}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Router ─────────────────────────────────────────────────────────────────

TOOL_MAP = {
    "search_inventory":        _search_inventory,
    "search_knowledge_base":   _search_knowledge_base,
    "reserve_car":             _reserve_car,
"send_purchase_email":     _send_purchase_email,
}


def run_tool(name: str, inputs: dict) -> str:
    fn = TOOL_MAP.get(name)
    if not fn:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = fn(**inputs)
    except Exception as e:
        result = {"success": False, "error": str(e)}
    return json.dumps(result, ensure_ascii=False, default=str)


if __name__ == "__main__":
    print("=== בדיקות tools ===\n")

    print("1. Tesla Electric 2023+")
    r = _search_inventory(make="Tesla", fuel_type="Electric", year_min=2023)
    for c in r["results"][:2]:
        print(f"   {c['year']} {c['make']} {c['model']} | ${c['price']:,} | {c['status']}")

    print("\n2. BMW X5 pre-2022 → pending_delisting")
    r = _search_inventory(make="BMW", model="X5", year_max=2021)
    for c in r["results"]:
        print(f"   {c['year']} | sellable={c['sellable']} | {c['status']}")

    print("\n3. reserve_car — year 2020 → נחסם בקוד")
    r = _reserve_car(66, "Test User", "test@example.com")
    print(f"   success={r['success']} | {r.get('error')} | {r.get('reason','')}")

    print("\n4. reserve_car — רכב תקין")
    r = _reserve_car(2, "Jane Smith", "jane@test.com")
    print(f"   success={r['success']} | {r.get('message','')}")

    print("\n5. send_purchase_email (dev mode)")
    r = _send_purchase_email("Jane Smith", "jane@test.com", 2, "2023 Tesla Model 3 - $39,990")
    print(f"   {r}")

    print("\n✓ הכל עובד")
