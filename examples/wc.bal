


fn count_lines(text: str) -> int:
    var count = 0
    var i = 0
    while i < len(text):
        if text[i] == "\n":
            count = count + 1
        i = i + 1
    return count

fn count_words(text: str) -> int:
    var count = 0
    var in_word = false
    var i = 0
    while i < len(text):
        if text[i] == " " or text[i] == "\n" or text[i] == "\t":
            if in_word:
                count = count + 1
                in_word = false
        else:
            in_word = true
        i = i + 1
    if in_word:
        count = count + 1
    return count

fn main():
    let text = read_file("examples/hello.bal")
    print(count_lines(text))
    print(count_words(text))
    print(len(text))
    return 0
