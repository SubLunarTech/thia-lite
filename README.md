# 🌟 Thia-Lite

**AI-Native Astrological Prediction Assistant** — a lightweight, local-first clone of [thia-libre](https://github.com/thia-libre/thia-libre) that runs on 8GB RAM with no Docker required.

Powered by **Ollama (Qwen 3.5)** + **Swiss Ephemeris** + **multi-source traditional rules RAG**.

## Quick Start

```bash
# One-command install
bash install.sh

# Interactive CLI (Claude Code style)
./thia-lite chat

# Terminal UI
./thia-lite-tui

# Health check
./thia-lite health
```

## Features

### 🔭 Full Astrology Engine
All 175+ tools from thia-libre's Swiss Ephemeris engine:
- Natal charts, synastry, composite
- Transits, solar/lunar returns
- Profections, firdaria, zodiacal releasing
- Dignities, sect analysis, antiscia, midpoints
- Eclipses, planetary hours, electional windows
- Fixed stars, Astro*Carto*Graphy, and more

### 🤖 Local AI
- **Qwen 3.5 9B** (or 4B for lower RAM) via Ollama
- Full tool calling — the AI invokes astrology tools automatically
- Conversation memory with semantic search
- No data leaves your machine

### 📡 MCP Protocol
- **MCP Server**: Expose tools to Claude Desktop, Pi agent, etc.
- **MCP Client**: Connect to thia-libre and other MCP servers
- Extensible via `~/.thia-lite/mcp_servers.json`

### 📚 Traditional Rules (RAG)
- William Lilly — *Christian Astrology* (1647)
- Ptolemy — *Tetrabiblos* (2nd century CE)
- Picatrix — *Ghayat al-Hakim* (public-domain source pipeline)
- Firmicus Maternus — *Mathesis*
- Vettius Valens — *Anthologies* (public-domain source pipeline)
- All public domain, loaded from `thia_lite/rules/*_rules_data.json` and searchable via `astrology_rules_rag_search`

Current corpus counts (local build):
- Lilly: 2785
- Ptolemy: 1068
- Picatrix: 288
- Firmicus: 216
- Valens: 2415
- Total: 6772

## Interfaces

| Interface | Command | Style |
|-----------|---------|-------|
| **CLI** | `./thia-lite chat` | Claude Code |
| **TUI** | `./thia-lite-tui` | Claude Code (Textual) |
| **Desktop** | *Coming soon* | Claude Desktop (Tauri) |
| **MCP Server** | `./thia-lite serve` | For Claude Desktop / Pi |

## Architecture

```
thia-lite
├── thia_lite/
│   ├── cli.py              # Claude Code-style CLI
│   ├── tui.py              # Claude Code-style TUI
│   ├── db.py               # SQLite (replaces 4 databases)
│   ├── config.py           # Configuration
│   ├── engines/
│   │   └── astrology.py    # Swiss Ephemeris (full port)
│   ├── llm/
│   │   ├── client.py
│   │   ├── tool_executor.py
│   │   └── conversation.py
│   ├── mcp/
│   │   ├── server.py       # MCP server (stdio/HTTP)
│   │   └── client.py       # MCP client
│   └── rules/
│       ├── lilly_rules_data.json
│       ├── ptolemy_rules_data.json
│       ├── picatrix_rules_data.json
│       ├── firmicus_rules_data.json
│       └── valens_rules_data.json
└── install.sh              # One-command installer
```

## Configuration

Edit `~/.thia-lite/config.toml`:

```toml
[llm]
provider = "ollama"
host = "http://localhost:11434"
model = "qwen3.5:9b"
temperature = 0.3

[mcp]
server_mode = "stdio"
server_port = 8443
```

Quick rules verification:
```bash
cd /home/opc/thia-lite
python3 -c "from thia_lite.rules import get_rules_stats; print(get_rules_stats())"
```

## Claude Desktop Integration

Add to your Claude Desktop MCP config:

```json
{
    "mcpServers": {
        "thia-lite": {
            "command": "/path/to/thia-lite/.venv/bin/python",
            "args": ["-m", "thia_lite", "serve", "--mode", "stdio"]
        }
    }
}
```

## Requirements

- Python 3.11+
- 8GB RAM (6GB minimum with smaller model)
- ~2GB disk (model + ephemeris data)

## License

GPL-3.0-or-later
