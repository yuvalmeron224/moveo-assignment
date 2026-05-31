"""
router.py — Two-stage intent classifier.

Stage 1: LLM (Claude Haiku) — semantic understanding, handles synonyms and paraphrasing.
Stage 2: Keyword overrides — safety net for reserve/purchase; fallback if LLM fails.

WE decide which tool runs — Claude (in agent.py) only formats the response.
"""

import os
import re
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Car brands & models known to our inventory ──────────────────────────────

CAR_BRANDS = [
    "tesla", "bmw", "mercedes", "porsche", "audi", "lexus", "volvo",
    "rivian", "polestar", "genesis", "bentley", "ferrari", "lamborghini",
    "rolls-royce", "maserati", "aston martin", "mclaren", "lucid",
    "cadillac", "range rover",
]

CAR_MODELS = [
    "model 3", "model y", "model s", "model x", "cybertruck",
    "ix", "i4", "x5", "m3", "m5", "530e",
    "eqs", "eqb", "gle", "c300", "glc",
    "taycan", "cayenne", "macan", "panamera", "911",
    "e-tron", "q7", "q8", "a6", "a7",
    "rx 450h", "lx 600", "rz 450e", "es 300h",
    "xc40", "xc60", "xc90", "ex90",
    "r1t", "r1s", "gv60", "gv70", "gv80",
    "urus", "artura", "spectre", "granturismo",
]

# ─── Keyword lists (fallback + safety override) ───────────────────────────────

INVENTORY_KEYWORDS = [
    "car", "vehicle", "available", "availability", "price", "cost",
    "stock", "inventory", "buy", "show me", "do you have", "looking for",
    "electric", "hybrid", "gasoline", "mileage", "color", "year",
    "newer", "older", "cheapest", "expensive", "under", "below",
]

KB_KEYWORDS = [
    "policy", "return", "refund", "cancel", "cancellation",
    "warranty", "guarantee", "shipping", "ship",
    "test drive", "test-drive", "testdrive", "appointment",
    "maintenance", "oil change",
    "contact", "support", "phone", "hours",
    "financing", "finance", "loan", "trade-in", "trade in",
    "zone", "distance", "how much does delivery", "delivery cost",
    "how do i schedule", "how do i book",
]

# Explicit phrases — LLM might miss exact user phrasings, keywords catch them.
RESERVE_KEYWORDS = [
    # English
    "reserve", "reservation",
    "i'd like to reserve", "i want to reserve", "can i reserve",
    "put it on hold", "hold it for me",
    "book this", "book the", "book a car", "booking a car",
    # Hebrew
    "הזמנה", "להזמין", "לשריין", "שריין", "שמור לי", "תשמור לי",
    "אני רוצה להזמין", "אפשר להזמין", "לקבוע",
]

PURCHASE_KEYWORDS = [
    # English
    "i want to buy", "i'd like to buy", "i want to purchase",
    "i'll take it", "i'll buy", "ready to buy", "ready to purchase",
    "proceed with purchase", "complete the purchase", "finalize",
    # Hebrew
    "אני רוצה לקנות", "אני רוצה לרכוש", "לקנות", "לרכוש",
    "אקנה", "ארכוש", "רוצה לסגור עסקה",
]

EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
)

VALID_INTENTS = {
    "search_inventory",
    "search_knowledge_base",
    "reserve_car",
    "purchase_intent",
    "general",
}

# ─── LLM classifier ──────────────────────────────────────────────────────────

_LLM_SYSTEM = """You are an intent classifier for a luxury car dealership chatbot.
Classify the customer message into exactly one intent.

The dealership serves customers in ANY language (English, Hebrew, Arabic, Spanish, etc.).
Translate mentally before classifying — language does not change the intent.
Examples: "הזמנה של רכב" = reserve a car, "quiero comprar" = purchase intent.

Intents:
- search_inventory: customer wants to find, browse, or ask about specific vehicles, prices, availability, make/model/year/color/fuel type
- search_knowledge_base: customer asks about policies, returns, refunds, warranties, delivery, test drives, financing, maintenance, contact info, hours
- reserve_car: customer wants to hold, save, reserve, or book a specific vehicle — any expression of wanting to secure it
- purchase_intent: customer explicitly wants to BUY a vehicle right now (not just browse or inquire)
- general: greeting, thanks, small talk, or anything unrelated to the above

Rules:
- reserve_car wins over search_inventory even if the car isn't named yet ("save that one for me")
- reserve_car ONLY when the customer explicitly and currently wants to hold/book a vehicle NOW.
  Do NOT use reserve_car for:
    • conditional phrasing ("if I want to", "what if", "אם אני רוצה", "האם אפשר")
    • negation ("I don't want to reserve", "אני לא רוצה להזמין")
    • cancellation ("cancel my reservation", "לבטל הזמנה")
    • past actions ("I reserved last week", "הזמנתי בשבוע שעבר")
    • third-party intent ("my friend wants to reserve", "החבר שלי רוצה להזמין")
  For these: use search_inventory (browsing) or search_knowledge_base (process questions).
- purchase_intent ONLY when the customer explicitly wants to BUY right now, not just browse or inquire.
  Same exclusions apply as reserve_car.
- When unsure between inventory and KB, pick inventory if the question needs live stock data

Respond with ONLY valid JSON: {"intent": "<one of the five intents above>"}"""


