fn greet(name: str) -> str:
    return "Hello, " + name

fn main():
    print(greet("world"))
    var total = 0
    for i in range(100):
        total = total + i
    print(total)
    if 42 % 2 == 0:
        print("42 is even")
    return 0
