#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <curl/curl.h>
#include "jarvis.h"
#include "json.h"

/* ── dynamic response buffer ───────────────────────────────────── */

typedef struct { char *data; size_t len; size_t cap; } ApiBuf;

static size_t write_cb(void *ptr, size_t size, size_t nmemb, void *ud) {
    ApiBuf *b = (ApiBuf *)ud;
    size_t n = size * nmemb;
    if (b->len + n + 1 > b->cap) {
        size_t nc = b->cap + n + 8192;
        char *nd = realloc(b->data, nc);
        if (!nd) return 0;
        b->data = nd; b->cap = nc;
    }
    memcpy(b->data + b->len, ptr, n);
    b->len += n;
    b->data[b->len] = '\0';
    return n;
}

static ApiBuf buf_new(void) {
    char *d = malloc(8192);
    if (d) d[0] = '\0';
    return (ApiBuf){ d, 0, d ? 8192 : 0 };
}

/* ── CURL helpers ──────────────────────────────────────────────── */

static struct curl_slist *make_headers(int json_body) {
    struct curl_slist *h = NULL;
    if (json_body)
        h = curl_slist_append(h, "Content-Type: application/json");
    if (g_config.api_key[0]) {
        char auth[320];
        snprintf(auth, sizeof(auth), "Authorization: Bearer %s", g_config.api_key);
        h = curl_slist_append(h, auth);
    }
    return h;
}

/* GET url — returns malloc'd body or NULL. Caller frees. */
static char *http_get(const char *url, long timeout_ms, long *code_out) {
    CURL *c = curl_easy_init();
    if (!c) return NULL;

    ApiBuf b = buf_new();
    if (!b.data) { curl_easy_cleanup(c); return NULL; }

    curl_easy_setopt(c, CURLOPT_URL,                url);
    curl_easy_setopt(c, CURLOPT_WRITEFUNCTION,      write_cb);
    curl_easy_setopt(c, CURLOPT_WRITEDATA,          &b);
    curl_easy_setopt(c, CURLOPT_TIMEOUT_MS,         timeout_ms);
    curl_easy_setopt(c, CURLOPT_CONNECTTIMEOUT_MS,  2000L);
    curl_easy_setopt(c, CURLOPT_NOSIGNAL,           1L);

    struct curl_slist *h = make_headers(0);
    if (h) curl_easy_setopt(c, CURLOPT_HTTPHEADER, h);

    CURLcode rc = curl_easy_perform(c);
    if (code_out) curl_easy_getinfo(c, CURLINFO_RESPONSE_CODE, code_out);
    if (h) curl_slist_free_all(h);
    curl_easy_cleanup(c);

    if (rc != CURLE_OK) { free(b.data); return NULL; }
    return b.data;
}

/* POST url with JSON body — returns malloc'd body or NULL. */
static char *http_post(const char *url, const char *body, long timeout_ms, long *code_out) {
    CURL *c = curl_easy_init();
    if (!c) return NULL;

    ApiBuf b = buf_new();
    if (!b.data) { curl_easy_cleanup(c); return NULL; }

    curl_easy_setopt(c, CURLOPT_URL,                url);
    curl_easy_setopt(c, CURLOPT_POST,               1L);
    curl_easy_setopt(c, CURLOPT_POSTFIELDS,         body);
    curl_easy_setopt(c, CURLOPT_WRITEFUNCTION,      write_cb);
    curl_easy_setopt(c, CURLOPT_WRITEDATA,          &b);
    curl_easy_setopt(c, CURLOPT_TIMEOUT_MS,         timeout_ms);
    curl_easy_setopt(c, CURLOPT_CONNECTTIMEOUT_MS,  2000L);
    curl_easy_setopt(c, CURLOPT_NOSIGNAL,           1L);

    struct curl_slist *h = make_headers(1);
    curl_easy_setopt(c, CURLOPT_HTTPHEADER, h);

    CURLcode rc = curl_easy_perform(c);
    if (code_out) curl_easy_getinfo(c, CURLINFO_RESPONSE_CODE, code_out);
    curl_slist_free_all(h);
    curl_easy_cleanup(c);

    if (rc != CURLE_OK) { free(b.data); return NULL; }
    return b.data;
}

/* Build full URL from base + path */
static void api_url(char *buf, size_t sz, const char *path) {
    snprintf(buf, sz, "%s%s", g_config.api_url, path);
}

/* ── public: api_online / api_get_json ─────────────────────────── */

