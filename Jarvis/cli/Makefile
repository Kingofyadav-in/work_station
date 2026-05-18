CC      = gcc
CFLAGS  = -Wall -Wextra -std=c11 -O2 -Iinclude
LDFLAGS = -lcurl
SRCS    = src/jarvis.c src/core.c src/output.c src/config.c src/json.c src/state.c src/api.c
OBJS    = $(SRCS:.c=.o)
TARGET  = jarvis
INSTALL = $(HOME)/bin

.PHONY: all clean install uninstall

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)
	@echo ""
	@echo "  built  ->  ./$(TARGET)"
	@echo ""

src/%.o: src/%.c include/jarvis.h
	$(CC) $(CFLAGS) -c -o $@ $<

install: $(TARGET)
	@mkdir -p $(INSTALL)
	cp $(TARGET) $(INSTALL)/jarvis
	@echo "  installed  ->  $(INSTALL)/jarvis"

uninstall:
	rm -f $(INSTALL)/jarvis
	@echo "  removed  ->  $(INSTALL)/jarvis"

clean:
	rm -f $(OBJS) $(TARGET)
