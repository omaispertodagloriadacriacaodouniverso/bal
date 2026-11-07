


fn is_alpha(c: int) -> bool:
    return (c >= 97 and c <= 122) or (c >= 65 and c <= 90) or c == 95

fn is_digit(c: int) -> bool:
    return c >= 48 and c <= 57



var T = [0]
var S = [0]
var E = [0]
var L = [0]
var src = ""
var pos = 0

fn tok_type(k: int) -> int:
    return T[k]

fn tok_text(k: int) -> str:
    return str_slice(src, S[k], E[k])

fn peek_k(k: int) -> int:
    if k < len(T):
        return k
    return len(T) - 1

fn advance() -> int:
    var k = pos
    pos = pos + 1
    return k

fn lex():
    var i = 0
    var line = 1
    var n = len(src)
    var indent = 0
    while i < n:
        var c = char_at(src, i)
        if c == 10:
            append(T, 6)
            append(S, i)
            append(E, i + 1)
            append(L, line)
            line = line + 1
            i = i + 1
        else:
            if c == 32 or c == 9 or c == 13:
                i = i + 1
            else:
                if c == 35:
                    while i < n and char_at(src, i) != 10:
                        i = i + 1
                else:
                    if is_alpha(c):
                        var s = i
                        while i < n and is_alpha(char_at(src, i)):
                            i = i + 1
                        while i < n and is_digit(char_at(src, i)):
                            i = i + 1
                        append(T, 1)
                        append(S, s)
                        append(E, i)
                        append(L, line)
                    else:
                        if is_digit(c):
                            var s2 = i
                            while i < n and is_digit(char_at(src, i)):
                                i = i + 1
                            append(T, 2)
                            append(S, s2)
                            append(E, i)
                            append(L, line)
                        else:
                            if c == 34:
                                var s3 = i
                                i = i + 1
                                while i < n and char_at(src, i) != 34:
                                    i = i + 1
                                i = i + 1
                                append(T, 4)
                                append(S, s3)
                                append(E, i)
                                append(L, line)
                            else:
                                append(T, 5)
                                append(S, i)
                                append(E, i + 1)
                                append(L, line)
                                i = i + 1
    append(T, 9)
    append(S, n)
    append(E, n)
    append(L, line)

fn skip_newlines():
    while tok_type(peek_k(pos)) == 6:
        pos = pos + 1


fn parse_expr() -> str:
    return parse_or()

fn parse_or() -> str:
    var left = parse_and()
    while str_eq(tok_text(peek_k(pos)), "or"):
        pos = pos + 1
        var right = parse_and()
        left = "(or " + left + " " + right + ")"
    return left

fn parse_and() -> str:
    var left = parse_cmp()
    while str_eq(tok_text(peek_k(pos)), "and"):
        pos = pos + 1
        var right = parse_cmp()
        left = "(and " + left + " " + right + ")"
    return left

fn parse_cmp() -> str:
    var left = parse_add()
    var t = tok_text(peek_k(pos))
    while str_eq(t, "==") or str_eq(t, "!=") or str_eq(t, "<") or str_eq(t, ">") or str_eq(t, "<=") or str_eq(t, ">="):
        pos = pos + 1
        var right = parse_add()
        left = "(" + t + " " + left + " " + right + ")"
        t = tok_text(peek_k(pos))
    return left

fn parse_add() -> str:
    var left = parse_mul()
    var t = tok_text(peek_k(pos))
    while str_eq(t, "+") or str_eq(t, "-"):
        pos = pos + 1
        var right = parse_mul()
        left = "(" + t + " " + left + " " + right + ")"
        t = tok_text(peek_k(pos))
    return left

fn parse_mul() -> str:
    var left = parse_unary()
    var t = tok_text(peek_k(pos))
    while str_eq(t, "*") or str_eq(t, "/") or str_eq(t, "%"):
        pos = pos + 1
        var right = parse_unary()
        left = "(" + t + " " + left + " " + right + ")"
        t = tok_text(peek_k(pos))
    return left

fn parse_unary() -> str:
    var t = tok_text(peek_k(pos))
    if str_eq(t, "-"):
        pos = pos + 1
        return "(- " + parse_unary() + ")"
    if str_eq(t, "not"):
        pos = pos + 1
        return "(not " + parse_unary() + ")"
    return parse_postfix()

