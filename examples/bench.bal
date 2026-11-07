fn sum_squares(n: int) -> int:
    var total = 0
    var i = 0
    while i < n:
        total = total + i * i
        i = i + 1
    return total

fn main():
    print(sum_squares(10000000))
    return 0
