#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Thia-Lite Installer — One-Command Setup
# ─────────────────────────────────────────────────────────────────────────────
# Downloads and installs everything needed to run Thia-Lite:
# 1. Python 3.11+ check
# 2. Ollama (if not installed)
# 3. Qwen 3.5 model (auto-detect 9B or 4B based on RAM)
# 4. Pi agentic toolkit
# 5. Thia-Lite Python package
# 6. Swiss Ephemeris data
# 7. First-run configuration
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

info()  { echo -e "${CYAN}ℹ${NC}  $1"; }
ok()    { echo -e "${GREEN}✓${NC}  $1"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $1"; }
err()   { echo -e "${RED}✗${NC}  $1"; }

# ─── Banner ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${CYAN}"
echo "  ╔════════════════════════════════════════════╗"
echo "  ║  🌟 Thia-Lite Installer                   ║"
echo "  ║  AI-Native Astrological Prediction         ║"
echo "  ╚════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# ─── Check System Requirements ────────────────────────────────────────────────

info "Checking system requirements..."

# Python 3.11+
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        ok "Python $PY_VERSION found"
    else
        err "Python 3.11+ required (found $PY_VERSION)"
        echo "  Install: https://www.python.org/downloads/"
        exit 1
    fi
else
    err "Python 3 not found"
    echo "  Install: https://www.python.org/downloads/"
    exit 1
fi

# RAM check
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))

if [ "$TOTAL_RAM_GB" -ge 8 ]; then
    ok "RAM: ${TOTAL_RAM_GB}GB (sufficient)"
elif [ "$TOTAL_RAM_GB" -ge 6 ]; then
    warn "RAM: ${TOTAL_RAM_GB}GB (minimum — will use smaller model)"
else
    err "RAM: ${TOTAL_RAM_GB}GB (insufficient — 8GB recommended)"
    echo "  Thia-Lite requires at least 6GB RAM to run."
    exit 1
fi

# ─── Install Ollama ───────────────────────────────────────────────────────────

if command -v ollama &>/dev/null; then
    ok "Ollama already installed"
else
    info "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    ok "Ollama installed"
fi

# Start Ollama if not running
if ! pgrep -x "ollama" > /dev/null 2>&1; then
    info "Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 3
    ok "Ollama started"
fi

# ─── Pull Qwen Model (Auto-Detect Best Size) ─────────────────────────────────

# Choose model based on RAM
if [ "$TOTAL_RAM_GB" -ge 10 ]; then
    MODEL="qwen2.5:7b"
    info "Selecting Qwen 2.5 7B (best tool calling for your RAM)"
elif [ "$TOTAL_RAM_GB" -ge 8 ]; then
    MODEL="qwen2.5:7b"
    info "Selecting Qwen 2.5 7B (tight but workable on 8GB)"
else
    MODEL="qwen2.5:3b"
    info "Selecting Qwen 2.5 3B (smaller model for limited RAM)"
fi

# Check if model already pulled
if ollama list 2>/dev/null | grep -q "$(echo $MODEL | cut -d: -f1)"; then
    ok "Model $MODEL already available"
else
    info "Downloading $MODEL (this may take a few minutes)..."
    ollama pull "$MODEL"
    ok "Model $MODEL downloaded"
fi

# ─── Install Thia-Lite ────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THIA_DIR="${SCRIPT_DIR}"

info "Installing Thia-Lite..."

# Create virtual environment
if [ ! -d "$THIA_DIR/.venv" ]; then
    python3 -m venv "$THIA_DIR/.venv"
fi

# Activate and install
source "$THIA_DIR/.venv/bin/activate"
pip install --upgrade pip -q
pip install -e "$THIA_DIR" -q 2>&1 | tail -1

ok "Thia-Lite installed"

# ─── Install Pi Agentic Toolkit ───────────────────────────────────────────────

