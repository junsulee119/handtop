"""PNG checks for theme images.

check() is plain Python (no decoder): signature, every chunk's length and CRC, IHDR values, and
the image data inflated with a hard size limit, so a file that claims a huge size or inflates
without end is refused before any decoder sees it. decode() then lets GdkPixbuf (on the device)
decode the whole image; imgops.py does the scaling and shifting."""
import struct
import zlib

SIG = b"\x89PNG\r\n\x1a\n"
# colour type -> (allowed bit depths, samples per pixel)
_TYPES = {0: ((1, 2, 4, 8, 16), 1), 2: ((8, 16), 3), 3: ((1, 2, 4, 8), 1), 4: ((8, 16), 2),
          6: ((8, 16), 4)}


class BadPNG(ValueError):
    pass


def check(data, max_size=(4096, 4096)):
    """Return (width, height) of a well-formed PNG; raise BadPNG otherwise."""
    if not data.startswith(SIG):
        raise BadPNG("not a PNG file")
    pos, ihdr, idat, seen_end = len(SIG), None, [], False
    while pos < len(data):
        if pos + 8 > len(data):
            raise BadPNG("cut off")
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        if length > 0x7FFFFFFF or pos + 12 + length > len(data):
            raise BadPNG("cut off or bad chunk length")
        body = data[pos + 8:pos + 8 + length]
        crc = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]
        if zlib.crc32(ctype + body) & 0xFFFFFFFF != crc:
            raise BadPNG(f"damaged ({ctype.decode('latin-1')} checksum)")
        if ihdr is None and ctype != b"IHDR":
            raise BadPNG("IHDR is not first")
        if ctype == b"IHDR":
            if ihdr is not None or length != 13:
                raise BadPNG("bad IHDR")
            ihdr = struct.unpack(">IIBBBBB", body)
        elif ctype == b"IDAT":
            idat.append(body)
        elif ctype == b"IEND":
            seen_end = True
            break
        pos += 12 + length
    if not seen_end:
        raise BadPNG("no IEND (cut off)")
    w, h, depth, color, comp, filt, interlace = ihdr
    if not (1 <= w <= max_size[0] and 1 <= h <= max_size[1]):
        raise BadPNG(f"{w}x{h} is outside the allowed size")
    if color not in _TYPES or depth not in _TYPES[color][0] or comp or filt or interlace > 1:
        raise BadPNG("unsupported PNG format")
    if not idat:
        raise BadPNG("no image data")
    bits = depth * _TYPES[color][1]
    limit = _raw_size(w, h, bits, interlace)
    d = zlib.decompressobj()
    out = 0
    for chunk in idat:
        try:
            out += len(d.decompress(chunk, limit + 1 - out))
        except zlib.error:
            raise BadPNG("image data is damaged") from None
        if out > limit or d.unconsumed_tail:
            raise BadPNG("image data larger than its size says")
    if not d.eof:
        raise BadPNG("image data cut off")
    if out != limit:
        raise BadPNG("image data does not match its size")
    return w, h


def _raw_size(w, h, bits, interlace):
    """Exact inflated size: one filter byte per row plus the row's bytes (per Adam7 pass)."""
    def rows(pw, ph):
        return 0 if pw == 0 or ph == 0 else ph * (1 + (pw * bits + 7) // 8)
    if not interlace:
        return rows(w, h)
    passes = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2),
              (0, 1, 1, 2))
    return sum(rows((w - x0 + dx - 1) // dx, (h - y0 + dy - 1) // dy) for x0, y0, dx, dy in passes)


def decode(path):
    """Decode fully with GdkPixbuf; return the pixbuf. Raises BadPNG."""
    from .imgops import load
    try:
        return load(path)
    except Exception as e:                       # GLib.Error and friends
        raise BadPNG(f"could not be decoded ({e})") from None
