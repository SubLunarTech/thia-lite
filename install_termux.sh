#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Thia-Lite Termux Installer (Android)
# ─────────────────────────────────────────────────────────────────────────────
# Run this inside Termux on Android:
#   curl -fsSL https://raw.githubusercontent.com/thia-libre/thia-lite/main/install_termux.sh | bash
#
# Termux gives us a full Linux environment on Android — no root needed.
# This install script handles:
# 1. Termux package updates
# 2. Python 3.11+ from Termux repos
# 3. Ollama (arm64)
# 4. Qwen 3.5 4B model (smaller for phone RAM)
# 5. Thia-Lite Python package
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
echo "  🌟 Thia-Lite — Android/Termux Installer"
echo -e "${NC}"

# ─── Check Termux ─────────────────────────────────────────────────────────────

if [ -z "${TERMUX_VERSION:-}" ] && [ ! -d "$HOME/../usr" ]; then
    err "This script should be run in Termux on Android."
    echo "  Install Termux from F-Droid: https://f-droid.org/packages/com.termux/"
    exit 1
fi

info "Termux detected. Updating packages..."
pkg update -y -q 2>/dev/null || apt update -y -q
pkg upgrade -y -q 2>/dev/null || apt upgrade -y -q

# ─── Install Dependencies ────────────────────────────────────────────────────

info "Installing system dependencies..."
pkg install -y python git clang make libffi openssl-tool 2>/dev/null || \
    apt install -y python git clang make libffi openssl-tool

ok "Python $(python3 --version | cut -d' ' -f2) installed"

# Check RAM
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
info "Device RAM: ${TOTAL_RAM_GB}GB"

# ─── Install Ollama (Termux/ARM64) ───────────────────────────────────────────

if command -v ollama &>/dev/null; then
    ok "Ollama already installed"
else
    info "Installing Ollama for Android..."
    # Ollama has ARM64 Linux builds that work in Termux
    curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null || {
        warn "Ollama auto-install failed. Trying manual install..."
        ARCH=$(uname -m)
        if [ "$ARCH" = "aarch64" ]; then
            curl -fsSL -o ollama "https://ollama.com/download/ollama-linux-arm64"
            chmod +x ollama
            mv ollama $PREFIX/bin/
            ok "Ollama installed manually (arm64)"
        else
            err "Unsupported architecture: $ARCH"
            exit 1
        fi
    }
fi

# Start Ollama
if ! pgrep -x "ollama" > /dev/null 2>&1; then
    info "Starting Ollama..."
    ollama serve &>/dev/null &
    sleep 5
fi

# ─── Pull Model (Phone-Sized) ────────────────────────────────────────────────

# On phones, use smaller models
if [ "$TOTAL_RAM_GB" -ge 8 ]; then
    MODEL="qwen2.5:7b"
    info "8GB+ RAM — using Qwen 2.5 7B"
elif [ "$TOTAL_RAM_GB" -ge 6 ]; then
    MODEL="qwen2.5:3b"
    info "6GB RAM — using Qwen 2.5 3B"
elif [ "$TOTAL_RAM_GB" -ge 4 ]; then
    MODEL="qwen2.5:1.5b"
    info "4GB RAM — using Qwen 2.5 1.5B (basic tool calling)"
else
    MODEL="qwen2.5:0.5b"
    warn "Low RAM — using Qwen 2.5 0.5B (limited capabilities)"
fi

if ollama list 2>/dev/null | grep -q "$(echo $MODEL | cut -d: -f1)"; then
    ok "Model $MODEL available"
else
    info "Downloading $MODEL..."
    ollama pull "$MODEL"
    ok "Model ready"
fi

# ─── Install Thia-Lite ────────────────────────────────────────────────────────

THIA_DIR="$HOME/thia-lite"

if [ -d "$THIA_DIR" ]; then
    info "Updating existing installation..."
    cd "$THIA_DIR" && git pull --rebase 2>/dev/null || true
else
    info "Cloning thia-lite..."
    git clone https://github.com/thia-libre/thia-lite.git "$THIA_DIR" 2>/dev/null || {
        # If git clone fails, just create the directory
        mkdir -p "$THIA_DIR"
        warn "Git clone failed — install from pip instead"
    }
fi

cd "$THIA_DIR"

# Create venv
python3 -m venv .venv 2>/dev/null || python3 -m venv --without-pip .venv
source .venv/bin/activate

pip install --upgrade pip -q 2>/dev/null || true
pip install -e . -q 2>&1 | tail -1 || pip install pydantic httpx typer rich textual -q

ok "Thia-Lite installed"

# ─── Config ───────────────────────────────────────────────────────────────────

THIA_CONFIG_DIR="$HOME/.thia-lite"
mkdir -p "$THIA_CONFIG_DIR/data/ephe" "$THIA_CONFIG_DIR/logs"

cat > "$THIA_CONFIG_DIR/config.toml" << EOF
# Thia-Lite (Android/Termux)
[ollama]
host = "http://localhost:11434"
model = "$MODEL"
temperature = 0.3
timeout = 180

[mcp]
server_mode = "stdio"
EOF

# ─── Launcher ─────────────────────────────────────────────────────────────────

cat > "$PREFIX/bin/thia-lite" << EOF
#!/usr/bin/env bash
source "$THIA_DIR/.venv/bin/activate"
python -m thia_lite "\$@"
EOF
chmod +x "$PREFIX/bin/thia-lite"

# ─── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}${BOLD}✨ Thia-Lite installed!${NC}"
echo ""
echo -e "  ${CYAN}thia-lite chat${NC}     Start chatting"
echo -e "  ${CYAN}thia-lite health${NC}   Check system"
echo -e "  ${CYAN}thia-lite update${NC}   Check for updates"
echo ""
echo -e "  Model: $MODEL"
echo -e "  RAM: ${TOTAL_RAM_GB}GB"
echo ""
