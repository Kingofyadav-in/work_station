#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/wait.h>

static void msleep(long ms) {
    struct timespec ts = { ms / 1000, (ms % 1000) * 1000000L };
    nanosleep(&ts, NULL);
}
#include "jarvis.h"
#include "json.h"

#define POLL_SECS  30

/* ── paths ─────────────────────────────────────────────────────── */

static void pid_path(char *buf, size_t sz) {
    const char *h = getenv("HOME");
    snprintf(buf, sz, "%s/.jarvis/daemon.pid", h ? h : "/tmp");
}

static void log_path(char *buf, size_t sz) {
    const char *h = getenv("HOME");
    snprintf(buf, sz, "%s/.jarvis/daemon.log", h ? h : "/tmp");
}

/* ── PID helpers ────────────────────────────────────────────────── */

static pid_t running_pid(void) {
    char path[512]; pid_path(path, sizeof(path));
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    pid_t pid = 0;
    if (fscanf(f, "%d", &pid) != 1) pid = 0;
    fclose(f);
    if (pid <= 0) return 0;
    if (kill(pid, 0) != 0) { unlink(path); return 0; }
    return pid;
}

static int write_pid(pid_t pid) {
    char path[512]; pid_path(path, sizeof(path));
    FILE *f = fopen(path, "w");
    if (!f) return 0;
    fprintf(f, "%d\n", pid);
    fclose(f);
    return 1;
}

/* ── logging ────────────────────────────────────────────────────── */

static FILE *g_lf = NULL;

static void dlog(const char *fmt, ...) {
    if (!g_lf) return;
    time_t t = time(NULL);
    struct tm *lt = localtime(&t);
    char ts[24];
    strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M:%S", lt);
    fprintf(g_lf, "[%s] ", ts);
    va_list ap;
    va_start(ap, fmt);
    vfprintf(g_lf, fmt, ap);
    va_end(ap);
    fflush(g_lf);
}

/* ── main daemon loop ───────────────────────────────────────────── */

static void daemon_loop(void) {
    char lpath[512]; log_path(lpath, sizeof(lpath));
    g_lf = fopen(lpath, "a");

    dlog("started (PID %d, poll every %ds)\n", getpid(), POLL_SECS);

    char last_focus[256] = {0};
    int  last_done       = -1;
    int  poll_n          = 0;

    while (1) {
        sleep(POLL_SECS);
        poll_n++;

        char *raw = api_get_json("/api/live", 5000L);
        if (!raw) {
            dlog("poll #%d  API unreachable\n", poll_n);
            continue;
        }

        JsonNode *root = json_parse(raw); free(raw);
        if (!root) { dlog("parse error\n"); continue; }

        const char *focus = json_str(root, "status.current_focus");

        /* Count completed tasks */
        int n_tasks = json_count(root, "state.workflow.tasks");
        int n_done  = 0;
        for (int i = 0; i < n_tasks; i++) {
            JsonNode *t  = json_item(root, "state.workflow.tasks", i);
            const char *st = json_str(t, "status");
            if (st && strcmp(st, "done") == 0) n_done++;
        }

        /* Focus change */
        if (focus && focus[0] && last_focus[0] &&
                strcmp(focus, last_focus) != 0) {
            dlog("focus: %s\n", focus);
            char msg[280];
            snprintf(msg, sizeof(msg), "Focus: %.250s", focus);
            api_notify_send(msg);
        }
        if (focus) snprintf(last_focus, sizeof(last_focus), "%.255s", focus);

        /* New completions */
        if (last_done >= 0 && n_done > last_done) {
            int delta = n_done - last_done;
            dlog("%d task(s) completed (total done: %d)\n", delta, n_done);
            char msg[64];
            snprintf(msg, sizeof(msg), "%d task%s completed",
                     delta, delta == 1 ? "" : "s");
            api_notify_send(msg);
        }
        last_done = n_done;

        /* Heartbeat every 10 polls (~5 min) */
        if (poll_n % 10 == 0)
            dlog("heartbeat  poll=%d  focus='%.60s'  done=%d\n",
                 poll_n, last_focus[0] ? last_focus : "?", last_done);

        json_free(root);
    }
}

/* ── start ──────────────────────────────────────────────────────── */

static int cmd_daemon_start(void) {
    if (running_pid() > 0) {
        j_error("daemon already running (PID %d)\n", running_pid());
        return EXIT_ERR;
    }

    pid_t child = fork();
    if (child < 0) { j_error("fork: %s\n", strerror(errno)); return EXIT_ERR; }

    if (child > 0) {
        /* parent: wait briefly to confirm child established */
        msleep(120);
        pid_t pid = running_pid();
        if (pid > 0) j_success("  daemon started  (PID %d)\n\n", pid);
        else         j_success("  daemon started\n\n");
        return EXIT_OK;
    }

    /* child: daemonize via double-fork */
    if (setsid() < 0) _exit(1);
    pid_t gc = fork();
    if (gc < 0) _exit(1);
    if (gc > 0) _exit(0);   /* first child exits, grandchild continues */

    /* grandchild: proper daemon */
    umask(0);
    int null = open("/dev/null", O_RDWR);
    if (null >= 0) {
        dup2(null, STDIN_FILENO);
        dup2(null, STDOUT_FILENO);
        dup2(null, STDERR_FILENO);
        if (null > 2) close(null);
    }

    write_pid(getpid());
    api_init();      /* re-init curl in new process */
    daemon_loop();   /* never returns */
    _exit(0);
}

/* ── stop ───────────────────────────────────────────────────────── */

static int cmd_daemon_stop(void) {
    pid_t pid = running_pid();
    if (pid <= 0) { j_error("daemon not running\n"); return EXIT_ERR; }
    if (kill(pid, SIGTERM) != 0) {
        j_error("stop failed (PID %d): %s\n", pid, strerror(errno));
        return EXIT_ERR;
    }
    char path[512]; pid_path(path, sizeof(path));
    unlink(path);
    j_success("  daemon stopped  (PID %d)\n\n", pid);
    return EXIT_OK;
}

/* ── status ─────────────────────────────────────────────────────── */

static int cmd_daemon_status(void) {
    pid_t pid = running_pid();
    char lpath[512]; log_path(lpath, sizeof(lpath));

    j_print("\n  Daemon  ");
    if (pid > 0) {
        j_success("running");
        j_dim("  (PID %d)\n", pid);
    } else {
        j_dim("not running\n");
        j_dim("  start with: jarvis daemon start\n");
    }
    j_dim("  log: %s\n\n", lpath);
    return EXIT_OK;
}

/* ── entry point ────────────────────────────────────────────────── */

int cmd_daemon(int argc, char *argv[]) {
    const char *sub = (argc >= 2) ? argv[1] : "status";
    if (strcmp(sub, "start")  == 0) return cmd_daemon_start();
    if (strcmp(sub, "stop")   == 0) return cmd_daemon_stop();
    if (strcmp(sub, "status") == 0) return cmd_daemon_status();
    j_error("usage: jarvis daemon [start|stop|status]\n");
    return EXIT_ERR;
}