fn parse_postfix() -> str:
    var expr = parse_primary()
    while tok_type(peek_k(pos)) == 5 or str_eq(tok_text(peek_k(pos)), "("):
        var t = tok_text(peek_k(pos))
        if str_eq(t, "("):
            pos = pos + 1
            var args = ""
            while pos < len(T) and tok_type(peek_k(pos)) != 6 and not str_eq(tok_text(peek_k(pos)), ")"):
                args = args + " " + parse_expr()
                if str_eq(tok_text(peek_k(pos)), ", "):
                    pos = pos + 1
            pos = pos + 1
            expr = "(call " + expr + args + ")"
        else:
            if str_eq(t, "["):
                pos = pos + 1
                var idx = parse_expr()
                pos = pos + 1
                expr = "(index " + expr + " " + idx + ")"
            else:
                if str_eq(t, "."):
                    pos = pos + 1
                    var f = tok_text(peek_k(pos))
                    pos = pos + 1
                    expr = "(attr " + expr + " " + f + ")"
                else:
                    pos = pos + 1
    return expr

fn parse_primary() -> str:
    var k = peek_k(pos)
    var t = tok_type(k)
    if t == 2:
        pos = pos + 1
        return tok_text(k)
    if t == 4:
        pos = pos + 1
        return "\"" + tok_text(k) + "\""
    if t == 1:
        pos = pos + 1
        var w = tok_text(k)
        if str_eq(w, "true"):
            return "true"
        if str_eq(w, "false"):
            return "false"
        if str_eq(w, "None"):
            return "None"
        return w
    if str_eq(tok_text(k), "("):
        pos = pos + 1
        var e = parse_expr()
        pos = pos + 1
        return e
    if str_eq(tok_text(k), "["):
        pos = pos + 1
        var elems = ""
        while pos < len(T) and tok_type(peek_k(pos)) != 6 and not str_eq(tok_text(peek_k(pos)), "]"):
            elems = elems + " " + parse_expr()
            if str_eq(tok_text(peek_k(pos)), ", "):
                pos = pos + 1
        pos = pos + 1
        return "(array" + elems + ")"
    return "?"

fn parse_block(depth: int) -> str:
    var out = ""
    skip_newlines()
    while pos < len(T):
        var k = peek_k(pos)
        if tok_type(k) == 9:
            return out
        if tok_type(k) == 6:
            pos = pos + 1
            continue
        var w = tok_text(k)
        if str_eq(w, "fn"):
            pos = pos + 1
            var name = tok_text(peek_k(pos))
            pos = pos + 1
            pos = pos + 1
            while pos < len(T) and tok_type(peek_k(pos)) != 6 and not str_eq(tok_text(peek_k(pos)), ")"):
                pos = pos + 1
            pos = pos + 1
            if str_eq(tok_text(peek_k(pos)), "->"):
                pos = pos + 1
                pos = pos + 1
            skip_newlines()
            out = out + "(fn " + name + parse_block(depth + 1) + ")"
            continue
        if str_eq(w, "let") or str_eq(w, "var"):
            pos = pos + 1
            var name = tok_text(peek_k(pos))
            pos = pos + 1
            if str_eq(tok_text(peek_k(pos)), ":"):
                pos = pos + 2
            pos = pos + 1
            var e = parse_expr()
            out = out + "(" + w + " " + name + " " + e + ")"
            continue
        if str_eq(w, "if"):
            pos = pos + 1
            var cond = parse_expr()
            pos = pos + 1
            skip_newlines()
            out = out + "(if " + cond + parse_block(depth + 1) + ")"
            continue
        if str_eq(w, "while"):
            pos = pos + 1
            var cond = parse_expr()
            pos = pos + 1
            skip_newlines()
            out = out + "(while " + cond + parse_block(depth + 1) + ")"
            continue
        if str_eq(w, "return"):
            pos = pos + 1
            out = out + "(return " + parse_expr() + ")"
            continue
        if str_eq(w, "print"):
            pos = pos + 1
            out = out + "(print " + parse_expr() + ")"
            continue
        if str_eq(w, "assert"):
            pos = pos + 1
            out = out + "(assert " + parse_expr() + ")"
            continue
        if str_eq(w, "test"):
            pos = pos + 1
            var name = tok_text(peek_k(pos))
            pos = pos + 1
            pos = pos + 1
            skip_newlines()
            out = out + "(test " + name + parse_block(depth + 1) + ")"
            continue

        var before = pos
        var e = parse_expr()
        if pos == before:
            pos = pos + 1  # never stall on an unexpected token
            continue
        if str_eq(tok_text(peek_k(pos)), "="):
            pos = pos + 1
            out = out + "(assign " + e + " " + parse_expr() + ")"
        else:
            out = out + "(expr " + e + ")"
    return out

fn main():
    src = read_file("examples/factorial.bal")
    lex()
    print(parse_block(0))
    return 0
