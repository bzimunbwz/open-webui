# Deploying ClaudeSK on DigitalOcean (2 GB droplet)

Runs your customized **Open WebUI** + the **facade gateway** + **Caddy** (auto HTTPS) on one
droplet, with **persistent volumes** (settings/users/providers never reset) and a **swap file**
so 2 GB of RAM doesn't OOM.

> Tuned for the **$18/mo — 2 vCPU / 2 GB / 60 GB SSD** droplet. A 4 GB swap file makes the
> heavy frontend build and runtime spikes fit. Avoid heavy RAG/Knowledge use (local embeddings
> load PyTorch into RAM and lean on swap = slow); normal chat + the facade gateway + Claude Code
> run comfortably.

## 1. Create the droplet
- DigitalOcean → **Create → Droplet** → Ubuntu 24.04 LTS
- Size: **Basic / Regular / 2 GB / 2 vCPU ($18/mo)**
- Add your SSH key → Create → note the **public IP**.

## 2. DNS — two A records → droplet IP
| Host | Type | Value |
|------|------|-------|
| `claudesk.pro` (`@`) | A | `<droplet-ip>` |
| `gateway.claudesk.pro` | A | `<droplet-ip>` |

## 3. One-shot deploy
SSH in (`ssh root@<droplet-ip>`) and run:
```
curl -fsSL https://get.docker.com | sh      # (deploy.sh also does this if skipped)
git clone https://github.com/bzimunbwz/open-webui.git
cd open-webui
bash deploy.sh
```
`deploy.sh` automatically: creates a **4 GB swap file**, installs Docker, generates a `.env`
with random `WEBUI_SECRET_KEY` + `GATEWAY_ADMIN_KEY`, then builds & starts everything.

> The **first build is slow on 2 GB (10–20 min)** — that's the SvelteKit build compiling.
> Swap is what keeps it from being killed. Watch it:
> `docker compose -f docker-compose.claudesk.yml logs -f open-webui`

If you'd rather do it manually instead of the script:
```
# create swap first (critical on 2 GB)
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
# then:
cp .env.example .env && nano .env     # set WEBUI_SECRET_KEY, GATEWAY_ADMIN_KEY, CLOUDFLARE_*
docker compose -f docker-compose.claudesk.yml up -d --build
```

## 4. First-time setup in the app
1. Open **https://claudesk.pro** → create the admin account (first user = admin).
2. **Admin → Settings → Connections → add an OpenAI connection:**
   - Base URL: `http://gateway:3000/v1`  (internal docker network)
   - API Key: any value (e.g. `sk-internal`)
   → your facade models (Claude Opus 4.8, etc.) appear.
3. **Admin → Providers:** set Gateway URL `https://gateway.claudesk.pro` + your `GATEWAY_ADMIN_KEY`,
   then re-add the provider API keys you exported from the old gateway.

## 5. Keep RAM healthy on 2 GB
- `free -h` shows RAM + swap; `docker stats` shows per-container usage.
- Expected idle: Open WebUI ~0.5–0.8 GB, gateway ~0.1 GB, Caddy ~0.03 GB → fits in 2 GB.
- Heavy spikes (frontend build, or RAG embedding if you upload Knowledge) spill to swap — fine,
  just slower. If you use Knowledge a lot, set `RAG_EMBEDDING_ENGINE` to an external API in `.env`.
- **Firewall:** DigitalOcean → Networking → Firewall → allow inbound 22, 80, 443.

## 6. Update later
```
cd open-webui && git pull
docker compose -f docker-compose.claudesk.yml up -d --build
```
Data persists in volumes `openwebui-data` (`/app/backend/data`) and `gateway-data` (`/app/data`).

## 7. Backups
```
docker run --rm -v open-webui_openwebui-data:/d -v $PWD:/b alpine tar czf /b/owui-backup.tgz -C /d .
docker run --rm -v open-webui_gateway-data:/d  -v $PWD:/b alpine tar czf /b/gw-backup.tgz  -C /d .
```

## Why this fixes Railway's problems
- **Persistent volumes** → settings, users, providers, subscriptions survive restarts.
- **Swap on a fixed-RAM box** → no OOM crash-loops (the thing that was wiping/restarting you).
- **Single source build** → your UI, branding, permissions, and gateway ship together.
