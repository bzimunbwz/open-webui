"""
Facade Model Gateway
====================
OpenAI-compatible proxy with:
- Clean facade model names for users
- Multiple API keys per provider with round-robin rotation
- Automatic fallback across providers
- Admin CRUD for providers, models, and tiers
- Persistent storage for all admin changes
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
PROVIDERS_PATH = os.path.join(DATA_DIR, "providers.json")
MODELS_PATH = os.path.join(DATA_DIR, "models.json")
TIERS_PATH = os.path.join(DATA_DIR, "tiers.json")
ADMIN_API_KEY = os.getenv("GATEWAY_ADMIN_KEY", "sk-gateway-admin")

# Runtime state
providers: dict = {}          # id → {name, base_url, api_keys: [...]}
facade_models: dict = {}      # id → {id, name, tier, backends: [...]}
model_tiers: dict = {}        # id → "free"|"paid"
provider_status: dict = {}    # id → {failures, cooldown_until, ...}
key_index: dict = {}          # provider_id → current key index (for rotation)


def ensure_data_dir():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def resolve_env(raw: str) -> str:
    return re.sub(r'\$\{(\w+)\}', lambda m: os.getenv(m.group(1), ""), raw)


# ── Load / Save ────────────────────────────────────────────────────────────

def load_all():
    load_providers()
    load_models()
    load_tiers()


def load_providers():
    """Load providers: persistent overrides first, fall back to config.json."""
    global providers
    # Try persistent first
    try:
        with open(PROVIDERS_PATH) as f:
            providers = json.load(f)
        logger.info(f"Loaded {len(providers)} providers from persistent storage")
    except FileNotFoundError:
        # Fall back to config.json
        with open(CONFIG_PATH) as f:
            cfg = json.loads(resolve_env(f.read()))
        raw_providers = cfg.get("providers", {})
        providers = {}
        for pid, p in raw_providers.items():
            providers[pid] = {
                "name": p.get("name", pid),
                "base_url": p.get("base_url", ""),
                "api_keys": p.get("api_keys", [p["api_key"]] if p.get("api_key") else []),
            }
        logger.info(f"Loaded {len(providers)} providers from config.json")

    # Init health tracking
    for pid in providers:
        if pid not in provider_status:
            provider_status[pid] = {"failures": 0, "last_failure": 0, "cooldown_until": 0}
        if pid not in key_index:
            key_index[pid] = 0


def save_providers():
    ensure_data_dir()
    with open(PROVIDERS_PATH, "w") as f:
        json.dump(providers, f, indent=2)


def load_models():
    global facade_models
    # Try persistent first
    try:
        with open(MODELS_PATH) as f:
            models_list = json.load(f)
        facade_models = {m["id"]: m for m in models_list}
        logger.info(f"Loaded {len(facade_models)} models from persistent storage")
    except FileNotFoundError:
        with open(CONFIG_PATH) as f:
            cfg = json.loads(resolve_env(f.read()))
        facade_models = {}
        for m in cfg.get("facade_models", []):
            facade_models[m["id"]] = m
        logger.info(f"Loaded {len(facade_models)} models from config.json")


def save_models():
    ensure_data_dir()
    with open(MODELS_PATH, "w") as f:
        json.dump(list(facade_models.values()), f, indent=2)


def load_tiers():
    global model_tiers
    try:
        with open(TIERS_PATH) as f:
            model_tiers = json.load(f)
    except FileNotFoundError:
        model_tiers = {}


def save_tiers():
    ensure_data_dir()
    with open(TIERS_PATH, "w") as f:
        json.dump(model_tiers, f, indent=2)


def get_model_tier(model_id: str) -> str:
    if model_id in model_tiers:
        return model_tiers[model_id]
    return facade_models.get(model_id, {}).get("tier", "paid")


# ── API Key Rotation ───────────────────────────────────────────────────────

def get_next_key(provider_id: str) -> str:
    """Round-robin through provider's API keys."""
    prov = providers.get(provider_id, {})
    keys = prov.get("api_keys", [])
    if not keys:
        return ""

    idx = key_index.get(provider_id, 0) % len(keys)
    key_index[provider_id] = (idx + 1) % len(keys)
    return keys[idx]


