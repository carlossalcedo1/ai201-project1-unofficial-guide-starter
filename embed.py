"""
embed.py — Stage 3 of the UF Dining Unofficial Guide RAG pipeline.

  chunks.json  →  all-MiniLM-L6-v2  →  ChromaDB  →  retrieve()
  ───────────     ────────────────     ─────────     ──────────
  from ingest.py  sentence-transformers  local disk   top-k=5

Run:
    python embed.py                  # embed + store (run once)
    python embed.py --query "..."    # embed + store, then test retrieval

The ChromaDB collection persists to ./chroma_db/ so you only need to
embed once. Subsequent calls to retrieve() read from disk instantly.
"""

from __future__ import annotations

import argparse
import json
import os

import chromadb
from sentence_transformers import SentenceTransformer

# ── Config ──────────────────────────────────────────────────────────────────────
CHUNKS_FILE    = "chunks.json"
CHROMA_DIR     = "chroma_db"          # local folder ChromaDB persists to
COLLECTION     = "uf_dining"          # collection name inside ChromaDB
EMBED_MODEL    = "all-MiniLM-L6-v2"  # from planning.md §Retrieval Approach
TOP_K          = 5                    # from planning.md §Retrieval Approach


# ── Load model + DB (module-level so retrieve() can be imported cheaply) ────────
print(f"Loading embedding model: {EMBED_MODEL} ...")
model = SentenceTransformer(EMBED_MODEL)

chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = chroma_client.get_or_create_collection(
    name=COLLECTION,
    metadata={"hnsw:space": "cosine"},   # cosine similarity per architecture diagram
)


# ── Embedding + Storage ─────────────────────────────────────────────────────────
def embed_and_store(chunks_file: str = CHUNKS_FILE) -> int:
    """
    Read chunks.json, encode every chunk, and upsert into ChromaDB.

    Why upsert (not insert):
    - Upsert is idempotent — running embed.py twice won't duplicate chunks.
      ChromaDB matches on chunk_id, so re-running is safe.

    What gets stored per chunk:
    - id          : chunk_id (e.g. "src01_chunk0002") — unique key
    - embedding   : 384-dimensional float vector from all-MiniLM-L6-v2
    - document    : the raw chunk text (returned alongside results at retrieval)
    - metadata    : source_id, source_title, source_url, token_count,
                    chunk_index (position of this chunk within its source doc)
                    — surfaced in retrieve() so the answer cites its source
    """
    if not os.path.exists(chunks_file):
        raise FileNotFoundError(
            f"{chunks_file} not found. Run `python ingest.py` first."
        )

    with open(chunks_file, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Encoding {len(chunks)} chunks with {EMBED_MODEL} ...")
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)

    print("Upserting into ChromaDB ...")
    collection.upsert(
        ids        = [c["chunk_id"]    for c in chunks],
        embeddings = embeddings.tolist(),
        documents  = texts,
        metadatas  = [
            {
                "source_id"   : c["source_id"],
                "source_title": c["source_title"],
                "source_url"  : c["source_url"],
                "token_count" : c["token_count"],
                # chunk_index: position of this chunk within its source document
                # parsed from chunk_id e.g. "src01_chunk0003" → 3
                # useful for reconstructing surrounding context if needed
                "chunk_index" : int(c["chunk_id"].split("chunk")[-1]),
            }
            for c in chunks
        ],
    )

    stored = collection.count()
    print(f"✓  ChromaDB collection '{COLLECTION}' now holds {stored} chunks.\n")
    return stored


# ── Retrieval ───────────────────────────────────────────────────────────────────
def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Encode the query and return the top-k most similar chunks.

    How it works:
    - The query string is embedded with the same model used at index time.
      Using the same model is critical — the query vector and the stored
      chunk vectors must live in the same embedding space for cosine
      similarity to be meaningful.
    - ChromaDB computes cosine similarity between the query vector and every
      stored chunk vector, then returns the top_k closest matches.

    Returns a list of dicts, each with:
        text         — the chunk text (inject this into the LLM prompt)
        source_title — human-readable source name
        source_url   — cite this in the final answer
        score        — cosine distance (lower = more similar; 0 = identical)
    """
    query_embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks_out = []
    for text, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks_out.append({
            "text"         : text,
            "source_title" : meta["source_title"],
            "source_url"   : meta["source_url"],
            "source_id"    : meta["source_id"],
            "chunk_index"  : meta["chunk_index"],
            "score"        : round(dist, 4),
        })

    return chunks_out


# ── Main ────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Embed chunks and store in ChromaDB.")
    parser.add_argument("--query", type=str, default=None,
                        help="Optional test query to run after embedding.")
    parser.add_argument("--skip-embed", action="store_true",
                        help="Skip embedding (DB already populated) and just run query.")
    args = parser.parse_args()

    if not args.skip_embed:
        embed_and_store()

    if args.query:
        print(f"\nQuery: \"{args.query}\"")
        print("=" * 65)
        results = retrieve(args.query)
        for i, r in enumerate(results, 1):
            print(f"\n[{i}] score={r['score']}  {r['source_title']}")
            print(f"    {r['source_url']}")
            print(f"    {r['text'][:300].strip()} ...")
        print("=" * 65)
    else:
        print("Tip: test retrieval with:")
        print("  python embed.py --skip-embed --query \"what happens to unused flex dollars\"")


if __name__ == "__main__":
    main()
