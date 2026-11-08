/* balc parser — recursive descent parser for bal */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "parser.h"

/* Include lexer */
#include "lexer.h"

/* ── AST Node Types ── */




/* ── Parser State ── */
typedef struct {
    Token* tokens;
    int pos;
    int count;
} Parser;

static ASTNode* new_node(NodeType type) {
    ASTNode* n = calloc(1, sizeof(ASTNode));
    n->type = type;
    n->children = xmalloc(8 * sizeof(ASTNode*));
    n->child_cap = 8;
    return n;
}

static void add_child(ASTNode* parent, ASTNode* child) {
    if (parent->child_count >= parent->child_cap) {
        parent->child_cap *= 2;
        parent->children = xrealloc(parent->children, parent->child_cap * sizeof(ASTNode*));
    }
    parent->children[parent->child_count++] = child;
}

static Token* peek(Parser* p, int offset) {
    int idx = p->pos + offset;
    if (idx < p->count) return &p->tokens[idx];
    return &p->tokens[p->count - 1];
}

static Token* advance(Parser* p) {
    Token* t = &p->tokens[p->pos];
    if (p->pos < p->count - 1) p->pos++;
    return t;
}

static int expect(Parser* p, TokenType type, const char* val) {
    Token* t = peek(p, 0);
    if (t->type != type) return 0;
    if (val && strcmp(t->value, val) != 0) return 0;
    advance(p);
    return 1;
}

static void skip_newlines(Parser* p) {
    while (peek(p, 0)->type == TOK_NEWLINE) advance(p);
}

static ASTNode* parse_expr(Parser* p);
static ASTNode* parse_stmt(Parser* p);
static ASTNode* parse_block(Parser* p);

/* ── Type parsing ── */
static char* parse_type(Parser* p) {
    Token* t = peek(p, 0);
    char* base = NULL;
    if (t->type == TOK_KEYWORD && (strcmp(t->value, "int") == 0 || strcmp(t->value, "float") == 0 ||
        strcmp(t->value, "bool") == 0 || strcmp(t->value, "str") == 0 || strcmp(t->value, "void") == 0)) {
        base = xstrdup(t->value);
        advance(p);
    } else if (t->type == TOK_IDENT) {
        base = xstrdup(t->value);
        advance(p);
    } else if (t->type == TOK_LBRACKET) {
        advance(p);
        char* inner = parse_type(p);
        expect(p, TOK_RBRACKET, NULL);
        char buf[256];
        snprintf(buf, sizeof(buf), "[%s]", inner);
        base = xstrdup(buf);
        free(inner);
    } else {
        return xstrdup("int");
    }
    /* Nullable suffix */
    if (peek(p, 0)->type == TOK_QUESTION) {
        advance(p);
        char buf[256];
        snprintf(buf, sizeof(buf), "%s?", base);
        free(base);
        base = xstrdup(buf);
    }
    return base;
}

/* ── Expression parsing (precedence climbing) ── */
static ASTNode* parse_primary(Parser* p) {
    Token* t = peek(p, 0);
    if (t->type == TOK_INT) {
        ASTNode* n = new_node(NODE_INT);
        n->value = xstrdup(t->value);
        advance(p);
        return n;
    }
    if (t->type == TOK_FLOAT) {
        ASTNode* n = new_node(NODE_FLOAT);
        n->value = xstrdup(t->value);
        advance(p);
        return n;
    }
    if (t->type == TOK_STR) {
        ASTNode* n = new_node(NODE_STR);
        n->value = xstrdup(t->value);
        advance(p);
        return n;
    }
    if (t->type == TOK_KEYWORD && (strcmp(t->value, "true") == 0 || strcmp(t->value, "false") == 0)) {
        ASTNode* n = new_node(NODE_BOOL);
        n->value = xstrdup(t->value);
        advance(p);
        return n;
    }
    if (t->type == TOK_KEYWORD && strcmp(t->value, "None") == 0) {
        ASTNode* n = new_node(NODE_IDENT);
        n->value = xstrdup("NULL");
        advance(p);
        return n;
    }
    if (t->type == TOK_IDENT) {
        ASTNode* n = new_node(NODE_IDENT);
        n->value = xstrdup(t->value);
        advance(p);
        return n;
    }
    if (t->type == TOK_LPAREN) {
        advance(p);
        ASTNode* e = parse_expr(p);
        expect(p, TOK_RPAREN, NULL);
        return e;
    }
    if (t->type == TOK_LBRACKET) {
        advance(p);
        ASTNode* n = new_node(NODE_ARRAY);
        while (peek(p, 0)->type != TOK_RBRACKET && peek(p, 0)->type != TOK_EOF) {
            ASTNode* elem = parse_expr(p);
            add_child(n, elem);
            if (peek(p, 0)->type == TOK_COMMA) advance(p);
        }
        expect(p, TOK_RBRACKET, NULL);
        return n;
    }
    return NULL;
}

