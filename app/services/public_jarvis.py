from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT_DIR / "logs" / "public_chat_config.json"
LOG_PATH = ROOT_DIR / "logs" / "public_chat.jsonl"

_JARVIS_DIR = ROOT_DIR / "Jarvis"
if str(_JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(_JARVIS_DIR))

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "fallback": True,
    "rpm": 12,
    "provider": "",
    "model": "",
    "prompt": (
        "You are Jarvis AI on kingofyadav.in. Help website visitors with concise, useful answers. "
        "You are not the private local Jarvis control plane. Do not run commands, change state, "
        "or claim access to private memory."
    ),
}


def load_config() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(data, dict):
        cfg.update(data)
    cfg["enabled"] = bool(cfg.get("enabled"))
    cfg["fallback"] = bool(cfg.get("fallback"))
    try:
        cfg["rpm"] = max(1, min(120, int(cfg.get("rpm", 12))))
    except (TypeError, ValueError):
        cfg["rpm"] = 12
    return cfg


def save_config(config: dict[str, Any]) -> None:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config)
    cfg["enabled"] = bool(cfg.get("enabled"))
    cfg["fallback"] = bool(cfg.get("fallback"))
    cfg["rpm"] = max(1, min(120, int(cfg.get("rpm", 12))))
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(CONFIG_PATH)


def read_recent_questions(limit: int = 50) -> list[dict[str, Any]]:
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    for line in lines:
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    return list(reversed(items))


_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "what", "how", "why", "where", "when",
    "who", "which", "that", "this", "these", "those", "and", "or", "but",
    "for", "with", "from", "about", "into", "onto", "your", "my", "our",
    "their", "its", "you", "me", "him", "her", "us", "them", "not", "more",
    "some", "any", "all", "each", "just", "than", "then", "also",
})


def analyze_topics(items: list[dict[str, Any]], top: int = 15) -> list[tuple[str, int]]:
    """Return the most frequent meaningful words in recent public questions."""
    counts: Counter[str] = Counter()
    for item in items:
        msg = item.get("message", "").lower()
        for word in re.findall(r"\b[a-z]{3,}\b", msg):
            if word not in _STOP_WORDS:
                counts[word] += 1
    return counts.most_common(top)


def test_public_message(message: str) -> dict[str, Any]:
    """Admin-side test: send a message through the public chat prompt (no rate limiting)."""
    try:
        from ai_connector import _call_model as call_model, ai_status, get_active_model, get_active_provider
    except Exception as exc:
        return {"ok": False, "error": f"AI connector unavailable: {exc}"}

    cfg = load_config()
    provider = cfg.get("provider") or get_active_provider()
    model = cfg.get("model") or get_active_model()
    status = ai_status()
    if status.get("status") != "ready":
        return {"ok": False, "error": status.get("message", "AI unavailable"), "provider": provider, "model": model}

    system_prompt = cfg.get("prompt") or DEFAULT_CONFIG["prompt"]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": message[:1200]},
    ]
    try:
        reply = call_model(system_prompt, messages, provider, model)
        return {"ok": True, "reply": reply, "provider": provider, "model": model}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "provider": provider, "model": model}


def get_knowledge_status() -> list[dict[str, Any]]:
    """Return availability and size of each site knowledge page."""
    site_root = Path(os.getenv("JARVIS_PUBLIC_SITE_ROOT", str(ROOT_DIR.parent / "HI")))
    candidates = [
        ("Home",          site_root / "index.html"),
        ("About Me",      site_root / "pages" / "about-me.html"),
        ("Services",      site_root / "pages" / "services.html"),
        ("Professional",  site_root / "pages" / "professional.html"),
        ("Collaboration", site_root / "pages" / "collaboration.html"),
        ("Contact",       site_root / "pages" / "contact.html"),
        ("Blog",          site_root / "pages" / "blog.html"),
        ("Blog Data",     site_root / "blog-data.json"),
    ]
    results: list[dict[str, Any]] = []
    for label, path in candidates:
        exists = path.exists()
        chars = 0
        if exists:
            try:
                chars = path.stat().st_size
            except Exception:
                pass
        results.append({"name": label, "available": exists, "chars": chars})
    return results
