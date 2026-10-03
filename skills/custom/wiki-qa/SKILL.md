---
name: wiki-qa
description: How to answer questions over the wiki corpus — the Document Graph navigation loop (folder TOC → document TOC → section content → hybrid search), image handling via stored descriptions and the budgeted query_image tool, and citation rules. Read this before answering any wiki question.
---

# Wiki QA — answering questions over the wiki corpus

The wiki is a Document Graph: `Folder → Document → MarkdownSection` in a Ladybug
database. Every document is split at headings; each section has an id
(`{markdown_hash}::{sequence}`), a one-line `description`, and (for substantial
sections) a paragraph `summary`. You answer ONLY from section text you actually read.

## Navigation loop

1. `get_folder_toc()` — list the documents (id, name, one-line description). Pick
   the document(s) most likely to hold the answer.
2. `get_document_toc(document_id, max_level=2)` — inspect the chosen document's
   section tree (ids, titles, descriptions). This is the map; do not skip it.
3. `get_section_content(section_ids)` — read the raw Markdown of ONLY the sections
   whose description matches the question. Use `start_line`/`max_lines` to slice
   very long sections or tables.
4. `search_sections(query, mode="hybrid")` — hybrid semantic + BM25 search over
   section titles, text, summaries and keywords. Use it when you do not know which
   document/section holds the answer; pass `document_id` to scope it. Use 2–3
   simple keywords rather than long phrases.
5. Iterate — read more sections or search with different terms — until you have
   grounded evidence, then answer.

Anti-patterns: never crawl every section; never answer from the TOC descriptions
alone; never invent a section id.

## Images

Images appear in section text as `<!-- Image: <file> (hash: ...) -->` comments,
usually followed by `<!-- Image Description: ... -->` and
`<!-- Image Keywords: ... -->` generated at ingestion time.

- Prefer the stored `Image Description` — it answers most "what does the figure
  show" questions without any VLM call.
- For questions needing exact visual details (axis values, layout, small labels),
  call `query_image(image, question)` on the ONE most relevant image. It is
  budgeted — max 3 calls per question. Ask a specific, self-contained question
  (e.g. "What value does the 2018 bar reach on the y-axis?"), not a keyword.

## Answering rules

- Cite every fact with its section id `[hash::sequence]` and the source filename.
- Answer directly: concise conclusion first, then supporting details and citations.
- If the corpus genuinely does not contain the answer, say so explicitly.
- Do not use `write_file`/`edit_file` — deliver the answer as your message.
