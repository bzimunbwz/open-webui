#!/usr/bin/env bash
# ClaudeSK restore — loads a snapshot back into the docker volumes.
#   ./restore.sh backups/20260712-101500
# Also accepts a raw webui.db + gateway JSON dir migrated from Railway:
#   ./restore.sh --webui-db ./webui.db --gateway-dir ./gateway-data
set -euo pipefail

if [[ "${1:-}" == "--webui-db" ]]; then
  DB="${2:?path to webui.db}"; shift 2
  GWDIR=""
  if [[ "${1:-}" == "--gateway-dir" ]]; then GWDIR="${2:?}"; fi

  echo "==> Stopping services"
  docker compose -f docker-compose.claudesk.yml stop open-webui gateway

  echo "==> Restoring webui.db"
  docker run --rm -v openwebui-data:/data -v "$(realpath "$(dirname "${DB}")")":/src \
    alpine sh -c "cp /src/$(basename "${DB}") /data/webui.db && chown 0:0 /data/webui.db"

  if [[ -n "${GWDIR}" ]]; then
    echo "==> Restoring gateway JSON data"
    docker run --rm -v gateway-data:/data -v "$(realpath "${GWDIR}")":/src \
      alpine sh -c "cp -a /src/. /data/"
  fi

  echo "==> Starting services"
  docker compose -f docker-compose.claudesk.yml start gateway open-webui
  echo "==> Restore complete."
  exit 0
fi

SRC="${1:?usage: ./restore.sh backups/<timestamp>}"
echo "==> Restoring from ${SRC}"

docker compose -f docker-compose.claudesk.yml stop open-webui gateway

docker run --rm -v openwebui-data:/data -v "$(realpath "${SRC}")":/backup \
  alpine sh -c "rm -rf /data/* && tar xzf /backup/openwebui-data.tar.gz -C /data"

docker run --rm -v gateway-data:/data -v "$(realpath "${SRC}")":/backup \
  alpine sh -c "rm -rf /data/* && tar xzf /backup/gateway-data.tar.gz -C /data"

docker compose -f docker-compose.claudesk.yml start gateway open-webui
echo "==> Restore complete."
