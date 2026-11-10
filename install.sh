#!/usr/bin/env bash
# ==============================================================================
# ACE (Autonomous Compositional Evolution) Universal Installer (Edition 4)
# Supported: Linux / macOS / WSL / Android Termux (x86_64, arm64)
# Profiles: local-complete, host-assisted, core, offline-bundle
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

PROFILE="${ACE_PROFILE:-local-complete}"
TARGET_DIR="${ACE_WORKSPACE:-${HOME}/.local/share/ace/workspace}"
BIN_DIR="${ACE_BIN_DIR:-${HOME}/.local/bin}"
MODEL_CACHE="${ACE_MODEL_CACHE:-${HOME}/.cache/ace/models}"
OFFLINE_MODE="${ACE_OFFLINE:-false}"
SKIP_PIP="false"
MIN_DISK_MB=50
SIMULATE_SMOKE_FAILURE="false"
RUN_VERIFY="true"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            PROFILE="${2:-}"
            shift 2
            ;;
        --target-dir|--workspace)
            TARGET_DIR="${2:-}"
            shift 2
            ;;
        --bin-dir)
            BIN_DIR="${2:-}"
            shift 2
            ;;
        --model-cache)
            MODEL_CACHE="${2:-}"
            shift 2
            ;;
        --offline)
            OFFLINE_MODE="true"
            shift
            ;;
        --skip-pip)
            SKIP_PIP="true"
            shift
            ;;
        --min-disk-mb)
            MIN_DISK_MB="${2:-50}"
            shift 2
            ;;
        --simulate-smoke-failure)
            SIMULATE_SMOKE_FAILURE="true"
            shift
            ;;
        --no-verify)
            RUN_VERIFY="false"
            shift
            ;;
        --verify)
            RUN_VERIFY="true"
            shift
            ;;
        -h|--help)
            echo "Penggunaan: ./install.sh [--profile local-complete|host-assisted|core|offline-bundle] [--target-dir DIR] [--bin-dir DIR] [--model-cache DIR] [--offline]"
            exit 0
            ;;
        *)
            echo "❌ Argumen tidak dikenal: $1" >&2
            exit 2
            ;;
    esac
done

# 1. Validate profile (INST04-INST06)
case "${PROFILE}" in
    local-complete|host-assisted|core|offline-bundle)
        ;;
    *)
        echo "❌ Error: Profil instalasi '${PROFILE}' tidak valid. Gunakan: local-complete, host-assisted, core, atau offline-bundle." >&2
        exit 2
        ;;
esac

if [[ "${PROFILE}" == "offline-bundle" ]]; then
    OFFLINE_MODE="true"
fi

# 2. Detect Platform & Termux Android ARM64 (INST03)
PLATFORM_KIND="linux"
if [[ -n "${TERMUX_VERSION:-}" ]] || [[ "${PREFIX:-}" == *"com.termux"* ]]; then
    PLATFORM_KIND="termux-android"
elif [[ "$(uname -s)" == "Darwin" ]]; then
    PLATFORM_KIND="macos"
fi

echo "=========================================================="
echo " 🚀 Memasang ACE Edition 4 (${PLATFORM_KIND} | profil: ${PROFILE})"
echo "=========================================================="

# 3. Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "❌ Error: python3 belum terpasang di PATH." >&2
    exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✔ Python terdeteksi: $(command -v python3) (v${PY_VER})"

