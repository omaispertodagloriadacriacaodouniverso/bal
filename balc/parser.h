/* parser.h */
#ifndef PARSER_H
#define PARSER_H

#include "lexer.h"

typedef enum {
    NODE_PROGRAM, NODE_FUNC, NODE_PARAM, NODE_STRUCT,
    NODE_LET, NODE_RETURN, NODE_IF, NODE_WHILE, NODE_FOR,
    NODE_PRINT, NODE_EXPR_STMT, NODE_BLOCK,
    NODE_BINOP, NODE_UNARY, NODE_CALL, NODE_IDENT,
    NODE_INT, NODE_FLOAT, NODE_STR, NODE_BOOL, NODE_INDEX, NODE_ATTR,
    NODE_ARRAY, NODE_TEST, NODE_ASSERT,
} NodeType;

typedef struct ASTNode {
    NodeType type;
    char* value;
    char* type_name;
    int is_mutable;
    int is_nullable;
    struct ASTNode* left;
    struct ASTNode* right;
    struct ASTNode** children;
    int child_count;
    int child_cap;
} ASTNode;

ASTNode* parse_source(Token* tokens, int count);

#endif