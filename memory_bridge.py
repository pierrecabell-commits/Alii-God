#!/usr/bin/env python3
"""
Alii Memory Bridge
Connects alii_core.db (SQLite) + memories.json -> Qdrant for semantic search.
Uses simple TF-IDF-style vectors via sentence embeddings (via Ollama or fallback).
"""
import os
import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from config import (QDRANT_URL, SQLITE_DB, MEMORIES_JSON, COLLECTION_NAME,
                    EMBED_DIM, LOG_DIR, DATA_DIR, OLLAMA_URL)

LOG_FILE = str(LOG_DIR / "memory_bridge.log")
STATE_FILE = str(DATA_DIR / "memory_bridge_state.json")

# Module-level QdrantClient singleton — avoids per-call connection overhead.
_qdrant_client = None


def _get_client():
    """Return (creating if necessary) the shared QdrantClient."""
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient as _QC
        _qdrant_client = _QC(url=QDRANT_URL)
    return _qdrant_client


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_embedding_ollama(text: str) -> list:
    """Get embedding from Ollama nomic-embed-text model."""
    import urllib.request
    import json as _json
    try:
        payload = _json.dumps({"model": "nomic-embed-text", "prompt": text[:2000]}).encode()
        req = urllib.request.Request(f"{OLLAMA_URL}/api/embeddings", payload)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read())
            emb = data.get("embedding", [])
            if emb:
                return emb
    except Exception:
        pass
    return None


def hash_embedding(text: str, dim: int = EMBED_DIM) -> list:
    """Deterministic fallback: hash text to a normalized float vector."""
    import math
    seed = hashlib.sha256(text.encode()).hexdigest()
    vec = []
    for i in range(dim):
        h = hashlib.md5(f"{seed}{i}".encode()).hexdigest()
        val = (int(h[:4], 16) / 32767.5) - 1.0
        vec.append(val)
    mag = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / mag, 6) for x in vec]


def get_embedding(text: str) -> list:
    """Get embedding, trying Ollama first then hash fallback."""
    emb = get_embedding_ollama(text)
    if emb and len(emb) == EMBED_DIM:
        return emb
    # Try to pull nomic-embed-text dimensions
    if emb and len(emb) > 0:
        return emb  # use whatever dimension Ollama returns
    return hash_embedding(text, EMBED_DIM)


def ensure_collection(client, dim: int):
    """Create Qdrant collection if it doesn't exist."""
    from qdrant_client.models import Distance, VectorParams
    try:
        client.get_collection(COLLECTION_NAME)
        log(f"Collection '{COLLECTION_NAME}' already exists")
    except Exception:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        log(f"Created collection '{COLLECTION_NAME}' dim={dim}")


def load_sqlite_memories() -> list:
    """Load memories from alii_core.db."""
    if not os.path.exists(SQLITE_DB):
        log(f"SQLite DB not found: {SQLITE_DB}")
        return []
    conn = sqlite3.connect(SQLITE_DB)
    rows = conn.execute(
        "SELECT id, category, content, metadata, timestamp FROM memories"
    ).fetchall()
    conn.close()
    items = []
    for row in rows:
        items.append({
            "source": "sqlite",
            "id": f"sqlite_{row[0]}",
            "category": row[1] or "",
            "content": row[2] or "",
            "metadata": row[3] or "{}",
            "timestamp": row[4] or "",
        })
    log(f"Loaded {len(items)} memories from SQLite")
    return items


def load_json_memories() -> list:
    """Load memories from memories.json."""
    items = []
    for json_path in [str(MEMORIES_JSON)]:
        if not os.path.exists(json_path):
            continue
        try:
            with open(json_path) as f:
                data = json.load(f)
            idx = 0
            for category in ["context", "facts", "projects"]:
                for entry in data.get(category, []):
                    items.append({
                        "source": "json",
                        "id": f"json_{Path(json_path).parent.name}_{idx}",
                        "category": category,
                        "content": entry.get("content", ""),
                        "metadata": json.dumps(entry.get("metadata", {})),
                        "timestamp": entry.get("timestamp", ""),
                    })
                    idx += 1
            log(f"Loaded {idx} memories from {json_path}")
        except Exception as e:
            log(f"Error reading {json_path}: {e}")
    return items


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"indexed_ids": []}


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def index_memories(force: bool = False):
    """Index all memories into Qdrant."""
    from qdrant_client.models import PointStruct

    log("=== Memory Bridge START ===")
    client = _get_client()

    # Load memories
    all_items = load_sqlite_memories() + load_json_memories()
    if not all_items:
        log("No memories to index")
        return

    # Determine embedding dimension from first item
    test_emb = get_embedding(all_items[0]["content"][:200])
    dim = len(test_emb)
    log(f"Embedding dimension: {dim}")

    ensure_collection(client, dim)
    state = load_state()
    indexed = set(state.get("indexed_ids", []))

    points = []
    skipped = 0
    for item in all_items:
        uid = item["id"]
        if not force and uid in indexed:
            skipped += 1
            continue
        content = item["content"]
        if not content.strip():
            continue
        emb = get_embedding(content)
        if len(emb) != dim:
            continue
        # Convert string id to integer hash for Qdrant
        point_id = int(hashlib.md5(uid.encode()).hexdigest()[:8], 16)
        points.append(PointStruct(
            id=point_id,
            vector=emb,
            payload={
                "source": item["source"],
                "original_id": uid,
                "category": item["category"],
                "content": content[:500],
                "timestamp": item["timestamp"],
            }
        ))
        indexed.add(uid)

    if points:
        # Batch upsert in chunks of 100
        for i in range(0, len(points), 100):
            batch = points[i:i + 100]
            client.upsert(collection_name=COLLECTION_NAME, points=batch)
        log(f"Indexed {len(points)} new memories (skipped {skipped} already indexed)")
    else:
        log(f"All {skipped} memories already indexed")

    state["indexed_ids"] = list(indexed)
    state["last_run"] = datetime.now().isoformat()
    save_state(state)
    log("=== Memory Bridge DONE ===")


def search_memories(query: str, limit: int = 5) -> list:
    """Semantic search over memories."""
    client = _get_client()
    emb = get_embedding(query)
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=emb,
        limit=limit,
    ).points
    return [{"score": r.score, "content": r.payload.get("content", ""),
             "category": r.payload.get("category", ""),
             "source": r.payload.get("source", "")}
            for r in results]


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "search":
        query = " ".join(sys.argv[2:]) or "alii capabilities"
        results = search_memories(query)
        for r in results:
            print(f"[{r['score']:.3f}] ({r['category']}) {r['content'][:120]}")
    elif len(sys.argv) > 1 and sys.argv[1] == "--force":
        index_memories(force=True)
    else:
        index_memories()
