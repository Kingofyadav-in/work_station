#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
import urllib.request
import re
from collections import deque
from pathlib import Path
from typing import Any, Generator, cast

from behavior import build_behavior_rules
from context import get_runtime_context
from profile_manager import get_session

_ROOT_DIR      = Path(__file__).resolve().parent.parent
_HI_STATE_PATH = _ROOT_DIR / "Kingofyadav" / "state.json"
_HISTORY_PATH  = _ROOT_DIR / "logs" / "ai_history.jsonl"
_HISTORY_LOCK  = _ROOT_DIR / "logs" / "ai_history.jsonl.lock"
_MODEL_CFG     = _ROOT_DIR / "logs" / "ai_model_config.json"

if str(_ROOT_DIR / "shared") not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR / "shared"))
if str(_ROOT_DIR / "Kingofyadav") not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR / "Kingofyadav"))

from file_lock import file_lock  # noqa: E402

try:
    from memory_store import search_memories, sync_from_state  # noqa: E402
except Exception:  # pragma: no cover - memory search is optional at AI import time
    search_memories = None
    sync_from_state = None

_MAX_HISTORY     = 6
_MAX_PROMPT_CHARS = 4000

_HISTORY: deque[tuple[str, str]] = deque(maxlen=_MAX_HISTORY)
_CACHED_SYSTEM_PROMPT: str | None = None
_AI_LOCK = threading.Lock()

# ── Provider catalogue ────────────────────────────────────────────────────────

PROVIDERS: dict[str, dict] = {
    "openai": {
        "label":   "OpenAI",
        "models":  ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
        "default": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "label":   "Claude (Anthropic)",
        "models":  ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-7"],
        "default": "claude-sonnet-4-6",
        "env_key": "ANTHROPIC_API_KEY",
    },
"ollama": {
        "label":   "Ollama (Local)",
        "models":  [],
        "default": os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        "env_key": None,
    },
}

_OLLAMA_BASE = os.getenv("OLLAMA_HOST", "http://localhost:11434")
_OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
_OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "2048"))
_OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "96"))

# ── Model config (persisted to logs/ai_model_config.json) ────────────────────

def get_model_config() -> dict:
    try:
        return json.loads(_MODEL_CFG.read_text(encoding="utf-8"))
    except Exception:
        return {"provider": "ollama", "model": _OLLAMA_DEFAULT_MODEL}


def set_model_config(provider: str, model: str) -> None:
    try:
        with file_lock(_MODEL_CFG.with_suffix(_MODEL_CFG.suffix + ".lock")):
            _MODEL_CFG.parent.mkdir(parents=True, exist_ok=True)
            _MODEL_CFG.write_text(
                json.dumps({"provider": provider, "model": model}, indent=2),
                encoding="utf-8",
            )
    except Exception:
        pass


def get_active_provider() -> str:
    return get_model_config().get("provider", "openai")


def get_active_model() -> str:
    cfg = get_model_config()
    p   = cfg.get("provider", "openai")
    return cfg.get("model") or PROVIDERS.get(p, {}).get("default", "gpt-4o-mini")


# ── Ollama helpers ────────────────────────────────────────────────────────────

