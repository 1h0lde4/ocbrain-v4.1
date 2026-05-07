#!/usr/bin/env bash
# =============================================================================
#  OCBrain — Self-Healing Setup (merged: user architecture + full deps)
#  Combines: resume system, ERR trap, locked Python, binary-first installs
#            + full dep coverage, sentence-transformers fix, Ollama, spaCy
#
#  Usage:
#    bash setup.sh                      # interactive
#    TRAIN=y VOICE=n bash setup.sh      # non-interactive / CI
#    RESET_INSTALL=1 bash setup.sh      # full clean reset
# =============================================================================

set -uo pipefail
set -o errtrace

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'
BLU='\033[0;34m'; CYN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GRN}  ✓${NC}  $*"; }
warn() { echo -e "${YLW}  ⚠${NC}  $*"; }
info() { echo -e "${BLU}  →${NC}  $*"; }
fix()  { echo -e "${CYN}  ⚙${NC}  $*"; }
fail() { echo -e "${RED}  ✗${NC}  $*"; }
die()  { echo -e "\n${RED}${BOLD}  FATAL:${NC} $*\n"; exit 1; }
step() { echo -e "\n${BOLD}$*${NC}"; }

# ── State / log files ─────────────────────────────────────────────────────────
STATE_FILE=".ocbrain_install_state"
PYTHON_FILE=".python_selected"
LOG_FILE=".ocbrain_install.log"

# Start logging everything
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "$(date): setup.sh started"

# ERR trap — prints exact line number of crash
trap 'echo ""; fail "Crashed at line $LINENO — check $LOG_FILE for details"; exit 1' ERR

# ── Idempotency helpers ───────────────────────────────────────────────────────
mark_done() { echo "$1" >> "$STATE_FILE"; }
is_done()   { grep -Fxq "$1" "$STATE_FILE" 2>/dev/null; }

run_step() {
    local id="$1"
    local name="$2"
    shift 2
    if is_done "$id"; then
        ok "[SKIP] $name — already done"
        return 0
    fi
    step "  $name"
    if "$@"; then
        mark_done "$id"
        ok "$name done"
    else
        fail "$name failed"
        exit 1
    fi
}

# ── Reset ─────────────────────────────────────────────────────────────────────
if [[ "${RESET_INSTALL:-}" == "1" ]]; then
    warn "RESET_INSTALL=1 — wiping state and venv..."
    rm -rf .venv "$STATE_FILE" "$PYTHON_FILE"
    warn "Reset done. Re-running setup from scratch."
fi

# ── Restore persisted state from previous run ─────────────────────────────────
# PYTHON_BIN and venv are restored here so subsequent run_step calls
# can skip already-completed steps correctly.
PYTHON_BIN=""
PYTHON=""
PIP=""

if [[ -f "$PYTHON_FILE" ]]; then
    PYTHON_BIN="$(cat "$PYTHON_FILE")"
    ok "[RESUME] Python: $PYTHON_BIN"
fi

