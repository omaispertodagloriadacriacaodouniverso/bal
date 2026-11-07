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
            # Strip inline comments
            if "#" in line:
                line = line[:line.index("#")]
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

    def _tokenize_line(self, text, line_num, base_col):
        i = 0
        while i < len(text):
            if text[i].isspace():
                i += 1
                continue

            if text[i] in ('"', "'"):
                quote = text[i]
                j = i + 1
                while j < len(text) and text[j] != quote:
                    if text[j] == "\\" and j + 1 < len(text):
                        j += 2
                    else:
                        j += 1
                raw = text[i + 1:j]
                # Process escape sequences
                val = raw.encode().decode("unicode_escape")
                self.tokens.append(Token(TT_STR, val, line_num, base_col + i))
                i = j + 1
                continue

            if text[i].isdigit() or (text[i] == "." and i + 1 < len(text) and text[i + 1].isdigit()):
                j = i
                is_float = False
                while j < len(text) and (text[j].isdigit() or text[j] == "."):
                    if text[j] == ".":
                        is_float = True
                    j += 1
                val = text[i:j]
                if is_float:
                    self.tokens.append(Token(TT_FLOAT, float(val), line_num, base_col + i))
                else:
                    self.tokens.append(Token(TT_INT, int(val), line_num, base_col + i))
                i = j
                continue

            if text[i:i + 2] == "->":
                self.tokens.append(Token(TT_ARROW, "->", line_num, base_col + i))
                i += 2
                continue

            if text[i] in "+-*/%<>!=":
                if i + 1 < len(text) and text[i + 1] == "=":
                    self.tokens.append(Token(TT_OP, text[i:i + 2], line_num, base_col + i))
                    i += 2
                else:
                    self.tokens.append(Token(TT_OP, text[i], line_num, base_col + i))
                    i += 1
                continue

            if text[i] == ":":
                self.tokens.append(Token(TT_COLON, ":", line_num, base_col + i))
                i += 1
                continue

            if text[i] == ",":
                self.tokens.append(Token(TT_COMMA, ",", line_num, base_col + i))
                i += 1
                continue

            if text[i] == ".":
                self.tokens.append(Token(TT_DOT, ".", line_num, base_col + i))
                i += 1
                continue

            if text[i] == "?":
                self.tokens.append(Token(TT_QUESTION, "?", line_num, base_col + i))
                i += 1
                continue

            if text[i] == "(":
                self.tokens.append(Token(TT_LPAREN, "(", line_num, base_col + i))
                i += 1
                continue
            if text[i] == ")":
                self.tokens.append(Token(TT_RPAREN, ")", line_num, base_col + i))
                i += 1
                continue

            if text[i] == "[":
                self.tokens.append(Token(TT_LBRACKET, "[", line_num, base_col + i))
                i += 1
                continue
            if text[i] == "]":
                self.tokens.append(Token(TT_RBRACKET, "]", line_num, base_col + i))
                i += 1
                continue

            if text[i].isalpha() or text[i] == "_":
                j = i
                while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                word = text[i:j]
                if word in KEYWORDS:
                    self.tokens.append(Token(TT_KEYWORD, word, line_num, base_col + i))
                else:
                    self.tokens.append(Token(TT_IDENT, word, line_num, base_col + i))
                i = j
                continue

            raise SyntaxError(f"Unknown character {text[i]!r} at line {line_num}")


def tokenize(source):
    return Lexer(source).tokenize()
