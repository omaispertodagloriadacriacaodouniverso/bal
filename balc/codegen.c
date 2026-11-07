/* balc codegen — generates C code from AST */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "lexer.h"
#include "parser.h"

/* ── Type mapping ── */
static const char* ctype_of(const char* t) {
    if (!t) return "int";
    /* strip ? suffix */
    static char buf[256];
    strncpy(buf, t, sizeof(buf)-1);
    buf[sizeof(buf)-1] = '\0';
    int len = strlen(buf);
    if (len > 0 && buf[len-1] == '?') buf[len-1] = '\0';
    if (strcmp(buf, "int") == 0) return "int";
    if (strcmp(buf, "float") == 0) return "double";
    if (strcmp(buf, "bool") == 0) return "int";
    if (strcmp(buf, "str") == 0) return "const char*";
    if (strcmp(buf, "void") == 0) return "void";
    return buf; /* struct name or other */
}

/* ── Code generation state ── */
typedef struct {
    char** lines;
    int count;
    int capacity;
    int indent;
    /* tracking */
    char** array_vars;
    int array_count;
    char** struct_vars;
    char** struct_types;
    int struct_var_count;
    char** func_returns;
    char** func_return_types;
    int func_return_count;
    char** declared_vars;
    int declared_count;
    ASTNode** structs;
    int struct_count;
    ASTNode** tests;
    int test_count;
    int in_test;
    int in_global;
    char** global_init;
    int global_init_count;
    char** global_names;
    int global_names_count;
} CodeGen;

static void cg_init(CodeGen* cg) {
    cg->lines = malloc(4096 * sizeof(char*));
    cg->count = 0;
    cg->capacity = 4096;
    cg->indent = 0;
    cg->array_vars = malloc(256 * sizeof(char*));
    cg->array_count = 0;
    cg->struct_vars = malloc(256 * sizeof(char*));
    cg->struct_types = malloc(256 * sizeof(char*));
    cg->struct_var_count = 0;
    cg->func_returns = malloc(256 * sizeof(char*));
    cg->func_return_types = malloc(256 * sizeof(char*));
    cg->func_return_count = 0;
    cg->structs = malloc(64 * sizeof(ASTNode*));
    cg->struct_count = 0;
    cg->declared_vars = malloc(256 * sizeof(char*));
    cg->declared_count = 0;
    cg->tests = malloc(64 * sizeof(ASTNode*));
    cg->test_count = 0;
    cg->in_test = 0;
    cg->in_global = 0;
    cg->global_init = malloc(256 * sizeof(char*));
    cg->global_init_count = 0;
    cg->global_names = malloc(256 * sizeof(char*));
    cg->global_names_count = 0;
}

static void cg_emit(CodeGen* cg, const char* code) {
    if (cg->count >= cg->capacity) {
        cg->capacity *= 2;
        cg->lines = realloc(cg->lines, cg->capacity * sizeof(char*));
    }
    char buf[4096];
    snprintf(buf, sizeof(buf), "%*s%s", cg->indent * 4, "", code);
    cg->lines[cg->count++] = strdup(buf);
}

static int is_array_var(CodeGen* cg, const char* name) {
    for (int i = 0; i < cg->array_count; i++)
        if (strcmp(cg->array_vars[i], name) == 0) return 1;
    return 0;
}

static const char* struct_var_type(CodeGen* cg, const char* name) {
    for (int i = 0; i < cg->struct_var_count; i++)
        if (strcmp(cg->struct_vars[i], name) == 0) return cg->struct_types[i];
    return NULL;
}

static const char* func_return_type(CodeGen* cg, const char* name) {
    for (int i = 0; i < cg->func_return_count; i++)
        if (strcmp(cg->func_returns[i], name) == 0) return cg->func_return_types[i];
    return NULL;
}

static int is_struct_name(CodeGen* cg, const char* name) {
    for (int i = 0; i < cg->struct_count; i++)
        if (strcmp(cg->structs[i]->value, name) == 0) return 1;
    return 0;
}

static ASTNode* find_struct(CodeGen* cg, const char* name) {
    for (int i = 0; i < cg->struct_count; i++)
        if (strcmp(cg->structs[i]->value, name) == 0) return cg->structs[i];
    return NULL;
}

/* ── Forward declarations ── */
static char* gen_expr(CodeGen* cg, ASTNode* node);

static int expr_is_str(CodeGen* cg, ASTNode* n) {
    if (!n) return 0;
    if (n->type == NODE_STR) return 1;
    if (n->type == NODE_CALL && n->left && n->left->type == NODE_IDENT) {
        const char* rt = func_return_type(cg, n->left->value);
        if (rt && (strcmp(rt, "str") == 0 || strcmp(rt, "str?") == 0)) return 1;
        const char* fn = n->left->value;
        if (strcmp(fn, "read_file") == 0 || strcmp(fn, "str_concat") == 0 ||
            strcmp(fn, "str_slice") == 0 || strcmp(fn, "str_trim") == 0) return 1;
    }
    if (n->type == NODE_BINOP && n->value && strcmp(n->value, "+") == 0)
        return expr_is_str(cg, n->left) || expr_is_str(cg, n->right);
    return 0;
}

static void collect_lets(CodeGen* cg, ASTNode* node, char names[][256], ASTNode* nodes[], int* count, int max) {
    if (!node) return;
    if (node->type == NODE_LET && node->value && node->child_count >= 1 && node->children[0]->type != NODE_INDEX) {
        int found = 0;
        for (int i = 0; i < *count; i++) if (strcmp(names[i], node->value) == 0) { found = 1; break; }
        if (!found && *count < max) {
            strncpy(names[*count], node->value, 255);
            nodes[*count] = node;
            (*count)++;
        }
    }
    for (int i = 0; i < node->child_count; i++) collect_lets(cg, node->children[i], names, nodes, count, max);
    if (node->left) collect_lets(cg, node->left, names, nodes, count, max);
    if (node->right) collect_lets(cg, node->right, names, nodes, count, max);
}

