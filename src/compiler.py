#!/usr/bin/env python3
"""bal compiler — transpiles bal AST to C code."""

import os
import sys
import tempfile
import subprocess

sys.path.insert(0, os.path.dirname(__file__))
from parser import (parse, Program, FuncDef, Param, StructDef, LetStmt, ReturnStmt,
    IfStmt, WhileStmt, ForStmt, ExprStmt, PrintStmt, BinOp, UnaryOp, Call,
    Ident, IntLit, FloatLit, StrLit, BoolLit, Index, Attr, TestDef, AssertStmt, AssignStmt)

TYPE_MAP = {
    "int": "int",
    "float": "double",
    "bool": "int",
    "str": "const char*",
    "void": "void",
    "Arena": "Arena",
}

def ctype_of(t):
    if t is None:
        return "int"
    if t.endswith("?"):
        t = t[:-1]
    return TYPE_MAP.get(t, t)

class CodeGen:
    def __init__(self):
        self.lines = []
        self.indent = 0
        self.structs = []
        self.functions = []
        self.externs = []
        self.tests = []
        self.declared_vars = set()
        self.func_returns = {}
        self.array_vars = set()
        self.struct_vars = {}
        self.nullable_vars = set()
        self.in_test = False
        self.in_global = False
        self.global_init = []
        self.global_names = set()

    def emit(self, code):
        self.lines.append("    " * self.indent + code)

    def gen(self, node):
        if isinstance(node, Program):
            for stmt in node.stmts:
                if isinstance(stmt, StructDef):
                    self.structs.append(stmt)
                elif isinstance(stmt, FuncDef):
                    self.func_returns[stmt.name] = stmt.ret_type
                    if stmt.body == []:
                        self.externs.append(stmt)
                    else:
                        self.functions.append(stmt)
                elif isinstance(stmt, TestDef):
                    self.tests.append(stmt)
                else:
                    # top-level statement -> C global
                    self.indent = 0
                    self.in_global = True
                    if isinstance(stmt, LetStmt):
                        self.global_names.add(stmt.name)
                        stmt.mutable = True  # globals must be assignable
                    self.gen_stmt(stmt)
                    self.in_global = False
                    self.indent = 0
            self.lines.insert(0, "#include <stdio.h>")
            self.lines.insert(1, "#include <stdlib.h>")
            self.lines.insert(2, "#include <string.h>")
            self.lines.insert(3, "")
            self.lines.insert(4, "typedef struct { int* data; int len; int cap; } BalArray;")
            self.lines.insert(5, "static BalArray bal_array_new(int* data, int n) { BalArray a; a.data = data; a.len = n; a.cap = n; return a; }")
            self.lines.insert(6, "static void bal_array_append(BalArray* a, int val) { if (a->len >= a->cap) { a->cap = a->cap * 2 + 1; a->data = realloc(a->data, a->cap * sizeof(int)); } a->data[a->len++] = val; }")
            self.lines.insert(7, "static char* str_concat(const char* a, const char* b) { size_t la = strlen(a), lb = strlen(b); char* r = malloc(la + lb + 1); memcpy(r, a, la); memcpy(r + la, b, lb); r[la+lb] = 0; return r; }")
            self.lines.insert(8, "static char* read_file(const char* path) { FILE* f = fopen(path, \"r\"); if (!f) return \"\"; fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET); char* buf = malloc(sz + 1); fread(buf, 1, sz, f); buf[sz] = 0; fclose(f); return buf; }")
            self.lines.insert(9, "static void write_file(const char* path, const char* content) { FILE* f = fopen(path, \"w\"); if (f) { fputs(content, f); fclose(f); } }")
            self.lines.insert(10, "static int str_find(const char* s, const char* sub) { const char* p = strstr(s, sub); return p ? (int)(p - s) : -1; }")
            self.lines.insert(11, "static char* str_slice(const char* s, int start, int end) { int len = strlen(s); if (start < 0) start = 0; if (end > len) end = len; if (start > end) start = end; char* r = malloc(end - start + 1); memcpy(r, s + start, end - start); r[end-start] = 0; return r; }")
            self.lines.insert(12, "static char* str_trim(const char* s) { while (*s == ' ' || *s == '\\t' || *s == '\\n' || *s == '\\r') s++; size_t len = strlen(s); while (len > 0 && (s[len-1] == ' ' || s[len-1] == '\\t' || s[len-1] == '\\n' || s[len-1] == '\\r')) len--; char* r = malloc(len + 1); memcpy(r, s, len); r[len] = 0; return r; }")
            self.lines.insert(13, "static int str_contains(const char* s, const char* sub) { return strstr(s, sub) != NULL; }")
            self.lines.insert(14, "static int str_count(const char* s, const char* sub) { int count = 0; const char* p = s; size_t sublen = strlen(sub); if (sublen == 0) return 0; while ((p = strstr(p, sub)) != NULL) { count++; p += sublen; } return count; }")
            self.lines.insert(15, "static int str_eq(const char* a, const char* b) { return strcmp(a, b) == 0; }")
            # Arena allocator
            self.lines.insert(15, "typedef struct { char* pool; size_t used; size_t cap; } Arena;")
            self.lines.insert(16, "static Arena arena_new(size_t cap) { Arena a; a.pool = malloc(cap); a.used = 0; a.cap = cap; return a; }")
            self.lines.insert(17, "static void* arena_alloc(Arena* a, size_t size) { if (a->used + size > a->cap) return NULL; void* p = a->pool + a->used; a->used += size; return p; }")
            self.lines.insert(18, "static void arena_free(Arena* a) { free(a->pool); a->used = 0; a->cap = 0; }")
            self.lines.insert(19, "#define bal_assert(c) do { if (!(c)) { fprintf(stderr, \"assert failed: %s:%d\\n\", __FILE__, __LINE__); exit(1); } } while (0)")
            self.lines.insert(20, "#define bal_tassert(c) do { if (!(c)) { fprintf(stderr, \"assert failed: %s:%d\\n\", __FILE__, __LINE__); return 1; } } while (0)")
            self.lines.insert(20, "")
            for s in self.structs:
                self.gen_struct(s)
            self.lines.append("")
            for f in self.functions:
                self.gen_func_decl(f)
            self.lines.append("")
            for e in self.externs:
                self.gen_extern(e)
            if self.global_init:
                self.lines.append("static void bal_init_globals(void) {")
                self.indent += 1
                for g in self.global_init:
                    self.emit(g + ";")
                self.indent -= 1
                self.lines.append("}")
                self.lines.append("")
            for f in self.functions:
                self.gen_func(f)
            if self.tests:
                for i, t in enumerate(self.tests):
                    self.lines.append("")
                    self.lines.append(f"static int bal_test_{i}(void) {{")
                    self.indent += 1
                    self.declared_vars = set()
                    self.array_vars = set()
                    self.struct_vars = {}
                    self.nullable_vars = set()
                    self.in_test = True
                    for s in t.body:
                        self.gen_stmt(s)
                    self.in_test = False
                    self.emit("return 0;")
                    self.indent -= 1
                    self.lines.append("}")
                self.lines.append("")
                self.lines.append("static int bal_run_tests(void) {")
                self.indent += 1
                self.emit("int fails = 0;")
                for i, t in enumerate(self.tests):
                    escaped = t.name.replace("\\", "\\\\").replace('"', '\\"')
                    self.emit(f'if (bal_test_{i}()) {{ printf("FAIL: {escaped}\\n"); fails++; }} else {{ printf("PASS: {escaped}\\n"); }}')
                self.emit("return fails;")
                self.indent -= 1
                self.lines.append("}")
                self.lines.append("")
                self.lines.append("int main(int argc, char** argv) {")
                self.indent += 1
                self.emit("int f = bal_run_tests();")
                self.emit("int r = bal_user_main(argc, argv);")
                self.emit("return f ? 1 : r;")
                self.indent -= 1
                self.lines.append("}")
            return "\n".join(self.lines)

        elif isinstance(node, StructDef):
            self.structs.append(node)

        elif isinstance(node, FuncDef):
            pass

    def gen_struct_decl(self, node):
        pass

    def gen_struct(self, node):
        self.lines.append(f"typedef struct {{")
        self.indent += 1
        for fname, ftype in node.fields:
            ctype = ctype_of(ftype)
            self.emit(f"{ctype} {fname};")
        self.indent -= 1
        self.lines.append(f"}} {node.name};")
        self.lines.append("")

    def gen_func_decl(self, node):
        if node.name == "main":
            if self.tests:
                self.lines.append("static int bal_user_main(int argc, char** argv);")
                return
            ret = "int"
            params = "int argc, char** argv"
        else:
            ret = ctype_of(node.ret_type)
            params = ", ".join(f"{ctype_of(p.type)} {p.name}" for p in node.params) if node.params else "void"
        self.lines.append(f"{ret} {node.name}({params});")

    def gen_extern(self, node):
        # Skip declaration: libc headers (stdio.h etc.) already declare these,
        # and re-declaring with a fixed signature conflicts (e.g. printf varargs).
        return

    def _collect_lets(self, stmts, acc):
        for s in stmts:
            if isinstance(s, LetStmt) and s.name not in acc:
                acc[s.name] = s
            for attr in ("body", "elifs", "else_body"):
                sub = getattr(s, attr, None)
                if isinstance(sub, list):
                    if attr == "elifs":
                        for c, b in sub:
                            self._collect_lets([c], acc)
                            self._collect_lets(b, acc)
                    else:
                        self._collect_lets(sub, acc)

    def gen_func(self, node):
        self.declared_vars = set(self.global_names)
        # array_vars persists: global arrays must stay visible inside functions
        self.struct_vars = {}
        self.nullable_vars = set()
        fname = "bal_user_main" if (node.name == "main" and self.tests) else node.name
        if node.name == "main":
            ret = "int"
            params = "int argc, char** argv"
        else:
            ret = ctype_of(node.ret_type)
            params = ", ".join(f"{ctype_of(p.type)} {p.name}" for p in node.params) if node.params else "void"
        self.lines.append("")
        self.lines.append(f"{ret} {fname}({params}) {{")
        self.indent += 1
        if node.name == "main" and self.global_init:
            self.emit("bal_init_globals();")
        # hoist all let/var declarations to the top of the function (C block scope)
        decls = {}
        self._collect_lets(node.body, decls)
        for name, s in decls.items():
            if name in self.declared_vars:
                continue
            self.declared_vars.add(name)
            if isinstance(s.expr, tuple) and s.expr[0] == "list":
                self.array_vars.add(name)
                self.emit(f"int* _{name}_data;")
                self.emit(f"BalArray {name};")
                continue
            ctype = ctype_of(s.type) if s.type else self.infer_type(s.expr)
            if s.type and s.type.endswith("?"):
                self.nullable_vars.add(name)
            self.emit(f"{ctype} {name};")
        for stmt in node.body:
            self.gen_stmt(stmt)
        if node.name == "main":
            if not node.body or not isinstance(node.body[-1], ReturnStmt):
                self.emit("return 0;")
        elif node.ret_type == "void" and (not node.body or not isinstance(node.body[-1], ReturnStmt)):
            self.emit("return;")
        self.indent -= 1
        self.lines.append("}")

    def gen_stmt(self, stmt):
        if isinstance(stmt, LetStmt):
            if isinstance(stmt.expr, tuple) and stmt.expr[0] == "list":
                elems = stmt.expr[1]
                arr_name = stmt.name
                self.array_vars.add(arr_name)
                self.declared_vars.add(arr_name)
                if self.in_global:
                    self.emit(f"int* _{arr_name}_data;")
                    self.emit(f"BalArray {arr_name};")
                    self.global_init.append(f"_{arr_name}_data = malloc({len(elems)} * sizeof(int));")
                    for i, e in enumerate(elems):
                        self.global_init.append(f"_{arr_name}_data[{i}] = {self.gen_expr(e)};")
                    self.global_init.append(f"{arr_name} = bal_array_new(_{arr_name}_data, {len(elems)});")
                    return
                if arr_name in self.declared_vars:
                    # hoisted to function top: emit assignments only
                    self.emit(f"_{arr_name}_data = malloc({len(elems)} * sizeof(int));")
                    for i, e in enumerate(elems):
                        self.emit(f"_{arr_name}_data[{i}] = {self.gen_expr(e)};")
                    self.emit(f"{arr_name} = bal_array_new(_{arr_name}_data, {len(elems)});")
                    return
                self.emit(f"int* _{arr_name}_data = malloc({len(elems)} * sizeof(int));")
                for i, e in enumerate(elems):
                    self.emit(f"_{arr_name}_data[{i}] = {self.gen_expr(e)};")
                self.emit(f"BalArray {arr_name} = bal_array_new(_{arr_name}_data, {len(elems)});")
                return

            nullable = False
            ctype = ctype_of(stmt.type) if stmt.type else "int"
            if stmt.type and stmt.type.endswith("?"):
                nullable = True
                ctype = ctype_of(stmt.type[:-1])
            if stmt.type is None:
                ctype = self.infer_type(stmt.expr)
            init = self.gen_expr(stmt.expr)
            if init == "None":
                init = "0" if ctype in ("int", "double", "float") else "NULL"
            if stmt.name in self.declared_vars:
                self.emit(f"{stmt.name} = {init};")
            else:
                self.declared_vars.add(stmt.name)
                if nullable:
                    self.nullable_vars.add(stmt.name)
                if isinstance(stmt.expr, Call) and isinstance(stmt.expr.func, Ident) and stmt.expr.func.name in [s.name for s in self.structs]:
                    struct_name = stmt.expr.func.name
                    self.struct_vars[stmt.name] = struct_name
                    self.emit(f"{struct_name} {stmt.name} = {init};")
                elif stmt.mutable or ctype == "Arena":
                    self.emit(f"{ctype} {stmt.name} = {init};")
                else:
                    self.emit(f"const {ctype} {stmt.name} = {init};")
            return

        elif isinstance(stmt, ReturnStmt):
            if stmt.expr:
                self.emit(f"return {self.gen_expr(stmt.expr)};")
            else:
                self.emit("return;")

        elif isinstance(stmt, IfStmt):
            self.emit(f"if ({self.gen_expr(stmt.cond)}) {{")
            self.indent += 1
            for s in stmt.body:
                self.gen_stmt(s)
            self.indent -= 1
            for elif_cond, elif_body in (stmt.elifs or []):
                self.emit(f"}} else if ({self.gen_expr(elif_cond)}) {{")
                self.indent += 1
                for s in elif_body:
                    self.gen_stmt(s)
                self.indent -= 1
            if stmt.else_body:
                self.emit("} else {")
                self.indent += 1
                for s in stmt.else_body:
                    self.gen_stmt(s)
                self.indent -= 1
            self.emit("}")

        elif isinstance(stmt, WhileStmt):
            self.emit(f"while ({self.gen_expr(stmt.cond)}) {{")
            self.indent += 1
            for s in stmt.body:
                self.gen_stmt(s)
            self.indent -= 1
            self.emit("}")

        elif isinstance(stmt, ForStmt):
            if isinstance(stmt.iterable, Ident) and stmt.iterable.name in self.array_vars:
                arr = stmt.iterable.name
                self.emit(f"for (int _i = 0; _i < {arr}.len; _i++) {{")
                self.indent += 1
                self.emit(f"int {stmt.var} = {arr}.data[_i];")
                for s in stmt.body:
                    self.gen_stmt(s)
                self.indent -= 1
                self.emit("}")
            elif isinstance(stmt.iterable, Call) and isinstance(stmt.iterable.func, Ident) and stmt.iterable.func.name == "range":
                n = self.gen_expr(stmt.iterable.args[0])
                self.emit(f"for (int {stmt.var} = 0; {stmt.var} < {n}; {stmt.var}++) {{")
                self.indent += 1
                for s in stmt.body:
                    self.gen_stmt(s)
                self.indent -= 1
                self.emit("}")
            else:
                self.emit(f"/* for {stmt.var} in ... */")

        elif isinstance(stmt, PrintStmt):
            expr = self.gen_expr(stmt.expr)
            t = self.infer_type(stmt.expr)
            if t == "const char*":
                self.emit(f'printf("%s\\n", {expr});')
            elif t == "double":
                self.emit(f'printf("%f\\n", {expr});')
            else:
                self.emit(f'printf("%d\\n", {expr});')

        elif isinstance(stmt, ExprStmt):
            self.emit(f"{self.gen_expr(stmt.expr)};")

        elif isinstance(stmt, AssignStmt):
            tgt = self.gen_expr(stmt.target)
            val = self.gen_expr(stmt.expr)
            if isinstance(stmt.target.obj, Ident) and stmt.target.obj.name in self.array_vars:
                self.emit(f"{stmt.target.obj.name}.data[{self.gen_expr(stmt.target.idx)}] = {val};")
            else:
                self.emit(f"{tgt} = {val};")

        elif isinstance(stmt, AssertStmt):
            macro = "bal_tassert" if self.in_test else "bal_assert"
            self.emit(f"{macro}({self.gen_expr(stmt.expr)});")

    def gen_expr(self, expr):
        if isinstance(expr, IntLit):
            return str(expr.value)
        if isinstance(expr, FloatLit):
            return str(expr.value)
        if isinstance(expr, StrLit):
            escaped = (expr.value.replace("\\", "\\\\").replace('"', '\\"')
                       .replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r"))
            return f'"{escaped}"'
        if isinstance(expr, BoolLit):
            return "1" if expr.value else "0"
        if isinstance(expr, Ident):
            if expr.name == "NULL":
                return "NULL"
            if expr.name == "None":
                return "0"
            return expr.name
        if isinstance(expr, BinOp):
            left = self.gen_expr(expr.left)
            right = self.gen_expr(expr.right)
            op = expr.op
            if op == "+":
                if self.infer_type(expr.left) == "const char*" or self.infer_type(expr.right) == "const char*":
                    return f'str_concat({left}, {right})'
                return f"({left} + {right})"
            if op == "-":
                return f"({left} - {right})"
            if op == "*":
                return f"({left} * {right})"
            if op == "/":
                return f"({left} / {right})"
            if op == "%":
                return f"({left} % {right})"
            if op == "==" or op == "!=":
                if isinstance(expr.left, Index) and isinstance(expr.right, StrLit) and len(expr.right.value) == 1:
                    ch = expr.right.value
                    if ch == "\n": right = "'\\n'"
                    elif ch == "\t": right = "'\\t'"
                    elif ch == "\r": right = "'\\r'"
                    else: right = f"'{ch}'"
                if isinstance(expr.right, Index) and isinstance(expr.left, StrLit) and len(expr.left.value) == 1:
                    ch = expr.left.value
                    if ch == "\n": left = "'\\n'"
                    elif ch == "\t": left = "'\\t'"
                    elif ch == "\r": left = "'\\r'"
                    else: left = f"'{ch}'"
                if op == "==":
                    return f"({left} == {right})"
                return f"({left} != {right})"
            if op == "<":
                return f"({left} < {right})"
            if op == ">":
                return f"({left} > {right})"
            if op == "<=":
                return f"({left} <= {right})"
            if op == ">=":
                return f"({left} >= {right})"
            if op == "and":
                return f"({left} && {right})"
            if op == "or":
                return f"({left} || {right})"
            return f"({left} {op} {right})"
        if isinstance(expr, UnaryOp):
            operand = self.gen_expr(expr.expr)
            if expr.op == "-":
                return f"(-{operand})"
            if expr.op == "not":
                return f"(!{operand})"
            return f"({expr.op}{operand})"
        if isinstance(expr, Call):
            # Arena methods: Arena.new(cap), a.alloc(size), a.free()
            if isinstance(expr.func, Attr):
                obj = self.gen_expr(expr.func.obj)
                args = ", ".join(self.gen_expr(a) for a in expr.args)
                if isinstance(expr.func.obj, Ident) and expr.func.obj.name == "Arena" and expr.func.field == "new":
                    return f"arena_new({args})"
                if expr.func.field == "alloc":
                    return f"arena_alloc(&{obj}, {args})"
                if expr.func.field == "free":
                    return f"(arena_free(&{obj}), 0)"
            func = self.gen_expr(expr.func)
            args = ", ".join(self.gen_expr(a) for a in expr.args)
            if func == "len":
                if isinstance(expr.args[0], Ident) and expr.args[0].name in self.array_vars:
                    return f"{args}.len"
                return f"(int)strlen({args})"
            if func == "str":
                return args
            if func == "range":
                return args
            if func == "print":
                return f'printf("%d\\n", {args})'
            if func == "read_file":
                return f"read_file({args})"
            if func == "write_file":
                return f"(write_file({args}), 0)"
            if func == "get_arg":
                return f"argv[{args}]"
            if func == "num_args":
                return "argc"
            if func == "append":
                arr_name = self.gen_expr(expr.args[0])
                val = self.gen_expr(expr.args[1])
                return f"(bal_array_append(&{arr_name}, {val}), 0)"
            if func == "Some":
                return args if args else "0"
            if func == "is_none":
                x = self.gen_expr(expr.args[0])
                return f"({x} == 0)"
            if func == "unwrap":
                return self.gen_expr(expr.args[0])
            if func == "str_find":
                return f"str_find({args})"
            if func == "str_slice":
                return f"str_slice({args})"
            if func == "str_trim":
                return f"str_trim({args})"
            if func == "str_contains":
                return f"str_contains({args})"
            if func == "str_eq":
                return f"(strcmp({args}) == 0)"
            if func == "str_count":
                return f"str_count({args})"
            if func == "str_len":
                return f"(int)strlen({args})"
            if func == "char_at":
                s = self.gen_expr(expr.args[0])
                idx = self.gen_expr(expr.args[1])
                return f"(int)(unsigned char)({s})[{idx}]"
            if func == "str_concat":
                return f"str_concat({args})"
            # Struct construction
            if isinstance(expr.func, Ident) and expr.func.name in [s.name for s in self.structs]:
                struct_name = expr.func.name
                struct_def = next(s for s in self.structs if s.name == struct_name)
                fields = ", ".join(f".{f[0]} = {self.gen_expr(a)}" for f, a in zip(struct_def.fields, expr.args))
                return f"({struct_name}){{{fields}}}"
            return f"{func}({args})"
        if isinstance(expr, Index):
            obj = self.gen_expr(expr.obj)
            idx = self.gen_expr(expr.idx)
            if isinstance(expr.obj, Ident) and expr.obj.name in self.array_vars:
                return f"{obj}.data[{idx}]"
            return f"{obj}[{idx}]"
        if isinstance(expr, Attr):
            obj = self.gen_expr(expr.obj)
            return f"{obj}.{expr.field}"
        if isinstance(expr, tuple) and expr[0] == "list":
            return "/* list */"
        return "0"

    def infer_type(self, expr):
        if isinstance(expr, IntLit):
            return "int"
        if isinstance(expr, FloatLit):
            return "double"
        if isinstance(expr, StrLit):
            return "const char*"
        if isinstance(expr, BoolLit):
            return "int"
        if isinstance(expr, BinOp):
            if expr.op in ("+", "-", "*", "/", "%"):
                lt = self.infer_type(expr.left)
                rt = self.infer_type(expr.right)
                if lt == "const char*" or rt == "const char*":
                    return "const char*"
                if lt == "double" or rt == "double":
                    return "double"
                return "int"
            return "int"
        if isinstance(expr, Call):
            if isinstance(expr.func, Attr):
                if isinstance(expr.func.obj, Ident) and expr.func.obj.name == "Arena" and expr.func.field == "new":
                    return "Arena"
                if expr.func.field == "alloc":
                    return "void*"
                if expr.func.field == "free":
                    return "int"
            if isinstance(expr.func, Ident):
                if expr.func.name == "len":
                    return "int"
                if expr.func.name == "read_file":
                    return "const char*"
                if expr.func.name == "get_arg":
                    return "const char*"
                if expr.func.name == "append":
                    return "int"
                if expr.func.name in ("str_find","str_len","str_contains","str_count","is_none","unwrap","char_at"):
                    return "int"
                if expr.func.name in ("str_slice","str_trim","str_concat"):
                    return "const char*"
                if expr.func.name in [s.name for s in self.structs]:
                    return expr.func.name
                if expr.func.name in self.func_returns:
                    rt = self.func_returns[expr.func.name]
                    if rt.endswith("?"):
                        rt = rt[:-1]
                    return ctype_of(rt)
        if isinstance(expr, Ident):
            if expr.name in self.array_vars:
                return "BalArray"
            if expr.name in self.struct_vars:
                return self.struct_vars[expr.name]
        if isinstance(expr, Attr):
            if isinstance(expr.obj, Ident) and expr.obj.name in self.struct_vars:
                struct_name = self.struct_vars[expr.obj.name]
                struct_def = next((s for s in self.structs if s.name == struct_name), None)
                if struct_def:
                    for fname, ftype in struct_def.fields:
                        if fname == expr.field:
                            return ctype_of(ftype)
        return "int"


def compile_bal(source, output_path=None):
    from parser import parse
    ast = parse(source)
    codegen = CodeGen()
    codegen.gen(ast)
    c_code = "\n".join(codegen.lines)

    if output_path:
        with open(output_path, "w") as f:
            f.write(c_code)
        return c_code

    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as f:
        f.write(c_code)
        c_path = f.name

    exe_path = c_path.replace(".c", "")
    result = subprocess.run(
        ["gcc", "-O2", "-o", exe_path, c_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("C compilation failed:")
        print(result.stderr)
        print("\n--- Generated C ---")
        print(c_code)
        return None

    return exe_path, c_code


def main():
    if len(sys.argv) < 2:
        print("Usage: bal <file.bal> [--emit-c]")
        sys.exit(1)

    source = open(sys.argv[1]).read()
    emit_c = "--emit-c" in sys.argv

    if emit_c:
        ast = parse(source)
        codegen = CodeGen()
        codegen.gen(ast)
        print("\n".join(codegen.lines))
        return

    result = compile_bal(source)
    if result is None:
        sys.exit(1)

    exe_path, c_code = result
    run = subprocess.run([exe_path] + sys.argv[2:], capture_output=False)
    os.unlink(exe_path)
    sys.exit(run.returncode)


if __name__ == "__main__":
    main()
