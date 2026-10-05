"""Wiki CLI commands — build and query a personal wiki over the Document Graph.

The single ``wiki`` command group wraps the genai-graph Document Graph stack with
wiki-friendly defaults (docling conversion, uncaptioned-image VLM descriptions,
hybrid vector + BM25 retrieval):

- ``wiki add``     — dispatch sources through the profile's ingest route table
  (docling conversion by default) and ingest them into the Document Graph, with
  LLM structure discovery, section summaries and image descriptions.
- ``wiki search``  — hybrid (semantic + BM25) search across ingested sections.
- ``wiki ask``     — deep agent that navigates the Document Graph to answer
  questions; one-shot, interactive REPL (``--chat``) or Textual TUI (``--tui``).

Models are never hardcoded: LLMs, the VLM and the embeddings model resolve from
``config/docgraph.yaml`` (``docgraph_profiles.<profile>.llms`` / ``embeddings``)
and ``config/app_conf.yaml`` tags, with CLI flags overriding.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from genai_tk.cli.base import CliTopCommand

console = Console()


def _load_docgraph_profile(profile: str) -> dict[str, Any]:
    """Return the ``docgraph_profiles.<profile>`` mapping from config/docgraph.yaml."""
    from genai_graph.bench.config import load_raw_docgraph_yaml

    raw = load_raw_docgraph_yaml()
    profiles = raw.get("docgraph_profiles", {}) or {}
    data = profiles.get(profile)
    if data is None:
        console.print(f"[red]DocGraph profile '{profile}' not found in config/docgraph.yaml.[/red]")
        raise typer.Exit(1)
    return data


def _resolve_db_path(db_path: str | None, profile_data: dict[str, Any], profile: str) -> str:
    """Resolve the Ladybug database path: explicit flag, then the docgraph profile."""
    if db_path:
        return db_path
    paths = profile_data.get("paths") or {}
    kg_db = paths.get("kg_db")
    if kg_db:
        return str(kg_db)
    console.print(f"[red]No database path: pass --db or set docgraph_profiles.{profile}.paths.kg_db in config/docgraph.yaml.[/red]")
    raise typer.Exit(1)


def _resolve_llm(llm: str | None, profile_data: dict[str, Any]) -> str | None:
    """Resolve the summary/structure LLM: explicit flag, then the profile's llms.summary."""
    if llm:
        return llm
    llms = profile_data.get("llms") or {}
    return llms.get("summary") or None


def _resolve_embeddings(embeddings: str | None, profile_data: dict[str, Any]) -> str | None:
    """Resolve the embeddings model: explicit flag, then the profile's ``embeddings`` key.

    The literal value ``none`` disables embeddings (vectorless graph, BM25 only).
    """
    if embeddings:
        return None if embeddings.lower() == "none" else embeddings
    return profile_data.get("embeddings") or None


