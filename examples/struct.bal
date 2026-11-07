struct Point:
    x: float
    y: float

fn distance(p1: Point, p2: Point) -> float:
    var dx = p2.x - p1.x
    var dy = p2.y - p1.y
    return dx * dx + dy * dy

fn main():
    let p1 = Point(1.0, 2.0)
    let p2 = Point(4.0, 6.0)
    print(distance(p1, p2))
    return 0
