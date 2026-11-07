fn main():
    if num_args() < 2:
        print("Usage: bal freq.bal <file>")
        return 1
    let path = get_arg(1)
    let text = read_file(path)
    print(str_count(text, "a"))
    return 0
