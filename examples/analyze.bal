fn main():
    if num_args() < 2:
        print("Usage: bal analyze.bal <file>")
        return 1
    let path = get_arg(1)
    let text = read_file(path)
    print(len(text))
    return 0
