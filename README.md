# Wiki — a personal wiki over the genai-graph Document Graph

`wiki` is a complete example of building a domain agent on top of
[genai-tk](https://github.com/tclatos/genai-tk) +
[genai-graph](https://github.com/tclatos/genai-graph): a single CLI group that
turns a folder of documents (Markdown, PDF, DOCX, PPTX, …) into a navigable
**Document Graph**, then answers questions about it with a **deep agent** that
walks the graph — headings, sections, and hybrid search instead of chunk
fragmentation.

Built from scratch using only the toolkit's README, scaffolded skills and
library surface — the full story (including every failure along the way) is in
[genai-graph/docs/design/wiki-agent-scaffolding-retrospective.md](https://github.com/tclatos/genai-graph/blob/main/docs/design/wiki-agent-scaffolding-retrospective.md).

## What it does

| Command | What it does |
|---|---|
| `wiki add SOURCES...` | Markdownize sources (docling; uncaptioned images described by a VLM) and ingest the `Folder → Document → MarkdownSection` graph with section summaries and hybrid-search chunks. |
| `wiki search QUERY` | Section-level search: hybrid (vector + BM25), vector-only, or bm25-only, with `--folder` / `--doc` scoping. |
| `wiki ask [QUESTION]` | Deep agent navigates the graph to answer, with section-id citations. One-shot, `--chat` interactive REPL, or `--tui` full-screen Textual chat. |

All models (agent LLM, summary/structure LLM, image VLM, embeddings) resolve
from `config/docgraph.yaml` + `config/providers/llm.yaml` — nothing hardcoded.

## Quick Start

Requires Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
# 1. Clone and install
#    (--extra harnessing installs deepagents/deerflow/sandbox — required by `wiki ask`)
git clone https://github.com/tclatos/wiki.git && cd wiki
uv sync --extra harnessing

# 2. Configure credentials for your providers (openrouter, deepinfra, …)
#    in the environment or your secrets manager.

# 3. Seed the corpus and build the wiki
uv run cli wiki add data/sources

# 4. Use it
uv run cli wiki search "vacation days"
uv run cli wiki ask "How many vacation days do employees get?"
```

To create **your own** wiki project from scratch (rather than cloning this
one), follow the [genai-graph README quick
start](https://github.com/tclatos/genai-graph#quick-start) — `uv init`, add
both libraries, then `uv run cli init --name "My Wiki" --with-graph --extra
harnessing`.

## CLI Reference

### `wiki add` — ingest documents

```bash
uv run cli wiki add ./docs                       # a directory
uv run cli wiki add report.pdf notes.docx        # individual files
uv run cli wiki add ./archive.zip                # zip: each archive is a Folder

# Options
uv run cli wiki add ./docs --profile wiki        # docgraph profile (default: wiki)
uv run cli wiki add ./docs --embeddings none     # vectorless: BM25-only, no embedding API
uv run cli wiki add ./docs --llm fast --force md # override LLM tag, redo conversion
```

Re-adding unchanged files is a no-op (content-hash MERGE); `--force md|graph|all`
invalidates caches from a given stage.

### `wiki search` — find sections

```bash
uv run cli wiki search "expense reimbursement deadline"
uv run cli wiki search "revenue" --doc acme_report_2043.docx
uv run cli wiki search "on-call" --mode bm25      # no embeddings needed
uv run cli wiki search "SLA" --mode vector --limit 5
```

### `wiki ask` — deep agent Q&A

```bash
uv run cli wiki ask "What is the severity 1 reporting delay?"  # one-shot
uv run cli wiki ask --chat                          # prompt_toolkit REPL
uv run cli wiki ask --tui                           # Textual chat (streaming + tool log)
uv run cli wiki ask "Summarize headcount" --llm glm_5.3_Flash@openrouter
```

The agent orients with `get_folder_toc`, inspects `get_document_toc`, reads
`get_section_content`, uses `search_sections` for targeted lookup and
`query_image` for figures (max 3 calls/turn) — the vectorless agentic-RAG loop
described in the `wiki-qa` and `kg-docgraph-agent` skills. Answers cite section
ids like `[8a47ec55cbea7e96::1]`.

## Configuration

- **`config/docgraph.yaml`** — the `wiki` profile: docling markdownize profile,
  image description settings, section summaries, embeddings model, DB paths
  (`data/kg/wiki.db`).
- **`config/agents.yaml`** — the `wiki` deep agent profile: LLM, system prompt
  (navigation discipline + citation rules), middleware stack
  (empty-response retry, observation truncation, tool-call dedup,
  map-before-search, wrap-up), skill directories, recursion limit.
- **`config/providers/llm.yaml` / `embeddings.yaml`** — model registry.
  **Declare every model your profiles reference explicitly** — do not rely on
  the models.dev catalogue being fetchable (see below).
- **`skills/custom/wiki-qa/`** — the domain skill the agent reads for
  navigation and answering rules. Add your own use-case skills here.

## Firewalled / offline notes

Learned the hard way — see the [retrospective](https://github.com/tclatos/genai-graph/blob/main/docs/design/wiki-agent-scaffolding-retrospective.md) for details:

- **Corporate proxy intercepting localhost** breaks Prefect's API calls. The
  managed server is auto-started by `wiki add` (with the bypass applied
  in-process); if you run flows yourself, set `NO_PROXY=localhost,127.0.0.1`.
- **models.dev / LLM endpoints unreachable?** Startup degrades gracefully
  (warning + empty model index) — but then every model must be declared in
  `config/providers/llm.yaml`.
- **Embedding API unreachable?** `wiki add --embeddings none` builds a
  vectorless graph; `wiki search --mode bm25` still works.

## Development

```bash
just lint          # ruff + skills validate
just fmt / check   # format / format+lint
just skills        # list merged skills
just test          # pytest
just run           # default agent chat (generic profile)
```

The repo vendors the merged 4-tier skill tree
(`skills/{development,runtime,governance,custom}`), scaffolded by `cli init` —
extend `skills/custom/` for your domain.

## See also

- [genai-tk](https://github.com/tclatos/genai-tk) — the agent toolkit
  (harnesses, LLM registry, markdownizer, scaffolding).
- [genai-graph](https://github.com/tclatos/genai-graph) — the Document Graph,
  Cypher engine and `cli docgraph` stack.
- [Scaffolding retrospective](https://github.com/tclatos/genai-graph/blob/main/docs/design/wiki-agent-scaffolding-retrospective.md)
  — what broke while building this, and the improvement list it produced.