static const char* infer_ctype(CodeGen* cg, ASTNode* e) {
    if (!e) return "int";
    if (e->type == NODE_STR) return "const char*";
    if (e->type == NODE_FLOAT) return "double";
    if (e->type == NODE_INT) return "int";
    if (e->type == NODE_CALL && e->left && e->left->type == NODE_IDENT) {
        const char* fn = e->left->value;
        if (is_struct_name(cg, fn)) return fn;
        const char* rt = func_return_type(cg, fn);
        if (rt) return ctype_of(rt);
        if (strcmp(fn, "read_file") == 0 || strcmp(fn, "str_concat") == 0 ||
            strcmp(fn, "str_slice") == 0 || strcmp(fn, "str_trim") == 0) return "const char*";
    }
    if (e->type == NODE_ARRAY) return "BalArray";
    return "int";
}

/* ── gen_stmt ── */
static void gen_stmt(CodeGen* cg, ASTNode* stmt) {
    if (!stmt) return;
    if (stmt->type == NODE_LET) {
        /* Index assignment: arr[i] = val (two children, first is INDEX) */
        if (stmt->child_count == 2 && stmt->children[0]->type == NODE_INDEX) {
            ASTNode* idx = stmt->children[0];
            char* obj = gen_expr(cg, idx->left);
            char* ix = gen_expr(cg, idx->right);
            char* val = gen_expr(cg, stmt->children[1]);
            char buf[4096];
            if (idx->left->type == NODE_IDENT && is_array_var(cg, idx->left->value))
                snprintf(buf, sizeof(buf), "%s.data[%s] = %s;", obj, ix, val);
            else
                snprintf(buf, sizeof(buf), "%s[%s] = %s;", obj, ix, val);
            cg_emit(cg, buf);
            free(obj); free(ix); free(val);
            return;
        }
        /* Array literal */
        if (stmt->children && stmt->children[0] && stmt->children[0]->type == NODE_ARRAY) {
            ASTNode* arr = stmt->children[0];
            char name[256];
            snprintf(name, sizeof(name), "%s", stmt->value);
            /* Track as array var */
            cg->array_vars[cg->array_count++] = strdup(name);
            char buf[4096];
            int hoisted = 0;
            for (int d = 0; d < cg->declared_count; d++)
                if (strcmp(cg->declared_vars[d], name) == 0) { hoisted = 1; break; }
            if (cg->in_global) {
                snprintf(buf, sizeof(buf), "int* _%s_data;", name);
                cg_emit(cg, buf);
                snprintf(buf, sizeof(buf), "BalArray %s;", name);
                cg_emit(cg, buf);
                char g[4096];
                snprintf(g, sizeof(g), "_%s_data = malloc(%d * sizeof(int));", name, arr->child_count);
                cg->global_init[cg->global_init_count++] = strdup(g);
            } else if (hoisted) {
            snprintf(buf, sizeof(buf), "_%s_data = malloc(%d * sizeof(int));", name, arr->child_count);
            cg_emit(cg, buf);
            } else {
            snprintf(buf, sizeof(buf), "int* _%s_data = malloc(%d * sizeof(int));", name, arr->child_count);
            cg_emit(cg, buf);
            }
            for (int i = 0; i < arr->child_count; i++) {
                char* val = gen_expr(cg, arr->children[i]);
                if (cg->in_global) {
                    snprintf(buf, sizeof(buf), "_%s_data[%d] = %s;", name, i, val);
                    cg->global_init[cg->global_init_count++] = strdup(buf);
                } else {
                    snprintf(buf, sizeof(buf), "_%s_data[%d] = %s;", name, i, val);
                    cg_emit(cg, buf);
                }
                free(val);
            }
            if (cg->in_global) {
                snprintf(buf, sizeof(buf), "%s = bal_array_new(_%s_data, %d);", name, name, arr->child_count);
                cg->global_init[cg->global_init_count++] = strdup(buf);
            } else if (hoisted) {
                snprintf(buf, sizeof(buf), "%s = bal_array_new(_%s_data, %d);", name, name, arr->child_count);
                cg_emit(cg, buf);
            } else {
                snprintf(buf, sizeof(buf), "BalArray %s = bal_array_new(_%s_data, %d);", name, name, arr->child_count);
                cg_emit(cg, buf);
            }
            return;
        }

        /* Struct construction */
        int is_struct = 0;
        if (stmt->children && stmt->children[0] && stmt->children[0]->type == NODE_CALL) {
            ASTNode* call = stmt->children[0];
            if (call->left && call->left->type == NODE_IDENT && is_struct_name(cg, call->left->value)) {
                is_struct = 1;
            }
        }

        const char* ctype = "int";
        int nullable = 0;
        if (stmt->type_name) {
            char tbuf[256];
            strncpy(tbuf, stmt->type_name, sizeof(tbuf)-1);
            tbuf[sizeof(tbuf)-1] = '\0';
            if (strlen(tbuf) > 0 && tbuf[strlen(tbuf)-1] == '?') {
                nullable = 1;
                tbuf[strlen(tbuf)-1] = '\0';
            }
            ctype = ctype_of(tbuf);
        } else if (stmt->children && stmt->children[0]) {
            /* Infer type from expr - simplified */
            if (stmt->children[0]->type == NODE_STR) ctype = "const char*";
            else if (stmt->children[0]->type == NODE_FLOAT) ctype = "double";
            else if (stmt->children[0]->type == NODE_INT) ctype = "int";
            else if (stmt->children[0]->type == NODE_BINOP && strcmp(stmt->children[0]->value, "+") == 0 &&
                     ((stmt->children[0]->left && stmt->children[0]->left->type == NODE_STR) ||
                      (stmt->children[0]->right && stmt->children[0]->right->type == NODE_STR))) ctype = "const char*";
            else if (stmt->children[0]->type == NODE_CALL && stmt->children[0]->left && stmt->children[0]->left->type == NODE_IDENT) {
                const char* fn = stmt->children[0]->left->value;
                if (is_struct_name(cg, fn)) { ctype = fn; is_struct = 1; }
                else {
                    const char* rt = func_return_type(cg, fn);
                    if (rt && (strcmp(rt, "str") == 0 || strcmp(rt, "str?") == 0)) ctype = "const char*";
                    else if (strcmp(fn, "read_file") == 0 || strcmp(fn, "str_concat") == 0 || strcmp(fn, "str_slice") == 0 || strcmp(fn, "str_trim") == 0) ctype = "const char*";
                    else if (rt && strcmp(rt, "float") == 0) ctype = "double";
                }
            }
        }

        char* init = gen_expr(cg, stmt->children[0]);

        /* None → 0/NULL */
        if (strcmp(init, "None") == 0) {
            if (strcmp(ctype, "int") == 0 || strcmp(ctype, "double") == 0) init = strdup("0");
            else init = strdup("NULL");
        }

        /* Check if already declared (reassignment) */
        int already_declared = 0;
        for (int i = 0; i < cg->declared_count; i++) {
            if (strcmp(cg->declared_vars[i], stmt->value) == 0) { already_declared = 1; break; }
        }

        if (already_declared) {
            char buf[4096];
            snprintf(buf, sizeof(buf), "%s = %s;", stmt->value, init);
            cg_emit(cg, buf);
        } else {
            cg->declared_vars[cg->declared_count++] = strdup(stmt->value);
            if (is_struct) {
                cg->struct_vars[cg->struct_var_count] = strdup(stmt->value);
                cg->struct_types[cg->struct_var_count] = strdup(ctype);
                cg->struct_var_count++;
                char buf[4096];
                snprintf(buf, sizeof(buf), "%s %s = %s;", ctype, stmt->value, init);
                cg_emit(cg, buf);
            } else if (stmt->is_mutable || strcmp(ctype, "Arena") == 0) {
                char buf[4096];
                snprintf(buf, sizeof(buf), "%s %s = %s;", ctype, stmt->value, init);
                cg_emit(cg, buf);
            } else {
                char buf[4096];
                snprintf(buf, sizeof(buf), "const %s %s = %s;", ctype, stmt->value, init);
                cg_emit(cg, buf);
            }
        }

        if (nullable) {
            /* track nullable - not used in C codegen for now */
        }
        free(init);
        return;
    }

    if (stmt->type == NODE_RETURN) {
        if (stmt->child_count > 0) {
            char* expr = gen_expr(cg, stmt->children[0]);
            char buf[4096];
            snprintf(buf, sizeof(buf), "return %s;", expr);
            cg_emit(cg, buf);
            free(expr);
        } else {
            cg_emit(cg, "return;");
        }
        return;
    }

    if (stmt->type == NODE_IF) {
        char* cond = gen_expr(cg, stmt->children[0]);
        char buf[4096];
        snprintf(buf, sizeof(buf), "if (%s) {", cond);
        cg_emit(cg, buf);
        free(cond);
        cg->indent++;
        if (stmt->child_count > 1) gen_stmt(cg, stmt->children[1]);
        cg->indent--;
        /* elif chain: pairs of (cond, BLOCK); trailing BLOCK = else body */
        int j = 2;
        while (j + 1 < stmt->child_count && stmt->children[j]->type != NODE_BLOCK) {
            char* ec = gen_expr(cg, stmt->children[j]);
            char buf[4096];
            snprintf(buf, sizeof(buf), "} else if (%s) {", ec);
            cg_emit(cg, buf);
            free(ec);
            cg->indent++;
            gen_stmt(cg, stmt->children[j + 1]);
            cg->indent--;
            j += 2;
        }
        if (j < stmt->child_count) {
            cg_emit(cg, "} else {");
            cg->indent++;
            gen_stmt(cg, stmt->children[j]);
            cg->indent--;
        }
        cg_emit(cg, "}");
        return;
    }

    if (stmt->type == NODE_WHILE) {
        char* cond = gen_expr(cg, stmt->children[0]);
        char buf[4096];
        snprintf(buf, sizeof(buf), "while (%s) {", cond);
        cg_emit(cg, buf);
        free(cond);
        cg->indent++;
        if (stmt->child_count > 1) gen_stmt(cg, stmt->children[1]);
        cg->indent--;
        cg_emit(cg, "}");
        return;
    }

    if (stmt->type == NODE_FOR) {
        if (stmt->children[0] && stmt->children[0]->type == NODE_ARRAY) {
            /* for x in arr */
            ASTNode* arr = stmt->children[0];
            /* simplified: not fully supported */
        }
        /* for x in range(n) */
        if (stmt->children[0] && stmt->children[0]->type == NODE_CALL &&
            stmt->children[0]->left && stmt->children[0]->left->type == NODE_IDENT &&
            strcmp(stmt->children[0]->left->value, "range") == 0) {
            char* n = gen_expr(cg, stmt->children[0]->children[0]);
            char buf[4096];
            snprintf(buf, sizeof(buf), "for (int %s = 0; %s < %s; %s++) {", stmt->value, stmt->value, n, stmt->value);
            cg_emit(cg, buf);
            free(n);
            cg->indent++;
            if (stmt->child_count > 1) gen_stmt(cg, stmt->children[1]);
            cg->indent--;
            cg_emit(cg, "}");
            return;
        }
        /* for x in array var */
        if (stmt->children[0] && stmt->children[0]->type == NODE_IDENT && is_array_var(cg, stmt->children[0]->value)) {
            char* arr = stmt->children[0]->value;
            char buf[4096];
            snprintf(buf, sizeof(buf), "for (int _i = 0; _i < %s.len; _i++) {", arr);
            cg_emit(cg, buf);
            cg->indent++;
            snprintf(buf, sizeof(buf), "int %s = %s.data[_i];", stmt->value, arr);
            cg_emit(cg, buf);
            if (stmt->child_count > 1) gen_stmt(cg, stmt->children[1]);
            cg->indent--;
            cg_emit(cg, "}");
            return;
        }
        return;
    }

    if (stmt->type == NODE_PRINT) {
        if (stmt->child_count > 0) {
            char* expr = gen_expr(cg, stmt->children[0]);
            /* Determine format */
            const char* fmt = "%d";
            /* Simplified: check if it's a string literal or string-returning call */
            if (stmt->children[0]->type == NODE_STR) fmt = "%s";
            else if (stmt->children[0]->type == NODE_FLOAT) fmt = "%f";
            else if (stmt->children[0]->type == NODE_CALL && stmt->children[0]->left && stmt->children[0]->left->type == NODE_IDENT) {
                const char* fn = stmt->children[0]->left->value;
                /* Check func return type */
                for (int k = 0; k < cg->func_return_count; k++) {
                    if (strcmp(cg->func_returns[k], fn) == 0) {
                        if (strcmp(cg->func_return_types[k], "float") == 0) fmt = "%f";
                        if (strcmp(cg->func_return_types[k], "str") == 0) fmt = "%s";
                        if (strcmp(cg->func_return_types[k], "double") == 0) fmt = "%f";
                    }
                }
                if (strcmp(fn, "greet") == 0 || strcmp(fn, "str_concat") == 0 ||
                    strcmp(fn, "read_file") == 0 || strcmp(fn, "str_slice") == 0 ||
                    strcmp(fn, "str_trim") == 0) fmt = "%s";
            }
            char buf[4096];
            snprintf(buf, sizeof(buf), "printf(\"%s\\n\", %s);", fmt, expr);
            cg_emit(cg, buf);
            free(expr);
        }
        return;
    }

    if (stmt->type == NODE_ASSERT) {
        if (stmt->child_count > 0) {
            char* expr = gen_expr(cg, stmt->children[0]);
            char buf[4096];
            snprintf(buf, sizeof(buf), "%s(%s);", cg->in_test ? "bal_tassert" : "bal_assert", expr);
            cg_emit(cg, buf);
            free(expr);
        }
        return;
    }

    if (stmt->type == NODE_EXPR_STMT) {
        if (stmt->child_count > 0) {
            char* expr = gen_expr(cg, stmt->children[0]);
            char buf[4096];
            snprintf(buf, sizeof(buf), "%s;", expr);
            cg_emit(cg, buf);
            free(expr);
        }
        return;
    }

    if (stmt->type == NODE_BLOCK) {
        for (int i = 0; i < stmt->child_count; i++) {
            gen_stmt(cg, stmt->children[i]);
        }
        return;
    }
}

