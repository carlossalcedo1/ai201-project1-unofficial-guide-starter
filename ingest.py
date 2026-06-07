"""
ingest.py — Stage 1 & 2 of the UF Dining Unofficial Guide RAG pipeline.

  Document Ingestion  →  Cleaning  →  Chunking  →  chunks.json
  ───────────────────    ─────────    ─────────    ───────────
  requests + BS4            regex      tiktoken     saved for
  pdfplumber (PDFs)                   300 tok /    Stage 3
                                      50 overlap

Run:
    python ingest.py

Output:
    chunks.json   — list of chunk dicts ready for embedding
    (console)     — per-source stats + spec verification table
"""

from __future__ import annotations

import io
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from typing import Optional

import html
import pdfplumber
import requests
import tiktoken
from bs4 import BeautifulSoup

# ── Config ──────────────────────────────────────────────────────────────────────
CHUNK_SIZE = 300          # tokens  (from planning.md §Chunking Strategy)
OVERLAP    = 50           # tokens
STEP       = CHUNK_SIZE - OVERLAP   # = 250 tokens advance per window
ENCODING   = "cl100k_base"          # tiktoken encoding (used by GPT-4 / Claude tokenisers)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 (research-bot)"
    )
}

# ── Sources (planning.md §Documents) ───────────────────────────────────────────
SOURCES: list[dict] = [
    {
        "id": 1,
        "title": "UF Dining Terms & Conditions 2025-26",
        "url": "https://businessservices.ufl.edu/2025-2026-terms-conditions/",
        "type": "html",
    },
    {
        "id": 2,
        "title": "Florida Fresh Dining – New Food Concepts",
        "url": (
            "https://businessservices.ufl.edu/2022/10/10/"
            "florida-fresh-dining-introduces-new-food-concepts-"
            "new-technology-and-mobile-ordering-at-uf/"
        ),
        "type": "html",
    },
    {
        "id": 3,
        "title": "UF Food Service Master Plan (PDF)",
        "url": (
            "https://businessservices.ufl.edu/wp-content/uploads/2020/01/"
            "Food-Svcs-Master-Plan-Report_Final_December-2019.pdf"
        ),
        "type": "pdf",
    },
    {
        "id": 4,
        "title": "Florida Alligator – UF Vegan Dining Experience",
        "url": "https://www.alligator.org/article/2024/01/uf-vegan-experience",
        "type": "html",
    },
    {
        "id": 5,
        "title": "Spoon University – New Dining Hall Review",
        "url": "https://spoonuniversity.com/school/ufl/reviewing-the-new-dining-hall/",
        "type": "html",
    },
    {
        "id": 6,
        "title": "HerCampus UFL – Dietary Restrictions in College",
        "url": "https://www.hercampus.com/school/ufl/living-dietary-restrictions-college/",
        "type": "html",
    },
    {
        "id": 7,
        "title": "UF Dining Program Overview",
        "url": "https://businessservices.ufl.edu/services/dining/",
        "type": "html",
    },
    {
        "id": 8,
        "title": "GatorCare Campus Food Resources (PDF)",
        "url": (
            "https://ufh-gatorcare.sites.medinfo.ufl.edu/files/2015/09/"
            "Campus-Food-Resources-V5.pdf"
        ),
        "type": "pdf",
    },
    {
        "id": 9,
        "title": "Prked – Guide to UF Meal Plans 2024-25",
        "url": "https://prked.com/post/guide-to-uf-meal-plans-2024-2025",
        "type": "html",
    },
    {
        "id": 10,
        "title": "Florida Alligator – Bite Club Meal Plan Alternative",
        "url": "https://www.alligator.org/article/2024/09/what-to-know-about-a-new-student-meal-plan-alternative",
        "type": "html",
    },
]


# ── Data classes ────────────────────────────────────────────────────────────────
@dataclass
class Document:
    source_id: int
    title: str
    url: str
    text: str


@dataclass
class Chunk:
    chunk_id: str        # e.g. "src01_chunk0003"
    source_id: int
    source_title: str
    source_url: str
    text: str
    token_count: int


# ── Caching ─────────────────────────────────────────────────────────────────────
CACHE_DIR = "documents"   # raw text cached here after first fetch

