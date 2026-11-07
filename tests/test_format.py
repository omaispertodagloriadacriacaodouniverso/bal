#!/usr/bin/env python3
"""Tests for src/format.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from format import format_line, format_source

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

def test_comma_in_string_preserved():
    """Commas inside string literals must NOT get spaces added."""
    out = format_line('print("a,b,c")')
    check("comma in string preserved", '"a,b,c"' in out, f"got: {out!r}")

def test_comma_outside_string():
    """Commas outside strings should get a space after."""
    out = format_line("f(1,2,3)")
    check("comma outside string spaced", "1, 2, 3" in out, f"got: {out!r}")

def test_operators_spaced():
    out = format_line("x=1+2")
    check("operators spaced", "x = 1 + 2" in out, f"got: {out!r}")

def test_string_with_operator():
    """Operators inside strings should not be spaced."""
    out = format_line('print("a+b")')
    check("operator in string preserved", '"a+b"' in out, f"got: {out!r}")

def test_format_source_indent():
    src = "fn main():\n    print(1)\n"
    out = format_source(src)
    check("indent preserved", "    print(1)" in out, f"got: {out!r}")

if __name__ == "__main__":
    test_comma_in_string_preserved()
    test_comma_outside_string()
    test_operators_spaced()
    test_string_with_operator()
    test_format_source_indent()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