def mark_key_failed(provider_id: str, failed_key: str):
    """On key failure, rotate to next key. If all keys exhausted, mark provider failed."""
    prov = providers.get(provider_id, {})
    keys = prov.get("api_keys", [])
    if len(keys) <= 1:
        mark_failure(provider_id)
        return

    # Just rotate — the next attempt will use the next key
    logger.info(f"Rotating key for {provider_id} (key ending ...{failed_key[-4:] if len(failed_key) >= 4 else '****'} failed)")


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

    keys = prov.get("api_keys", [])
    attempts = max(len(keys), 1)  # Try each key at least once

    for attempt in range(attempts):
        api_key = get_next_key(pid)
        url = prov["base_url"].rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req_body = {**body, "model": backend_model}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if stream:
                    req = client.build_request("POST", url, json=req_body, headers=headers)
                    resp = await client.send(req, stream=True)
                    if resp.status_code == 429:
                        await resp.aclose()
                        mark_key_failed(pid, api_key)
                        logger.info(f"Key rate-limited on {pid}, trying next key (attempt {attempt + 1}/{attempts})")
                        continue
                    if resp.status_code in RETRYABLE or resp.status_code >= 400:
                        await resp.aclose()
                        mark_failure(pid)
                        return None
                    mark_success(pid)
                    return resp
                else:
                    resp = await client.post(url, json=req_body, headers=headers)
                    if resp.status_code == 429:
                        mark_key_failed(pid, api_key)
                        logger.info(f"Key rate-limited on {pid}, trying next key (attempt {attempt + 1}/{attempts})")
                        continue
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

    # All keys exhausted
    mark_failure(pid)
    return None


# ── Auth ────────────────────────────────────────────────────────────────────

