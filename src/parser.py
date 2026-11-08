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

    def parse_func(self):
        self.expect(TT_KEYWORD, "fn")
        name = self.expect(TT_IDENT).value
        self.expect(TT_LPAREN)
        params = []
        while self.peek().type != TT_RPAREN:
            pname = self.expect(TT_IDENT).value
            self.expect(TT_COLON)
            ptype = self.parse_type()
            params.append(Param(pname, ptype))
            if self.peek().type == TT_COMMA:
                self.advance()
        self.expect(TT_RPAREN)
        ret_type = "void"
        if self.peek().type == TT_ARROW:
            self.advance()
            ret_type = self.parse_type()
        self.expect(TT_COLON)
        self.skip_newlines()
        self.expect(TT_INDENT)
        body = self.parse_block()
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
            ftype = self.parse_type()
            fields.append((fname, ftype))
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
        self.expect(TT_COLON)
        self.skip_newlines()
        self.expect(TT_INDENT)
        body = self.parse_block()
        elifs = []
        else_body = None
        # Handle elif/else
        while self.peek().type == TT_KEYWORD and self.peek().value in ("elif", "else"):
            if self.peek().value == "elif":
                self.advance()
                elif_cond = self.parse_expr()
                self.expect(TT_COLON)
                self.skip_newlines()
                self.expect(TT_INDENT)
                elif_body = self.parse_block()
                elifs.append((elif_cond, elif_body))
            else:
                self.advance()
                self.expect(TT_COLON)
                self.skip_newlines()
                self.expect(TT_INDENT)
                else_body = self.parse_block()
                break
        return IfStmt(cond, body, elifs, else_body)

    def parse_while(self):
        self.expect(TT_KEYWORD, "while")
        cond = self.parse_expr()
        self.expect(TT_COLON)
        self.skip_newlines()
        self.expect(TT_INDENT)
        body = self.parse_block()
        return WhileStmt(cond, body)

    def parse_for(self):
        self.expect(TT_KEYWORD, "for")
        var = self.expect(TT_IDENT).value
        self.expect(TT_KEYWORD, "in")
        iterable = self.parse_expr()
        self.expect(TT_COLON)
        self.skip_newlines()
        self.expect(TT_INDENT)
        body = self.parse_block()
        return ForStmt(var, iterable, body)

    def parse_test(self):
        self.expect(TT_KEYWORD, "test")
        name = self.expect(TT_STR).value
        self.expect(TT_COLON)
        self.skip_newlines()
        self.expect(TT_INDENT)
        body = self.parse_block()
        return TestDef(name, body)

    def parse_extern(self):
        self.expect(TT_KEYWORD, "extern")
        self.expect(TT_KEYWORD, "fn")
        name = self.expect(TT_IDENT).value
        self.expect(TT_LPAREN)
        params = []
        while self.peek().type != TT_RPAREN:
            pname = self.expect(TT_IDENT).value
            self.expect(TT_COLON)
            ptype = self.parse_type()
            params.append(Param(pname, ptype))
            if self.peek().type == TT_COMMA:
                self.advance()
        self.expect(TT_RPAREN)
        ret_type = "void"
        if self.peek().type == TT_ARROW:
            self.advance()
            ret_type = self.parse_type()
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
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.peek().type == TT_KEYWORD and self.peek().value == "or":
            self.advance()
            right = self.parse_and()
            left = BinOp(left, "or", right)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.peek().type == TT_KEYWORD and self.peek().value == "and":
            self.advance()
            right = self.parse_not()
            left = BinOp(left, "and", right)
        return left

    def parse_not(self):
        if self.peek().type == TT_KEYWORD and self.peek().value == "not":
            self.advance()
            return UnaryOp("not", self.parse_not())
        return self.parse_cmp()

    def parse_cmp(self):
        left = self.parse_add()
        while self.peek().type == TT_OP and self.peek().value in ("==", "!=", "<", ">", "<=", ">="):
            op = self.advance().value
            right = self.parse_add()
            left = BinOp(left, op, right)
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.peek().type == TT_OP and self.peek().value in ("+", "-"):
            op = self.advance().value
            right = self.parse_mul()
            left = BinOp(left, op, right)
        return left

    def parse_mul(self):
        left = self.parse_unary()
        while self.peek().type == TT_OP and self.peek().value in ("*", "/", "%"):
            op = self.advance().value
            right = self.parse_unary()
            left = BinOp(left, op, right)
        return left

    def parse_unary(self):
        if self.peek().type == TT_OP and self.peek().value in ("-", "+"):
            op = self.advance().value
            return UnaryOp(op, self.parse_unary())
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
