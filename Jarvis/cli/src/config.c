#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "jarvis.h"

void config_defaults(JarvisConfig *cfg) {
    snprintf(cfg->api_url,     sizeof(cfg->api_url),     "%s", JARVIS_API_URL);
    snprintf(cfg->api_key,     sizeof(cfg->api_key),     "%s", "");
    snprintf(cfg->name,        sizeof(cfg->name),        "%s", "Amit");
    snprintf(cfg->ai_provider, sizeof(cfg->ai_provider), "%s", "ollama");
    cfg->json_output = 0;
    cfg->no_color    = 0;
}

/*
 * Load ~/.jarvis/config — simple KEY=VALUE format, one per line.
 * Lines starting with # are comments. Missing file is not an error.
 *
 * Example ~/.jarvis/config:
 *   name=Amit
 *   api_url=http://127.0.0.1:5050
 *   api_key=
 *   ai_provider=ollama
 */
int config_load(JarvisConfig *cfg) {
    const char *home = getenv("HOME");
    if (!home) return 0;

    char path[512];
    snprintf(path, sizeof(path), "%s/%s", home, JARVIS_CONFIG);

    FILE *f = fopen(path, "r");
    if (!f) return 0;

    char line[512];
    while (fgets(line, sizeof(line), f)) {
        char *nl = strchr(line, '\n');
        if (nl) *nl = '\0';

        if (line[0] == '#' || line[0] == '\0') continue;

        char *eq = strchr(line, '=');
        if (!eq) continue;
        *eq = '\0';
        const char *key = line;
        const char *val = eq + 1;

        if      (strcmp(key, "name")        == 0) snprintf(cfg->name,        sizeof(cfg->name),        "%s", val);
        else if (strcmp(key, "api_url")     == 0) snprintf(cfg->api_url,     sizeof(cfg->api_url),     "%s", val);
        else if (strcmp(key, "api_key")     == 0) snprintf(cfg->api_key,     sizeof(cfg->api_key),     "%s", val);
        else if (strcmp(key, "ai_provider") == 0) snprintf(cfg->ai_provider, sizeof(cfg->ai_provider), "%s", val);
        else if (strcmp(key, "no_color")    == 0) cfg->no_color = (strcmp(val, "1") == 0 || strcmp(val, "true") == 0);
        else if (strcmp(key, "state_path")  == 0) snprintf(cfg->state_path, sizeof(cfg->state_path), "%s", val);
    }

    fclose(f);
    return 1;
}
