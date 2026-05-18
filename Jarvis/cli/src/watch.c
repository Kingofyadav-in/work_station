#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include "jarvis.h"

static volatile sig_atomic_t g_watch_stop = 0;
static void watch_stop_handler(int sig) { (void)sig; g_watch_stop = 1; }

int cmd_watch(int argc, char *argv[]) {
    int interval = 10;
    const char *target = "status";

    for (int i = 1; i < argc; i++) {
        if ((strcmp(argv[i], "--interval") == 0 || strcmp(argv[i], "-n") == 0)
                && i + 1 < argc) {
            int v = atoi(argv[++i]);
            if (v >= 1 && v <= 3600) interval = v;
        } else {
            target = argv[i];
        }
    }

    /* Validate target early */
    if (strcmp(target, "status") != 0 && strcmp(target, "tasks")  != 0 &&
        strcmp(target, "focus")  != 0 && strcmp(target, "health") != 0 &&
        strcmp(target, "memory") != 0) {
        j_error("unknown watch target '%s'\n", target);
        j_dim("  valid: status  tasks  focus  health  memory\n\n");
        return EXIT_ERR;
    }

    signal(SIGINT,  watch_stop_handler);
    signal(SIGTERM, watch_stop_handler);

    while (!g_watch_stop) {
        /* Clear screen, move cursor home */
        printf("\033[2J\033[H");
        fflush(stdout);

        j_dim("  watching  ");
        j_bold("%s", target);
        j_dim("  —  every %ds  —  Ctrl+C to exit\n\n", interval);

        if      (strcmp(target, "status") == 0) cmd_status();
        else if (strcmp(target, "tasks")  == 0) cmd_tasks();
        else if (strcmp(target, "focus")  == 0) cmd_focus();
        else if (strcmp(target, "health") == 0) cmd_health();
        else if (strcmp(target, "memory") == 0) cmd_memory();

        /* Sleep in 1s ticks so SIGINT is noticed quickly */
        for (int s = 0; s < interval && !g_watch_stop; s++)
            sleep(1);
    }

    /* Move to a clean line on exit */
    printf("\033[2J\033[H");
    j_dim("  watch exited\n\n");
    return EXIT_OK;
}
