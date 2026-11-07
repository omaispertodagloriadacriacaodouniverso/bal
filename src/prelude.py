"""C prelude — standard headers and runtime helpers emitted at the top of every generated file."""

C_HEADERS = [
    "#include <stdio.h>",
    "#include <stdlib.h>",
    "#include <string.h>",
    "",
]

C_RUNTIME = [
    "typedef struct { int* data; int len; int cap; } BalArray;",
    "static BalArray bal_array_new(int* data, int n) { BalArray a; a.data = data; a.len = n; a.cap = n; return a; }",
    "static void bal_array_append(BalArray* a, int val) { if (a->len >= a->cap) { a->cap = a->cap * 2 + 1; a->data = realloc(a->data, a->cap * sizeof(int)); } a->data[a->len++] = val; }",
    "static char* str_concat(const char* a, const char* b) { size_t la = strlen(a), lb = strlen(b); char* r = malloc(la + lb + 1); memcpy(r, a, la); memcpy(r + la, b, lb); r[la+lb] = 0; return r; }",
    "static char* read_file(const char* path) { FILE* f = fopen(path, \"r\"); if (!f) return \"\"; fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET); char* buf = malloc(sz + 1); fread(buf, 1, sz, f); buf[sz] = 0; fclose(f); return buf; }",
    "static void write_file(const char* path, const char* content) { FILE* f = fopen(path, \"w\"); if (f) { fputs(content, f); fclose(f); } }",
    "static int str_find(const char* s, const char* sub) { const char* p = strstr(s, sub); return p ? (int)(p - s) : -1; }",
    "static char* str_slice(const char* s, int start, int end) { int len = strlen(s); if (start < 0) start = 0; if (end > len) end = len; if (start > end) start = end; char* r = malloc(end - start + 1); memcpy(r, s + start, end - start); r[end-start] = 0; return r; }",
    "static char* str_trim(const char* s) { while (*s == ' ' || *s == '\\t' || *s == '\\n' || *s == '\\r') s++; size_t len = strlen(s); while (len > 0 && (s[len-1] == ' ' || s[len-1] == '\\t' || s[len-1] == '\\n' || s[len-1] == '\\r')) len--; char* r = malloc(len + 1); memcpy(r, s, len); r[len] = 0; return r; }",
    "static int str_contains(const char* s, const char* sub) { return strstr(s, sub) != NULL; }",
    "static int str_count(const char* s, const char* sub) { int count = 0; const char* p = s; size_t sublen = strlen(sub); if (sublen == 0) return 0; while ((p = strstr(p, sub)) != NULL) { count++; p += sublen; } return count; }",
    "static int str_eq(const char* a, const char* b) { return strcmp(a, b) == 0; }",
    # Arena allocator (FIXED: a->used, a->cap instead of a.used, a.cap)
    "typedef struct { char* pool; size_t used; size_t cap; } Arena;",
    "static Arena arena_new(size_t cap) { Arena a; a.pool = malloc(cap); a.used = 0; a.cap = cap; return a; }",
    "static void* arena_alloc(Arena* a, size_t size) { if (a->used + size > a->cap) return NULL; void* p = a->pool + a->used; a->used += size; return p; }",
    "static void arena_free(Arena* a) { free(a->pool); a->used = 0; a->cap = 0; }",
    "#define bal_assert(c) do { if (!(c)) { fprintf(stderr, \"assert failed: %s:%d\\n\", __FILE__, __LINE__); exit(1); } } while (0)",
    "#define bal_tassert(c) do { if (!(c)) { fprintf(stderr, \"assert failed: %s:%d\\n\", __FILE__, __LINE__); return 1; } } while (0)",
    "",
]

def prelude_lines():
    """Return the full C prelude as a list of lines."""
    return C_HEADERS + C_RUNTIME