def get_ollama_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{_OLLAMA_BASE}/api/tags", timeout=2) as r:
            data = json.loads(r.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def sort_ollama_models(models: list[str]) -> list[str]:
    def score(name: str) -> tuple[float, int, int, str]:
        lower = name.lower()
        match = re.search(r"(\d+(?:\.\d+)?)b", lower)
        size = float(match.group(1)) if match else 999.0
        runtime_bias = 0 if any(token in lower for token in ("mini", "small", "tiny", "compact")) else 1
        return (size, runtime_bias, len(name), lower)

    return sorted(dict.fromkeys(models), key=score)


def _ollama_chat(model: str, messages: list[dict]) -> str:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "num_ctx": _OLLAMA_NUM_CTX,
            "num_predict": _OLLAMA_NUM_PREDICT,
        },
    }).encode()
    req  = urllib.request.Request(
        f"{_OLLAMA_BASE}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["message"]["content"]


def _ollama_stream(model: str, messages: list[dict]) -> Generator[str, None, None]:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "num_ctx": _OLLAMA_NUM_CTX,
            "num_predict": _OLLAMA_NUM_PREDICT,
        },
    }).encode()
    req  = urllib.request.Request(
        f"{_OLLAMA_BASE}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            if not raw.strip():
                continue
            chunk = json.loads(raw)
            delta = chunk.get("message", {}).get("content", "")
            if delta:
                yield delta
            if chunk.get("done"):
                break


# ── Provider status ───────────────────────────────────────────────────────────

def provider_status(provider: str | None = None) -> dict[str, str]:
    p = provider or get_active_provider()

    if p == "openai":
        try:
            from openai import OpenAI  # noqa: F401
        except ImportError:
            return {"status": "unavailable", "message": "openai SDK not installed — pip install openai"}
        if not os.getenv("OPENAI_API_KEY"):
            return {"status": "unconfigured", "message": "OPENAI_API_KEY not set in .env"}
        m = get_active_model() if p == get_active_provider() else PROVIDERS["openai"]["default"]
        base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        label = "Groq" if "groq.com" in base_url else "OpenAI"
        return {"status": "ready", "message": f"{label} · {m}"}

    if p == "anthropic":
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return {"status": "unavailable", "message": "anthropic SDK not installed — pip install anthropic"}
        if not os.getenv("ANTHROPIC_API_KEY"):
            return {"status": "unconfigured", "message": "ANTHROPIC_API_KEY not set in .env"}
        m = get_active_model() if p == get_active_provider() else PROVIDERS["anthropic"]["default"]
        return {"status": "ready", "message": f"Claude · {m}"}

    if p == "ollama":
        models = sort_ollama_models(get_ollama_models())
        if not models:
            return {"status": "unavailable", "message": f"Ollama not reachable at {_OLLAMA_BASE}  — run: ollama serve"}
        m = get_active_model() if p == get_active_provider() else models[0]
        return {"status": "ready", "message": f"Ollama · {m}  ({len(models)} models)"}

    return {"status": "unknown", "message": f"Unknown provider: {p}"}


def ai_status() -> dict[str, str]:
    return provider_status(get_active_provider())


# ── History ───────────────────────────────────────────────────────────────────

def _load_hi_state() -> dict:
    try:
        return json.loads(_HI_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_history_from_disk() -> None:
    try:
        with file_lock(_HISTORY_LOCK):
            if not _HISTORY_PATH.exists():
                return
            lines = _HISTORY_PATH.read_text(encoding="utf-8").splitlines()
        pairs: list[tuple[str, str]] = []
        for line in lines[-(_MAX_HISTORY * 2):]:
            try:
                obj = json.loads(line)
                pairs.append((obj["user"], obj["assistant"]))
            except Exception:
                continue
        for pair in pairs[-_MAX_HISTORY:]:
            _HISTORY.append(pair)
    except Exception:
        pass


def _append_history_to_disk(user: str, assistant: str) -> None:
    try:
        with file_lock(_HISTORY_LOCK):
            _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _HISTORY_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"user": user, "assistant": assistant}, ensure_ascii=False) + "\n")
            lines = _HISTORY_PATH.read_text(encoding="utf-8").splitlines()
            if len(lines) > _MAX_HISTORY * 2:
                _HISTORY_PATH.write_text(
                    "\n".join(lines[-(_MAX_HISTORY * 2):]) + "\n", encoding="utf-8"
                )
    except Exception:
        pass


_load_history_from_disk()


# ── Prompt builders ───────────────────────────────────────────────────────────

