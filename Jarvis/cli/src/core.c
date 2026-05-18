#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "jarvis.h"

/* Read PRETTY_NAME from /etc/os-release */
static void get_os_name(char *buf, int len) {
    snprintf(buf, len, "Linux");
    FILE *f = fopen("/etc/os-release", "r");
    if (!f) return;
    char line[256];
    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "PRETTY_NAME=", 12) != 0) continue;
        char *val = line + 12;
        if (*val == '"') val++;
        char *end = strchr(val, '"');
        if (!end) end = strchr(val, '\n');
        if (end) *end = '\0';
        snprintf(buf, (size_t)len, "%.*s", len - 1, val);
        break;
    }
    fclose(f);
}

/*
 * Default view — shown when `jarvis` is run with no arguments.
 *
 * ┌─ JARVIS ──────────────────────────────── Mon 18 May  13:27 ─┐
 * │                                                              │
 * │  Hello, Amit  -  Jarvis CLI v0.1.0                          │
 * │                                                              │
 * │  System  ->  Ubuntu 24.04.4 LTS                             │
 * │  Mode    ->  CLI  -  Local                                   │
 * │                                                              │
 * │  Tip     ->  jarvis help  to see all commands                │
 * │                                                              │
 * └──────────────────────────────────────────────────────────────┘
 */
int cmd_default(void) {
    char os[128];
    get_os_name(os, sizeof(os));

    char greeting[96];
    snprintf(greeting, sizeof(greeting), "Hello, %s  -  Jarvis CLI v%s",
             g_config.name, JARVIS_VERSION);

    j_box_header(JARVIS_NAME, jarvis_time_str());
    j_box_empty();
    j_box_row(NULL, greeting);
    j_box_empty();
    j_box_row("System", os);
    j_box_row("Mode",   "CLI  -  Local");
    j_box_empty();
    j_box_row("Tip",    "jarvis help  to see all commands");
    j_box_empty();
    j_box_footer();
    return EXIT_OK;
}

int cmd_help(int argc, char *argv[]) {
    (void)argc; (void)argv;

    j_bold("\n  JARVIS CLI  ");
    j_dim("v%s\n\n", JARVIS_VERSION);

    j_bold("  Usage\n");
    j_dim("    jarvis [command] [args] [--flags]\n\n");

    j_bold("  Core\n");
    j_print("    %-20s  %s\n", "help",    "Show this help");
    j_print("    %-20s  %s\n", "version", "Version and build info");
    j_print("    %-20s  %s\n", "config",  "Show current config");
    j_print("    %-20s  %s\n", "time",    "Current date and time");
    j_print("    %-20s  %s\n", "hello",   "Greeting");

    j_bold("\n  Online  ");
    j_dim("(auto: API first, fallback offline)\n");
    j_print("    %-20s  %s\n", "status",         "Overview — live platform + tasks");
    j_print("    %-20s  %s\n", "health",         "Platform health — API, network, device");
    j_print("    %-20s  %s\n", "run",            "Run a Jarvis command via API");
    j_print("    %-20s  %s\n", "ask",            "Ask AI — [--stream] [--model <m>]");

    j_bold("\n  Offline  ");
    j_dim("(reads state.json directly)\n");
    j_print("    %-20s  %s\n", "who",              "Identity profile");
    j_print("    %-20s  %s\n", "focus",            "Current focus and next actions");
    j_print("    %-20s  %s\n", "tasks [--blocked]","Task list; --blocked shows blockers");
    j_print("    %-20s  %s\n", "memory [search]",  "Recent memories; search <query> filters");

    j_print("    %-20s  %s\n", "add-task",  "Add a task to workflow");
    j_print("    %-20s  %s\n", "done",      "Mark a task done");
    j_print("    %-20s  %s\n", "estimate",  "Set time estimate  <id> <minutes>");

    j_bold("\n  Write  ");
    j_dim("(API required)\n");
    j_print("    %-20s  %s\n", "remember",  "Save a memory note");
    j_print("    %-20s  %s\n", "set-focus", "Set current focus");
    j_print("    %-20s  %s\n", "sync",      "Sync device status and peers");
    j_print("    %-20s  %s\n", "journal",   "Recent activity feed  [hours]");

    j_bold("\n  Workspace\n");
    j_print("    %-20s  %s\n", "projects",  "List git repos with branch + status");

    j_bold("\n  Live\n");
    j_print("    %-20s  %s\n", "watch",     "Live-refresh a view  [target] [-n secs]");
    j_print("    %-20s  %s\n", "daemon",    "Background poller   [start|stop|status]");
    j_print("    %-20s  %s\n", "notify",    "Desktop notification <message>");

    j_bold("\n  Flags\n");
    j_print("    %-20s  %s\n", "--json",     "Output raw JSON (future phases)");
    j_print("    %-20s  %s\n", "--no-color", "Disable ANSI colors");

    j_bold("\n  Coming in C-9+\n");
    j_dim("    task blockers  ask --context  memory export  shell completions\n\n");

    return EXIT_OK;
}

