fn main():
    let s = "  Hello, World!  "
    print(str_trim(s))
    print(str_find(s, "World"))
    print(str_contains(s, "Hello"))
    print(str_count(s, "l"))
    print(str_slice(s, 2, 7))
    print(str_len(s))
    return 0
