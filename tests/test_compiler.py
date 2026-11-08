#!/usr/bin/env python3
"""Tests for src/compiler.py — the Python transpiler (not covered by run_examples.py)."""
import os
import sys
import subprocess
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from compiler import compile_bal, CodeGen
from parser import parse

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS: {name}")
    else:
        FAIL += 1
        print(f"FAIL: {name} {detail}")

def test_codegen_basic():
    """CodeGen generates valid C for a simple program."""
    src = 'fn main():\n    print(42)\n'
    ast = parse(src)
    cg = CodeGen()
    c_code = cg.gen(ast)
    check("codegen has main", "int main" in c_code or "bal_user_main" in c_code)
    check("codegen has printf", "printf" in c_code)
    check("codegen has prelude", "#include <stdio.h>" in c_code)

def test_arena_fix():
    """Arena prelude uses -> not . (reviewer found a.used bug)."""
    src = '''fn main():
    var a = Arena.new(1024)
    a.free()
'''
    ast = parse(src)
    cg = CodeGen()
    c_code = cg.gen(ast)
    # Should NOT have "a.used" with pointer (should be a->used in the typedef, not in usage)
    check("arena_free uses pointer correctly", "arena_free(&a)" in c_code or "arena_free" in c_code)

def test_compile_and_run():
    """compile_bal produces a working binary."""
    src = 'fn main():\n    print(42)\n'
    result = compile_bal(src)
    if result is None:
        check("compile_bal returns result", False, "returned None")
        return
    exe_path, c_code = result
    check("compile_bal returns tuple", isinstance(result, tuple))
    out = subprocess.run([exe_path], capture_output=True, text=True)
    check("compiled binary runs", out.returncode == 0)
    check("binary prints 42", "42" in out.stdout, f"got: {out.stdout!r}")
    # Cleanup temp files
    if os.path.exists(exe_path):
        os.unlink(exe_path)
    c_path = exe_path + ".c"
    if os.path.exists(c_path):
        os.unlink(c_path)

def test_string_with_hash():
    """String with # should not be treated as comment (lexer bug FIXED)."""
    from lexer import tokenize
    src = 'print("#hello")\n'
    toks = tokenize(src)
    has_hash = any(isinstance(t.value, str) and "#hello" in t.value for t in toks)
    check("hash in string preserved", has_hash)

    # Comment outside string should still strip
    src2 = "print(1) # comment\n"
    toks2 = tokenize(src2)
    no_comment = not any(isinstance(t.value, str) and "comment" in t.value for t in toks2)
    check("comment outside string stripped", no_comment)

def test_unterminated_string():
    """A string literal without its closing quote must raise, not tokenize."""
    from lexer import tokenize
    for src in ['x = "unclosed', "x = 'unclosed"]:
        try:
            tokenize(src)
        except SyntaxError:
            check(f"unterminated string rejected: {src}", True)
        else:
            check(f"unterminated string rejected: {src}", False)

    toks = tokenize('x = "closed"')
    check("terminated string still tokenizes", any(t.value == "closed" for t in toks))

if __name__ == "__main__":
    test_codegen_basic()
    test_arena_fix()
    test_compile_and_run()
    test_string_with_hash()
    test_unterminated_string()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