if [[ -f ".venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
    PYTHON=".venv/bin/python"
    PIP=".venv/bin/pip"
    ok "[RESUME] Venv active ($($PYTHON --version 2>/dev/null))"
fi

# ── Distro detection ──────────────────────────────────────────────────────────
detect_distro() {
    PKG_MANAGER="unknown"
    if [[ -f /etc/os-release ]]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DISTRO_ID="${ID:-unknown}"
        DISTRO_LIKE="${ID_LIKE:-}"
        if echo "$DISTRO_ID $DISTRO_LIKE" | grep -qiE "ubuntu|debian|mint|pop|kali|raspbian"; then
            PKG_MANAGER="apt"
        elif echo "$DISTRO_ID $DISTRO_LIKE" | grep -qiE "fedora|rhel|centos|rocky|alma"; then
            PKG_MANAGER="dnf"
        elif echo "$DISTRO_ID $DISTRO_LIKE" | grep -qiE "arch|manjaro|endeavour"; then
            PKG_MANAGER="pacman"
        elif echo "$DISTRO_ID $DISTRO_LIKE" | grep -qiE "opensuse|suse"; then
            PKG_MANAGER="zypper"
        fi
    fi
    ok "Distro: ${DISTRO_ID:-unknown} | Package manager: $PKG_MANAGER"
}

# ── System packages ───────────────────────────────────────────────────────────
step_sysdeps() {
    detect_distro
    info "Installing build tools and system libraries..."

    case "$PKG_MANAGER" in
        apt)
            sudo apt-get update -qq
            sudo apt-get install -y --no-install-recommends \
                build-essential curl git ca-certificates \
                python3-dev \
                libssl-dev libffi-dev \
                zlib1g-dev libbz2-dev \
                libreadline-dev libsqlite3-dev \
                liblzma-dev \
                libgomp1 \
                libstdc++6 \
                portaudio19-dev \
                ;;
        dnf)
            sudo dnf install -y \
                gcc gcc-c++ curl git ca-certificates \
                python3-devel openssl-devel libffi-devel \
                zlib-devel bzip2-devel readline-devel sqlite-devel \
                xz-devel libgomp portaudio-devel \
                ;;
        pacman)
            sudo pacman -S --noconfirm --needed \
                base-devel curl git ca-certificates \
                python openssl libffi zlib bzip2 readline sqlite \
                xz libgomp portaudio \
                ;;
        zypper)
            sudo zypper install -y \
                gcc gcc-c++ curl git ca-certificates \
                python3-devel libopenssl-devel libffi-devel \
                zlib-devel libbz2-devel libreadline-devel sqlite3-devel \
                xz-devel libgomp1 portaudio-devel \
                ;;
        *)
            warn "Unknown package manager — skipping system packages."
            warn "If setup fails, manually install: build-essential libssl-dev libffi-dev libgomp1"
            ;;
    esac
    ok "System dependencies installed"
}

