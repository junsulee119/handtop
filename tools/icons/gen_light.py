"""Bright-background (light taskbar) variants of the input-mode icons.
Same pixel art and glass shape as gen_rainbow.py; dark drawing, pastel glass, stronger ring."""
import colorsys
from PIL import Image, ImageDraw
import gen_base as M
N = M.N
LIGHT = {  # name: (glass tint, ring)
    "desktop": ("#a9b6d0", "#5b6d91"),
    "gamepad": ("#9fcfab", "#3f8a55"),
    "bt":      ("#a3bde6", "#3d68b0"),
    "wired":   ("#e2b88f", "#b0753f"),
}
INK, INK_SHADE, ACCENT = "#2b303b", "#4f5869", "#3d7bd9"
SAT, VAL, STRIPE_A, GAP_A, TINT_A = 0.65, 0.88, 0.75, 0.15, 0.55

def render(icon):
    name, parts, _bg, _ring, _acc, external = icon
    tint, ring = (M.rgb(c) for c in LIGHT[name])
    gl = set(); g = {}
    for art, top, left in parts:
        for yy, r in enumerate(M.rows(art)):
            for xx, c in enumerate(r):
                if c != ".":
                    g[(xx + left, yy + top)] = c
                if c in M.SOLID:
                    gl.add((xx + left, yy + top))
    halo = {(x + dx, y + dy) for (x, y) in gl for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    for y in range(N):
        for x in range(N):
            outer = M.coverage(x, y, 0, 4.5); inner = M.coverage(x, y, 1, 3.5)
            if external:
                d = x + y
                if d % 4 < 2 and (x, y) not in halo:
                    r, gg, b = colorsys.hsv_to_rgb(d / (2 * N - 2) * 0.85, SAT, VAL)
                    fill, fa_ = (round(r * 255), round(gg * 255), round(b * 255)), STRIPE_A
                else:
                    fill, fa_ = tint, GAP_A
            else:
                fill, fa_ = tint, TINT_A
            fa = inner * fa_; ra = outer - inner; a = fa + ra
            if a <= 0:
                continue
            col = tuple(round((fill[k] * fa + ring[k] * ra) / a) for k in range(3))
            im.putpixel((x, y), col + (round(min(a, 1) * 255),))
    low = {}
    for (x, y), c in g.items():
        if c == "W":
            low[x] = max(low.get(x, -1), y)
    for (x, y), c in g.items():
        if c == "W":
            im.putpixel((x, y), M.rgb(INK_SHADE if low[x] == y else INK) + (255,))
        elif c == "A":
            im.putpixel((x, y), M.rgb(ACCENT) + (255,))
        elif c in M.COLORS_LIGHT:
            im.putpixel((x, y), M.rgb(M.COLORS_LIGHT[c]) + (255,))
    return im

def svg(im, name):
    rects = []
    for y in range(N):
        for x in range(N):
            r, g, b, a = im.getpixel((x, y))
            if a:
                op = "" if a == 255 else f' fill-opacity="{a/255:.3f}"'
                rects.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="#{r:02x}{g:02x}{b:02x}"{op}/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{N}" height="{N}" viewBox="0 0 {N} {N}" shape-rendering="crispEdges">\n'
            f'<!-- Handtop input-mode indicator: {name}, light-background variant. Pixel art 23x23. -->\n' + "\n".join(rects) + "\n</svg>\n")

if __name__ == "__main__":
    ims = []
    for ic in M.ICONS:
        im = render(ic); ims.append(im)
        im.save(f"inputmode-{ic[0]}-light.png")
        open(f"inputmode-{ic[0]}-light.svg", "w").write(svg(im, ic[0]))
    dark = [Image.open(f"inputmode-{ic[0]}.png") for ic in M.ICONS]
    BAR_H, W, cell = 31, 200, 8 * N
    sheet = Image.new("RGB", (W * 4 + 4 * (cell + 6) + 40, 2 * (cell + 16) + 10), "#0e1015")
    for row, (label, barbg, fg, line, icons) in enumerate([
            ("dark bar", "#1a1e26", "#e8eaee", "#333a48", dark),
            ("light bar", "#eceff4", "#2b303b", "#c9ced8", ims)]):
        y0 = 10 + row * (cell + 16)
        bar = Image.new("RGB", (W, BAR_H), barbg)
        bd = ImageDraw.Draw(bar); bd.line([(0, 0), (W, 0)], fill=line); bd.text((6, 10), label, fill=fg)
        for i, im in enumerate(icons):
            bar.paste(im, (90 + i * 26, (BAR_H - N) // 2), im)
        sheet.paste(bar.resize((W * 4, BAR_H * 4), Image.NEAREST), (10, y0 + (cell - BAR_H * 4) // 2))
        for i, im in enumerate(icons):
            t = Image.new("RGB", (cell, cell), barbg); big = im.resize((cell, cell), Image.NEAREST)
            t.paste(big, (0, 0), big); sheet.paste(t, (W * 4 + 25 + i * (cell + 6), y0))
    sheet.save("preview-light.png")