def _cache_path(source_id: int) -> str:
    import os
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"source_{source_id:02d}.txt")


# ── Ingestion ───────────────────────────────────────────────────────────────────
def fetch_html(url: str) -> str:
    """
    Download a web page and extract the main body text.

    Why this approach:
    - We strip nav/header/footer/scripts so the chunks don't pollute
      the vector store with boilerplate like "Home | About | Contact".
    - We prefer <main> or <article> because that's where the actual
      content lives on modern CMS sites (UF Business Services, Alligator,
      Spoon, HerCampus all use standard semantic HTML).
    - Falling back to soup.body means we still get something even on
      non-semantic pages (Prked, older UF pages).
    """
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove boilerplate tags
    for tag in soup(["nav", "header", "footer", "script", "style", "aside",
                     "form", "noscript", "iframe"]):
        tag.decompose()

    # Prefer semantic content containers
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", class_=re.compile(
            r"(entry|post|article|content|body|text)[-_]?(content|body|text|wrap)?",
            re.I
        ))
    )
    target = main if main else soup.body
    return target.get_text(separator="\n") if target else soup.get_text(separator="\n")


def fetch_pdf(url: str) -> str:
    """
    Download a PDF and extract text page-by-page with pdfplumber.

    Why pdfplumber:
    - It handles multi-column layouts better than PyPDF2.
    - The Food Service Master Plan (source #3) is a formatted audit report;
      pdfplumber preserves paragraph structure well enough for chunking.
    - Pages with no extractable text (scanned images) are skipped silently.
    """
    resp = requests.get(url, headers=HEADERS, timeout=45)
    resp.raise_for_status()
    pages = []
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                pages.append(text)
    return "\n\n".join(pages)


def ingest_source(source: dict) -> Optional[Document]:
    """
    Load a source, using a local cache in documents/ when available.

    Cache strategy:
    - On first run: fetch from the web, save raw text to documents/source_NN.txt
    - On subsequent runs: read from that file (fast, no network needed)
    - To force a re-fetch: delete the cache file for that source

    This is important for the class project: scraping takes time and some
    sites rate-limit repeated requests. Caching means you only pay that cost
    once.
    """
    import os
    cache = _cache_path(source["id"])

    # ── Cache hit ────────────────────────────────────────────────────────────
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            text = f.read()
        print(f"  [{source['id']:02d}] {source['title'][:48]} (cached ✓, {len(text):,} chars)")
        return Document(source_id=source["id"], title=source["title"],
                        url=source["url"], text=text)

    # ── Cache miss: fetch from web ───────────────────────────────────────────
    print(f"  [{source['id']:02d}] Fetching {source['title'][:48]} ...", end=" ", flush=True)
    try:
        if source["type"] == "pdf":
            text = fetch_pdf(source["url"])
        else:
            text = fetch_html(source["url"])

        if not text or len(text.strip()) < 100:
            print("⚠  very short — skipping")
            return None

        # Save to cache
        with open(cache, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"✓  ({len(text):,} chars, saved to {cache})")
        return Document(source_id=source["id"], title=source["title"],
                        url=source["url"], text=text)

    except requests.exceptions.HTTPError as e:
        print(f"✗  HTTP {e.response.status_code}")
        return None
    except Exception as e:
        print(f"✗  {type(e).__name__}: {e}")
        return None


