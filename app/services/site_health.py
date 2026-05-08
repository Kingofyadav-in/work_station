from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Any

WEBSITE_URL = "https://kingofyadav.in"
API_BASE = "http://localhost:5050"

# Website pages to probe
WEBSITE_PAGES: list[tuple[str, str]] = [
    ("/",                         "Home"),
    ("/pages/about-me.html",      "About Me"),
    ("/pages/professional.html",  "Professional"),
    ("/pages/services.html",      "Services"),
    ("/pages/contact.html",       "Contact"),
    ("/pages/social.html",        "Social"),
    ("/pages/collaboration.html", "Collaboration"),
    ("/pages/blog.html",           "Blog"),
    ("/sitemap.xml",              "Sitemap"),
    ("/manifest.json",            "Manifest"),
]

# API endpoints to probe
API_ENDPOINTS: list[tuple[str, str]] = [
    ("/api/health",             "Health"),
    ("/api/status",             "Status"),
    ("/api/public-state",       "Public State"),
    ("/api/intake-stats",       "Intake Stats"),
    ("/api/public-chat/config", "Chat Config"),
    ("/api/live",               "Live"),
    ("/api/live-class",         "Live Class"),
    ("/api/journal",            "Journal"),
    ("/api/events",             "Events"),
]


def _check_url(url: str, timeout: int = 8) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Jarvis-HealthCheck/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = round((time.perf_counter() - start) * 1000)
            return {"ok": True, "status": resp.status, "ms": elapsed, "error": ""}
    except urllib.error.HTTPError as exc:
        elapsed = round((time.perf_counter() - start) * 1000)
        # 401/403 = server up, requires auth — treat as healthy
        # 404/5xx = real failure
        ok = exc.code in (401, 403)
        note = "auth-protected" if ok else ""
        return {"ok": ok, "status": exc.code, "ms": elapsed, "error": note if ok else str(exc)[:120]}
    except Exception as exc:
        elapsed = round((time.perf_counter() - start) * 1000)
        return {"ok": False, "status": 0, "ms": elapsed, "error": str(exc)[:120]}


def check_website_pages() -> list[dict[str, Any]]:
    results = []
    for path, label in WEBSITE_PAGES:
        r = _check_url(WEBSITE_URL + path)
        r["path"] = path
        r["label"] = label
        r["url"] = WEBSITE_URL + path
        results.append(r)
    return results


def check_api_endpoints() -> list[dict[str, Any]]:
    results = []
    for path, label in API_ENDPOINTS:
        r = _check_url(API_BASE + path)
        r["path"] = path
        r["label"] = label
        r["url"] = API_BASE + path
        results.append(r)
    return results


def check_all() -> dict[str, Any]:
    website = check_website_pages()
    apis = check_api_endpoints()

    web_ok = sum(1 for w in website if w["ok"])
    api_ok = sum(1 for a in apis if a["ok"])
    avg_web_ms = round(sum(w["ms"] for w in website) / len(website)) if website else 0
    avg_api_ms = round(sum(a["ms"] for a in apis) / len(apis)) if apis else 0

    return {
        "website": website,
        "apis": apis,
        "summary": {
            "website_ok": web_ok,
            "website_total": len(website),
            "api_ok": api_ok,
            "api_total": len(apis),
            "avg_web_ms": avg_web_ms,
            "avg_api_ms": avg_api_ms,
            "all_ok": web_ok == len(website) and api_ok == len(apis),
        },
    }