void api_init(void) {
    curl_global_init(CURL_GLOBAL_ALL);
}

char *api_get_json(const char *path, long timeout_ms) {
    char url[512]; api_url(url, sizeof(url), path);
    long code = 0;
    char *raw = http_get(url, timeout_ms, &code);
    if (!raw || code != 200) { free(raw); return NULL; }
    return raw;
}

int api_online(void) {
    char url[512]; api_url(url, sizeof(url), "/api/health");
    long code = 0;
    char *r = http_get(url, 2000L, &code);
    int ok = (r != NULL && code == 200);
    free(r);
    return ok;
}

/* ── jarvis status ──────────────────────────────────────────────── */

static int status_online(void) {
    char url[512]; api_url(url, sizeof(url), "/api/live");
    long code = 0;
    char *raw = http_get(url, 5000L, &code);
    if (!raw || code != 200) { free(raw); return 0; }

    JsonNode *root = json_parse(raw);
    free(raw);
    if (!root) return 0;

    const char *name     = json_str(root,  "state.hi.display_name");
    const char *focus    = json_str(root,  "status.current_focus");
    const char *net      = json_str(root,  "status.connectivity");
    const char *last_cmd = json_str(root,  "status.last_command");
    int listener         = json_bool(root, "status.listener_online", 0);
    int dev_trusted      = json_bool(root, "status.device_trusted",  0);

    /* workflow fields live in state.workflow */
    const char *wstatus = json_str(root, "state.workflow.status");

    /* task summary */
    int total = json_count(root, "state.workflow.tasks");
    int active = 0, blocked = 0, done = 0;
    for (int i = 0; i < total; i++) {
        JsonNode *t = json_item(root, "state.workflow.tasks", i);
        const char *st = json_str(t, "status");
        if (!st) continue;
        if (strcmp(st, "todo") == 0 || strcmp(st, "doing") == 0) active++;
        else if (strcmp(st, "blocked") == 0) blocked++;
        else if (strcmp(st, "done")    == 0) done++;
    }

    char tasks_str[64];
    snprintf(tasks_str, sizeof(tasks_str), "%d active  %d blocked  %d done",
             active, blocked, done);

    /* Strip http:// from api_url for display */
    const char *api_disp = g_config.api_url;
    if (strncmp(api_disp, "http://", 7) == 0)  api_disp += 7;
    if (strncmp(api_disp, "https://", 8) == 0) api_disp += 8;
    char api_str[80];
    snprintf(api_str, sizeof(api_str), "online  (%.55s)", api_disp);

    j_box_header("STATUS", jarvis_time_str());
    j_box_empty();
    j_box_row(NULL,      name ? name : g_config.name);
    j_box_empty();
    j_box_row("Focus",   (focus && focus[0] && strcmp(focus,"none") != 0) ? focus : "(none set)");
    j_box_row("State",   wstatus ? wstatus : "ready");
    j_box_row("Tasks",   tasks_str);
    j_box_empty();
    j_box_row("API",     api_str);
    j_box_row("Network", net    ? net    : "unknown");
    j_box_row("Device",  dev_trusted ? "trusted" : "not trusted");
    if (listener &&
        last_cmd && last_cmd[0] && strcmp(last_cmd, "none") != 0)
        j_box_row("Last", last_cmd);
    j_box_empty();
    j_box_footer();

    json_free(root);
    return 1;
}

int cmd_status(void) {
    if (api_online() && status_online()) return EXIT_OK;
    /* API unreachable — fall back to offline state.json */
    j_dim("  API offline — reading state.json\n\n");
    return cmd_status_offline();
}

/* ── jarvis health ──────────────────────────────────────────────── */

