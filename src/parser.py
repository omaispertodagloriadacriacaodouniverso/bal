#!/usr/bin/env python3
"""bal parser — converts token stream to AST."""

import sys
import os
from dataclasses import dataclass, field
from typing import Optional

# Import lexer
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from lexer import tokenize, TT_EOF, TT_INDENT, TT_DEDENT, TT_NEWLINE, TT_INT, TT_FLOAT, TT_STR, TT_IDENT, TT_KEYWORD, TT_OP, TT_COLON, TT_COMMA, TT_DOT, TT_QUESTION, TT_LPAREN, TT_RPAREN, TT_LBRACKET, TT_RBRACKET, TT_ARROW

# ── AST Nodes (dataclasses — much less boilerplate than manual __init__) ──

@dataclass
class Program:
    stmts: list

@dataclass
class FuncDef:
    name: str
    params: list  # [(name, type)]
    ret_type: str
    body: list

@dataclass
class Param:
    name: str
    type: str

@dataclass
class StructDef:
    name: str
    fields: list  # [(name, type)]

@dataclass
class LetStmt:
    name: str
    type: Optional[str]
    expr: object
    mutable: bool = False

@dataclass
class ReturnStmt:
    expr: Optional[object]

@dataclass
class IfStmt:
    cond: object
    body: list
    elifs: list = field(default_factory=list)
    else_body: Optional[list] = None

@dataclass
class WhileStmt:
    cond: object
    body: list

@dataclass
class ForStmt:
    var: str
    iterable: object
    body: list

@dataclass
class ExprStmt:
    expr: object

@dataclass
class PrintStmt:
    expr: object

@dataclass
class BinOp:
    left: object
    op: str
    right: object

@dataclass
class UnaryOp:
    op: str
    expr: object

@dataclass
class Call:
    func: object
    args: list

@dataclass
class Ident:
    name: str

@dataclass
class IntLit:
    value: int

@dataclass
class FloatLit:
    value: float

@dataclass
class StrLit:
    value: str

@dataclass
class BoolLit:
    value: bool

@dataclass
class Index:
    obj: object
    idx: object

@dataclass
class Attr:
    obj: object
    field: str

@dataclass
class TestDef:
    name: str
    body: list

@dataclass
class AssertStmt:
    expr: object

@dataclass
class AssignStmt:
    target: object
    expr: object

@dataclass
class ListExpr:
    elems: list

# ── Binary operator precedence (lowest to highest) ──

BINARY_LEVELS = [
    ("or",),
    ("and",),
    ("==", "!=", "<", ">", "<=", ">="),
    ("+", "-"),
    ("*", "/", "%"),
]

