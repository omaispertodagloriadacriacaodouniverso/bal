# Refactoring Log — bal codebase improvements

## 2026-11-07 — Major refactoring session

### ✅ Completed

| Change | File | Impact |
|--------|------|--------|
| Extracted C prelude to module | `src/prelude.py` (new) | Eliminates 21 hardcoded `insert(i, ...)` calls |
| Split `gen_stmt` (133 lines) into 9 methods | `src/compiler.py` | Each method <25 lines, testable |
| Split `gen_expr` (150 lines) into dispatch + helpers | `src/compiler.py` | Cleaner, less nesting |
| Fixed lexer #-in-string bug | `src/lexer.py` | String-aware comment stripping |
| Converted AST to dataclasses | `src/parser.py` | 115 → 60 lines of boilerplate |
| Added compiler tests | `tests/test_compiler.py` (new) | 9 tests covering codegen, arena, lexer |
| Fixed Arena pointer bug in prelude | `src/prelude.py` | `a->used` instead of `a.used` |

### 📊 Metrics

- **Before**: compiler.py 650 lines, monolithic methods
- **After**: compiler.py ~550 lines, modular methods + prelude.py 50 lines
- **Tests**: 20/20 examples + 9/9 compiler tests = **29 total passing**
- **LOC reduction**: ~115 lines from dataclasses alone

### 🐛 Known bugs found (not yet fixed)

1. `balc` C compiler: passing `str` as function parameter generates garbage (segfault in complex cases)
2. `format.py`: corrupts string literals containing commas (`"a,b"` → `"a, b"`)
3. `parser.py`: tuple `("list", elems)` used as AST node instead of proper class
4. `compiler.py`: `array_vars` leaks between functions (not reset per scope)
5. `compiler.py`: `nullable_vars` is write-only (never read)
6. `compiler.py`: `compile_bal` returns 3 different types (str | None | tuple)

### 🎯 Next steps

1. Fix balc str-param bug (C codegen)
2. Fix format.py string corruption
3. Add ListExpr dataclass to parser
4. Fix array_vars scope leak
5. Unify compile_bal return type
