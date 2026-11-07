fn is_prime(n: int) -> bool:
    if n < 2:
        return false
    var i = 2
    while i * i <= n:
        if n % i == 0:
            return false
        i = i + 1
    return true

fn main():
    var count = 0
    var n = 2
    while n < 1000000:
        if is_prime(n):
            count = count + 1
        n = n + 1
    print(count)
    return 0
