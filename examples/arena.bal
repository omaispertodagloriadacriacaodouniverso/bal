fn main():
    let a: Arena = Arena.new(1024)
    let p = a.alloc(16)
    assert(p != None)
    a.free()
    print(42)
    return 0
