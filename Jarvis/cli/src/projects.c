#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include "jarvis.h"

#define PROJECTS_ROOT_REL  "dev/projects"
#define MAX_PROJECTS        64
#define NAME_W              20   /* column width for project name */
#define BRANCH_W            14   /* column width for branch */

/* Run git -C <path> <args>, return first line (malloc'd) or NULL */
static char *git_run(const char *path, const char *args) {
    char cmd[1024];
    snprintf(cmd, sizeof(cmd), "git -C '%s' %s 2>/dev/null", path, args);
    FILE *f = popen(cmd, "r");
    if (!f) return NULL;
    char buf[512] = {0};
    if (!fgets(buf, sizeof(buf), f)) { pclose(f); return NULL; }
    pclose(f);
    size_t len = strlen(buf);
    if (len > 0 && buf[len-1] == '\n') buf[len-1] = '\0';
    return strdup(buf);
}

static int is_git_repo(const char *path) {
    char check[768];
    snprintf(check, sizeof(check), "%.756s/.git", path);
    struct stat st;
    return stat(check, &st) == 0;
}

typedef struct {
    char name[128];
    char branch[64];
    char commit[128];   /* short hash + subject */
    int  dirty;
} Repo;

static int cmp_repo(const void *a, const void *b) {
    return strcmp(((const Repo *)a)->name, ((const Repo *)b)->name);
}

int cmd_projects(void) {
    const char *home = getenv("HOME");
    if (!home) { j_error("HOME not set\n"); return EXIT_ERR; }

    char root[1024];
    if (g_config.projects_root[0] == '/')
        snprintf(root, sizeof(root), "%s", g_config.projects_root);
    else if (g_config.projects_root[0])
        snprintf(root, sizeof(root), "%s/%s", home, g_config.projects_root);
    else
        snprintf(root, sizeof(root), "%s/%s", home, PROJECTS_ROOT_REL);

    DIR *d = opendir(root);
    if (!d) { j_error("cannot open projects root: %s\n", root); return EXIT_ERR; }

    Repo repos[MAX_PROJECTS];
    int count = 0;

    struct dirent *ent;
    while ((ent = readdir(d)) != NULL && count < MAX_PROJECTS) {
        if (ent->d_name[0] == '.') continue;

        char full[768];
        snprintf(full, sizeof(full), "%.500s/%.250s", root, ent->d_name);

        struct stat st;
        if (stat(full, &st) != 0 || !S_ISDIR(st.st_mode)) continue;
        if (!is_git_repo(full)) continue;

        Repo *r = &repos[count++];
        snprintf(r->name, sizeof(r->name), "%.127s", ent->d_name);

        char *branch = git_run(full, "rev-parse --abbrev-ref HEAD");
        snprintf(r->branch, sizeof(r->branch), "%s", branch ? branch : "?");
        free(branch);

        /* short hash + subject, truncated */
        char *log = git_run(full, "log -1 --format='%h  %s'");
        snprintf(r->commit, sizeof(r->commit), "%s", log ? log : "—");
        free(log);

        char *dirty = git_run(full, "status --porcelain");
        r->dirty = (dirty && dirty[0] != '\0');
        free(dirty);
    }
    closedir(d);

    if (count == 0) {
        j_dim("\n  No git repos found in %s\n\n", root);
        return EXIT_OK;
    }

    qsort(repos, count, sizeof(Repo), cmp_repo);

    j_bold("\n  Projects  ");
    j_dim("(%d)\n\n", count);

    for (int i = 0; i < count; i++) {
        Repo *r = &repos[i];

        /* name column */
        int npad = NAME_W - (int)strlen(r->name);
        if (npad < 1) npad = 1;

        /* branch column */
        int blen = (int)strlen(r->branch);
        int bpad = BRANCH_W - blen;
        if (bpad < 1) bpad = 1;

        /* truncate commit message to 45 chars */
        char commit_trunc[50];
        snprintf(commit_trunc, sizeof(commit_trunc), "%.46s", r->commit);

        j_print("  %s", r->name);
        j_dim("%*s", npad, "");
        if (r->dirty) j_print("%-*s", BRANCH_W, r->branch);
        else          j_dim("%-*s", BRANCH_W, r->branch);
        if (r->dirty) j_print("*  ");
        else          j_print("   ");
        j_dim("%s\n", commit_trunc);
    }
    j_print("\n");
    return EXIT_OK;
}
