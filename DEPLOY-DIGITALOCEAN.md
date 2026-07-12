# ClaudeSK → DigitalOcean migration runbook

You have paying customers, so this runbook is built around one rule: **Railway keeps
serving traffic until DigitalOcean is proven working.** Nothing is deleted, and DNS is
the last thing that moves. If DO misbehaves you flip DNS back and lose nothing.

Total hands-on time: about an hour, most of it waiting on a Docker build.

---

## What actually has to survive

| Data | Where it lives on Railway | How it moves |
|---|---|---|
| Users, passwords, chats, admin settings | `webui.db` (Open WebUI volume) | Admin panel → Download Database |
| Subscriptions, coupons, packages, credits, usage, providers | `*.json` (gateway volume) | `GET /admin/export` → `POST /admin/import` |
| Uploaded files (docs users attached) | `uploads/` (Open WebUI volume) | ⚠️ See "Known losses" |

**Known losses — read this before starting.**

1. **Sessions.** Railway auto-generated a `WEBUI_SECRET_KEY` and stored it on the
   volume, where we cannot reach it. On DO you set a fresh one, which invalidates
   existing login tokens. **Every user has to log in again.** Their accounts,
   passwords, chats and subscriptions are all intact — it is a re-login, not data loss.
   Post a heads-up to your customers before cutover.
2. **Uploaded files.** `uploads/` is not inside `webui.db` and Railway gives no shell,
   so previously attached documents will show broken links. Chats themselves are fine.
   If this matters, say so before cutover and the files can be pulled out through the
   Open WebUI files API first.

---

## Phase 0 — Back up, while Railway is still live

Do this **first**, before touching anything.

### 0a. Open WebUI database

Admin Panel → Settings → **Database** → **Download Database**. You get `webui.db`.
Keep it somewhere safe. This one file is your users, chats and settings.

### 0b. Gateway data

```bash
curl -H "Authorization: Bearer sk-gateway-admin" \
  https://webapp-2nd-service-production.up.railway.app/admin/export \
  -o gateway-backup.json
```

Open the file and sanity-check it before you trust it:

```bash
python -c "import json;d=json.load(open('gateway-backup.json'));print(d['count'],'files:',list(d['files']))"
```

You should see `subscriptions.json`, `coupons.json`, `packages.json`, `credits.json`,
`usage.json`, `providers.json`, `models.json`, `tiers.json`. **If `subscriptions.json`
is missing or empty, stop** — that is your paying customers. Do not proceed.

---

## Phase 1 — Droplet

Create a Droplet: **Ubuntu 24.04**, **4 GB RAM / 2 vCPU / 80 GB SSD** (~$24/mo).
Don't go below 4 GB — Open WebUI's build and the Python gateway will OOM on 2 GB,
which is the same wall you hit on Railway's trial. Add your SSH key at creation.

```bash
ssh root@YOUR_DROPLET_IP

# Docker
curl -fsSL https://get.docker.com | sh

# Swap — cheap insurance against an OOM during the frontend build
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Firewall
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable

# Code
git clone https://github.com/bzimunbwz/open-webui.git /opt/claudesk
cd /opt/claudesk
```

### Configure

```bash
cp .env.example .env
openssl rand -hex 32   # -> paste as WEBUI_SECRET_KEY
openssl rand -hex 32   # -> paste as GATEWAY_ADMIN_KEY
nano .env
```

Fill in `WEBUI_SECRET_KEY`, `GATEWAY_ADMIN_KEY`, `BYNARA_API_KEY`, `CLOD_API_KEY`,
and any Cloudflare keys. **Use a real random `GATEWAY_ADMIN_KEY`** — the old
`sk-gateway-admin` default is visible in your public repo, meaning anyone can call
your `/admin/*` endpoints today.

---

## Phase 2 — DNS

At your registrar, create **A records → droplet IP**:

| Type | Name | Value |
|---|---|---|
| A | `@` | droplet IP |
| A | `www` | droplet IP |
| A | `gateway` | droplet IP |

Set **TTL to 300 seconds** now, so the cutover is fast and reversible.

Point `gateway` at the droplet immediately — it's a new hostname, nothing depends on
it yet. Leave `@` and `www` on Railway until Phase 4.

---

## Phase 3 — Deploy and verify (Railway still serving customers)

```bash
cd /opt/claudesk
docker compose -f docker-compose.claudesk.yml up -d --build
docker compose -f docker-compose.claudesk.yml logs -f
```

The first build takes 10–20 minutes. Caddy will issue certificates automatically once
DNS resolves.

**Restore your data:**

```bash
# Gateway — subscriptions, coupons, usage
scp gateway-backup.json root@YOUR_DROPLET_IP:/opt/claudesk/     # from your laptop

curl -X POST https://gateway.claudesk.pro/admin/import \
  -H "Authorization: Bearer YOUR_NEW_GATEWAY_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  --data @gateway-backup.json
```

The response echoes what it restored — confirm `subscriptions` is non-zero.

```bash
# Open WebUI — users and chats
scp webui.db root@YOUR_DROPLET_IP:/opt/claudesk/                # from your laptop
cd /opt/claudesk && ./restore.sh --webui-db ./webui.db
```

**Verify before cutting over**, using the gateway subdomain that's already live:

```bash
curl https://gateway.claudesk.pro/health
curl https://gateway.claudesk.pro/v1/models
```

Then edit `/etc/hosts` on your own laptop to point `claudesk.pro` at the droplet IP,
and browse the site as if it were live: log in as a real user, send a message, check a
subscription shows correctly, confirm a long code answer isn't truncated. Only when
that all passes do you touch DNS.

---

## Phase 4 — Cutover

1. **Re-export the gateway data from Railway one last time** (Phase 0b) and re-import
   it to DO. Customers have been buying and chatting during Phase 3; this captures
   anything new. Same for `webui.db` if chat history matters.
2. Flip the `@` and `www` A records to the droplet IP.
3. Watch it: `docker compose -f docker-compose.claudesk.yml logs -f`
4. **Leave Railway running for 48 hours.** It costs a few dollars and it is your
   instant rollback: if DO breaks, point DNS back and you are live again in 5 minutes.
5. Once you're confident, tear Railway down.

---

## After you're live

**Back up on a schedule.** `backup.sh` snapshots both volumes:

```bash
cd /opt/claudesk && ./backup.sh          # -> backups/<timestamp>/
crontab -e
0 3 * * * cd /opt/claudesk && ./backup.sh >> /var/log/claudesk-backup.log 2>&1
```

It keeps the 14 most recent snapshots. Restore any of them with
`./restore.sh backups/<timestamp>`.

**Get the backups off the box.** A snapshot on the same droplet does not protect you
from losing the droplet. Enable DigitalOcean's weekly Droplet Backups (20% of droplet
cost), or push `backups/` to Spaces/S3.

**Watch the disk.** `df -h` and `du -sh /var/lib/docker/volumes/*`. 80 GB is a lot of
headroom compared to Railway's 5 GB, but the ChromaDB vector store is what filled the
old volume, so it's worth a glance now and then.

**Costs.** The $200 DigitalOcean credit expires **60 days after signup** and does not
roll over. After that a 4 GB droplet is ~$24/mo. Set a calendar reminder for day 55 so
the expiry doesn't surprise you.

---

## Updating later

```bash
cd /opt/claudesk
./backup.sh
git pull
docker compose -f docker-compose.claudesk.yml up -d --build
```
