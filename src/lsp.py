#!/usr/bin/env python3
"""Minimal LSP server for bal — stdlib only, JSON-RPC over stdio.

Supports: initialize, shutdown, exit, textDocument/didOpen, didChange,
textDocument/formatting, textDocument/publishDiagnostics (parse errors).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lexer import tokenize  # noqa: E402
from parser import Parser  # noqa: E402
from format import format_source  # noqa: E402


def read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        k, _, v = line.decode().partition(":")
        headers[k.strip().lower()] = v.strip()
    length = int(headers.get("content-length", 0))
    body = sys.stdin.buffer.read(length)
    return json.loads(body)


def send(msg):
    body = json.dumps(msg).encode()
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    sys.stdout.buffer.flush()


def diagnose(source):
    diags = []
    try:
        tokens = tokenize(source)
        Parser(tokens).parse()
    except SyntaxError as e:
        line = getattr(e, "args", [""])[0]
        import re
        m = re.search(r"line (\d+)", str(e))
        ln = int(m.group(1)) - 1 if m else 0
        diags.append({
            "range": {"start": {"line": ln, "character": 0},
                      "end": {"line": ln, "character": 1}},
            "severity": 1,
            "source": "bal",
            "message": str(e),
        })
    except Exception as e:
        diags.append({
            "range": {"start": {"line": 0, "character": 0},
                      "end": {"line": 0, "character": 1}},
            "severity": 1,
            "source": "bal",
            "message": str(e),
        })
    return diags


docs = {}


def main():
    while True:
        msg = read_message()
        if msg is None:
            return 0
        method = msg.get("method", "")
        mid = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "capabilities": {
                    "textDocumentSync": {"openClose": True, "change": 1},
                    "documentFormattingProvider": True,
                },
                "serverInfo": {"name": "bal-lsp", "version": "0.1"},
            }})
        elif method == "shutdown":
            send({"jsonrpc": "2.0", "id": mid, "result": None})
        elif method == "exit":
            return 0
        elif method == "textDocument/didOpen":
            uri = params["textDocument"]["uri"]
            docs[uri] = params["textDocument"]["text"]
            send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                  "params": {"uri": uri, "diagnostics": diagnose(docs[uri])}})
        elif method == "textDocument/didChange":
            uri = params["textDocument"]["uri"]
            docs[uri] = params["contentChanges"][0]["text"]
            send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
                  "params": {"uri": uri, "diagnostics": diagnose(docs[uri])}})
        elif method == "textDocument/formatting":
            uri = params["textDocument"]["uri"]
            text = docs.get(uri, "")
            formatted = format_source(text)
            send({"jsonrpc": "2.0", "id": mid, "result": [{
                "range": {"start": {"line": 0, "character": 0},
                          "end": {"line": len(text.split("\n")), "character": 0}},
                "newText": formatted,
            }]})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "result": None})


if __name__ == "__main__":
    sys.exit(main())
