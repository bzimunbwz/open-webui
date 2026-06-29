#!/usr/bin/env bash
# ClaudeSK one-shot deploy for a 2 GB DigitalOcean droplet.
# Run as root from inside the cloned repo:  bash deploy.sh
set -e

cd "$(dirname "$0")"

# 1) Swap — REQUIRED on 2 GB. Covers the heavy frontend build + runtime spikes
#    so the container is never OOM-killed.
if ! swapon --show | grep -q '/swapfile'; then
  echo ">> Creating 4 GB swap file..."
  fallocate -l 4G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=4096
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=10 >/dev/null 2>&1 || true
  echo ">> Swap active:"; swapon --show
fi

# 2) Docker
if ! command -v docker >/dev/null 2>&1; then
  echo ">> Installing Docker..."
  curl -fsSL https://get.docker.com | sh
fi

# 3) .env with auto-generated secrets (edit afterwards to add provider/Cloudflare keys)
if [ ! -f .env ]; then
  cp .env.example .env
  SECRET=$(openssl rand -hex 32)
  ADMIN="sk-$(openssl rand -hex 16)"
  sed -i "s|change-me-to-a-long-random-string|$SECRET|" .env
  sed -i "s|change-me-strong-admin-key|$ADMIN|" .env
  echo ">> Created .env with generated WEBUI_SECRET_KEY and GATEWAY_ADMIN_KEY."
  echo ">> Edit it to add CLOUDFLARE_* if needed:  nano .env"
fi

# 4) Build + start (first build is slow on 2 GB — swap makes it succeed; be patient)
echo ">> Building and starting containers (first build can take 10-20 min on 2 GB)..."
docker compose -f docker-compose.claudesk.yml up -d --build

echo ""
echo ">> Done. Useful commands:"
echo "   docker compose -f docker-compose.claudesk.yml ps"
echo "   docker compose -f docker-compose.claudesk.yml logs -f open-webui"
echo "   free -h    # check memory + swap"
