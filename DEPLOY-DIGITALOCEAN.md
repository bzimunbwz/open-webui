# Deploying ClaudeSK on DigitalOcean

Runs your customized **Open WebUI** + the **facade gateway** + **Caddy** (automatic HTTPS)
on a single droplet, with **persistent volumes** so settings, users, providers and
subscriptions never reset, and enough RAM so it never OOMs.

## 1. Create the droplet
- DigitalOcean → **Create → Droplet**
- Image: **Ubuntu 24.04 LTS**
- Size: Basic → Regular → **4 GB RAM / 2 vCPU** (~$24/mo; your $205 credit ≈ 8 months).
  2 GB works only with the slim build + `RAG_EMBEDDING_ENGINE` offload.
- Add your SSH key → **Create**. Note the **public IP**.

## 2. Point the domain
In your DNS provider for `claudesk.pro`, add two **A records → droplet IP**:

| Host | Type | Value |
|------|------|-------|
| `claudesk.pro` (or `@`) | A | `<droplet-ip>` |
| `gateway.claudesk.pro` | A | `<droplet-ip>` |

Wait a few minutes for DNS to propagate.

## 3. Install Docker
SSH in (`ssh root@<droplet-ip>`) and run:
```
curl -fsSL https://get.docker.com | sh
```

## 4. Get the code
```
git clone https://github.com/bzimunbwz/open-webui.git
cd open-webui
```

## 5. Configure env
```
cp .env.example .env
nano .env
```
Set at least:
- `WEBUI_SECRET_KEY` → run `openssl rand -hex 32` and paste the value
- `GATEWAY_ADMIN_KEY` → a strong secret (replaces the old hardcoded `sk-gateway-admin`)
- `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_KEY` → only if you use Cloudflare Workers AI

## 6. Launch
```
docker compose -f docker-compose.claudesk.yml up -d --build
```
First build takes several minutes. Check status / logs:
```
docker compose -f docker-compose.claudesk.yml ps
docker compose -f docker-compose.claudesk.yml logs -f open-webui
```
Caddy auto-issues HTTPS certs for `claudesk.pro` and `gateway.claudesk.pro`.

## 7. First-time setup in the app
1. Open **https://claudesk.pro** → create the admin account (first user becomes admin).
2. **Admin → Settings → Connections → add an OpenAI connection:**
   - Base URL: `http://gateway:3000/v1`  (internal docker network — fast)
   - API Key: any value (e.g. `sk-internal`)
   This makes your facade models (Claude Opus 4.8, etc.) appear.
3. **Admin → Providers page:** set
   - Gateway URL: `https://gateway.claudesk.pro`
   - Admin key: your `GATEWAY_ADMIN_KEY`
   Then **re-add your provider API keys** (the ones you exported from the old gateway).
4. Logos/branding ship inside the build; `WEBUI_NAME` comes from `.env`.

## 8. Updating later
```
cd open-webui && git pull
docker compose -f docker-compose.claudesk.yml up -d --build
```
Data persists in the named volumes (`openwebui-data`, `gateway-data`) across rebuilds.

## 9. Housekeeping
- **Firewall:** DigitalOcean → Networking → Firewall → allow inbound **22, 80, 443**.
- **Memory check:** `docker stats`. If open-webui is near the limit, set
  `RAG_EMBEDDING_ENGINE` to offload embeddings, or resize the droplet.
- **Backup the data:**
  ```
  docker run --rm -v open-webui_openwebui-data:/d -v $PWD:/b alpine tar czf /b/owui-backup.tgz -C /d .
  docker run --rm -v open-webui_gateway-data:/d  -v $PWD:/b alpine tar czf /b/gw-backup.tgz  -C /d .
  ```

## Why this fixes the Railway problems
- **No settings reset:** data lives in persistent Docker volumes on the droplet disk.
- **No OOM restarts:** you control the RAM (4 GB), unlike Railway's small instances.
- **One repo build:** your custom UI, branding, permissions and gateway all ship together.