int cmd_health(void) {
    char url[512]; api_url(url, sizeof(url), "/api/status");
    long code = 0;
    char *raw = http_get(url, 5000L, &code);

    if (!raw || code != 200) {
        free(raw);
        j_error("API not reachable at %s\n", g_config.api_url);
        return EXIT_ERR;
    }

    JsonNode *root = json_parse(raw);
    free(raw);
    if (!root) { j_error("failed to parse /api/status\n"); return EXIT_ERR; }

    const char *hostname = json_str(root,  "hostname");
    const char *os_str   = json_str(root,  "os");
    const char *net      = json_str(root,  "connectivity");
    const char *time_str = json_str(root,  "time");
    int listener         = json_bool(root, "listener_online", 0);
    int jarvis_ok        = json_bool(root, "jarvis_online",   0);
    int dev_reg          = json_bool(root, "device_registered", 0);
    int dev_trusted      = json_bool(root, "device_trusted",  0);

    j_box_header("HEALTH", jarvis_time_str());
    j_box_empty();
    j_box_row("API",      "online");
    j_box_row("Listener", listener  ? "online"  : "offline");
    j_box_row("Jarvis",   jarvis_ok ? "loaded"  : "error");
    j_box_row("Network",  net ? net : "unknown");
    j_box_row("Device",   dev_trusted ? "trusted"
                          : dev_reg    ? "registered"
                          : "not registered");
    if (hostname) j_box_row("Host",   hostname);
    if (os_str)   j_box_row("OS",     os_str);
    if (time_str) j_box_row("Time",   time_str);
    j_box_empty();
    j_box_footer();

    json_free(root);
    return EXIT_OK;
}

/* ── jarvis run "command" ───────────────────────────────────────── */

/* Escape for JSON string — writes to out (max outlen bytes) */
static void json_escape_str(const char *src, char *out, size_t outlen) {
    size_t i = 0;
    while (*src && i + 2 < outlen) {
        if (*src == '"' || *src == '\\') {
            if (i + 3 >= outlen) break;
            out[i++] = '\\';
        }
        out[i++] = *src++;
    }
    out[i] = '\0';
}

/* Print a multi-line string with "  " indent on each line */
static void print_indented(const char *text) {
    if (!text || !text[0]) return;
    /* Strip trailing newlines */
    size_t len = strlen(text);
    while (len > 0 && text[len-1] == '\n') len--;

    char *dup = malloc(len + 1);
    if (!dup) return;
    memcpy(dup, text, len);
    dup[len] = '\0';

    char *line = strtok(dup, "\n");
    while (line) {
        j_print("  %s\n", line);
        line = strtok(NULL, "\n");
    }
    free(dup);
}

int cmd_run(int argc, char *argv[]) {
    if (argc < 2) {
        j_error("usage: jarvis run \"command text\"\n");
        return EXIT_ERR;
    }

    /* Join remaining args into one command string */
    char cmd[512] = {0};
    for (int i = 1; i < argc; i++) {
        if (i > 1) strncat(cmd, " ", sizeof(cmd) - strlen(cmd) - 1);
        strncat(cmd, argv[i], sizeof(cmd) - strlen(cmd) - 1);
    }

    if (!api_online()) {
        j_error("API not reachable at %s\n", g_config.api_url);
        return EXIT_ERR;
    }

    char url[512]; api_url(url, sizeof(url), "/api/command");
    char esc[512]; json_escape_str(cmd, esc, sizeof(esc));
    char body[640];
    snprintf(body, sizeof(body), "{\"command\":\"%s\"}", esc);

    long code = 0;
    char *raw = http_post(url, body, 12000L, &code);
    if (!raw) { j_error("API request failed\n"); return EXIT_ERR; }

    if (code == 429) {
        j_error("rate limit exceeded\n");
        free(raw);
        return EXIT_ERR;
    }

    JsonNode *root = json_parse(raw);
    free(raw);
    if (!root) { j_error("failed to parse response\n"); return EXIT_ERR; }

    int ok           = json_bool(root, "ok", 0);
    const char *result = json_str(root, "result");
    const char *error  = json_str(root, "error");
    const char *action = json_str(root, "action");

    j_print("\n");
    j_dim("  > %s", cmd);
    if (action && action[0]) j_dim("  [%s]", action);
    j_print("\n\n");

    if (result && result[0]) {
        print_indented(result);
    } else if (error && error[0]) {
        j_error("%s\n", error);
    }
    j_print("\n");

    json_free(root);
    return ok ? EXIT_OK : EXIT_ERR;
}

/* ── jarvis ask "question" ──────────────────────────────────────────── */

/* Word-wrap text at `width` chars, printing each line with "  " indent */
static void print_wrapped(const char *text, int width) {
    if (!text || !text[0]) return;
    const char *p = text;
    while (*p) {
        const char *nl = strchr(p, '\n');
        int line_len = nl ? (int)(nl - p) : (int)strlen(p);

        if (line_len == 0) {
            j_print("\n");
        } else {
            int pos = 0;
            while (pos < line_len) {
                int rem = line_len - pos;
                if (rem <= width) {
                    j_print("  %.*s\n", rem, p + pos);
                    pos += rem;
                } else {
                    int wrap = width;
                    while (wrap > 0 && p[pos + wrap] != ' ') wrap--;
                    if (wrap == 0) wrap = width;
                    j_print("  %.*s\n", wrap, p + pos);
                    pos += wrap;
                    while (pos < line_len && p[pos] == ' ') pos++;
                }
            }
        }
        p += line_len;
        if (*p == '\n') p++;
    }
}

