#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "json.h"

/* Encode a Unicode codepoint to UTF-8, returns byte count written to out[] */
static int utf8_enc(unsigned int cp, char *out) {
    if (cp < 0x80) {
        out[0] = (char)cp; return 1;
    } else if (cp < 0x800) {
        out[0] = (char)(0xC0 | (cp >> 6));
        out[1] = (char)(0x80 | (cp & 0x3F)); return 2;
    } else if (cp < 0x10000) {
        out[0] = (char)(0xE0 | (cp >> 12));
        out[1] = (char)(0x80 | ((cp >> 6) & 0x3F));
        out[2] = (char)(0x80 | (cp & 0x3F)); return 3;
    } else {
        out[0] = (char)(0xF0 | (cp >> 18));
        out[1] = (char)(0x80 | ((cp >> 12) & 0x3F));
        out[2] = (char)(0x80 | ((cp >> 6) & 0x3F));
        out[3] = (char)(0x80 | (cp & 0x3F)); return 4;
    }
}

/* ── parser cursor ─────────────────────────────────────────── */

typedef struct { const char *p; const char *end; } Cur;

static void skip_ws(Cur *c) {
    while (c->p < c->end && isspace((unsigned char)*c->p)) c->p++;
}

/* ── node allocation ───────────────────────────────────────── */

static JsonNode *node_new(int type) {
    JsonNode *n = calloc(1, sizeof(JsonNode));
    if (n) n->type = type;
    return n;
}

/* ── forward declaration ───────────────────────────────────── */
static JsonNode *parse_value(Cur *c);

/* ── string parser ─────────────────────────────────────────── */

static char *parse_str(Cur *c) {
    if (c->p >= c->end || *c->p != '"') return NULL;
    c->p++;

    /* worst-case output length = remaining bytes (handles multi-byte passthrough) */
    size_t maxlen = (size_t)(c->end - c->p) + 1;
    char *out = malloc(maxlen);
    if (!out) return NULL;
    char *w = out;

    while (c->p < c->end && *c->p != '"') {
        if (*c->p == '\\') {
            c->p++;
            if (c->p >= c->end) break;
            switch (*c->p) {
                case '"':  *w++ = '"';  break;
                case '\\': *w++ = '\\'; break;
                case '/':  *w++ = '/';  break;
                case 'n':  *w++ = '\n'; break;
                case 't':  *w++ = '\t'; break;
                case 'r':  *w++ = '\r'; break;
                case 'u': {
                    /* \uXXXX — parse 4 hex digits, encode as UTF-8 */
                    if (c->p + 4 < c->end) {
                        char hex[5] = {c->p[1], c->p[2], c->p[3], c->p[4], '\0'};
                        unsigned int cp = (unsigned int)strtoul(hex, NULL, 16);
                        char tmp[4];
                        int nb = utf8_enc(cp, tmp);
                        for (int i = 0; i < nb; i++) *w++ = tmp[i];
                        c->p += 4; /* skip 2014; outer c->p++ skips 'u' */
                    }
                    break;
                }
                default:   *w++ = *c->p; break;
            }
        } else {
            *w++ = *c->p;
        }
        c->p++;
    }
    *w = '\0';
    if (c->p < c->end && *c->p == '"') c->p++; /* consume closing " */
    return out;
}

/* ── object / array parsers ────────────────────────────────── */

static JsonNode *parse_object(Cur *c) {
    if (c->p >= c->end || *c->p != '{') return NULL;
    c->p++;

    JsonNode *obj  = node_new(JSON_OBJECT);
    JsonNode *tail = NULL;

    skip_ws(c);
    while (c->p < c->end && *c->p != '}') {
        skip_ws(c);
        if (*c->p != '"') break;               /* malformed */

        char *key = parse_str(c);
        if (!key) break;

        skip_ws(c);
        if (c->p >= c->end || *c->p != ':') { free(key); break; }
        c->p++;                                /* consume : */
        skip_ws(c);

        JsonNode *val = parse_value(c);
        if (!val) { free(key); break; }
        val->key = key;

        if (!obj->child) obj->child = val;
        else             tail->next = val;
        tail = val;

        skip_ws(c);
        if (c->p < c->end && *c->p == ',') c->p++;
        skip_ws(c);
    }
    if (c->p < c->end && *c->p == '}') c->p++;
    return obj;
}

