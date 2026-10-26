# rg35xxh-bootsplash: plain C, libc only. Cross build: make CC=aarch64-linux-gnu-gcc SYSROOT=<rootfs>
CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra
SYSROOT ?=
ifneq ($(SYSROOT),)
  CFLAGS += --sysroot=$(SYSROOT)
  LDFLAGS += --sysroot=$(SYSROOT)
endif

rg35xxh-bootsplash: rg35xxh-bootsplash.c assets.h
	$(CC) $(CFLAGS) -o $@ rg35xxh-bootsplash.c $(LDFLAGS)

clean:
	rm -f rg35xxh-bootsplash
.PHONY: clean