/* Online path — POST /api/command "ask <question>", return result or NULL */
static char *ask_online(const char *question) {
    char url[512]; api_url(url, sizeof(url), "/api/command");

    char esc[1024]; json_escape_str(question, esc, sizeof(esc));
    char body[1200];
    snprintf(body, sizeof(body), "{\"command\":\"ask %s\"}", esc);

    long code = 0;
    char *raw = http_post(url, body, 60000L, &code);
    if (!raw) return NULL;

    if (code == 429) { free(raw); j_error("rate limit exceeded\n"); return NULL; }
    if (code != 200) { free(raw); return NULL; }

    JsonNode *root = json_parse(raw);
    free(raw);
    if (!root) return NULL;

    const char *result = json_str(root, "result");
    const char *error  = json_str(root, "error");
    char *out = NULL;

    if (result && result[0]) {
        out = strdup(result);
    } else if (error && error[0]) {
        out = strdup(error);
    }
    json_free(root);
    return out;
}

/* Offline path — direct Ollama call at g_config.ai_url */
static char *ask_ollama(const char *question) {
    char url[320];
    snprintf(url, sizeof(url), "%s/api/generate", g_config.ai_url);

    /* Build context from state.json if available */
    char context[512] = "You are Jarvis, a personal AI assistant. Be concise.";
    JsonNode *s = state_load();
    if (s) {
        const char *name  = json_str(s, "profile.display_name");
        const char *focus = json_str(s, "workflow.current_focus");
        snprintf(context, sizeof(context),
            "You are Jarvis, personal AI assistant for %s. "
            "Current focus: %s. Be concise and direct.",
            name  && name[0]  ? name  : g_config.name,
            focus && focus[0] ? focus : "unset");
        json_free(s);
    }

    char esc_ctx[600];  json_escape_str(context,  esc_ctx,  sizeof(esc_ctx));
    char esc_q[1024];   json_escape_str(question, esc_q,    sizeof(esc_q));

    char body[2048];
    snprintf(body, sizeof(body),
        "{\"model\":\"%s\","
        "\"system\":\"%s\","
        "\"prompt\":\"%s\","
        "\"stream\":false}",
        g_config.ai_model, esc_ctx, esc_q);

    long code = 0;
    char *raw = http_post(url, body, 60000L, &code);
    if (!raw || code != 200) { free(raw); return NULL; }

    JsonNode *root = json_parse(raw);
    free(raw);
    if (!root) return NULL;

    const char *resp = json_str(root, "response");
    char *out = (resp && resp[0]) ? strdup(resp) : NULL;
    json_free(root);
    return out;
}

int cmd_ask(int argc, char *argv[]) {
    if (argc < 2) {
        j_error("usage: jarvis ask \"question\"\n");
        return EXIT_ERR;
    }

    char question[1024] = {0};
    for (int i = 1; i < argc; i++) {
        if (i > 1) strncat(question, " ", sizeof(question) - strlen(question) - 1);
        strncat(question, argv[i], sizeof(question) - strlen(question) - 1);
    }

    j_print("\n");
    j_dim("  > %s\n\n", question);

    int online = api_online();
    char *answer = online ? ask_online(question) : NULL;

    if (!answer && strcmp(g_config.ai_provider, "ollama") == 0) {
        if (!online) j_dim("  API offline — asking Ollama directly\n\n");
        answer = ask_ollama(question);
    }

    if (!answer) {
        j_error("no AI available — check API or Ollama at %s\n", g_config.ai_url);
        return EXIT_ERR;
    }

    print_wrapped(answer, 70);
    j_print("\n");
    free(answer);
    return EXIT_OK;
}

/* ── C-4: write commands ────────────────────────────────────────────── */

/* POST /api/command <cmd_str>, print result, return exit code.
 * Callers must verify api_online() before calling. */