static JsonNode *parse_array(Cur *c) {
    if (c->p >= c->end || *c->p != '[') return NULL;
    c->p++;

    JsonNode *arr  = node_new(JSON_ARRAY);
    JsonNode *tail = NULL;

    skip_ws(c);
    while (c->p < c->end && *c->p != ']') {
        skip_ws(c);
        JsonNode *val = parse_value(c);
        if (!val) break;

        if (!arr->child) arr->child = val;
        else             tail->next = val;
        tail = val;

        skip_ws(c);
        if (c->p < c->end && *c->p == ',') c->p++;
        skip_ws(c);
    }
    if (c->p < c->end && *c->p == ']') c->p++;
    return arr;
}

/* ── value dispatcher ──────────────────────────────────────── */

static JsonNode *parse_value(Cur *c) {
    skip_ws(c);
    if (c->p >= c->end) return NULL;

    char ch = *c->p;

    if (ch == '"') {
        JsonNode *n = node_new(JSON_STRING);
        n->sv = parse_str(c);
        return n;
    }
    if (ch == '{') return parse_object(c);
    if (ch == '[') return parse_array(c);

    if (ch == 't' && c->end - c->p >= 4 && strncmp(c->p, "true", 4) == 0) {
        JsonNode *n = node_new(JSON_BOOL); n->bv = 1; c->p += 4; return n;
    }
    if (ch == 'f' && c->end - c->p >= 5 && strncmp(c->p, "false", 5) == 0) {
        JsonNode *n = node_new(JSON_BOOL); n->bv = 0; c->p += 5; return n;
    }
    if (ch == 'n' && c->end - c->p >= 4 && strncmp(c->p, "null", 4) == 0) {
        c->p += 4; return node_new(JSON_NULL);
    }
    if (ch == '-' || isdigit((unsigned char)ch)) {
        JsonNode *n = node_new(JSON_NUMBER);
        char *end;
        n->nv = strtod(c->p, &end);
        c->p = end;
        return n;
    }
    return NULL; /* unparseable */
}

/* ── public API ────────────────────────────────────────────── */

JsonNode *json_parse(const char *src) {
    if (!src) return NULL;
    Cur c = { src, src + strlen(src) };
    return parse_value(&c);
}

void json_free(JsonNode *n) {
    if (!n) return;
    json_free(n->child);
    json_free(n->next);
    free(n->key);
    free(n->sv);
    free(n);
}

/* Get a direct child of an object by key name */
static JsonNode *obj_get_key(JsonNode *obj, const char *key) {
    if (!obj || obj->type != JSON_OBJECT) return NULL;
    for (JsonNode *c = obj->child; c; c = c->next) {
        if (c->key && strcmp(c->key, key) == 0) return c;
    }
    return NULL;
}

JsonNode *json_get(JsonNode *root, const char *path) {
    if (!root || !path) return NULL;

    char buf[256];
    snprintf(buf, sizeof(buf), "%s", path);

    JsonNode *cur = root;
    char *tok = strtok(buf, ".");
    while (tok && cur) {
        cur = obj_get_key(cur, tok);
        tok = strtok(NULL, ".");
    }
    return cur;
}

const char *json_str(JsonNode *root, const char *path) {
    JsonNode *n = json_get(root, path);
    if (!n || n->type != JSON_STRING) return NULL;
    return n->sv;
}

int json_int(JsonNode *root, const char *path, int def) {
    JsonNode *n = json_get(root, path);
    if (!n || n->type != JSON_NUMBER) return def;
    return (int)n->nv;
}

int json_bool(JsonNode *root, const char *path, int def) {
    JsonNode *n = json_get(root, path);
    if (!n) return def;
    if (n->type == JSON_BOOL)   return n->bv;
    if (n->type == JSON_NUMBER) return (int)n->nv != 0;
    if (n->type == JSON_STRING && n->sv)
        return strcmp(n->sv, "true") == 0 || strcmp(n->sv, "1") == 0;
    return def;
}

int json_count(JsonNode *root, const char *path) {
    JsonNode *n = json_get(root, path);
    if (!n || n->type != JSON_ARRAY) return 0;
    int count = 0;
    for (JsonNode *c = n->child; c; c = c->next) count++;
    return count;
}

JsonNode *json_item(JsonNode *root, const char *path, int idx) {
    JsonNode *n = json_get(root, path);
    if (!n || n->type != JSON_ARRAY) return NULL;
    int i = 0;
    for (JsonNode *c = n->child; c; c = c->next) {
        if (i++ == idx) return c;
    }
    return NULL;
}
