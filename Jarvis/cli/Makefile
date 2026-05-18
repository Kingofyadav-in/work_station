CC      = gcc
CFLAGS  = -Wall -Wextra -std=c11 -O2 -Iinclude
LDFLAGS = -lcurl
SRCS    = src/jarvis.c src/core.c src/output.c src/config.c src/json.c src/state.c src/api.c src/projects.c src/watch.c src/daemon.c
OBJS    = $(SRCS:.c=.o)
TARGET  = jarvis
INSTALL  = $(HOME)/bin
MAN1DIR  = $(HOME)/share/man/man1

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
	@mkdir -p $(MAN1DIR)
	cp man/jarvis.1 $(MAN1DIR)/jarvis.1
	@echo "  installed  ->  $(INSTALL)/jarvis"
	@echo "  man page   ->  $(MAN1DIR)/jarvis.1"

uninstall:
	rm -f $(INSTALL)/jarvis
	rm -f $(MAN1DIR)/jarvis.1
	@echo "  removed  ->  $(INSTALL)/jarvis"

clean:
	rm -f $(OBJS) $(TARGET)