# ── Cleaning ────────────────────────────────────────────────────────────────────
def clean_text(text: str) -> str:
    """
    Normalise whitespace and strip common web/PDF artefacts.

    Why each step:
    - Collapsing 3+ newlines: preserves paragraph breaks (2 newlines) but
      removes the excessive blank lines that BeautifulSoup emits between
      block elements.
    - Inline space collapse: removes indentation left over from HTML pre-
      formatting that adds no semantic value.
    - Page-number / separator lines: PDF pages often emit lines like "12"
      or "---" between sections; these would appear mid-chunk and confuse
      the retriever.
    - Skip-to / cookie notices: common in modern UF web pages; removing
      them keeps chunks on-topic.
    """
    # Decode HTML entities (&amp; → &, &nbsp; → space, &lt; → <, etc.)
    # BeautifulSoup handles most of these, but PDFs and some scrapers leave them behind.
    text = html.unescape(text)
    # Replace non-breaking spaces with regular spaces
    text = text.replace(" ", " ")

    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse excessive blank lines (keep at most one blank line = paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse inline whitespace (tabs, multiple spaces)
    text = re.sub(r"[ \t]+", " ", text)

    # Remove lines that are purely whitespace / page numbers / separators
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        # Skip: empty, lone digits (page numbers), lone punctuation rows
        if not stripped:
            lines.append("")
            continue
        if re.fullmatch(r"[\d\s\-–—_=*#|]{1,6}", stripped):
            continue
        lines.append(stripped)
    text = "\n".join(lines)

    # Strip navigation / legal boilerplate phrases (common on UF sites)
    boilerplate = [
        r"Skip to (main )?content",
        r"Cookie (Policy|Settings|Notice)",
        r"Privacy Policy",
        r"Terms of (Use|Service)",
        r"All rights reserved",
        r"©\s*\d{4}",
        r"Share (this|on|via)",
        r"Follow us on",
    ]
    for pattern in boilerplate:
        text = re.sub(pattern + r".*", "", text, flags=re.I)

    # Final trim
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


# ── Chunking ────────────────────────────────────────────────────────────────────
def chunk_text(doc: Document) -> list[Chunk]:
    """
    Sliding-window token chunking.

    Algorithm:
      1. Encode the entire cleaned text to a token list (tiktoken cl100k_base).
      2. Advance a window of CHUNK_SIZE (300) tokens, stepping STEP (250) tokens
         each iteration — so consecutive chunks share the last OVERLAP (50) tokens.
      3. Decode each window back to a string; store as a Chunk.

    Why 300 / 50:
    - From planning.md: "300 tokens captures a complete thought without pulling
      in unrelated content … 50 tokens ensures a sentence overlapping a chunk
      boundary is present in both chunks."
    - Our sources are short-to-medium articles (200–3000 words). A 300-token
      window = ~225 words, which covers 2-4 typical paragraphs.

    Why cl100k_base encoding:
    - Same tokeniser family as the models we'll use downstream (Claude, GPT-4).
      Counting tokens in the same encoding as the LLM prevents silent truncation
      when chunks are injected into the system prompt.
    """
    enc = tiktoken.get_encoding(ENCODING)
    tokens = enc.encode(doc.text)
    total_tokens = len(tokens)

    chunks: list[Chunk] = []
    idx = 0

    for start in range(0, total_tokens, STEP):
        end = min(start + CHUNK_SIZE, total_tokens)
        window = tokens[start:end]

        # Skip tiny trailing windows (< 30 tokens) — they're usually
        # a dangling sentence fragment that adds noise without value.
        if len(window) < 30:
            break

        chunk_text_str = enc.decode(window)

        chunks.append(Chunk(
            chunk_id=f"src{doc.source_id:02d}_chunk{idx:04d}",
            source_id=doc.source_id,
            source_title=doc.title,
            source_url=doc.url,
            text=chunk_text_str,
            token_count=len(window),
        ))
        idx += 1

    return chunks


# ── Verification helpers ─────────────────────────────────────────────────────────
def verify_chunks(all_chunks: list[Chunk]) -> None:
    """
    Print a spec-compliance table so you can see at a glance whether
    the output matches planning.md.
    """
    print("\n" + "=" * 65)
    print("SPEC VERIFICATION")
    print("=" * 65)
    print(f"{'Source':<45} {'Chunks':>6} {'MaxTok':>7} {'MinTok':>7}")
    print("-" * 65)

    by_source: dict[int, list[Chunk]] = {}
    for c in all_chunks:
        by_source.setdefault(c.source_id, []).append(c)

    over_limit = 0
    for sid in sorted(by_source):
        group = by_source[sid]
        max_tok = max(c.token_count for c in group)
        min_tok = min(c.token_count for c in group)
        flag = "  ← !" if max_tok > CHUNK_SIZE else ""
        if max_tok > CHUNK_SIZE:
            over_limit += 1
        title = group[0].source_title[:44]
        print(f"{title:<45} {len(group):>6} {max_tok:>7} {min_tok:>7}{flag}")

    print("-" * 65)
    print(f"Total chunks: {len(all_chunks)}")
    print(f"Chunks exceeding {CHUNK_SIZE}-token limit: {over_limit}  "
          f"({'✓ PASS' if over_limit == 0 else '✗ FAIL'})")

    # Overlap spot-check: last OVERLAP tokens of chunk N should appear at
    # the start of chunk N+1 for the same source.
    enc = tiktoken.get_encoding(ENCODING)
    mismatches = 0
    for sid, group in by_source.items():
        for i in range(len(group) - 1):
            toks_a = enc.encode(group[i].text)
            toks_b = enc.encode(group[i + 1].text)
            # The tail of chunk i should equal the head of chunk i+1
            tail = toks_a[-OVERLAP:] if len(toks_a) >= OVERLAP else toks_a
            head = toks_b[:len(tail)]
            if tail != head:
                mismatches += 1

    print(f"Overlap token-boundary mismatches: {mismatches}  "
          f"({'✓ PASS' if mismatches == 0 else '✗ FAIL – check STEP calculation'})")
    print("=" * 65)


# ── Main ────────────────────────────────────────────────────────────────────────
def main() -> None:
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  UF Dining Guide — Ingestion + Chunking                 ║")
    print(f"║  Chunk size: {CHUNK_SIZE} tokens  |  Overlap: {OVERLAP} tokens           ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    # ── 1. Ingest ───────────────────────────────────────────────────────────────
    print("── Stage 1: Ingestion ──────────────────────────────────────")
    documents: list[Document] = []
    for source in SOURCES:
        doc = ingest_source(source)
        if doc:
            documents.append(doc)
        time.sleep(0.5)   # be polite to servers

    print(f"\nSuccessfully ingested {len(documents)}/{len(SOURCES)} sources.\n")
    if not documents:
        print("ERROR: No documents ingested. Check your internet connection.")
        sys.exit(1)

    # ── 2. Clean ────────────────────────────────────────────────────────────────
    print("── Stage 2a: Cleaning ─────────────────────────────────────")
    for doc in documents:
        before = len(doc.text)
        doc.text = clean_text(doc.text)
        after = len(doc.text)
        print(f"  [{doc.source_id:02d}] {before:>7,} → {after:>7,} chars  "
              f"({100*(before-after)/before:.1f}% removed)")

    # ── Visual inspection: print first document in full ─────────────────────
    print("\n" + "=" * 65)
    print(f"DOCUMENT INSPECTION — [{documents[0].source_id:02d}] {documents[0].title}")
    print("(Read this. If you see nav text, HTML entities, or off-topic")
    print(" content, delete its cache file and tighten clean_text().)")
    print("=" * 65)
    print(documents[0].text)
    print("=" * 65 + "\n")

    # ── 3. Chunk ────────────────────────────────────────────────────────────────
    print("\n── Stage 2b: Chunking (300 tok / 50 overlap) ──────────────")
    all_chunks: list[Chunk] = []
    for doc in documents:
        chunks = chunk_text(doc)
        all_chunks.extend(chunks)
        print(f"  [{doc.source_id:02d}] {len(doc.text):>7,} chars  →  {len(chunks):>4} chunks")

    # ── 4. Verify ───────────────────────────────────────────────────────────────
    verify_chunks(all_chunks)

    # ── 5. Save ─────────────────────────────────────────────────────────────────
    out_path = "chunks.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([asdict(c) for c in all_chunks], f, indent=2, ensure_ascii=False)

    print(f"\n✓  Saved {len(all_chunks)} chunks → {out_path}")

    # ── 5-chunk preview ─────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("5-CHUNK PREVIEW")
    print("=" * 65)
    for c in all_chunks[:5]:
        print(f"\n[{c.chunk_id}]  source={c.source_id}  tokens={c.token_count}")
        print(f"URL: {c.source_url}")
        print("-" * 40)
        print(c.text)
        print()
    print("=" * 65)
    print("   Ready for Stage 3: Embedding + Vector Store (embed.py)\n")


if __name__ == "__main__":
    main()
