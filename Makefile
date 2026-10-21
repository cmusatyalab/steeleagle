# Cross-builds eagled for an arm64 vehicle computer with Ubuntu 20.04 (glibc
# 2.31), such as a Particle Tachyon:
#
#   make eagled-arm64      # writes build/arm64/eagled
#
# eagled links Gabriel through cgo, so this first installs Gabriel's library for
# arm64 with cargo-c, into build/arm64/gabriel, where pkg-config finds it. Both
# builds run in a container with Ubuntu 20.04's arm64 cross compiler, so that
# the binary runs on the vehicle's older glibc. The container uses this
# machine's Go, and is built from Gabriel's examples/h264/Dockerfile.aarch64 if
# it is missing.
#
# GABRIEL_SRC is the gabriel-rust checkout, whose go directory go.mod replaces
# Gabriel's Go bindings with.

GABRIEL_SRC ?= ../gabriel-rust
ARM64_IMAGE ?= gabriel-h264-aarch64

ARM64_TARGET := aarch64-unknown-linux-gnu
BUILD_DIR := build/arm64
# Where libgabriel for arm64 is installed. The containers mount it at the same
# path, which its pkg-config file names.
GABRIEL_ARM64_PREFIX := $(CURDIR)/$(BUILD_DIR)/gabriel
GABRIEL_PREFIX_MOUNT := /gabriel
GO_CACHE_DIR := build/gocache-arm64
CARGO_REGISTRY := $(HOME)/.cargo/registry
GABRIEL_DIR := $(abspath $(GABRIEL_SRC))
# Where cargo writes the arm64 library, apart from the host's build.
GABRIEL_ARM64_TARGET_DIR := target/aarch64

DOCKER_RUN := docker run --rm -u $(shell id -u):$(shell id -g) -e HOME=/tmp

.PHONY: eagled-arm64 libgabriel-arm64 arm64-image clean-arm64

# The checkouts are mounted side by side, where go.mod's replace directive
# expects them.
eagled-arm64: libgabriel-arm64 | $(BUILD_DIR) $(GO_CACHE_DIR)
	$(DOCKER_RUN) \
		-v $(CURDIR):/src/steeleagle-go \
		-v $(GABRIEL_DIR):/src/gabriel-rust \
		-v $(GABRIEL_ARM64_PREFIX):$(GABRIEL_PREFIX_MOUNT):ro \
		-e PKG_CONFIG_PATH=$(GABRIEL_PREFIX_MOUNT)/lib/pkgconfig \
		-v $(shell go env GOROOT):/usr/local/go:ro \
		-v $(shell go env GOMODCACHE):/gomod -e GOMODCACHE=/gomod \
		-v $(CURDIR)/$(GO_CACHE_DIR):/gocache -e GOCACHE=/gocache \
		-e CGO_ENABLED=1 -e GOOS=linux -e GOARCH=arm64 -e CC=aarch64-linux-gnu-gcc \
		-w /src/steeleagle-go $(ARM64_IMAGE) \
		/usr/local/go/bin/go build -o $(BUILD_DIR)/eagled ./cmd/eagled
	@echo "built $(BUILD_DIR)/eagled"

# Cargo builds only what changed, so this is quick when Gabriel did not. Only
# the static library is installed, so eagled carries all of Gabriel.
libgabriel-arm64: arm64-image | $(CARGO_REGISTRY) $(GABRIEL_ARM64_PREFIX)
	$(DOCKER_RUN) \
		-v $(GABRIEL_DIR):/src -v $(CARGO_REGISTRY):/cargo/registry -w /src \
		-v $(GABRIEL_ARM64_PREFIX):$(GABRIEL_PREFIX_MOUNT) \
		-e CARGO_TARGET_DIR=/src/$(GABRIEL_ARM64_TARGET_DIR) $(ARM64_IMAGE) \
		cargo cinstall --release --locked --target $(ARM64_TARGET) -p gabriel \
			--library-type staticlib --prefix $(GABRIEL_PREFIX_MOUNT) --libdir lib

arm64-image:
	@docker image inspect $(ARM64_IMAGE) >/dev/null 2>&1 || \
		docker build -t $(ARM64_IMAGE) \
			-f $(GABRIEL_DIR)/examples/h264/Dockerfile.aarch64 $(GABRIEL_DIR)/examples/h264

$(BUILD_DIR) $(GO_CACHE_DIR) $(CARGO_REGISTRY) $(GABRIEL_ARM64_PREFIX):
	mkdir -p $@

clean-arm64:
	rm -rf $(BUILD_DIR) $(GO_CACHE_DIR)