if command -v npm &>/dev/null; then
    if command -v pi &>/dev/null; then
        ok "Pi agent already installed"
    else
        info "Installing Pi agentic toolkit..."
        npm install -g @mariozechner/pi-coding-agent 2>/dev/null || warn "Pi install failed (optional)"
    fi

    # Configure Pi to use local Ollama
    PI_CONFIG_DIR="$HOME/.pi/agent"
    mkdir -p "$PI_CONFIG_DIR"

    cat > "$PI_CONFIG_DIR/models.json" << EOF
{
    "providers": {
        "ollama": {
            "baseUrl": "http://localhost:11434/v1",
            "api": "openai-completions",
            "apiKey": "ollama",
            "models": [{"id": "$MODEL"}]
        }
    }
}
EOF

    cat > "$PI_CONFIG_DIR/settings.json" << EOF
{
    "defaultProvider": "ollama",
    "defaultModel": "$MODEL"
}
EOF
    ok "Pi configured for Ollama"
else
    warn "npm not found — skipping Pi agent (install Node.js for coding features)"
fi

# ─── Write Thia-Lite Config ──────────────────────────────────────────────────

THIA_CONFIG_DIR="$HOME/.thia-lite"
mkdir -p "$THIA_CONFIG_DIR/data/ephe" "$THIA_CONFIG_DIR/logs"

cat > "$THIA_CONFIG_DIR/config.toml" << EOF
# Thia-Lite Configuration
# Generated by installer on $(date)

[ollama]
host = "http://localhost:11434"
model = "$MODEL"
temperature = 0.3

[mcp]
server_mode = "stdio"
server_port = 8443
EOF

ok "Configuration written to $THIA_CONFIG_DIR/config.toml"

# ─── MCP Config for Claude Desktop ───────────────────────────────────────────

MCP_CONFIG_EXAMPLE="$THIA_DIR/mcp-config.json"
cat > "$MCP_CONFIG_EXAMPLE" << EOF
{
    "mcpServers": {
        "thia-lite": {
            "command": "$THIA_DIR/.venv/bin/python",
            "args": ["-m", "thia_lite", "serve", "--mode", "stdio"],
            "env": {}
        }
    }
}
EOF

info "Claude Desktop MCP config: $MCP_CONFIG_EXAMPLE"

# ─── Create Launch Scripts ────────────────────────────────────────────────────

# CLI launcher
cat > "$THIA_DIR/thia-lite" << EOF
#!/usr/bin/env bash
source "$THIA_DIR/.venv/bin/activate"
python -m thia_lite "\$@"
EOF
chmod +x "$THIA_DIR/thia-lite"

# TUI launcher
cat > "$THIA_DIR/thia-lite-tui" << EOF
#!/usr/bin/env bash
source "$THIA_DIR/.venv/bin/activate"
python -c "from thia_lite.tui import run_tui; run_tui()"
EOF
chmod +x "$THIA_DIR/thia-lite-tui"

# ─── Smoke Test ───────────────────────────────────────────────────────────────

echo ""
info "Running smoke test..."

if "$THIA_DIR/.venv/bin/python" -c "from thia_lite.config import get_settings; s = get_settings(); print(f'Config OK: model={s.ollama.model}')" 2>/dev/null; then
    ok "Smoke test passed"
else
    warn "Smoke test failed — check installation"
fi

# ─── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔════════════════════════════════════════════╗"
echo "  ║  ✨ Installation Complete!                 ║"
echo "  ╚════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "  ${BOLD}Quick Start:${NC}"
echo -e "    ${CYAN}./thia-lite chat${NC}           Interactive CLI"
echo -e "    ${CYAN}./thia-lite-tui${NC}            Terminal UI"
echo -e "    ${CYAN}./thia-lite serve${NC}          MCP server (for Claude Desktop)"
echo -e "    ${CYAN}./thia-lite health${NC}         System check"
echo ""
echo -e "  ${BOLD}Model:${NC} $MODEL"
echo -e "  ${BOLD}Config:${NC} $THIA_CONFIG_DIR/config.toml"
echo ""