def check_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {ADMIN_API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_user_tier(request: Request) -> str:
    return request.headers.get("X-User-Tier", "free").lower()


# ── Public Routes ───────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    load_all()


@app.get("/health")
async def health():
    return {"status": True}


@app.get("/v1/models")
async def list_models(request: Request):
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

    tier = get_model_tier(requested_model)
    user_tier = get_user_tier(request)

    if tier == "paid" and user_tier not in ("paid", "admin"):
        raise HTTPException(
            status_code=403,
            detail=json.dumps({
                "error": "subscription_required",
                "message": f"'{facade['name']}' requires a subscription. Please upgrade to use this model.",
                "model": requested_model,
                "required_tier": "paid",
            })
        )

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


# ── Admin: Provider CRUD ────────────────────────────────────────────────────

@app.get("/admin/config")
async def admin_get_config(request: Request):
    """Get full config (providers + models)."""
    check_admin(request)
    return {
        "providers": providers,
        "models": list(facade_models.values()),
    }


@app.get("/admin/providers")
async def admin_list_providers(request: Request):
    """View provider health status."""
    check_admin(request)
    status = {}
    for pid, prov in providers.items():
        ps = provider_status.get(pid, {})
        keys = prov.get("api_keys", [])
        status[pid] = {
            "name": prov.get("name", pid),
            "base_url": prov.get("base_url", ""),
            "key_count": len(keys),
            "current_key_index": key_index.get(pid, 0),
            "failures": ps.get("failures", 0),
            "in_cooldown": ps.get("cooldown_until", 0) > time.time(),
            "cooldown_remaining_s": max(0, round(ps.get("cooldown_until", 0) - time.time())),
        }
    return {"providers": status}


@app.post("/admin/providers")
async def admin_create_provider(request: Request):
    """Create a new provider. Body: {id, name, base_url, api_keys: [...]}"""
    check_admin(request)
    body = await request.json()
    pid = body.get("id", "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="id is required")
    if pid in providers:
        raise HTTPException(status_code=409, detail=f"Provider '{pid}' already exists")

    providers[pid] = {
        "name": body.get("name", pid),
        "base_url": body.get("base_url", ""),
        "api_keys": body.get("api_keys", []),
    }
    provider_status[pid] = {"failures": 0, "last_failure": 0, "cooldown_until": 0}
    key_index[pid] = 0
    save_providers()
    logger.info(f"Admin created provider: {pid}")
    return {"status": "created", "provider": pid}


@app.put("/admin/providers/{provider_id}")
async def admin_update_provider(provider_id: str, request: Request):
    """Update provider. Body: any subset of {name, base_url, api_keys}"""
    check_admin(request)
    if provider_id not in providers:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    body = await request.json()
    prov = providers[provider_id]
    if "name" in body:
        prov["name"] = body["name"]
    if "base_url" in body:
        prov["base_url"] = body["base_url"]
    if "api_keys" in body:
        prov["api_keys"] = [k for k in body["api_keys"] if k.strip()]
        key_index[provider_id] = 0  # Reset rotation

    save_providers()
    logger.info(f"Admin updated provider: {provider_id} ({len(prov.get('api_keys', []))} keys)")
    return {"status": "updated", "provider": provider_id, "key_count": len(prov.get("api_keys", []))}


@app.delete("/admin/providers/{provider_id}")
async def admin_delete_provider(provider_id: str, request: Request):
    """Delete a provider."""
    check_admin(request)
    if provider_id not in providers:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    del providers[provider_id]
    provider_status.pop(provider_id, None)
    key_index.pop(provider_id, None)
    save_providers()
    logger.info(f"Admin deleted provider: {provider_id}")
    return {"status": "deleted", "provider": provider_id}


@app.post("/admin/providers/{provider_id}/reset")
async def admin_reset_provider(provider_id: str, request: Request):
    check_admin(request)
    if provider_id not in providers:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    mark_success(provider_id)
    key_index[provider_id] = 0
    return {"status": "reset", "provider": provider_id}


@app.get("/admin/providers/{provider_id}/models")
async def admin_sync_provider_models(provider_id: str, request: Request):
    """Proxy /models request to a provider (avoids browser CORS issues)."""
    check_admin(request)
    if provider_id not in providers:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    prov = providers[provider_id]
    base_url = prov.get("base_url", "").rstrip("/")
    if not base_url:
        raise HTTPException(status_code=400, detail="Provider has no base_url")
    api_keys = prov.get("api_keys", [])
    headers = {"Content-Type": "application/json"}
    if api_keys:
        headers["Authorization"] = f"Bearer {api_keys[0]}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(f"{base_url}/models", headers=headers)
            res.raise_for_status()
            return res.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch models from {base_url}: {str(e)}")


# ── Admin: Model CRUD ──────────────────────────────────────────────────────

@app.get("/admin/models")
async def admin_list_models(request: Request):
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


@app.post("/admin/models")
async def admin_create_model(request: Request):
    check_admin(request)
    body = await request.json()
    model_id = body.get("id", "").strip()
    name = body.get("name", "").strip()
    if not model_id or not name:
        raise HTTPException(status_code=400, detail="id and name are required")
    if model_id in facade_models:
        raise HTTPException(status_code=409, detail=f"Model '{model_id}' already exists")
    if not body.get("backends"):
        raise HTTPException(status_code=400, detail="At least one backend is required")

    tier = body.get("tier", "paid")
    model = {"id": model_id, "name": name, "tier": tier, "backends": body["backends"]}
    facade_models[model_id] = model
    model_tiers[model_id] = tier
    save_models()
    save_tiers()
    logger.info(f"Admin created model: {name} ({model_id})")
    return {"status": "created", "model": model}


@app.put("/admin/models/{model_id}")
async def admin_edit_model(model_id: str, request: Request):
    check_admin(request)
    if model_id not in facade_models:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    body = await request.json()
    model = facade_models[model_id]

    if "name" in body:
        model["name"] = body["name"].strip()
    if "tier" in body and body["tier"] in ("free", "paid"):
        model["tier"] = body["tier"]
        model_tiers[model_id] = body["tier"]
    if "backends" in body:
        if not body["backends"]:
            raise HTTPException(status_code=400, detail="At least one backend is required")
        model["backends"] = body["backends"]

    facade_models[model_id] = model
    save_models()
    save_tiers()
    logger.info(f"Admin updated model: {model['name']} ({model_id})")
    return {"status": "updated", "model": model}


@app.delete("/admin/models/{model_id}")
async def admin_delete_model(model_id: str, request: Request):
    check_admin(request)
    if model_id not in facade_models:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    name = facade_models[model_id]["name"]
    del facade_models[model_id]
    model_tiers.pop(model_id, None)
    save_models()
    save_tiers()
    logger.info(f"Admin deleted model: {name} ({model_id})")
    return {"status": "deleted", "model": model_id, "name": name}


@app.post("/admin/models/{model_id}/tier")
async def admin_set_tier(model_id: str, request: Request):
    check_admin(request)
    if model_id not in facade_models:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    body = await request.json()
    new_tier = body.get("tier", "").lower()
    if new_tier not in ("free", "paid"):
        raise HTTPException(status_code=400, detail="tier must be 'free' or 'paid'")

    model_tiers[model_id] = new_tier
    facade_models[model_id]["tier"] = new_tier
    save_tiers()
    save_models()

    name = facade_models[model_id]["name"]
    return {"model": model_id, "name": name, "tier": new_tier}


@app.post("/admin/reload")
async def admin_reload(request: Request):
    check_admin(request)
    load_all()
    return {"status": "reloaded", "models": len(facade_models), "providers": len(providers)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
