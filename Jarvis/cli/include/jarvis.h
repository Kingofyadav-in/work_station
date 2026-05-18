#ifndef JARVIS_H
#define JARVIS_H

#define JARVIS_VERSION  "0.1.0"
#define JARVIS_NAME     "JARVIS"
#define JARVIS_API_URL  "http://127.0.0.1:5050"
#define JARVIS_CONFIG   ".jarvis/config"

#define EXIT_OK      0
#define EXIT_ERR     1
#define EXIT_UNKNOWN 2

/* ANSI escape codes */
#define C_RESET   "\033[0m"
#define C_BOLD    "\033[1m"
#define C_DIM     "\033[2m"
#define C_RED     "\033[31m"
#define C_GREEN   "\033[32m"
#define C_YELLOW  "\033[33m"
#define C_BLUE    "\033[34m"
#define C_CYAN    "\033[36m"
#define C_WHITE   "\033[37m"

typedef struct {
    char api_url[256];
    char api_key[256];
    char name[64];
    char ai_provider[32];   /* ollama | claude | gpt */
    char state_path[512];   /* path to state.json — absolute or relative to $HOME */
    int  json_output;
    int  no_color;
} JarvisConfig;

/* Global config — defined in jarvis.c, used everywhere */
extern JarvisConfig g_config;

/* Core commands */
int cmd_default(void);
int cmd_help(int argc, char *argv[]);
int cmd_version(void);
int cmd_time(void);
int cmd_hello(void);

/* Offline state commands (state.c) */
int cmd_who(void);
int cmd_focus(void);
int cmd_tasks(void);
int cmd_status_offline(void);

/* API bridge commands (api.c — requires libcurl) */
void api_init(void);
int  api_online(void);
int  cmd_status(void);
int  cmd_health(void);
int  cmd_run(int argc, char *argv[]);

/* Output — box drawing uses BOX_WIDTH=68 visual chars */
void j_print(const char *fmt, ...);
void j_bold(const char *fmt, ...);
void j_error(const char *fmt, ...);
void j_success(const char *fmt, ...);
void j_dim(const char *fmt, ...);
void j_box_header(const char *title, const char *right);
void j_box_footer(void);
void j_box_row(const char *label, const char *value);
void j_box_empty(void);

/* Config */
void config_defaults(JarvisConfig *cfg);
int  config_load(JarvisConfig *cfg);

/* Utils */
const char *jarvis_time_str(void);   /* "Mon 18 May  13:27" — pure ASCII */
const char *jarvis_date_str(void);   /* "Monday, 18 May 2026" */
int         is_tty(void);
int         vis_len(const char *s);  /* visual width: counts UTF-8 codepoints, not bytes */

#endif /* JARVIS_H */
