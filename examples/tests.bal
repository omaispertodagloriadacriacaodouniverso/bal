fn add(a: int, b: int) -> int:
    return a + b

test "addition works":
    assert(add(2, 3) == 5)
    assert(add(- 1, 1) == 0)

test "strings concat":
    let s = "foo" + "bar"
    assert(str_len(s) == 6)

fn main():
    print(add(40, 2))
    return 0