# ── Rust / cargo ──────────────────────────────────────────────────────────────
# Required by tokenizers (a sentence-transformers dependency).
# Critical fix: export PYENV_ROOT + cargo PATH globally so they persist
# across all subsequent step functions.
step_rust() {
    # Source cargo env if already installed
    [[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"

    if command -v cargo &>/dev/null; then
        ok "Rust: $(cargo --version)"
        return 0
    fi

    info "Installing Rust via rustup (needed for tokenizers)..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
        | sh -s -- -y --no-modify-path \
        || { warn "Rust install failed — tokenizers will need pre-built wheel"; return 0; }

    source "$HOME/.cargo/env"

    if command -v cargo &>/dev/null; then
        ok "Rust installed: $(rustc --version)"
    else
        warn "cargo not in PATH after install — tokenizers may fail to build"
    fi
}

# ── pyenv ────────────────────────────────────────────────────────────────────
# Fix from user's script: export PYENV_ROOT at the TOP LEVEL (not inside
# a subshell) so pyenv is available to every subsequent step.
step_pyenv() {
    export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
    export PATH="$PYENV_ROOT/bin:$PATH"

    if command -v pyenv &>/dev/null; then
        ok "pyenv already installed: $(pyenv --version)"
        eval "$(pyenv init -)"
        return 0
    fi

    info "Installing pyenv..."
    curl -fsSL https://pyenv.run | bash \
        || die "pyenv install failed. Check your internet connection."

    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"

    if command -v pyenv &>/dev/null; then
        ok "pyenv installed: $(pyenv --version)"
    else
        die "pyenv installed but not found in PATH. Add to your shell:\n\
  export PYENV_ROOT=\"\$HOME/.pyenv\"\n\
  export PATH=\"\$PYENV_ROOT/bin:\$PATH\"\n\
  eval \"\$(pyenv init -)\""
    fi
}

# ── Python (locked to 3.11.9) ─────────────────────────────────────────────────
TARGET_PYTHON="3.11.9"

step_python() {
    export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)" 2>/dev/null || true

    if ! pyenv versions --bare 2>/dev/null | grep -qx "$TARGET_PYTHON"; then
        info "Installing Python $TARGET_PYTHON via pyenv..."
        pyenv install "$TARGET_PYTHON" \
            || die "Python $TARGET_PYTHON install failed.\nCheck pyenv output above."
    fi

    pyenv local "$TARGET_PYTHON"
    PYTHON_BIN="$(pyenv which python 2>/dev/null)" \
        || die "pyenv which python failed after install"

    echo "$PYTHON_BIN" > "$PYTHON_FILE"
    ok "Python locked: $($PYTHON_BIN --version)"
}

# ── Virtual environment ───────────────────────────────────────────────────────
step_venv() {
    if [[ -z "${PYTHON_BIN:-}" ]]; then
        PYTHON_BIN="$(cat "$PYTHON_FILE" 2>/dev/null)" \
            || die "PYTHON_BIN not set and $PYTHON_FILE missing. Run setup.sh from scratch."
    fi

    # Check if existing venv was built with the right Python
    if [[ -d ".venv" ]]; then
        EXISTING=$(.venv/bin/python -c 'import sys;print(sys.version[:6])' 2>/dev/null || echo "0.0.0")
        TARGET=$("$PYTHON_BIN" -c 'import sys;print(sys.version[:6])')
        if [[ "$EXISTING" != "$TARGET" ]]; then
            warn "Venv Python mismatch ($EXISTING ≠ $TARGET) — rebuilding..."
            rm -rf .venv
        fi
    fi

    if [[ ! -d ".venv" ]]; then
        info "Creating virtual environment..."
        "$PYTHON_BIN" -m venv .venv \
            || die "venv creation failed."
    fi

    # shellcheck disable=SC1091
    source .venv/bin/activate
    PYTHON=".venv/bin/python"
    PIP=".venv/bin/pip"

    ok "Venv ready: $($PYTHON --version)"
}

# ── pip upgrade ───────────────────────────────────────────────────────────────
step_pip_upgrade() {
    "$PYTHON" -m pip install --upgrade pip setuptools wheel \
        --timeout 120 --quiet \
        || warn "pip upgrade had warnings — continuing"
    ok "pip $(pip --version | cut -d' ' -f2) ready"
}

# ── pip install helper ────────────────────────────────────────────────────────
# Uses --prefer-binary by default (user's improvement).
# Caller can pass --no-binary :none: to override when source build is needed.
pip_install() {
    local desc="$1"; shift
    local max_retries=3
    local attempt=0

    while (( attempt < max_retries )); do
        (( attempt++ )) || true
        [[ $attempt -gt 1 ]] && { warn "Retry $attempt/$max_retries: $desc"; sleep 3; }

        if "$PIP" install \
            --prefer-binary \
            --no-cache-dir \
            --timeout 120 \
            "$@" 2>/tmp/ocbrain_pip.err; then
            return 0
        fi
    done

    fail "Failed to install: $desc"
    cat /tmp/ocbrain_pip.err
    return 1
}

# ── Core packages (Phase A — pure Python, always pre-built) ──────────────────
step_core_a() {
    info "Phase A: pure-Python packages (fast)..."
    pip_install "core packages" \
        "fastapi>=0.111.0" \
        "uvicorn[standard]>=0.30.1" \
        "httpx>=0.27.0" \
        "aiofiles>=23.2.1" \
        "pydantic>=2.7.1" \
        "tomli>=2.0.1" \
        "tomli-w>=1.0.0" \
        "watchdog>=4.0.1" \
        "PyYAML>=6.0.1" \
        "click>=8.1.7" \
        "rich>=13.7.1" \
        "requests>=2.32.3" \
        "feedparser>=6.0.11" \
        "sqlalchemy>=2.0.30" \
        "pystray>=0.19.5" \
        "Pillow>=10.3.0" \
        "datasketch>=1.6.4" \
        --quiet \
        || die "Core package install failed. Check your internet connection."
}

# ── Compilation packages (Phase B) ───────────────────────────────────────────
# ORDER MATTERS: numpy and typer must be pinned BEFORE spacy and chromadb
# are installed, because:
#   spacy 3.7.x requires numpy<2.0 and typer<0.10.0
#   chromadb 0.5.x requires typer>=0.9.0
#   Installing all at once gives pip no room to satisfy both simultaneously.
step_core_b() {
    info "Phase B: pinning shared deps before ML packages..."

    # 1. numpy — hard cap from spacy 3.7.x, also needed by sentence-transformers
    pip_install "numpy (pinned <2.0)" \
        "numpy>=1.23.0,<2.0" \
        --quiet \
        && ok "numpy ✓" \
        || warn "numpy pin failed — ABI issues may occur"

    # 2. typer — must satisfy BOTH spacy (<0.10.0) AND chromadb (>=0.9.0)
    pip_install "typer (spacy+chromadb compatible range)" \
        "typer>=0.9.0,<0.10.0" \
        --quiet \
        && ok "typer ✓" \
        || warn "typer pin failed — spacy/chromadb conflict may still occur"

    # 3. spacy — resolver now has numpy and typer already locked
    pip_install "spacy" \
        "spacy>=3.7.0,<3.8" \
        --quiet \
        && ok "spacy ✓" \
        || warn "spacy failed — classifier will use keyword-only mode"

    # 4. trafilatura — independent, no shared-dep conflict
    pip_install "trafilatura" \
        "trafilatura>=1.9.0" \
        --quiet \
        && ok "trafilatura ✓" \
        || warn "trafilatura failed — web search will have limited extraction"
}

# ── torch CPU (ALWAYS required — sentence-transformers needs it at import time) ──
step_torch_cpu() {
    if "$PYTHON" -c "import torch" &>/dev/null 2>&1; then
        ok "torch already installed: $("$PYTHON" -c 'import torch; print(torch.__version__)')"
        return 0
    fi

    info "Installing torch (required by sentence-transformers at import time)..."
    if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null 2>&1; then
        CUDA_VER=$(nvidia-smi | grep -oP 'CUDA Version: \K[\d.]+' | head -1 || echo "unknown")
        ok "NVIDIA GPU detected (CUDA $CUDA_VER)"
        pip_install "torch (CUDA)" torch --quiet \
            || {
                warn "CUDA torch failed — falling back to CPU build"
                pip_install "torch (CPU fallback)" \
                    torch --index-url https://download.pytorch.org/whl/cpu --quiet \
                    || die "torch install failed entirely. Check $LOG_FILE"
            }
    else
        info "No NVIDIA GPU — installing torch CPU build (~500 MB)"
        pip_install "torch (CPU)" \
            torch --index-url https://download.pytorch.org/whl/cpu --quiet \
            || die "torch CPU install failed. Check $LOG_FILE"
    fi
    ok "torch ✓: $("$PYTHON" -c 'import torch; print(torch.__version__)')"
}

# ── chromadb (needs sqlite3 >= 3.35 + onnxruntime + import-time patch) ────────
step_chromadb() {
    # ── 1. sqlite3 version check ─────────────────────────────────────────────
    SQLITE_VER=$("$PYTHON" -c "import sqlite3; print(sqlite3.sqlite_version)" 2>/dev/null || echo "0.0.0")
    SQLITE_MIN=$(echo "$SQLITE_VER" | awk -F. '{print $2}')

    if (( SQLITE_MIN < 35 )); then
        warn "sqlite3 $SQLITE_VER < 3.35 — installing pysqlite3-binary"
        pip_install "pysqlite3-binary" pysqlite3-binary --quiet \
            && ok "pysqlite3-binary ✓" \
            || warn "pysqlite3-binary failed — chromadb may not import"

        # CRITICAL: write sitecustomize.py into the venv so the sqlite3
        # monkey-patch applies automatically every time Python starts.
        # Without this, pysqlite3-binary is installed but never used.
        SITE_DIR=$("$PYTHON" -c "import site; print(site.getsitepackages()[0])")
        info "Writing sqlite3 monkey-patch → $SITE_DIR/sitecustomize.py"
        cat > "$SITE_DIR/sitecustomize.py" << 'PATCH'
# OCBrain: swap system sqlite3 for pysqlite3-binary so chromadb works
# on systems where system sqlite3 < 3.35 (e.g. Ubuntu 20.04)
try:
    import pysqlite3 as _pysqlite3
    import sys as _sys
    _sys.modules["sqlite3"] = _sys.modules.pop("pysqlite3", _pysqlite3)
except ImportError:
    pass
PATCH
        ok "sqlite3 monkey-patch written to sitecustomize.py"
    else
        ok "sqlite3 $SQLITE_VER ✓"
    fi

    # ── 2. onnxruntime — install explicitly before chromadb ──────────────────
    # chromadb depends on onnxruntime; on some systems it silently fails as a
    # transitive dep, then chromadb raises ModuleNotFoundError at import time.
    info "Installing onnxruntime (chromadb dependency)..."
    pip_install "onnxruntime" onnxruntime --prefer-binary --quiet \
        && ok "onnxruntime ✓" \
        || warn "onnxruntime failed — chromadb may crash on import"

    # ── 3. chromadb install ───────────────────────────────────────────────────
    pip_install "chromadb" "chromadb>=0.5.0,<0.6" --quiet \
        || die "chromadb install failed. Check $LOG_FILE"

    # ── 4. verify import works ───────────────────────────────────────────────
    if "$PYTHON" -c "import chromadb" &>/dev/null 2>&1; then
        ok "chromadb import verified ✓"
    else
        warn "chromadb import failed — trying inline sqlite3 patch as fallback..."
        if "$PYTHON" - <<< $'import sys\ntry:\n    import pysqlite3\n    sys.modules["sqlite3"]=pysqlite3\nexcept ImportError: pass\nimport chromadb\nprint("ok")' 2>/dev/null; then
            ok "chromadb import OK with inline patch"
        else
            fail "chromadb still fails to import — check $LOG_FILE"
            warn "Try: source .venv/bin/activate && python -c \"import pysqlite3,sys; sys.modules['sqlite3']=pysqlite3; import chromadb\""
        fi
    fi
}

# ── sentence-transformers + full huggingface ecosystem ────────────────────────
# Root cause of previous failures:
#   - tight upper-bound pins (<4.42, <0.19, <0.25) blocked trl 1.2.0 from
#     getting transformers>=4.56.2, leaving the stack in a broken mixed state
#   - split pip calls allowed partial upgrades that left incompatible combinations
# Fix: install the ENTIRE ecosystem in ONE pip call with no artificial upper caps.
#   Let pip's resolver find a consistent set satisfying ALL constraints at once.
step_sentence_transformers() {
    info "Installing sentence-transformers + huggingface ecosystem..."

    [[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env" || true

    # Unset binary-only restriction: tokenizers may need source build fallback
    local OLD_PIP_ONLY_BINARY="${PIP_ONLY_BINARY:-}"
    unset PIP_ONLY_BINARY 2>/dev/null || true

    # Confirm torch is present (installed by step_torch_cpu)
    if ! "$PYTHON" -c "import torch" &>/dev/null 2>&1; then
        die "torch is not installed. This is a bug — step_torch_cpu should have run first."
    fi

    # ONE pip call for the entire huggingface ecosystem.
    # Constraints:
    #   transformers>=4.56.2  — satisfies trl 1.2.0 AND sentence-transformers
    #   tokenizers>=0.21      — required by transformers 4.56+
    #   huggingface_hub>=0.26 — required by transformers 4.56+
    #   sentence-transformers>=3.0.1 — the target package
    # NO upper-bound caps — let pip find a consistent set.
    info "  Resolving huggingface ecosystem in single pass..."
    if pip_install "huggingface ecosystem"         "huggingface_hub>=0.26"         "tokenizers>=0.21"         "transformers>=4.56.2"         "sentence-transformers>=3.0.1"         --quiet; then
        : # success path below
    else
        # Retry without --prefer-binary (tokenizers may need source build)
        warn "  Retrying without binary restriction..."
        "$PIP" install             --no-cache-dir             --timeout 180             "huggingface_hub>=0.26"             "tokenizers>=0.21"             "transformers>=4.56.2"             "sentence-transformers>=3.0.1"             || {
                # Final fallback: force-compile tokenizers from source
                warn "  Final fallback: source build for tokenizers..."
                "$PIP" install                     --no-cache-dir                     --timeout 300                     --no-binary tokenizers                     "huggingface_hub>=0.26"                     "tokenizers>=0.21"                     "transformers>=4.56.2"                     "sentence-transformers>=3.0.1"                     || die "sentence-transformers install failed after all attempts.\nEnsure Rust is installed: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh\nThen re-run: RESET_INSTALL=1 bash setup.sh"
            }
    fi

    [[ -n "$OLD_PIP_ONLY_BINARY" ]] && export PIP_ONLY_BINARY="$OLD_PIP_ONLY_BINARY"

    # Verify — use the actual class import, not just the module
    if "$PYTHON" -c "from sentence_transformers import SentenceTransformer" &>/dev/null 2>&1; then
        ST_VER=$("$PYTHON" -c "import sentence_transformers; print(sentence_transformers.__version__)" 2>/dev/null || echo "?")
        TR_VER=$("$PYTHON" -c "import transformers; print(transformers.__version__)" 2>/dev/null || echo "?")
        ok "sentence-transformers $ST_VER ✓  (transformers $TR_VER)"
    else
        fail "sentence-transformers import failed"
        warn "Run manually to see full error:"
        warn "  source .venv/bin/activate"
        warn "  python -c \"from sentence_transformers import SentenceTransformer\""
        # Do not die here — let the verification step report it clearly
    fi
}


# ── Project editable install ──────────────────────────────────────────────────
step_project() {
    [[ -f version.txt ]] || echo "2.1.0" > version.txt

    pip_install "ocbrain (editable)" \
        -e . --quiet \
        || die "Failed to install OCBrain. Check that pyproject.toml is valid."
}

# ── spaCy model ───────────────────────────────────────────────────────────────
step_spacy_model() {
    if "$PYTHON" -c "import en_core_web_sm" &>/dev/null 2>&1; then
        ok "spaCy model already installed"
        return 0
    fi

    info "Downloading spaCy model en_core_web_sm..."

    if "$PYTHON" -m spacy download en_core_web_sm --quiet 2>/tmp/ocbrain_spacy.err; then
        ok "spaCy model ✓"
    else
        warn "spacy download command failed — trying direct pip URL..."
        SPACY_WHL="https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl"
        pip_install "en_core_web_sm (direct)" "$SPACY_WHL" --quiet \
            && ok "spaCy model ✓ (direct URL)" \
            || {
                warn "spaCy model install failed — classifier will use keyword-only mode"
                warn "Fix manually: source .venv/bin/activate && python -m spacy download en_core_web_sm"
            }
    fi
}

# ── Optional: training deps ───────────────────────────────────────────────────
step_training() {
    echo ""
    TRAIN="${TRAIN:-}"
    if [[ -z "$TRAIN" ]]; then
        echo -e "${BOLD}  Training dependencies${NC} (LoRA fine-tuning — requires GPU 6+ GB VRAM)"
        echo    "  Allows OCBrain to train its own models locally over time."
        read -rp "  Install training dependencies? [y/N] " TRAIN
    fi
    [[ "$TRAIN" =~ ^[Yy]$ ]] || { warn "Skipping training deps"; return 0; }

    info "Installing training stack..."
    [[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env" || true
    unset PIP_ONLY_BINARY 2>/dev/null || true

    # trl 1.2.0 needs transformers>=4.56.2
    # Install in ONE call — single resolver pass prevents conflicts
    pip_install "training stack" \
        "trl>=1.2.0" \
        "transformers>=4.56.2" \
        "peft>=0.11.1" \
        "datasets>=2.19.2" \
        --quiet \
        && ok "  training stack ✓" \
        || warn "  training stack failed — some training features will be limited"

    info "Installing bitsandbytes..."
    pip_install "bitsandbytes" "bitsandbytes>=0.43.1" --quiet \
        && ok "  bitsandbytes ✓" \
        || {
            warn "  bitsandbytes CUDA build failed — trying CPU version..."
            "$PIP" install bitsandbytes --prefer-binary --quiet \
                && ok "  bitsandbytes ✓ (CPU)" \
                || warn "  bitsandbytes failed — 4-bit quantization disabled"
        }
    ok "Training dependencies installed"
}

# ── Optional: voice deps ──────────────────────────────────────────────────────
step_voice() {
    echo ""
    VOICE="${VOICE:-}"
    if [[ -z "$VOICE" ]]; then
        echo -e "${BOLD}  Voice input${NC} (Whisper STT + pyttsx3 TTS)"
        read -rp "  Install voice dependencies? [y/N] " VOICE
    fi
    [[ "$VOICE" =~ ^[Yy]$ ]] || { warn "Skipping voice deps"; return 0; }

    for pkg in "openai-whisper>=20231117" "pyttsx3>=2.90" "sounddevice>=0.4.6" "soundfile>=0.12.1" "keyboard>=0.13.5"; do
        pip_install "$pkg" "$pkg" --quiet \
            && ok "  $pkg ✓" \
            || warn "  $pkg failed — voice may be limited"
    done
    ok "Voice dependencies installed"
}

# ── Ollama ────────────────────────────────────────────────────────────────────
step_ollama() {
    if command -v ollama &>/dev/null; then
        ok "Ollama found: $(ollama --version 2>/dev/null || echo installed)"
        if ollama list 2>/dev/null | grep -qE '(mistral|codestral|llama|gemma|phi)'; then
            ok "Ollama model ready"
        else
            info "Pulling mistral model (~4 GB)..."
            ollama pull mistral \
                && ok "mistral ✓" \
                || warn "ollama pull failed — run manually: ollama pull mistral"
        fi
        return 0
    fi

    warn "Ollama not installed — required for bootstrap/shadow stage"
    AUTO_OLLAMA="${AUTO_OLLAMA:-}"
    if [[ -z "$AUTO_OLLAMA" ]]; then
        read -rp "  Install Ollama now? [y/N] " AUTO_OLLAMA
    fi

    if [[ "$AUTO_OLLAMA" =~ ^[Yy]$ ]]; then
        fix "Installing Ollama..."
        curl -fsSL https://ollama.ai/install.sh | sh \
            && ok "Ollama installed" \
            && ollama pull mistral \
            && ok "mistral ✓" \
            || warn "Ollama install failed — install manually: https://ollama.ai"
    else
        warn "Skipping Ollama — OCBrain will start but queries will fail until Ollama is running"
    fi
}

# ── Data dirs + project structure ────────────────────────────────────────────
step_dirs() {
    mkdir -p data/{raw,chunks,evals,gaps,exports}
    for d in core modules modules/coding modules/web_search \
              modules/knowledge modules/system_ctrl modules/_template \
              learning interface; do
        mkdir -p "$d"
        [[ -f "$d/__init__.py" ]] || touch "$d/__init__.py"
    done
    ok "Directories ready"
}

# ── Install verification ──────────────────────────────────────────────────────
step_verify() {
    echo ""
    info "Verifying installation..."
    local pass=0 fail_count=0

    _check() {
        local label="$1" module="$2"
        if "$PYTHON" -c "import $module" &>/dev/null 2>&1; then
            ok "  $label"; (( pass++ )) || true
        else
            fail "  $label (import failed)"; (( fail_count++ )) || true
        fi
    }

    _check "fastapi"               fastapi
    _check "uvicorn"               uvicorn
    _check "httpx"                 httpx
    _check "chromadb"              chromadb
    _check "sentence_transformers" sentence_transformers
    _check "pydantic"              pydantic
    _check "aiofiles"              aiofiles
    _check "yaml (PyYAML)"         yaml
    _check "click"                 click
    _check "rich"                  rich
    _check "trafilatura"           trafilatura
    _check "spacy"                 spacy

    echo ""
    if [[ $fail_count -eq 0 ]]; then
        ok "All $pass packages verified ✓"
    else
        warn "$fail_count package(s) failed — check $LOG_FILE"
        warn "To fix: source .venv/bin/activate && pip install -r requirements.txt"
    fi
}

# =============================================================================
#  MAIN — run all steps
# =============================================================================
echo ""
cat << 'BANNER'
  ╔══════════════════════════════════════════════════╗
  ║   OCBrain — Self-Healing Setup                   ║
  ║   Resumes from last successful step on re-run    ║
  ╚══════════════════════════════════════════════════╝
BANNER
echo ""

run_step "s1_sysdeps"    "System build dependencies"         step_sysdeps
run_step "s2_rust"       "Rust / cargo"                      step_rust
run_step "s3_pyenv"      "pyenv"                             step_pyenv
run_step "s4_python"     "Python $TARGET_PYTHON (locked)"    step_python
run_step "s5_venv"       "Virtual environment"               step_venv
run_step "s6_pip"        "pip / wheel / setuptools upgrade"  step_pip_upgrade
run_step "s7_core_a"     "Core packages (Phase A)"           step_core_a
run_step "s8_core_b"     "Core packages (Phase B — compile)" step_core_b
run_step "s9_torch"     "torch (CPU — always required)"     step_torch_cpu
run_step "s9_chromadb"   "chromadb + sqlite3 check"          step_chromadb
run_step "s10_sentrans"  "sentence-transformers stack"       step_sentence_transformers
run_step "s11_project"   "OCBrain package install"           step_project
run_step "s12_spacy"     "spaCy language model"              step_spacy_model
step_training   # optional — not wrapped in run_step (interactive prompt)
step_voice      # optional — not wrapped in run_step (interactive prompt)
run_step "s13_ollama"    "Ollama"                            step_ollama
run_step "s14_dirs"      "Data directories"                  step_dirs
step_verify

rm -f /tmp/ocbrain_pip.err /tmp/ocbrain_spacy.err 2>/dev/null || true

echo ""
cat << 'DONE'
  ╔═══════════════════════════════════════════════════╗
  ║   Setup complete!                                 ║
  ║                                                   ║
  ║   Start OCBrain:                                  ║
  ║     source .venv/bin/activate                     ║
  ║     python main.py                                ║
  ║                                                   ║
  ║   Web UI:   http://localhost:7437                 ║
  ║   API docs: http://localhost:7437/docs            ║
  ║                                                   ║
  ║   CLI: ocbrain "your question"                    ║
  ╚═══════════════════════════════════════════════════╝
DONE
