"""
app.py — Streamlit chat UI for the AI Car Concierge.
"""

import time
import streamlit as st
from agent import chat, create_session
from database import run_migration
from vector_store import build_vector_store
from analytics import get_confidence_stats, get_recent_low_confidence

MAX_MESSAGES_PER_SESSION = 50   # hard cap — prevents runaway API spend

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Premium Cars — AI Concierge",
    page_icon="🚗",
    layout="centered",
)

# ─── Startup (runs once per server process) ──────────────────────────────────

@st.cache_resource(show_spinner="Initializing...")
def initialize():
    run_migration()
    build_vector_store()

initialize()

# ─── Session state ───────────────────────────────────────────────────────────

if "history" not in st.session_state:
    st.session_state.history = create_session()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_message_time" not in st.session_state:
    st.session_state.last_message_time = 0.0

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🚗 Premium Cars")
    st.markdown("**Beverly Hills, CA**")
    st.markdown("AI Concierge — Available 24/7")
    st.divider()

    st.markdown("#### Try asking:")
    examples = [
        "Do you have any Tesla electric cars?",
        "Show me BMWs under $80,000",
        "What's your return policy?",
        "Do you have a BMW X5 from 2020?",
        "I'd like to reserve a car",
        "How does delivery work?",
    ]
    for example in examples:
        if st.button(example, use_container_width=True, key=example):
            st.session_state._pending_input = example

    st.divider()

    if st.button("🗑️ New conversation", use_container_width=True):
        st.session_state.history  = create_session()
        st.session_state.messages = []
        st.rerun()

    st.divider()

    # ── Router confidence stats ───────────────────────────────────────────────
    st.markdown("#### Router confidence")
    stats = get_confidence_stats()

    if not stats or stats.get("total", 0) == 0:
        st.caption("No classifications yet.")
    else:
        total = stats["total"]
        bc    = stats["by_confidence"]
        high   = bc.get("high",   0)
        medium = bc.get("medium", 0)
        low    = bc.get("low",    0)

        # Colour-coded confidence bars
        st.progress(high / total,   text=f"High    {high}/{total}")
        st.progress(medium / total, text=f"Medium  {medium}/{total}")
        low_pct = low / total
        st.progress(low_pct, text=f"Low     {low}/{total}")

        if stats.get("overrides"):
            st.caption(f"Keyword overrides: {stats['overrides']}")
        if stats.get("clarifications"):
            st.caption(f"Clarifications asked: {stats['clarifications']}")

        # Show recent low-confidence cases so you can review them
        if low > 0:
            with st.expander(f"Recent low-confidence ({low})"):
                for row in get_recent_low_confidence(limit=5):
                    override_tag = " ⚡override" if row["overridden"] else ""
                    clarify_tag  = " ❓clarified" if row["needs_clarify"] else ""
                    st.markdown(
                        f"**{row['intent']}**{override_tag}{clarify_tag}  \n"
                        f"`{row['ts']}`  \n"
                        f"_{row['message_preview']}_"
                    )
                    st.divider()

    st.divider()
    st.caption("support@premiumcars.com")
    st.caption("+1 (800) 555-0199")

# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown("## Premium Cars — AI Concierge")
st.caption("Ask me about our vehicles, policies, reservations, or pricing.")
st.divider()

# ─── Chat history ────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ─── Handle sidebar example buttons ─────────────────────────────────────────

pending = st.session_state.pop("_pending_input", None)

# ─── Chat input ──────────────────────────────────────────────────────────────

user_input = st.chat_input("Ask about our vehicles, policies, or reservations...") or pending

if user_input:
    # Rate limit: 1 message per second (prevents rapid-fire double-sends)
    now = time.time()
    if now - st.session_state.last_message_time < 1.0:
        st.warning("Please wait a moment before sending another message.")
        st.stop()

    # Hard session cap — prevents runaway API spend
    if len(st.session_state.messages) >= MAX_MESSAGES_PER_SESSION:
        st.error("Session limit reached. Please start a new conversation.")
        st.stop()

    st.session_state.last_message_time = now

    # Show user message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Get agent response
    with st.chat_message("assistant"):
        with st.status("Thinking...", expanded=False) as status:
            reply, st.session_state.history = chat(user_input, st.session_state.history)
            status.update(label="Done", state="complete", expanded=False)
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
