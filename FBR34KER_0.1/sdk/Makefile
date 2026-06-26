CC ?= clang
AR ?= llvm-ar
BUILD_DIR ?= build
TARGET ?= aarch64-none-elf
CFLAGS ?= --target=$(TARGET) -std=c11 -O2 -ffreestanding -fno-builtin \
	-Wall -Wextra -Werror -Iinclude
HOST_CC ?= cc
HOST_CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror -Iinclude

SOURCES := src/handoff_builder.c src/handoff_validate.c src/profile_match.c
OBJECTS := $(patsubst src/%.c,$(BUILD_DIR)/%.o,$(SOURCES))
LIBRARY := $(BUILD_DIR)/libfbr34ker_sdk.a
EXAMPLES := minimal_loader callback_console framebuffer_loader

.PHONY: all test examples clean
all: $(LIBRARY)

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/%.o: src/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(LIBRARY): $(OBJECTS)
	$(AR) rcs $@ $^

examples: $(addprefix $(BUILD_DIR)/,$(EXAMPLES))

$(BUILD_DIR)/%: examples/%/main.c $(SOURCES) | $(BUILD_DIR)
	$(HOST_CC) $(HOST_CFLAGS) $< $(SOURCES) -o $@

test: examples $(BUILD_DIR)/sdk_harness
	$(BUILD_DIR)/sdk_harness
	@for example in $(addprefix $(BUILD_DIR)/,$(EXAMPLES)); do $$example; done

$(BUILD_DIR)/sdk_harness: tests/sdk_harness.c $(SOURCES) | $(BUILD_DIR)
	$(HOST_CC) $(HOST_CFLAGS) $< $(SOURCES) -o $@

clean:
	rm -rf $(BUILD_DIR)
