#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "jarvis.h"
#include "json.h"

#define STATE_PATH_REL "dev/projects/work_station/Kingofyadav/state.json"

/* Read entire file into a malloc'd buffer — caller must free */
static char *file_read(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    rewind(f);
    if (len <= 0) { fclose(f); return NULL; }
    char *buf = malloc((size_t)len + 1);
    if (!buf) { fclose(f); return NULL; }
    size_t got = fread(buf, 1, (size_t)len, f);
    buf[got] = '\0';
    fclose(f);
    return buf;
}

JsonNode *state_load(void) {
    const char *home = getenv("HOME");
    if (!home) { j_error("HOME not set\n"); return NULL; }

    char path[1024];
    if (g_config.state_path[0] == '/') {
        snprintf(path, sizeof(path), "%s", g_config.state_path);
    } else if (g_config.state_path[0]) {
        snprintf(path, sizeof(path), "%s/%s", home, g_config.state_path);
    } else {
        snprintf(path, sizeof(path), "%s/%s", home, STATE_PATH_REL);
    }

    char *src = file_read(path);
    if (!src) {
        j_error("state.json not found: %s\n", path);
        return NULL;
    }

    JsonNode *root = json_parse(src);
    free(src);
    if (!root) { j_error("failed to parse state.json\n"); }
    return root;
}

/* ── jarvis who ─────────────────────────────────────────────── */

int cmd_who(void) {
    JsonNode *s = state_load();
    if (!s) return EXIT_ERR;

    const char *display = json_str(s, "profile.display_name");
    const char *role    = json_str(s, "profile.owner_role");
    const char *domain  = json_str(s, "profile.domain");
    const char *host    = json_str(s, "profile.host");
    const char *id      = json_str(s, "profile.id");

    j_box_header("WHO", jarvis_time_str());
    j_box_empty();
    j_box_row(NULL,     display ? display : "(unnamed)");
    j_box_empty();
    if (role   && role[0])   j_box_row("Role",   role);
    if (domain && domain[0]) j_box_row("Domain", domain);
    if (host   && host[0])   j_box_row("Host",   host);
    if (id     && id[0])     j_box_row("ID",     id);
    j_box_empty();
    j_box_footer();

    json_free(s);
    return EXIT_OK;
}

/* ── jarvis focus ───────────────────────────────────────────── */

int cmd_focus(void) {
    JsonNode *s = state_load();
    if (!s) return EXIT_ERR;

    const char *focus  = json_str(s, "workflow.current_focus");
    const char *status = json_str(s, "workflow.status");

    /* collect non-empty next_actions */
    int nact = json_count(s, "workflow.next_actions");

    if (!focus || focus[0] == '\0') {
        j_dim("\n  No current focus set.\n\n");
    } else {
        j_box_header("FOCUS", jarvis_time_str());
        j_box_empty();
        j_box_row(NULL, focus);
        j_box_empty();
        if (status && status[0]) j_box_row("Status", status);
        j_box_empty();
        j_box_footer();
    }

    if (nact > 0) {
        j_bold("\n  Next actions\n");
        for (int i = 0; i < nact && i < 5; i++) {
            JsonNode *a = json_item(s, "workflow.next_actions", i);
            if (a && a->type == JSON_STRING && a->sv && a->sv[0])
                j_print("    - %s\n", a->sv);
        }
        j_print("\n");
    }

    json_free(s);
    return EXIT_OK;
}

/* ── jarvis tasks ───────────────────────────────────────────── */

static const char *task_icon(const char *st) {
    if (!st)                        return " ";
    if (strcmp(st, "done")      == 0) return "v";
    if (strcmp(st, "doing")     == 0) return ">";
    if (strcmp(st, "blocked")   == 0) return "!";
    if (strcmp(st, "cancelled") == 0) return "x";
    return "-"; /* todo */
}

int cmd_tasks(void) {
    JsonNode *s = state_load();
    if (!s) return EXIT_ERR;

    int total = json_count(s, "workflow.tasks");

    if (total == 0) {
        j_dim("\n  No tasks.\n\n");
        json_free(s);
        return EXIT_OK;
    }

    j_bold("\n  Tasks  ");
    j_dim("(%d)\n\n", total);

    for (int i = 0; i < total; i++) {
        JsonNode *t = json_item(s, "workflow.tasks", i);
        if (!t) continue;

        const char *title  = json_str(t, "title");
        const char *status = json_str(t, "status");
        const char *due    = json_str(t, "due");
        const char *icon   = task_icon(status);

        int is_done      = status && strcmp(status, "done")      == 0;
        int is_blocked   = status && strcmp(status, "blocked")   == 0;
        int is_cancelled = status && strcmp(status, "cancelled") == 0;

        if (is_done || is_cancelled) {
            j_dim("  [%s] %s\n", icon, title ? title : "—");
        } else if (is_blocked) {
            j_print("  ["); j_error("!"); j_print("] %s", title ? title : "—");
            if (due && due[0]) j_dim("  due: %s", due);
            j_print("\n");
        } else {
            j_print("  [%s] %s", icon, title ? title : "—");
            if (due && due[0]) j_dim("  due: %s", due);
            j_print("\n");
        }
    }
    j_print("\n");

    json_free(s);
    return EXIT_OK;
}

/* ── jarvis status ──────────────────────────────────────────── */

int cmd_status_offline(void) {
    JsonNode *s = state_load();
    if (!s) return EXIT_ERR;

    const char *name    = json_str(s, "profile.display_name");
    const char *focus   = json_str(s, "workflow.current_focus");
    const char *wstatus = json_str(s, "workflow.status");
    int total = json_count(s, "workflow.tasks");

    int active = 0, blocked = 0, done = 0;
    for (int i = 0; i < total; i++) {
        JsonNode *t = json_item(s, "workflow.tasks", i);
        const char *st = json_str(t, "status");
        if (!st) continue;
        if (strcmp(st, "todo")  == 0 || strcmp(st, "doing") == 0) active++;
        else if (strcmp(st, "blocked")   == 0) blocked++;
        else if (strcmp(st, "done")      == 0) done++;
    }

    char tasks_str[64];
    snprintf(tasks_str, sizeof(tasks_str), "%d active  %d blocked  %d done",
             active, blocked, done);

    j_box_header("STATUS", jarvis_time_str());
    j_box_empty();
    j_box_row(NULL,     name ? name : g_config.name);
    j_box_empty();
    j_box_row("Focus",  (focus && focus[0]) ? focus : "(none set)");
    j_box_row("State",  wstatus ? wstatus : "ready");
    j_box_row("Tasks",  tasks_str);
    j_box_empty();
    j_box_row("Source", "offline  -  state.json");
    j_box_empty();
    j_box_footer();

    json_free(s);
    return EXIT_OK;
}
