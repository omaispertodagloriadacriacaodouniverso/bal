fn main():
    let data = [10, 20, 30, 40, 50]
    var total = 0
    var i = 0
    while i < len(data):
        total = total + data[i]
        i = i + 1
        print(total)
        print(len(data))

        append(data, 60)
        print(len(data))
        print(data[5])
        return 0
