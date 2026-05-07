#!/usr/bin/env bash
# install.sh — OCBrain one-liner installer
# Usage: curl -fsSL https://raw.githubusercontent.com/1h0lde4/OCBrain/main/install.sh | bash
#
# Supports: Debian/Ubuntu (apt), Fedora/RHEL (dnf),
#           Arch Linux (AUR), macOS (Homebrew), any OS (pip)

set -euo pipefail

GITHUB_REPO="1h0lde4/OCBrain"
GITHUB_RAW="https://raw.githubusercontent.com/${GITHUB_REPO}/main"
GITHUB_API="https://api.github.com/repos/${GITHUB_REPO}/releases/latest"
APT_REPO="https://YOUR_USERNAME.github.io/ocbrain/apt"
GPG_KEY_URL="https://YOUR_USERNAME.github.io/ocbrain/apt/ocbrain.gpg"

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; BLU='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLU}[ocbrain]${NC} $*"; }
ok()    { echo -e "${GRN}[ocbrain]${NC} ✓ $*"; }
warn()  { echo -e "${YLW}[ocbrain]${NC} ⚠ $*"; }
die()   { echo -e "${RED}[ocbrain]${NC} ✗ $*"; exit 1; }

banner() {
    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║   OCBrain  Installer  v2.0   ║"
    echo "  ║   github.com/${GITHUB_REPO}  ║"
    echo "  ╚══════════════════════════════════════╝"
    echo ""
}

detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then echo "macos"; return; fi
    [[ -f /etc/os-release ]] || die "Cannot detect OS"
    . /etc/os-release
    local id="${ID:-linux}" like="${ID_LIKE:-}"
    for s in "$id" $like; do
        case "${s,,}" in
            arch|manjaro|endeavouros) echo "arch";  return ;;
            fedora|rhel|centos|rocky|alma) echo "rpm"; return ;;
        esac
    done
    echo "deb"
}

check_python() {
    command -v python3 &>/dev/null || die "Python 3 not found. Install Python 3.11+ first."
    local ver major minor
    ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    [[ "$major" -ge 3 && "$minor" -ge 11 ]] || die "Python 3.11+ required (found $ver)"
    ok "Python $ver"
}

get_latest_version() {
    curl -fsSL "$GITHUB_API" 2>/dev/null \
        | grep '"tag_name"' | cut -d'"' -f4 | tr -d 'v' \
        || echo "2.0.0"
}

# ── Installation methods ──────────────────────────────────────

install_pip() {
    info "Installing via pip from GitHub..."
    pip3 install --upgrade pip --quiet
    pip3 install "git+https://github.com/${GITHUB_REPO}.git" --quiet
    ok "Installed via pip"
}

install_pip_release() {
    local ver="$1"
    info "Installing release v${ver} via pip..."
    pip3 install --upgrade pip --quiet
    pip3 install "https://github.com/${GITHUB_REPO}/archive/refs/tags/v${ver}.tar.gz" --quiet
    ok "Installed v${ver} via pip"
}

install_deb() {
    info "Installing via apt (Debian/Ubuntu)..."
    sudo apt-get update -qq
    sudo apt-get install -y curl gnupg python3 python3-pip

    if curl -fsSL "$GPG_KEY_URL" &>/dev/null; then
        curl -fsSL "$GPG_KEY_URL" | sudo gpg --dearmor -o /usr/share/keyrings/ocbrain.gpg
        echo "deb [signed-by=/usr/share/keyrings/ocbrain.gpg] $APT_REPO stable main" \
            | sudo tee /etc/apt/sources.list.d/ocbrain.list > /dev/null
        sudo apt-get update -qq
        if sudo apt-get install -y ocbrain 2>/dev/null; then
            ok "Installed via apt"; return
        fi
    fi
    warn "APT repo not ready — falling back to pip"
    install_pip
    _post_install_linux
}

install_rpm() {
    info "Installing via dnf (Fedora/RHEL)..."
    if command -v dnf &>/dev/null; then
        if sudo dnf copr enable -y "${GITHUB_REPO/\//\/}" 2>/dev/null; then
            sudo dnf install -y ocbrain 2>/dev/null && { ok "Installed via dnf"; return; }
        fi
    fi
    warn "COPR repo not ready — falling back to pip"
    sudo dnf install -y python3 python3-pip 2>/dev/null || true
    install_pip
    _post_install_linux
}

