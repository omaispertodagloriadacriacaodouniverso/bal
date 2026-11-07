fn main():
    let nums = [3, 1, 4, 1, 5]
    var r: int? = None
    for x in nums:
        if x == 4:
            r = Some(x)
    if is_none(r):
        print(0)
    else:
        print(unwrap(r))
    return 0
