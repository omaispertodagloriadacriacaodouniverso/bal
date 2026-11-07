fn fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

fn main():
    for i in range(10):
        print(fib(i))
    return 0
