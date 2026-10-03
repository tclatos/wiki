"""Interactive Textual chat TUI for the wiki agent.

Streams canonical harness events (``TokenEvent``, ``ToolCallEvent``, …) into a
chat transcript with a tool-call log, mirroring the shared ``chat_repl`` event
model. Launched with ``wiki ask --tui``.
"""

from __future__ import annotations

import uuid

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Input, Markdown, RichLog

from genai_tk.agents.harness import (
    ClarificationEvent,
    EndEvent,
    ErrorEvent,
    NodeEvent,
    ThinkingEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from genai_tk.agents.harness.base import BaseHarness


class WikiChatApp(App[None]):
    """Chat TUI over any :class:`BaseHarness` — streaming answers + tool log."""

    CSS = """
    #chat {
        height: 1fr;
    }
    #transcript {
        height: 2fr;
        padding: 0 1;
    }
    #tool_log {
        height: 1fr;
        border-top: solid $accent;
        padding: 0 1;
    }
    #prompt {
        dock: bottom;
    }
    """

    BINDINGS = [("ctrl+q", "quit", "Quit")]
    TITLE = "Wiki Chat"

    def __init__(self, harness: BaseHarness) -> None:
        super().__init__()
        self._harness = harness
        self._thread_id = uuid.uuid4().hex
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="chat"):
            with VerticalScroll(id="transcript"):
                yield Markdown("", id="answer")
            yield RichLog(id="tool_log", markup=True, wrap=True, highlight=False)
        yield Input(placeholder="Ask the wiki… (/quit to exit)", id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#prompt", Input).focus()

    @on(Input.Submitted)
    async def _on_submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.clear()
        if not text or self._busy:
            return
        if text in ("/quit", "/exit", "/q"):
            self.exit()
            return
        if text == "/clear":
            self._thread_id = uuid.uuid4().hex
            self.query_one("#answer", Markdown).update("")
            self.query_one("#tool_log", RichLog).clear()
            return

        self._busy = True
        transcript = self.query_one("#transcript", VerticalScroll)
        transcript.mount(Markdown(f"**You:** {text}"))
        answer = Markdown("", classes="assistant")
        await transcript.mount(answer)
        transcript.scroll_end(animate=False)

        parts: list[str] = []
        tool_log = self.query_one("#tool_log", RichLog)
        try:
            async for event_ in self._harness.astream(text, thread_id=self._thread_id):
                if isinstance(event_, TokenEvent):
                    parts.append(event_.text)
                    answer.update("".join(parts))
                    transcript.scroll_end(animate=False)
                elif isinstance(event_, ThinkingEvent):
                    tool_log.write(f"[dim italic]{event_.text}[/dim italic]")
                elif isinstance(event_, ToolCallEvent):
                    tool_log.write(f"[cyan]→ {event_.tool_name}({event_.args})[/cyan]")
                elif isinstance(event_, ToolResultEvent):
                    content = (event_.content or "")[:200]
                    tool_log.write(f"[cyan]← {content}[/cyan]")
                elif isinstance(event_, NodeEvent):
                    tool_log.write(f"[dim]node: {event_.node}[/dim]")
                elif isinstance(event_, ClarificationEvent):
                    parts.append(event_.question)
                    answer.update("".join(parts))
                elif isinstance(event_, ErrorEvent):
                    tool_log.write(f"[red]error: {event_.message}[/red]")
                elif isinstance(event_, EndEvent):
                    pass
        finally:
            self._busy = False
            transcript.scroll_end(animate=False)


async def run_wiki_chat_tui(harness: BaseHarness) -> None:
    """Run the wiki chat TUI against *harness* (multi-turn, one thread)."""
    ensure_ready = getattr(harness, "ensure_ready", None)
    if callable(ensure_ready):
        await ensure_ready()
    app = WikiChatApp(harness)
    await app.run_async()
