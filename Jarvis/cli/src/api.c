#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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

/* ── public: api_online ─────────────────────────────────────────── */

void api_init(void) {
    curl_global_init(CURL_GLOBAL_ALL);
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
