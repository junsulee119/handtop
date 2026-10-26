/*
 * rg35xxh-bootsplash: the animated Handtop boot screen.
 *
 * Left: the Handtop logo with keys lighting up on its keyboard like someone typing (walks across
 * the keys, ~8 frames/s). Right: a box with the live boot log -- systemd's "Starting / Started /
 * Finished ... / Failed to start" messages from the journal (journalctl -f, PID 1), one line per
 * unit: ".." while it starts, "OK" when done, "FAIL" in red (kept visible). Newest at the bottom.
 *
 * Draws straight into the framebuffer (/dev/fb0, XRGB8888) from early boot; the text console is
 * detached from it first (rg35xxh-bootlogo show). Stops on SIGTERM (rg35xxh-bootlogo done, once
 * the desktop owns the screen) or after MAX_SECONDS. Only changed rows are copied to the screen.
 * Plain C, libc only: the logo, layout and pre-rendered font come from assets.h
 * (tools/icons/gen_logo.py). Build: src/bootsplash/Makefile. Test without a screen:
 * rg35xxh-bootsplash --dump out.ppm <frame> < journal-lines.txt
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include "assets.h"

#define FRAME_MS 120
#define MAX_SECONDS 180
#define MAX_LINES 160
#define LINE_H 14
#define LOG_X (BOX_X0 + 12)
#define LOG_Y (BOX_Y0 + 40)
#define TEXT_X (LOG_X + 5 * GLYPH_W)
#define LOG_ROWS ((BOX_Y1 - 8 - LOG_Y) / LINE_H)
#define TEXT_COLS ((BOX_X1 - 12 - TEXT_X) / GLYPH_W)
#define LIT_KEYS 3
#define LIT_STEP 7

static uint32_t canvas[SCR_W * SCR_H];
static uint8_t *fb;
static int fb_stride, fb_w, fb_h, off_x, off_y;
static volatile sig_atomic_t stop;

enum { WAIT, OK, FAIL };
static struct line { int state; char unit[96]; char text[160]; } lines[MAX_LINES];
static int nlines;

/* ---- drawing -------------------------------------------------------------------------- */
static void fill(int x0, int y0, int w, int h, uint32_t c)
{
	for (int y = y0; y < y0 + h; y++)
		for (int x = x0; x < x0 + w; x++)
			if (x >= 0 && y >= 0 && x < SCR_W && y < SCR_H)
				canvas[y * SCR_W + x] = c;
}

static uint32_t mix(uint32_t bg, uint32_t fg, int a)
{
	uint32_t r = (((fg >> 16) & 255) * a + ((bg >> 16) & 255) * (255 - a)) / 255;
	uint32_t g = (((fg >> 8) & 255) * a + ((bg >> 8) & 255) * (255 - a)) / 255;
	uint32_t b = ((fg & 255) * a + (bg & 255) * (255 - a)) / 255;
	return r << 16 | g << 8 | b;
}

static void alpha_blit(const uint8_t *src, int sw, int sh, int x0, int y0, uint32_t col)
{
	for (int y = 0; y < sh; y++)
		for (int x = 0; x < sw; x++) {
			int a = src[y * sw + x], px = x0 + x, py = y0 + y;
			if (a && px >= 0 && py >= 0 && px < SCR_W && py < SCR_H)
				canvas[py * SCR_W + px] = mix(canvas[py * SCR_W + px], col, a);
		}
}

/* Text in the pre-rendered mono font; UTF-8 "…" is the only non-ASCII glyph. */
static void text(const char *s, int x, int y, uint32_t col, int maxcols)
{
	for (int n = 0; *s && n < maxcols; n++) {
		int g;
		if ((unsigned char)s[0] == 0xe2 && (unsigned char)s[1] == 0x80 && (unsigned char)s[2] == 0xa6) {
			g = GLYPH_ELLIPSIS;
			s += 3;
		} else {
			int c = (unsigned char)*s++;
			g = (c >= 32 && c < 127) ? c - GLYPH_FIRST : '?' - GLYPH_FIRST;
		}
		alpha_blit(GLYPHS + g * GLYPH_W * GLYPH_H, GLYPH_W, GLYPH_H, x + n * GLYPH_W, y, col);
	}
}

