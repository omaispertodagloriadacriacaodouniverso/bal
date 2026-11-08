/* lexer.h */
#ifndef LEXER_H
#define LEXER_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Safe allocation — abort on OOM / NULL instead of writing to NULL */
static inline void* xmalloc(size_t n) {
    void* p = malloc(n);
    if (!p) { fprintf(stderr, "balc: out of memory (%zu bytes)\n", n); exit(1); }
    return p;
}
static inline void* xrealloc(void* p, size_t n) {
    void* q = realloc(p, n);
    if (!q) { fprintf(stderr, "balc: out of memory (%zu bytes)\n", n); exit(1); }
    return q;
}
static inline char* xstrdup(const char* s) {
    if (!s) { fprintf(stderr, "balc: strdup(NULL)\n"); exit(1); }
    char* r = strdup(s);
    if (!r) { fprintf(stderr, "balc: out of memory (strdup)\n"); exit(1); }
    return r;
}

/* Growable string vector — replaces fixed-size char* tables (no overflow) */
typedef struct { char** items; int count; int cap; } StrVec;
static inline void sv_init(StrVec* v) { v->items = NULL; v->count = 0; v->cap = 0; }
static inline void sv_push(StrVec* v, const char* s) {
    if (v->count == v->cap) {
        v->cap = v->cap ? v->cap * 2 : 8;
        v->items = xrealloc(v->items, (size_t)v->cap * sizeof(char*));
    }
    v->items[v->count++] = xstrdup(s);
}
static inline int sv_has(const StrVec* v, const char* s) {
    for (int i = 0; i < v->count; i++)
        if (strcmp(v->items[i], s) == 0) return 1;
    return 0;
}
static inline int sv_find(const StrVec* v, const char* s) {
    for (int i = 0; i < v->count; i++)
        if (strcmp(v->items[i], s) == 0) return i;
    return -1;
}
static inline void sv_clear(StrVec* v) {
    for (int i = 0; i < v->count; i++) free(v->items[i]);
    v->count = 0;
}

typedef enum {
    TOK_EOF, TOK_INDENT, TOK_DEDENT, TOK_NEWLINE,
    TOK_INT, TOK_FLOAT, TOK_STR, TOK_IDENT, TOK_KEYWORD,
    TOK_OP, TOK_COLON, TOK_COMMA, TOK_DOT, TOK_QUESTION,
    TOK_LPAREN, TOK_RPAREN, TOK_LBRACKET, TOK_RBRACKET, TOK_ARROW,
} TokenType;

typedef struct {
    TokenType type;
    char* value;
    int line;
    int col;
} Token;

Token* lex_source(const char* source);

#endif