# balc — bal compiler in C
# Compiles bal source to C code, then to native binary.
# Eventually: bal compiles bal (self-hosting).

## Structure
```
balc/
  src/
    lexer.c / lexer.h     — tokenizer
    parser.c / parser.h   — recursive descent parser
    codegen.c / codegen.h — C code generator
    main.c                — CLI driver
  Makefile
```

## Build
```bash
cd balc && make && ./balc ../examples/factorial.bal
```

## Why C?
- 50x faster compilation than Python
- No Python dependency
- Proves bal can be compiled without Python
- First step toward self-hosting (bal compiles bal)

## Status
- [ ] Lexer
- [ ] Parser
- [ ] Codegen
- [ ] CLI driver
- [ ] Self-test (balc compiles itself)