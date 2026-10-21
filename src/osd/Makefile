# rg35xxh-osd: plain C Wayland client (wl_shm + wlr-layer-shell). Needs wayland-scanner and the
# wayland-client / wayland-protocols development files (pkg-config).
#   make                                      native build
#   make CC=aarch64-linux-gnu-gcc SYSROOT=/path/to/arm64/rootfs    cross build (build/07b-osd.sh)
CFLAGS ?= -O2
CFLAGS += -Wall -Wextra -Wno-unused-parameter -std=gnu11
SYSROOT ?=
PKG_CONFIG ?= pkg-config
ifneq ($(SYSROOT),)
  SYSFLAGS := --sysroot=$(SYSROOT)
  PKG_CONFIG := PKG_CONFIG_SYSROOT_DIR=$(SYSROOT) \
    PKG_CONFIG_LIBDIR=$(SYSROOT)/usr/lib/aarch64-linux-gnu/pkgconfig:$(SYSROOT)/usr/share/pkgconfig pkg-config
  WL_PROTOCOLS ?= $(SYSROOT)/usr/share/wayland-protocols
endif
WAYLAND_SCANNER ?= wayland-scanner
WL_PROTOCOLS ?= $(shell $(PKG_CONFIG) --variable=pkgdatadir wayland-protocols)
XDG_SHELL := $(WL_PROTOCOLS)/stable/xdg-shell/xdg-shell.xml
LAYER_SHELL := protocol/wlr-layer-shell-unstable-v1.xml
GEN := gen

rg35xxh-osd: rg35xxh-osd.c $(GEN)/wlr-layer-shell-unstable-v1-client-protocol.h \
             $(GEN)/wlr-layer-shell-unstable-v1-protocol.c $(GEN)/xdg-shell-protocol.c
	$(CC) $(SYSFLAGS) $(CFLAGS) -I$(GEN) $(shell $(PKG_CONFIG) --cflags wayland-client) -o $@ \
	  rg35xxh-osd.c $(GEN)/wlr-layer-shell-unstable-v1-protocol.c $(GEN)/xdg-shell-protocol.c \
	  $(LDFLAGS) $(shell $(PKG_CONFIG) --libs wayland-client)

$(GEN)/wlr-layer-shell-unstable-v1-client-protocol.h: $(LAYER_SHELL)
	mkdir -p $(GEN) && $(WAYLAND_SCANNER) client-header $< $@
$(GEN)/wlr-layer-shell-unstable-v1-protocol.c: $(LAYER_SHELL)
	mkdir -p $(GEN) && $(WAYLAND_SCANNER) private-code $< $@
$(GEN)/xdg-shell-protocol.c: $(XDG_SHELL)                # layer-shell popups refer to xdg_popup
	mkdir -p $(GEN) && $(WAYLAND_SCANNER) private-code $< $@

clean:
	rm -rf $(GEN) rg35xxh-osd
.PHONY: clean
