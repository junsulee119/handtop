"""Shake frames for the input-mode icons: the drawing (not the glass) shifted dx px sideways.
Writes inputmode-<mode>[-light]-shake<dx>.png for dx in SHIFTS. Run next to gen_*.py."""
import gen_base as M
import gen_rainbow as R    # dark set renderer (variant used: saturation 0.65, value 0.58)
import gen_light as L
SHIFTS = (-2, -1, 1, 2)

def shifted(icon, dx):
    name, parts, *rest = icon
    return (name, [(art, top, left + dx) for art, top, left in parts], *rest)

if __name__ == "__main__":
    for ic in M.ICONS:
        for dx in SHIFTS:
            R.render(shifted(ic, dx), 0.65, 0.58, False).save(f"inputmode-{ic[0]}-shake{dx}.png")
            L.render(shifted(ic, dx)).save(f"inputmode-{ic[0]}-light-shake{dx}.png")
