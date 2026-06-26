# ClaudeSK.pro — Deployment & Architecture Guide

> **Purpose of this file:** If you are an AI assistant (or developer) asked to modify, debug, or redeploy this project, read this file first. It explains the full architecture, every service, how they connect, and how to deploy.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Repository Structure](#repository-structure)
3. [Service 1: Open WebUI (Frontend + Backend)](#service-1-open-webui)
4. [Service 2: Facade Model Gateway](#service-2-facade-model-gateway)
5. [How They Connect](#how-they-connect)
6. [Deployment on Railway](#deployment-on-railway)
7. [Custom Domain Setup](#custom-domain-setup)
8. [Environment Variables Reference](#environment-variables-reference)
9. [Admin Panel Features](#admin-panel-features)
10. [Facade Model System Explained](#facade-model-system-explained)
11. [API Key Rotation & Fallback Logic](#api-key-rotation--fallback-logic)
12. [Common Modifications](#common-modifications)
13. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

This is a SaaS AI chat platform built on Open WebUI. It has TWO services:

```
┌─────────────────────────────────────────────────────┐
│                    Users (Browser)                   │
│                  https://claudesk.pro                │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────▼────────────────┐
          │   SERVICE 1: Open WebUI     │
          │   (Frontend + Backend)      │
          │   Port: 8080                │
          │   Dockerfile.railway        │
          │                             │
          │   Users see clean model     │
          │   names like:               │
          │   - Claude Opus 4.8         │
          │   - ChatGPT Codex 5.5      │
          │   - GPT-4o                  │
          │                             │
          │   Admin Panel has custom    │
          │   "Providers" tab           │
          └────────────┬────────────────┘
                       │ OpenAI-compatible API calls
                       │
          ┌────────────▼────────────────┐
          │   SERVICE 2: Gateway        │
          │   (Facade Model Proxy)      │
          │   Port: 3000                │
          │   gateway/Dockerfile        │
          │                             │
          │   Routes requests to        │
          │   backend LLM providers     │
          │   with fallback             │
          └────────────┬────────────────┘
                       │
        ┌──────────────┼──────────────────┐
        │              │                  │
   ┌────▼────┐   ┌────▼────┐      ┌─────▼─────┐
   │FreeModel│   │  LLM7   │      │   Z.AI    │   ... more providers
   │  .dev   │   │  .io    │      │           │
   └─────────┘   └─────────┘      └───────────┘
```

**Key concept: Facade Models.** Users never see real provider model IDs. They see admin-defined names like "Claude Opus 4.8". Behind each facade model, the gateway tries multiple providers in order. If provider A fails or hits rate limits, it automatically falls back to provider B, C, etc.

---

## Repository Structure

```
open-webui-main/
├── Dockerfile              # Original Open WebUI Dockerfile (builds from source, large)
├── Dockerfile.railway      # Slim Dockerfile for Railway (uses prebuilt image, recommended)
├── railway.json            # Railway build config for Open WebUI service
├── railway.toml            # Railway deploy config (healthcheck, mounts)
├── DEPLOY.md               # THIS FILE
├── SAAS_SETUP.md           # Additional SaaS setup notes
│
├── gateway/                # *** FACADE MODEL GATEWAY (separate service) ***
│   ├── Dockerfile          # Gateway Docker image
│   ├── main.py             # FastAPI app — all gateway logic
│   ├── config.json         # Default providers & facade models (seed config)
│   └── requirements.txt    # Python deps: fastapi, uvicorn, httpx
│
├── src/                    # *** OPEN WEBUI FRONTEND (Svelte/SvelteKit) ***
│   ├── lib/
│   │   └── components/
│   │       ├── admin/
│   │       │   └── Providers.svelte       # *** CUSTOM: Provider management UI ***
│   │       └── chat/
│   │           └── ModelSelector/
│   │               └── ModelItem.svelte   # *** MODIFIED: Free/Paid badges ***
│   └── routes/
│       └── (app)/
│           └── admin/
│               ├── +layout.svelte         # *** MODIFIED: Added "Providers" tab ***
│               └── providers/
│                   └── +page.svelte       # *** CUSTOM: Providers route ***
│
├── backend/                # Open WebUI Python backend (FastAPI, mostly unmodified)
└── ...                     # Other Open WebUI files (unmodified)
```

### Files WE Modified (vs stock Open WebUI)

| File | What Changed |
|---|---|
| `src/lib/components/chat/ModelSelector/ModelItem.svelte` | Added Free/Paid badge logic. Reads `model.info.meta.tier` from gateway, falls back to provider-name matching. Green badge = Free, Amber = Paid. |
| `src/routes/(app)/admin/+layout.svelte` | Added "Providers" nav tab between "Functions" and "Settings". |
| `src/routes/(app)/admin/providers/+page.svelte` | New route page that renders the Providers component. |
| `src/lib/components/admin/Providers.svelte` | **Entire file is custom.** Full admin UI for managing providers, API keys, facade models, and tiers. |
| `Dockerfile.railway` | New. Slim Railway deployment using prebuilt Open WebUI image. |
| `railway.json` / `railway.toml` | New. Railway deployment configuration. |
| `gateway/*` | **Entire directory is custom.** The facade model gateway service. |

---

## Service 1: Open WebUI

**What it is:** The user-facing chat interface. Users sign up, pick a model, chat.

**Tech stack:** SvelteKit frontend + Python FastAPI backend + SQLite database.

**Docker image:** Uses `ghcr.io/open-webui/open-webui:main` (prebuilt) via `Dockerfile.railway`.

**Port:** 8080

**Key files:**
- `Dockerfile.railway` — what Railway builds
- `railway.json` — build config (tells Railway to use Dockerfile.railway)
- `railway.toml` — deploy config (healthcheck on /health, mount for /app/backend/data)

**Database:** SQLite at `/app/backend/data/webui.db`. This is on a Railway persistent volume so it survives redeploys.

---

## Service 2: Facade Model Gateway

**What it is:** A lightweight Python proxy (FastAPI) that sits between Open WebUI and the real LLM providers.

**Port:** 3000

**Key file:** `gateway/main.py` — the entire gateway is this one file (~400 lines).

### What the Gateway Does

1. **Exposes facade models** via `/v1/models` — returns clean names like "Claude Opus 4.8"
2. **Routes chat requests** via `/v1/chat/completions` — receives request for a facade model, tries backend providers in order
3. **Rotates API keys** — each provider can have multiple keys; uses round-robin, skips rate-limited keys
4. **Manages access tiers** — FREE models are available to all, PAID models require subscription (checked via X-User-Tier header)
5. **Provides admin API** — full CRUD for providers, models, tiers, and API keys
6. **Persists state** — all admin changes saved to `/app/data/` (needs Railway volume)

### Gateway Data Files (in /app/data/)

| File | Purpose |
|---|---|
| `providers.json` | Provider configs with API keys (created after first admin edit) |
| `models.json` | Facade model definitions (created after first admin edit) |
| `tiers.json` | Model tier overrides: free/paid (created after first admin edit) |

On first boot, the gateway reads `config.json` as seed data. Once admin makes changes via the UI, persistent JSON files in `/app/data/` take precedence.

---

## How They Connect

Open WebUI connects to the Gateway as if it were an OpenAI API:

```
Open WebUI  →  OPENAI_API_BASE_URLS = https://<gateway-domain>/v1
               OPENAI_API_KEYS = <any-key>  (gateway doesn't validate this currently)
```

This is configured either:
- Via Railway environment variables on the Open WebUI service, OR
- Via Admin Panel → Settings → Connections → OpenAI API

The Gateway then calls the real providers (FreeModel.dev, LLM7, Z.AI, etc.) using the API keys stored in its config.

---

## Deployment on Railway

### Prerequisites

- GitHub account with this repo pushed
- Railway account (https://railway.com) linked to GitHub
- At least one LLM provider API key

### Step-by-Step

#### Deploy Service 1: Open WebUI

1. Go to Railway → **New Project** → **Deploy from GitHub Repo** → select `open-webui`
2. Railway auto-detects `railway.json` and builds using `Dockerfile.railway`
3. In **Settings → Networking**: generate domain, set port to **8080**
4. In **Settings → Volumes**: add a volume mounted at `/app/backend/data`
5. In **Variables**, add:
   ```
   PORT=8080
   WEBUI_SECRET_KEY=<random-secret-string>
   WEBUI_NAME=ClaudeSK
   ENABLE_SIGNUP=true
   DEFAULT_USER_ROLE=user
   RAG_EMBEDDING_ENGINE=openai
   ```
6. Wait for deployment to complete. Open the generated URL — first signup becomes admin.

#### Deploy Service 2: Gateway

1. In the SAME Railway project, click **+ New Service** → **GitHub Repo** → select `open-webui` again
2. In **Settings → Source**: set **Root Directory** to `gateway`
3. In **Settings → Networking**: generate domain, set port to **3000**
4. In **Settings → Volumes**: add a volume mounted at `/app/data`
5. In **Variables**, add:
   ```
   PORT=3000
   GATEWAY_ADMIN_KEY=sk-your-admin-key-here
   FREEMODEL_API_KEY=your-freemodel-key
   LLM7_API_KEY=your-llm7-key
   ZAI_API_KEY=your-zai-key
   FREELLMAPI_BASE_URL=https://your-freellmapi-instance/v1
   FREELLMAPI_API_KEY=your-freellmapi-key
   ```
6. Wait for deployment.

#### Connect Open WebUI to Gateway

After both services are deployed:

1. Add to Open WebUI's Railway **Variables**:
   ```
   OPENAI_API_BASE_URLS=https://<gateway-railway-domain>/v1
   OPENAI_API_KEYS=sk-gateway
   ```
   OR do it via Admin Panel → Settings → Connections → OpenAI API

2. Open WebUI will now fetch models from the gateway and users see facade model names.

#### Connect Admin Panel to Gateway

1. Log into Open WebUI as admin
2. Go to Admin Panel → **Providers** tab
3. Enter Gateway URL: `https://<gateway-railway-domain>`
4. Enter Admin Key: same as `GATEWAY_ADMIN_KEY`
5. Click Connect — you can now manage providers, keys, and models from the UI

---

## Custom Domain Setup

Domain: **claudesk.pro**

1. In Railway → Open WebUI service → **Settings → Networking → Custom Domain**
2. Add `claudesk.pro`
3. Railway shows a CNAME target (e.g., `abc123.up.railway.app`)
4. Go to your domain registrar's DNS settings
5. Add CNAME record:
   - Name: `@` (or `claudesk.pro`)
   - Target: the Railway-provided value
6. For `www`: add another CNAME → same target
7. Wait 5-30 min for DNS propagation

Update `CORS_ALLOW_ORIGIN` in Open WebUI variables to `https://claudesk.pro`.

---

## Environment Variables Reference

### Open WebUI Service

| Variable | Required | Description |
|---|---|---|
| `PORT` | Yes | Must be `8080` |
| `WEBUI_SECRET_KEY` | Yes | Random secret for JWT signing |
| `WEBUI_NAME` | No | Brand name shown in UI (default: "Open WebUI") |
| `ENABLE_SIGNUP` | No | `true` / `false` — allow user registration |
| `DEFAULT_USER_ROLE` | No | `user` or `admin` — role for new signups |
| `RAG_EMBEDDING_ENGINE` | No | Set to `openai` to avoid loading local ML models (saves RAM) |
| `OPENAI_API_BASE_URLS` | Yes | Gateway URL: `https://<gateway>/v1` |
| `OPENAI_API_KEYS` | Yes | Any string (gateway doesn't validate) |
| `CORS_ALLOW_ORIGIN` | No | Set to your domain for production |

### Gateway Service

| Variable | Required | Description |
|---|---|---|
| `PORT` | Yes | Must be `3000` |
| `GATEWAY_ADMIN_KEY` | Yes | Secret key for admin API auth |
| `GATEWAY_CONFIG_PATH` | No | Path to config.json (default: `/app/config.json`) |
| `GATEWAY_DATA_DIR` | No | Path to persistent data (default: `/app/data`) |
| `FREEMODEL_API_KEY` | No | API key for FreeModel.dev |
| `LLM7_API_KEY` | No | API key for LLM7.io |
| `ZAI_API_KEY` | No | API key for Z.AI |
| `FREELLMAPI_BASE_URL` | No | URL of self-hosted FreeLLMAPI instance |
| `FREELLMAPI_API_KEY` | No | API key for FreeLLMAPI |

---

## Admin Panel Features

### Providers Tab (Custom — `Providers.svelte`)

Two sub-tabs:

**Providers:**
- Add/edit/delete LLM providers
- Each provider has: ID, name, base URL, and multiple API keys
- Bulk upload keys: paste one key per line
- Health monitoring: green (healthy), yellow (failures), red (cooldown)
- Reset failed providers

**Facade Models:**
- Add/edit/delete user-facing model names
- Click FREE/PAID badge to toggle tier
- Set backend providers with fallback order
- Each backend = provider ID + real model ID on that provider

### How Tier Control Works

- All models default to **PAID**
- Admin clicks the badge to switch to **FREE**
- FREE = available to all users
- PAID = returns 403 "subscription_required" error to non-subscribers
- Tier state persists in `/app/data/tiers.json`

---

## Facade Model System Explained

### Example

Admin creates facade model:
```json
{
  "id": "claude-opus-4.8",
  "name": "Claude Opus 4.8",
  "tier": "paid",
  "backends": [
    { "provider": "freemodel", "model": "claude-opus-4-8" },
    { "provider": "llm7", "model": "claude-opus-4-8" },
    { "provider": "zai", "model": "claude-opus-4-8" }
  ]
}
```

When a user selects "Claude Opus 4.8" and sends a message:
1. Gateway receives request for model `claude-opus-4.8`
2. Tries FreeModel.dev with model ID `claude-opus-4-8`
3. If FreeModel fails (timeout/rate-limit/error) → tries LLM7
4. If LLM7 fails → tries Z.AI
5. If all fail → returns 503 error

The user never knows which provider actually served the response.

---

## API Key Rotation & Fallback Logic

### Multiple Keys Per Provider

Each provider can have many API keys. The gateway rotates through them:

```
Provider: FreeModel.dev
Keys: [key-A, key-B, key-C]

Request 1 → uses key-A
Request 2 → uses key-B
Request 3 → uses key-C
Request 4 → uses key-A (round-robin)

If key-B gets 429 rate-limited:
  → immediately tries key-C on same request
  → next request starts from key-C
```

### Provider Fallback

If a provider returns errors 3 times consecutively, it enters a 30-second cooldown. During cooldown, the gateway skips it and tries the next provider.

### Relevant Code in gateway/main.py

- `get_next_key()` — round-robin key selection
- `try_provider()` — single provider attempt with key rotation on 429
- `chat_completions()` — iterates through backends in order
- `mark_failure()` / `mark_success()` — health tracking
- `FAILURE_COOLDOWN = 30` — seconds to skip a failed provider
- `MAX_FAILURES = 3` — failures before cooldown

---

## Common Modifications

### Adding a New Provider

**Via UI:** Admin Panel → Providers → Add Provider → fill in ID, name, base URL, API keys.

**Via code:** Edit `gateway/config.json`, add to the `providers` object:
```json
"newprovider": {
  "name": "New Provider",
  "base_url": "https://api.newprovider.com/v1",
  "api_key": "${NEWPROVIDER_API_KEY}"
}
```
Then add `NEWPROVIDER_API_KEY` to Railway variables.

### Adding a New Facade Model

**Via UI:** Admin Panel → Providers → Facade Models tab → Add Model.

**Via code:** Edit `gateway/config.json`, add to `facade_models` array.

### Changing the Free/Paid Badge Appearance

Edit `src/lib/components/chat/ModelSelector/ModelItem.svelte`. Search for `modelTier === 'free'`. The badge is a `<span>` with Tailwind classes.

### Adding More Tier Levels (e.g., "premium", "enterprise")

1. Update `gateway/main.py`: modify `get_model_tier()`, `chat_completions()` access check, and the tier POST endpoint to accept new values
2. Update `Providers.svelte`: add new tier options in the UI
3. Update `ModelItem.svelte`: add new badge color

### Upgrading Open WebUI

The `Dockerfile.railway` pulls `ghcr.io/open-webui/open-webui:main`. To pin a version:
```dockerfile
FROM ghcr.io/open-webui/open-webui:v0.5.0
```
**Warning:** After upgrading, check if our modified files (`ModelItem.svelte`, `+layout.svelte`) conflict with upstream changes. The custom files are:
- `src/lib/components/chat/ModelSelector/ModelItem.svelte`
- `src/routes/(app)/admin/+layout.svelte`
- `src/routes/(app)/admin/providers/+page.svelte`
- `src/lib/components/admin/Providers.svelte`

### Switching from SQLite to PostgreSQL

1. Add a PostgreSQL service in Railway (one click)
2. Set `DATABASE_URL` in Open WebUI variables to the Postgres connection string
3. Open WebUI auto-migrates on next boot

---

## Troubleshooting

### Open WebUI healthcheck fails on Railway

- **Cause:** Not enough RAM. Open WebUI with embedding models needs 1GB+.
- **Fix:** Set `RAG_EMBEDDING_ENGINE=openai` to disable local models. Or upgrade Railway plan.

### Gateway healthcheck fails

- **Cause:** Missing dependencies or config error.
- **Fix:** Check deploy logs. Ensure `config.json` exists and is valid JSON.

### Models not showing up in Open WebUI

- **Cause:** Open WebUI can't reach the gateway.
- **Fix:** Verify `OPENAI_API_BASE_URLS` points to `https://<gateway-domain>/v1`. Test by visiting `https://<gateway-domain>/v1/models` in browser.

### "All providers failed" error

- **Cause:** Every backend provider for that facade model is down or rate-limited.
- **Fix:** Check gateway admin status: `GET /admin/providers` with admin key. Reset cooldowns if needed. Add more API keys.

### Admin Providers page shows "connect" form

- **Cause:** Gateway URL not configured in the Providers page yet.
- **Fix:** Enter the gateway Railway URL and admin key. It saves to localStorage.

### Rate limiting

- **Cause:** API key hit provider's rate limit.
- **Fix:** Add more API keys via Providers page → Bulk Upload Keys. The gateway auto-rotates through them.

---

## Gateway Admin API Reference

All endpoints require header: `Authorization: Bearer <GATEWAY_ADMIN_KEY>`

### Providers

| Method | Endpoint | Body | Description |
|---|---|---|---|
| GET | `/admin/providers` | — | List all providers with health status |
| POST | `/admin/providers` | `{id, name, base_url, api_keys: [...]}` | Create provider |
| PUT | `/admin/providers/{id}` | `{name?, base_url?, api_keys?}` | Update provider |
| DELETE | `/admin/providers/{id}` | — | Delete provider |
| POST | `/admin/providers/{id}/reset` | — | Reset failure counter |

### Facade Models

| Method | Endpoint | Body | Description |
|---|---|---|---|
| GET | `/admin/models` | — | List all facade models |
| POST | `/admin/models` | `{id, name, tier, backends: [{provider, model}, ...]}` | Create model |
| PUT | `/admin/models/{id}` | `{name?, tier?, backends?}` | Update model |
| DELETE | `/admin/models/{id}` | — | Delete model |
| POST | `/admin/models/{id}/tier` | `{"tier": "free"}` | Toggle tier |

### System

| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/config` | Get full config (providers + models) |
| POST | `/admin/reload` | Reload config from disk |
| GET | `/health` | Health check |

---

## LLM Provider API Endpoints

| Provider | Base URL | Docs |
|---|---|---|
| FreeModel.dev | `https://api.freemodel.dev/v1` | https://freemodel.dev/dashboard/docs |
| LLM7.io | `https://api.llm7.io/v1` | https://docs.llm7.io/quickstart |
| Z.AI | `https://api.z.ai/api/paas/v4/` | https://docs.z.ai/guides/develop/openai/python |
| FreeLLMAPI | Self-hosted | https://github.com/tashfeenahmed/freellmapi |

All providers use OpenAI-compatible API format (`/chat/completions`, `/models`).

---

## GitHub Repository

- **Owner:** bzimunbwz
- **Repo:** https://github.com/bzimunbwz/open-webui
- **Domain:** https://claudesk.pro

## Deployment Platform

- **Railway** (https://railway.com)
- Two services in one project: Open WebUI + Gateway
- Both need persistent volumes

---

*Last updated: June 26, 2026*