def _cap_prompt(prompt: str) -> str:
    return prompt[:_MAX_PROMPT_CHARS] + " [truncated]" if len(prompt) > _MAX_PROMPT_CHARS else prompt


def _build_system_prompt(behavior: dict) -> str:
    global _CACHED_SYSTEM_PROMPT
    key = f"{behavior['response_mode']}:{behavior['command_style']}"
    with _AI_LOCK:
        if _CACHED_SYSTEM_PROMPT and _CACHED_SYSTEM_PROMPT.startswith(f"__key:{key}__"):
            return _CACHED_SYSTEM_PROMPT[len(f"__key:{key}__"):]
        prompt = (
            "You are Jarvis, a Human Interface bridge. "
            "Human decides. Jarvis interprets. CLI executes. System responds. Human confirms. "
            "Provide detailed, well-structured responses with clear sections, explanations, and examples when relevant. "
            "Be thorough — cover context, rationale, steps, and edge cases. Use markdown formatting. "
            f"Current response mode is {behavior['response_mode']}. "
            f"Preferred command style is {behavior['command_style']}."
        )
        _CACHED_SYSTEM_PROMPT = f"__key:{key}__{prompt}"
        return prompt


def _user_context_message(prefix: str, prompt: str) -> str:
    context  = get_runtime_context(log_limit=5)
    profiles = context["profiles"]
    hi       = profiles.get("HI", {})
    ai       = profiles.get("AI", {})
    hi_state = _load_hi_state()
    memory   = hi_state.get("memory", [])
    workflow = hi_state.get("workflow", {})
    prefs    = hi_state.get("preferences", {})
    recent_memory_texts = [m.get("text", "") for m in memory[-5:]] if memory else []
    relevant_memory_texts: list[str] = []
    if search_memories is not None and sync_from_state is not None:
        try:
            sync_from_state(memory)
            for item in search_memories(prompt, limit=5):
                text = item.get("text") or item.get("event") or item.get("command")
                if text:
                    relevant_memory_texts.append(str(text))
        except Exception:
            relevant_memory_texts = []

    return (
        f"{prefix}\n"
        f"Human: {hi.get('name')} | role: {hi.get('role')} | domain: {hi.get('domain')} | lang: {hi.get('language')}\n"
        f"AI: {ai.get('name')} | mode: {ai.get('mode')}\n"
        f"Response mode: {hi.get('preferred_response_mode', 'adaptive')}\n"
        f"Focus: {workflow.get('current_focus') or 'none'}\n"
        f"Memory ({len(memory)} total, last 5): {recent_memory_texts if recent_memory_texts else 'none'}\n"
        f"Relevant memory for this request: {relevant_memory_texts if relevant_memory_texts else 'none'}\n"
        f"Preferences: response_mode={prefs.get('response_mode','adaptive')}, verbosity={prefs.get('verbosity','medium')}\n"
        f"Recent logs:\n{context['recent_logs']}\n\n"
        f"User request: {_cap_prompt(prompt)}"
    )


def _build_messages(system_prompt: str, user_prompt: str) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": system_prompt}]
    with _AI_LOCK:
        history_snapshot = list(_HISTORY)
    for past_user, past_asst in history_snapshot:
        msgs.append({"role": "user",      "content": past_user})
        msgs.append({"role": "assistant", "content": past_asst})
    msgs.append({"role": "user", "content": user_prompt})
    return msgs


# ── Core inference ────────────────────────────────────────────────────────────

def _call_model(system_prompt: str, messages: list[dict], provider: str, model: str) -> str:
    if provider == "openai":
        from openai import OpenAI
        _base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        content = OpenAI(base_url=_base_url).chat.completions.create(
            model=model,
            messages=cast(Any, messages),
        ).choices[0].message.content
        return content or ""

    if provider == "anthropic":
        import anthropic
        sys_content = next((m["content"] for m in messages if m["role"] == "system"), system_prompt)
        user_msgs   = [m for m in messages if m["role"] != "system"]
        resp = anthropic.Anthropic().messages.create(
            model=model, max_tokens=4096,
            system=sys_content, messages=cast(Any, user_msgs),
        )
        block = resp.content[0] if resp.content else None
        return str(getattr(block, "text", "") or "")

    if provider == "ollama":
        return _ollama_chat(model, messages)

    raise ValueError(f"Unknown provider: {provider}")


