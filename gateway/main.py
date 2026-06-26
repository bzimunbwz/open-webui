"""
Facade Model Gateway
====================
OpenAI-compatible proxy that presents clean model names to users
and routes requests to multiple backend providers with automatic fallback.

Admin controls:
- Toggle any model between FREE and PAID
- FREE models: available to all users
- PAID models: require subscription (checked via X-User-Tier header)
- All tier changes persist across restarts
"""

import os
import re
import json
import time
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

app = FastAPI(title="Facade Model Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ──────────────────────────────────────────────────────────────────

CONFIG_PATH = os.getenv("GATEWAY_CONFIG_PATH", "/app/config.json")
DATA_DIR = os.getenv("GATEWAY_DATA_DIR", "/app/data")
TIERS_PATH = os.path.join(DATA_DIR, "tiers.json")
MODELS_PATH = os.path.join(DATA_DIR, "models.json")  # admin-modified models persist here
ADMIN_API_KEY = os.getenv("GATEWAY_ADMIN_KEY", "sk-gateway-admin")

# Provider health tracking
provider_status: dict[str, dict] = {}

# Runtime state
providers: dict = {}
facade_models: dict = {}
model_tiers: dict = {}  # model_id → "free" | "paid" (admin-controlled, persisted)


def resolve_env(raw: str) -> str:
    """Replace ${ENV_VAR} with actual env values."""
    return re.sub(r'\$\{(\w+)\}', lambda m: os.getenv(m.group(1), ""), raw)


def ensure_data_dir():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def load_config():
    global providers, facade_models
    with open(CONFIG_PATH) as f:
        cfg = json.loads(resolve_env(f.read()))

    providers = cfg.get("providers", {})

    # Start with config-defined models
    facade_models = {}
    for m in cfg.get("facade_models", []):
        facade_models[m["id"]] = m

    # Overlay admin-modified models (these take precedence)
    load_models_override()

    # Init provider health
    for pid in providers:
        if pid not in provider_status:
            provider_status[pid] = {"failures": 0, "last_failure": 0, "cooldown_until": 0}

    logger.info(f"Loaded {len(facade_models)} facade models, {len(providers)} providers")


def load_models_override():
    """Load admin-created/edited models from persistent storage."""
    global facade_models
    try:
        with open(MODELS_PATH) as f:
            overrides = json.load(f)
        for m in overrides:
            facade_models[m["id"]] = m
        logger.info(f"Loaded {len(overrides)} model overrides from admin")
    except FileNotFoundError:
        pass


def save_models_override():
    """Save all current facade models to persistent storage."""
    ensure_data_dir()
    models_list = list(facade_models.values())
    with open(MODELS_PATH, "w") as f:
        json.dump(models_list, f, indent=2)


def load_tiers():
    """Load admin-set tiers from persistent storage."""
    global model_tiers
    try:
        with open(TIERS_PATH) as f:
            model_tiers = json.load(f)
        logger.info(f"Loaded {len(model_tiers)} tier overrides")
    except FileNotFoundError:
        model_tiers = {}
        logger.info("No tier overrides found, using config defaults")


def save_tiers():
    """Persist tier overrides to disk."""
    ensure_data_dir()
    with open(TIERS_PATH, "w") as f:
        json.dump(model_tiers, f, indent=2)


def get_model_tier(model_id: str) -> str:
    """Get effective tier: admin override > config default."""
    if model_id in model_tiers:
        return model_tiers[model_id]
    facade = facade_models.get(model_id, {})
    return facade.get("tier", "paid")


# ── Provider Health ─────────────────────────────────────────────────────────

FAILURE_COOLDOWN = 30
MAX_FAILURES = 3


def mark_failure(pid: str):
    s = provider_status.setdefault(pid, {"failures": 0, "last_failure": 0, "cooldown_until": 0})
    s["failures"] += 1
    s["last_failure"] = time.time()
    if s["failures"] >= MAX_FAILURES:
        s["cooldown_until"] = time.time() + FAILURE_COOLDOWN
        logger.warning(f"Provider {pid} in cooldown for {FAILURE_COOLDOWN}s")


def mark_success(pid: str):
    provider_status[pid] = {"failures": 0, "last_failure": 0, "cooldown_until": 0}


def is_available(pid: str) -> bool:
    return provider_status.get(pid, {}).get("cooldown_until", 0) <= time.time()


# ── Proxy Logic ─────────────────────────────────────────────────────────────

RETRYABLE = {429, 500, 502, 503, 504, 520, 521, 522, 523, 524}


async def try_provider(pid: str, backend_model: str, body: dict, stream: bool, timeout: float = 120.0):
    prov = providers.get(pid)
    if not prov or not prov.get("base_url") or not is_available(pid):
        return None

    url = prov["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if prov.get("api_key"):
        headers["Authorization"] = f"Bearer {prov['api_key']}"

    req_body = {**body, "model": backend_model}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if stream:
                req = client.build_request("POST", url, json=req_body, headers=headers)
                resp = await client.send(req, stream=True)
                if resp.status_code in RETRYABLE or resp.status_code >= 400:
                    await resp.aclose()
                    mark_failure(pid)
                    return None
                mark_success(pid)
                return resp
            else:
                resp = await client.post(url, json=req_body, headers=headers)
                if resp.status_code in RETRYABLE or resp.status_code >= 400:
                    mark_failure(pid)
                    return None
                mark_success(pid)
                return resp
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as e:
        mark_failure(pid)
        logger.warning(f"Provider {pid} error: {e}")
        return None
    except Exception as e:
        mark_failure(pid)
        logger.error(f"Provider {pid} unexpected: {e}")
        return None


# ── Auth Helpers ────────────────────────────────────────────────────────────

def check_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {ADMIN_API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_user_tier(request: Request) -> str:
    """
    Determine user's subscription tier from request headers.
    Open WebUI passes user info - we check X-User-Tier header.
    Default: 'free' (unsubscribed users).
    """
    return request.headers.get("X-User-Tier", "free").lower()


# ── Routes ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    load_config()
    load_tiers()


@app.get("/health")
async def health():
    return {"status": True}


@app.get("/v1/models")
async def list_models(request: Request):
    """Return all facade models with their current tier badge."""
    data = []
    for mid, mcfg in facade_models.items():
        tier = get_model_tier(mid)
        data.append({
            "id": mid,
            "object": "model",
            "created": 1700000000,
            "owned_by": "claudesk",
            "name": mcfg["name"],
            "info": {
                "meta": {
                    "description": mcfg["name"],
                    "tier": tier,
                }
            },
        })
    return {"object": "list", "data": data}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    requested_model = body.get("model", "")
    stream = body.get("stream", False)

    facade = facade_models.get(requested_model)
    if not facade:
        raise HTTPException(status_code=404, detail=f"Model '{requested_model}' not found")

    # ── Access control ──
    tier = get_model_tier(requested_model)
    user_tier = get_user_tier(request)

    if tier == "paid" and user_tier != "paid" and user_tier != "admin":
        raise HTTPException(
            status_code=403,
            detail=json.dumps({
                "error": "subscription_required",
                "message": f"'{facade['name']}' requires a subscription. Please upgrade to use this model.",
                "model": requested_model,
                "required_tier": "paid",
            })
        )

    # ── Fallback routing ──
    for backend in facade.get("backends", []):
        pid = backend["provider"]
        bmodel = backend["model"]
        logger.info(f"Trying {facade['name']} → {pid}/{bmodel}")

        resp = await try_provider(pid, bmodel, body, stream=stream)
        if resp is not None:
            if stream:
                async def stream_out():
                    try:
                        async for chunk in resp.aiter_bytes(1024):
                            yield chunk
                    finally:
                        await resp.aclose()

                return StreamingResponse(
                    stream_out(),
                    media_type="text/event-stream",
                    headers={"X-Gateway-Provider": pid, "X-Model-Tier": tier},
                )
            else:
                result = resp.json()
                result["model"] = requested_model
                return JSONResponse(
                    content=result,
                    headers={"X-Gateway-Provider": pid, "X-Model-Tier": tier},
                )

    raise HTTPException(status_code=503, detail=f"All providers failed for '{requested_model}'")


# ── Admin API ───────────────────────────────────────────────────────────────

@app.get("/admin/models")
async def admin_list_models(request: Request):
    """List all models with their current tier and backend providers."""
    check_admin(request)
    result = []
    for mid, mcfg in facade_models.items():
        result.append({
            "id": mid,
            "name": mcfg["name"],
            "tier": get_model_tier(mid),
            "backends": mcfg.get("backends", []),
        })
    return {"models": result}


@app.post("/admin/models/{model_id}/tier")
async def admin_set_tier(model_id: str, request: Request):
    """Toggle a model's tier. Body: {"tier": "free"} or {"tier": "paid"}"""
    check_admin(request)
    if model_id not in facade_models:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    body = await request.json()
    new_tier = body.get("tier", "").lower()
    if new_tier not in ("free", "paid"):
        raise HTTPException(status_code=400, detail="tier must be 'free' or 'paid'")

    model_tiers[model_id] = new_tier
    save_tiers()

    name = facade_models[model_id]["name"]
    logger.info(f"Admin set {name} ({model_id}) → {new_tier}")
    return {"model": model_id, "name": name, "tier": new_tier}


@app.post("/admin/models/bulk-tier")
async def admin_bulk_tier(request: Request):
    """Set tier for multiple models at once. Body: {"models": {"model-id": "free", ...}}"""
    check_admin(request)
    body = await request.json()
    updates = body.get("models", {})
    results = []

    for mid, tier in updates.items():
        if mid not in facade_models:
            continue
        if tier not in ("free", "paid"):
            continue
        model_tiers[mid] = tier
        results.append({"model": mid, "name": facade_models[mid]["name"], "tier": tier})

    save_tiers()
    return {"updated": results}


@app.post("/admin/models")
async def admin_create_model(request: Request):
    """
    Create a new facade model.
    Body: {
        "id": "gpt-4.1",
        "name": "GPT 4.1",
        "tier": "paid",
        "backends": [
            {"provider": "freemodel", "model": "gpt-4.1"},
            {"provider": "llm7", "model": "gpt-4.1"}
        ]
    }
    """
    check_admin(request)
    body = await request.json()

    model_id = body.get("id", "").strip()
    name = body.get("name", "").strip()
    tier = body.get("tier", "paid").lower()
    backends = body.get("backends", [])

    if not model_id or not name:
        raise HTTPException(status_code=400, detail="id and name are required")
    if model_id in facade_models:
        raise HTTPException(status_code=409, detail=f"Model '{model_id}' already exists. Use PUT to edit.")
    if not backends:
        raise HTTPException(status_code=400, detail="At least one backend is required")

    model = {"id": model_id, "name": name, "tier": tier, "backends": backends}
    facade_models[model_id] = model
    model_tiers[model_id] = tier
    save_models_override()
    save_tiers()

    logger.info(f"Admin created model: {name} ({model_id})")
    return {"status": "created", "model": model}


@app.put("/admin/models/{model_id}")
async def admin_edit_model(model_id: str, request: Request):
    """
    Edit an existing facade model.
    Body: any subset of {name, tier, backends}
    """
    check_admin(request)
    if model_id not in facade_models:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    body = await request.json()
    model = facade_models[model_id]

    if "name" in body:
        model["name"] = body["name"].strip()
    if "tier" in body:
        tier = body["tier"].lower()
        if tier in ("free", "paid"):
            model["tier"] = tier
            model_tiers[model_id] = tier
    if "backends" in body:
        if not body["backends"]:
            raise HTTPException(status_code=400, detail="At least one backend is required")
        model["backends"] = body["backends"]

    facade_models[model_id] = model
    save_models_override()
    save_tiers()

    logger.info(f"Admin updated model: {model['name']} ({model_id})")
    return {"status": "updated", "model": model}


@app.delete("/admin/models/{model_id}")
async def admin_delete_model(model_id: str, request: Request):
    """Delete a facade model."""
    check_admin(request)
    if model_id not in facade_models:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    name = facade_models[model_id]["name"]
    del facade_models[model_id]
    model_tiers.pop(model_id, None)
    save_models_override()
    save_tiers()

    logger.info(f"Admin deleted model: {name} ({model_id})")
    return {"status": "deleted", "model": model_id, "name": name}


@app.get("/admin/providers")
async def admin_providers(request: Request):
    """View provider health status."""
    check_admin(request)
    status = {}
    for pid, prov in providers.items():
        ps = provider_status.get(pid, {})
        status[pid] = {
            "name": prov["name"],
            "base_url": prov["base_url"][:50] + "..." if len(prov.get("base_url", "")) > 50 else prov.get("base_url", ""),
            "failures": ps.get("failures", 0),
            "in_cooldown": ps.get("cooldown_until", 0) > time.time(),
            "cooldown_remaining_s": max(0, round(ps.get("cooldown_until", 0) - time.time())),
        }
    return {"providers": status}


@app.post("/admin/providers/{provider_id}/reset")
async def admin_reset_provider(provider_id: str, request: Request):
    """Reset a provider's failure counter."""
    check_admin(request)
    if provider_id not in providers:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    mark_success(provider_id)
    return {"status": "reset", "provider": provider_id}


@app.post("/admin/reload")
async def admin_reload(request: Request):
    """Reload config from disk."""
    check_admin(request)
    load_config()
    load_tiers()
    return {"status": "reloaded", "models": len(facade_models), "providers": len(providers)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
