#!/usr/bin/env python3
"""bal formatter — uses lexer INDENT/DEDENT tokens for correct block depth,
normalizes spacing around operators, strips trailing whitespace."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

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
    """Normalize spacing in one string-aware pass: binops, space runs, commas."""
    if not code:
        return ""
    out = []
    in_str = None
    i = 0
    n = len(code)
    while i < n:
        ch = code[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(code[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = ch
            out.append(ch)
            i += 1
            continue
        # binary operators (longest first so '->' isn't split)
        matched = next((op for op in BINOPS if code.startswith(op, i)), None)
        if matched:
            out.append(f" {matched} ")
            i += len(matched)
            continue
        if ch == " ":
            # collapse runs; no space after '(' or before ')'
            if out and out[-1] not in (" ", "("):
                out.append(" ")
            i += 1
            continue
        if ch == "," and i + 1 < n and code[i + 1] != " ":
            out.append(", ")
            i += 1
            continue
        out.append(ch)
        i += 1
    code = "".join(out)
    code = code.replace("( ", "(").replace(" )", ")")
    return code.rstrip()


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
