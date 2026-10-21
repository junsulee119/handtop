/*
 * rg35xxh-osd: the volume / brightness pop-up for Handtop (replaces wob).
 *
 * A vertical bar at the left edge of the screen, vertically centred: the level as a number on
 * top (pixel font) and a bar filling from the bottom. Blue for volume, amber for brightness.
 *
 * Input: the input daemon writes a level (0-100) and a newline to
 * $XDG_RUNTIME_DIR/wob-volume.sock or wob-brightness.sock (FIFOs; the names are kept from wob,
 * so the daemon is unchanged). Each level shows the bar for TIMEOUT_MS on the focused screen,
 * above everything, without taking any input. While hidden there is no surface at all.
 *
 * Plain Wayland client (wl_shm + wlr-layer-shell), no toolkit: ~1-2 MB of memory.
 * Build: src/osd/Makefile (the image build uses build/07b-osd.sh).
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/timerfd.h>
#include <unistd.h>
#include <wayland-client.h>

#include "wlr-layer-shell-unstable-v1-client-protocol.h"

/* ---- look ------------------------------------------------------------------------------ */
#define W 36                /* panel size ("100" is 22 px wide: 2 px clear of the border) */
#define H 280
#define MARGIN 16           /* from the left edge */
#define OFFSET 3            /* border inset */
#define BORDER 2
#define PAD 3               /* gap inside the border */
#define DIGIT_SCALE 2       /* 3x5 font drawn at 2x: 6x10 per digit, 2 px apart */
#define TEXT_GAP 4          /* between the number and the bar */
#define TIMEOUT_MS 1200

#define BG 0xE61a1e26u      /* ARGB, not premultiplied */
static const struct { const char *name; uint32_t border, level; } KINDS[] = {
    {"volume",     0xFF3D5A8Au, 0xFF8FB4FFu},
    {"brightness", 0xFF8A6A2Fu, 0xFFFFD28Fu},
};
#define NKINDS 2
#define TEXT 0xFFE8EAEEu

static const char *FONT[10] = {     /* 3x5, rows top to bottom */
    "111101101101111", "010110010010111", "111001111100111", "111001111001111", "101101111001001",
    "111100111001111", "111100111101111", "111001010010010", "111101111101111", "111101111001111",
};

/* ---- state ----------------------------------------------------------------------------- */
struct buffer { struct wl_buffer *wl; uint32_t *px; int busy; };

static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct zwlr_layer_shell_v1 *layer_shell;
static struct wl_surface *surface;
static struct zwlr_layer_surface_v1 *layer_surface;
static int configured;
static struct buffer buffers[2];
static int kind, level;

static uint32_t premul(uint32_t c)
{
    uint32_t a = c >> 24;
    uint32_t r = ((c >> 16) & 0xff) * a / 255, g = ((c >> 8) & 0xff) * a / 255, b = (c & 0xff) * a / 255;
    return a << 24 | r << 16 | g << 8 | b;
}

static void fill(uint32_t *px, int x, int y, int w, int h, uint32_t c)
{
    for (int j = y; j < y + h; j++)
        for (int i = x; i < x + w; i++)
            if (i >= 0 && i < W && j >= 0 && j < H)
                px[j * W + i] = c;
}

static void draw(uint32_t *px)
{
    uint32_t border = KINDS[kind].border, lv = KINDS[kind].level;
    fill(px, 0, 0, W, H, premul(BG));
    fill(px, OFFSET, OFFSET, W - 2 * OFFSET, BORDER, border);                    /* border */
    fill(px, OFFSET, H - OFFSET - BORDER, W - 2 * OFFSET, BORDER, border);
    fill(px, OFFSET, OFFSET, BORDER, H - 2 * OFFSET, border);
    fill(px, W - OFFSET - BORDER, OFFSET, BORDER, H - 2 * OFFSET, border);

    int in = OFFSET + BORDER + PAD;                                              /* inner box */
    char num[4];
    snprintf(num, sizeof num, "%d", level);
    int n = strlen(num), dw = 3 * DIGIT_SCALE, gap = DIGIT_SCALE;
    int tw = n * dw + (n - 1) * gap, tx = (W - tw) / 2, ty = in;
    for (int d = 0; d < n; d++)
        for (int r = 0; r < 5; r++)
            for (int c = 0; c < 3; c++)
                if (FONT[num[d] - '0'][r * 3 + c] == '1')
                    fill(px, tx + d * (dw + gap) + c * DIGIT_SCALE, ty + r * DIGIT_SCALE,
                         DIGIT_SCALE, DIGIT_SCALE, TEXT);

    int top = ty + 5 * DIGIT_SCALE + TEXT_GAP;                                  /* the bar */
    fill(px, OFFSET + BORDER, top - TEXT_GAP / 2, W - 2 * (OFFSET + BORDER), 1, border);   /* divider */
    int full = H - in - top, h = full * level / 100;
    fill(px, in, H - in - h, W - 2 * in, h, lv);
}

