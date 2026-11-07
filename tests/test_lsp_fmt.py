#!/usr/bin/env python3
"""Smoke tests for bal formatter and LSP server (stdlib only)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from format import format_source  # noqa: E402


def test_formatter_idempotent():
    for f in sorted((ROOT / "examples").glob("*.bal")):
        src = f.read_text()
        once = format_source(src)
        twice = format_source(once)
        assert once == twice, f"not idempotent: {f.name}"
    print("formatter idempotent on all examples: OK")


def test_formatter_normalizes():
    src = "fn main():\n        let x=1+2\n        print(x)\n"
    out = format_source(src)
    assert "    let x = 1 + 2" in out, out
    print("formatter normalizes spacing/indent: OK")


def _msg(m):
    body = json.dumps(m).encode()
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def _read(stream):
    headers = {}
    while True:
        line = stream.readline()
        if not line or line.strip() == b"":
            break
        k, _, v = line.decode().partition(":")
        headers[k.strip().lower()] = v.strip()
    return json.loads(stream.read(int(headers["content-length"])))


def test_lsp():
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "src" / "lsp.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        proc.stdin.write(_msg({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                               "params": {}}))
        proc.stdin.flush()
        resp = _read(proc.stdout)
        assert resp["result"]["capabilities"]["documentFormattingProvider"]

        bad = "fn main():\n    let x = \n"
        proc.stdin.write(_msg({"jsonrpc": "2.0", "method": "textDocument/didOpen",
                               "params": {"textDocument": {"uri": "file:///t.bal",
                                                           "text": bad}}}))
        proc.stdin.flush()
        diag = _read(proc.stdout)
        assert diag["method"] == "textDocument/publishDiagnostics"
        assert len(diag["params"]["diagnostics"]) >= 1, diag

        proc.stdin.write(_msg({"jsonrpc": "2.0", "id": 2,
                               "method": "textDocument/formatting",
                               "params": {"textDocument": {"uri": "file:///t.bal"}}}))
        proc.stdin.flush()
        fmt = _read(proc.stdout)
        assert fmt["result"][0]["newText"], fmt

        proc.stdin.write(_msg({"jsonrpc": "2.0", "id": 3, "method": "shutdown"}))
        proc.stdin.flush()
        _read(proc.stdout)
        proc.stdin.write(_msg({"jsonrpc": "2.0", "method": "exit"}))
        proc.stdin.flush()
    finally:
        proc.kill()
    print("lsp initialize/diagnostics/formatting: OK")


if __name__ == "__main__":
    test_formatter_idempotent()
    test_formatter_normalizes()
    test_lsp()
    print("all lsp/fmt tests passed")