def _score_confidence(intent: str, msg_lower: str) -> str:
    """
    Deterministic confidence scoring based on message signals.
    The LLM decides WHAT the intent is. The code decides HOW CERTAIN we are.

    high  → clear explicit signal in the message matches the intent
    medium → LLM classified it but no strong keyword signal
    low   → intent is 'general' with no matching signals (truly ambiguous)
    """
    has_brand = _contains(msg_lower, CAR_BRANDS) or _contains(msg_lower, CAR_MODELS)
    has_kb    = _contains(msg_lower, KB_KEYWORDS)
    has_inv   = _contains(msg_lower, INVENTORY_KEYWORDS)
    has_res   = _contains(msg_lower, RESERVE_KEYWORDS)
    has_pur   = _contains(msg_lower, PURCHASE_KEYWORDS)

    if intent == "reserve_car"           and has_res:            return "high"
    if intent == "purchase_intent"       and has_pur:            return "high"
    if intent == "search_inventory"      and (has_brand or has_inv): return "high"
    if intent == "search_knowledge_base" and has_kb:             return "high"
    if intent == "general"               and not (has_brand or has_kb or has_inv or has_res or has_pur):
        return "low"   # nothing matched → truly ambiguous
    return "medium"    # LLM classified but no clear keyword signal


def _llm_classify(message: str, history: list) -> str:
    """
    Call Claude Haiku to semantically classify the user's intent.
    Returns intent only — confidence is scored separately by _score_confidence().
    Raises on failure so caller can fallback.
    """
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Include last 2 turns so the LLM has context for pronouns like "it", "that one"
    recent_lines = []
    for msg in history[-4:]:
        content = msg.get("content", "")
        if isinstance(content, str):
            role = "Customer" if msg["role"] == "user" else "Agent"
            recent_lines.append(f"{role}: {content[:300]}")

    context_block = (
        "Recent conversation:\n" + "\n".join(recent_lines)
        if recent_lines else ""
    )

    user_content = (
        f"{context_block}\n\nClassify this message: \"{message}\""
        if context_block
        else f"Classify this message: \"{message}\""
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=30,
        system=_LLM_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    raw    = response.content[0].text.strip()
    data   = json.loads(raw)
    intent = data["intent"]

    if intent not in VALID_INTENTS:
        raise ValueError(f"LLM returned unknown intent: {intent!r}")

    return intent


# ── Override suppression markers ─────────────────────────────────────────────
# When any of these patterns are present, the keyword safety override is skipped.
# The LLM's classification is trusted instead — it handles these cases correctly.

# 1. Conditional/hypothetical — "אם אני רוצה להזמין" = question, not intent.
CONDITIONAL_MARKERS = [
    "if i", "if you", "what if", "maybe i", "maybe you",
    "could i", "would i", "should i", "can i ask",
    "how do i", "how would i", "how can i",
    "suppose", "hypothetically",
    "אם ", "האם ", "אולי ", "מה אם", "איך אני", "איך אפשר", "האם אפשר",
]

# 2. Negation — "אני לא רוצה להזמין" — contains reserve keyword but refuses.
NEGATION_MARKERS = [
    "don't ", "dont ", "do not ", "not sure", "not ready",
    "won't ", "wont ", "can't ", "cant ", "never ",
    "no need", "no thank", "actually no", "changed my mind",
    "לא ", "אין ", "בלי ", "לא רוצה", "לא מעוניין", "לא בטוח",
]

# 3. Cancellation — "לבטל הזמנה" — contains "reservation" but intent is to cancel.
CANCEL_MARKERS = [
    "cancel", "cancellation", "undo", "remove reservation",
    "delete reservation", "drop reservation",
    "לבטל", "ביטול", "למחוק הזמנה", "לבטל הזמנה",
]

# 4. Third party — "החבר שלי רוצה להזמין" — not the customer's own intent.
THIRD_PARTY_MARKERS = [
    "my friend", "my wife", "my husband", "my partner",
    "my colleague", "my boss", "someone else", "for someone",
    "החבר שלי", "האישה שלי", "הבעל שלי", "השותף שלי",
    "עמית שלי", "מישהו אחר", "בשביל מישהו",
]


def _is_conditional(text: str) -> bool:
    return any(marker in text for marker in CONDITIONAL_MARKERS)

def _is_negated(text: str) -> bool:
    return any(marker in text for marker in NEGATION_MARKERS)

def _is_cancellation(text: str) -> bool:
    return any(marker in text for marker in CANCEL_MARKERS)

def _is_third_party(text: str) -> bool:
    return any(marker in text for marker in THIRD_PARTY_MARKERS)


# ─── Keyword helpers ─────────────────────────────────────────────────────────

def _has_email_in_history(history: list) -> bool:
    for msg in history:
        content = msg.get("content", "")
        if isinstance(content, str) and EMAIL_PATTERN.search(content):
            return True
    return False


def _contains(text: str, keywords: list) -> bool:
    for kw in keywords:
        if len(kw) <= 3:
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, text):
                return True
        else:
            if kw in text:
                return True
    return False


