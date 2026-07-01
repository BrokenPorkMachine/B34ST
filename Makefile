PROJECT := fbr34ker
VERSION := 0.6.1b
RELEASE_CHANNEL := beta
RELEASE_NAME := B34ST_$(VERSION)_Beta
SOURCE_ID := $(VERSION)-beta
BUILD_DIR ?= build
SECURITY_MODEL ?= 0
EXTRA_CFLAGS += $(if $(filter 1,$(SECURITY_MODEL)),-DFBR34KER_ENABLE_SECURITY_MODEL,)
FBR34KER_PLATFORM ?= qemu_virt
ifneq ($(origin FORGE_PLATFORM), undefined)
FBR34KER_PLATFORM := $(FORGE_PLATFORM)
endif
ifneq ($(origin TARGET), command line)
TARGET := $(BUILD_DIR)/$(PROJECT)
endif
LINKER_SCRIPT := linker/$(FBR34KER_PLATFORM).ld
ifneq ($(origin MODULE_OUTPUT), command line)
MODULE_OUTPUT := $(BUILD_DIR)/modules/hello-dynamic.fmod
endif
INTEGRATION_BUILD_DIR ?= build-integration
INTEGRATION_TARGET ?= $(INTEGRATION_BUILD_DIR)/fbr34ker-test
INTEGRATION_MODULE ?= $(INTEGRATION_BUILD_DIR)/modules/hello-dynamic.fmod
RUNTIME_ARTIFACT_DIR ?= runtime-artifacts
SMOKE_DIR ?= $(RUNTIME_ARTIFACT_DIR)/smoke
DIAGNOSTICS_DIR ?= $(RUNTIME_ARTIFACT_DIR)/diagnostics
RELEASE_MANIFEST ?= RELEASE_MANIFEST.json
PACKAGE_DIR ?= dist
RELEASE_ZIP := B34ST_$(VERSION)_Beta
LOADER_SIM_DIR ?= $(BUILD_DIR)/loader-simulation
GENERIC_LOADER_BUILD_DIR ?= build-loader
GENERIC_LOADER_TARGET ?= $(GENERIC_LOADER_BUILD_DIR)/fbr34ker-qemu-loader
GENERIC_QEMU_SMOKE_DIR ?= $(RUNTIME_ARTIFACT_DIR)/generic-smoke
PROBE_QEMU_SMOKE_DIR ?= $(RUNTIME_ARTIFACT_DIR)/probe-smoke
HARDWARE_PROBE_BUILD_DIR ?= build-hardware-probe
HARDWARE_PROBE_TARGET ?= $(HARDWARE_PROBE_BUILD_DIR)/fbr34ker-hardware-probe
SDK_BUILD_DIR ?= build-sdk
SDK_LIBRARY ?= $(SDK_BUILD_DIR)/libfbr34ker_sdk.a
HANDOFF_DIR ?= build/handoff
HANDOFF_BLOB ?= $(HANDOFF_DIR)/handoff-v4.fbhb
SDK_CONFORMANCE_REPORT ?= $(HANDOFF_DIR)/sdk-conformance.json
DEPLOYMENT_SIM_DIR ?= $(BUILD_DIR)/deployment-simulation
APPLE_BOOT_DIR ?= build-apple
A12_BOOT_DIR := $(APPLE_BOOT_DIR)/a12
A12X_BOOT_DIR := $(APPLE_BOOT_DIR)/a12x
A13_BOOT_DIR := $(APPLE_BOOT_DIR)/a13
A14_BOOT_DIR := $(APPLE_BOOT_DIR)/a14
M1_BOOT_DIR  := $(APPLE_BOOT_DIR)/m1
A15_BOOT_DIR := $(APPLE_BOOT_DIR)/a15
M2_BOOT_DIR  := $(APPLE_BOOT_DIR)/m2
APPLE_BRINGUP_SIM_DIR := $(APPLE_BOOT_DIR)/bringup-simulation
PHYSICAL_INTEGRATION_SIM_DIR := $(APPLE_BOOT_DIR)/physical-integration-simulation
PHYSICAL_VALIDATION_DIR := $(APPLE_BOOT_DIR)/physical-validation-candidate

CC := clang
LD := ld.lld
OBJCOPY := $(shell if command -v llvm-objcopy >/dev/null 2>&1; then \
	command -v llvm-objcopy; \
	elif test -x /opt/homebrew/opt/llvm/bin/llvm-objcopy; then \
	echo /opt/homebrew/opt/llvm/bin/llvm-objcopy; \
	elif test -x /usr/local/opt/llvm/bin/llvm-objcopy; then \
	echo /usr/local/opt/llvm/bin/llvm-objcopy; \
	else echo llvm-objcopy; fi)
READELF := $(shell command -v llvm-readelf 2>/dev/null || command -v readelf 2>/dev/null || echo llvm-readelf)
QEMU := qemu-system-aarch64
PYTHON := python3
BUILD_JOBS ?= 4
AR := $(shell command -v llvm-ar 2>/dev/null || command -v ar 2>/dev/null || echo llvm-ar)

REPRO_FLAGS := -ffile-prefix-map=$(CURDIR)=. -fdebug-prefix-map=$(CURDIR)=.
HARDEN_CFLAGS := -fstack-protector-strong -mstack-protector-guard=global \
                 -fzero-call-used-regs=used-gpr \
                 -Wshadow -Wundef -Wmissing-prototypes -Wmissing-declarations \
                 -Wimplicit-fallthrough -Wnull-dereference -Wswitch-enum \
                 -Wformat=2 -Wno-format-nonliteral
CFLAGS := --target=aarch64-none-elf -std=c11 -ffreestanding -fno-builtin \
          $(HARDEN_CFLAGS) \
          -fno-pic -fno-pie -fno-omit-frame-pointer -mgeneral-regs-only -mstrict-align -march=armv8-a -O2 -g \
          $(REPRO_FLAGS) -DFBR34KER_BUILD_TARGET=\"$(FBR34KER_PLATFORM)\" \
          -DFBR34KER_SOURCE_ID=\"$(SOURCE_ID)\" $(EXTRA_CFLAGS) \
          -Wall -Wextra -Werror -Iinclude
ASFLAGS := --target=aarch64-none-elf -ffreestanding -fno-pic -fno-pie \
           -march=armv8-a -g $(REPRO_FLAGS) -Iinclude