static void rounded_box(int x0, int y0, int x1, int y1, int r, uint32_t fillc, uint32_t edge)
{
	for (int y = y0; y <= y1; y++) {
		int dy = y < y0 + r ? y0 + r - y : (y > y1 - r ? y - (y1 - r) : 0);
		int in = 0;
		while (in < r && (r - in) * (r - in) + dy * dy > r * r)
			in++;
		if (!dy)
			in = 0;
		fill(x0 + in, y, x1 - x0 + 1 - 2 * in, 1, (y == y0 || y == y1) ? edge : fillc);
		canvas[y * SCR_W + x0 + in] = edge;
		canvas[y * SCR_W + x1 - in] = edge;
	}
}

static void draw_logo(int frame)
{
	for (int y = 0; y < LOGO_N; y++)
		for (int x = 0; x < LOGO_N; x++) {
			int i = LOGO_IDX[y * LOGO_N + x];
			fill(LOGO_X + x * LOGO_Z, LOGO_Y + y * LOGO_Z, LOGO_Z, LOGO_Z, i ? LOGO_PAL[i] : COL_BG);
		}
	for (int j = 0; j < LIT_KEYS; j++) {             /* the "typing" keys */
		const uint8_t *k = KEYS + 4 * ((frame + j * LIT_STEP) % NKEYS);
		fill(LOGO_X + k[0] * LOGO_Z, LOGO_Y + k[1] * LOGO_Z, k[2] * LOGO_Z, k[3] * LOGO_Z, COL_LIT);
	}
}

static void draw_static(void)
{
	fill(0, 0, SCR_W, SCR_H, COL_BG);
	for (int y = 0; y < WORD_H; y++)
		for (int x = 0; x < WORD_W; x++) {
			int i = WORD_IDX[y * WORD_W + x];
			if (i)
				fill(WORD_X + x * WORD_Z, WORD_Y + y * WORD_Z, WORD_Z, WORD_Z, WORD_PAL[i]);
		}
	rounded_box(BOX_X0, BOX_Y0, BOX_X1, BOX_Y1, 8, COL_BOX, COL_BOX_EDGE);
	alpha_blit(TITLE, TITLE_W, TITLE_H, BOX_X0 + 12, BOX_Y0 + 8, COL_TITLE);
	fill(BOX_X0 + 1, BOX_Y0 + 31, BOX_X1 - BOX_X0 - 1, 1, COL_BOX_EDGE);
}

static void draw_log(void)
{
	fill(BOX_X0 + 1, LOG_Y, BOX_X1 - BOX_X0 - 1, LOG_ROWS * LINE_H, COL_BOX);
	int first = nlines > LOG_ROWS ? nlines - LOG_ROWS : 0;
	for (int i = first; i < nlines; i++) {
		int y = LOG_Y + (i - first) * LINE_H;
		struct line *l = &lines[i];
		static const char *tag[] = { " ..", " OK", "FAIL" };
		static const uint32_t tagc[] = { COL_WAIT, COL_OK, COL_FAIL };
		text(tag[l->state], LOG_X, y, tagc[l->state], 4);
		char buf[200];
		if ((int)strlen(l->text) > TEXT_COLS) {         /* cut with an ellipsis */
			snprintf(buf, sizeof buf, "%.*s\xe2\x80\xa6", TEXT_COLS - 1, l->text);
		} else {
			snprintf(buf, sizeof buf, "%s", l->text);
		}
		text(buf, TEXT_X, y, l->state == WAIT ? COL_DIM : (l->state == FAIL ? COL_FAIL : COL_TEXT), TEXT_COLS);
	}
}

