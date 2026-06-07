# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->

---
I choose the campus dining domain at the University of Florida. This domain is hard to find as information changes frequently as new plans are added and removed. I am able to mix personal experiences with all the information a user needs. This information is valuable because many students make the mistake of choosing a meal plan without considering other options, they have negatives that many overlook when only looking into the universities description.

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
| 1 | Business Services at University of Florida | Student mean plan terms and conditions, official rules, swipe limits, grace periods, etc| https://businessservices.ufl.edu/2025-2026-terms-conditions/ |
| 2 | Florida Fresh Dining| Shows new technologies and food spots around campus. Main points include variety, a better food and service experience | https://businessservices.ufl.edu/2022/10/10/florida-fresh-dining-introduces-new-food-concepts-new-technology-and-mobile-ordering-at-uf/ |
| 3 | Business Services at Universiy of Florida | Food Service Master Plan, independent audit of all 45 UF dining locations | https://businessservices.ufl.edu/wp-content/uploads/2020/01/Food-Svcs-Master-Plan-Report_Final_December-2019.pdf|
| 4 | Florida Alligator | A personal look on the UF vegan dining experience | https://www.alligator.org/article/2024/01/uf-vegan-experience |
| 5 | Spoon University | Student review over UF latest dining hall | https://spoonuniversity.com/school/ufl/reviewing-the-new-dining-hall/ |
| 6 | HerCampus UFL | A personal look on living with dietary restrictions in college, what options there are | https://www.hercampus.com/school/ufl/living-dietary-restrictions-college/ |
| 7 | University of Florida | Overview of the dining program at the University of Florida |  https://businessservices.ufl.edu/services/dining/ |
| 8 | GatorCare UF | Options about every option open on campus and information| https://ufh-gatorcare.sites.medinfo.ufl.edu/files/2015/09/Campus-Food-Resources-V5.pdf |
| 9 | Prked | A guide to choosing the best meal plan for your budget | https://prked.com/post/guide-to-uf-meal-plans-2024-2025 |
| 10 | Florida Allgiator | Bite Club, a new student meal plan altnerative | https://www.alligator.org/article/2024/09/what-to-know-about-a-new-student-meal-plan-alternative |

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:** My chunk size was 300 tokens and this fit my documents as almost all of my sources are short-to-medium form, and information tends to live in 2-4 sentence chunks. 300 Tokens captures a complete through without pulling in unrelated content from the same page. I chose an overlap size of 50 otkens to ensure a sentence overlaps a chunk boundary.

**Overlap:** 50 tokens, I used overlap to ensure context was not being lost in between chunks.

**Why these choices fit your documents:** Preprocessing included HTML entity decoding, whitespace noramlization, page number and seperator removal, boilerplate stripping, and HTML tag removal. Some things i failed to consider are stopword removal which can hurt semantic search ad deduplication of near-identifical chunks across sources which was more common then I expected.

**Final chunk count:** 368

---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:** all-MiniLM-L6-v2 via sentence-transformers, this model runs locally with no API key, has no rate limits and is fast enough for this use case since we are only embeding 300ish chunks. It was trained on general web text which matches our domain well.

**Production tradeoff reflection:** For a real-world use case I would consider accuracy on domain-specific text when it comes to picking a different model. Using a model fine-tuned on university text would outperform a general-purpose model on queries aout meal plans and dining policies. I would also consider latency, local models are CPU bound and luckily I have a good computer but it cannot be said if the document size and vector database expands that the same speed will be kept. API-hosted models offload computer but add around 100-300ms per call. Lastly, multilingual support would be a great feature to implement and would require another model.

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:** The system enforces grounding by having specific keywords that construct the LLM to only use information in the required documents.

**How source attribution is surfaced in the response:** The system prompt in "generate.py" uses this exact instruction "Answer the user's question using ONLY the information in the provided documents. Do not use any outside knowledge, general assumptions, or information not present in the documents below. If the documents do not contain enough information to answer the question, respond with exactly: 'I don't have enough information on that.'" The words ONLY and "do not use any outside knowledge" are load-bearing meaning they prohibit the model from drawing on training data. 