LDFLAGS := -T $(LINKER_SCRIPT) -Map=$(TARGET).map --gc-sections --fatal-warnings

COMMON_C_SOURCES := \
    arch/arm64/cpu.c \
    arch/arm64/mmu.c \
    kernel/allocator.c \
    kernel/architecture.c \
    kernel/board.c \
    kernel/boot_evidence.c \
    kernel/bringup_report.c \
    kernel/build_info.c \
    kernel/bringup.c \
    kernel/command.c \
    kernel/console.c \
    kernel/crash.c \
    kernel/crc32.c \
    kernel/device_tree.c \
    kernel/driver.c \
    kernel/event.c \
    kernel/exception.c \
    kernel/fault.c \
    kernel/framebuffer_console.c \
    kernel/format.c \
    kernel/handoff.c \
    kernel/hardware_probe.c \
    kernel/kernel_patches.c \
    kernel/secure_boot_bypass.c \
    kernel/persistence.c \
    kernel/hal_sim.c \
    kernel/interrupt.c \
    kernel/lifecycle.c \
    kernel/log.c \
    kernel/main.c \
    kernel/module.c \
    kernel/mmio.c \
    kernel/physical_memory.c \
    kernel/protocol.c \
    kernel/sha256.c \
    kernel/service_guard.c \
    kernel/service_registry.c \
    kernel/stack_guard.c \
    kernel/string.c \
    kernel/trace.c \
    kernel/watchdog.c \
    kernel/apple_platform.c \
    kernel/usb.c \
    kernel/usbliter8_exploit.c \
    kernel/trust_cache.c \
    kernel/jailbreak.c \
    kernel/jbinit.c \
    modules/hello/hello.c \
    platform/gic.c

ifeq ($(FBR34KER_PLATFORM),qemu_virt)
PLATFORM_C_SOURCES := \
    platform/qemu_virt/platform.c \
    platform/qemu_virt/timer.c \
    platform/qemu_virt/uart.c \
    platform/qemu_virt/semihosting.c
else ifeq ($(FBR34KER_PLATFORM),generic_arm64)
PLATFORM_C_SOURCES := \
    platform/generic_arm64/platform.c \
    platform/generic_arm64/timer.c
else
$(error Unsupported FBR34KER_PLATFORM '$(FBR34KER_PLATFORM)')
endif

ifeq ($(FBR34KER_PLATFORM),qemu_virt)
ASFLAGS += -DFBR34KER_ENABLE_GICV3_SRE=1
endif

C_SOURCES := $(COMMON_C_SOURCES) $(PLATFORM_C_SOURCES)
ANALYZE_SOURCES := $(COMMON_C_SOURCES) \
    platform/qemu_virt/platform.c platform/qemu_virt/timer.c \
    platform/qemu_virt/uart.c platform/qemu_virt/semihosting.c \
    platform/generic_arm64/platform.c \
    platform/generic_arm64/timer.c examples/generic_loader/loader_adapter.c \
    loader/qemu_handoff/loader.c
ASM_SOURCES := arch/arm64/start.S arch/arm64/vectors.S
OBJECTS := $(patsubst %.c,$(BUILD_DIR)/%.o,$(C_SOURCES)) \
           $(patsubst %.S,$(BUILD_DIR)/%.o,$(ASM_SOURCES))
DEPENDENCIES := $(filter %.d,$(OBJECTS:.o=.d))
SDK_SOURCES := sdk/src/handoff_builder.c sdk/src/handoff_validate.c sdk/src/profile_match.c
SDK_OBJECTS := $(patsubst sdk/src/%.c,$(SDK_BUILD_DIR)/%.o,$(SDK_SOURCES))
SDK_DEPENDENCIES := $(SDK_OBJECTS:.o=.d)
SDK_CFLAGS := --target=aarch64-none-elf -std=c11 -ffreestanding -fno-builtin \
              -O2 -g $(REPRO_FLAGS) -Wall -Wextra -Werror -Isdk/include

.PHONY: all clean run inspect check check-native check-loader-example check-launcher check-version analyze \
        doctor integration integration-build smoke diagnostics release-gate verify modules check-host \
        generic manifest sign-manifest dist package permissions check-scripts check-install abi-check \
        loader-simulate loader-check generic-loader generic-qemu-run generic-qemu-smoke probe-qemu-smoke hardware-probe \
        sdk sdk-test sdk-analyze handoff-binary loader-conformance-test verify-layouts deployment-simulate apple-boot-images apple-bringup-simulate physical-integration-simulate physical-validation-candidate print-target \
        exploit-chain kernel-patches secure-boot-bypass persistence start-exploit establish-persistence

all: $(TARGET).elf $(TARGET).bin

print-target:
	@echo $(TARGET)

$(TARGET).elf: $(OBJECTS) $(LINKER_SCRIPT) | $(BUILD_DIR)
	$(LD) $(LDFLAGS) -o $@ $(OBJECTS)

$(TARGET).bin: $(TARGET).elf
	$(OBJCOPY) -O binary $< $@

$(BUILD_DIR)/%.o: %.c include/fbr34ker/version.h
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -ffunction-sections -fdata-sections \
		-MMD -MP -MF $(@:.o=.d) -c $< -o $@

$(BUILD_DIR)/%.o: %.S
	@mkdir -p $(dir $@)
	$(CC) $(ASFLAGS) -c $< -o $@

$(BUILD_DIR):
	mkdir -p $@

run: all
	@command -v $(QEMU) >/dev/null 2>&1 || { \
		echo "qemu-system-aarch64 is not installed"; exit 1; }
	$(QEMU) -machine virt,gic-version=3 -cpu cortex-a72 -m 256M \
		-nographic -monitor none -serial stdio -semihosting-config enable=on,target=native -kernel $(TARGET).bin

inspect: $(TARGET).elf
	$(READELF) -h -S -s $<

doctor:
	$(PYTHON) scripts/doctor.py

check: check-native check-loader-example check-launcher check-scripts check-install abi-check check-host

check-host:
	env -u MAKEFLAGS -u MFLAGS -u MAKELEVEL -u TARGET \
		$(PYTHON) scripts/run_host_tests.py --timeout 300 --module-timeout 60

