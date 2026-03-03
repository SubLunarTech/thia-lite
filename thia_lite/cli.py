"""
Thia-Lite CLI — Claude Code Clone
====================================
Interactive CLI that mirrors Claude Code's UX:
- Rich markdown rendering in terminal
- Tool call status indicators
- Streaming responses
- Slash commands (/help, /tool, /config, /clear)
- Command history
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich import box

# ─── Theme (Claude Code inspired) ────────────────────────────────────────────

THIA_THEME = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "tool": "bold magenta",
    "tool_result": "dim green",
    "thinking": "dim yellow italic",
    "user_prompt": "bold blue",
    "assistant": "white",
    "header": "bold cyan",
    "muted": "dim white",
})

console = Console(theme=THIA_THEME)
app = typer.Typer(
    name="thia-lite",
    help="🌟 Thia-Lite — AI-Native Astrological Prediction Assistant",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


# ─── Chat Command (Main Interactive Mode) ────────────────────────────────────

@app.command()
def chat(
    message: Optional[str] = typer.Argument(None, help="Initial message (or omit for interactive mode)"),
    conversation: Optional[str] = typer.Option(None, "--conversation", "-c", help="Resume conversation by ID"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override Ollama model"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug info"),
):
    """Start an interactive chat session (Claude Code style)."""
    from thia_lite.config import get_settings
    get_settings()
    
    level = logging.DEBUG if verbose else logging.WARNING
    logging.getLogger().setLevel(level)

    asyncio.run(_chat_loop(message, conversation, model))


async def _chat_loop(initial_message: Optional[str], conv_id: Optional[str], model: Optional[str]):
    """Main interactive chat loop."""
    from thia_lite.llm.conversation import ConversationManager
    from thia_lite.llm.client import get_llm_client
    from thia_lite.llm.tool_executor import get_tool_names

    # Initialize
    _register_all_tools()
    manager = ConversationManager()

    if model:
        get_llm_client().config.model = model

    # Check Ollama health
    client = get_llm_client()
    healthy = await client.is_healthy()
    if not healthy:
        console.print(Panel(
            "[error]Cannot connect to Ollama.[/error]\n\n"
            "Make sure Ollama is running:\n"
            "  [bold]ollama serve[/bold]\n\n"
            "Then pull the model:\n"
            "  [bold]ollama pull qwen3.5:4b[/bold]",
            title="⚠️  Connection Error",
            border_style="red",
        ))
        raise typer.Exit(1)

    model_ok = await client.is_model_available()
    if not model_ok:
        console.print(f"[warning]Model '{getattr(client.config, 'model', 'unknown')}' not found. Pulling...[/warning]")
        console.print(f"  Run: [bold]ollama pull {getattr(client.config, 'model', 'unknown')}[/bold]")
        raise typer.Exit(1)

    # Header
    _print_header(getattr(client.config, 'model', 'unknown'), len(get_tool_names()))

    # Load or create conversation
    if conv_id:
        messages = manager.load_conversation(conv_id)
        console.print(f"[muted]Resumed conversation {conv_id} ({len(messages)} messages)[/muted]")
    else:
        manager.new_conversation()

    # Handle initial message
    if initial_message:
        await _handle_user_input(manager, initial_message)

    # Interactive loop
    while True:
        try:
            console.print()
            user_input = Prompt.ask("[user_prompt]>[/user_prompt]")

            if not user_input.strip():
                continue

            # Slash commands
            if user_input.startswith("/"):
                should_continue = await _handle_slash_command(user_input, manager)
                if not should_continue:
                    break
                continue

            await _handle_user_input(manager, user_input)

        except (KeyboardInterrupt, EOFError):
            console.print("\n[muted]Goodbye! ✨[/muted]")
            break


async def _handle_user_input(manager, user_input: str):
    """Process user input and display response."""
    from thia_lite.llm.tool_executor import ToolExecutor

    # Set up callbacks for tool status display
    executor = manager.executor

    tool_count = 0

    def on_tool_call(name, args):
        nonlocal tool_count
        tool_count += 1
        args_str = ", ".join(f"{k}={_truncate(str(v), 40)}" for k, v in args.items())
        console.print(f"  [tool]⚡ {name}[/tool]([muted]{args_str}[/muted])")

    def on_tool_result(name, result):
        if isinstance(result, dict) and "error" in result:
            console.print(f"  [error]✗ {name}: {result['error']}[/error]")
        else:
            summary = _truncate(json.dumps(result, default=str), 80)
            console.print(f"  [tool_result]✓ {name}[/tool_result] [muted]{summary}[/muted]")

    def on_thinking(iteration, total):
        if iteration > 1:
            console.print(f"  [thinking]⏳ Thinking (step {iteration}/{total})...[/thinking]")

    executor.on_tool_call(on_tool_call)
    executor.on_tool_result(on_tool_result)
    executor.on_thinking(on_thinking)

    # Execute
    start = time.monotonic()
    result = await manager.send_message(user_input)
    elapsed = time.monotonic() - start

    # Display response
    console.print()
    if result["content"]:
        try:
            md = Markdown(result["content"])
            console.print(md)
        except Exception:
            console.print(result["content"])

    # Footer stats (Claude Code style)
    stats_parts = []
    if result.get("tool_calls_made"):
        stats_parts.append(f"{len(result['tool_calls_made'])} tool calls")
    stats_parts.append(f"{elapsed:.1f}s")
    console.print(f"[muted]{'  •  '.join(stats_parts)}[/muted]")


async def _handle_slash_command(cmd: str, manager) -> bool:
    """Handle slash commands. Returns False if should exit."""
    from thia_lite.llm.tool_executor import get_tool_names, _tool_registry

    parts = cmd.strip().split()
    command = parts[0].lower()

    if command in ("/quit", "/exit", "/q"):
        console.print("[muted]Goodbye! ✨[/muted]")
        return False

    elif command == "/help":
        console.print(Panel(
            "[bold]Commands:[/bold]\n"
            "  /help          Show this help\n"
            "  /tools         List available tools\n"
            "  /tool <name>   Show tool details\n"
            "  /history       Show conversation history\n"
            "  /new           Start new conversation\n"
            "  /conversations List recent conversations\n"
            "  /config        Show current config\n"
            "  /clear         Clear screen\n"
            "  /quit          Exit",
            title="Help",
            border_style="cyan",
        ))

    elif command == "/tools":
        table = Table(title="Available Tools", box=box.ROUNDED, border_style="magenta")
        table.add_column("Tool", style="bold")
        table.add_column("Description", style="dim")

        for name in sorted(get_tool_names()):
            desc = _tool_registry[name].get("description", "")[:60]
            table.add_row(name, desc)

        console.print(table)

    elif command == "/tool":
        if len(parts) < 2:
            console.print("[warning]Usage: /tool <name>[/warning]")
        else:
            tool_name = parts[1]
            tool_info = _tool_registry.get(tool_name)
            if tool_info:
                console.print(Panel(
                    f"[bold]{tool_info['name']}[/bold]\n\n"
                    f"{tool_info['description']}\n\n"
                    f"[bold]Parameters:[/bold]\n"
                    f"{json.dumps(tool_info['parameters'], indent=2)}",
                    title=f"Tool: {tool_name}",
                    border_style="magenta",
                ))
            else:
                console.print(f"[error]Unknown tool: {tool_name}[/error]")

    elif command == "/history":
        from thia_lite.db import get_db
        if manager.current_conversation_id:
            msgs = get_db().get_conversation_messages(manager.current_conversation_id, limit=20)
            for m in msgs:
                role_style = "user_prompt" if m["role"] == "user" else "assistant"
                content = _truncate(m["content"], 120)
                console.print(f"[{role_style}]{m['role']}:[/{role_style}] {content}")
        else:
            console.print("[muted]No active conversation[/muted]")

    elif command == "/new":
        manager.new_conversation()
        console.print("[success]Started new conversation[/success]")

    elif command == "/conversations":
        convs = manager.list_conversations(10)
        if convs:
            table = Table(box=box.ROUNDED, border_style="cyan")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Updated", style="muted")
            for c in convs:
                table.add_row(c["id"], c["title"], c.get("updated_at", ""))
            console.print(table)
        else:
            console.print("[muted]No conversations yet[/muted]")

    elif command == "/config":
        from thia_lite.config import get_settings
        s = get_settings()
        console.print(Panel(
            f"[bold]Model:[/bold] {s.ollama.model}\n"
            f"[bold]Ollama:[/bold] {s.ollama.host}\n"
            f"[bold]DB:[/bold] {s.db_path}\n"
            f"[bold]Rules:[/bold] {', '.join(s.rule_sources)}\n"
            f"[bold]Debug:[/bold] {s.debug}",
            title="Configuration",
            border_style="cyan",
        ))

    elif command == "/clear":
        console.clear()

    else:
        console.print(f"[warning]Unknown command: {command}. Type /help for help.[/warning]")

    return True


# ─── Tool Command (Direct Execution) ─────────────────────────────────────────

@app.command()
def tool(
    tool_name: str = typer.Argument(..., help="Tool name to execute"),
    args: Optional[str] = typer.Option(None, "--args", "-a", help="JSON arguments"),
    date: Optional[str] = typer.Option(None, "--date", help="Date (YYYY-MM-DD)"),
    time_str: Optional[str] = typer.Option(None, "--time", help="Time (HH:MM)"),
    lat: Optional[float] = typer.Option(None, "--lat", help="Latitude"),
    lon: Optional[float] = typer.Option(None, "--lon", help="Longitude"),
):
    """Execute a single tool directly."""
    _register_all_tools()

    from thia_lite.llm.tool_executor import _tool_handlers

    handler = _tool_handlers.get(tool_name)
    if not handler:
        console.print(f"[error]Unknown tool: {tool_name}[/error]")
        raise typer.Exit(1)

    # Build payload
    if args:
        payload = json.loads(args)
    else:
        payload = {}
        if date:
            payload["date"] = date
        if time_str:
            payload["time"] = time_str
        if lat is not None:
            payload["latitude"] = lat
        if lon is not None:
            payload["longitude"] = lon

    result = asyncio.run(_run_tool(tool_name, handler, payload))
    console.print_json(json.dumps(result, indent=2, default=str))


async def _run_tool(tool_name, handler, payload):
    result = handler(tool_name, payload)
    if asyncio.iscoroutine(result):
        result = await result
    return result


# ─── Serve Command (MCP Server) ──────────────────────────────────────────────

@app.command()
def serve(
    mode: str = typer.Option("stdio", "--mode", "-m", help="Server mode: stdio, http"),
    port: int = typer.Option(8443, "--port", "-p", help="HTTP port (for http mode)"),
):
    """Start as an MCP server (for Claude Desktop / Pi integration)."""
    _register_all_tools()
    console.print(f"[header]Starting MCP server in {mode} mode...[/header]")

    if mode == "stdio":
        from thia_lite.mcp.server import run_stdio_server
        asyncio.run(run_stdio_server())
    elif mode == "http":
        from thia_lite.mcp.server import run_http_server
        asyncio.run(run_http_server(port))
    else:
        console.print(f"[error]Unknown mode: {mode}[/error]")
        raise typer.Exit(1)


# ─── Health Command ──────────────────────────────────────────────────────────

@app.command()
def health():
    """Check system health (Ollama, database, tools)."""
    asyncio.run(_health_check())


async def _health_check():
    from thia_lite.llm.client import get_llm_client
    from thia_lite.db import get_db
    from thia_lite.config import get_settings

    settings = get_settings()
    client = get_llm_client()
    db = get_db()

    table = Table(title="Thia-Lite Health Check", box=box.ROUNDED, border_style="cyan")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    # LLM Provider
    healthy = await client.is_healthy()
    model_ok = await client.is_model_available() if healthy else False
    table.add_row(
        f"LLM ({client.provider})",
        "[green]✓[/green]" if healthy else "[red]✗[/red]",
        f"{getattr(client.config, 'host', 'Remote')}",
    )
    table.add_row(
        "Model",
        "[green]✓[/green]" if model_ok else "[red]✗[/red]",
        f"{getattr(client.config, 'model', 'unknown')}",
    )

    # Database
    try:
        stats = db.get_stats()
        table.add_row(
            "Database",
            "[green]✓[/green]",
            f"{settings.db_path} ({stats.get('memories', 0)} memories)",
        )
        table.add_row(
            "Vector Search",
            "[green]✓[/green]" if stats.get("vec_available") else "[yellow]⚠[/yellow]",
            "sqlite-vec" if stats.get("vec_available") else "Text search fallback",
        )
    except Exception as e:
        table.add_row("Database", "[red]✗[/red]", str(e))

    # Tools
    _register_all_tools()
    from thia_lite.llm.tool_executor import get_tool_names
    tool_count = len(get_tool_names())
    table.add_row(
        "Tools",
        "[green]✓[/green]" if tool_count > 0 else "[yellow]⚠[/yellow]",
        f"{tool_count} tools registered",
    )

    # Logging
    log_file = settings.config_dir / "logs" / "thia.log"
    table.add_row(
        "Logging",
        "[green]✓[/green]" if log_file.exists() else "[yellow]⚠[/yellow]",
        f"{log_file}",
    )

    console.print(table)


# ─── Config Command ──────────────────────────────────────────────────────────

@app.command("config")
def config_cmd(
    key: Optional[str] = typer.Argument(None, help="Config key (dot notation)"),
    value: Optional[str] = typer.Option(None, "--set", "-s", help="Value to set"),
):
    """View or set configuration."""
    from thia_lite.config import get_settings, save_config

    if key and value:
        save_config({key: value})
        console.print(f"[success]Set {key} = {value}[/success]")
    elif key:
        s = get_settings()
        # Navigate dotted key
        obj = s
        for part in key.split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                console.print(f"[error]Unknown key: {key}[/error]")
                return
        console.print(f"{key} = {obj}")
    else:
        s = get_settings()
        console.print(Panel(
            f"Model: {s.ollama.model}\n"
            f"Ollama: {s.ollama.host}\n"
            f"DB: {s.db_path}\n"
            f"Rules: {', '.join(s.rule_sources)}\n"
            f"MCP mode: {s.mcp.server_mode}\n"
            f"MCP port: {s.mcp.server_port}",
            title="Current Configuration",
            border_style="cyan",
        ))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _print_header(model: str, tool_count: int):
    """Print the Claude Code-style welcome header."""
    console.print()
    console.print(Panel(
        "[bold cyan]🌟 Thia-Lite[/bold cyan]\n"
        "[dim]AI-Native Astrological Prediction Assistant[/dim]\n\n"
        f"Model: [bold]{model}[/bold]  •  Tools: [bold]{tool_count}[/bold]  •  "
        f"Rules: [bold]Lilly + Ptolemy[/bold]\n\n"
        "[dim]Type your message, or /help for commands. Ctrl+C to exit.[/dim]",
        border_style="cyan",
        box=box.DOUBLE,
    ))


def _truncate(s: str, max_len: int = 80) -> str:
    """Truncate string with ellipsis."""
    return s[:max_len - 3] + "..." if len(s) > max_len else s


def _register_all_tools():
    """Register all available tools from engines."""
    from thia_lite.llm.tool_executor import register_memory_tools
    # Core astrology
    try:
        from thia_lite.engines.astrology import register_astrology_tools
        register_astrology_tools()
    except Exception as e:
        logger.warning(f"Could not register astrology tools: {e}")
    # Memory tools
    try:
        register_memory_tools()
    except Exception as e:
        logger.warning(f"Could not register memory tools: {e}")
    # Autonomy tools
    try:
        from thia_lite.engines.autonomy import register_autonomy_tools
        register_autonomy_tools()
    except Exception as e:
        logger.warning(f"Could not register autonomy tools: {e}")
    # Ported engines (fixed stars, profections, financial, vedic, timezone)
    try:
        from thia_lite.engines.ported_tools import register_ported_tools
        register_ported_tools()
    except Exception as e:
        logger.warning(f"Could not register ported tools: {e}")
    # Verification & correlation
    try:
        from thia_lite.engines.verification import register_verification_tools
        register_verification_tools()
    except Exception as e:
        logger.warning(f"Could not register verification tools: {e}")
    # Chart rendering
    try:
        from thia_lite.engines.chart_renderer import register_chart_tools
        register_chart_tools()
    except Exception as e:
        logger.warning(f"Could not register chart tools: {e}")


# ─── Entry Point ──────────────────────────────────────────────────────────────

@app.command("update")
def update_cmd(
    check_only: bool = typer.Option(False, "--check", help="Only check, don't update"),
):
    """Check for updates and self-update."""
    asyncio.run(_do_update(check_only))


async def _do_update(check_only: bool):
    from thia_lite import __version__
    from thia_lite.updater import check_for_updates, update_from_git, format_update_message

    console.print(f"[muted]Current version: v{__version__}[/muted]")
    console.print("[muted]Checking GitHub for updates...[/muted]")

    update = await check_for_updates(__version__)
    if update:
        console.print(format_update_message(update))
        if not check_only:
            console.print("\n[info]Updating...[/info]")
            success, msg = update_from_git()
            if success:
                console.print(f"[success]{msg}[/success]")
                console.print("[info]Restart thia-lite to use the new version.[/info]")
            else:
                console.print(f"[error]{msg}[/error]")
                if update.get("download_url"):
                    console.print(f"  Download manually: {update['download_url']}")
    else:
        console.print("[success]You're up to date![/success]")


@app.command("version")
def version():
    """Show version."""
    from thia_lite import __version__
    console.print(f"thia-lite v{__version__}")


def main():
    app()


if __name__ == "__main__":
    main()
