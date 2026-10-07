# Justfile for Wiki
# Run `just` to see available recipes.

# Default recipe — show help
default:
    @just --list

# ── Development ─────────────────────────────────────────────────────────────

# Install / sync dependencies
sync:
    uv sync

# Format code with ruff
fmt:
    uv run ruff format .

# Lint code with ruff
lint:
    uv run ruff check .
    uv run cli skills validate --all || true

# Format + lint
check: fmt lint

# Run tests
test:
    uv run pytest tests/ -v

# Run unit tests only
test-unit:
    uv run pytest tests/ -v

# ── Skills ───────────────────────────────────────────────────────────────────

# List all available skills
skills:
    uv run cli skills list

# Add a skill by name (bundled)
add-skill name:
    uv run cli skills add {{name}}

# Validate all skills
lint-skills:
    uv run cli skills validate --all

# ── Workflows & Prefect ─────────────────────────────────────────────────────

# List available workflows
workflows:
    uv run cli workflow list

# Open local Prefect dashboard
prefect-ui:
    uv run cli prefect ui

# ── Web Interface ────────────────────────────────────────────────────────────

# Launch Streamlit webapp (entry point discovered from genai-tk package)
webapp:
    entry=$(uv run python -c 'import pathlib, genai_tk; print(pathlib.Path(genai_tk.__file__).parent / "webapp/main/streamlit.py")') && uv run python -m streamlit run "$entry"

# ── Wiki Commands ────────────────────────────────────────────────────────────

# Ingest documents, URLs, or git repos into wiki
add sources:
    uv run cli wiki add {{sources}}

# Search the wiki with hybrid semantic + BM25 retrieval
search query:
    uv run cli wiki search "{{query}}"

# Ask the wiki a question with the deep agent
ask question:
    uv run cli wiki ask "{{question}}"

# Interactive deep agent REPL chat
ask-chat:
    uv run cli wiki ask --chat

# Launch agent chat
run:
    uv run cli wiki ask --chat

