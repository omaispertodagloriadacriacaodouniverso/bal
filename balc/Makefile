CC = gcc
CFLAGS = -O2 -Wall -Wextra
TARGET = balc

all: $(TARGET)

$(TARGET): lexer.c parser.c codegen.c
	$(CC) $(CFLAGS) -o $(TARGET) lexer.c parser.c codegen.c

clean:
	rm -f $(TARGET)

test: $(TARGET)
	./$(TARGET) ../examples/factorial.bal 2>&1 | head -20