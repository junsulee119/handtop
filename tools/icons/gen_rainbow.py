import colorsys
from PIL import Image, ImageDraw
import gen_base as M   # base arts, coverage(), ICONS
N = M.N
def hexrgb(r, g, b): return (round(r*255), round(g*255), round(b*255))

def render(icon, sat, val, per_stripe):
    name, parts, bg, ringc, accent, external = icon
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    gl = set()
    for art, top, left in parts:
        for yy, r in enumerate(M.rows(art)):
            for xx, c in enumerate(r):
                if c in M.SOLID:
                    gl.add((xx + left, yy + top))
    halo = {(x + dx, y + dy) for (x, y) in gl for dx in (-1, 0, 1) for dy in (-1, 0, 1)} if HALO else set()
    for y in range(N):
        for x in range(N):
            outer = M.coverage(x, y, 0, 4.5); inner = M.coverage(x, y, 1, 3.5)
            if external:
                d = x + y                                   # diagonal position 0..44
                strong = d % 4 < 2 and (x, y) not in halo
                if strong:
                    t = (d // 4) / 11 if per_stripe else d / (2 * N - 2)
                    fill = hexrgb(*colorsys.hsv_to_rgb(t * 0.85, sat, val)); fa_ = ALPHA
                else:
                    fill = M.rgb(bg); fa_ = 0.12
            else:
                fill = M.rgb(bg); fa_ = 0.45
            fa = inner * fa_; ra = outer - inner; a = fa + ra
            if a <= 0:
                continue
            col = tuple(round((fill[k] * fa + M.rgb(ringc)[k] * ra) / a) for k in range(3))
            im.putpixel((x, y), col + (round(min(a, 1) * 255),))
    g = {}
    for art, top, left in parts:
        for yy, r in enumerate(M.rows(art)):
            for xx, c in enumerate(r):
                if c != ".":
                    g[(xx + left, yy + top)] = c
    low = {}
    for (x, y), c in g.items():
        if c == "W":
            low[x] = max(low.get(x, -1), y)
    for (x, y), c in g.items():
        if c == "W":
            im.putpixel((x, y), M.rgb(M.SHADE if low[x] == y else M.WHITE) + (255,))
        elif c == "A":
            im.putpixel((x, y), M.rgb(accent) + (255,))
        elif c in M.COLORS:
            im.putpixel((x, y), M.rgb(M.COLORS[c]) + (255,))
    # The 1 px halo around the drawing (where the stripes stop) is an opaque dark outline, so the
    # white handheld stays visible on a light background too (External Controller mode picker).
    if external and HALO:
        for (x, y) in halo - set(g):
            if 0 <= x < N and 0 <= y < N and M.coverage(x, y, 1, 3.5) >= 0.99:
                im.putpixel((x, y), M.rgb(OUTLINE) + (255,))
    return im

HALO, ALPHA = True, 0.7
OUTLINE = "#161a22"            # halo colour (dark, opaque)
VARIANTS = [("gradient .55", 0.55, 0.50, False),
            ("gradient .65", 0.65, 0.50, False),
            ("gradient .65 brighter", 0.65, 0.58, False)]
BAR_H, W, cell = 31, 210, 8 * N
sheet = Image.new("RGB", (W * 4 + 4 * (cell + 6) + 40, len(VARIANTS) * (cell + 16) + 10), "#0e1015")
for row, (label, s, v, ps) in enumerate(VARIANTS):
    ims = [render(ic, s, v, ps) for ic in M.ICONS]
    for ic, im in zip(M.ICONS, ims):
        im.save(f"grad65-{row}-{ic[0]}.png")
    y0 = 10 + row * (cell + 16)
    bar = Image.new("RGB", (W, BAR_H), "#1a1e26")
    bd = ImageDraw.Draw(bar); bd.line([(0, 0), (W, 0)], fill="#333a48"); bd.text((4, 10), label, fill="#e8eaee")
    for i, im in enumerate(ims):
        bar.paste(im, (104 + i * 26, (BAR_H - N) // 2), im)
    sheet.paste(bar.resize((W * 4, BAR_H * 4), Image.NEAREST), (10, y0 + (cell - BAR_H * 4) // 2))
    for i, im in enumerate(ims):
        t = Image.new("RGB", (cell, cell), "#1a1e26"); big = im.resize((cell, cell), Image.NEAREST)
        t.paste(big, (0, 0), big); sheet.paste(t, (W * 4 + 25 + i * (cell + 6), y0))
sheet.save("preview-rainbow4.png")
