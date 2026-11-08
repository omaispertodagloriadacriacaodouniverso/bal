"""Type inference and builtin tables for the bal compiler.

Single source of truth for: C type mapping, builtin return types, and
expression type inference — shared by codegen and any other consumer.
"""

from parser import (BinOp, BoolLit, Call, FloatLit, Ident, IntLit, StrLit,
                    Attr, Index)

TYPE_MAP = {
    "int": "int",
    "float": "double",
    "bool": "int",
    "str": "const char*",
    "void": "void",
    "Arena": "Arena",
}


def ctype_of(t):
    """Map a bal type annotation to its C type."""
    if t is None:
        return "int"
    if t.endswith("?"):
        t = t[:-1]
    return TYPE_MAP.get(t, t)


# Builtin function name -> C return type
BUILTIN_RETURN_TYPES = {
    "len": "int",
    "read_file": "const char*",
    "get_arg": "const char*",
    "append": "int",
    "str_find": "int",
    "str_len": "int",
    "str_contains": "int",
    "str_count": "int",
    "is_none": "int",
    "unwrap": "int",
    "char_at": "int",
    "str_slice": "const char*",
    "str_trim": "const char*",
    "str_concat": "const char*",
    "str_eq": "int",
    "write_file": "int",
    "num_args": "int",
    "print": "int",
    "str": "const char*",
    "range": "int",
    "Some": "int",
}


def infer_expr_type(expr, *, array_vars=frozenset(), struct_vars=None,
                    structs=None, func_returns=None):
    """Infer the C type of an expression.

    Keyword-only context params avoid coupling to CodeGen internals.
    """
    struct_vars = struct_vars or {}
    structs = structs or []
    func_returns = func_returns or {}

    if isinstance(expr, IntLit):
        return "int"
    if isinstance(expr, FloatLit):
        return "double"
    if isinstance(expr, StrLit):
        return "const char*"
    if isinstance(expr, BoolLit):
        return "int"
    if isinstance(expr, BinOp):
        if expr.op in ("+", "-", "*", "/", "%"):
            lt = infer_expr_type(expr.left, array_vars=array_vars,
                                 struct_vars=struct_vars, structs=structs,
                                 func_returns=func_returns)
            rt = infer_expr_type(expr.right, array_vars=array_vars,
                                 struct_vars=struct_vars, structs=structs,
                                 func_returns=func_returns)
            if lt == "const char*" or rt == "const char*":
                return "const char*"
            if lt == "double" or rt == "double":
                return "double"
            return "int"
        return "int"
    if isinstance(expr, Call):
        if isinstance(expr.func, Attr):
            if (isinstance(expr.func.obj, Ident)
                    and expr.func.obj.name == "Arena"
                    and expr.func.field == "new"):
                return "Arena"
            if expr.func.field == "alloc":
                return "void*"
            if expr.func.field == "free":
                return "int"
        if isinstance(expr.func, Ident):
            name = expr.func.name
            if name in BUILTIN_RETURN_TYPES:
                return BUILTIN_RETURN_TYPES[name]
            if name in [s.name for s in structs]:
                return name
            if name in func_returns:
                rt = func_returns[name]
                if rt.endswith("?"):
                    rt = rt[:-1]
                return ctype_of(rt)
    if isinstance(expr, Ident):
        if expr.name in array_vars:
            return "BalArray"
        if expr.name in struct_vars:
            return struct_vars[expr.name]
    if isinstance(expr, Attr):
        if isinstance(expr.obj, Ident) and expr.obj.name in struct_vars:
            struct_name = struct_vars[expr.obj.name]
            struct_def = next((s for s in structs if s.name == struct_name), None)
            if struct_def:
                for fname, ftype in struct_def.fields:
                    if fname == expr.field:
                        return ctype_of(ftype)
    return "int"