def _stream_model(system_prompt: str, messages: list[dict], provider: str, model: str) -> Generator[str, None, None]:
    if provider == "openai":
        from openai import OpenAI
        with OpenAI().chat.completions.create(model=model, messages=cast(Any, messages), stream=True) as s:
            for chunk in s:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield delta
        return

    if provider == "anthropic":
        import anthropic
        sys_content = next((m["content"] for m in messages if m["role"] == "system"), system_prompt)
        user_msgs   = [m for m in messages if m["role"] != "system"]
        with anthropic.Anthropic().messages.stream(
            model=model, max_tokens=4096,
            system=sys_content, messages=cast(Any, user_msgs),
        ) as s:
            for text in s.text_stream:
                yield text
        return

    if provider == "ollama":
        yield from _ollama_stream(model, messages)
        return

    raise ValueError(f"Unknown provider: {provider}")


# ── Public API ────────────────────────────────────────────────────────────────

def ask_ai(prompt: str) -> str:
    if not prompt.strip():
        return "Refused: empty AI prompt."

    behavior = build_behavior_rules(
        get_runtime_context(log_limit=1)["profiles"],
        get_session(), prompt, action="ai", payload=prompt,
    )
    status = ai_status()
    if status["status"] != "ready":
        return status["message"]

    provider      = get_active_provider()
    model         = get_active_model()
    system_prompt = _build_system_prompt(behavior)
    user_prompt   = _user_context_message("Conversation mode.", prompt)
    messages      = _build_messages(system_prompt, user_prompt)

    reply = _call_model(system_prompt, messages, provider, model)
    with _AI_LOCK:
        _HISTORY.append((prompt, reply))
    _append_history_to_disk(prompt, reply)
    return reply


def ask_ai_stream(prompt: str) -> Generator[str, None, None]:
    if not prompt.strip():
        yield "Refused: empty AI prompt."
        return

    behavior = build_behavior_rules(
        get_runtime_context(log_limit=1)["profiles"],
        get_session(), prompt, action="ai", payload=prompt,
    )
    status = ai_status()
    if status["status"] != "ready":
        yield status["message"]
        return

    provider      = get_active_provider()
    model         = get_active_model()
    system_prompt = _build_system_prompt(behavior)
    user_prompt   = _user_context_message("Conversation mode.", prompt)
    messages      = _build_messages(system_prompt, user_prompt)

    chunks: list[str] = []
    for delta in _stream_model(system_prompt, messages, provider, model):
        chunks.append(delta)
        yield delta

    reply = "".join(chunks)
    with _AI_LOCK:
        _HISTORY.append((prompt, reply))
    _append_history_to_disk(prompt, reply)


def plan_with_ai(prompt: str) -> str:
    if not prompt.strip():
        return "Refused: empty planning prompt."

    behavior = build_behavior_rules(
        get_runtime_context(log_limit=1)["profiles"],
        get_session(), prompt, action="plan", payload=prompt,
    )
    status = ai_status()
    if status["status"] != "ready":
        return status["message"]

    provider = get_active_provider()
    model    = get_active_model()
    system_prompt = (
        "You are Jarvis in planning mode. "
        "Return a concise numbered plan. "
        "Separate human decisions from AI execution clearly. "
        "Do not claim actions already happened. "
        f"Current response mode is {behavior['response_mode']}."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": _user_context_message("Planning mode.", prompt)},
    ]
    return _call_model(system_prompt, messages, provider, model)