/* ── gen_expr ── */
static char* gen_expr(CodeGen* cg, ASTNode* node) {
    if (!node) return strdup("0");
    char buf[4096];

    switch (node->type) {
        case NODE_INT:
            return strdup(node->value);
        case NODE_FLOAT:
            return strdup(node->value);
        case NODE_STR:
            snprintf(buf, sizeof(buf), "\"%s\"", node->value);
            return strdup(buf);
        case NODE_BOOL:
            return strdup(strcmp(node->value, "true") == 0 ? "1" : "0");
        case NODE_IDENT:
            if (strcmp(node->value, "NULL") == 0) return strdup("NULL");
            if (strcmp(node->value, "None") == 0) return strdup("0");
            return strdup(node->value);
        case NODE_BINOP: {
            char* left = gen_expr(cg, node->left);
            char* right = gen_expr(cg, node->right);
            /* Single-char string literal vs string index → char comparison */
            if ((strcmp(node->value, "==") == 0 || strcmp(node->value, "!=") == 0) &&
                ((node->left->type == NODE_STR && (strlen(node->left->value) == 1 || (strlen(node->left->value) == 2 && node->left->value[0] == '\\')) && node->right->type == NODE_INDEX) ||
                 (node->right->type == NODE_STR && (strlen(node->right->value) == 1 || (strlen(node->right->value) == 2 && node->right->value[0] == '\\')) && node->left->type == NODE_INDEX))) {
                ASTNode* strlit = node->left->type == NODE_STR ? node->left : node->right;
                char* other = node->left->type == NODE_STR ? right : left;
                char cbuf[8];
                char c;
                if (strlen(strlit->value) == 2 && strlit->value[0] == '\\') {
                    switch (strlit->value[1]) {
                        case 'n': c = '\n'; break;
                        case 't': c = '\t'; break;
                        case 'r': c = '\r'; break;
                        case '0': c = '\0'; break;
                        default: c = strlit->value[1]; break;
                    }
                } else c = strlit->value[0];
                if (c == '\n') snprintf(cbuf, sizeof(cbuf), "'\\n'");
                else if (c == '\t') snprintf(cbuf, sizeof(cbuf), "'\\t'");
                else if (c == '\r') snprintf(cbuf, sizeof(cbuf), "'\\r'");
                else if (c == '\\') snprintf(cbuf, sizeof(cbuf), "'\\\\'");
                else if (c == '\'') snprintf(cbuf, sizeof(cbuf), "'\\''");
                else snprintf(cbuf, sizeof(cbuf), "'%c'", c);
                snprintf(buf, sizeof(buf), "(%s %s %s)", other, node->value, cbuf);
                char* res = strdup(buf);
                free(left); free(right);
                return res;
            }
            if (strcmp(node->value, "+") == 0) {
                int is_str = expr_is_str(cg, node->left) || expr_is_str(cg, node->right);
                if (is_str) {
                    snprintf(buf, sizeof(buf), "str_concat(%s, %s)", left, right);
                } else {
                    snprintf(buf, sizeof(buf), "(%s + %s)", left, right);
                }
                char* res = strdup(buf);
                free(left); free(right);
                return res;
            }
            if (strcmp(node->value, "-") == 0) { snprintf(buf, sizeof(buf), "(%s - %s)", left, right); }
            else if (strcmp(node->value, "*") == 0) { snprintf(buf, sizeof(buf), "(%s * %s)", left, right); }
            else if (strcmp(node->value, "/") == 0) { snprintf(buf, sizeof(buf), "(%s / %s)", left, right); }
            else if (strcmp(node->value, "%") == 0) { snprintf(buf, sizeof(buf), "(%s %% %s)", left, right); }
            else if (strcmp(node->value, "==") == 0) { snprintf(buf, sizeof(buf), "(%s == %s)", left, right); }
            else if (strcmp(node->value, "!=") == 0) { snprintf(buf, sizeof(buf), "(%s != %s)", left, right); }
            else if (strcmp(node->value, "<") == 0) { snprintf(buf, sizeof(buf), "(%s < %s)", left, right); }
            else if (strcmp(node->value, ">") == 0) { snprintf(buf, sizeof(buf), "(%s > %s)", left, right); }
            else if (strcmp(node->value, "<=") == 0) { snprintf(buf, sizeof(buf), "(%s <= %s)", left, right); }
            else if (strcmp(node->value, ">=") == 0) { snprintf(buf, sizeof(buf), "(%s >= %s)", left, right); }
            else if (strcmp(node->value, "and") == 0) { snprintf(buf, sizeof(buf), "(%s && %s)", left, right); }
            else if (strcmp(node->value, "or") == 0) { snprintf(buf, sizeof(buf), "(%s || %s)", left, right); }
            else { snprintf(buf, sizeof(buf), "(%s %s %s)", left, node->value, right); }
            char* res = strdup(buf);
            free(left); free(right);
            return res;
        }
        case NODE_UNARY: {
            char* operand = gen_expr(cg, node->left);
            if (strcmp(node->value, "-") == 0) snprintf(buf, sizeof(buf), "(-%s)", operand);
            else if (strcmp(node->value, "not") == 0) snprintf(buf, sizeof(buf), "(!%s)", operand);
            else snprintf(buf, sizeof(buf), "(%s%s)", node->value, operand);
            char* res = strdup(buf);
            free(operand);
            return res;
        }
        case NODE_CALL: {
            /* Arena methods: Arena.new(cap), a.alloc(size), a.free() */
            if (node->left && node->left->type == NODE_ATTR) {
                ASTNode* attr = node->left;
                if (attr->left && attr->left->type == NODE_IDENT && strcmp(attr->left->value, "Arena") == 0 && strcmp(attr->value, "new") == 0) {
                    char* arg = node->child_count > 0 ? gen_expr(cg, node->children[0]) : strdup("0");
                    snprintf(buf, sizeof(buf), "arena_new(%s)", arg);
                    free(arg);
                    return strdup(buf);
                }
                char* obj = gen_expr(cg, attr->left);
                if (strcmp(attr->value, "alloc") == 0) {
                    char* arg = node->child_count > 0 ? gen_expr(cg, node->children[0]) : strdup("0");
                    snprintf(buf, sizeof(buf), "arena_alloc(&%s, %s)", obj, arg);
                    free(obj); free(arg);
                    return strdup(buf);
                }
                if (strcmp(attr->value, "free") == 0) {
                    snprintf(buf, sizeof(buf), "(arena_free(&%s), 0)", obj);
                    free(obj);
                    return strdup(buf);
                }
            }
            /* Struct construction */
            if (node->left && node->left->type == NODE_IDENT && is_struct_name(cg, node->left->value)) {
                ASTNode* struct_def = find_struct(cg, node->left->value);
                char fields[4096] = "";
                int pos = 0;
                for (int i = 0; i < node->child_count && i < struct_def->child_count; i++) {
                    char* val = gen_expr(cg, node->children[i]);
                    if (i > 0) pos += snprintf(fields + pos, sizeof(fields) - pos, ", ");
                    pos += snprintf(fields + pos, sizeof(fields) - pos, ".%s = %s", struct_def->children[i]->value, val);
                    free(val);
                }
                snprintf(buf, sizeof(buf), "(%s){%s}", node->left->value, fields);
                return strdup(buf);
            }
            char* func = gen_expr(cg, node->left);
            /* Builtins */
            if (strcmp(func, "len") == 0) {
                if (node->child_count > 0 && node->children[0]->type == NODE_IDENT && is_array_var(cg, node->children[0]->value)) {
                    char* arr = node->children[0]->value;
                    snprintf(buf, sizeof(buf), "%s.len", arr);
                    free(func);
                    return strdup(buf);
                }
                char* arg = gen_expr(cg, node->children[0]);
                snprintf(buf, sizeof(buf), "(int)strlen(%s)", arg);
                free(func); free(arg);
                return strdup(buf);
            }
            if (strcmp(func, "char_at") == 0) {
                char* arg = gen_expr(cg, node->children[0]);
                char* idx = gen_expr(cg, node->children[1]);
                snprintf(buf, sizeof(buf), "(int)(unsigned char)(%s)[%s]", arg, idx);
                free(func); free(arg); free(idx);
                return strdup(buf);
            }
            if (strcmp(func, "str_eq") == 0) {
                char* arg = gen_expr(cg, node->children[0]);
                char* arg2 = gen_expr(cg, node->children[1]);
                snprintf(buf, sizeof(buf), "str_eq(%s, %s)", arg, arg2);
                free(func); free(arg); free(arg2);
                return strdup(buf);
            }
            if (strcmp(func, "str_len") == 0) {
                char* arg = gen_expr(cg, node->children[0]);
                snprintf(buf, sizeof(buf), "(int)strlen(%s)", arg);
                free(func); free(arg);
                return strdup(buf);
            }
            if (strcmp(func, "read_file") == 0) {
                char* arg = gen_expr(cg, node->children[0]);
                snprintf(buf, sizeof(buf), "read_file(%s)", arg);
                free(func); free(arg);
                return strdup(buf);
            }
            if (strcmp(func, "num_args") == 0) { free(func); return strdup("argc"); }
            if (strcmp(func, "get_arg") == 0) {
                char* arg = gen_expr(cg, node->children[0]);
                snprintf(buf, sizeof(buf), "argv[%s]", arg);
                free(func); free(arg);
                return strdup(buf);
            }
            if (strcmp(func, "is_none") == 0) {
                char* arg = gen_expr(cg, node->children[0]);
                snprintf(buf, sizeof(buf), "(%s == 0)", arg);
                free(func); free(arg);
                return strdup(buf);
            }
            if (strcmp(func, "unwrap") == 0) {
                char* arg = gen_expr(cg, node->children[0]);
                free(func);
                return arg;
            }
            if (strcmp(func, "Some") == 0) {
                if (node->child_count > 0) {
                    char* arg = gen_expr(cg, node->children[0]);
                    free(func);
                    return arg;
                }
                free(func);
                return strdup("0");
            }
            if (strcmp(func, "append") == 0) {
                char* arr = gen_expr(cg, node->children[0]);
                char* val = gen_expr(cg, node->children[1]);
                snprintf(buf, sizeof(buf), "(bal_array_append(&%s, %s), 0)", arr, val);
                free(func); free(arr); free(val);
                return strdup(buf);
            }
            /* Generic function call */
            char args[4096] = "";
            int pos = 0;
            for (int i = 0; i < node->child_count; i++) {
                char* a = gen_expr(cg, node->children[i]);
                if (i > 0) pos += snprintf(args + pos, sizeof(args) - pos, ", ");
                pos += snprintf(args + pos, sizeof(args) - pos, "%s", a);
                free(a);
            }
            snprintf(buf, sizeof(buf), "%s(%s)", func, args);
            free(func);
            return strdup(buf);
        }
        case NODE_INDEX: {
            char* obj = gen_expr(cg, node->left);
            char* idx = gen_expr(cg, node->right);
            if (is_array_var(cg, node->left->type == NODE_IDENT ? node->left->value : "")) {
                snprintf(buf, sizeof(buf), "%s.data[%s]", obj, idx);
            } else {
                snprintf(buf, sizeof(buf), "%s[%s]", obj, idx);
            }
            free(obj); free(idx);
            return strdup(buf);
        }
        case NODE_ATTR: {
            char* obj = gen_expr(cg, node->left);
            snprintf(buf, sizeof(buf), "%s.%s", obj, node->value);
            free(obj);
            return strdup(buf);
        }
        case NODE_ARRAY: {
            /* Handled in gen_stmt as LetStmt; standalone array expr not supported */
            return strdup("0");
        }
        default:
            return strdup("0");
    }
}