/* ---- buffers --------------------------------------------------------------------------- */
static void buffer_release(void *data, struct wl_buffer *b) { ((struct buffer *)data)->busy = 0; }
static const struct wl_buffer_listener buffer_listener = { buffer_release };

static int make_buffers(void)
{
    int stride = W * 4, size = stride * H;
    int fd = memfd_create("rg35xxh-osd", MFD_CLOEXEC);
    if (fd < 0 || ftruncate(fd, 2 * size) < 0)
        return -1;
    uint32_t *data = mmap(NULL, 2 * size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (data == MAP_FAILED)
        return -1;
    struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, 2 * size);
    for (int i = 0; i < 2; i++) {
        buffers[i].wl = wl_shm_pool_create_buffer(pool, i * size, W, H, stride, WL_SHM_FORMAT_ARGB8888);
        buffers[i].px = data + i * W * H;
        wl_buffer_add_listener(buffers[i].wl, &buffer_listener, &buffers[i]);
    }
    wl_shm_pool_destroy(pool);
    close(fd);
    return 0;
}

static void redraw(void)
{
    if (!configured)
        return;
    struct buffer *b = !buffers[0].busy ? &buffers[0] : !buffers[1].busy ? &buffers[1] : NULL;
    if (!b)
        return;                                   /* both on screen still: the next level redraws */
    draw(b->px);
    wl_surface_attach(surface, b->wl, 0, 0);
    wl_surface_damage_buffer(surface, 0, 0, W, H);
    wl_surface_commit(surface);
    b->busy = 1;
}

/* ---- the layer surface ----------------------------------------------------------------- */
static void hide(void)
{
    if (layer_surface)
        zwlr_layer_surface_v1_destroy(layer_surface);
    if (surface)
        wl_surface_destroy(surface);
    layer_surface = NULL;
    surface = NULL;
    configured = 0;
    buffers[0].busy = buffers[1].busy = 0;      /* the compositor drops them with the surface */
}

static void ls_configure(void *data, struct zwlr_layer_surface_v1 *ls, uint32_t serial, uint32_t w, uint32_t h)
{
    zwlr_layer_surface_v1_ack_configure(ls, serial);
    configured = 1;
    redraw();
}

static void ls_closed(void *data, struct zwlr_layer_surface_v1 *ls) { hide(); }
static const struct zwlr_layer_surface_v1_listener ls_listener = { ls_configure, ls_closed };

static void show(void)
{
    if (surface) {
        redraw();
        return;
    }
    surface = wl_compositor_create_surface(compositor);
    struct wl_region *none = wl_compositor_create_region(compositor);     /* input passes through */
    wl_surface_set_input_region(surface, none);
    wl_region_destroy(none);
    layer_surface = zwlr_layer_shell_v1_get_layer_surface(layer_shell, surface, NULL,
                        ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY, "rg35xxh-osd");
    zwlr_layer_surface_v1_set_size(layer_surface, W, H);
    zwlr_layer_surface_v1_set_anchor(layer_surface, ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT);   /* centred vertically */
    zwlr_layer_surface_v1_set_margin(layer_surface, 0, 0, 0, MARGIN);
    zwlr_layer_surface_v1_set_exclusive_zone(layer_surface, -1);
    zwlr_layer_surface_v1_set_keyboard_interactivity(layer_surface, 0);
    zwlr_layer_surface_v1_add_listener(layer_surface, &ls_listener, NULL);
    wl_surface_commit(surface);
}