# ── Parser ──

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, type_, value=None):
        tok = self.peek()
        if tok.type != type_ or (value is not None and tok.value != value):
            raise SyntaxError(f"Expected {type_} {value}, got {tok} at line {tok.line}")
        return self.advance()

    def skip_newlines(self):
        while self.peek().type == TT_NEWLINE:
            self.advance()

    def parse(self):
        stmts = []
        self.skip_newlines()
        while self.peek().type != TT_EOF:
            stmt = self.parse_stmt()
            if stmt:
                stmts.append(stmt)
            self.skip_newlines()
        return Program(stmts)

    def parse_stmt(self):
        tok = self.peek()
        if tok.type == TT_KEYWORD:
            if tok.value == "fn":
                return self.parse_func()
            if tok.value == "struct":
                return self.parse_struct()
            if tok.value == "let":
                return self.parse_let(mutable=False)
            if tok.value == "var":
                return self.parse_let(mutable=True)
            if tok.value == "if":
                return self.parse_if()
            if tok.value == "while":
                return self.parse_while()
            if tok.value == "for":
                return self.parse_for()
            if tok.value == "return":
                self.advance()
                expr = self.parse_expr() if self.peek().type != TT_NEWLINE else None
                return ReturnStmt(expr)
            if tok.value == "print":
                self.advance()
                expr = self.parse_expr()
                return PrintStmt(expr)
            if tok.value == "extern":
                return self.parse_extern()
            if tok.value == "test":
                return self.parse_test()
            if tok.value == "assert":
                self.advance()
                return AssertStmt(self.parse_expr())
        if tok.type == TT_IDENT:
            # Could be assignment: x = expr
            if self.peek(1).type == TT_OP and self.peek(1).value == "=":
                name = self.advance().value
                self.expect(TT_OP, "=")
                expr = self.parse_expr()
                return LetStmt(name, None, expr, mutable=True)
            expr = self.parse_expr()
            if isinstance(expr, Index) and self.peek().type == TT_OP and self.peek().value == "=":
                self.advance()
                return AssignStmt(expr, self.parse_expr())
            return ExprStmt(expr)
        # Skip INDENT/DEDENT
        if tok.type in (TT_INDENT, TT_DEDENT):
            self.advance()
            return None
        raise SyntaxError(f"Unexpected token {tok} at line {tok.line}")

    def _parse_signature(self):
        """Parse (params) -> ret_type. Shared by parse_func and parse_extern."""
        self.expect(TT_LPAREN)
        params = []
        while self.peek().type != TT_RPAREN:
            pname = self.expect(TT_IDENT).value
            self.expect(TT_COLON)
            params.append(Param(pname, self.parse_type()))
            if self.peek().type == TT_COMMA:
                self.advance()
        self.expect(TT_RPAREN)
        ret_type = "void"
        if self.peek().type == TT_ARROW:
            self.advance()
            ret_type = self.parse_type()
        return params, ret_type

    def _parse_block_after_colon(self):
        """Parse `: <newline> INDENT block`. Used by fn/if/elif/else/while/for/test/struct."""
        self.expect(TT_COLON)
        self.skip_newlines()
        self.expect(TT_INDENT)
        return self.parse_block()

    def parse_func(self):
        self.expect(TT_KEYWORD, "fn")
        name = self.expect(TT_IDENT).value
        params, ret_type = self._parse_signature()
        body = self._parse_block_after_colon()
        return FuncDef(name, params, ret_type, body)

    def parse_struct(self):
        self.expect(TT_KEYWORD, "struct")
        name = self.expect(TT_IDENT).value
        self.expect(TT_COLON)
        self.skip_newlines()
        self.expect(TT_INDENT)
        fields = []
        while self.peek().type not in (TT_DEDENT, TT_EOF):
            self.skip_newlines()
            if self.peek().type == TT_DEDENT:
                break
            fname = self.expect(TT_IDENT).value
            self.expect(TT_COLON)
            fields.append((fname, self.parse_type()))
            self.skip_newlines()
        if self.peek().type == TT_DEDENT:
            self.advance()
        return StructDef(name, fields)

    def parse_let(self, mutable=False):
        kw = self.advance()  # let or var
        mutable = (kw.value == "var")
        name = self.expect(TT_IDENT).value
        type_ = None
        if self.peek().type == TT_COLON:
            self.advance()
            type_ = self.parse_type()
        self.expect(TT_OP, "=")
        expr = self.parse_expr()
        return LetStmt(name, type_, expr, mutable)

    def parse_if(self):
        self.expect(TT_KEYWORD, "if")
        cond = self.parse_expr()
        body = self._parse_block_after_colon()
        elifs = []
        else_body = None
        while self.peek().type == TT_KEYWORD and self.peek().value in ("elif", "else"):
            if self.peek().value == "elif":
                self.advance()
                elif_cond = self.parse_expr()
                elif_body = self._parse_block_after_colon()
                elifs.append((elif_cond, elif_body))
            else:
                self.advance()
                else_body = self._parse_block_after_colon()
                break
        return IfStmt(cond, body, elifs, else_body)

    def parse_while(self):
        self.expect(TT_KEYWORD, "while")
        cond = self.parse_expr()
        body = self._parse_block_after_colon()
        return WhileStmt(cond, body)

    def parse_for(self):
        self.expect(TT_KEYWORD, "for")
        var = self.expect(TT_IDENT).value
        self.expect(TT_KEYWORD, "in")
        iterable = self.parse_expr()
        body = self._parse_block_after_colon()
        return ForStmt(var, iterable, body)

    def parse_test(self):
        self.expect(TT_KEYWORD, "test")
        name = self.expect(TT_STR).value
        body = self._parse_block_after_colon()
        return TestDef(name, body)

    def parse_extern(self):
        self.expect(TT_KEYWORD, "extern")
        self.expect(TT_KEYWORD, "fn")
        name = self.expect(TT_IDENT).value
        params, ret_type = self._parse_signature()
        return FuncDef(name, params, ret_type, [])

    def parse_type(self):
        tok = self.peek()
        base = None
        if tok.type == TT_KEYWORD and tok.value in ("int", "float", "bool", "str", "void"):
            self.advance()
            base = tok.value
        elif tok.type == TT_IDENT:
            self.advance()
            base = tok.value
        elif tok.type == TT_LBRACKET:
            self.advance()
            inner = self.parse_type()
            self.expect(TT_RBRACKET)
            base = f"[{inner}]"
        else:
            raise SyntaxError(f"Expected type, got {tok}")
        # Nullable suffix: int?, str?, etc.
        if self.peek().type == TT_QUESTION:
            self.advance()
            return base + "?"
        return base

    def parse_block(self):
        stmts = []
        while self.peek().type not in (TT_DEDENT, TT_EOF):
            self.skip_newlines()
            if self.peek().type in (TT_DEDENT, TT_EOF):
                break
            stmt = self.parse_stmt()
            if stmt:
                stmts.append(stmt)
            self.skip_newlines()
        if self.peek().type == TT_DEDENT:
            self.advance()
        return stmts

    def parse_expr(self):
        return self._parse_binary(0)

    # Precedence levels, lowest to highest. Keyword ops checked via TT_KEYWORD,
    # symbol ops via TT_OP.

    def _parse_binary(self, level):
        if level >= len(BINARY_LEVELS):
            return self._parse_unary_level()
        ops = BINARY_LEVELS[level]
        left = self._parse_binary(level + 1)
        while self._peek_op(ops):
            op = self.advance().value
            left = BinOp(left, op, self._parse_binary(level + 1))
        return left

    def _peek_op(self, ops):
        tok = self.peek()
        if tok.value in ops:
            return tok.type == TT_KEYWORD or tok.type == TT_OP
        return False

    def _parse_unary_level(self):
        if self.peek().type == TT_KEYWORD and self.peek().value == "not":
            self.advance()
            return UnaryOp("not", self._parse_unary_level())
        if self.peek().type == TT_OP and self.peek().value in ("-", "+"):
            op = self.advance().value
            return UnaryOp(op, self._parse_unary_level())
        return self.parse_postfix()

    def parse_postfix(self):
        expr = self.parse_primary()
        while True:
            if self.peek().type == TT_LPAREN:
                self.advance()
                args = []
                while self.peek().type != TT_RPAREN:
                    args.append(self.parse_expr())
                    if self.peek().type == TT_COMMA:
                        self.advance()
                self.expect(TT_RPAREN)
                expr = Call(expr, args)
            elif self.peek().type == TT_LBRACKET:
                self.advance()
                idx = self.parse_expr()
                self.expect(TT_RBRACKET)
                expr = Index(expr, idx)
            elif self.peek().type == TT_DOT:
                self.advance()
                field = self.expect(TT_IDENT).value
                expr = Attr(expr, field)
            else:
                break
        return expr

    def parse_primary(self):
        tok = self.peek()
        if tok.type == TT_INT:
            self.advance()
            return IntLit(tok.value)
        if tok.type == TT_FLOAT:
            self.advance()
            return FloatLit(tok.value)
        if tok.type == TT_STR:
            self.advance()
            return StrLit(tok.value)
        if tok.type == TT_KEYWORD and tok.value in ("true", "false"):
            self.advance()
            return BoolLit(tok.value == "true")
        if tok.type == TT_KEYWORD and tok.value == "None":
            self.advance()
            return Ident("NULL")
        if tok.type == TT_IDENT:
            self.advance()
            return Ident(tok.value)
        if tok.type == TT_LPAREN:
            self.advance()
            expr = self.parse_expr()
            self.expect(TT_RPAREN)
            return expr
        if tok.type == TT_LBRACKET:
            self.advance()
            elems = []
            while self.peek().type != TT_RBRACKET:
                elems.append(self.parse_expr())
                if self.peek().type == TT_COMMA:
                    self.advance()
            self.expect(TT_RBRACKET)
            return ListExpr(elems)
        raise SyntaxError(f"Unexpected token {tok} at line {tok.line}")

def parse(source):
    tokens = tokenize(source)
    return Parser(tokens).parse()
