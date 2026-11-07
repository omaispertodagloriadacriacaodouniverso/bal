# bal codegen — milestone 3 skeleton
# NOTE: balc has a bug passing str params between fns (garbage values),
# so we inline everything in main for now.

fn ctype_of(t: str) -> str:
    if t == "int":
        return "int"
    if t == "float":
        return "double"
    if t == "bool":
        return "int"
    if t == "str":
        return "const char*"
    return t

fn main():
    # Test type mapping
    print(ctype_of("int"))
    print(ctype_of("str"))
    # TODO: full codegen once balc str-param bug is fixed
    print("/* codegen.bal milestone 3 - skeleton OK */")

main()