static ASTNode* parse_postfix(Parser* p) {
    ASTNode* expr = parse_primary(p);
    while (1) {
        if (peek(p, 0)->type == TOK_LPAREN) {
            advance(p);
            ASTNode* call = new_node(NODE_CALL);
            call->left = expr;
            while (peek(p, 0)->type != TOK_RPAREN && peek(p, 0)->type != TOK_EOF) {
                ASTNode* arg = parse_expr(p);
                add_child(call, arg);
                if (peek(p, 0)->type == TOK_COMMA) advance(p);
            }
            expect(p, TOK_RPAREN, NULL);
            expr = call;
        } else if (peek(p, 0)->type == TOK_LBRACKET) {
            advance(p);
            ASTNode* idx = parse_expr(p);
            expect(p, TOK_RBRACKET, NULL);
            ASTNode* node = new_node(NODE_INDEX);
            node->left = expr;
            node->right = idx;
            expr = node;
        } else if (peek(p, 0)->type == TOK_DOT) {
            advance(p);
            Token* field = peek(p, 0);
            if (field->type == TOK_IDENT) {
                ASTNode* attr = new_node(NODE_ATTR);
                attr->left = expr;
                attr->value = xstrdup(field->value);
                advance(p);
                expr = attr;
            }
        } else {
            break;
        }
    }
    return expr;
}

static ASTNode* parse_unary(Parser* p) {
    if (peek(p, 0)->type == TOK_OP && (peek(p,0)->value[0] == '-' || peek(p,0)->value[0] == '+')) {
        char* op = xstrdup(peek(p,0)->value);
        advance(p);
        ASTNode* operand = parse_unary(p);
        ASTNode* node = new_node(NODE_UNARY);
        node->value = op;
        node->left = operand;
        return node;
    }
    if (peek(p, 0)->type == TOK_KEYWORD && strcmp(peek(p,0)->value, "not") == 0) {
        advance(p);
        ASTNode* operand = parse_unary(p);
        ASTNode* node = new_node(NODE_UNARY);
        node->value = xstrdup("not");
        node->left = operand;
        return node;
    }
    return parse_postfix(p);
}

static ASTNode* parse_mul(Parser* p) {
    ASTNode* left = parse_unary(p);
    while (peek(p, 0)->type == TOK_OP && (peek(p,0)->value[0] == '*' || peek(p,0)->value[0] == '/' || peek(p,0)->value[0] == '%')) {
        char* op = xstrdup(peek(p,0)->value);
        advance(p);
        ASTNode* right = parse_unary(p);
        ASTNode* node = new_node(NODE_BINOP);
        node->value = op;
        node->left = left;
        node->right = right;
        left = node;
    }
    return left;
}

static ASTNode* parse_add(Parser* p) {
    ASTNode* left = parse_mul(p);
    while (peek(p, 0)->type == TOK_OP && (peek(p,0)->value[0] == '+' || peek(p,0)->value[0] == '-')) {
        char* op = xstrdup(peek(p,0)->value);
        advance(p);
        ASTNode* right = parse_mul(p);
        ASTNode* node = new_node(NODE_BINOP);
        node->value = op;
        node->left = left;
        node->right = right;
        left = node;
    }
    return left;
}

