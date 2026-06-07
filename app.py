"""
app.py — Stage 5: Gradio interface for the UF Dining Unofficial Guide.

Wires the full pipeline:
    user query → retrieve() → generate_answer() → display answer + sources

Run:
    python app.py

Then open http://localhost:7860 in your browser.

First-time setup (if not done already):
    python ingest.py   # scrape + chunk
    python embed.py    # embed + store in chroma_db/
"""

import gradio as gr
from embed import retrieve
from generate import generate_answer


# ── Core pipeline function ───────────────────────────────────────────────────────
def answer_question(question: str) -> tuple[str, str]:
    """
    Called by Gradio on every submission.

    Returns:
        answer_text  — the grounded LLM answer
        sources_text — formatted source list (programmatic, not LLM-generated)
    """
    if not question.strip():
        return "Please enter a question.", ""

    # Stage 3: retrieve top-5 chunks
    chunks = retrieve(question)

    # Stage 4: generate grounded answer
    result = generate_answer(question, chunks)

    # Format sources for display
    sources_md = "\n".join(
        f"- [{s['title']}]({s['url']})  *(score: {s['score']})*"
        for s in result["sources"]
    )

    return result["answer"], sources_md


# ── Example questions (from planning.md §Evaluation Plan) ───────────────────────
EXAMPLES = [
    ["What happens to unused flex dollars at the end of the spring semester at UF?"],
    ["What do students say about vegan options at Broward and Gator Corner?"],
    ["How often can a student swipe into a UF dining hall in a single day?"],
    ["What is Cravings Campus Kitchen and how does it compare to the main dining halls?"],
    ["What was the student complaint that led to the creation of Bite Club?"],
]


# ── Gradio UI ────────────────────────────────────────────────────────────────────
with gr.Blocks(title="UF Dining Unofficial Guide") as demo:
    gr.Markdown(
        """
        # 🐊 UF Dining Unofficial Guide
        Ask anything about University of Florida campus dining — meal plans,
        dining halls, vegan options, swipe policies, and more.
        Answers are grounded in student reviews and official UF sources.
        """
    )

    with gr.Row():
        with gr.Column(scale=2):
            question_box = gr.Textbox(
                label="Your question",
                placeholder="e.g. What happens to unused flex dollars?",
                lines=2,
            )
            submit_btn = gr.Button("Ask", variant="primary")

        with gr.Column(scale=3):
            answer_box = gr.Textbox(
                label="Answer",
                lines=6,
                interactive=False,
            )
            sources_box = gr.Markdown(label="Sources")

    gr.Examples(
        examples=EXAMPLES,
        inputs=question_box,
        label="Try one of your eval questions",
    )

    submit_btn.click(
        fn=answer_question,
        inputs=question_box,
        outputs=[answer_box, sources_box],
    )
    question_box.submit(        # also fires on Enter key
        fn=answer_question,
        inputs=question_box,
        outputs=[answer_box, sources_box],
    )

if __name__ == "__main__":
    demo.launch()