Structurally, two mechanisms help enforce grounding, these include low temperature of 0.2 which keeps the model closer to the retrieved text and reduces creative deviation. Second, source attribution, sources are appended after generation so the LLM never decides what to cite and attribtuion cannot be hallucinated. If the model says it doesnt have enough information, no sources are listed because no chunks were relevant enough (<0.5 score).

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | What happens to unused flex dollars at the end of the spring semester at UF? | They expire and are forfeited — flex rolls over fall-to-spring but all unused flex is lost at end of spring. | Any flex dollars remaining at the end of the spring semester are forfeited and will not roll over to the following academic year. |  0.40 - Relevant | Accurate |
| 2 | What do UF students say about vegan options at Broward and Gator Corner dining halls? | Options exist but are limited; campus dietitian acknowledged gaps and added tofu scramble and lentil soup. | UF students say that Broward has better vegan options, with a clearly marked vegan station and multiple hot options, while Gator Corner has less prominent vegan signage and limited options. Students also mention that the variety of vegan options is limited and availability is better earlier in the day. Some students supplement their dining hall meals with groceries due to the limited options. | 0.24 - Relevant | Great - Accurate |
| 3 | How often can a student swipe into a UF dining hall within a single day? | Once every 45 minutes per swipe, at either The Eatery at Broward Hall or the Food Hall at Gator Corner. | A student can enter The Eatery at Broward Hall or the Food Hall at Gator Corner once every 45 minutes per location. The 45-minute timer resets independently at each hall. | 0.32 - Relevant | Good |
| 4 | What is Cravings Campus Kitchen and how does it compare to Broward and Gator Corner? | It's UF's newest dining hall at the Racquet Club, reviewed as higher quality than the two main buffet-style halls, but with long lines. | I don't have enough information on that. | Off-target | Accurate |
| 5 | What was the student complaint that led to the creation of the Bite Club meal plan alternative? | Students felt locked into expensive UF meal plans with unused meals they couldn't roll over, and no option to eat at off-campus restaurants. | The student complaints that led to the creation of the Bite Club meal plan alternative were: unused meal swipes at the end of each week, the inability to use meal plan currency at off-campus restaurants, and the feeling of being locked into a high-cost plan with no flexibility. | Relevant - 0.26 | Accurate |

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:** "Best spots to eat on campus"

**What the system returned:** I don't have enough information on that.

**Root cause (tied to a specific pipeline stage):**  Retrieval, no relevant source.

**What you would change to fix it:** I would add a source based on user experiences that describe the best food spots to eat. There is not enough user subjective articles for questions like this, but framing the question differently  ("Tell me the top on campus food spots") answers the question based on 1 article.

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:** Having everything written down before writing any code made it a lot easier to start implementation. When it came time to write chunk_text there were no decisions to make mid-code which also made it easier to verify output was correct.

**One way your implementation diverged from the spec, and why:** In the architecture diagram, I specified using Claude API for the generation stage but the actual implementation ued Groqs version since it was free and was just enough for this use case. This change didn't affect any other stage of change since its the last step and only depends on the retrieved chunks.

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI: The Chunking Strategy section from planning.md and the pipeline diagram image, specifying 300 tokens, 50 overlap, tiktoken cl100k_base encoding, and requests+BeautifulSoup for HTML sources with pdfplumber for the two PDF sources.
- *What it produced: Complete ingest.py with fetch_html(), fetch_pdf(), clean_text(), and chunk_text() using a sliding window token approach. It also added a local caching system that saves scraped documents to documents/ so sources don't need to be re-fetched on every run.
- *What I changed or overrode: The initial clean_text() was missing HTML entity decoding (&amp;, &nbsp;) which the assignment checklist explicitly required. I directed the AI to add html.unescape() and non-breaking space removal.

**Instance 2**

- *What I gave the AI: The Retrieval Approach section from planning.md (all-MiniLM-L6-v2, top-k=5) and the grounding and source attribution requirements from the assignment prompt.
- *What it produced: generate.py with a system prompt, context injection, and Groq API call, plus app.py with a Gradio interface and the five eval questions pre-loaded as examples.
- *What I changed or overrode: The initial version left source attribution to the LLM by asking it to cite sources in its response. I directed the AI to remove that and instead append sources programmatically from the chunk metadata after generation, so attribution could not be hallucinated. I also directed it to set temperature=0.2 explicitly so that it wouldnt creatively deviate from the sources.
