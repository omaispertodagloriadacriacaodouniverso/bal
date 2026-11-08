#!/usr/bin/env python3
"""bal compiler — transpiles bal AST to C code."""

import os
import sys
import tempfile
import subprocess

sys.path.insert(0, os.path.dirname(__file__))
from parser import (parse, Program, FuncDef, StructDef, LetStmt, ReturnStmt,
    IfStmt, WhileStmt, ForStmt, ExprStmt, PrintStmt, BinOp, UnaryOp, Call,
    Ident, IntLit, FloatLit, StrLit, BoolLit, Index, Attr, TestDef, AssertStmt, AssignStmt, ListExpr)
from prelude import prelude_lines
from baltypes import ctype_of, infer_expr_type

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
        self.in_test = False
        self.in_global = False
        self.global_init = []
        self.global_names = set()

    def emit(self, code):
        self.lines.append("    " * self.indent + code)

    def gen(self, node):
        """Generate C for a Program: prelude, structs, decls, globals, funcs, tests."""
        if not isinstance(node, Program):
            return ""
        self._collect_top_level(node)
        self.lines[0:0] = prelude_lines()
        self._gen_structs()
        self._gen_prototypes()
        self._gen_globals_init()
        for f in self.functions:
            self.gen_func(f)
        if self.tests:
            self._gen_tests()
        return "\n".join(self.lines)

    def _collect_top_level(self, node):
        """Sort top-level statements into structs/functions/externs/tests/globals."""
        for stmt in node.stmts:
            if isinstance(stmt, StructDef):
                self.structs.append(stmt)
            elif isinstance(stmt, FuncDef):
                self.func_returns[stmt.name] = stmt.ret_type
                (self.externs if stmt.body == [] else self.functions).append(stmt)
            elif isinstance(stmt, TestDef):
                self.tests.append(stmt)
            else:
                self.indent = 0
                self.in_global = True
                if isinstance(stmt, LetStmt):
                    self.global_names.add(stmt.name)
                    stmt.mutable = True
                self.gen_stmt(stmt)
                self.in_global = False
                self.indent = 0

    def _gen_structs(self):
        for s in self.structs:
            self.gen_struct(s)
        self.lines.append("")

    def _gen_prototypes(self):
        for f in self.functions:
            self.gen_func_decl(f)
        self.lines.append("")
        for e in self.externs:
            self.gen_extern(e)

    def _gen_globals_init(self):
        if not self.global_init:
            return
        self.lines.append("static void bal_init_globals(void) {")
        self.indent += 1
        for g in self.global_init:
            self.emit(g + ";")
        self.indent -= 1
        self.lines.append("}")
        self.lines.append("")

    def _gen_tests(self):
        """Emit test functions + bal_run_tests + main wrapper."""
        for i, t in enumerate(self.tests):
            self.lines.append("")
            self.lines.append(f"static int bal_test_{i}(void) {{")
            self.indent += 1
            self.declared_vars = set()
            self.array_vars = set()
            self.struct_vars = {}
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
        # Reset per-function scope. Keep only global arrays visible (they're declared at file scope).
        global_arrays = {n for n in self.array_vars if n in self.global_names}
        self.declared_vars = set(self.global_names)
        self.array_vars = global_arrays  # FIX: was persisting local arrays between functions
        self.struct_vars = {}
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
            if isinstance(s.expr, ListExpr):
                self.array_vars.add(name)
                self.emit(f"int* _{name}_data;")
                self.emit(f"BalArray {name};")
                continue
            ctype = ctype_of(s.type) if s.type else self.infer_type(s.expr)
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
        """Dispatch statement generation to type-specific methods."""
        handlers = {
            LetStmt: self._gen_let,
            ReturnStmt: self._gen_return,
            IfStmt: self._gen_if,
            WhileStmt: self._gen_while,
            ForStmt: self._gen_for,
            PrintStmt: self._gen_print,
            ExprStmt: self._gen_expr_stmt,
            AssignStmt: self._gen_assign,
            AssertStmt: self._gen_assert,
        }
        handler = handlers.get(type(stmt))
        if handler:
            handler(stmt)

    def _gen_let(self, stmt):
        """Generate a let/variable declaration."""
        if isinstance(stmt.expr, ListExpr):
            self._gen_array_let(stmt)
            return

        nullable = stmt.type is not None and stmt.type.endswith("?")
        ctype = ctype_of(stmt.type[:-1] if nullable else stmt.type) if stmt.type else self.infer_type(stmt.expr)
        init = self.gen_expr(stmt.expr)
        if init == "None":
            init = "0" if ctype in ("int", "double", "float") else "NULL"
        if stmt.name in self.declared_vars:
            self.emit(f"{stmt.name} = {init};")
            return
        self.declared_vars.add(stmt.name)
        if isinstance(stmt.expr, Call) and isinstance(stmt.expr.func, Ident) and stmt.expr.func.name in [s.name for s in self.structs]:
            struct_name = stmt.expr.func.name
            self.struct_vars[stmt.name] = struct_name
            self.emit(f"{struct_name} {stmt.name} = {init};")
        elif stmt.mutable or ctype == "Arena":
            self.emit(f"{ctype} {stmt.name} = {init};")
        else:
            self.emit(f"const {ctype} {stmt.name} = {init};")

    def _gen_array_let(self, stmt):
        """Generate an array literal declaration. Handles global, hoisted, and local cases."""
        elems = stmt.expr.elems
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
        elif arr_name in self.declared_vars:
            self.emit(f"_{arr_name}_data = malloc({len(elems)} * sizeof(int));")
            for i, e in enumerate(elems):
                self.emit(f"_{arr_name}_data[{i}] = {self.gen_expr(e)};")
            self.emit(f"{arr_name} = bal_array_new(_{arr_name}_data, {len(elems)});")
        else:
            self.emit(f"int* _{arr_name}_data = malloc({len(elems)} * sizeof(int));")
            for i, e in enumerate(elems):
                self.emit(f"_{arr_name}_data[{i}] = {self.gen_expr(e)};")
            self.emit(f"BalArray {arr_name} = bal_array_new(_{arr_name}_data, {len(elems)});")

    def _gen_return(self, stmt):
        self.emit(f"return {self.gen_expr(stmt.expr)};" if stmt.expr else "return;")

    def _gen_if(self, stmt):
        self.emit(f"if ({self.gen_expr(stmt.cond)}) {{")
        self._gen_block(stmt.body)
        for elif_cond, elif_body in (stmt.elifs or []):
            self.emit(f"}} else if ({self.gen_expr(elif_cond)}) {{")
            self._gen_block(elif_body)
        if stmt.else_body:
            self.emit("} else {")
            self._gen_block(stmt.else_body)
        self.emit("}")

    def _gen_while(self, stmt):
        self.emit(f"while ({self.gen_expr(stmt.cond)}) {{")
        self._gen_block(stmt.body)
        self.emit("}")

    def _gen_for(self, stmt):
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
            self._gen_block(stmt.body)
            self.emit("}")
        else:
            self.emit(f"/* for {stmt.var} in ... */")

    def _gen_print(self, stmt):
        expr = self.gen_expr(stmt.expr)
        t = self.infer_type(stmt.expr)
        fmt = {"const char*": "%s", "double": "%f"}.get(t, "%d")
        self.emit(f'printf("{fmt}\\n", {expr});')

    def _gen_expr_stmt(self, stmt):
        self.emit(f"{self.gen_expr(stmt.expr)};")

    def _gen_assign(self, stmt):
        tgt = self.gen_expr(stmt.target)
        val = self.gen_expr(stmt.expr)
        if isinstance(stmt.target.obj, Ident) and stmt.target.obj.name in self.array_vars:
            self.emit(f"{stmt.target.obj.name}.data[{self.gen_expr(stmt.target.idx)}] = {val};")
        else:
            self.emit(f"{tgt} = {val};")

    def _gen_assert(self, stmt):
        macro = "bal_tassert" if self.in_test else "bal_assert"
        self.emit(f"{macro}({self.gen_expr(stmt.expr)});")

    def _gen_block(self, stmts):
        """Generate a block of statements with indent."""
        self.indent += 1
        for s in stmts:
            self.gen_stmt(s)
        self.indent -= 1

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
        if isinstance(expr, ListExpr):
            return "/* list */"
        return "0"

    def infer_type(self, expr):
        """Delegate to types.infer_expr_type with current codegen context."""
        return infer_expr_type(expr, array_vars=self.array_vars,
                               struct_vars=self.struct_vars,
                               structs=self.structs,
                               func_returns=self.func_returns)


