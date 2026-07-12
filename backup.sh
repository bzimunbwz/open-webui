#!/usr/bin/env bash
# ClaudeSK backup — snapshots both docker volumes to ./backups/<timestamp>/
# Run on the droplet:  ./backup.sh
# Restore:             ./restore.sh backups/<timestamp>
set -euo pipefail

TS="$(date -u +%Y%m%d-%H%M%S)"
DEST="$(pwd)/backups/${TS}"
mkdir -p "${DEST}"

echo "==> Backing up to ${DEST}"

# Open WebUI data: webui.db (users, chats, settings) + uploads
docker run --rm \
  -v openwebui-data:/data:ro \
  -v "${DEST}":/backup \
  alpine tar czf /backup/openwebui-data.tar.gz -C /data .

# Gateway data: subscriptions, coupons, packages, credits, usage, providers
docker run --rm \
  -v gateway-data:/data:ro \
  -v "${DEST}":/backup \
  alpine tar czf /backup/gateway-data.tar.gz -C /data .

echo "==> Done:"
ls -lh "${DEST}"

# Keep the 14 most recent snapshots
cd "$(pwd)/backups" && ls -1dt */ | tail -n +15 | xargs -r rm -rf
echo "==> Old snapshots pruned (keeping 14)."