def _keyword_classify(msg_lower: str) -> str:
    """Pure keyword fallback — used when LLM is unavailable."""
    if _contains(msg_lower, RESERVE_KEYWORDS):
        return "reserve_car"
    if _contains(msg_lower, PURCHASE_KEYWORDS):
        return "purchase_intent"

    has_brand = _contains(msg_lower, CAR_BRANDS) or _contains(msg_lower, CAR_MODELS)
    has_kb    = _contains(msg_lower, KB_KEYWORDS)
    has_inv   = _contains(msg_lower, INVENTORY_KEYWORDS)

    if (has_brand or has_inv) and has_kb:
        return "compound"
    if has_brand or has_inv:
        return "search_inventory"
    if has_kb:
        return "search_knowledge_base"
    return "general"


def _build_route(intent: str, has_email: bool) -> dict:
    """Convert intent string → full route dict with tool_choice."""
    if intent == "reserve_car":
        return {
            "intent":      "reserve_car",
            "has_email":   has_email,
            "tool_choice": {"type": "tool", "name": "reserve_car"},
        }
    if intent == "purchase_intent":
        if has_email:
            return {
                "intent":      "purchase_intent",
                "has_email":   True,
                "tool_choice": {"type": "tool", "name": "send_purchase_email"},
            }
        return {
            "intent":      "purchase_intent_no_email",
            "has_email":   False,
            "tool_choice": None,
        }
    if intent == "search_inventory":
        return {
            "intent":      "search_inventory",
            "has_email":   has_email,
            "tool_choice": {"type": "tool", "name": "search_inventory"},
        }
    if intent == "search_knowledge_base":
        return {
            "intent":      "search_knowledge_base",
            "has_email":   has_email,
            "tool_choice": {"type": "tool", "name": "search_knowledge_base"},
        }
    # general or compound → let Claude decide
    return {
        "intent":      intent,
        "has_email":   has_email,
        "tool_choice": {"type": "auto"},
    }


# ─── Main classifier ─────────────────────────────────────────────────────────

