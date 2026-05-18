#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "jarvis.h"

/* Global config — loaded once in main, read-only everywhere else */
JarvisConfig g_config;

int main(int argc, char *argv[]) {
    config_defaults(&g_config);
    config_load(&g_config);
    api_init();

    /* Strip global flags from argv before routing.
     * We modify argc/argv in place so subcommand handlers
     * receive a clean argument list. */
    for (int i = 1; i < argc; ) {
        if (strcmp(argv[i], "--json") == 0) {
            g_config.json_output = 1;
            for (int j = i; j < argc - 1; j++) argv[j] = argv[j + 1];
            argc--;
        } else if (strcmp(argv[i], "--no-color") == 0) {
            g_config.no_color = 1;
            for (int j = i; j < argc - 1; j++) argv[j] = argv[j + 1];
            argc--;
        } else {
            i++;
        }
    }

    if (argc == 1) return cmd_default();

    const char *cmd = argv[1];

    if (strcmp(cmd, "help")      == 0 ||
        strcmp(cmd, "--help")    == 0 ||
        strcmp(cmd, "-h")        == 0) return cmd_help(argc - 1, argv + 1);

    if (strcmp(cmd, "version")   == 0 ||
        strcmp(cmd, "--version") == 0 ||
        strcmp(cmd, "-V")        == 0) return cmd_version();

    if (strcmp(cmd, "time")   == 0) return cmd_time();
    if (strcmp(cmd, "hello")  == 0) return cmd_hello();

    /* Offline state — reads state.json directly */
    if (strcmp(cmd, "who")    == 0) return cmd_who();
    if (strcmp(cmd, "focus")  == 0) return cmd_focus();
    if (strcmp(cmd, "tasks")  == 0) return cmd_tasks();
    if (strcmp(cmd, "memory") == 0) return cmd_memory();

    /* Online/offline auto commands */
    if (strcmp(cmd, "status")    == 0) return cmd_status();
    if (strcmp(cmd, "health")    == 0) return cmd_health();
    if (strcmp(cmd, "run")       == 0) return cmd_run(argc - 1, argv + 1);
    if (strcmp(cmd, "ask")       == 0) return cmd_ask(argc - 1, argv + 1);

    /* Write commands — require API */
    if (strcmp(cmd, "remember")  == 0) return cmd_remember(argc - 1, argv + 1);
    if (strcmp(cmd, "set-focus") == 0) return cmd_set_focus(argc - 1, argv + 1);
    if (strcmp(cmd, "add-task")  == 0) return cmd_add_task(argc - 1, argv + 1);
    if (strcmp(cmd, "done")      == 0) return cmd_done(argc - 1, argv + 1);

    /* C-5: workspace */
    if (strcmp(cmd, "projects")  == 0) return cmd_projects();
    if (strcmp(cmd, "sync")      == 0) return cmd_sync();
    if (strcmp(cmd, "journal")   == 0) return cmd_journal(argc - 1, argv + 1);

    /* C-6: live + background */
    if (strcmp(cmd, "watch")     == 0) return cmd_watch(argc - 1, argv + 1);
    if (strcmp(cmd, "daemon")    == 0) return cmd_daemon(argc - 1, argv + 1);
    if (strcmp(cmd, "notify")    == 0) return cmd_notify(argc - 1, argv + 1);

    j_error("unknown command '%s'  --  try: jarvis help\n", cmd);
    return EXIT_UNKNOWN;
}
