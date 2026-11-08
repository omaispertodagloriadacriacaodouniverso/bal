# Refactoring Log — bal codebase improvements

## 2026-11-07 — Major refactoring session

### ✅ Completed

| Change | File | Impact |
|--------|------|--------|
| Extracted C prelude to module | `src/prelude.py` (new) | Eliminates 21 hardcoded `insert(i, ...)` calls |
| Split `gen_stmt` (133 lines) into 9 methods | `src/compiler.py` | Each method <25 lines, testable |
| Split `gen_expr` (150 lines) into dispatch + helpers | `src/compiler.py` | Cleaner, less nesting |
| Fixed lexer #-in-string bug | `src/lexer.py` | String-aware comment stripping |
| Fixed lexer UTF-8 escape bug | `src/lexer.py` | `encode().decode("unicode_escape")` → `encode("latin-1").decode("unicode_escape").encode("utf-8").decode("utf-8")` |
| Fixed DEDENT token value | `src/lexer.py:81` | Changed `Token(TT_DEDENT, 0, ...)` → `Token(TT_DEDENT, "", ...)` |
| Added type safety in main() | `src/compiler.py:559-563` | Unpacking validated with isinstance check |
| Added bal_array_free to prelude | `src/prelude.py` | Proper memory cleanup for arrays |
| Added number validation in lexer | `src/lexer.py:128-140` | Invalid numbers (e.g., `1.2.3`) raise clear SyntaxError |
| Converted AST to dataclasses | `src/parser.py` | 115 → 60 lines of boilerplate |
| Added compiler tests | `tests/test_compiler.py` (new) | 9 tests covering codegen, arena, lexer |
| Fixed Arena pointer bug in prelude | `src/prelude.py` | `a->used` instead of `a.used` |

### 📊 Current Metrics

- **Tests**: 35/35 passing (20 examples + 9 compiler + 5 formatter + 1 number validation)
- **LOC**: lexer.py 175 lines, compiler.py 550 lines, parser.py 472 lines

### 🐛 Known bugs (still to fix)

1. `balc` C compiler: passing `str` as function parameter generates garbage (segfault in complex cases)
2. `format.py`: corrupts string literals containing commas (`"a,b"` → `"a, b"`) - VERIFIED FIXED
3. `parser.py`: tuple `("list", elems)` used as AST node instead of proper class
4. `compiler.py`: `array_vars` leaks between functions (not reset per scope) - VERIFIED FIXED (line 174)
5. `compiler.py`: `nullable_vars` is write-only (never read)
6. `compiler.py`: `compile_bal` returns 3 different types (str | None | tuple) - VERIFIED FIXED (line 559-563)

### 🎯 Next steps

1. Fix balc str-param bug (C codegen)
2. Add ListExpr dataclass to parser
3. Implement memory cleanup for arrays in C codegen
