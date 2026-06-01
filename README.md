# Premium Cars — AI Concierge

A production-grade AI chatbot for a luxury car dealership, built as an engineering assessment.

---

## Overview

Premium Cars is a Beverly Hills luxury dealership. Their AI Concierge handles customer inquiries 24/7 — searching live inventory, answering policy questions, reserving vehicles, and processing purchase inquiries — all through a natural conversation interface.

The system combines two data sources:
- **SQL database** — 100 vehicles with live stock counts and reservation state
- **Vector store** — 5 markdown policy documents (returns, shipping, maintenance, FAQs)

The agent routes between them automatically based on the nature of the question.

---

## Architecture

```
Customer (Streamlit UI)
         ↓
     app.py
     Rate limiting, session management, message history
         ↓
     agent.py
     Claude Haiku 4.5 — native tool_use, system prompt, agent loop
         ↓
     tools.py — 4 tools
         ↓
  ┌─────────────────────────────────────────────┐
  │  search_inventory      → Supabase Postgres  │
  │  search_knowledge_base → ChromaDB           │
  │  reserve_car           → Supabase Postgres  │
  │  send_purchase_email   → Resend API         │
  └─────────────────────────────────────────────┘
```

**Core principle: Claude formats answers — it does not make policy decisions.**

Every business rule (year eligibility, stock availability, reservation expiry) is enforced in Python code before results reach the LLM. Claude receives a clean JSON result with explicit `status`, `sellable`, and `status_note` fields. It never decides what can or cannot be sold — the code already decided.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| LLM | Claude Haiku 4.5 (Anthropic) | Fast, cheap, excellent instruction-following |
| Agent framework | Native Anthropic `tool_use` | Full control, no magic, no LangChain overhead |
| Embeddings | Voyage AI (`voyage-2`) | Outperforms OpenAI on retrieval benchmarks |
| Vector store | ChromaDB | Persistent, local, no extra infrastructure |
| Database | Supabase (PostgreSQL) | Managed Postgres, free tier, instant setup |
| Email | Resend API | Simple transactional email, reliable deliverability |
| Frontend | Streamlit | Fast to build, sufficient for demo |
| Deployment | Railway | Native Python support, persistent filesystem, simple env vars |

---

## AI Tools Used — and How They Accelerated Development

### Claude (Anthropic) — the agent itself
Claude powers the chatbot via native `tool_use`. It receives a system prompt, a set of 4 tool definitions, and the conversation history — and decides which tool to call (or whether to answer directly) on every turn.

Critically, Claude is not trusted to make business decisions. It receives pre-computed `status` and `sellable` fields and is instructed to format them — not interpret them. This separation prevents hallucinations about availability, pricing, or policy.

### Claude Code — development assistant
The entire codebase was built iteratively using Claude Code as a development assistant. Claude Code was used to explore options, surface tradeoffs, and review decisions — but every architectural choice was made by me. Claude proposed alternatives; I evaluated them, pushed back, and decided. 

### Voyage AI — semantic search
`voyage-2` embeddings power the knowledge base retrieval. Voyage AI is purpose-built for retrieval tasks and consistently outperforms general-purpose embedding models (including OpenAI `text-embedding-3`) on domain-specific content. The knowledge base is chunked by `##` headers and stored in ChromaDB. Falls back to a hash-based embedding if no API key is provided — allowing local development without credentials.

### Supabase — managed Postgres
Used as the production database. Supabase provides a free-tier managed PostgreSQL instance with connection pooling. The reservations system uses `expires_at > NOW()` queries for lazy expiry — meaning expired reservations are never explicitly deleted, just ignored at query time.

---

## Key Architectural Decisions

### 1. No router — tool descriptions as intent signals

Early versions used a separate LLM-based router to classify the user's intent before calling tools. This caused multiple problems:
- Double API calls per message (router + agent)
- Language bugs — the router responded in English even when the user wrote Hebrew
- Hallucinations — the router invented intent categories that didn't map to available tools
- Fragility — "אם אני רוצה להזמין" (conditional phrasing) triggered reservation flows incorrectly

**The fix:** remove the router entirely. Claude's `tool_choice: auto` mode lets the model read tool descriptions and select the correct tool autonomously. Each tool description is written as an explicit contract — what to use it for, and what NOT to use it for. This approach requires zero classification logic and handles edge cases naturally.

### 2. Reservations table instead of decrementing stock_count

The assignment specification asked to decrement `stock_count` when a car is reserved. This approach has a critical flaw: if the reservation expires, there is no way to automatically restore the count without a background job.

Instead, a separate `reservations` table was created:

```sql
CREATE TABLE reservations (
    id          SERIAL PRIMARY KEY,
    car_id      INTEGER NOT NULL,
    user_name   TEXT NOT NULL,
    user_email  TEXT NOT NULL,
    reserved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP NOT NULL
);
```

`available_units` is computed at query time: `stock_count - COUNT(active reservations)`. When a reservation expires, it is simply not counted — no cron job, no background process, no race conditions.

This also means the original `stock_count` is preserved and auditable at all times.

### 3. Business logic in code, not prompts

