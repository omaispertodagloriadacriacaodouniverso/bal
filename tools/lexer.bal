



fn is_alpha(c: int) -> bool:
    return (c >= 97 and c <= 122) or (c >= 65 and c <= 90) or c == 95

fn is_digit(c: int) -> bool:
    return c >= 48 and c <= 57

fn main():
    let src = read_file("examples/factorial.bal")
    var types = [0]
    var starts = [0]
    var ends = [0]
    var lines = [0]
    var i = 0
    var line = 1
    var n = len(src)
    while i < n:
        var c = char_at(src, i)
        if c == 10:
            append(types, 6)
            append(starts, i)
            append(ends, i + 1)
            append(lines, line)
            line = line + 1
            i = i + 1
        else:
            if c == 32 or c == 9 or c == 13:
                i = i + 1
            else:
                if is_alpha(c):
                    var s = i
                    while i < n and is_alpha(char_at(src, i)):
                        i = i + 1
                    while i < n and is_digit(char_at(src, i)):
                        i = i + 1
                    append(types, 1)
                    append(starts, s)
                    append(ends, i)
                    append(lines, line)
                else:
                    if is_digit(c):
                        var s2 = i
                        while i < n and is_digit(char_at(src, i)):
                            i = i + 1
                        append(types, 2)
                        append(starts, s2)
                        append(ends, i)
                        append(lines, line)
                    else:
                        if c == 34:
                            var s3 = i
                            i = i + 1
                            while i < n and char_at(src, i) != 34:
                                i = i + 1
                            i = i + 1
                            append(types, 4)
                            append(starts, s3)
                            append(ends, i)
                            append(lines, line)
                        else:
                            append(types, 5)
                            append(starts, i)
                            append(ends, i + 1)
                            append(lines, line)
                            i = i + 1
    append(types, 99)
    append(starts, n)
    append(ends, n)
    append(lines, line)

    var k = 1
    while k < len(types):
        print(types[k])
        print(str_slice(src, starts[k], ends[k]))
        print(lines[k])
        k = k + 1
    return 0
