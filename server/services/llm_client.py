"""
LLM Client Service — DCPI.
Primary: Groq API (fast cloud inference, concurrent multi-key).
All agents call call_claude() / call_claude_json() — provider is transparent.
Batch variants call_claude_batch() / call_claude_json_batch() run multiple
prompts concurrently against Groq for latency-sensitive multi-item workloads
(clause extraction, deviation scoring, mitigation generation).
"""
from pathlib import Path

import asyncio
import concurrent.futures
import json
import logging
import math
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

GROQ_API_KEY_RAW = os.getenv("GROQ_API_KEY", "").strip()
GROQ_API_KEYS_RAW = os.getenv("GROQ_API_KEYS", "").strip()

_combined_raw = GROQ_API_KEYS_RAW or GROQ_API_KEY_RAW
GROQ_API_KEYS: List[str] = []
if _combined_raw:
    candidates = _combined_raw.split(",")
    GROQ_API_KEYS = [k.strip() for k in candidates if k.strip().startswith("gsk_")]
    if not GROQ_API_KEYS and _combined_raw:
        GROQ_API_KEYS = [_combined_raw]

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT_SECONDS", "45"))
MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "2"))
GROQ_MAX_CONCURRENT = max(1, int(os.getenv("GROQ_MAX_CONCURRENT", "10")))
FALLBACK_GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.2-3b-preview",
    "mixtral-8x7b-32768",
]

USE_GROQ = bool(GROQ_API_KEYS)
if USE_GROQ:
    logger.info(
        f"LLM client: Groq primary ({GROQ_MODEL}, {len(GROQ_API_KEYS)} keys, "
        f"max_concurrent={GROQ_MAX_CONCURRENT})"
    )
else:
    logger.info(f"LLM client: No Groq API key configured")


# ── JSON Parser ────────────────────────────────────────────────────────────────

