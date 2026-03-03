"""
Thia-Lite TUI — Claude Code Clone (Textual)
=============================================
Full-featured terminal UI with:
- Left sidebar: conversation list + tool catalog
- Center: chat with markdown rendering
- Bottom: status bar (Ollama, model, RAM)
- Keybindings: Ctrl+N (new chat), Ctrl+T (tools), Ctrl+Q (quit)
"""

import asyncio
import json
import logging
import os
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import (
    Footer, Header, Input, Label, ListItem, ListView,
    Markdown, RichLog, Static, Button, TabbedContent, TabPane,
)

logger = logging.getLogger(__name__)


# ─── Constants ────────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: $surface;
}

#app-grid {
    layout: grid;
    grid-size: 3 1;
    grid-columns: 1fr 3fr 1fr;
    grid-gutter: 1;
    height: 100%;
}

#sidebar {
    width: 100%;
    background: $panel;
    border: solid $primary;
    padding: 1;
}

#chat-area {
    width: 100%;
    background: $surface;
}

#tools-panel {
    width: 100%;
    background: $panel;
    border: solid $accent;
    padding: 1;
}

#chat-log {
    height: 1fr;
    border: solid $primary;
    padding: 1;
    background: $surface;
    scrollbar-gutter: stable;
}

#input-area {
    dock: bottom;
    height: 3;
    padding: 0 1;
}

#chat-input {
    width: 100%;
}

#status-bar {
    dock: bottom;
    height: 1;
    background: $primary;
    color: $text;
    padding: 0 1;
}

.section-title {
    text-style: bold;
    color: $primary;
    padding: 0 0 1 0;
}

.conversation-item {
    padding: 0 1;
    height: 2;
}

.conversation-item:hover {
    background: $primary 20%;
}

.tool-item {
    padding: 0 1;
    height: 1;
    color: $accent;
}

.user-message {
    color: $text;
    padding: 0 0 1 0;
    text-style: bold;
}

.assistant-message {
    padding: 0 0 1 0;
}

.tool-call-msg {
    color: $accent;
    text-style: italic;
    padding: 0 0 0 2;
}