static int api_write_cmd(const char *cmd_str, long timeout_ms) {
    char url[512]; api_url(url, sizeof(url), "/api/command");
    char esc[1024]; json_escape_str(cmd_str, esc, sizeof(esc));
    char body[1200]; snprintf(body, sizeof(body), "{\"command\":\"%s\"}", esc);

    long code = 0;
    char *raw = http_post(url, body, timeout_ms, &code);
    if (!raw || code != 200) { free(raw); j_error("API request failed\n"); return EXIT_ERR; }

    JsonNode *root = json_parse(raw); free(raw);
    if (!root) { j_error("failed to parse response\n"); return EXIT_ERR; }

    int ok             = json_bool(root, "ok", 0);
    const char *result = json_str(root, "result");
    const char *error  = json_str(root, "error");

    if (result && result[0]) j_success("  %s\n\n", result);
    else if (error && error[0]) j_error("%s\n", error);

    json_free(root);
    return ok ? EXIT_OK : EXIT_ERR;
}

static void join_args(char *buf, size_t sz, int argc, char *argv[], int start) {
    buf[0] = '\0';
    for (int i = start; i < argc; i++) {
        if (i > start) strncat(buf, " ", sz - strlen(buf) - 1);
        strncat(buf, argv[i], sz - strlen(buf) - 1);
    }
}

int cmd_remember(int argc, char *argv[]) {
    if (argc < 2) { j_error("usage: jarvis remember <note text>\n"); return EXIT_ERR; }
    if (!api_online()) { j_error("API not reachable at %s\n", g_config.api_url); return EXIT_ERR; }
    char note[1024]; join_args(note, sizeof(note), argc, argv, 1);
    char cmd[1200]; snprintf(cmd, sizeof(cmd), "add memory %s", note);
    j_print("\n"); j_dim("  saving: %s\n\n", note);
    return api_write_cmd(cmd, 12000L);
}

int cmd_set_focus(int argc, char *argv[]) {
    if (argc < 2) { j_error("usage: jarvis set-focus <focus text>\n"); return EXIT_ERR; }
    if (!api_online()) { j_error("API not reachable at %s\n", g_config.api_url); return EXIT_ERR; }
    char focus[512]; join_args(focus, sizeof(focus), argc, argv, 1);
    char cmd[600]; snprintf(cmd, sizeof(cmd), "set current focus %s", focus);
    j_print("\n"); j_dim("  setting focus: %s\n\n", focus);
    return api_write_cmd(cmd, 12000L);
}

/* ── C-5: sync ──────────────────────────────────────────────────────── */

int cmd_sync(void) {
    if (!api_online()) {
        j_error("API not reachable at %s\n", g_config.api_url);
        return EXIT_ERR;
    }

    char url[512];
    long code = 0;

    /* Manifest */
    api_url(url, sizeof(url), "/api/sync/manifest");
    char *mraw = http_get(url, 5000L, &code);
    if (!mraw || code != 200) { free(mraw); j_error("sync manifest unavailable\n"); return EXIT_ERR; }
    JsonNode *manifest = json_parse(mraw); free(mraw);

    /* Peers */
    api_url(url, sizeof(url), "/api/sync/peers");
    char *praw = http_get(url, 5000L, &code);
    JsonNode *peers = (praw && code == 200) ? json_parse(praw) : NULL;
    free(praw);

    /* State summary */
    api_url(url, sizeof(url), "/api/sync/state-summary");
    char *sraw = http_get(url, 5000L, &code);
    JsonNode *summary = (sraw && code == 200) ? json_parse(sraw) : NULL;
    free(sraw);

    const char *device   = json_str(manifest, "label");
    const char *dev_id   = json_str(manifest, "device_id");
    const char *last_sync= json_str(manifest, "last_sync");
    int mem_count        = json_int(manifest, "memory_count", 0);
    int peer_count       = json_count(peers, "peers");

    char dev_str[128];
    char id_short[10] = {0};
    if (dev_id && strlen(dev_id) >= 8) snprintf(id_short, sizeof(id_short), "%.8s", dev_id);
    snprintf(dev_str, sizeof(dev_str), "%s  (%s)",
             device ? device : "unknown", id_short[0] ? id_short : "?");

    char peers_str[64];
    if (peer_count == 0)
        snprintf(peers_str, sizeof(peers_str), "none registered");
    else
        snprintf(peers_str, sizeof(peers_str), "%d peer%s", peer_count, peer_count == 1 ? "" : "s");

    char mem_str[32];
    snprintf(mem_str, sizeof(mem_str), "%d shareable", mem_count);

    char last_str[64];
    if (!last_sync || strcmp(last_sync, "null") == 0 || last_sync[0] == '\0')
        snprintf(last_str, sizeof(last_str), "never");
    else
        snprintf(last_str, sizeof(last_str), "%.19s", last_sync); /* trim to datetime */

    j_box_header("SYNC", jarvis_time_str());
    j_box_empty();
    j_box_row("Device",   dev_str);
    j_box_row("Peers",    peers_str);
    j_box_row("Memory",   mem_str);
    j_box_row("Last",     last_str);
    if (summary) {
        const char *focus = json_str(summary, "current_focus");
        if (focus && focus[0]) j_box_row("Focus", focus);
    }
    j_box_empty();
    j_box_footer();

    json_free(manifest);
    if (peers)   json_free(peers);
    if (summary) json_free(summary);
    return EXIT_OK;
}

