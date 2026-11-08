/* balc lexer — tokenizes bal source */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "lexer.h"





typedef struct {
    Token* tokens;
    int count;
    int capacity;
    int* indent_stack;
    int indent_top;
} Lexer;

static const char* KEYWORDS[] = {
    "fn", "let", "var", "const", "if", "elif", "else", "while", "for",
    "in", "return", "struct", "match", "extern", "print", "import",
    "and", "or", "not", "true", "false", "None",
    "int", "float", "bool", "str", "void",
    "test", "assert",
    NULL
};

static int is_keyword(const char* word) {
    for (int i = 0; KEYWORDS[i]; i++) {
        if (strcmp(KEYWORDS[i], word) == 0) return 1;
    }
    return 0;
}

static void lexer_init(Lexer* lex) {
    lex->tokens = xmalloc(1024 * sizeof(Token));
    lex->count = 0;
    lex->capacity = 1024;
    lex->indent_stack = xmalloc(64 * sizeof(int));
    lex->indent_stack[0] = 0;
    lex->indent_top = 0;
}

static void add_token(Lexer* lex, TokenType type, const char* value, int line, int col) {
    if (lex->count >= lex->capacity) {
        lex->capacity *= 2;
        lex->tokens = xrealloc(lex->tokens, lex->capacity * sizeof(Token));
    }
    lex->tokens[lex->count].type = type;
    lex->tokens[lex->count].value = xstrdup(value);
    lex->tokens[lex->count].line = line;
    lex->tokens[lex->count].col = col;
    lex->count++;
}

static void push_indent(Lexer* lex, int indent) {
    lex->indent_top++;
    lex->indent_stack[lex->indent_top] = indent;
}

static int pop_indent(Lexer* lex) {
    if (lex->indent_top > 0) {
        lex->indent_top--;
        return 1;
    }
    return 0;
}

int current_indent(Lexer* lex) {
    return lex->indent_stack[lex->indent_top];
}

/* Tokenize a single line (without indentation handling) */
static void tokenize_line(Lexer* lex, const char* text, int line_num, int base_col) {
    int i = 0;
    int len = strlen(text);
    char buf[256];
    
    while (i < len) {
        if (isspace((unsigned char)text[i])) { i++; continue; }
        
        /* String literal */
        if (text[i] == '"' || text[i] == '\'') {
            char quote = text[i];
            int j = i + 1;
            while (j < len && text[j] != quote) {
                if (text[j] == '\\' && j + 1 < len) j += 2;
                else j++;
            }
            int slen = j - i - 1;
            char* str = xmalloc(slen + 1);
            memcpy(str, text + i + 1, slen);
            str[slen] = '\0';
            add_token(lex, TOK_STR, str, line_num, base_col + i);
            i = j + 1;
            continue;
        }
        
        /* Number */
        if (isdigit((unsigned char)text[i]) || (text[i] == '.' && i + 1 < len && isdigit((unsigned char)text[i+1]))) {
            int j = i;
            int is_float = 0;
            while (j < len && (isdigit((unsigned char)text[j]) || text[j] == '.')) {
                if (text[j] == '.') is_float = 1;
                j++;
            }
            int nlen = j - i;
            char* num = xmalloc(nlen + 1);
            memcpy(num, text + i, nlen);
            num[nlen] = '\0';
            add_token(lex, is_float ? TOK_FLOAT : TOK_INT, num, line_num, base_col + i);
            i = j;
            continue;
        }
        
        /* Arrow -> */
        if (i + 1 < len && text[i] == '-' && text[i+1] == '>') {
            add_token(lex, TOK_ARROW, "->", line_num, base_col + i);
            i += 2;
            continue;
        }
        
        /* Operators */
        if (strchr("+-*/%<>!=&|", text[i])) {
            if (i + 1 < len && text[i+1] == '=') {
                char op[3] = {text[i], '=', '\0'};
                add_token(lex, TOK_OP, xstrdup(op), line_num, base_col + i);
                i += 2;
            } else {
                char op[2] = {text[i], '\0'};
                add_token(lex, TOK_OP, xstrdup(op), line_num, base_col + i);
                i++;
            }
            continue;
        }
        
        /* Single char tokens */
        if (text[i] == ':') { add_token(lex, TOK_COLON, ":", line_num, base_col + i); i++; continue; }
        if (text[i] == ',') { add_token(lex, TOK_COMMA, ",", line_num, base_col + i); i++; continue; }
        if (text[i] == '.') { add_token(lex, TOK_DOT, ".", line_num, base_col + i); i++; continue; }
        if (text[i] == '?') { add_token(lex, TOK_QUESTION, "?", line_num, base_col + i); i++; continue; }
        if (text[i] == '(') { add_token(lex, TOK_LPAREN, "(", line_num, base_col + i); i++; continue; }
        if (text[i] == ')') { add_token(lex, TOK_RPAREN, ")", line_num, base_col + i); i++; continue; }
        if (text[i] == '[') { add_token(lex, TOK_LBRACKET, "[", line_num, base_col + i); i++; continue; }
        if (text[i] == ']') { add_token(lex, TOK_RBRACKET, "]", line_num, base_col + i); i++; continue; }
        
        /* Identifiers and keywords */
        if (isalpha((unsigned char)text[i]) || text[i] == '_') {
            int j = i;
            while (j < len && (isalnum((unsigned char)text[j]) || text[j] == '_')) j++;
            int wlen = j - i;
            char* word = xmalloc(wlen + 1);
            memcpy(word, text + i, wlen);
            word[wlen] = '\0';
            if (is_keyword(word)) {
                add_token(lex, TOK_KEYWORD, word, line_num, base_col + i);
            } else {
                add_token(lex, TOK_IDENT, word, line_num, base_col + i);
            }
            i = j;
            continue;
        }
        
        /* Unknown */
        fprintf(stderr, "Unknown char '%c' at line %d\n", text[i], line_num);
        i++;
    }
}