static void present(int y0, int y1)
{
	for (int y = y0; y <= y1 && y < SCR_H; y++)
		if (y + off_y >= 0 && y + off_y < fb_h)
			memcpy(fb + (size_t)(y + off_y) * fb_stride + (size_t)off_x * 4, canvas + y * SCR_W,
			       (size_t)(fb_w < SCR_W ? fb_w : SCR_W) * 4);
}

/* ---- boot log ------------------------------------------------------------------------- */
static struct line *find(const char *unit)
{
	for (int i = nlines - 1; i >= 0; i--)
		if (!strcmp(lines[i].unit, unit))
			return &lines[i];
	return NULL;
}

static struct line *add(const char *unit)
{
	if (nlines == MAX_LINES) {                       /* keep the newest; FAIL lines stay readable */
		memmove(lines, lines + 1, sizeof lines[0] * (MAX_LINES - 1));
		nlines--;
	}
	struct line *l = &lines[nlines++];
	memset(l, 0, sizeof *l);
	snprintf(l->unit, sizeof l->unit, "%s", unit);
	return l;
}

/* "Started foo.service - Foo Daemon." -> unit "foo.service", text "Foo Daemon" */
static int parse(char *s)
{
	static const struct { const char *verb; int state; } V[] = {
		{ "Starting ", WAIT }, { "Started ", OK }, { "Finished ", OK }, { "Mounted ", OK },
		{ "Reached target ", OK }, { "Listening on ", OK }, { "Activated ", OK },
		{ "Failed to start ", FAIL }, { "Failed to mount ", FAIL }, { "Failed to listen on ", FAIL },
	};
	int state = -1;
	for (size_t i = 0; i < sizeof V / sizeof V[0]; i++)
		if (!strncmp(s, V[i].verb, strlen(V[i].verb))) {
			state = V[i].state;
			s += strlen(V[i].verb);
			break;
		}
	if (state < 0)
		return 0;
	size_t n = strlen(s);
	while (n && (s[n - 1] == '.' || s[n - 1] == '\n' || s[n - 1] == ' '))
		s[--n] = 0;                                   /* "..." / "." at the end */
	char *desc = strstr(s, " - ");
	if (desc) {
		*desc = 0;
		desc += 3;
	} else {
		desc = s;
	}
	struct line *l = find(s);
	if (!l || (l->state != WAIT && state == WAIT))
		l = add(s);
	if (l->state != FAIL)
		l->state = state;
	snprintf(l->text, sizeof l->text, "%s", desc);
	return 1;
}

static pid_t start_journal(int *fd)
{
	int p[2];
	if (pipe2(p, O_CLOEXEC) < 0)
		return -1;
	pid_t pid = fork();
	if (pid == 0) {
		dup2(p[1], 1);
		int null = open("/dev/null", O_WRONLY);
		if (null >= 0)
			dup2(null, 2);
		execlp("journalctl", "journalctl", "-b", "-f", "-n", "all", "-o", "cat", "--no-pager",
		       "_PID=1", (char *)NULL);
		_exit(127);
	}
	close(p[1]);
	if (pid < 0) {
		close(p[0]);
		return -1;
	}
	fcntl(p[0], F_SETFL, O_NONBLOCK);
	*fd = p[0];
	return pid;
}

static long now_ms(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return t.tv_sec * 1000 + t.tv_nsec / 1000000;
}

static void on_signal(int sig)
{
	(void)sig;
	stop = 1;
}

/* Test without a screen: rg35xxh-bootsplash --dump out.ppm FRAME < journal-lines.txt */
static int dump(const char *path, int frame)
{
	char s[512];
	while (fgets(s, sizeof s, stdin))
		parse(s);
	draw_static();
	draw_logo(frame);
	draw_log();
	FILE *o = fopen(path, "wb");
	if (!o)
		return 1;
	fprintf(o, "P6\n%d %d\n255\n", SCR_W, SCR_H);
	for (int i = 0; i < SCR_W * SCR_H; i++) {
		unsigned char px[3] = { canvas[i] >> 16, canvas[i] >> 8, canvas[i] };
		fwrite(px, 1, 3, o);
	}
	return fclose(o) != 0;
}

