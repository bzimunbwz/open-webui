#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Container entry point for Open WebUI.
# Handles secret key generation, optional Ollama/CUDA/Playwright setup,
# HuggingFace Space deployment, and launches the uvicorn server.
# ---------------------------------------------------------------------------

# Default optional env vars that we test below with bash's `,,` lowercase
# expansion. The two can't be combined inline (`${VAR:-default,,}` makes
# the default literal `,,`), so we normalise once up front and the simple
# `${VAR,,}` form stays safe under `set -u` everywhere else.
: "${WEB_LOADER_ENGINE:=}" "${USE_OLLAMA_DOCKER:=}" "${USE_CUDA_DOCKER:=}"

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
cd "$SCRIPT_DIR" || exit 1

# ── Data volume report + optional emergency cleanup ──────────────────────────
# The data volume fills up over time (ChromaDB vector store, downloaded model
# cache, user uploads). A full volume stops the app from booting, and on hosts
# with no shell access there is otherwise no way to see or fix it. So: always
# report usage into the logs, and purge only when explicitly asked to.

DATA_PATH="${DATA_DIR:-${SCRIPT_DIR}/data}"

if [[ -d "$DATA_PATH" ]]; then
  echo "── Data volume: ${DATA_PATH}"
  df -h "$DATA_PATH" 2>/dev/null || true
  echo "── Largest entries:"
  du -sh "${DATA_PATH}"/* 2>/dev/null | sort -rh | head -20 || true
fi

# CLEANUP_ON_BOOT — comma-separated targets to delete before starting:
#   cache      downloaded models, tiktoken   (regenerated automatically — safe)
#   vector_db  ChromaDB embeddings           (Knowledge/docs need re-indexing)
#   uploads    user-uploaded files           (chat text kept, attachments break)
#   all        all three
# Set it, deploy once to reclaim the space, then REMOVE it again — otherwise
# every future restart wipes these directories.
if [[ -n "${CLEANUP_ON_BOOT:-}" && -d "$DATA_PATH" ]]; then
  echo "── CLEANUP_ON_BOOT='${CLEANUP_ON_BOOT}' — purging before start"
  IFS=',' read -ra _targets <<< "${CLEANUP_ON_BOOT}"
  for _t in "${_targets[@]}"; do
    _t="$(echo "$_t" | tr -d '[:space:]')"
    case "$_t" in
      all)
        rm -rf "${DATA_PATH:?}/vector_db" "${DATA_PATH:?}/cache" "${DATA_PATH:?}/uploads"
        echo "   purged vector_db, cache, uploads"
        ;;
      vector_db|cache|uploads)
        rm -rf "${DATA_PATH:?}/${_t}"
        echo "   purged ${_t}"
        ;;
      "") ;;
      *) echo "   unknown target '${_t}' — skipped" ;;
    esac
  done
  mkdir -p "${DATA_PATH}/cache" "${DATA_PATH}/uploads"
  echo "── After cleanup:"
  df -h "$DATA_PATH" 2>/dev/null || true
fi

# ── Playwright browser installation (if configured) ──────────────────────────

if [[ "${WEB_LOADER_ENGINE,,}" == "playwright" ]]; then
  if [[ -z "${PLAYWRIGHT_WS_URL:-}" ]]; then
    echo "Installing Playwright Chromium browser..."
    playwright install chromium
    playwright install-deps chromium
  fi
  python -c "import nltk; nltk.download('punkt_tab')"
fi

# ── Secret key setup ─────────────────────────────────────────────────────────

KEY_FILE="${WEBUI_SECRET_KEY_FILE:-.webui_secret_key}"
PORT="${PORT:-8080}"
HOST="${HOST:-0.0.0.0}"

if [[ -z "${WEBUI_SECRET_KEY:-}" && -z "${WEBUI_JWT_SECRET_KEY:-}" ]]; then
  echo "No WEBUI_SECRET_KEY environment variable set, loading from file."

  if [[ ! -f "$KEY_FILE" ]]; then
    echo "Generating new WEBUI_SECRET_KEY..."
    head -c 12 /dev/random | base64 > "$KEY_FILE"
  fi

  echo "Loading WEBUI_SECRET_KEY from ${KEY_FILE}"
  WEBUI_SECRET_KEY=$(cat "$KEY_FILE")
fi

# ── Ollama (bundled Docker image) ────────────────────────────────────────────

if [[ "${USE_OLLAMA_DOCKER,,}" == "true" ]]; then
  echo "Starting bundled ollama serve..."
  ollama serve &
fi

# ── CUDA library paths ──────────────────────────────────────────────────────

if [[ "${USE_CUDA_DOCKER,,}" == "true" ]]; then
  echo "CUDA enabled — extending LD_LIBRARY_PATH for torch/cudnn libraries."
  export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:/usr/local/lib/python3.11/site-packages/torch/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib"
fi

# ── HuggingFace Space deployment ─────────────────────────────────────────────

if [[ -n "${SPACE_ID:-}" ]]; then
  echo "Configuring for HuggingFace Space deployment..."

  if [[ -n "${ADMIN_USER_EMAIL:-}" && -n "${ADMIN_USER_PASSWORD:-}" ]]; then
    echo "Creating admin user for Space..."
    WEBUI_SECRET_KEY="${WEBUI_SECRET_KEY:-}" \
      uvicorn open_webui.main:app --host "$HOST" --port "$PORT" --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" &
    webui_pid=$!

    echo "Waiting for server to become healthy..."
    until curl -sf "http://localhost:${PORT}/health" > /dev/null 2>&1; do
      sleep 1
    done

    echo "Registering admin user..."
    curl -sS -X POST "http://localhost:${PORT}/api/v1/auths/signup" \
      -H "Accept: application/json" \
      -H "Content-Type: application/json" \
      -d "{\"email\": \"${ADMIN_USER_EMAIL}\", \"password\": \"${ADMIN_USER_PASSWORD}\", \"name\": \"Admin\"}"

    echo "Restarting server..."
    kill "$webui_pid"
    wait "$webui_pid" 2>/dev/null || true
  fi

  export WEBUI_URL="${SPACE_HOST}"
fi

# ── Launch uvicorn ───────────────────────────────────────────────────────────

PYTHON_CMD=$(command -v python3 || command -v python)
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"

if [[ "$#" -gt 0 ]]; then
  ARGS=("$@")
else
  ARGS=(--workers "$UVICORN_WORKERS")
fi

exec env WEBUI_SECRET_KEY="${WEBUI_SECRET_KEY:-}" \
  "$PYTHON_CMD" -m uvicorn open_webui.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
    "${ARGS[@]}"