Token* lex_source(const char* source) {
    Lexer lex;
    lexer_init(&lex);
    
    /* Split into lines */
    char* src = xstrdup(source);
    char* line = strtok(src, "\n");
    int line_num = 1;
    
    while (line) {
        /* Strip trailing whitespace */
        int len = strlen(line);
        while (len > 0 && (line[len-1] == ' ' || line[len-1] == '\t' || line[len-1] == '\r')) len--;
        line[len] = '\0';
        
        /* Skip empty lines and comments */
        char* stripped = line;
        while (*stripped == ' ' || *stripped == '\t') stripped++;
        if (*stripped == '\0' || *stripped == '#') {
            add_token(&lex, TOK_NEWLINE, "\n", line_num, 0);
            line = strtok(NULL, "\n");
            line_num++;
            continue;
        }
        
        /* Handle inline comments */
        char* hash = strchr(line, '#');
        if (hash) *hash = '\0';
        
        /* Measure indentation */
        int indent = 0;
        while (line[indent] == ' ' || line[indent] == '\t') indent++;
        
        /* Handle indent/dedent */
        if (indent > current_indent(&lex)) {
            push_indent(&lex, indent);
            add_token(&lex, TOK_INDENT, "", line_num, 0);
        }
        while (indent < current_indent(&lex)) {
            pop_indent(&lex);
            add_token(&lex, TOK_DEDENT, "", line_num, 0);
        }
        
        /* Tokenize line content */
        tokenize_line(&lex, line + indent, line_num, indent);
        add_token(&lex, TOK_NEWLINE, "\n", line_num, 0);
        
        line = strtok(NULL, "\n");
        line_num++;
    }
    
    /* Dedent to 0 */
    while (current_indent(&lex) > 0) {
        pop_indent(&lex);
        add_token(&lex, TOK_DEDENT, "", line_num, 0);
    }
    
    add_token(&lex, TOK_EOF, "", line_num, 0);
    
    /* Add sentinel */
    add_token(&lex, TOK_EOF, "", line_num, 0);
    
    free(src);
    return lex.tokens;
}

/* Test main */