/* ---- globals --------------------------------------------------------------------------- */
static void reg_global(void *data, struct wl_registry *r, uint32_t name, const char *iface, uint32_t ver)
{
    if (!strcmp(iface, wl_compositor_interface.name))
        compositor = wl_registry_bind(r, name, &wl_compositor_interface, 4);
    else if (!strcmp(iface, wl_shm_interface.name))
        shm = wl_registry_bind(r, name, &wl_shm_interface, 1);
    else if (!strcmp(iface, zwlr_layer_shell_v1_interface.name))
        layer_shell = wl_registry_bind(r, name, &zwlr_layer_shell_v1_interface, 1);
}
static void reg_remove(void *data, struct wl_registry *r, uint32_t name) {}
static const struct wl_registry_listener reg_listener = { reg_global, reg_remove };

/* ---- main ------------------------------------------------------------------------------ */
static int open_fifo(const char *kind_name)
{
    const char *dir = getenv("XDG_RUNTIME_DIR");
    char path[512];
    snprintf(path, sizeof path, "%s/wob-%s.sock", dir ? dir : "/tmp", kind_name);
    struct stat st;
    if (stat(path, &st) == 0 && !S_ISFIFO(st.st_mode))
        unlink(path);
    if (mkfifo(path, 0660) < 0 && errno != EEXIST) {
        perror(path);
        return -1;
    }
    return open(path, O_RDWR | O_NONBLOCK | O_CLOEXEC);    /* RDWR: no EOF when a writer leaves */
}

int main(void)
{
    display = wl_display_connect(NULL);
    if (!display) {
        fprintf(stderr, "rg35xxh-osd: no Wayland display\n");
        return 1;
    }
    struct wl_registry *reg = wl_display_get_registry(display);
    wl_registry_add_listener(reg, &reg_listener, NULL);
    wl_display_roundtrip(display);
    if (!compositor || !shm || !layer_shell) {
        fprintf(stderr, "rg35xxh-osd: compositor lacks wl_shm or wlr-layer-shell\n");
        return 1;
    }
    if (make_buffers() < 0) {
        perror("rg35xxh-osd: buffers");
        return 1;
    }

    struct pollfd pfd[2 + NKINDS];
    pfd[0] = (struct pollfd){ wl_display_get_fd(display), POLLIN, 0 };
    int timer = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC | TFD_NONBLOCK);
    pfd[1] = (struct pollfd){ timer, POLLIN, 0 };
    char line[NKINDS][64];
    int len[NKINDS] = {0};
    for (int k = 0; k < NKINDS; k++) {
        pfd[2 + k] = (struct pollfd){ open_fifo(KINDS[k].name), POLLIN, 0 };
        if (pfd[2 + k].fd < 0)
            return 1;
    }

    for (;;) {
        while (wl_display_prepare_read(display) != 0)
            wl_display_dispatch_pending(display);
        wl_display_flush(display);
        if (poll(pfd, 2 + NKINDS, -1) < 0) {
            wl_display_cancel_read(display);
            if (errno == EINTR)
                continue;
            return 1;
        }
        if (pfd[0].revents & POLLIN) {
            if (wl_display_read_events(display) < 0)
                return 1;
        } else {
            wl_display_cancel_read(display);
        }
        if (pfd[0].revents & (POLLERR | POLLHUP))
            return 1;
        wl_display_dispatch_pending(display);

        if (pfd[1].revents & POLLIN) {
            uint64_t n;
            if (read(timer, &n, sizeof n) == sizeof n)
                hide();
        }
        for (int k = 0; k < NKINDS; k++) {
            if (!(pfd[2 + k].revents & POLLIN))
                continue;
            char buf[256];
            ssize_t got;
            int newest = -1;
            while ((got = read(pfd[2 + k].fd, buf, sizeof buf)) > 0)
                for (ssize_t i = 0; i < got; i++) {
                    if (buf[i] == '\n') {
                        line[k][len[k]] = 0;
                        if (len[k] > 0)
                            newest = atoi(line[k]);
                        len[k] = 0;
                    } else if (len[k] < (int)sizeof line[k] - 1) {
                        line[k][len[k]++] = buf[i];
                    }
                }
            if (newest >= 0) {
                kind = k;
                level = newest < 0 ? 0 : newest > 100 ? 100 : newest;
                struct itimerspec t = { {0, 0}, {TIMEOUT_MS / 1000, (TIMEOUT_MS % 1000) * 1000000L} };
                timerfd_settime(timer, 0, &t, NULL);
                show();
            }
        }
    }
}