def classify(message: str, history: list) -> dict:
    """
    Two-stage intent classification with confidence-based clarification.

    Stage 1 — LLM (semantic): understands synonyms, paraphrasing, and context.
              Returns intent + confidence score.
    Stage 2 — Keyword override: if LLM missed an explicit reserve/purchase
              keyword, keywords win. Also full fallback if LLM is unavailable.

    Low-confidence results set needs_clarification=True so agent.py can
    instruct Claude to ask the user for clarification before acting.

    Returns:
        {
            "intent":               str,
            "has_email":            bool,
            "tool_choice":          dict | None,
            "confidence":           "high" | "medium" | "low",
            "needs_clarification":  bool,
        }
    """
    msg_lower = message.lower().strip()

    has_email = (
        bool(EMAIL_PATTERN.search(message))
        or _has_email_in_history(history)
    )

    # ── Stage 1: LLM semantic classification ────────────────────────────────
    try:
        intent = _llm_classify(message, history)
        logger.info(f"LLM classifier → intent={intent!r}")
    except Exception as e:
        logger.warning(f"LLM classifier failed ({e}) — falling back to keywords")
        intent = _keyword_classify(msg_lower)
        logger.info(f"Keyword fallback → {intent!r}")

    # ── Stage 1b: Post-LLM correction ───────────────────────────────────────
    # The LLM itself can misclassify reserve/purchase in ambiguous contexts.
    # If it returned a high-action intent but the phrasing is clearly not an
    # explicit current action by this customer, demote it so we don't force
    # the wrong tool call on Claude.
    suppress = (
        _is_conditional(msg_lower)
        or _is_negated(msg_lower)
        or _is_cancellation(msg_lower)
        or _is_third_party(msg_lower)
    )
    if suppress and intent in ("reserve_car", "purchase_intent"):
        demoted = "search_knowledge_base" if _is_cancellation(msg_lower) else "search_inventory"
        logger.info(f"Post-LLM correction: {intent!r} → {demoted!r} (ambiguous phrasing)")
        intent = demoted

    # ── Stage 2: Keyword safety override ────────────────────────────────────
    # Override is suppressed for the same ambiguous signals — keyword alone
    # is not a reliable signal when phrasing is conditional, negated, etc.:
    #   conditional  → "אם אני רוצה להזמין" (hypothetical, not intent)
    #   negated      → "אני לא רוצה להזמין" (refusal, not intent)
    #   cancellation → "לבטל הזמנה" (contains "הזמנה" but wants to cancel)
    #   third party  → "החבר שלי רוצה להזמין" (not the customer's own action)
    overridden       = False
    suppress_override = (
        _is_conditional(msg_lower)
        or _is_negated(msg_lower)
        or _is_cancellation(msg_lower)
        or _is_third_party(msg_lower)
    )
    if suppress_override:
        logger.info(f"Keyword override suppressed — ambiguous phrasing detected")

    if intent not in ("reserve_car", "purchase_intent") and not suppress_override:
        if _contains(msg_lower, RESERVE_KEYWORDS):
            logger.info("Keyword override → reserve_car")
            intent, overridden = "reserve_car", True
        elif _contains(msg_lower, PURCHASE_KEYWORDS):
            logger.info("Keyword override → purchase_intent")
            intent, overridden = "purchase_intent", True

    # ── Stage 3: Deterministic confidence scoring ────────────────────────────
    confidence          = _score_confidence(intent, msg_lower)
    needs_clarification = confidence == "low"

    route = _build_route(intent, has_email)
    route["confidence"]          = confidence
    route["needs_clarification"] = needs_clarification
    route["overridden"]          = overridden

    # Low-confidence → don't force a specific tool; let Claude handle clarification
    if needs_clarification:
        route["tool_choice"] = {"type": "auto"}

    return route


# ─── Smoke test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        # Inventory — explicit
        ("Do you have a Tesla Model 3?",                    "search_inventory"),
        ("Show me electric cars under $80,000",             "search_inventory"),
        ("BMW X5 2024 price",                               "search_inventory"),
        # Inventory — synonyms that broke the old router
        ("I'd like to see what Porsches you carry",         "search_inventory"),
        ("What vehicles do you have in red?",               "search_inventory"),
        ("Anything available under fifty grand?",           "search_inventory"),
        # Knowledge base — explicit
        ("What is your return policy?",                     "search_knowledge_base"),
        ("How much does delivery cost?",                    "search_knowledge_base"),
        ("How do I schedule a test drive?",                 "search_knowledge_base"),
        # Knowledge base — synonyms
        ("Can I give the car back if I change my mind?",    "search_knowledge_base"),
        ("What happens if the car arrives damaged?",        "search_knowledge_base"),
        # Reserve — explicit
        ("I want to reserve the BMW iX",                    "reserve_car"),
        # Reserve — synonyms that broke the old router
        ("Can you hold this one for me?",                   "reserve_car"),
        ("Save that car for me please",                     "reserve_car"),
        ("I'd like to secure the Tesla Model S",            "reserve_car"),
        # Purchase — explicit
        ("I want to buy it, my email is john@example.com",  "purchase_intent"),
        ("I want to buy it",                                "purchase_intent_no_email"),
        # Purchase — synonyms
        ("I'll take the Porsche Taycan",                    "purchase_intent"),
        ("I'm ready to move forward with the purchase",     "purchase_intent"),
        # General
        ("Hello, how are you?",                             "general"),
        ("Thank you!",                                      "general"),
    ]

    print("=== Router smoke test (LLM + keyword) ===\n")
    all_pass = True
    for msg, expected in tests:
        result = classify(msg, [])
        actual = result["intent"]
        # purchase_intent_no_email is acceptable when expected is purchase_intent
        ok = actual == expected or (
            expected == "purchase_intent_no_email" and actual == "purchase_intent_no_email"
        )
        status = "✓" if ok else "✗"
        if not ok:
            all_pass = False
        print(f"  {status} [{actual:<35}] {msg}")

    print(f"\n{'✓ הכל תקין' if all_pass else '✗ יש כשלונות'}")