.thinking-msg {
    color: $warning;
    text-style: italic dim;
}
"""


# ─── Thia TUI App ────────────────────────────────────────────────────────────

class ThiaLiteApp(App):
    """The Thia-Lite TUI Application — Claude Code style."""

    TITLE = "🌟 Thia-Lite"
    SUB_TITLE = "AI-Native Astrological Prediction Assistant"
    CSS = CSS

    BINDINGS = [
        Binding("ctrl+n", "new_chat", "New Chat", show=True),
        Binding("ctrl+t", "toggle_tools", "Tools", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    is_processing = reactive(False)

    def __init__(self):
        super().__init__()
        self.conversation_manager = None
        self._tools_visible = True

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="app-grid"):
            # Left sidebar - conversations
            with Vertical(id="sidebar"):
                yield Static("💬 Conversations", classes="section-title")
                yield ListView(id="conv-list")
                yield Button("+ New Chat", id="new-chat-btn", variant="primary")

            # Center - chat
            with Vertical(id="chat-area"):
                yield ScrollableContainer(
                    RichLog(id="chat-log", highlight=True, markup=True, wrap=True),
                )
                with Horizontal(id="input-area"):
                    yield Input(
                        placeholder="Ask about astrology, or type /help...",
                        id="chat-input",
                    )

            # Right sidebar - tools
            with Vertical(id="tools-panel"):
                yield Static("⚡ Tools", classes="section-title")
                yield ListView(id="tools-list")

        yield Static("", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize on mount."""
        from thia_lite.llm.conversation import ConversationManager
        from thia_lite.engines.astrology import register_astrology_tools
        from thia_lite.llm.tool_executor import get_tool_names

        try:
            register_astrology_tools()
        except Exception as e:
            logger.warning(f"Could not register tools: {e}")

        self.conversation_manager = ConversationManager()
        self.conversation_manager.new_conversation()

        # Set up tool execution callbacks
        executor = self.conversation_manager.executor

        def on_tool_call(name, args):
            log = self.query_one("#chat-log", RichLog)
            args_str = ", ".join(f"{k}={str(v)[:30]}" for k, v in args.items())
            log.write(f"  ⚡ {name}({args_str})")

        def on_tool_result(name, result):
            log = self.query_one("#chat-log", RichLog)
            if isinstance(result, dict) and "error" in result:
                log.write(f"  ✗ {name}: {result['error']}")
            else:
                log.write(f"  ✓ {name}")

        executor.on_tool_call(on_tool_call)
        executor.on_tool_result(on_tool_result)

        # Populate tool list
        tools_list = self.query_one("#tools-list", ListView)
        for name in sorted(get_tool_names()):
            await tools_list.append(ListItem(Label(name), classes="tool-item"))

        # Update status bar
        await self._update_status()

        # Welcome message
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold cyan]🌟 Welcome to Thia-Lite[/]")
        log.write("[dim]AI-Native Astrological Prediction Assistant[/]")
        log.write("[dim]Powered by Qwen 3.5 + Swiss Ephemeris[/]")
        log.write("")
        log.write("[dim]Type a message, or /help for commands.[/]")
        log.write("─" * 50)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        if event.input.id != "chat-input":
            return

        text = event.value.strip()
        if not text:
            return

        event.input.value = ""
        log = self.query_one("#chat-log", RichLog)

        # Slash commands
        if text.startswith("/"):
            await self._handle_slash_command(text, log)
            return

        # Display user message
        log.write(f"\n[bold blue]> {text}[/]")

        # Process with LLM
        self.is_processing = True
        await self._update_status("Thinking...")

        try:
            result = await self.conversation_manager.send_message(text)

            # Display response
            log.write("")
            if result.get("content"):
                # Render as plain text with markup for TUI
                log.write(result["content"])

            # Stats
            stats = []
            if result.get("tool_calls_made"):
                stats.append(f"{len(result['tool_calls_made'])} tools")
            stats.append(f"{result.get('duration_ms', 0)}ms")
            log.write(f"\n[dim]{'  •  '.join(stats)}[/]")
            log.write("─" * 50)

        except Exception as e:
            log.write(f"\n[red]Error: {e}[/]")
        finally:
            self.is_processing = False
            await self._update_status()

    async def _handle_slash_command(self, cmd: str, log: RichLog):
        """Handle slash commands."""
        from thia_lite.llm.tool_executor import get_tool_names

        parts = cmd.split()
        command = parts[0].lower()

        if command == "/help":
            log.write("\n[bold]Commands:[/]")
            log.write("  /help          Show this help")
            log.write("  /tools         List tools")
            log.write("  /new           New conversation")
            log.write("  /clear         Clear chat")
            log.write("  /config        Show config")

        elif command == "/tools":
            log.write("\n[bold magenta]Available Tools:[/]")
            for name in sorted(get_tool_names()):
                log.write(f"  ⚡ {name}")

        elif command == "/new":
            self.conversation_manager.new_conversation()
            log.clear()
            log.write("[green]Started new conversation[/]")

        elif command == "/clear":
            log.clear()

        elif command == "/config":
            from thia_lite.config import get_settings
            s = get_settings()
            log.write(f"\n[bold]Config:[/]")
            log.write(f"  Model: {s.ollama.model}")
            log.write(f"  Ollama: {s.ollama.host}")
            log.write(f"  Rules: {', '.join(s.rule_sources)}")

        else:
            log.write(f"[yellow]Unknown command: {command}[/]")

    async def _update_status(self, extra: str = ""):
        """Update the status bar."""
        try:
            bar = self.query_one("#status-bar", Static)
            from thia_lite.config import get_settings
            s = get_settings()

            status = f"Model: {s.ollama.model}  •  Rules: Lilly + Ptolemy"
            if extra:
                status += f"  •  {extra}"
            bar.update(status)
        except NoMatches:
            pass

    def action_new_chat(self) -> None:
        """Start a new chat."""
        if self.conversation_manager:
            self.conversation_manager.new_conversation()
            try:
                log = self.query_one("#chat-log", RichLog)
                log.clear()
                log.write("[green]Started new conversation[/]")
            except NoMatches:
                pass

    def action_toggle_tools(self) -> None:
        """Toggle tools panel visibility."""
        try:
            panel = self.query_one("#tools-panel")
            self._tools_visible = not self._tools_visible
            panel.display = self._tools_visible
        except NoMatches:
            pass


# ─── Entry Point ──────────────────────────────────────────────────────────────

def run_tui():
    """Launch the TUI application."""
    app = ThiaLiteApp()
    app.run()


if __name__ == "__main__":
    run_tui()