class WikiCommands(CliTopCommand):
    """Build and query a wiki over the Document Graph."""

    description: str = "Build and query a wiki over the Document Graph"

    def get_description(self) -> tuple[str, str]:
        return "wiki", self.description

    def register_sub_commands(self, cli_app: typer.Typer) -> None:

        @cli_app.command("add")
        def add(
            sources: Annotated[
                list[str],
                typer.Argument(help="Directories, files, or .zip archives to add to the wiki (any markdownizer-supported format)."),
            ],
            profile: Annotated[
                str,
                typer.Option("--profile", "-p", help="DocGraph profile name (default: wiki)."),
            ] = "wiki",
            db_path: Annotated[
                str | None,
                typer.Option("--db", help="Path to the Ladybug database file (default: from the docgraph profile)."),
            ] = None,
            llm: Annotated[
                str | None,
                typer.Option(
                    "--llm",
                    "-m",
                    help="LLM id (name@provider) or tag for structure discovery + section summaries. "
                    "Defaults to docgraph_profiles.<profile>.llms.summary.",
                ),
            ] = None,
            embeddings: Annotated[
                str | None,
                typer.Option(
                    "--embeddings",
                    help="Embeddings model id enabling hybrid (vector + BM25) search. "
                    "Defaults to docgraph_profiles.<profile>.embeddings. Pass 'none' to "
                    "build a vectorless graph (BM25 search only, no embedding API calls).",
                ),
            ] = None,
            workers: Annotated[int, typer.Option("--workers", help="Parallelism for the LLM outline pre-pass.")] = 4,
            force: Annotated[
                str | None,
                typer.Option("--force", help="Force-invalidate caches from this stage onward (e.g. 'md', 'graph', 'all')."),
            ] = None,
        ) -> None:
            """Add documents to the wiki (ingest into the Document Graph).

            Sources are dispatched through the profile's ingest route table
            (docgraph_profiles.<profile>.ingest_routes; default 'wiki': docling
            conversion with uncaptioned-image VLM descriptions), then ingested as a
            Folder -> Document -> MarkdownSection graph with section descriptions and
            summaries. Re-adding unchanged files is a no-op (content-hash MERGE).

            Examples:
                wiki add ./docs
                wiki add handbook.pdf meeting_notes.docx
                wiki add ./papers --llm flash --embeddings qwen3_06b@deepinfra
            """
            from genai_tk.config_mgmt.file_patterns import resolve_config_path
            from genai_tk.utils.prefect_server import prefect_server
            from genai_tk.workflow.routing.dispatcher import ingest_dispatch_flow

            from genai_graph.orchestration.document_graph_flow import document_graph_flow

            # Flows run against the managed Prefect server (auto-started); this also
            # sets PREFECT_API_URL and bypasses corporate proxies for localhost,
            # avoiding flaky ephemeral-server health-check timeouts.
            server = prefect_server()
            server.ensure_running()
            server.configure_api_url()

            profile_data = _load_docgraph_profile(profile)
            resolved_db = _resolve_db_path(db_path, profile_data, profile)
            resolved_llm = _resolve_llm(llm, profile_data)
            resolved_embeddings = _resolve_embeddings(embeddings, profile_data)
            routes_name = profile_data.get("ingest_routes", "wiki")
            build = profile_data.get("build") or {}

            md_output_dir = str(Path(resolved_db).with_suffix("")) + "_markdown"

            per_source_dirs: list[str] = []
            for src in sources:
                stem = Path(resolve_config_path(src)).stem
                src_output_dir = str(Path(md_output_dir) / stem)
                console.print(f"[dim]Ingesting {src} -> {src_output_dir} (routes: {routes_name})[/dim]")
                ingest_dispatch_flow(
                    sources=[src],
                    md_output_dir=src_output_dir,
                    routes=routes_name,
                    force_stage=force,
                )
                per_source_dirs.append(src_output_dir)

            console.print(f"[dim]Ingesting Document Graph into {resolved_db} (llm={resolved_llm}, embeddings={resolved_embeddings})[/dim]")
            result = document_graph_flow(
                sources=per_source_dirs,
                db_path=resolved_db,
                force_stage=force,
                llm=resolved_llm,
                workers=workers,
                embeddings_id=resolved_embeddings,
                structure_strategy=build.get("structure_strategy", "auto"),
                generate_summaries=build.get("generate_summaries", True),
                summary_min_tokens=build.get("summary_min_tokens", 800),
                context_safety_ratio=build.get("context_safety_ratio", 0.9),
                fts=build.get("fts", True),
                chunk_size_tokens=build.get("chunk_size_tokens", 1500),
            )

            table = Table(title="Wiki — Add Result")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white")
            for key, label in (
                ("documents_processed", "Documents processed"),
                ("documents_skipped", "Skipped (unchanged)"),
                ("documents_failed", "Failed"),
                ("sections_created", "Sections created"),
                ("images_created", "Images created"),
                ("sections_summarized", "Sections summarized"),
            ):
                table.add_row(label, str(result.get(key, 0)))
            console.print(table)

        @cli_app.command("search")
        def search(
            query: Annotated[str, typer.Argument(help="Search query (keywords or a natural-language sentence).")],
            profile: Annotated[
                str,
                typer.Option("--profile", "-p", help="DocGraph profile name (default: wiki)."),
            ] = "wiki",
            db_path: Annotated[
                str | None,
                typer.Option("--db", help="Path to the Ladybug database file (default: from the docgraph profile)."),
            ] = None,
            limit: Annotated[int, typer.Option("--limit", "-l", help="Max number of matches.")] = 20,
            folder: Annotated[
                str | None,
                typer.Option("--folder", "-f", help="Restrict to this folder's subtree (hash, prefix, or name)."),
            ] = None,
            doc: Annotated[
                str | None,
                typer.Option("--doc", "--document", "-d", help="Restrict to this document (hash, prefix, filename, or path)."),
            ] = None,
            mode: Annotated[
                str,
                typer.Option(
                    "--mode",
                    help="Search mode: 'hybrid' (semantic + BM25, default), 'vector', 'bm25', or 'cypher'.",
                ),
            ] = "hybrid",
            embeddings: Annotated[
                str | None,
                typer.Option("--embeddings", help="Embeddings model for vector/hybrid search (default: from the docgraph profile)."),
            ] = None,
        ) -> None:
            """Search the wiki (hybrid semantic + BM25 by default).

            Examples:
                wiki search "operating expenses"
                wiki search "deadline for proposals" --doc handbook.pdf
                wiki search "renewable energy" --mode bm25
            """
            from genai_graph.kg.backend import KuzuBackend
            from genai_graph.kg.query.document_graph_tools import resolve_document_id, resolve_folder_id, search_sections

            profile_data = _load_docgraph_profile(profile)
            resolved_db = _resolve_db_path(db_path, profile_data, profile)
            resolved_embeddings = _resolve_embeddings(embeddings, profile_data)

            backend = KuzuBackend()
            backend.connect(resolved_db)

            folder_id = resolve_folder_id(backend, folder) if folder else None
            doc_id = resolve_document_id(backend, doc) if doc else None

            rows = search_sections(
                backend,
                query,
                limit=limit,
                folder_id=folder_id,
                document_id=doc_id,
                mode=mode,
                embeddings_id=resolved_embeddings,
            )
            if not rows:
                console.print(f"[yellow]No sections matched: {query!r}[/yellow]")
                return
            for r in rows:
                score_str = f", score: {r['score']}" if r.get("score") else ""
                desc_suffix = f" — {r['description']}" if r.get("description") else ""
                console.print(
                    f"- [{r['section_id']}] {r['title']} (line {r['line_start']}{score_str}){desc_suffix}"
                )
                if r.get("matched_chunk"):
                    console.print(f"    [dim]matched: {r['matched_chunk']}[/dim]")

        @cli_app.command("ask")
        def ask(
            query: Annotated[
                str | None,
                typer.Argument(help="Question to ask the wiki (omit with --chat/--tui for interactive mode)."),
            ] = None,
            profile: Annotated[
                str,
                typer.Option("--profile", "-p", help="Agent profile key (default: wiki)."),
            ] = "wiki",
            docgraph_profile: Annotated[
                str,
                typer.Option("--docgraph-profile", help="DocGraph profile name for db_path resolution (default: wiki)."),
            ] = "wiki",
            db_path: Annotated[
                str | None,
                typer.Option("--db", help="Path to the Ladybug database file (default: from the docgraph profile)."),
            ] = None,
            llm: Annotated[
                str | None,
                typer.Option("--llm", "-m", help="LLM id override (name@provider). Defaults to the profile's LLM."),
            ] = None,
            folder: Annotated[
                str | None,
                typer.Option("--folder", help="Folder to scope the agent to (hash, prefix, or name)."),
            ] = None,
            skill_dir: Annotated[
                list[str] | None,
                typer.Option("--skill-dir", help="Additional runtime skill directory (repeatable)."),
            ] = None,
            recursion_limit: Annotated[int, typer.Option("--recursion-limit", help="Max LangGraph steps per turn.")] = 160,
            chat: Annotated[bool, typer.Option("--chat", help="Interactive multi-turn REPL (memory enabled).")] = False,
            tui: Annotated[bool, typer.Option("--tui", help="Interactive Textual TUI chat (memory enabled).")] = False,
            trace: Annotated[bool, typer.Option("--trace", help="Print graph node trace lines.")] = False,
        ) -> None:
            """Ask the wiki a question — a deep agent navigates the Document Graph.

            Examples:
                wiki ask "What are the SLA response times?"
                wiki ask --chat                  # interactive REPL
                wiki ask --tui                   # interactive Textual TUI
                wiki ask "Summarize the onboarding process" --llm gpt_41@openai
            """
            from genai_tk.agents.harness.profiles import load_agent_profiles

            from genai_graph.agent import create_docgraph_agent
            from genai_graph.kg.query.document_graph_tools import DocumentGraphError

            profiles, _defaults, _default_key = load_agent_profiles()
            if profile not in profiles:
                console.print(f"[red]Agent profile {profile!r} not found. Available: {sorted(profiles)}[/red]")
                raise typer.Exit(1)
            agent_profile = profiles[profile]
            if hasattr(agent_profile, "recursion_limit"):
                agent_profile.recursion_limit = recursion_limit

            profile_data = _load_docgraph_profile(docgraph_profile)
            try:
                resolved_db_path = _resolve_db_path(db_path, profile_data, docgraph_profile)
            except typer.Exit:
                # Allow --chat/--tui sessions on a not-yet-created database file.
                if chat or tui:
                    resolved_db_path = str(Path(f"./data/kg/{docgraph_profile}.db"))
                else:
                    raise

            async def _run() -> None:
                from genai_tk.agents.harness.chat_repl import astream_turn, run_chat_repl

                try:
                    harness = create_docgraph_agent(
                        agent_profile,
                        llm=llm,
                        db_path=resolved_db_path,
                        docgraph_profile=docgraph_profile,
                        folder_id=folder,
                        extra_skill_dirs=skill_dir,
                    )
                except DocumentGraphError as exc:
                    console.print(f"[red]{exc}[/red]")
                    raise typer.Exit(1) from exc

                try:
                    if tui:
                        from wiki.tui import run_wiki_chat_tui

                        await run_wiki_chat_tui(harness)
                        return

                    if chat:
                        console.print(f"[cyan]Wiki agent ({profile}) — interactive mode. Type /quit to exit.[/cyan]\n")
                        await run_chat_repl(harness, initial_query=query, show_trace=trace)
                        return

                    if not query:
                        console.print("[red]A query is required in one-shot mode (or use --chat / --tui).[/red]")
                        raise typer.Exit(1)

                    label = llm or getattr(agent_profile, "llm", None) or "default"
                    console.print(f"[dim]Asking the wiki (llm={label})…[/dim]\n")
                    await astream_turn(harness, query, show_trace=trace, console=console)
                    console.print()
                finally:
                    await harness.aclose()

            try:
                asyncio.run(_run())
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted.[/yellow]")
