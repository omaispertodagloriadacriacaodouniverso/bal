# Real Sieve of Eratosthenes — O(n log log n)
fn main():
    let n = 1000000
    var is_comp = [0]
    var i = 0
    while i < n:
        append(is_comp, 0)
        i = i + 1
    var count = 0
    var p = 2
    while p < n:
        if is_comp.data[p] == 0:
            count = count + 1
            if p < 46341 and p * p < n:
                var m = p * p
                while m < n:
                    is_comp.data[m] = 1
                    m = m + p
        p = p + 1
    print(count)
    return 0
