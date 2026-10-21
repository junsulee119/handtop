from PIL import Image, ImageDraw
N = 23
def rows(a):
    r = a.strip("\n").split("\n"); w = len(r[0])
    assert all(len(x) == w for x in r), r
    return r
MOUSE = """
..WWWWW..
.WAAWSSW.
WAAAWSSSW
WAAAWSSSW
WAAAWSSSW
WWWWWWWWW
WSSSSSSSW
WSSSSSSSW
WSSSSSSSW
WSSSSSSSW
WSSSSSSSW
WSSSSSSSW
WSSSSSSSW
.WSSSSSW.
..WWWWW..
"""
# RG35XX H: D-pad (holes show the glass) and coloured X/A/B/Y (blue/red/yellow/green, Anbernic
# layout X top, A right, B bottom, Y left), dark screen D with a 2-px glare g, 3x3 sticks K/C.
HANDHELD = """
.WWWWWWWWWWWWWWW.
WWWWWWWWWWWWWWWWW
WWBWWDDDDDDDWWxWW
WBBBWDDDDgDDWyWaW
WWBWWDDDDDgDWWbWW
WWWWWDDDDDDDWWWWW
WKKKWDDDDDDDWKKKW
WKCKWDDDDDDDWKCKW
WKKKWDDDDDDDWKKKW
WWWWWWWWWWWWWWWWW
.WWWWWWWWWWWWWWW.
"""
SMALLHANDHELD = """
.WWWWWWWWWWWWWWW.
WWBWWDDDDDDDWWxWW
WBBBWDDDDgDDWyWaW
WWBWWDDDDDgDWWbWW
WWWWWDDDDDDDWWWWW
WKKKWDDDDDDDWKKKW
WKCKWDDDDDDDWKCKW
WKKKWDDDDDDDWKKKW
.WWWWWWWWWWWWWWW.
"""
WAVES = """
...WWWWWWW...
..W.......W..
.W..WWWWW..W.
...W.....W...
.....WWW.....
"""
CABLE = """
...............W.W.....
..............WWWWW....
..............WWWWW....
...............WWW.....
................W......
...........WWWWWW......
...........W...........
"""
def centred(art, top):
    w = len(rows(art)[0]); assert w % 2 == 1, w
    return (art, top, (N - w) // 2)
ICONS = [  # name, parts, bg, ring, accent, external
    ("desktop", [centred(MOUSE, 4)], "#3d4a63", "#5b6d91", "#9fc3ff", False),
    ("gamepad", [centred(HANDHELD, 6)], "#3d6a4a", "#5b9469", None, False),
    ("bt", [centred(WAVES, 4), centred(SMALLHANDHELD, 10)], "#3d5a8a", "#5f80bd", None, True),
    ("wired", [(CABLE, 3, 0), centred(SMALLHANDHELD, 10)], "#8a5f3d", "#c08a5c", None, True),
]
WHITE, SHADE = "#e8eaee", "#aab3c2"
SOLID = "WAKCDgxyab"            # opaque pixels (the rainbow halo is drawn around these)
COLORS = {"D": "#161a22", "g": "#464e5e", "K": "#3c4350", "C": "#808998",
          "x": "#4a8ce6", "a": "#e24646", "b": "#f0c83c", "y": "#50be64"}
COLORS_LIGHT = dict(COLORS, D="#cfd6e2", g="#f4f6fa", K="#8a93a3", C="#d5dae3")
def rgb(h): return tuple(int(h[i:i+2], 16) for i in (1, 3, 5))

def coverage(x, y, inset, r, ss=8):
    lo, hi = inset, N - inset; n = 0
    for i in range(ss):
        for j in range(ss):
            px, py = x + (i + .5) / ss, y + (j + .5) / ss
            cx = min(max(px, lo + r), hi - r); cy = min(max(py, lo + r), hi - r)
            if lo <= px <= hi and lo <= py <= hi and (px - cx) ** 2 + (py - cy) ** 2 <= r * r:
                n += 1
    return n / ss / ss

PATTERNS = {   # glass tint alpha per inside pixel for EXTERNAL modes; local modes stay solid 0.45
    "solid":   lambda x, y: 0.45,
    "dither":  lambda x, y: 0.55 if (x + y) % 2 == 0 else 0.12,
    "stripes": lambda x, y: 0.55 if (x + y) % 4 < 2 else 0.12,
    "fade":    lambda x, y: 0.65 - 0.55 * (y - 1) / (N - 3),
}

def render(icon, pattern):
    name, parts, bg, ringc, accent, external = icon
    alpha = PATTERNS[pattern] if external else PATTERNS["solid"]
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    for y in range(N):
        for x in range(N):
            outer = coverage(x, y, 0, 4.5); inner = coverage(x, y, 1, 3.5)
            fa = inner * alpha(x, y); ra = outer - inner; a = fa + ra
            if a <= 0:
                continue
            col = tuple(round((rgb(bg)[k] * fa + rgb(ringc)[k] * ra) / a) for k in range(3))
            im.putpixel((x, y), col + (round(min(a, 1) * 255),))
    g = {}
    for art, top, left in parts:
        for y, r in enumerate(rows(art)):
            for x, c in enumerate(r):
                if c != ".":
                    g[(x + left, y + top)] = c
    low = {}
    for (x, y), c in g.items():
        if c == "W":
            low[x] = max(low.get(x, -1), y)
    for (x, y), c in g.items():
        if c == "W":
            im.putpixel((x, y), rgb(SHADE if low[x] == y else WHITE) + (255,))
        elif c == "A":
            im.putpixel((x, y), rgb(accent) + (255,))
        elif c in COLORS:
            im.putpixel((x, y), rgb(COLORS[c]) + (255,))
        # "S"/"B": leave the glass showing through
    return im

BAR_H, W = 31, 200
sheet_rows = []
for p in ("solid", "dither", "stripes", "fade"):
    ims = [render(ic, p) for ic in ICONS]
    for ic, im in zip(ICONS, ims):
        im.save(f"{p}-{ic[0]}.png")
    sheet_rows.append((p, ims))
cell = 8 * N
sheet = Image.new("RGB", (W * 4 + 4 * (cell + 6) + 40, len(sheet_rows) * (cell + 16) + 10), "#0e1015")
for row, (p, ims) in enumerate(sheet_rows):
    y0 = 10 + row * (cell + 16)
    bar = Image.new("RGB", (W, BAR_H), "#1a1e26")
    bd = ImageDraw.Draw(bar); bd.line([(0, 0), (W, 0)], fill="#333a48")
    bd.text((4, 10), "external: " + p, fill="#e8eaee")
    for i, im in enumerate(ims):
        bar.paste(im, (96 + i * 26, (BAR_H - N) // 2), im)
    sheet.paste(bar.resize((W * 4, BAR_H * 4), Image.NEAREST), (10, y0 + (cell - BAR_H * 4) // 2))
    for i, im in enumerate(ims):
        t = Image.new("RGB", (cell, cell), "#1a1e26"); big = im.resize((cell, cell), Image.NEAREST)
        t.paste(big, (0, 0), big); sheet.paste(t, (W * 4 + 25 + i * (cell + 6), y0))
sheet.save("preview-23.png"); print(sheet.size)
