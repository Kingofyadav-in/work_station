# Jarvis Web API

FastAPI control plane for Jarvis. It exposes private authenticated control endpoints, public-safe state endpoints, live streams, audit journal queries, and the website-safe Jarvis chat endpoint.

## Files

| File | Responsibility |
|---|---|
| `api.py` | FastAPI app, auth, rate limiting, command execution, live streams |
| `public_chat.py` | Public website chat safety layer, prompt, knowledge loading, logging |
| `static/jarvis-widget.js` | Embeddable public chat widget |
| `static/502.html` | Nginx/service outage fallback page |
| `nginx-kingofyadav.in.conf` | Public Nginx site config |
| `nginx-jarvis-local.conf` | Local Nginx config |
| `tests/test_api.py` | API tests |

## Start

From the repo root:

```bash
bash scripts/start_api.sh
```

Or directly:

```bash
python3 web/api.py
```

Default:

```text
http://127.0.0.1:5050/api/health
```

## Environment

```bash
API_HOST=127.0.0.1
API_PORT=5050
JARVIS_API_KEY=
ALLOWED_ORIGIN=https://kingofyadav.in
JARVIS_TRUSTED_PROXY_ADDRS=127.0.0.1,::1

# Public website chat
JARVIS_PUBLIC_CHAT=0                       # set to 1 to enable
JARVIS_PUBLIC_CHAT_RPM=12                  # rate limit per visitor per minute
JARVIS_PUBLIC_CHAT_TIMEOUT=60              # AI call timeout in seconds (use 60 with local Ollama)
JARVIS_PUBLIC_CHAT_WORKERS=1               # serialize local Ollama public requests
JARVIS_PUBLIC_SITE_ROOT=/home/kingofyadav/HI
JARVIS_PUBLIC_CHAT_PROMPT=                 # custom system prompt (uses built-in default if blank)
JARVIS_PUBLIC_CHAT_PROVIDER=               # pin to ollama/openai/anthropic (blank = global selector)
JARVIS_PUBLIC_CHAT_MODEL=                  # pin model (blank = global selector)

# Live class feature (optional)
LIVE_CLASS_TOKEN=                          # token required to POST /api/live-class state updates
```

When `JARVIS_API_KEY` is empty, private endpoints are available only from localhost. When a key or scoped token is configured, use `Authorization: Bearer <token>` or `X-Api-Key: <token>`.

## Authentication

The API supports two auth styles:

| Style | Config | Scope behavior |
|---|---|---|
| Legacy key | `JARVIS_API_KEY` | Full access |
| Scoped tokens | `JARVIS_API_TOKENS` or `logs/api_tokens.json` | `read`, `command`, or full by token |

Scoped token file example:

```json
{
  "tokens": [
    {
      "name": "dashboard",
      "token": "change-me",
      "scopes": ["read", "command"],
      "rpm": 60
    },
    {
      "name": "readonly",
      "token": "change-me-read",
      "scopes": ["read"],
      "expires_at": "2026-12-31T23:59:59+00:00"
    }
  ]
}
```

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/` | no | Endpoint index |
| `GET` | `/api/health` | no | Liveness, listener flag, router flag |
| `GET` | `/api/health/detail` | read | Latest doctor report |
| `GET` | `/api/status` | read | Host, OS, connectivity, listener, device status |
| `GET` | `/api/state` | read | Private HI and AI state snapshot |
| `GET` | `/api/public-state` | no | Public-safe profile, focus, open tasks, public memories |
| `GET` | `/api/session` | read | Jarvis session fields |
| `GET` | `/api/history` | read | Last API-executed commands |
| `GET` | `/api/live` | read | Combined status and state |
| `GET` | `/api/public-chat/config` | read | Public chat configuration |
| `GET` | `/api/public-chat/history` | read | Recent public chat records |
| `GET` | `/api/public-chat/knowledge` | read | Public knowledge source status |
| `GET` | `/api/public-intake` | read | Enquiries and access request inbox |
| `POST` | `/api/local-admin-sync` | no | Sync browser-local admin signup/login snapshots |
| `GET` | `/api/local-admin-users` | read | Synced local admin registry |
| `GET` | `/api/events` | read | Server-sent events stream |
| `GET` | `/api/journal` | read | Audit event query |
| `WS` | `/api/ws/live` | read | Authenticated live status/state stream |
| `WS` | `/api/ws/public` | no | Public-safe live state stream |
| `POST` | `/api/command` | command | Execute a private Jarvis command |
| `POST` | `/api/jarvis-chat` | conditional | Website-safe public chat |
| `POST` | `/api/public-enquiry` | no | Public enquiry form submission |
| `POST` | `/api/public-signup` | no | Public signup / access request |
| `GET` | `/api/live-class` | no | Live class public state |
| `POST` | `/api/live-class` | token | Update live class state (requires `LIVE_CLASS_TOKEN`) |
| `GET` | `/api/docs` | no | OpenAPI UI |

## Examples

Health:

```bash
curl -s http://127.0.0.1:5050/api/health
```

Private command with API key:

```bash
curl -s -X POST http://127.0.0.1:5050/api/command \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JARVIS_API_KEY" \
  -d '{"command":"status"}'
```

Journal query:

```bash
curl -s "http://127.0.0.1:5050/api/journal?hours=24&type=action_completed&limit=25" \
  -H "Authorization: Bearer $JARVIS_API_KEY"
```

Public chat:

```bash
curl -s -X POST http://127.0.0.1:5050/api/jarvis-chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What services are offered?"}'
```

## Public Chat Safety Model

Public chat is separate from private command execution.

It does not:

- Call `Jarvis/router.py` command execution.
- Execute shell commands.
- Mutate HI state.
- Expose private memory.
- Read arbitrary local files.

It does:

- Use public website knowledge files under `JARVIS_PUBLIC_SITE_ROOT`.
- Use public-safe state from `/api/public-state`.
- Apply injection-pattern filtering.
- Enforce request size and rate limits.
- Log public interactions to `logs/public_chat.jsonl`.
- Return fallback answers when configured and provider calls fail.

## Website Widget

Embed:

```html
<script
  src="/api-static/jarvis-widget.js"
  data-endpoint="/api/jarvis-chat"
  data-live-endpoint="/api/ws/public"
  data-title="Jarvis AI"
  data-subtitle="Ask Jarvis about King Yadav and the website."
  defer>
</script>
```

The widget supports:

- Chat history in browser local storage.
- Public WebSocket live state.
- Public enquiry submissions.
- Public access request submissions.
- Speech input when browser support is available.
- Optional spoken replies.
- Suggested starter prompts.

## Rate Limits and Limits

| Limit | Value |
|---|---|
| POST rate limit | 60 rpm by default, token-specific when scoped |
| Public chat rate limit | `JARVIS_PUBLIC_CHAT_RPM`, default 12 rpm |
| Request body | 65,536 bytes |
| Public chat message | 1,200 characters |
| SSE max duration | 1,800 seconds |

## Deployment Notes

- Keep Python API bound to loopback unless you have explicit auth and proxy rules.
- Put Nginx in front for TLS and public routing.
- Serve `web/static/jarvis-widget.js` from a public static path such as `/api-static/jarvis-widget.js`.
- Keep `/api/command` private.
- Only expose `/api/jarvis-chat`, `/api/public-state`, and `/api/ws/public` publicly if desired.

## Tests

From the repo root:

```bash
python3 -m unittest discover -s web/tests -v
```