def _parse_json_robust(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError("Empty response text")
    text = text.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract from ```json ... ``` block
    code_block = re.search(r'```(?:json)?\s*([\s\S]*?)```', text, re.IGNORECASE)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: find outermost { ... } with brace counting
    brace_count = 0
    start_idx = -1
    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                try:
                    return json.loads(text[start_idx:i + 1])
                except json.JSONDecodeError:
                    start_idx = -1

    # Strategy 4: fix common LLM JSON errors and retry
    try:
        fixed = re.sub(r',\s*}', '}', text)
        fixed = re.sub(r',\s*]', ']', fixed)
        fixed = re.sub(r':\s*True\b', ': true', fixed)
        fixed = re.sub(r':\s*False\b', ': false', fixed)
        fixed = re.sub(r':\s*None\b', ': null', fixed)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    raise ValueError(f"All JSON parse strategies failed. Raw: {text[:300]}")


# ── Async runner (works inside and outside FastAPI event loop) ─────────────────

def _run_async(coro, timeout: Optional[float] = None):
    """
    Run a coroutine from sync context regardless of whether an event loop
    is already running (FastAPI runs sync handlers in a thread pool thread
    with no event loop, so asyncio.run() works directly there).
    """
    effective_timeout = timeout if timeout is not None else (GROQ_TIMEOUT + 10)
    try:
        asyncio.get_running_loop()
        # An event loop IS running (we're in an async context).
        # Submit to a thread to get a fresh loop.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result(timeout=effective_timeout)
    except RuntimeError:
        # No running loop — safe to call asyncio.run directly.
        return asyncio.run(coro)


def _estimate_batch_timeout(n_items: int) -> float:
    """Rough ceiling for a concurrent batch: waves of GROQ_MAX_CONCURRENT items."""
    if n_items <= 0:
        return GROQ_TIMEOUT + 10
    waves = math.ceil(n_items / GROQ_MAX_CONCURRENT)
    return (waves * GROQ_TIMEOUT) + 15


# ── Key rotation ───────────────────────────────────────────────────────────────

_key_index = 0
_key_errors: Dict[str, int] = {}


def _next_groq_key() -> Optional[str]:
    global _key_index
    if not GROQ_API_KEYS:
        return None
    # Simple round-robin, skip keys with too many errors
    for _ in range(len(GROQ_API_KEYS)):
        key = GROQ_API_KEYS[_key_index % len(GROQ_API_KEYS)]
        _key_index += 1
        if _key_errors.get(key, 0) < 3:
            return key
    # All keys have errors — reset and try again
    _key_errors.clear()
    key = GROQ_API_KEYS[0]
    _key_index = 1
    return key


# ── Shared aiohttp session for connection pooling ─────────────────────────────
# Removed: Global shared session causes event loop errors when called from
# multiple sync-to-async contexts (like FastAPI threadpools).
# We now use per-batch sessions instead.


# ── Groq async implementation ──────────────────────────────────────────────────

async def _call_groq_async(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2000,
    json_mode: bool = False,
    model: str = None,
    session: Any = None
) -> str:
    import aiohttp


    if not GROQ_API_KEYS:
        raise RuntimeError("No Groq API keys configured")

    api_key = _next_groq_key()
    if not api_key:
        raise RuntimeError("No healthy Groq API keys available")

    model = model or GROQ_MODEL
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "stream": False
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    # Use provided session or create a temporary one
    if session is None:
        async with aiohttp.ClientSession() as temp_session:
            return await _do_groq_request(
                temp_session, url, headers, payload, api_key, model
            )
    else:
        return await _do_groq_request(
            session, url, headers, payload, api_key, model
        )

async def _do_groq_request(session, url, headers, payload, api_key, model):
    import aiohttp
    try:
        async with session.post(
            url, headers=headers, json=payload,
            timeout=aiohttp.ClientTimeout(total=GROQ_TIMEOUT)
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                _key_errors[api_key] = _key_errors.get(api_key, 0) + 1
                raise RuntimeError(f"Groq HTTP {resp.status}: {body[:200]}")

            data = await resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("Groq response missing choices")

            message = choices[0].get("message", {})
            content = message.get("content", "")
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("Groq response missing content")

            tokens = data.get("usage", {}).get("total_tokens", 0)
            logger.info(f"Groq success | model={model} | tokens={tokens}")
            return content

    except asyncio.TimeoutError:
        _key_errors[api_key] = _key_errors.get(api_key, 0) + 1
        raise RuntimeError("Groq request timed out")

    except RuntimeError:
        raise

    except Exception as e:
        _key_errors[api_key] = _key_errors.get(api_key, 0) + 1
        logger.warning(f"Groq unexpected error: {e}")
        raise RuntimeError(f"Groq failed: {e}") from e


# ── Public synchronous single-call API ──────────────────────────────────────────

def call_claude(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2000
) -> str:
    """
    Call LLM and return text response using Groq.
    """
    if not USE_GROQ:
        raise RuntimeError("No Groq API key configured")
        
    return _run_async(
        _call_groq_async(system_prompt, user_message, max_tokens, json_mode=False)
    )


def call_claude_json(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2000
) -> dict:
    """
    Call LLM and return parsed JSON dict using Groq.
    """
    if not USE_GROQ:
        raise RuntimeError("No Groq API key configured")
        
    text = _run_async(
        _call_groq_async(system_prompt, user_message, max_tokens, json_mode=True)
    )
    return _parse_json_robust(text)


# ── Public concurrent batch API ─────────────────────────────────────────────────

async def _call_groq_text_batch_async(
    items: List[Tuple[str, str]],
    max_tokens: int
) -> List[Optional[str]]:
    import aiohttp
    semaphore = asyncio.Semaphore(GROQ_MAX_CONCURRENT)

    async def _one(system_prompt: str, user_message: str, session: Any) -> Optional[str]:
        async with semaphore:
            try:
                return await _call_groq_async(
                    system_prompt, user_message, max_tokens,
                    json_mode=False, session=session
                )
            except Exception as e:
                logger.error(f"Groq batch item failed: {e}")
                return None

    connector = aiohttp.TCPConnector(limit=GROQ_MAX_CONCURRENT * 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_one(sp, um, session) for sp, um in items]
        return await asyncio.gather(*tasks)


async def _call_groq_json_batch_async(
    items: List[Tuple[str, str]],
    max_tokens: int
) -> List[Optional[dict]]:
    import aiohttp
    semaphore = asyncio.Semaphore(GROQ_MAX_CONCURRENT)

    async def _one(system_prompt: str, user_message: str, session: Any) -> Optional[dict]:
        async with semaphore:
            try:
                text = await _call_groq_async(
                    system_prompt, user_message, max_tokens,
                    json_mode=True, session=session
                )
                return _parse_json_robust(text)
            except Exception as e:
                logger.error(f"Groq JSON batch item failed: {e}")
                return None

    connector = aiohttp.TCPConnector(limit=GROQ_MAX_CONCURRENT * 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_one(sp, um, session) for sp, um in items]
        return await asyncio.gather(*tasks)


def call_claude_batch(
    items: List[Tuple[str, str]],
    max_tokens: int = 1200
) -> List[Optional[str]]:
    """
    Run multiple (system_prompt, user_message) calls concurrently.
    Returns text responses in the same order as `items`; a failed item is None.
    """
    if not items:
        return []

    if not USE_GROQ:
        logger.error("No Groq API key configured for batch call")
        return [None] * len(items)
        
    return _run_async(
        _call_groq_text_batch_async(items, max_tokens),
        timeout=_estimate_batch_timeout(len(items))
    )


def call_claude_json_batch(
    items: List[Tuple[str, str]],
    max_tokens: int = 1500
) -> List[Optional[dict]]:
    """
    Run multiple (system_prompt, user_message) JSON calls concurrently.
    Returns parsed dicts in the same order as `items`; a failed/unparseable
    item is None so callers can apply their own per-item fallback.
    """
    if not items:
        return []

    if not USE_GROQ:
        logger.error("No Groq API key configured for JSON batch call")
        return [None] * len(items)

    return _run_async(
        _call_groq_json_batch_async(items, max_tokens),
        timeout=_estimate_batch_timeout(len(items))
    )


# ── Health checks ──────────────────────────────────────────────────────────────

def check_health() -> dict:
    """Full health status for both providers."""
    groq_status = {
        "available": USE_GROQ,
        "key_count": len(GROQ_API_KEYS),
        "model": GROQ_MODEL,
        "max_concurrent": GROQ_MAX_CONCURRENT,
        "fallback_models": FALLBACK_GROQ_MODELS
    }
    if USE_GROQ:
        try:
            async def _ping():
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(
                        "https://api.groq.com/openai/v1/models",
                        headers={"Authorization": f"Bearer {GROQ_API_KEYS[0]}"},
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as r:
                        return r.status == 200

            groq_status["reachable"] = _run_async(_ping(), timeout=10)
        except Exception:
            groq_status["reachable"] = False
    return {
        "primary_provider": "groq",
        "groq": groq_status
    }


def get_status() -> dict:
    """Alias kept for backward compat with any existing callers."""
    return check_health()


def has_available_provider() -> bool:
    """Return True when at least one LLM provider is reachable enough to try."""
    return USE_GROQ
    