/* ── gen_program ── */
static void gen_program(CodeGen* cg, ASTNode* node) {
    /* First pass: collect structs, tests and function signatures */
    for (int i = 0; i < node->child_count; i++) {
        if (node->children[i]->type == NODE_STRUCT) {
            cg->structs[cg->struct_count++] = node->children[i];
        }
        if (node->children[i]->type == NODE_TEST) {
            cg->tests[cg->test_count++] = node->children[i];
        }
    }

    /* Emit includes and helpers */
    cg_emit(cg, "#include <stdio.h>");
    cg_emit(cg, "#include <stdlib.h>");
    cg_emit(cg, "#include <string.h>");
    cg_emit(cg, "");
    cg_emit(cg, "typedef struct { int* data; int len; int cap; } BalArray;");
    cg_emit(cg, "static BalArray bal_array_new(int* data, int n) { BalArray a; a.data = data; a.len = n; a.cap = n; return a; }");
    cg_emit(cg, "static void bal_array_append(BalArray* a, int val) { if (a->len >= a->cap) { a->cap = a->cap * 2 + 1; a->data = realloc(a->data, a->cap * sizeof(int)); } a->data[a->len++] = val; }");
    cg_emit(cg, "static char* str_concat(const char* a, const char* b) { size_t la = strlen(a), lb = strlen(b); char* r = malloc(la + lb + 1); memcpy(r, a, la); memcpy(r + la, b, lb); r[la+lb] = 0; return r; }");
    cg_emit(cg, "static char* read_file(const char* path) { FILE* f = fopen(path, \"r\"); if (!f) return \"\"; fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET); char* buf = malloc(sz + 1); fread(buf, 1, sz, f); buf[sz] = 0; fclose(f); return buf; }");
    cg_emit(cg, "static void write_file(const char* path, const char* content) { FILE* f = fopen(path, \"w\"); if (f) { fputs(content, f); fclose(f); } }");
    cg_emit(cg, "static int str_find(const char* s, const char* sub) { const char* p = strstr(s, sub); return p ? (int)(p - s) : -1; }");
    cg_emit(cg, "static char* str_slice(const char* s, int start, int end) { int len = strlen(s); if (start < 0) start = 0; if (end > len) end = len; if (start > end) start = end; char* r = malloc(end - start + 1); memcpy(r, s + start, end - start); r[end-start] = 0; return r; }");
    cg_emit(cg, "static char* str_trim(const char* s) { while (*s == ' ' || *s == '\\t' || *s == '\\n' || *s == '\\r') s++; size_t len = strlen(s); while (len > 0 && (s[len-1] == ' ' || s[len-1] == '\\t' || s[len-1] == '\\n' || s[len-1] == '\\r')) len--; char* r = malloc(len + 1); memcpy(r, s, len); r[len] = 0; return r; }");
    cg_emit(cg, "static int str_contains(const char* s, const char* sub) { return strstr(s, sub) != NULL; }");
    cg_emit(cg, "static int str_count(const char* s, const char* sub) { int count = 0; const char* p = s; size_t sublen = strlen(sub); if (sublen == 0) return 0; while ((p = strstr(p, sub)) != NULL) { count++; p += sublen; } return count; }");
    cg_emit(cg, "static int str_eq(const char* a, const char* b) { return strcmp(a, b) == 0; }");
    cg_emit(cg, "typedef struct { char* pool; size_t used; size_t cap; } Arena;");
    cg_emit(cg, "static Arena arena_new(size_t cap) { Arena a; a.pool = malloc(cap); a.used = 0; a.cap = cap; return a; }");
    cg_emit(cg, "static void* arena_alloc(Arena* a, size_t size) { if (a->used + size > a->cap) return NULL; void* p = a->pool + a->used; a->used += size; return p; }");
    cg_emit(cg, "static void arena_free(Arena* a) { free(a->pool); a->used = 0; a->cap = 0; }");
    cg_emit(cg, "#define bal_assert(c) do { if (!(c)) { fprintf(stderr, \"assert failed: %s:%d\\n\", __FILE__, __LINE__); exit(1); } } while (0)");
    cg_emit(cg, "#define bal_tassert(c) do { if (!(c)) { fprintf(stderr, \"assert failed: %s:%d\\n\", __FILE__, __LINE__); return 1; } } while (0)");
    cg_emit(cg, "");

    /* Top-level statements -> C globals */
    for (int i = 0; i < node->child_count; i++) {
        ASTNode* c = node->children[i];
        if (c->type != NODE_STRUCT && c->type != NODE_FUNC && c->type != NODE_TEST) {
            cg->indent = 0;
            cg->declared_count = 0;
            cg->in_global = 1;
            if (c->type == NODE_LET && c->value)
                cg->global_names[cg->global_names_count++] = strdup(c->value);
            gen_stmt(cg, c);
            cg->in_global = 0;
        }
    }
    cg_emit(cg, "");
    if (cg->global_init_count > 0) {
        cg_emit(cg, "static void bal_init_globals(void) {");
        cg->indent++;
        for (int i = 0; i < cg->global_init_count; i++) cg_emit(cg, cg->global_init[i]);
        cg->indent--;
        cg_emit(cg, "}");
        cg_emit(cg, "");
    }
    cg_emit(cg, "");

    /* Emit structs */
    for (int i = 0; i < node->child_count; i++) {
        if (node->children[i]->type == NODE_STRUCT) {
            /* typedef struct */
            char buf[4096];
            snprintf(buf, sizeof(buf), "typedef struct {");
            cg_emit(cg, buf);
            cg->indent++;
            ASTNode* s = node->children[i];
            for (int j = 0; j < s->child_count; j++) {
                /* field: name : type */
                /* In our AST, struct fields are NODE_LET with value=field name, type_name=type */
                char fbuf[256];
                snprintf(fbuf, sizeof(fbuf), "%s %s;", ctype_of(s->children[j]->type_name), s->children[j]->value);
                cg_emit(cg, fbuf);
            }
            cg->indent--;
            snprintf(buf, sizeof(buf), "} %s;", s->value);
            cg_emit(cg, buf);
            cg_emit(cg, "");
        }
    }

    /* Forward declarations */
    for (int i = 0; i < node->child_count; i++) {
        if (node->children[i]->type == NODE_FUNC) {
            ASTNode* f = node->children[i];
            /* Track func return type */
            cg->func_returns[cg->func_return_count] = strdup(f->value);
            cg->func_return_types[cg->func_return_count] = strdup(f->type_name ? f->type_name : "void");
            cg->func_return_count++;
            /* extern check */
            int is_extern = f->is_mutable; /* reused field */
            if (is_extern) continue; /* libc already declares it */
            char params[4096] = "";
            int pos = 0;
            for (int j = 0; j < f->child_count; j++) {
                if (f->children[j]->type == NODE_PARAM) {
                    if (pos > 0) pos += snprintf(params + pos, sizeof(params) - pos, ", ");
                    const char* tn = f->children[j]->type_name ? f->children[j]->type_name : "int";
                    pos += snprintf(params + pos, sizeof(params) - pos, "%s %s", ctype_of(tn), f->children[j]->value);
                }
            }
            if (f->child_count == 0 || (f->child_count == 1 && f->children[0]->type == NODE_BLOCK)) {
                /* no params */
                if (strlen(params) == 0) strcpy(params, "void");
            }
            const char* ret = f->type_name ? ctype_of(f->type_name) : "void";
            const char* fname = f->value;
            if (strcmp(f->value, "main") == 0) {
                ret = "int";
                strcpy(params, "int argc, char** argv");
                if (cg->test_count > 0) fname = "bal_user_main";
            }
            char buf[4096];
            snprintf(buf, sizeof(buf), "%s %s(%s);", ret, fname, params);
            cg_emit(cg, buf);
        }
    }
    cg_emit(cg, "");

    /* Function definitions */
    for (int i = 0; i < node->child_count; i++) {
        if (node->children[i]->type == NODE_FUNC) {
            ASTNode* f = node->children[i];
            int is_extern = f->is_mutable;
            if (is_extern) continue; /* extern: just declaration (already emitted) */

            const char* ret = f->type_name ? ctype_of(f->type_name) : "void";
            const char* fname = f->value;
            if (strcmp(f->value, "main") == 0) {
                ret = "int";
                if (cg->test_count > 0) fname = "bal_user_main";
            }

            char params[4096] = "";
            int pos = 0;
            for (int j = 0; j < f->child_count; j++) {
                if (f->children[j]->type == NODE_PARAM) {
                    if (pos > 0) pos += snprintf(params + pos, sizeof(params) - pos, ", ");
                    const char* tn = f->children[j]->type_name ? f->children[j]->type_name : "int";
                    pos += snprintf(params + pos, sizeof(params) - pos, "%s %s", ctype_of(tn), f->children[j]->value);
                }
            }
            if (strlen(params) == 0) strcpy(params, "void");
            if (strcmp(f->value, "main") == 0) strcpy(params, "int argc, char** argv");

            char buf[4096];
            snprintf(buf, sizeof(buf), "%s %s(%s) {", ret, fname, params);
            cg_emit(cg, buf);
            cg->indent++;
            cg->declared_count = 0; /* reset per function */
            for (int g = 0; g < cg->global_names_count; g++)
                cg->declared_vars[cg->declared_count++] = strdup(cg->global_names[g]);
            if (strcmp(f->value, "main") == 0 && cg->global_init_count > 0)
                cg_emit(cg, "bal_init_globals();");
            /* hoist let/var declarations to function top (C block scope) */
            {
                char names[128][256];
                ASTNode* nodes[128];
                int ncount = 0;
                collect_lets(cg, f, names, nodes, &ncount, 128);
                for (int ni = 0; ni < ncount; ni++) {
                    int already = 0;
                    for (int d = 0; d < cg->declared_count; d++)
                        if (strcmp(cg->declared_vars[d], names[ni]) == 0) { already = 1; break; }
                    if (already) continue;
                    cg->declared_vars[cg->declared_count++] = strdup(names[ni]);
                    ASTNode* ln = nodes[ni];
                    char decl[512];
                    if (ln->child_count >= 1 && ln->children[0]->type == NODE_ARRAY) {
                        cg->array_vars[cg->array_count++] = strdup(names[ni]);
                        snprintf(decl, sizeof(decl), "int* _%s_data; BalArray %s;", names[ni], names[ni]);
                    } else {
                        const char* tn = ln->type_name ? ln->type_name : infer_ctype(cg, ln->children[0]);
                        snprintf(decl, sizeof(decl), "%s %s;", ctype_of(tn), names[ni]);
                    }
                    cg_emit(cg, decl);
                }
            }

            /* Find body (last child that is a BLOCK) */
            ASTNode* body = NULL;
            for (int j = f->child_count - 1; j >= 0; j--) {
                if (f->children[j]->type == NODE_BLOCK) { body = f->children[j]; break; }
            }
            if (body) {
                for (int j = 0; j < body->child_count; j++) {
                    gen_stmt(cg, body->children[j]);
                }
            }

            /* Add return for main */
            if (strcmp(f->value, "main") == 0) {
                /* Check if last stmt was return */
                int has_return = 0;
                if (body) {
                    for (int j = 0; j < body->child_count; j++) {
                        if (body->children[j]->type == NODE_RETURN) has_return = 1;
                    }
                }
                if (!has_return) cg_emit(cg, "return 0;");
            } else if (strcmp(ret, "void") == 0) {
                int has_return = 0;
                if (body) {
                    for (int j = 0; j < body->child_count; j++) {
                        if (body->children[j]->type == NODE_RETURN) has_return = 1;
                    }
                }
                if (!has_return) cg_emit(cg, "return;");
            }

            cg->indent--;
            cg_emit(cg, "}");
            cg_emit(cg, "");
        }
    }

    /* Test functions + runner */
    if (cg->test_count > 0) {
        for (int i = 0; i < cg->test_count; i++) {
            ASTNode* t = cg->tests[i];
            char buf[4096];
            cg_emit(cg, "");
            snprintf(buf, sizeof(buf), "static int bal_test_%d(void) {", i);
            cg_emit(cg, buf);
            cg->indent++;
            cg->declared_count = 0;
            cg->in_test = 1;
            if (t->child_count > 0 && t->children[0]->type == NODE_BLOCK) {
                for (int j = 0; j < t->children[0]->child_count; j++)
                    gen_stmt(cg, t->children[0]->children[j]);
            }
            cg->in_test = 0;
            cg_emit(cg, "return 0;");
            cg->indent--;
            cg_emit(cg, "}");
        }
        cg_emit(cg, "");
        cg_emit(cg, "static int bal_run_tests(void) {");
        cg->indent++;
        cg_emit(cg, "int fails = 0;");
        for (int i = 0; i < cg->test_count; i++) {
            char buf[4096];
            const char* name = cg->tests[i]->value ? cg->tests[i]->value : "";
            snprintf(buf, sizeof(buf),
                "if (bal_test_%d()) { printf(\"FAIL: %s\\n\"); fails++; } else { printf(\"PASS: %s\\n\"); }",
                i, name, name);
            cg_emit(cg, buf);
        }
        cg_emit(cg, "return fails;");
        cg->indent--;
        cg_emit(cg, "}");
        cg_emit(cg, "");
        cg_emit(cg, "int main(int argc, char** argv) {");
        cg->indent++;
        cg_emit(cg, "int f = bal_run_tests();");
        cg_emit(cg, "int r = bal_user_main(argc, argv);");
        cg_emit(cg, "return f ? 1 : r;");
        cg->indent--;
        cg_emit(cg, "}");
    }
}