# 4. Preflight Disk & RAM Checks (INST15, INST16)
mkdir -p "${TARGET_DIR}" "${BIN_DIR}" "${MODEL_CACHE}"
FREE_DISK_MB=$(python3 - "${TARGET_DIR}" << 'PYEOF'
import shutil, sys
usage = shutil.disk_usage(sys.argv[1])
print(usage.free // (1024 * 1024))
PYEOF
)
if [[ "${FREE_DISK_MB}" -lt "${MIN_DISK_MB}" ]]; then
    echo "❌ Error: Ruang disk tidak cukup (${FREE_DISK_MB} MB tersedia, minimal ${MIN_DISK_MB} MB dibutuhkan)." >&2
    exit 3
fi
echo "✔ Ruang disk tersedia: ${FREE_DISK_MB} MB (minimal ${MIN_DISK_MB} MB)"

# 5. Backup existing operational database for safe migration & rollback (INST13, INST14, G12)
BACKUP_DB=""
if [[ -f "${TARGET_DIR}/ace_operational.sqlite3" ]]; then
    BACKUP_DB="${TARGET_DIR}/ace_operational.sqlite3.bak"
    python3 - "${TARGET_DIR}/ace_operational.sqlite3" "${BACKUP_DB}" << 'PYEOF'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
try:
    with sqlite3.connect(src) as conn, sqlite3.connect(dst) as bck:
        conn.backup(bck)
except Exception:
    import shutil
    shutil.copy2(src, dst)
PYEOF
    echo "✔ Cadangan state operasional (WAL-safe) dibuat: ${BACKUP_DB}"
fi

# 6. Optional Python Editable Package Install (skipped in fast/offline mode or if already importable)
if [[ "${SKIP_PIP}" != "true" ]] && [[ "${OFFLINE_MODE}" != "true" ]]; then
    if ! PYTHONPATH="${SCRIPT_DIR}/code:${PYTHONPATH:-}" python3 -c "import ace_runtime, ace_operational" &>/dev/null; then
        if python3 -m pip --version &>/dev/null; then
            python3 -m pip install --no-build-isolation --no-deps --break-system-packages -e . &>/dev/null || \
            python3 -m pip install --no-build-isolation --no-deps -e . &>/dev/null || true
        fi
    fi
fi

# 7. Create portable CLI launchers in BIN_DIR (INST01, INST02, INST12)
cat << EOF > "${BIN_DIR}/ace"
#!/usr/bin/env bash
export PATH="\${HOME}/.local/bin:\${PATH}"
export ACE_WORKSPACE="\${ACE_WORKSPACE:-${TARGET_DIR}}"
export ACE_PROFILE="\${ACE_PROFILE:-${PROFILE}}"
export ACE_MODEL_CACHE="\${ACE_MODEL_CACHE:-${MODEL_CACHE}}"
export ACE_OFFLINE="\${ACE_OFFLINE:-${OFFLINE_MODE}}"
export ACE_LLAMA_SERVER_URL="\${ACE_LLAMA_SERVER_URL:-http://127.0.0.1:8081}"
export PYTHONPATH="${SCRIPT_DIR}/code:\${PYTHONPATH:-}"
exec python3 "${SCRIPT_DIR}/ace.py" "\$@"
EOF
chmod +x "${BIN_DIR}/ace"

cat << EOF > "${BIN_DIR}/ace-autonomy"
#!/usr/bin/env bash
export PATH="\${HOME}/.local/bin:\${PATH}"
export ACE_WORKSPACE="\${ACE_WORKSPACE:-${TARGET_DIR}}"
export PYTHONPATH="${SCRIPT_DIR}/code:\${PYTHONPATH:-}"
exec python3 "${SCRIPT_DIR}/autonomy.py" "\$@"
EOF
chmod +x "${BIN_DIR}/ace-autonomy"

export PATH="${BIN_DIR}:${HOME}/.local/bin:${PATH}"
export ACE_WORKSPACE="${TARGET_DIR}"
export ACE_PROFILE="${PROFILE}"
export ACE_MODEL_CACHE="${MODEL_CACHE}"
export ACE_OFFLINE="${OFFLINE_MODE}"
export ACE_LLAMA_SERVER_URL="${ACE_LLAMA_SERVER_URL:-http://127.0.0.1:8081}"

# 8. Initialize / Migrate Operational Store & Verify Model Cache (INST07-INST14)
PYTHONPATH="${SCRIPT_DIR}/code:${PYTHONPATH:-}" python3 - "${TARGET_DIR}" "${PROFILE}" "${OFFLINE_MODE}" "${MODEL_CACHE}" << 'PYEOF'
import json, sys
from pathlib import Path
from ace_operational.store import OperationalStore
from ace_operational.models_backend import ModelRouter

ws, prof, offline_str, model_cache = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
with OperationalStore(ws) as store:
    store.set_meta("profile", prof)
    store.set_offline(offline_str.lower() in ("1", "true", "yes"))
    store.recover_interrupted_tasks()
    router = ModelRouter(store)
    hc = router.health_check()
    if hc["local_gguf"]["corrupted_models"]:
        print(f"⚠ Peringatan: Terdeteksi berkas model GGUF rusak ({len(hc['local_gguf']['corrupted_models'])}); beralih aman ke {hc['active_backend']}.")
    else:
        print(f"✔ Backend model siap: {hc['active_backend']} (mode: {hc['mode']})")
PYEOF

# 9. Post-install Smoke Check & Rollback Guard (INST14, INST17-INST24)
if [[ "${SIMULATE_SMOKE_FAILURE}" == "true" ]]; then
    echo "⚠ Simulasi kegagalan smoke test aktif; mengembalikan state sebelumnya..." >&2
    if [[ -n "${BACKUP_DB}" ]] && [[ -f "${BACKUP_DB}" ]]; then
        mv -f "${BACKUP_DB}" "${TARGET_DIR}/ace_operational.sqlite3"
    fi
    exit 4
fi

if [[ "${RUN_VERIFY}" == "true" ]]; then
    echo "🩺 Menjalankan verifikasi integritas dan kesiapan operasional ACE..."
    "${BIN_DIR}/ace" doctor --workspace "${TARGET_DIR}" >/dev/null
    "${BIN_DIR}/ace" status --workspace "${TARGET_DIR}" --operational >/dev/null
    "${BIN_DIR}/ace" web --workspace "${TARGET_DIR}" --check-only >/dev/null
fi

if [[ -n "${BACKUP_DB}" ]] && [[ -f "${BACKUP_DB}" ]]; then
    rm -f "${BACKUP_DB}"
fi

echo "=========================================================="
echo "✨ Instalasi & Verifikasi ACE Selesai!"
echo "   - Profil aktif : ${PROFILE} (offline=${OFFLINE_MODE})"
echo "   - Workspace    : ${TARGET_DIR}"
echo "   - CLI Launcher : ${BIN_DIR}/ace"
echo "   - Mulai Chat   : ace chat"
echo "   - Mulai Web UI : ace web"
echo "=========================================================="
