#!/usr/bin/env python3
"""bal lexer — tokenizes bal source into a stream of tokens."""

TT_EOF = "EOF"
TT_INDENT = "INDENT"
TT_DEDENT = "DEDENT"
TT_NEWLINE = "NEWLINE"
TT_INT = "INT"
TT_FLOAT = "FLOAT"
TT_STR = "STR"
TT_IDENT = "IDENT"
TT_KEYWORD = "KEYWORD"
TT_OP = "OP"
TT_COLON = "COLON"
TT_COMMA = "COMMA"
TT_DOT = "DOT"
TT_QUESTION = "QUESTION"
TT_LPAREN = "LPAREN"
TT_RPAREN = "RPAREN"
TT_LBRACKET = "LBRACKET"
TT_RBRACKET = "RBRACKET"
TT_ARROW = "ARROW"

KEYWORDS = {
    "fn", "let", "var", "const", "if", "elif", "else", "while", "for",
    "in", "return", "struct", "match", "extern", "print", "import",
    "and", "or", "not", "true", "false", "None",    "int", "float", "bool", "str", "void",
    "test", "assert",
}

# Single-char punctuation -> token type
PUNCT = {
    ":": TT_COLON, ",": TT_COMMA, ".": TT_DOT, "?": TT_QUESTION,
    "(": TT_LPAREN, ")": TT_RPAREN, "[": TT_LBRACKET, "]": TT_RBRACKET,
}


class Token:
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, L{self.line})"


class Lexer:
    def __init__(self, source):
        self.source = source
        self.lines = source.split("\n")
        self.tokens = []
        self.indent_stack = [0]

    def tokenize(self):
        for line_num, line in enumerate(self.lines, 1):
            # Strip inline comments (string-aware: ignore # inside quotes)
            line = self._strip_comment(line)
            stripped = line.rstrip()
            if not stripped:
                self.tokens.append(Token(TT_NEWLINE, "\n", line_num, 0))
                continue
            if stripped.lstrip().startswith("#"):
                self.tokens.append(Token(TT_NEWLINE, "\n", line_num, 0))
                continue

            indent = len(line) - len(line.lstrip())
            if indent > self.indent_stack[-1]:
                self.indent_stack.append(indent)
                self.tokens.append(Token(TT_INDENT, indent, line_num, 0))
            while indent < self.indent_stack[-1]:
                self.indent_stack.pop()
                self.tokens.append(Token(TT_DEDENT, indent, line_num, 0))

            self._tokenize_line(line.lstrip(), line_num, indent)
            self.tokens.append(Token(TT_NEWLINE, "\n", line_num, 0))

        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(Token(TT_DEDENT, 0, len(self.lines), 0))

        self.tokens.append(Token(TT_EOF, None, len(self.lines), 0))
        return self.tokens

    @staticmethod
    def _strip_comment(line: str) -> str:
        """Remove inline # comments, but only outside string literals."""
        in_str = False
        quote_char = ""
        i = 0
        while i < len(line):
            c = line[i]
            if in_str:
                if c == "\\":
                    i += 2  # skip escaped char
                    continue
                if c == quote_char:
                    in_str = False
            elif c in ('"', "'"):
                in_str = True
                quote_char = c
            elif c == "#":
                return line[:i]
            i += 1
        return line

    def _tokenize_line(self, text, line_num, base_col):
        i = 0
        while i < len(text):
            ch = text[i]
            if ch.isspace():
                i += 1
                continue

            if ch in ('"', "'"):
                quote = ch
                j = i + 1
                while j < len(text) and text[j] != quote:
                    j += 2 if text[j] == "\\" and j + 1 < len(text) else 1
                raw = text[i + 1:j]
                val = raw.encode().decode("unicode_escape")
                self.tokens.append(Token(TT_STR, val, line_num, base_col + i))
                i = j + 1
                continue

            if ch.isdigit() or (ch == "." and i + 1 < len(text) and text[i + 1].isdigit()):
                j = i
                is_float = False
                while j < len(text) and (text[j].isdigit() or text[j] == "."):
                    if text[j] == ".":
                        is_float = True
                    j += 1
                val = text[i:j]
                ttype = TT_FLOAT if is_float else TT_INT
                self.tokens.append(Token(ttype, float(val) if is_float else int(val), line_num, base_col + i))
                i = j
                continue

            if text[i:i + 2] == "->":
                self.tokens.append(Token(TT_ARROW, "->", line_num, base_col + i))
                i += 2
                continue

            if ch in "+-*/%<>!=":
                if i + 1 < len(text) and text[i + 1] == "=":
                    self.tokens.append(Token(TT_OP, text[i:i + 2], line_num, base_col + i))
                    i += 2
                else:
                    self.tokens.append(Token(TT_OP, ch, line_num, base_col + i))
                    i += 1
                continue

            if ch in PUNCT:
                self.tokens.append(Token(PUNCT[ch], ch, line_num, base_col + i))
                i += 1
                continue

            if ch.isalpha() or ch == "_":
                j = i
                while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                word = text[i:j]
                ttype = TT_KEYWORD if word in KEYWORDS else TT_IDENT
                self.tokens.append(Token(ttype, word, line_num, base_col + i))
                i = j
                continue

            raise SyntaxError(f"Unknown character {ch!r} at line {line_num}")


def tokenize(source):
    return Lexer(source).tokenize()
