# ClaudeSK.pro - SaaS Setup Guide

## 1. Railway Environment Variables

Add these in Railway dashboard → Variables tab:

```
# Core
PORT=8080
WEBUI_SECRET_KEY=<generate-a-random-secret>
WEBUI_NAME=ClaudeSK
ENABLE_SIGNUP=true
DEFAULT_USER_ROLE=user

# Disable local ML models (saves RAM)
RAG_EMBEDDING_ENGINE=openai
AUDIO_STT_ENGINE=

# LLM Providers (semicolon-separated)
# Add your API keys for each provider
OPENAI_API_BASE_URLS=https://api.freemodel.dev/v1;https://api.llm7.io/v1;https://api.z.ai/api/paas/v4/
OPENAI_API_KEYS=<freemodel-key>;<llm7-key>;<zai-key>

# Security
CORS_ALLOW_ORIGIN=https://claudesk.pro
```

### FreeLLMAPI (Self-hosted proxy)
FreeLLMAPI is a self-hosted proxy that aggregates 16+ free providers.
See: https://github.com/tashfeenahmed/freellmapi
Deploy it separately on Railway, then add its URL to OPENAI_API_BASE_URLS.

## 2. Custom Domain Setup (claudesk.pro)

In Railway dashboard → Settings → Networking → Custom Domain:

1. Click "+ Custom Domain"
2. Enter: `claudesk.pro`
3. Railway gives you a CNAME record
4. Go to your domain registrar's DNS settings
5. Add CNAME record: `claudesk.pro` → `<railway-provided-value>`
6. Wait for DNS propagation (5-30 minutes)

For `www.claudesk.pro`, add another CNAME pointing to the same value.

## 3. Free vs Paid Model Tiers

Models are automatically labeled FREE or PAID based on their provider:
- Models from freellmapi, freemodel.dev, llm7.io → **FREE** badge
- Models from z.ai or other providers → **PAID** badge

To manually override, use Open WebUI's model tagging in Admin Panel:
- Tag a model with "free" → shows FREE badge
- Tag a model with "paid" → shows PAID badge

## 4. User Management

- First signup becomes admin
- Admin Panel → Users: manage accounts, set roles
- Admin Panel → Settings → General: toggle ENABLE_SIGNUP on/off
- Admin Panel → Settings → Models: control which models each user role can access

## 5. Billing (Future)

Open WebUI doesn't have built-in billing. Options:

**Option A: Stripe + Middleware (Recommended)**
- Add a reverse proxy (e.g., LiteLLM) between users and LLM APIs
- Track token usage per user
- Bill via Stripe based on usage

**Option B: Manual Tiers**
- Create user groups in Admin Panel (Free, Pro, Enterprise)
- Assign different model access per group
- Free users → free provider models only
- Paid users → all models
- Manage subscriptions manually or via Stripe Checkout links

**Option C: Use Open WebUI's built-in token system**
- Admin Panel → Settings → Users: set token limits per user role
- Free users get limited tokens, paid users get more