def emit_c(source):
    """Transpile bal source to C code. Returns the C source as a string."""
    ast = parse(source)
    codegen = CodeGen()
    codegen.gen(ast)
    return "\n".join(codegen.lines)


def compile_to_binary(c_code, keep_c=False):
    """Compile C code to a binary. Returns exe_path, or None on failure.
    Cleans up the temporary .c file unless keep_c=True."""
    with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as f:
        f.write(c_code)
        c_path = f.name

    exe_path = c_path[:-2]  # strip ".c"
    result = subprocess.run(
        ["gcc", "-O2", "-o", exe_path, c_path],
        capture_output=True, text=True
    )
    if not keep_c:
        os.unlink(c_path)
    if result.returncode != 0:
        print("C compilation failed:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None
    return exe_path


def compile_bal(source, output_path=None):
    """Full pipeline: bal source -> C -> binary.
    With output_path: writes C to that path, returns C code.
    Without: returns (exe_path, c_code) or None on failure."""
    c_code = emit_c(source)
    if output_path:
        with open(output_path, "w") as f:
            f.write(c_code)
        return c_code
    exe_path = compile_to_binary(c_code)
    if exe_path is None:
        return None
    return exe_path, c_code


def main():
    if len(sys.argv) < 2:
        print("Usage: bal <file.bal> [--emit-c]")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        source = f.read()
    emit_c_only = "--emit-c" in sys.argv

    if emit_c_only:
        print(emit_c(source))
        return

    result = compile_bal(source)
    if result is None:
        sys.exit(1)

    exe_path, _c_code = result
    run = subprocess.run([exe_path] + sys.argv[2:], capture_output=False)
    os.unlink(exe_path)
    sys.exit(run.returncode)


if __name__ == "__main__":
    main()