Any rule that can be enforced in code should not be trusted to a prompt. The LLM is a probabilistic text generator — it will occasionally be wrong. Code is deterministic.

Examples:
- **2022 policy** — `if car["year"] < POLICY_MIN_YEAR: return {"sellable": False}` in `tools.py`. Claude never decides this.
- **Stock check** — `reserve_car()` queries the DB and counts active reservations before writing. If a race condition occurs, the insert is rejected.
- **Pre-2022 cars hidden by default** — filtered from `search_inventory` results in Python. Claude never sees them unless the customer explicitly asks about a specific old year.
- **Confirmation gate** — the system prompt requires Claude to present a summary and wait for explicit "yes" before calling `reserve_car` or `send_purchase_email`. The tool itself also validates all required fields.

### 4. Reservation timing embedded in search results

`search_inventory` computes the release time of reserved vehicles directly in the same query, using:
```sql
EXTRACT(EPOCH FROM (MIN(expires_at) - NOW()))::int AS seconds_remaining
```

This means Claude receives `status_note: "All units reserved. Earliest release in 71h 23m"` in the search result itself — no second tool call needed. This reduces latency and eliminates a redundant round-trip.

### 5. Input sanitization and session safety

Several production-grade safety measures are in place:
- **Input sanitization** — unicode normalization (NFC) + control character removal protects against prompt injection via malformed inputs
- **Length cap** — inputs truncated at 2,000 characters
- **Iteration cap** — agent loop capped at 10 tool calls per message to prevent runaway API spend
- **History trimming** — conversation history capped at 40 messages (20 turns) to prevent context overflow
- **Rate limiting** — 1 message per second minimum in the UI
- **Session cap** — 50 messages per session hard limit

---

## Data Design

### Inventory (inventory.sql)
The SQL file contains 100 vehicles across 15 brands, designed with deliberate edge cases:

| Segment | Count | Purpose |
|---------|-------|---------|
| Sellable (2022+) | 82 | Normal happy path |
| Pending de-listing (2020–2021) | 15 | Conflict resolution testing |
| Out of stock (stock_count = 0) | 3 | Stock exhaustion edge case |

The pre-2022 vehicles are intentional — they exist in the DB to verify that the system correctly detects the policy conflict and refuses to sell them, while still acknowledging their existence when asked directly.

Price range: $39,990 – $579,900. Fuel types: Electric, Gasoline, Hybrid — each maps to a different maintenance schedule in the knowledge base.

### Knowledge Base (ChromaDB vector store)
5 markdown documents are chunked and indexed at startup using `##` header boundaries. Each chunk represents one coherent policy topic, which improves retrieval precision.

```
policy.md       → 2022+ sales rule (the critical conflict resolution trigger)
support.md      → refund windows, contact channels
faqs.md         → test drive scheduling
maintenance.md  → EV vs gasoline vs hybrid service intervals
shipping.md     → delivery zones, timeframes, costs
```



---

## The 4 Tools

| Tool | Purpose | Guard conditions |
|------|---------|-----------------|
| `search_inventory` | Query vehicles + reservations tables, compute real-time availability per unit, support all DB filters | None — safe read |
| `search_knowledge_base` | Query ChromaDB policies | None — safe read |
| `reserve_car` | Write reservation to DB | Requires: confirmed intent + car_id + name + email + year policy check |
| `send_purchase_email` | Send email via Resend | Requires: confirmed intent + email |

---

## Local Setup

### Prerequisites
- Python 3.10+
- A Supabase project 
- Run `data/inventory.sql` in the Supabase SQL editor to create and seed the database

### Steps

```bash
# 1. Clone the repository
git clone <repo-url>
cd moveo-assignment

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and DATABASE_URL (minimum required)

# 4. Run the app
streamlit run app.py
```

The app will automatically:
- Run the database migration on first startup
- Build the ChromaDB vector store from the knowledge base files
- Create the reservations table if it doesn't exist

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key (Anthropic console) |
| `DATABASE_URL` | ✅ | Supabase connection string |
| `VOYAGE_API_KEY` | Optional | Better RAG quality — hash fallback if missing |
| `RESEND_API_KEY` | Optional | Real email sending — console print if missing |

---

## Project Structure

```
├── app.py                  # Streamlit UI — session state, rate limiting, chat loop
├── agent.py                # Claude agent — system prompt, tool loop, input sanitization
├── tools.py                # 4 tools — all business logic, DB queries, email
├── database.py             # Postgres DB layer — connection, query/write helpers, migration
├── vector_store.py         # ChromaDB + Voyage AI — chunking, indexing, semantic search
├── knowledge_base/
│   ├── policy.md           # 2022+ sales policy — the critical conflict resolution rule
│   ├── support.md          # Refund policy and contact information
│   ├── faqs.md             # Test drive scheduling
│   ├── maintenance.md      # EV vs gasoline vs hybrid service schedules
│   └── shipping.md         # Delivery zones and logistics
├── data/
│   └── inventory.sql       # 100 vehicles — schema + seed data (edge cases included)
├── Procfile                # Railway startup command
├── requirements.txt        # Python dependencies
└── .env.example            # Environment variable template
```

---