static ASTNode* parse_cmp(Parser* p) {
    ASTNode* left = parse_add(p);
    while (peek(p, 0)->type == TOK_OP && (strcmp(peek(p,0)->value, "==") == 0 || strcmp(peek(p,0)->value, "!=") == 0 ||
           strcmp(peek(p,0)->value, "<") == 0 || strcmp(peek(p,0)->value, ">") == 0 ||
           strcmp(peek(p,0)->value, "<=") == 0 || strcmp(peek(p,0)->value, ">=") == 0)) {
        char* op = xstrdup(peek(p,0)->value);
        advance(p);
        ASTNode* right = parse_add(p);
        ASTNode* node = new_node(NODE_BINOP);
        node->value = op;
        node->left = left;
        node->right = right;
        left = node;
    }
    return left;
}

static ASTNode* parse_not(Parser* p) {
    if (peek(p, 0)->type == TOK_KEYWORD && strcmp(peek(p,0)->value, "not") == 0) {
        advance(p);
        ASTNode* operand = parse_not(p);
        ASTNode* node = new_node(NODE_UNARY);
        node->value = xstrdup("not");
        node->left = operand;
        return node;
    }
    return parse_cmp(p);
}

static ASTNode* parse_and(Parser* p) {
    ASTNode* left = parse_not(p);
    while (peek(p, 0)->type == TOK_KEYWORD && strcmp(peek(p,0)->value, "and") == 0) {
        advance(p);
        ASTNode* right = parse_not(p);
        ASTNode* node = new_node(NODE_BINOP);
        node->value = xstrdup("and");
        node->left = left;
        node->right = right;
        left = node;
    }
    return left;
}

static ASTNode* parse_or(Parser* p) {
    ASTNode* left = parse_and(p);
    while (peek(p, 0)->type == TOK_KEYWORD && strcmp(peek(p,0)->value, "or") == 0) {
        advance(p);
        ASTNode* right = parse_and(p);
        ASTNode* node = new_node(NODE_BINOP);
        node->value = xstrdup("or");
        node->left = left;
        node->right = right;
        left = node;
    }
    return left;
}

static ASTNode* parse_expr(Parser* p) {
    return parse_or(p);
}

/* ── Statement parsing ── */


static ASTNode* parse_block(Parser* p) {
    ASTNode* block = new_node(NODE_BLOCK);
    skip_newlines(p);
    if (peek(p, 0)->type != TOK_INDENT) return block;
    advance(p); /* consume INDENT */
    while (peek(p, 0)->type != TOK_DEDENT && peek(p, 0)->type != TOK_EOF) {
        skip_newlines(p);
        if (peek(p, 0)->type == TOK_DEDENT || peek(p, 0)->type == TOK_EOF) break;
        ASTNode* stmt = parse_stmt(p);
        if (stmt) add_child(block, stmt);
        skip_newlines(p);
    }
    if (peek(p, 0)->type == TOK_DEDENT) advance(p);
    return block;
}