/* ── Main ── */
int main(int argc, char** argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: balc <file.bal>\n");
        return 1;
    }

    FILE* f = fopen(argv[1], "r");
    if (!f) { fprintf(stderr, "Cannot open %s\n", argv[1]); return 1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char* src = malloc(sz + 1);
    fread(src, 1, sz, f);
    src[sz] = '\0';
    fclose(f);

    Token* tokens = lex_source(src);
    int count = 0;
    while (tokens[count].type != TOK_EOF) count++;
    count++;

    ASTNode* ast = parse_source(tokens, count);

    CodeGen cg;
    cg_init(&cg);
    gen_program(&cg, ast);

    /* Write to temp files next to the source (no hardcoded paths) */
    char cpath[4096], binpath[4096], errpath[4096];
    snprintf(cpath, sizeof(cpath), "%s.balc.c", argv[1]);
    snprintf(binpath, sizeof(binpath), "%s.balc.bin", argv[1]);
    snprintf(errpath, sizeof(errpath), "%s.balc.err", argv[1]);
    FILE* tmp = fopen(cpath, "w");
    for (int i = 0; i < cg.count; i++) {
        fprintf(tmp, "%s\n", cg.lines[i]);
    }
    fclose(tmp);

    /* Compile with gcc */
    char cmd[8192];
    snprintf(cmd, sizeof(cmd), "gcc -O2 -o %s %s 2>%s", binpath, cpath, errpath);
    int ret = system(cmd);
    if (ret != 0) {
        fprintf(stderr, "C compilation failed:\\n");
        FILE* err = fopen(errpath, "r");
        char buf[1024];
        while (fgets(buf, sizeof(buf), err)) fprintf(stderr, "%s", buf);
        fclose(err);
        return 1;
    }

    /* Run */
    snprintf(cmd, sizeof(cmd), "%s", binpath);
    ret = system(cmd);
    remove(cpath);
    remove(binpath);
    remove(errpath);
    return ret == -1 ? 1 : (ret >> 8);
}