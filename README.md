# bal — Python syntax, C speed

A minimal compiled language. Write Python, get C performance.

## Quick start

```bash
# Compile and run
python3 src/compiler.py examples/factorial.bal

# Emit C code
python3 src/compiler.py examples/factorial.bal --emit-c
```

## Language

```python
fn factorial(n: int) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)

fn main():
    var i = 0
    while i < 10:
        print(factorial(i))
        i = i + 1
```

### Types
- `int`, `float`, `bool`, `str`, `void`
- Type inference when possible

### Control flow
- `if` / `elif` / `else`
- `while` loops
- `for x in range(n)` loops

### Functions
- `fn name(params) -> type:`
- Recursion supported
- `extern fn` for C interop

### Variables
- `let` (immutable) / `var` (mutable)

### Operators
- Arithmetic: `+`, `-`, `*`, `/`, `%`
- Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Logical: `and`, `or`, `not`

### Builtins
- `print(x)` — auto-detects type
- `len(str)` — string length
- `str(x)` — convert to string
- `range(n)` — for loops

## Performance

| benchmark | bal (C) | Python | speedup |
|---|---|---|---|
| sum_squares(10M) | 0.068s | 0.507s | **7.5x** |
| fib(35) | ~0.08s | 1.04s | **~13x** |

## Architecture

```
bal source → lexer → parser → AST → C codegen → gcc → native binary
```

- No GC (manual memory)
- No runtime (just libc)
- Single-pass compilation
- Incremental (planned)

## Files

```
src/
  lexer.py      — tokenizer (indentation-based)
  parser.py     — recursive descent parser
  compiler.py   — codegen + gcc driver
examples/
  factorial.bal
  fib.bal
  hello.bal
  bench.bal
```

## Roadmap

- [x] Basic types and operators
- [x] Functions and recursion
- [x] Control flow (if/while/for)
- [x] String concatenation
- [ ] Structs and field access
- [ ] Arrays/lists
- [ ] Arena memory allocator
- [ ] Null safety (Option type)
- [ ] C FFI (extern fn calls)
- [ ] Incremental compilation
- [ ] LSP / formatter
- [ ] Package manager

## Why "bal"?

**bal** = **balance**. The sweet spot between Python's ergonomics and C's speed.
Not the fastest (that's C/Zig). Not the safest (that's Rust). Not the easiest (that's Python).
But the **most balanced** — good enough at everything, optimized for nothing, usable for everything.