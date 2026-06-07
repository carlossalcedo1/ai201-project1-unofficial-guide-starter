"""
test_retrieval.py — Retrieval evaluation for the UF Dining Unofficial Guide.

Tests 3 of the 5 evaluation queries from planning.md §Evaluation Plan against
the live ChromaDB collection. For each query, prints the top-5 chunks with
their distance scores and source URLs so you can judge relevance by eye.

Run AFTER embedding:
    python ingest.py          # scrape + chunk  (once)
    python embed.py           # embed + store   (once)
    python test_retrieval.py  # evaluate retrieval

What to look for:
- Score < 0.3  → strongly relevant, chunk should directly help answer the question
- Score 0.3–0.5 → loosely related, may contain partial information
- Score > 0.5  → likely off-topic for this query
- Are the top results from the sources you'd expect?
- Does the chunk text actually contain the answer?
"""

from embed import retrieve

# ── 3 eval queries from planning.md §Evaluation Plan ───────────────────────────
EVAL_QUERIES = [
    {
        "id": 1,
        "question": "What happens to unused flex dollars at the end of the spring semester at UF?",
        "expected": "They expire and are forfeited — flex rolls over fall-to-spring but all unused flex is lost at end of spring.",
        "expected_sources": ["UF Dining Terms & Conditions"],
    },
    {
        "id": 2,
        "question": "What do UF students say about vegan options at Broward and Gator Corner dining halls?",
        "expected": "Options exist but are limited; campus dietitian acknowledged gaps and added tofu scramble and lentil soup.",
        "expected_sources": ["Florida Alligator – UF Vegan", "HerCampus"],
    },
    {
        "id": 5,
        "question": "What was the student complaint that led to the creation of the Bite Club meal plan alternative?",
        "expected": "Students felt locked into expensive UF meal plans with unused meals they couldn't roll over, and no option to eat at off-campus restaurants.",
        "expected_sources": ["Florida Alligator – Bite Club"],
    },
]


def run_eval() -> None:
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  UF Dining Guide — Retrieval Evaluation                 ║")
    print("║  3 of 5 eval queries from planning.md                   ║")
    print("╚══════════════════════════════════════════════════════════╝")

    for q in EVAL_QUERIES:
        print(f"\n{'═'*65}")
        print(f"QUERY {q['id']}: {q['question']}")
        print(f"Expected answer: {q['expected']}")
        print(f"Expected source(s): {', '.join(q['expected_sources'])}")
        print(f"{'─'*65}")

        results = retrieve(q["question"])

        for i, r in enumerate(results, 1):
            relevance = (
                "✓ strong" if r["score"] < 0.3 else
                "~ partial" if r["score"] < 0.5 else
                "✗ weak"
            )
            print(f"\n  [{i}] score={r['score']}  {relevance}")
            print(f"       source : {r['source_title']}  (chunk #{r['chunk_index']})")
            print(f"       url    : {r['source_url']}")
            print(f"       text   : {r['text'][:350].strip()} ...")

        print()

    print("═"*65)
    print("Eval complete. Review scores and text above.")
    print("If top results score > 0.5 on a query, check that the")
    print("relevant source was scraped successfully (see documents/).")
    print("═"*65)


if __name__ == "__main__":
    run_eval()