/* ── C-5: journal ───────────────────────────────────────────────────── */

int cmd_journal(int argc, char *argv[]) {
    int hours = 24;
    if (argc >= 2) hours = atoi(argv[1]);
    if (hours <= 0 || hours > 168) hours = 24;

    if (!api_online()) {
        j_error("API not reachable at %s\n", g_config.api_url);
        return EXIT_ERR;
    }

    char url[512];
    api_url(url, sizeof(url), "/api/journal");
    char full_url[640];
    snprintf(full_url, sizeof(full_url), "%s?hours=%d&limit=30", url, hours);

    long code = 0;
    char *raw = http_get(full_url, 8000L, &code);
    if (!raw || code != 200) { free(raw); j_error("journal unavailable\n"); return EXIT_ERR; }

    JsonNode *root = json_parse(raw); free(raw);
    if (!root) { j_error("failed to parse journal\n"); return EXIT_ERR; }

    int total = json_count(root, "events");

    j_bold("\n  Journal  ");
    j_dim("(last %dh — %d events)\n\n", hours, total);

    if (total == 0) {
        j_dim("  No events.\n\n");
        json_free(root);
        return EXIT_OK;
    }

    for (int i = 0; i < total && i < 30; i++) {
        JsonNode *ev = json_item(root, "events", i);
        if (!ev) continue;
        const char *ts      = json_str(ev, "ts");
        const char *type    = json_str(ev, "type");
        const char *source  = json_str(ev, "source");

        /* Extract HH:MM from ISO ts: "2026-05-18T14:35:..." */
        char time_str[8] = {0};
        if (ts && strlen(ts) >= 16) snprintf(time_str, sizeof(time_str), "%.5s", ts + 11);
        else if (ts) snprintf(time_str, sizeof(time_str), "--:--");

        char label[32] = {0};
        if (source && source[0]) snprintf(label, sizeof(label), "%.14s", source);
        else if (type && type[0]) snprintf(label, sizeof(label), "%.14s", type);

        /* payload is a nested object — extract the most useful field */
        const char *cmd_str = json_str(ev, "payload.command");
        const char *task    = json_str(ev, "payload.task");
        const char *text    = json_str(ev, "payload.text");
        const char *action  = json_str(ev, "payload.action");

        char detail[72] = {0};
        if      (cmd_str && cmd_str[0]) snprintf(detail, sizeof(detail), "%.68s", cmd_str);
        else if (task    && task[0])    snprintf(detail, sizeof(detail), "%.68s", task);
        else if (text    && text[0])    snprintf(detail, sizeof(detail), "%.68s", text);
        else if (action  && action[0])  snprintf(detail, sizeof(detail), "%.68s", action);
        else if (type    && type[0])    snprintf(detail, sizeof(detail), "%.68s", type);

        j_dim("  %s  ", time_str);
        j_print("%-16s", label);
        j_dim("  %s\n", detail);
    }
    j_print("\n");

    json_free(root);
    return EXIT_OK;
}

/* ── C-6: notify ────────────────────────────────────────────────────── */

/* Send a desktop notification via notify-send (fork+exec, no shell) */
void api_notify_send(const char *message) {
    pid_t pid = fork();
    if (pid < 0) return;
    if (pid == 0) {
        execlp("notify-send", "notify-send",
               "-a", "Jarvis", "-i", "dialog-information",
               "Jarvis", message, (char *)NULL);
        _exit(0);
    }
    /* Don't wait — fire and forget */
}

int cmd_notify(int argc, char *argv[]) {
    if (argc < 2) { j_error("usage: jarvis notify <message>\n"); return EXIT_ERR; }
    char msg[512] = {0};
    join_args(msg, sizeof(msg), argc, argv, 1);
    j_success("  %s\n\n", msg);
    api_notify_send(msg);
    return EXIT_OK;
}

