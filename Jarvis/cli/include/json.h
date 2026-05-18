#ifndef JSON_H
#define JSON_H

/*
 * Minimal recursive-descent JSON parser.
 * All nodes are malloc'd — call json_free(root) when done.
 * Strings passed to json_str/json_int/json_count must use dot-separated
 * key paths: "workflow.tasks", "profile.display_name".
 */

#define JSON_NULL   0
#define JSON_BOOL   1
#define JSON_NUMBER 2
#define JSON_STRING 3
#define JSON_ARRAY  4
#define JSON_OBJECT 5

typedef struct JsonNode JsonNode;
struct JsonNode {
    int       type;
    char     *key;    /* object member key — owned */
    char     *sv;     /* STRING value — owned */
    double    nv;     /* NUMBER value */
    int       bv;     /* BOOL value (0 or 1) */
    JsonNode *child;  /* ARRAY/OBJECT: first child */
    JsonNode *next;   /* next sibling in parent's list */
};

JsonNode   *json_parse(const char *src);
void        json_free(JsonNode *n);

/* Lookup by dot-separated path: "workflow.current_focus" */
JsonNode   *json_get(JsonNode *root, const char *path);

/* Convenience accessors — return default if key missing or wrong type */
const char *json_str(JsonNode *root, const char *path);          /* NULL if absent */
int         json_int(JsonNode *root, const char *path, int def);
int         json_bool(JsonNode *root, const char *path, int def);/* handles JSON true/false */
int         json_count(JsonNode *root, const char *path);        /* array length, 0 if absent */
JsonNode   *json_item(JsonNode *root, const char *path, int idx);/* array element by index */

#endif /* JSON_H */