static ASTNode* parse_stmt(Parser* p) {
    Token* t = peek(p, 0);
    if (t->type == TOK_KEYWORD) {
        if (strcmp(t->value, "fn") == 0) {
            advance(p);
            ASTNode* node = new_node(NODE_FUNC);
            Token* name = peek(p, 0);
            if (name->type == TOK_IDENT) {
                node->value = xstrdup(name->value);
                advance(p);
            }
            expect(p, TOK_LPAREN, NULL);
            while (peek(p, 0)->type != TOK_RPAREN && peek(p, 0)->type != TOK_EOF) {
                ASTNode* param = new_node(NODE_PARAM);
                Token* pname = peek(p, 0);
                if (pname->type == TOK_IDENT) {
                    param->value = xstrdup(pname->value);
                    advance(p);
                }
                expect(p, TOK_COLON, NULL);
                char* ptype = parse_type(p);
                param->type_name = ptype;
                add_child(node, param);
                if (peek(p, 0)->type == TOK_COMMA) advance(p);
            }
            expect(p, TOK_RPAREN, NULL);
            if (peek(p, 0)->type == TOK_ARROW) {
                advance(p);
                node->type_name = parse_type(p); /* return type */
            } else {
                node->type_name = xstrdup("void");
            }
            expect(p, TOK_COLON, NULL);
            skip_newlines(p);
            ASTNode* body = parse_block(p);
            add_child(node, body);
            return node;
        }
        if (strcmp(t->value, "struct") == 0) {
            advance(p);
            ASTNode* node = new_node(NODE_STRUCT);
            Token* name = peek(p, 0);
            if (name->type == TOK_IDENT) {
                node->value = xstrdup(name->value);
                advance(p);
            }
            expect(p, TOK_COLON, NULL);
            skip_newlines(p);
            expect(p, TOK_INDENT, NULL);
            while (peek(p, 0)->type != TOK_DEDENT && peek(p, 0)->type != TOK_EOF) {
                skip_newlines(p);
                if (peek(p, 0)->type == TOK_DEDENT) break;
                ASTNode* field = new_node(NODE_LET);
                Token* fname = peek(p, 0);
                if (fname->type == TOK_IDENT) {
                    field->value = xstrdup(fname->value);
                    advance(p);
                }
                expect(p, TOK_COLON, NULL);
                field->type_name = parse_type(p);
                add_child(node, field);
                skip_newlines(p);
            }
            if (peek(p, 0)->type == TOK_DEDENT) advance(p);
            return node;
        }
        if (strcmp(t->value, "let") == 0 || strcmp(t->value, "var") == 0) {
            int mutable = (strcmp(t->value, "var") == 0);
            advance(p);
            ASTNode* node = new_node(NODE_LET);
            node->is_mutable = mutable;
            Token* name = peek(p, 0);
            if (name->type == TOK_IDENT) {
                node->value = xstrdup(name->value);
                advance(p);
            }
            if (peek(p, 0)->type == TOK_COLON) {
                advance(p);
                node->type_name = parse_type(p);
            }
            expect(p, TOK_OP, "=");
            ASTNode* expr = parse_expr(p);
            add_child(node, expr);
            return node;
        }
        if (strcmp(t->value, "if") == 0) {
            advance(p);
            ASTNode* node = new_node(NODE_IF);
            ASTNode* cond = parse_expr(p);
            add_child(node, cond);
            expect(p, TOK_COLON, NULL);
            skip_newlines(p);
            ASTNode* body = parse_block(p);
            add_child(node, body);
            /* Handle elif/else */
            while (peek(p, 0)->type == TOK_KEYWORD && (strcmp(peek(p,0)->value, "elif") == 0 || strcmp(peek(p,0)->value, "else") == 0)) {
                if (strcmp(peek(p,0)->value, "elif") == 0) {
                    advance(p);
                    ASTNode* elif_cond = parse_expr(p);
                    expect(p, TOK_COLON, NULL);
                    skip_newlines(p);
                    ASTNode* elif_body = parse_block(p);
                    /* Store as child pair (cond, body) */
                    add_child(node, elif_cond);
                    add_child(node, elif_body);
                } else {
                    advance(p);
                    expect(p, TOK_COLON, NULL);
                    skip_newlines(p);
                    ASTNode* else_body = parse_block(p);
                    add_child(node, else_body);
                    break;
                }
            }
            return node;
        }
        if (strcmp(t->value, "while") == 0) {
            advance(p);
            ASTNode* node = new_node(NODE_WHILE);
            ASTNode* cond = parse_expr(p);
            add_child(node, cond);
            expect(p, TOK_COLON, NULL);
            skip_newlines(p);
            ASTNode* body = parse_block(p);
            add_child(node, body);
            return node;
        }
        if (strcmp(t->value, "for") == 0) {
            advance(p);
            ASTNode* node = new_node(NODE_FOR);
            Token* var = peek(p, 0);
            if (var->type == TOK_IDENT) {
                node->value = xstrdup(var->value);
                advance(p);
            }
            expect(p, TOK_KEYWORD, "in");
            ASTNode* iter = parse_expr(p);
            add_child(node, iter);
            expect(p, TOK_COLON, NULL);
            skip_newlines(p);
            ASTNode* body = parse_block(p);
            add_child(node, body);
            return node;
        }
        if (strcmp(t->value, "return") == 0) {
            advance(p);
            ASTNode* node = new_node(NODE_RETURN);
            if (peek(p, 0)->type != TOK_NEWLINE && peek(p, 0)->type != TOK_DEDENT && peek(p, 0)->type != TOK_EOF) {
                ASTNode* expr = parse_expr(p);
                add_child(node, expr);
            }
            return node;
        }
        if (strcmp(t->value, "print") == 0) {
            advance(p);
            ASTNode* node = new_node(NODE_PRINT);
            ASTNode* expr = parse_expr(p);
            add_child(node, expr);
            return node;
        }
        if (strcmp(t->value, "test") == 0) {
            advance(p);
            ASTNode* node = new_node(NODE_TEST);
            Token* name = peek(p, 0);
            if (name->type == TOK_STR) {
                node->value = xstrdup(name->value);
                advance(p);
            }
            expect(p, TOK_COLON, NULL);
            skip_newlines(p);
            ASTNode* body = parse_block(p);
            add_child(node, body);
            return node;
        }
        if (strcmp(t->value, "assert") == 0) {
            advance(p);
            ASTNode* node = new_node(NODE_ASSERT);
            ASTNode* expr = parse_expr(p);
            add_child(node, expr);
            return node;
        }
        if (strcmp(t->value, "extern") == 0) {
            advance(p);
            expect(p, TOK_KEYWORD, "fn");
            ASTNode* node = new_node(NODE_FUNC);
            /* mark as extern */
            node->is_mutable = 1; /* reuse field as extern flag */
            Token* name = peek(p, 0);
            if (name->type == TOK_IDENT) {
                node->value = xstrdup(name->value);
                advance(p);
            }
            expect(p, TOK_LPAREN, NULL);
            while (peek(p, 0)->type != TOK_RPAREN && peek(p, 0)->type != TOK_EOF) {
                ASTNode* param = new_node(NODE_PARAM);
                Token* pname = peek(p, 0);
                if (pname->type == TOK_IDENT) {
                    param->value = xstrdup(pname->value);
                    advance(p);
                }
                expect(p, TOK_COLON, NULL);
                param->type_name = parse_type(p);
                add_child(node, param);
                if (peek(p, 0)->type == TOK_COMMA) advance(p);
            }
            expect(p, TOK_RPAREN, NULL);
            if (peek(p, 0)->type == TOK_ARROW) {
                advance(p);
                node->type_name = parse_type(p);
            } else {
                node->type_name = xstrdup("void");
            }
            return node;
        }
    }
    if (t->type == TOK_IDENT) {
        /* Assignment: x = expr */
        if (peek(p, 1)->type == TOK_OP && strcmp(peek(p,1)->value, "=") == 0) {
            advance(p);
            expect(p, TOK_OP, "=");
            ASTNode* expr = parse_expr(p);
            ASTNode* node = new_node(NODE_LET);
            node->value = xstrdup(t->value);
            node->is_mutable = 1;
            add_child(node, expr);
            return node;
        }
        ASTNode* expr = parse_expr(p);
        if (expr->type == NODE_INDEX && peek(p, 0)->type == TOK_OP && strcmp(peek(p,0)->value, "=") == 0) {
            advance(p);
            ASTNode* val = parse_expr(p);
            ASTNode* node = new_node(NODE_LET);
            node->is_mutable = 1;
            add_child(node, expr);
            add_child(node, val);
            return node;
        }
        ASTNode* node = new_node(NODE_EXPR_STMT);
        add_child(node, expr);
        return node;
    }
    /* Skip INDENT/DEDENT */
    if (t->type == TOK_INDENT || t->type == TOK_DEDENT) {
        advance(p);
        return NULL;
    }
    return NULL;
}

ASTNode* parse_source(Token* tokens, int count) {
    Parser p;
    p.tokens = tokens;
    p.pos = 0;
    p.count = count;
    ASTNode* program = new_node(NODE_PROGRAM);
    skip_newlines(&p);
    while (peek(&p, 0)->type != TOK_EOF) {
        ASTNode* stmt = parse_stmt(&p);
        if (stmt) add_child(program, stmt);
        skip_newlines(&p);
    }
    return program;
}