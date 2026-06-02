"""
vector_store.py
Embeddings: Voyage AI (production) / hash fallback (dev without key).
Store: ChromaDB persistent, chunked by ## headers.
"""
import os
import re
import hashlib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import chromadb

KB_PATH     = Path(__file__).parent / "knowledge_base"
CHROMA_PATH = Path(__file__).parent / "data" / "chroma_db"
COLLECTION  = "knowledge_base"

VOYAGE_KEY  = os.environ.get("VOYAGE_API_KEY")


# ─── Embeddings ─────────────────────────────────────────────────────────────

def embed(texts: list[str]) -> list[list[float]]:
    if VOYAGE_KEY:
        return _voyage_embed(texts)
    print("⚠️  VOYAGE_API_KEY חסר — משתמש ב-fallback (לא סמנטי)")
    return _hash_embed(texts)


def _voyage_embed(texts: list[str]) -> list[list[float]]:
    import voyageai
    client = voyageai.Client(api_key=VOYAGE_KEY)
    result = client.embed(texts, model="voyage-2", input_type="document")
    return result.embeddings


def _hash_embed(texts: list[str]) -> list[list[float]]:
    import math
    DIM = 256
    vectors = []
    for text in texts:
        h   = hashlib.sha256(text.encode()).digest()
        vec = [math.sin(h[i % 32] + i) * math.cos(h[i % 32] * i + 1) for i in range(DIM)]
        n   = sum(x**2 for x in vec) ** 0.5 or 1
        vectors.append([x / n for x in vec])
    return vectors


# ─── Chunking ────────────────────────────────────────────────────────────────

def chunk_markdown(file_path: Path) -> list[dict]:
    """חותך לפי ## headers — כל section = chunk סמנטי."""
    text     = file_path.read_text(encoding="utf-8")
    sections = re.split(r'\n(?=## )', text)
    chunks   = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        lines  = section.split('\n')
        header = lines[0].lstrip('#').strip()
        body   = '\n'.join(lines[1:]).strip()
        if not body:
            continue
        chunk_id = hashlib.md5(f"{file_path.name}::{header}".encode()).hexdigest()
        chunks.append({
            "id":     chunk_id,
            "text":   section,
            "source": file_path.name,
            "header": header,
        })
    return chunks


# ─── Build / Load ────────────────────────────────────────────────────────────

def build_vector_store(force: bool = False):
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    if force:
        try:
            client.delete_collection(COLLECTION)
            print("מחק collection קיים...")
        except Exception:
            pass

    try:
        col = client.get_collection(COLLECTION)
        if col.count() > 0 and not force:
            print(f"✓ Vector store קיים ({col.count()} chunks)")
            return
    except Exception:
        pass

    col = client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    all_chunks = []
    for md_file in sorted(KB_PATH.glob("*.md")):
        chunks = chunk_markdown(md_file)
        all_chunks.extend(chunks)
        print(f"  {md_file.name}: {len(chunks)} chunks")

    print(f"מייצר embeddings ל-{len(all_chunks)} chunks...")
    embeddings = embed([c["text"] for c in all_chunks])

    col.add(
        ids        = [c["id"]     for c in all_chunks],
        documents  = [c["text"]   for c in all_chunks],
        embeddings = embeddings,
        metadatas  = [{"source": c["source"], "header": c["header"]} for c in all_chunks],
    )
    print(f"✓ Vector store נבנה: {col.count()} chunks")


# ─── Search ──────────────────────────────────────────────────────────────────

def search_knowledge_base(query_text: str, n_results: int = 3) -> dict:
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        col    = client.get_collection(COLLECTION)
    except Exception:
        return {"success": False, "error": "vector_store_unavailable", "results": []}

    try:
        query_vec = embed([query_text])[0]
        results   = col.query(
            query_embeddings = [query_vec],
            n_results        = min(n_results, col.count()),
            include          = ["documents", "metadatas", "distances"],
        )
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "text":      doc,
            "source":    meta["source"],
            "header":    meta["header"],
            "relevance": round(1 - dist, 3),
        })

    return {"success": True, "count": len(hits), "results": hits}


# ─── Inspection (dev only) ───────────────────────────────────────────────────

def inspect_chunks():
    """Print every chunk in the store — header, source, first 120 chars."""
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        col = client.get_collection(COLLECTION)
    except Exception:
        print("✗ Vector store לא קיים — הרץ build_vector_store() קודם")
        return

    data = col.get(include=["documents", "metadatas"])
    docs  = data["documents"]
    metas = data["metadatas"]

    by_source: dict = {}
    for doc, meta in zip(docs, metas):
        src = meta["source"]
        by_source.setdefault(src, []).append((meta["header"], doc))

    total = 0
    for src in sorted(by_source):
        chunks = by_source[src]
        print(f"\n  [{src}] — {len(chunks)} chunks")
        for header, doc in chunks:
            preview = doc.replace("\n", " ")[:120]
            print(f"    • {header}")
            print(f"      {preview}...")
            total += 1

    print(f"\n  סה\"כ: {total} chunks")


def inspect_search(query_text: str, n_results: int = 3):
    """Run a search and print full results with relevance scores."""
    print(f"\n  שאילתה: \"{query_text}\"")
    res = search_knowledge_base(query_text, n_results=n_results)
    if not res["success"]:
        print(f"  ✗ שגיאה: {res.get('error')}")
        return
    for i, hit in enumerate(res["results"], 1):
        print(f"  #{i} [{hit['source']}] \"{hit['header']}\" — relevance: {hit['relevance']}")
        preview = hit["text"].replace("\n", " ")[:160]
        print(f"      {preview}...")


if __name__ == "__main__":
    import sys

    # python3 vector_store.py rebuild    → force rebuild + search test
    # python3 vector_store.py chunks     → show all chunks
    # python3 vector_store.py search     → run search battery
    # python3 vector_store.py            → rebuild + full inspection

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("rebuild", "all"):
        build_vector_store(force=True)

    if mode in ("chunks", "all"):
        print("\n══════ CHUNKS IN STORE ══════")
        inspect_chunks()

    if mode in ("search", "all"):
        SEARCH_TESTS = [
            ("Can I return a car after buying it?",   "support.md"),
            ("How do I book a test drive?",           "faqs.md"),
            ("What is the minimum car year you sell?","policy.md"),
            ("EV battery charging tips",              "maintenance.md"),
            ("How much does delivery cost?",          "shipping.md"),
            ("financing options",                     "faqs.md"),
            ("warranty coverage",                     "faqs.md"),
        ]

        print("\n══════ SEARCH QUALITY ══════")
        all_pass = True
        for q, expected_src in SEARCH_TESTS:
            res = search_knowledge_base(q, n_results=1)
            if not res["success"] or not res["results"]:
                print(f"  ✗ {q!r} — אין תוצאות")
                all_pass = False
                continue
            top = res["results"][0]
            ok  = top["source"] == expected_src
            mark = "✓" if ok else "✗"
            color = "\033[92m" if ok else "\033[91m"
            end   = "\033[0m"
            print(f"  {color}{mark}{end} [{top['source']}] {top['header']!r} "
                  f"(relevance={top['relevance']}) — Q: {q!r}")
            if not ok:
                print(f"      ↳ ציפינו: {expected_src}")
                all_pass = False

        print(f"\n  {'✓ כל חיפושים נכונים' if all_pass else '✗ יש כשלונות בחיפוש'}")

    if mode == "detail":
        # Interactive: python3 vector_store.py detail "your query here"
        q = sys.argv[2] if len(sys.argv) > 2 else "return policy"
        inspect_search(q, n_results=3)
