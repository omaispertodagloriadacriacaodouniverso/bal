#!/usr/bin/env python3
"""Minimal LSP server for bal — stdlib only, JSON-RPC over stdio.

Supports: initialize, shutdown, exit, textDocument/didOpen, didChange,
textDocument/formatting, textDocument/publishDiagnostics (parse errors).
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lexer import tokenize
from parser import Parser
from format import format_source


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
    return json.loads(sys.stdin.buffer.read(length))


def send(msg):
    body = json.dumps(msg).encode()
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    sys.stdout.buffer.flush()


def diagnose(source):
    """Parse source and return LSP diagnostics for any syntax errors."""
    try:
        Parser(tokenize(source)).parse()
        return []
    except SyntaxError as e:
        m = re.search(r"line (\d+)", str(e))
        ln = int(m.group(1)) - 1 if m else 0
        return [{"range": {"start": {"line": ln, "character": 0},
                            "end": {"line": ln, "character": 1}},
                  "severity": 1, "source": "bal", "message": str(e)}]
    except Exception as e:
        return [{"range": {"start": {"line": 0, "character": 0},
                            "end": {"line": 0, "character": 1}},
                  "severity": 1, "source": "bal", "message": str(e)}]


docs = {}


def _publish_diagnostics(uri):
    send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
          "params": {"uri": uri, "diagnostics": diagnose(docs[uri])}})


def handle_initialize(msg):
    send({"jsonrpc": "2.0", "id": msg.get("id"), "result": {
        "capabilities": {
            "textDocumentSync": {"openClose": True, "change": 1},
            "documentFormattingProvider": True,
        },
        "serverInfo": {"name": "bal-lsp", "version": "0.1"},
    }})


def handle_did_open(msg):
    uri = msg["params"]["textDocument"]["uri"]
    docs[uri] = msg["params"]["textDocument"]["text"]
    _publish_diagnostics(uri)


def handle_did_change(msg):
    uri = msg["params"]["textDocument"]["uri"]
    docs[uri] = msg["params"]["contentChanges"][0]["text"]
    _publish_diagnostics(uri)


def handle_formatting(msg):
    uri = msg["params"]["textDocument"]["uri"]
    text = docs.get(uri, "")
    send({"jsonrpc": "2.0", "id": msg.get("id"), "result": [{
        "range": {"start": {"line": 0, "character": 0},
                  "end": {"line": len(text.split("\n")), "character": 0}},
        "newText": format_source(text),
    }]})


HANDLERS = {
    "initialize": handle_initialize,
    "shutdown": lambda m: send({"jsonrpc": "2.0", "id": m.get("id"), "result": None}),
    "exit": lambda m: sys.exit(0),
    "textDocument/didOpen": handle_did_open,
    "textDocument/didChange": handle_did_change,
    "textDocument/formatting": handle_formatting,
}


def main():
    while True:
        msg = read_message()
        if msg is None:
            return 0
        handler = HANDLERS.get(msg.get("method", ""))
        if handler:
            handler(msg)
        elif msg.get("id") is not None:
            send({"jsonrpc": "2.0", "id": msg["id"], "result": None})


if __name__ == "__main__":
    sys.exit(main())