install_arch() {
    info "Installing via AUR (Arch Linux)..."
    if command -v yay &>/dev/null; then
        yay -S --noconfirm ocbrain 2>/dev/null && { ok "Installed via yay"; return; }
    elif command -v paru &>/dev/null; then
        paru -S --noconfirm ocbrain 2>/dev/null && { ok "Installed via paru"; return; }
    fi
    warn "AUR package not ready — falling back to pip"
    install_pip
    _post_install_linux
}

install_macos() {
    info "Installing on macOS..."
    if ! command -v brew &>/dev/null; then
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    if brew tap "YOUR_USERNAME/ocbrain" 2>/dev/null && \
       brew install --cask ocbrain 2>/dev/null; then
        ok "Installed via Homebrew"
    else
        warn "Homebrew tap not ready — falling back to pip"
        install_pip
    fi
    # LaunchAgent autostart
    local plist="$HOME/Library/LaunchAgents/io.ocbrain.plist"
    if [[ ! -f "$plist" ]]; then
        curl -fsSL "${GITHUB_RAW}/install/io.ocbrain.plist" -o "$plist" 2>/dev/null || true
        launchctl load "$plist" 2>/dev/null || true
    fi
}

_post_install_linux() {
    # Install systemd user service if available
    if command -v systemctl &>/dev/null; then
        local svc_dir="$HOME/.config/systemd/user"
        mkdir -p "$svc_dir"
        cat > "$svc_dir/ocbrain.service" << 'SVC'
[Unit]
Description=OCBrain
After=network.target

[Service]
Type=simple
ExecStart=ocbrain-start
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
SVC
        systemctl --user daemon-reload 2>/dev/null || true
        systemctl --user enable ocbrain 2>/dev/null || true
        ok "Systemd service enabled (ocbrain.service)"
    fi
}

check_ollama() {
    echo ""
    if command -v ollama &>/dev/null; then
        ok "Ollama found"
        if ! ollama list 2>/dev/null | grep -qE "mistral|llama|gemma"; then
            info "Pulling mistral model (may take a few minutes)..."
            ollama pull mistral && ok "mistral model ready"
        else
            ok "Ollama model(s) ready"
        fi
    else
        warn "Ollama not installed — required for bootstrap stage"
        warn "Install from: https://ollama.ai"
        warn "Then run: ollama pull mistral && ollama pull codestral"
    fi
}

post_install() {
    echo ""
    if command -v ocbrain &>/dev/null || python3 -c "import interface.cli" 2>/dev/null; then
        ok "OCBrain installed successfully!"
    else
        warn "ocbrain not found in PATH — you may need to restart your shell"
        warn "Or activate your virtualenv: source .venv/bin/activate"
    fi

    echo ""
    echo "  ╔═════════════════════════════════════════╗"
    echo "  ║   Getting started                       ║"
    echo "  ║                                         ║"
    echo "  ║   Start:    ocbrain-start              ║"
    echo "  ║   Web UI:   http://localhost:7437       ║"
    echo "  ║   Docs:     http://localhost:7437/docs  ║"
    echo "  ║   CLI:      ocbrain \"your question\"   ║"
    echo "  ║                                         ║"
    echo "  ║   GitHub:                               ║"
    echo "  ║   github.com/${GITHUB_REPO}    ║"
    echo "  ╚═════════════════════════════════════════╝"
    echo ""
}

main() {
    banner
    check_python

    OS=$(detect_os)
    VERSION=$(get_latest_version)
    info "OS: $OS | Latest release: v$VERSION"

    # Allow --pip flag to force pip install
    if [[ "${1:-}" == "--pip" ]]; then
        install_pip
        check_ollama
        post_install
        exit 0
    fi

    case "$OS" in
        deb)   install_deb   ;;
        rpm)   install_rpm   ;;
        arch)  install_arch  ;;
        macos) install_macos ;;
        *)     warn "Unknown OS — using pip"; install_pip ;;
    esac

    check_ollama
    post_install
}

main "$@"
