/* lexer.h */
#ifndef LEXER_H
#define LEXER_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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