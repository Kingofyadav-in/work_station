#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include "jarvis.h"
#include "json.h"

#define STATE_PATH_REL "dev/projects/work_station/Kingofyadav/state.json"

/* Resolve the state.json path into buf */
static void state_get_path(char *buf, size_t sz) {
    const char *home = getenv("HOME");
    if (!home) home = "/home/user";
    if (g_config.state_path[0] == '/')
        snprintf(buf, sz, "%s", g_config.state_path);
    else if (g_config.state_path[0])
        snprintf(buf, sz, "%s/%s", home, g_config.state_path);
    else
        snprintf(buf, sz, "%s/%s", home, STATE_PATH_REL);
}

/* Run: python3 -c <script> <path> <arg>
 * Returns malloc'd stdout line (caller frees), or NULL on failure. */
static char *run_py(const char *script, const char *path, const char *arg) {
    int pfd[2];
    if (pipe(pfd) != 0) return NULL;

    pid_t pid = fork();
    if (pid < 0) { close(pfd[0]); close(pfd[1]); return NULL; }

    if (pid == 0) {
        close(pfd[0]);
        dup2(pfd[1], STDOUT_FILENO);
        close(pfd[1]);
        execlp("python3", "python3", "-c", script, path, arg, (char *)NULL);
        _exit(1);
    }

    close(pfd[1]);
    char buf[256] = {0};
    ssize_t n = read(pfd[0], buf, sizeof(buf) - 1);
    if (n > 0) { buf[n] = '\0'; if (buf[n-1] == '\n') buf[n-1] = '\0'; }
    close(pfd[0]);

    int st;
    waitpid(pid, &st, 0);
    if (!WIFEXITED(st) || WEXITSTATUS(st) != 0) return NULL;
    return strdup(buf);
}

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

/* ── jarvis memory ──────────────────────────────────────────── */

int cmd_memory(void) {
    JsonNode *s = state_load();
    if (!s) return EXIT_ERR;

    int total = json_count(s, "memory");

    if (total == 0) {
        j_dim("\n  No memories stored.\n\n");
        json_free(s);
        return EXIT_OK;
    }

    j_bold("\n  Memory  ");
    j_dim("(%d)\n\n", total);

    /* show last 10, most recent first */
    int start = total > 10 ? total - 10 : 0;
    for (int i = total - 1; i >= start; i--) {
        JsonNode *m = json_item(s, "memory", i);
        if (!m) continue;
        const char *text = json_str(m, "text");
        const char *when = json_str(m, "created_at");
        const char *type = json_str(m, "type");

        char date[12] = {0};
        if (when && strlen(when) >= 10)
            snprintf(date, sizeof(date), "%.10s", when);

        j_dim("  %s", date[0] ? date : "----------");
        if (type && type[0]) j_dim("  [%s]", type);
        j_print("  %s\n", text ? text : "\xe2\x80\x94");
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

/* ── jarvis add-task / done ─────────────────────────────────── */

static const char *PY_ADD_TASK =
    "import json,sys,datetime as dt\n"
    "path,title=sys.argv[1],sys.argv[2]\n"
    "s=json.load(open(path))\n"
    "tasks=s.setdefault('workflow',{}).setdefault('tasks',[])\n"
    "nums=[int(t['id'].split('-')[-1]) for t in tasks if 'id' in t and t['id'].startswith('task-')]\n"
    "idx=max(nums,default=0)+1\n"
    "tid='task-{:03d}'.format(idx)\n"
    "now=dt.datetime.now(dt.timezone.utc).isoformat()\n"
    "tasks.append({'id':tid,'title':title,'status':'todo','created_at':now,'due':None,'estimate':None,'blockers':[]})\n"
    "json.dump(s,open(path,'w'),indent=2,ensure_ascii=False)\n"
    "print(tid)\n";

static const char *PY_DONE =
    "import json,sys\n"
    "path,tid=sys.argv[1],sys.argv[2]\n"
    "s=json.load(open(path))\n"
    "found=False\n"
    "for t in s.get('workflow',{}).get('tasks',[]):\n"
    "    if t.get('id')==tid: t['status']='done'; found=True; break\n"
    "if not found: print('error: task not found'); sys.exit(1)\n"
    "json.dump(s,open(path,'w'),indent=2,ensure_ascii=False)\n"
    "print('ok')\n";

int cmd_add_task(int argc, char *argv[]) {
    if (argc < 2) { j_error("usage: jarvis add-task <title>\n"); return EXIT_ERR; }

    char title[512] = {0};
    for (int i = 1; i < argc; i++) {
        if (i > 1) strncat(title, " ", sizeof(title) - strlen(title) - 1);
        strncat(title, argv[i], sizeof(title) - strlen(title) - 1);
    }

    char path[1024]; state_get_path(path, sizeof(path));
    j_print("\n"); j_dim("  adding: %s\n\n", title);

    char *out = run_py(PY_ADD_TASK, path, title);
    if (!out) { j_error("failed to write state.json\n"); return EXIT_ERR; }

    j_success("  Task added: %s\n\n", out);
    free(out);
    return EXIT_OK;
}

int cmd_done(int argc, char *argv[]) {
    if (argc < 2) { j_error("usage: jarvis done <task_id>\n"); return EXIT_ERR; }

    char path[1024]; state_get_path(path, sizeof(path));
    j_print("\n"); j_dim("  marking %s done...\n\n", argv[1]);

    char *out = run_py(PY_DONE, path, argv[1]);
    if (!out) { j_error("task not found: %s\n", argv[1]); return EXIT_ERR; }

    j_success("  Done: %s\n\n", argv[1]);
    free(out);
    return EXIT_OK;
}
