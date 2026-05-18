#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include "jarvis.h"

/*
 * BOX_WIDTH: total visual width of a box line including the two border chars.
 * All strings passed into box functions must be pure ASCII so that strlen()
 * returns the correct visual width. Box-drawing chars (─ ┌ etc.) are handled
 * by loop counters, never by strlen.
 */
#define BOX_WIDTH 68

static int use_color(void) {
    return !g_config.no_color && is_tty();
}

/* Conditional colour emit to stdout */
static void co(const char *code) {
    if (use_color()) fputs(code, stdout);
}

/* Conditional colour emit to stderr */
static void ce(const char *code) {
    if (!g_config.no_color && isatty(STDERR_FILENO)) fputs(code, stderr);
}

int is_tty(void) {
    return isatty(STDOUT_FILENO);
}

/*
 * Visual width of a UTF-8 string: count leading bytes only.
 * Each leading byte (not 10xxxxxx) represents one codepoint = 1 visual cell
 * for all non-East-Asian scripts. Use this instead of strlen() in box math.
 */
int vis_len(const char *s) {
    if (!s) return 0;
    int n = 0;
    const unsigned char *p = (const unsigned char *)s;
    while (*p) {
        if ((*p & 0xC0) != 0x80) n++; /* leading byte = one codepoint */
        p++;
    }
    return n;
}

/* Print the UTF-8 horizontal box char n times */
static void hrep(int n) {
    for (int i = 0; i < n; i++) fputs("\xe2\x94\x80", stdout); /* U+2500 ─ */
}

void j_print(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
}

void j_bold(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    co(C_BOLD);
    vprintf(fmt, ap);
    co(C_RESET);
    va_end(ap);
}

void j_error(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    ce(C_RED C_BOLD);
    fputs("  error  ", stderr);
    ce(C_RESET);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
}

void j_success(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    co(C_GREEN);
    vprintf(fmt, ap);
    co(C_RESET);
    va_end(ap);
}

void j_dim(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    co(C_DIM);
    vprintf(fmt, ap);
    co(C_RESET);
    va_end(ap);
}

/*
 * Box header:  ┌─ TITLE ──────────────────────── right ─┐
 *
 * Visual layout (all positions are visual chars, not bytes):
 *   ┌(1) ─(1) [sp(1) title(tlen) sp(1)] [fill x─] [sp(1) right(rlen) sp(1) ─(1)] ┐(1)
 *   fixed = 2 + (tlen>0 ? tlen+2 : 0) + (rlen>0 ? rlen+3 : 0) + 1
 *   fill  = BOX_WIDTH - fixed
 *
 * Strings must be pure ASCII — strlen() is used for visual width.
 */
void j_box_header(const char *title, const char *right) {
    int tlen = vis_len(title);
    int rlen = vis_len(right);

    int fixed = 2
              + (tlen > 0 ? tlen + 2 : 0)
              + (rlen > 0 ? rlen + 3 : 0)
              + 1;
    int fill = BOX_WIDTH - fixed;
    if (fill < 2) fill = 2;

    co(C_CYAN);
    fputs("\xe2\x94\x8c", stdout); /* ┌ */
    fputs("\xe2\x94\x80", stdout); /* ─ */
    if (tlen > 0) {
        co(C_RESET); co(C_BOLD);
        printf(" %s ", title);
        co(C_RESET); co(C_CYAN);
    }
    hrep(fill);
    if (rlen > 0) {
        co(C_RESET); co(C_DIM);
        printf(" %s ", right);
        co(C_RESET); co(C_CYAN);
        fputs("\xe2\x94\x80", stdout); /* ─ */
    }
    fputs("\xe2\x94\x90\n", stdout); /* ┐ */
    co(C_RESET);
}

/*
 * Box footer:  └──────────────────────────────────────────────────┘
 */
void j_box_footer(void) {
    co(C_CYAN);
    fputs("\xe2\x94\x94", stdout); /* └ */
    hrep(BOX_WIDTH - 2);
    fputs("\xe2\x94\x98\n", stdout); /* ┘ */
    co(C_RESET);
}

/*
 * Box row:
 *   label non-NULL:  │  label  ->  value             │
 *   label NULL:      │  value (bold)                  │
 *
 * Inner visual width = BOX_WIDTH - 2 = 66.
 * Strings must be pure ASCII.
 */
void j_box_row(const char *label, const char *value) {
    int llen = (label && label[0]) ? vis_len(label) : 0;
    int vlen = vis_len(value);
    int spaces;

    co(C_CYAN);
    fputs("\xe2\x94\x82", stdout); /* │ */
    co(C_RESET);

    if (llen == 0) {
        /* Full-width bold value — greeting style */
        spaces = 62 - vlen;  /* inner(66) - leading(2) - trailing(2) - vlen */
        fputs("  ", stdout);
        co(C_BOLD);
        fputs(value ? value : "", stdout);
        co(C_RESET);
    } else {
        /* label  ->  value */
        spaces = 56 - llen - vlen; /* inner(66) - lead(2) - arrow(6) - trail(2) */
        fputs("  ", stdout);
        co(C_YELLOW);
        fputs(label, stdout);
        co(C_RESET);
        co(C_DIM); fputs("  ->  ", stdout); co(C_RESET);
        fputs(value ? value : "", stdout);
    }

    printf("%*s", (spaces > 0 ? spaces : 0), "");
    fputs("  ", stdout);
    co(C_CYAN);
    fputs("\xe2\x94\x82\n", stdout); /* │ */
    co(C_RESET);
}

/*
 * Empty box row:  │                                                              │
 */
void j_box_empty(void) {
    co(C_CYAN);
    fputs("\xe2\x94\x82", stdout); /* │ */
    co(C_RESET);
    printf("%*s", BOX_WIDTH - 2, "");
    co(C_CYAN);
    fputs("\xe2\x94\x82\n", stdout); /* │ */
    co(C_RESET);
}

/* ASCII-only time string safe for strlen-based box width math */
const char *jarvis_time_str(void) {
    static char buf[32];
    time_t t = time(NULL);
    struct tm *lt = localtime(&t);
    strftime(buf, sizeof(buf), "%a %d %b  %H:%M", lt);
    return buf;
}

const char *jarvis_date_str(void) {
    static char buf[48];
    time_t t = time(NULL);
    struct tm *lt = localtime(&t);
    strftime(buf, sizeof(buf), "%A, %d %B %Y", lt);
    return buf;
}