int cmd_version(void) {
    char os[128];
    get_os_name(os, sizeof(os));

#ifdef __GNUC__
    char cc[48];
    snprintf(cc, sizeof(cc), "gcc %d.%d.%d", __GNUC__, __GNUC_MINOR__, __GNUC_PATCHLEVEL__);
#else
    const char *cc = "cc";
#endif

    j_bold("\n  Jarvis CLI  ");
    j_print("%s\n", JARVIS_VERSION);
    j_dim("  %s\n", cc);
    j_dim("  %s\n", os);
    j_dim("  Built: %s\n\n", __DATE__);

    return EXIT_OK;
}

int cmd_time(void) {
    time_t t = time(NULL);
    struct tm *lt = localtime(&t);

    char weekday[32], day_mon_year[32], clock_str[16], tz[32];
    strftime(weekday,      sizeof(weekday),      "%A",             lt);
    strftime(day_mon_year, sizeof(day_mon_year), "%d %B %Y",       lt);
    strftime(clock_str,    sizeof(clock_str),    "%H:%M:%S",       lt);
    strftime(tz,           sizeof(tz),           "%Z (UTC%z)",     lt);

    j_bold("\n  %s, %s\n", weekday, day_mon_year);
    j_print("  %s  ", clock_str);
    j_dim("%s\n\n", tz);

    return EXIT_OK;
}

int cmd_hello(void) {
    j_bold("\n  Hello, %s.\n", g_config.name);
    j_dim("  Jarvis CLI v%s  -  %s\n\n", JARVIS_VERSION, jarvis_time_str());
    return EXIT_OK;
}

int cmd_config(void) {
    const char *home = getenv("HOME");
    char cpath[512];
    snprintf(cpath, sizeof(cpath), "%s/.jarvis/config", home ? home : "~");

    j_bold("\n  Config  ");
    j_dim("%s\n\n", cpath);

    j_print("    %-16s  %s\n", "name",         g_config.name);
    j_print("    %-16s  %s\n", "api_url",       g_config.api_url);

    if (g_config.api_key[0]) {
        char masked[16];
        snprintf(masked, sizeof(masked), "%.8s...", g_config.api_key);
        j_dim("    %-16s  %s\n", "api_key", masked);
    } else {
        j_dim("    %-16s  %s\n", "api_key", "(not set)");
    }

    j_print("    %-16s  %s\n", "ai_provider",   g_config.ai_provider);
    j_print("    %-16s  %s\n", "ai_model",       g_config.ai_model);
    j_print("    %-16s  %s\n", "ai_url",         g_config.ai_url);

    if (g_config.state_path[0])
        j_print("    %-16s  %s\n", "state_path",    g_config.state_path);
    else
        j_dim("    %-16s  %s\n", "state_path",    "(default)");

    if (g_config.projects_root[0])
        j_print("    %-16s  %s\n", "projects_root", g_config.projects_root);
    else
        j_dim("    %-16s  %s\n", "projects_root", "(not set)");

    j_dim("    %-16s  %s\n", "no_color",       g_config.no_color ? "1" : "0");
    j_print("\n");
    return EXIT_OK;
}