check-launcher:
	@test -x fbr34ker
	@test -x b34stctl
	@test -x scripts/B34ST
	@test -x scripts/fbr34ker.sh
	@./fbr34ker --help >/dev/null
	@./fbr34ker --version >/dev/null
	@test -x host/fbr34kdeploy
	@test -x host/fbr34kdeploy-target
	@test -x host/fbr34kbootimg
	@test -x host/fbr34kirecovery
	@test -x host/fbr34kbringup
	@test -x host/fbr34kdevice
	@test -x host/fbr34kbridge
	@test -x host/fbr34ksession
	@test -x host/fbr34khardware
	@host/fbr34kdeploy --version >/dev/null
	@host/fbr34kdeploy-target --help >/dev/null
	@host/fbr34kbootimg --help >/dev/null
	@host/fbr34kirecovery --help >/dev/null
	@host/fbr34kbringup --help >/dev/null
	@host/fbr34kdevice --help >/dev/null
	@host/fbr34kbridge --help >/dev/null
	@host/fbr34ksession --help >/dev/null
	@host/fbr34khardware --help >/dev/null

check-scripts:
	$(PYTHON) scripts/check_sources.py
	$(PYTHON) scripts/check_version_consistency.py --expected $(VERSION)

abi-check:
	./fbr34ker abi-check

check-install:
	rm -rf $(BUILD_DIR)/install-test
	./scripts/install.sh --prefix /usr/local --destdir $(CURDIR)/$(BUILD_DIR)/install-test
	$(CURDIR)/$(BUILD_DIR)/install-test/usr/local/bin/fbr34ker version >/dev/null
	$(CURDIR)/$(BUILD_DIR)/install-test/usr/local/bin/fbr34ker abi-check >/dev/null
	$(CURDIR)/$(BUILD_DIR)/install-test/usr/local/bin/fbr34ker ipsw --help >/dev/null
	$(CURDIR)/$(BUILD_DIR)/install-test/usr/local/bin/fbr34ker ramdisk list-targets --json >/dev/null
	$(CURDIR)/$(BUILD_DIR)/install-test/usr/local/bin/fbr34ker forensics list-profiles >/dev/null
	$(CURDIR)/$(BUILD_DIR)/install-test/usr/local/bin/fbr34ker cve stats >/dev/null
	$(CURDIR)/$(BUILD_DIR)/install-test/usr/local/bin/B34ST --version >/dev/null
	./scripts/uninstall.sh --prefix /usr/local --destdir $(CURDIR)/$(BUILD_DIR)/install-test
	@test ! -e $(BUILD_DIR)/install-test/usr/local/bin/fbr34ker
	@test ! -e $(BUILD_DIR)/install-test/usr/local/bin/B34ST