int main(int argc, char **argv)
{
	if (argc == 4 && !strcmp(argv[1], "--dump"))
		return dump(argv[2], atoi(argv[3]));
	int fd = open("/dev/fb0", O_RDWR | O_CLOEXEC);
	struct fb_var_screeninfo v;
	struct fb_fix_screeninfo f;
	if (fd < 0 || ioctl(fd, FBIOGET_VSCREENINFO, &v) < 0 || ioctl(fd, FBIOGET_FSCREENINFO, &f) < 0
	    || v.bits_per_pixel != 32) {
		fprintf(stderr, "rg35xxh-bootsplash: no 32-bit framebuffer\n");
		return 1;
	}
	fb = mmap(NULL, f.smem_len, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	if (fb == MAP_FAILED)
		return 1;
	fb_stride = f.line_length;
	fb_w = v.xres;
	fb_h = v.yres;
	off_x = fb_w > SCR_W ? (fb_w - SCR_W) / 2 : 0;    /* centred on a bigger screen */
	off_y = fb_h > SCR_H ? (fb_h - SCR_H) / 2 : 0;

	struct sigaction sa = { .sa_handler = on_signal };
	sigaction(SIGTERM, &sa, NULL);
	sigaction(SIGINT, &sa, NULL);
	signal(SIGPIPE, SIG_IGN);

	draw_static();
	draw_logo(0);
	draw_log();
	present(0, SCR_H - 1);

	int jfd = -1;
	pid_t jpid = -1;
	long start = now_ms(), next_frame = start + FRAME_MS, retry = start;
	int frame = 0;
	char buf[4096];
	size_t have = 0;
	while (!stop && now_ms() - start < MAX_SECONDS * 1000L) {
		if (jpid < 0 && now_ms() >= retry) {             /* journald may not be up yet */
			jpid = start_journal(&jfd);
			retry = now_ms() + 1000;
		}
		struct pollfd p = { .fd = jfd, .events = POLLIN };
		int wait = (int)(next_frame - now_ms());
		poll(&p, jpid > 0 ? 1 : 0, wait > 0 ? wait : 0);
		int changed = 0;
		if (jpid > 0 && (p.revents & (POLLIN | POLLHUP))) {
			ssize_t n = read(jfd, buf + have, sizeof buf - 1 - have);
			if (n > 0) {
				have += n;
				buf[have] = 0;
				char *s = buf, *nl;
				while ((nl = strchr(s, '\n'))) {
					*nl = 0;
					changed |= parse(s);
					s = nl + 1;
				}
				have = strlen(s);
				memmove(buf, s, have);
				if (have == sizeof buf - 1)
					have = 0;                       /* an absurdly long line: drop it */
			} else if (n == 0 || (errno != EAGAIN && errno != EINTR)) {
				close(jfd);                             /* journalctl ended: start it again */
				waitpid(jpid, NULL, 0);
				jpid = -1;
				jfd = -1;
				have = 0;
			}
		}
		if (changed) {
			draw_log();
			present(LOG_Y, LOG_Y + LOG_ROWS * LINE_H);
		}
		if (now_ms() >= next_frame) {
			draw_logo(++frame);
			present(LOGO_Y, LOGO_Y + LOGO_N * LOGO_Z - 1);
			next_frame += FRAME_MS;
			if (next_frame < now_ms())
				next_frame = now_ms() + FRAME_MS;
		}
	}
	if (jpid > 0) {
		kill(jpid, SIGTERM);
		waitpid(jpid, NULL, 0);
	}
	return 0;
}
