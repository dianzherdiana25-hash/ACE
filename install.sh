#!/usr/bin/env bash
# ==============================================================================
# ACE (Autonomous Compositional Evolution) Installer & Environment Setup
# Supported: Linux / macOS / WSL (x86_64, arm64)
# Compatible: Antigravity VM, Local Dev, Headless Cloud Agents, CI/CD
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "=========================================================="
echo "    🚀 Installing ACE (Autonomous Compositional Evolution) "
echo "=========================================================="

# 1. Check Python version
if ! command -v python3 &>/dev/null; then
    echo "❌ Error: python3 is not installed or not in PATH."
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✔ Found Python: $(which python3) (v${PY_VER})"

# 2. Check for pip or uv
INSTALL_CMD=""
if python3 -m pip --version &>/dev/null; then
    INSTALL_CMD="python3 -m pip install --break-system-packages -e ."
elif command -v uv &>/dev/null; then
    INSTALL_CMD="uv pip install -e ."
else
    echo "⚠ Warning: pip/uv not found globally. Falling back to venv..."
    python3 -m venv .venv
    source .venv/bin/activate
    python3 -m pip install -e .
fi

# 3. Install ACE in editable mode
echo "📦 Installing ACE into Python user environment..."
if [ -n "${INSTALL_CMD}" ]; then
    ${INSTALL_CMD} || python3 -m pip install -e .
fi

# 4. Link CLI binaries to user bin (~/.local/bin) if not present
mkdir -p "${HOME}/.local/bin"
for bin_name in ace ace-autonomy; do
    if [ ! -f "${HOME}/.local/bin/${bin_name}" ]; then
        if [ "${bin_name}" = "ace" ]; then
            cat << 'EOF' > "${HOME}/.local/bin/ace"
#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ -f "${ROOT}/dianzherdiana25-hash/ACE/ace.py" ]; then
    exec python3 "${ROOT}/dianzherdiana25-hash/ACE/ace.py" "$@"
else
    exec python3 -m ace_runtime.cli "$@"
fi
EOF
        else
            cat << 'EOF' > "${HOME}/.local/bin/ace-autonomy"
#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ -f "${ROOT}/dianzherdiana25-hash/ACE/autonomy.py" ]; then
    exec python3 "${ROOT}/dianzherdiana25-hash/ACE/autonomy.py" "$@"
else
    exec python3 -m ace_autonomy.cli "$@"
fi
EOF
        fi
        chmod +x "${HOME}/.local/bin/${bin_name}"
    fi
done

export PATH="${HOME}/.local/bin:${PATH}"

# 5. Run Self-Diagnostics (ace doctor)
echo "🩺 Running ACE System Integrity Diagnostics..."
python3 ace.py doctor

echo "=========================================================="
echo "✨ ACE Installation & Verification Complete!"
echo "   - CLI available: 'ace' & 'ace-autonomy'"
echo "   - Python import: import ace_runtime, ace_smt, ace_egraph..."
echo "=========================================================="
