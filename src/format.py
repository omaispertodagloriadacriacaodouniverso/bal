#!/usr/bin/env python3
"""bal formatter — uses lexer INDENT/DEDENT tokens for correct block depth,
normalizes spacing around operators, strips trailing whitespace."""

import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from lexer import tokenize, TT_INDENT, TT_DEDENT, TT_NEWLINE  # noqa: E402

# longest first so '->' isn't split into '- >'
BINOPS = ["==", "!=", "<=", ">=", "->", "+", "-", "*", "/", "%", "<", ">", "="]


def line_depths(source):
    """Map 1-based line number -> indent depth, from raw leading whitespace.
    (Lexer INDENT/DEDENT tokens are unreliable across multi-level dedents.)"""
    depths = {}
    for ln, raw in enumerate(source.split("\n"), start=1):
        stripped = raw.lstrip(" ")
        if not stripped:
            continue
        lead = len(raw) - len(stripped)
        depths[ln] = lead // 4
    return depths


def _split_code_comment(line):
    in_str = None
    for i, ch in enumerate(line):
        if in_str:
            if ch == in_str:
                in_str = None
        elif ch in ('"', "'"):
            in_str = ch
        elif ch == "#":
            return line[:i], line[i:]
    return line, ""


def format_line(code):
    if not code:
        return ""
    # spaces around binary ops (outside strings)
    out = []
    in_str = None
    i = 0
    while i < len(code):
        ch = code[i]
        if in_str:
            out.append(ch)
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = ch
            out.append(ch)
            i += 1
            continue
        matched = False
        for op in BINOPS:
            if code.startswith(op, i):
                out.append(f" {op} ")
                i += len(op)
                matched = True
                break
        if matched:
            continue
        out.append(ch)
        i += 1
    code = "".join(out)
    # collapse runs of spaces outside strings; keep one space between tokens
    res = []
    in_str = None
    for ch in code:
        if in_str:
            res.append(ch)
            if ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
            res.append(ch)
            continue
        if ch == " ":
            if res and res[-1] not in (" ", "("):
                res.append(" ")
            continue
        res.append(ch)
    code = "".join(res)
    # space after comma — string-aware (don't touch commas inside string literals)
    code = _space_after_comma(code)
    code = code.replace("( ", "(").replace(" )", ")")
    return code.rstrip()


def _space_after_comma(code: str) -> str:
    """Add space after commas, but only outside string literals."""
    out = []
    in_str = None
    i = 0
    while i < len(code):
        ch = code[i]
        if in_str:
            out.append(ch)
            if ch == "\\":
                if i + 1 < len(code):
                    out.append(code[i + 1])
                    i += 2
                    continue
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = ch
            out.append(ch)
            i += 1
            continue
        if ch == "," and i + 1 < len(code) and code[i + 1] != " ":
            out.append(", ")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def format_source(source):
    depths = line_depths(source)
    out = []
    for ln, raw in enumerate(source.split("\n"), start=1):
        code, comment = _split_code_comment(raw)
        stripped = code.strip()
        if not stripped:
            out.append("")
            continue
        indent = "    " * depths.get(ln, 0)
        formatted = format_line(stripped)
        if comment.strip():
            formatted += "  " + comment.strip()
        out.append(indent + formatted)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out) + "\n"


def main():
    if len(sys.argv) < 2:
        print("Usage: bal fmt <file.bal> [--check]", file=sys.stderr)
        return 1
    path = sys.argv[1]
    check = "--check" in sys.argv
    with open(path) as f:
        src = f.read()
    formatted = format_source(src)
    if check:
        if formatted != src:
            print(f"{path}: not formatted", file=sys.stderr)
            return 1
        return 0
    if formatted != src:
        with open(path, "w") as f:
            f.write(formatted)
        print(f"formatted {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