permissions:
	chmod +x fbr34ker b34stctl scripts/B34ST host/fbr34kctl host/forgectl host/fbr34kdeploy host/fbr34kdeploy-target host/fbr34kbootimg host/fbr34kirecovery host/fbr34kbringup host/fbr34kdevice host/fbr34kbridge host/fbr34ksession host/fbr34khardware host/*.py scripts/*.py scripts/*.sh

check-native:
	@mkdir -p $(BUILD_DIR)/tests
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/format.c kernel/string.c tests/format_console_stub.c \
		tests/format_harness.c -o $(BUILD_DIR)/tests/format_harness
	$(BUILD_DIR)/tests/format_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/sha256.c kernel/string.c tests/sha256_harness.c \
		-o $(BUILD_DIR)/tests/sha256_harness
	$(BUILD_DIR)/tests/sha256_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/crc32.c tests/crc32_harness.c -o $(BUILD_DIR)/tests/crc32_harness
	$(BUILD_DIR)/tests/crc32_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		tests/boot_image_format_harness.c -o $(BUILD_DIR)/tests/boot_image_format_harness
	$(BUILD_DIR)/tests/boot_image_format_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		tests/first_stage_adapter_format_harness.c -o $(BUILD_DIR)/tests/first_stage_adapter_format_harness
	$(BUILD_DIR)/tests/first_stage_adapter_format_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/device_tree.c kernel/string.c tests/device_tree_harness.c \
		-o $(BUILD_DIR)/tests/device_tree_harness
	$(BUILD_DIR)/tests/device_tree_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/allocator.c kernel/string.c tests/allocator_harness.c \
		-o $(BUILD_DIR)/tests/allocator_harness
	$(BUILD_DIR)/tests/allocator_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/handoff.c kernel/string.c tests/handoff_harness.c \
		-o $(BUILD_DIR)/tests/handoff_harness
	$(BUILD_DIR)/tests/handoff_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/bringup.c kernel/event.c kernel/fault.c kernel/handoff.c kernel/string.c tests/bringup_harness.c \
		-o $(BUILD_DIR)/tests/bringup_harness
	$(BUILD_DIR)/tests/bringup_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/framebuffer_console.c kernel/string.c tests/framebuffer_console_harness.c \
		-o $(BUILD_DIR)/tests/framebuffer_console_harness
	$(BUILD_DIR)/tests/framebuffer_console_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/watchdog.c kernel/string.c tests/watchdog_harness.c \
		-o $(BUILD_DIR)/tests/watchdog_harness
	$(BUILD_DIR)/tests/watchdog_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		-DFBR34KER_PHYSICAL_PROBE_IMAGE=1 kernel/hardware_probe.c \
		tests/hardware_probe_harness.c -o $(BUILD_DIR)/tests/hardware_probe_harness
	$(BUILD_DIR)/tests/hardware_probe_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/service_guard.c kernel/string.c tests/service_guard_harness.c \
		-o $(BUILD_DIR)/tests/service_guard_harness
	$(BUILD_DIR)/tests/service_guard_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/lifecycle.c kernel/fault.c kernel/trace.c kernel/format.c kernel/string.c tests/format_console_stub.c tests/lifecycle_harness.c -o $(BUILD_DIR)/tests/lifecycle_harness
	$(BUILD_DIR)/tests/lifecycle_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/event.c kernel/fault.c kernel/string.c tests/event_harness.c -o $(BUILD_DIR)/tests/event_harness
	$(BUILD_DIR)/tests/event_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/event.c kernel/fault.c kernel/service_registry.c kernel/string.c tests/service_registry_harness.c -o $(BUILD_DIR)/tests/service_registry_harness
	$(BUILD_DIR)/tests/service_registry_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/event.c kernel/fault.c kernel/service_registry.c kernel/driver.c kernel/string.c tests/driver_harness.c -o $(BUILD_DIR)/tests/driver_harness
	$(BUILD_DIR)/tests/driver_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/board.c kernel/format.c kernel/string.c tests/format_console_stub.c tests/board_harness.c -o $(BUILD_DIR)/tests/board_harness
	$(BUILD_DIR)/tests/board_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/mmio.c kernel/string.c tests/mmio_harness.c -o $(BUILD_DIR)/tests/mmio_harness
	$(BUILD_DIR)/tests/mmio_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/physical_memory.c kernel/string.c tests/physical_memory_harness.c -o $(BUILD_DIR)/tests/physical_memory_harness
	$(BUILD_DIR)/tests/physical_memory_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		-DFBR34KER_HOST_TEST=1 kernel/boot_evidence.c kernel/crc32.c kernel/format.c kernel/string.c tests/format_console_stub.c tests/boot_evidence_harness.c -o $(BUILD_DIR)/tests/boot_evidence_harness
	$(BUILD_DIR)/tests/boot_evidence_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/lifecycle.c kernel/event.c kernel/fault.c kernel/trace.c kernel/format.c kernel/service_registry.c kernel/driver.c kernel/architecture.c kernel/board.c kernel/mmio.c kernel/physical_memory.c kernel/bringup_report.c kernel/string.c tests/format_console_stub.c tests/mmu_log_stub.c tests/architecture_harness.c -o $(BUILD_DIR)/tests/architecture_harness
	$(BUILD_DIR)/tests/architecture_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/trace.c kernel/format.c kernel/string.c tests/format_console_stub.c tests/trace_harness.c -o $(BUILD_DIR)/tests/trace_harness
	$(BUILD_DIR)/tests/trace_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		-DFBR34KER_ENABLE_FAULT_INJECTION=1 kernel/fault.c kernel/trace.c kernel/format.c kernel/string.c tests/format_console_stub.c tests/fault_harness.c -o $(BUILD_DIR)/tests/fault_harness
	$(BUILD_DIR)/tests/fault_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/hal_sim.c kernel/string.c tests/hal_sim_harness.c -o $(BUILD_DIR)/tests/hal_sim_harness
	$(BUILD_DIR)/tests/hal_sim_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		-DFBR34KER_ENABLE_FAULT_INJECTION=1 kernel/event.c kernel/fault.c kernel/trace.c kernel/format.c kernel/service_registry.c kernel/driver.c kernel/string.c tests/format_console_stub.c tests/runtime_validation_harness.c -o $(BUILD_DIR)/tests/runtime_validation_harness
	$(BUILD_DIR)/tests/runtime_validation_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		tests/deployment_protocol_harness.c -o $(BUILD_DIR)/tests/deployment_protocol_harness
	$(BUILD_DIR)/tests/deployment_protocol_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		tests/bridge_protocol_format_harness.c -o $(BUILD_DIR)/tests/bridge_protocol_format_harness
	$(BUILD_DIR)/tests/bridge_protocol_format_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		tests/physical_validation_format_harness.c -o $(BUILD_DIR)/tests/physical_validation_format_harness
	$(BUILD_DIR)/tests/physical_validation_format_harness
	$(CC) -std=c11 -O2 -ffreestanding -fno-builtin -Wall -Wextra -Werror -Iinclude \
		kernel/kernel_patches.c kernel/secure_boot_bypass.c kernel/persistence.c \
		kernel/string.c kernel/mmio.c tests/security_model_harness.c \
		-o $(BUILD_DIR)/tests/security_model_harness
	$(BUILD_DIR)/tests/security_model_harness


check-loader-example:
	@mkdir -p $(BUILD_DIR)/examples
	$(CC) $(CFLAGS) -Iexamples/generic_loader -c \
		examples/generic_loader/loader_adapter.c \
		-o $(BUILD_DIR)/examples/loader_adapter.o

analyze:
	$(PYTHON) scripts/run_static_analysis.py --clang $(CC) --timeout 45 \
		--jobs $(BUILD_JOBS) --include-dir include --source-id $(VERSION)-analysis $(ANALYZE_SOURCES)

$(SDK_BUILD_DIR)/%.o: sdk/src/%.c
	@mkdir -p $(dir $@)
	$(CC) $(SDK_CFLAGS) -MMD -MP -MF $(@:.o=.d) -c $< -o $@

$(SDK_LIBRARY): $(SDK_OBJECTS)
	$(AR) rcs $@ $(SDK_OBJECTS)

SDK_HOST_CFLAGS := -std=c11 -O2 -Wall -Wextra -Werror -Isdk/include

sdk: $(SDK_LIBRARY)

sdk-analyze:
	$(PYTHON) scripts/run_static_analysis.py --clang $(CC) --timeout 45 \
		--jobs $(BUILD_JOBS) --include-dir sdk/include --source-id $(VERSION)-sdk-analysis $(SDK_SOURCES)

sdk-test: sdk
	@mkdir -p $(SDK_BUILD_DIR)/tests $(SDK_BUILD_DIR)/examples
	$(CC) $(SDK_HOST_CFLAGS) $(SDK_SOURCES) sdk/tests/sdk_harness.c -o $(SDK_BUILD_DIR)/tests/sdk_harness
	$(SDK_BUILD_DIR)/tests/sdk_harness
	@for example in minimal_loader callback_console framebuffer_loader; do \
		$(CC) $(SDK_HOST_CFLAGS) $(SDK_SOURCES) sdk/examples/$$example/main.c \
			-o $(SDK_BUILD_DIR)/examples/$$example; \
		$(SDK_BUILD_DIR)/examples/$$example >/dev/null; \
	done

$(MODULE_OUTPUT): modules/dynamic_hello/module.json host/fbr34kctl.py
	@mkdir -p $(dir $@)
	$(PYTHON) host/fbr34kctl.py compile-module $< $@

modules: $(MODULE_OUTPUT)

generic:
	$(MAKE) FBR34KER_PLATFORM=generic_arm64 BUILD_DIR=build-generic \
		TARGET=build-generic/fbr34ker-generic all

LOADER_CFLAGS := --target=aarch64-none-elf -std=c11 -ffreestanding -fno-builtin \
    -fno-pic -fno-pie -fno-omit-frame-pointer -mgeneral-regs-only -mstrict-align -march=armv8-a -O2 -g \
    $(REPRO_FLAGS) -Wall -Wextra -Werror -Iinclude
LOADER_ASFLAGS := --target=aarch64-none-elf -ffreestanding -fno-pic -fno-pie \
    -march=armv8-a -g $(REPRO_FLAGS) -Iinclude

$(GENERIC_LOADER_BUILD_DIR)/loader.o: loader/qemu_handoff/loader.c
	@mkdir -p $(dir $@)
	$(CC) $(LOADER_CFLAGS) -ffunction-sections -fdata-sections \
		-MMD -MP -MF $(@:.o=.d) -c $< -o $@

$(GENERIC_LOADER_BUILD_DIR)/start.o: loader/qemu_handoff/start.S
	@mkdir -p $(dir $@)
	$(CC) $(LOADER_ASFLAGS) -c $< -o $@

$(GENERIC_LOADER_TARGET).elf: $(GENERIC_LOADER_BUILD_DIR)/loader.o \
        $(GENERIC_LOADER_BUILD_DIR)/start.o loader/qemu_handoff/linker.ld
	$(LD) -T loader/qemu_handoff/linker.ld -Map=$(GENERIC_LOADER_TARGET).map \
		--gc-sections --fatal-warnings -o $@ \
		$(GENERIC_LOADER_BUILD_DIR)/start.o $(GENERIC_LOADER_BUILD_DIR)/loader.o

$(GENERIC_LOADER_TARGET).bin: $(GENERIC_LOADER_TARGET).elf
	$(OBJCOPY) -O binary $< $@

generic-loader: generic $(GENERIC_LOADER_TARGET).elf $(GENERIC_LOADER_TARGET).bin

hardware-probe:
	$(MAKE) FBR34KER_PLATFORM=generic_arm64 BUILD_DIR=$(HARDWARE_PROBE_BUILD_DIR) \
		TARGET=$(HARDWARE_PROBE_TARGET) \
		EXTRA_CFLAGS=-DFBR34KER_PHYSICAL_PROBE_IMAGE=1 all

loader-simulate: generic modules
	rm -rf $(LOADER_SIM_DIR)
	$(PYTHON) host/fbr34kctl.py loader-simulate examples/handoff-v4.json \
		--image build-generic/fbr34ker-generic.elf \
		--module $(MODULE_OUTPUT) --output $(LOADER_SIM_DIR) >/dev/null

loader-check: loader-simulate
	$(PYTHON) host/fbr34kctl.py loader-report \
		$(LOADER_SIM_DIR)/loader-conformance.json
	@$(PYTHON) -c 'import json, pathlib, sys; p=pathlib.Path("$(LOADER_SIM_DIR)/loader-conformance.json"); d=json.loads(p.read_text()); sys.exit(0 if d.get("result") == "pass" else 1)'

handoff-binary:
	@mkdir -p $(HANDOFF_DIR)
	$(PYTHON) host/fbr34kctl.py handoff-build examples/handoff-v4.json $(HANDOFF_BLOB) >/dev/null
	$(PYTHON) host/fbr34kctl.py handoff-roundtrip $(HANDOFF_BLOB) >/dev/null

loader-conformance-test: handoff-binary
	$(PYTHON) host/fbr34kctl.py loader-conformance --handoff $(HANDOFF_BLOB) \
		--profile examples/hardware-profile.json --report $(SDK_CONFORMANCE_REPORT) >/dev/null
	@$(PYTHON) -c 'import json, pathlib, sys; d=json.loads(pathlib.Path("$(SDK_CONFORMANCE_REPORT)").read_text()); sys.exit(1 if d.get("result") == "fail" else 0)'

generic-qemu-run: generic-loader
	@command -v $(QEMU) >/dev/null 2>&1 || { echo "qemu-system-aarch64 is required"; exit 1; }
	$(QEMU) -machine virt,gic-version=3 -cpu cortex-a72 -m 2G -nographic \
		-monitor none -serial stdio -no-reboot \
		-semihosting-config enable=on,target=native \
		-kernel $(GENERIC_LOADER_TARGET).bin \
		-device loader,file=build-generic/fbr34ker-generic.bin,addr=0x80000000,force-raw=on

generic-qemu-smoke: generic-loader
	@command -v $(QEMU) >/dev/null 2>&1 || { echo "qemu-system-aarch64 is required"; exit 1; }
	$(PYTHON) scripts/qemu_generic_smoke.py \
		--loader $(GENERIC_LOADER_TARGET).bin \
		--image build-generic/fbr34ker-generic.bin \
		--output $(GENERIC_QEMU_SMOKE_DIR) --expected-version $(VERSION)

probe-qemu-smoke: generic-loader hardware-probe
	@command -v $(QEMU) >/dev/null 2>&1 || { echo "qemu-system-aarch64 is required"; exit 1; }
	$(PYTHON) scripts/qemu_probe_smoke.py \
		--loader $(GENERIC_LOADER_TARGET).bin \
		--image $(HARDWARE_PROBE_TARGET).bin \
		--output $(PROBE_QEMU_SMOKE_DIR) --expected-version $(VERSION)

integration-build:
	rm -rf $(INTEGRATION_BUILD_DIR)
	$(MAKE) BUILD_DIR=$(INTEGRATION_BUILD_DIR) TARGET=$(INTEGRATION_TARGET) \
		EXTRA_CFLAGS="-DFBR34KER_ENABLE_TEST_COMMANDS=1 -DFBR34KER_ENABLE_FAULT_INJECTION=1" all
	$(PYTHON) host/fbr34kctl.py compile-module \
		modules/dynamic_hello/module.json $(INTEGRATION_MODULE)
	$(PYTHON) scripts/verify_layout.py $(INTEGRATION_TARGET).elf \
		--expected-entry 0x40080000
	@strings $(INTEGRATION_TARGET).elf | grep -qx 'test-crash' || { \
		echo "integration image is missing the test-only crash hook"; exit 1; }
	@strings $(INTEGRATION_TARGET).elf | grep -qx 'fault-arm' || { \
		echo "integration image is missing deterministic fault injection"; exit 1; }

integration:
	@command -v $(QEMU) >/dev/null 2>&1 || { \
		echo "qemu-system-aarch64 is required for integration tests"; exit 1; }
	$(MAKE) integration-build
	$(MAKE) generic-loader
	FBR34KER_QEMU_REQUIRED=1 \
	FBR34KER_QEMU_IMAGE=$(INTEGRATION_TARGET).bin \
	FBR34KER_MODULE_IMAGE=$(INTEGRATION_MODULE) \
	FBR34KER_GENERIC_LOADER_IMAGE=$(GENERIC_LOADER_TARGET).bin \
	FBR34KER_GENERIC_MONITOR_IMAGE=build-generic/fbr34ker-generic.bin \
	FBR34KER_EXPECTED_VERSION=$(VERSION) \
	FBR34KER_ENABLE_CRASH_TEST=1 \
		$(PYTHON) -m unittest discover -s tests -p 'test_qemu*.py' -v

smoke:
	@command -v $(QEMU) >/dev/null 2>&1 || { \
		echo "qemu-system-aarch64 is required for the smoke test"; exit 1; }
	$(MAKE) integration-build
	$(PYTHON) scripts/qemu_smoke.py \
		--image $(INTEGRATION_TARGET).bin \
		--module $(INTEGRATION_MODULE) \
		--output $(SMOKE_DIR) \
		--expected-version $(VERSION) --runtime-validation --crash-test

diagnostics: all generic hardware-probe modules
	$(PYTHON) scripts/collect_diagnostics.py --output $(DIAGNOSTICS_DIR) --smoke-dir $(SMOKE_DIR)

deployment-simulate: generic modules
	rm -rf $(DEPLOYMENT_SIM_DIR)
	$(PYTHON) scripts/run_deployment_simulation.py --output $(DEPLOYMENT_SIM_DIR)

APPLE_BOOT_COMMON = --monitor build-generic/fbr34ker-generic.bin \
	--monitor-load 0x80000000 --monitor-entry 0x80000000 \
	--handoff $(HANDOFF_BLOB) --module $(MODULE_OUTPUT)

apple-boot-images: generic modules handoff-binary
	rm -rf $(APPLE_BOOT_DIR)
	$(PYTHON) host/boot_image.py build --profile profiles/apple-a12-recovery.json \
		$(APPLE_BOOT_COMMON) --output $(A12_BOOT_DIR)/boot.img \
		--raw-output $(A12_BOOT_DIR)/boot.raw
	$(PYTHON) host/boot_image.py build --profile profiles/apple-a12x-recovery.json \
		$(APPLE_BOOT_COMMON) --output $(A12X_BOOT_DIR)/boot.img \
		--raw-output $(A12X_BOOT_DIR)/boot.raw
	$(PYTHON) host/boot_image.py build --profile profiles/apple-a13-recovery.json \
		$(APPLE_BOOT_COMMON) --output $(A13_BOOT_DIR)/boot.img \
		--raw-output $(A13_BOOT_DIR)/boot.raw
	$(PYTHON) host/boot_image.py build --profile profiles/apple-a14-recovery.json \
		$(APPLE_BOOT_COMMON) --output $(A14_BOOT_DIR)/boot.img \
		--raw-output $(A14_BOOT_DIR)/boot.raw
	$(PYTHON) host/boot_image.py build --profile profiles/apple-a15-recovery.json \
		$(APPLE_BOOT_COMMON) --output $(A15_BOOT_DIR)/boot.img \
		--raw-output $(A15_BOOT_DIR)/boot.raw
	$(PYTHON) host/boot_image.py build --profile profiles/apple-m1-recovery.json \
		$(APPLE_BOOT_COMMON) --output $(M1_BOOT_DIR)/boot.img \
		--raw-output $(M1_BOOT_DIR)/boot.raw
	$(PYTHON) host/boot_image.py build --profile profiles/apple-m2-recovery.json \
		$(APPLE_BOOT_COMMON) --output $(M2_BOOT_DIR)/boot.img \
		--raw-output $(M2_BOOT_DIR)/boot.raw
	$(PYTHON) host/boot_image.py inspect $(A12_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(A12X_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(A13_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(A14_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(A15_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(M1_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(M2_BOOT_DIR)/boot.img --json >/dev/null


apple-bringup-simulate: apple-boot-images
	rm -rf $(APPLE_BRINGUP_SIM_DIR)
	$(PYTHON) scripts/run_hardware_bringup_simulation.py \
		--output $(APPLE_BRINGUP_SIM_DIR) \
		--image $(A13_BOOT_DIR)/boot.img \
		--profile profiles/apple-a13-recovery.json \
		--device-info examples/a13-device-info.json

physical-integration-simulate: apple-boot-images
	rm -rf $(PHYSICAL_INTEGRATION_SIM_DIR)
	$(PYTHON) scripts/run_physical_integration_simulation.py \
		--output $(PHYSICAL_INTEGRATION_SIM_DIR) \
		--image $(A13_BOOT_DIR)/boot.img \
		--profile profiles/apple-a13-iphone-recovery.json \
		--device-info examples/a13-device-info.json


physical-validation-candidate: apple-boot-images
	rm -rf $(PHYSICAL_VALIDATION_DIR)
	$(PYTHON) scripts/run_physical_validation_candidate.py \
		--output $(PHYSICAL_VALIDATION_DIR) \
		--image $(A13_BOOT_DIR)/boot.img \
		--profile profiles/apple-a13-iphone-recovery.json \
		--device-info examples/a13-device-info.json$(if $(wildcard $(RUNTIME_ARTIFACT_DIR)/gate/summary.json), --qemu-summary $(RUNTIME_ARTIFACT_DIR)/gate/summary.json,)
	$(PYTHON) host/physical_validation.py validate-session \
		$(PHYSICAL_VALIDATION_DIR)/success-session.zip >/dev/null
	$(PYTHON) host/physical_validation.py validate-session \
		$(PHYSICAL_VALIDATION_DIR)/recovered-session.zip >/dev/null

manifest: all generic hardware-probe modules loader-check loader-conformance-test sdk generic-loader build-operational deployment-simulate apple-boot-images apple-bringup-simulate physical-integration-simulate physical-validation-candidate
	$(PYTHON) scripts/release_manifest.py \
		--version $(VERSION) --channel $(RELEASE_CHANNEL) \
		--source-id $(SOURCE_ID) --release-name $(RELEASE_NAME) \
		--output $(RELEASE_MANIFEST) --checksums CHECKSUMS.sha256 \
		build/fbr34ker.bin build/fbr34ker.elf build/fbr34ker.map \
		build-generic/fbr34ker-generic.bin build-generic/fbr34ker-generic.elf \
		build-generic/fbr34ker-generic.map $(MODULE_OUTPUT) \
		$(LOADER_SIM_DIR)/loader-conformance.json \
		$(LOADER_SIM_DIR)/handoff-v4.bin \
		$(LOADER_SIM_DIR)/memory-regions.bin \
		$(LOADER_SIM_DIR)/platform-services.bin \
		$(LOADER_SIM_DIR)/callback-stubs.bin \
		$(LOADER_SIM_DIR)/boot-modules.bin \
		$(LOADER_SIM_DIR)/normalized-handoff.json \
		$(LOADER_SIM_DIR)/sparse-memory.json \
		$(GENERIC_LOADER_TARGET).bin $(GENERIC_LOADER_TARGET).elf \
		$(GENERIC_LOADER_TARGET).map \
		$(HARDWARE_PROBE_TARGET).bin $(HARDWARE_PROBE_TARGET).elf \
		$(HARDWARE_PROBE_TARGET).map \
		$(SDK_LIBRARY) $(HANDOFF_BLOB) $(SDK_CONFORMANCE_REPORT) \
		$(DEPLOYMENT_SIM_DIR)/simulation-summary.json \
		$(DEPLOYMENT_SIM_DIR)/evidence.zip \
		$(A12_BOOT_DIR)/boot.img $(A12_BOOT_DIR)/boot.img.json \
		$(A12_BOOT_DIR)/boot.raw $(A12_BOOT_DIR)/boot.raw.json \
		$(A12X_BOOT_DIR)/boot.img $(A12X_BOOT_DIR)/boot.img.json \
		$(A12X_BOOT_DIR)/boot.raw $(A12X_BOOT_DIR)/boot.raw.json \
		$(A13_BOOT_DIR)/boot.img $(A13_BOOT_DIR)/boot.img.json \
		$(A13_BOOT_DIR)/boot.raw $(A13_BOOT_DIR)/boot.raw.json \
		$(A14_BOOT_DIR)/boot.img $(A14_BOOT_DIR)/boot.img.json \
		$(A14_BOOT_DIR)/boot.raw $(A14_BOOT_DIR)/boot.raw.json \
		$(A15_BOOT_DIR)/boot.img $(A15_BOOT_DIR)/boot.img.json \
		$(A15_BOOT_DIR)/boot.raw $(A15_BOOT_DIR)/boot.raw.json \
		$(M1_BOOT_DIR)/boot.img $(M1_BOOT_DIR)/boot.img.json \
		$(M1_BOOT_DIR)/boot.raw $(M1_BOOT_DIR)/boot.raw.json \
		$(M2_BOOT_DIR)/boot.img $(M2_BOOT_DIR)/boot.img.json \
		$(M2_BOOT_DIR)/boot.raw $(M2_BOOT_DIR)/boot.raw.json \
		$(APPLE_BRINGUP_SIM_DIR)/simulation-summary.json \
		$(APPLE_BRINGUP_SIM_DIR)/success-evidence.zip \
		$(APPLE_BRINGUP_SIM_DIR)/failure-evidence.zip \
		$(APPLE_BRINGUP_SIM_DIR)/recovered-evidence.zip \
		$(PHYSICAL_INTEGRATION_SIM_DIR)/simulation-summary.json \
		$(PHYSICAL_INTEGRATION_SIM_DIR)/success-session.zip \
		$(PHYSICAL_INTEGRATION_SIM_DIR)/failure-session.zip \
		$(PHYSICAL_INTEGRATION_SIM_DIR)/recovered-session.zip \
		$(PHYSICAL_VALIDATION_DIR)/summary.json \
		$(PHYSICAL_VALIDATION_DIR)/candidate-report.json \
		$(PHYSICAL_VALIDATION_DIR)/qemu-summary.json \
		$(PHYSICAL_VALIDATION_DIR)/success-session.zip \
		$(PHYSICAL_VALIDATION_DIR)/failure-session.zip \
		$(PHYSICAL_VALIDATION_DIR)/recovered-session.zip \
		$(PHYSICAL_VALIDATION_DIR)/failure-matrix/console.zip \
		$(PHYSICAL_VALIDATION_DIR)/failure-matrix/memory-map.zip \
		$(PHYSICAL_VALIDATION_DIR)/failure-matrix/timer.zip \
		$(PHYSICAL_VALIDATION_DIR)/failure-matrix/boot-evidence.zip

sign-manifest: manifest
	@test -n "$(SIGNING_KEY)" || { echo "set SIGNING_KEY=/path/to/private-key"; exit 2; }
	./scripts/sign_manifest.sh $(RELEASE_MANIFEST) "$(SIGNING_KEY)"

verify:
	$(PYTHON) scripts/non_qemu_verify.py --version $(VERSION) \
		--build-jobs $(BUILD_JOBS) --output validation-logs/non-qemu

verify-layouts:
	$(PYTHON) scripts/verify_layout.py $(TARGET).elf --expected-entry 0x40080000
	$(PYTHON) scripts/verify_layout.py build-generic/fbr34ker-generic.elf --expected-entry 0x80000000
	$(PYTHON) scripts/verify_layout.py $(GENERIC_LOADER_TARGET).elf --expected-entry 0x40080000 --profile loader
	$(PYTHON) scripts/verify_layout.py $(HARDWARE_PROBE_TARGET).elf --expected-entry 0x80000000
	@strings $(HARDWARE_PROBE_TARGET).elf | grep -qx 'physical-hardware-probe' || { echo "hardware probe metadata missing"; exit 1; }
	$(PYTHON) host/fbr34kctl.py manifest $(TARGET).bin
	$(PYTHON) host/boot_image.py inspect $(A12_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(A12X_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(A13_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(A14_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(A15_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(M1_BOOT_DIR)/boot.img --json >/dev/null
	$(PYTHON) host/boot_image.py inspect $(M2_BOOT_DIR)/boot.img --json >/dev/null
	@test -s $(APPLE_BRINGUP_SIM_DIR)/simulation-summary.json
	@test -s $(PHYSICAL_INTEGRATION_SIM_DIR)/simulation-summary.json
	@test -s $(PHYSICAL_VALIDATION_DIR)/summary.json
	@$(PYTHON) -c 'import json,pathlib,sys; d=json.loads(pathlib.Path("$(PHYSICAL_VALIDATION_DIR)/summary.json").read_text()); sys.exit(0 if d.get("candidate_ready") else 1)'

release-gate:
	$(PYTHON) scripts/release_gate.py --version $(VERSION) --release-stage $(RELEASE_CHANNEL) \
		--output $(RUNTIME_ARTIFACT_DIR)/gate --diagnostics $(DIAGNOSTICS_DIR)

package: verify build-operational
	$(PYTHON) scripts/package_release.py --release-name $(RELEASE_NAME) \
		--output-dir $(PACKAGE_DIR) --kind all

sdk-release: all build-operational apple-boot-images
	$(PYTHON) scripts/package_release.py --release-name $(RELEASE_NAME) \
		--output-dir $(PACKAGE_DIR) --kind operational

#====================================================================
# EXPLOIT CHAIN TARGETS
#====================================================================

OPERATIONAL_DIR := build-exploit
OPERATIONAL_TARGET := $(OPERATIONAL_DIR)/fbr34ker-operational

ifeq ($(SECURITY_MODEL),0)
kernel-patches: all
	@echo "Kernel-patch state model built; release mutation gate is disabled"

secure-boot-bypass: all
	@echo "Secure-boot state model built; release mutation gate is disabled"

persistence: all
	@echo "Persistence state model built; release mutation gate is disabled"

exploit-chain: all
	@echo "Security models disabled (set SECURITY_MODEL=1 for functional build)"
else
kernel-patches: all
	@echo "Kernel-patch subsystem built with MUTATION ENABLED"

secure-boot-bypass: all
	@echo "Secure-boot bypass built with MUTATION ENABLED"

persistence: all
	@echo "Persistence subsystem built with MUTATION ENABLED"

exploit-chain: all
	@echo "Security-chain built with operational mutation enabled"
endif

build-operational:
	$(MAKE) SECURITY_MODEL=1 FBR34KER_PLATFORM=generic_arm64 \
		BUILD_DIR=$(OPERATIONAL_DIR) \
		TARGET=$(OPERATIONAL_TARGET) \
		EXTRA_CFLAGS="-DFBR34KER_ENABLE_FAULT_INJECTION=1 -DFBR34KER_ENABLE_TEST_COMMANDS=1" \
		all
	@echo "Operational build complete: $(OPERATIONAL_TARGET).bin"
	@ls -la $(OPERATIONAL_TARGET).bin $(OPERATIONAL_TARGET).elf

operational: build-operational
	@echo ""
	@echo "============================================"
	@echo "FBR34KER OPERATIONAL BUILD"
	@echo "============================================"
	@echo "Security models: ENABLED"
	@echo "Kernel patching: ACTUAL MEMORY WRITES"
	@echo "USB support:     ACTIVE (DWC3 gadget)"
	@echo "Apple platform:  ACTIVE (A12/A13)"
	@echo "USB exploit:     ACTIVE (USBliter8)"
	@echo "Persist model:   ENABLED"
	@echo "============================================"

start-exploit: operational
	@mkdir -p $(OPERATIONAL_DIR)/exploit
	@echo "============================================" > $(OPERATIONAL_DIR)/exploit/exploit-summary.txt
	@echo "FBR34KER Exploit Chain - Operational" >> $(OPERATIONAL_DIR)/exploit/exploit-summary.txt
	@echo "============================================" >> $(OPERATIONAL_DIR)/exploit/exploit-summary.txt
	@echo "Build version: $(VERSION)" >> $(OPERATIONAL_DIR)/exploit/exploit-summary.txt
	@echo "Security models: ENABLED" >> $(OPERATIONAL_DIR)/exploit/exploit-summary.txt
	@echo "Kernel patching: Actual memory writes" >> $(OPERATIONAL_DIR)/exploit/exploit-summary.txt
	@echo "USB: DWC3 gadget (CDC ACM)" >> $(OPERATIONAL_DIR)/exploit/exploit-summary.txt
	@echo "Boot chain: USBliter8 -> FBR34KER monitor -> A12+ kernel" >> $(OPERATIONAL_DIR)/exploit/exploit-summary.txt
	@echo "============================================" >> $(OPERATIONAL_DIR)/exploit/exploit-summary.txt
	@cp $(OPERATIONAL_TARGET).elf $(OPERATIONAL_DIR)/exploit/
	@cp $(OPERATIONAL_TARGET).bin $(OPERATIONAL_DIR)/exploit/
	@echo "Operational exploit artifacts in $(OPERATIONAL_DIR)/exploit/"

establish-persistence: operational
	@mkdir -p $(OPERATIONAL_DIR)/persistence
	@echo "============================================" > $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "FBR34KER Persistence - Operational" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "============================================" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "Persistence hooks for iOS post-exploitation:" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "  1. Boot hook installation (launchd/rc)" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "  2. Kernel extension deployment" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "  3. Hidden storage allocation" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "  4. Payload deployment" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "  5. Detection evasion" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "  6. Tamper resistance" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "  7. OTA update persistence" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "Status: OPERATIONAL (mutation enabled)" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "============================================" >> $(OPERATIONAL_DIR)/persistence/persistence-plan.txt
	@echo "Persistence plan written to $(OPERATIONAL_DIR)/persistence/persistence-plan.txt"

clean:
	rm -rf build build-generic build-loader build-hardware-probe build-sdk build-integration build-apple build-exploit runtime-artifacts diagnostics dist
	rm -f RELEASE_MANIFEST.json RELEASE_MANIFEST.json.sig CHECKSUMS.sha256

# Produces a deterministic source archive with executable modes preserved.
dist:
	$(PYTHON) scripts/package_release.py --release-name $(RELEASE_NAME) \
		--output-dir $(PACKAGE_DIR) --kind source

-include $(DEPENDENCIES) $(SDK_DEPENDENCIES) \
	$(GENERIC_LOADER_BUILD_DIR)/loader.d
