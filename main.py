import math
import os
import struct
import zlib

W = 1024
H = 1024
PIX = bytearray(W * H * 3)

_seed = 12345


def rnd():
    global _seed
    _seed = (_seed * 1103515245 + 12345) & 0x7FFFFFFF
    return _seed / 0x7FFFFFFF


def lerp(a, b, t):
    return a + (b - a) * t


def blend_px(x, y, r, g, b, a):
    if x < 0 or x >= W or y < 0 or y >= H:
        return
    i = (y * W + x) * 3
    if a >= 255:
        PIX[i] = r
        PIX[i + 1] = g
        PIX[i + 2] = b
        return
    ia = 255 - a
    PIX[i] = (r * a + PIX[i] * ia) // 255
    PIX[i + 1] = (g * a + PIX[i + 1] * ia) // 255
    PIX[i + 2] = (b * a + PIX[i + 2] * ia) // 255


def span(y, x0, x1, r, g, b, a):
    if y < 0 or y >= H:
        return
    if x0 < 0:
        x0 = 0
    if x1 >= W:
        x1 = W - 1
    if x1 < x0:
        return
    i = (y * W + x0) * 3
    if a >= 255:
        for _ in range(x0, x1 + 1):
            PIX[i] = r
            PIX[i + 1] = g
            PIX[i + 2] = b
            i += 3
        return
    ia = 255 - a
    for _ in range(x0, x1 + 1):
        PIX[i] = (r * a + PIX[i] * ia) // 255
        PIX[i + 1] = (g * a + PIX[i + 1] * ia) // 255
        PIX[i + 2] = (b * a + PIX[i + 2] * ia) // 255
        i += 3


def chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def save_png(path):
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += PIX[y * W * 3:(y + 1) * W * 3]
    data = chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + data)


FONT = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
}


def draw_text(x, y, s, scale, r, g, b, a):
    cx = x
    for ch in s:
        glyph = FONT.get(ch)
        if glyph:
            for row in range(7):
                bits = glyph[row]
                for col in range(5):
                    if bits[col] == "1":
                        for dy in range(scale):
                            span(y + row * scale + dy, cx + col * scale, cx + col * scale + scale - 1, r, g, b, a)
        cx += 6 * scale


def line(x0, y0, x1, y1, r, g, b, a):
    dx = x1 - x0
    dy = y1 - y0
    steps = int(max(abs(dx), abs(dy)))
    if steps == 0:
        blend_px(int(x0), int(y0), r, g, b, a)
        return
    for i in range(steps + 1):
        t = i / steps
        blend_px(int(x0 + dx * t), int(y0 + dy * t), r, g, b, a)


def poly(points, r, g, b, a):
    ys = [p[1] for p in points]
    y0 = max(0, int(min(ys)))
    y1 = min(H - 1, int(max(ys)))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            span(y, int(xs[k]), int(xs[k + 1]), r, g, b, a)


def ellipse(cx, cy, rx, ry, r, g, b, a):
    for y in range(cy - ry, cy + ry + 1):
        dy = (y - cy) / ry
        v = 1.0 - dy * dy
        if v < 0:
            continue
        dx = math.sqrt(v) * rx
        span(y, int(cx - dx), int(cx + dx), r, g, b, a)


def circle(cx, cy, rad, r, g, b, a):
    ellipse(cx, cy, rad, rad, r, g, b, a)


def ring(cx, cy, rx, ry, t, r, g, b, a):
    for y in range(cy - ry, cy + ry + 1):
        dy = (y - cy) / ry
        v = 1.0 - dy * dy
        if v < 0:
            continue
        dx = math.sqrt(v) * rx
        ry2 = ry - t
        rx2 = rx - t
        if ry2 <= 0 or rx2 <= 0:
            span(y, int(cx - dx), int(cx + dx), r, g, b, a)
            continue
        dy2 = (y - cy) / ry2
        v2 = 1.0 - dy2 * dy2
        if v2 > 0:
            dx2 = math.sqrt(v2) * rx2
            span(y, int(cx - dx), int(cx - dx2), r, g, b, a)
            span(y, int(cx + dx2), int(cx + dx), r, g, b, a)
        else:
            span(y, int(cx - dx), int(cx + dx), r, g, b, a)


def rot_rect(cx, cy, w, h, ang):
    c = math.cos(ang)
    s = math.sin(ang)
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append((cx + dx * c - dy * s, cy + dx * s + dy * c))
    return pts


def rounded_rect(x0, y0, x1, y1, rad, r, g, b, a):
    for y in range(y0, y1 + 1):
        xa = x0
        xb = x1
        if y < y0 + rad:
            dy = (y0 + rad) - y
            dx = math.sqrt(max(0, rad * rad - dy * dy))
            xa = int(x0 + rad - dx)
            xb = int(x1 - rad + dx)
        elif y > y1 - rad:
            dy = y - (y1 - rad)
            dx = math.sqrt(max(0, rad * rad - dy * dy))
            xa = int(x0 + rad - dx)
            xb = int(x1 - rad + dx)
        span(y, xa, xb, r, g, b, a)


def rounded_rect_vgrad(x0, y0, x1, y1, rad, top, bot, a):
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, y1 - y0)
        r = int(lerp(top[0], bot[0], t))
        g = int(lerp(top[1], bot[1], t))
        b = int(lerp(top[2], bot[2], t))
        xa = x0
        xb = x1
        if y < y0 + rad:
            dy = (y0 + rad) - y
            dx = math.sqrt(max(0, rad * rad - dy * dy))
            xa = int(x0 + rad - dx)
            xb = int(x1 - rad + dx)
        elif y > y1 - rad:
            dy = y - (y1 - rad)
            dx = math.sqrt(max(0, rad * rad - dy * dy))
            xa = int(x0 + rad - dx)
            xb = int(x1 - rad + dx)
        span(y, xa, xb, r, g, b, a)


def background():
    top = (233, 229, 223)
    bot = (205, 199, 191)
    gcx, gcy, gr = 640, 400, 430
    for y in range(H):
        t = y / (H - 1)
        br = int(lerp(top[0], bot[0], t))
        bg = int(lerp(top[1], bot[1], t))
        bb = int(lerp(top[2], bot[2], t))
        for x in range(W):
            dx = x - gcx
            dy = y - gcy
            d = math.sqrt(dx * dx + dy * dy) / gr
            if d < 1.0:
                f = (1.0 - d) * 0.30
                r = int(br + (255 - br) * f)
                g = int(bg + (250 - bg) * f)
                b = int(bb + (240 - bb) * f)
            else:
                r, g, b = br, bg, bb
            i = (y * W + x) * 3
            PIX[i] = r
            PIX[i + 1] = g
            PIX[i + 2] = b


def canopy():
    cx, cy, rx, ry = 700, 168, 205, 92
    for y in range(cy - ry, cy + 1):
        dy = (y - cy) / ry
        v = 1.0 - dy * dy
        if v < 0:
            continue
        hw = int(rx * math.sqrt(v))
        x0 = cx - hw
        x1 = cx + hw
        for p in range(6):
            pa = cx - rx + p * (2 * rx) / 6
            pb = cx - rx + (p + 1) * (2 * rx) / 6
            xa = max(x0, int(pa))
            xb = min(x1, int(pb) - 1)
            if xb >= xa:
                if p % 2 == 0:
                    col = (198, 52, 44)
                else:
                    col = (244, 232, 210)
                span(y, xa, xb, col[0], col[1], col[2], 255)
    for t in range(0, 181):
        ang = math.pi * t / 180.0
        x = int(cx + rx * math.cos(ang))
        y = int(cy - ry * math.sin(ang))
        blend_px(x, y, 150, 40, 34, 255)
        blend_px(x, y + 1, 150, 40, 34, 255)


def toast():
    cx, cy, ang = 700, 372, -0.24
    c = math.cos(ang)
    s = math.sin(ang)
    crust = rot_rect(cx, cy, 150, 130, ang)
    poly(crust, 176, 118, 58, 255)
    crumb = rot_rect(cx, cy, 132, 112, ang)
    poly(crumb, 232, 186, 110, 255)
    for _ in range(110):
        lx = (rnd() * 2 - 1) * 58
        ly = (rnd() * 2 - 1) * 48
        x = int(cx + lx * c - ly * s)
        y = int(cy + lx * s + ly * c)
        blend_px(x, y, 190, 140, 70, 255)
        blend_px(x + 1, y, 190, 140, 70, 255)
    bx = cx - (-66) * s
    by = cy + (-66) * c
    butter = rot_rect(bx, by, 48, 20, ang)
    poly(butter, 250, 226, 130, 255)
    gx = bx - 10 * c - (-4) * s
    gy = by - 10 * s + (-4) * c
    gloss = rot_rect(gx, gy, 26, 5, ang)
    poly(gloss, 255, 246, 200, 255)


def scene():
    background()
    ellipse(440, 852, 155, 15, 60, 55, 50, 55)
    ellipse(730, 848, 150, 15, 60, 55, 50, 50)
    ellipse(730, 822, 148, 30, 245, 244, 242, 255)
    ring(730, 822, 148, 30, 4, 200, 198, 194, 255)
    ellipse(730, 822, 132, 24, 252, 251, 250, 255)
    ellipse(712, 812, 58, 11, 90, 80, 70, 45)
    rounded_rect_vgrad(300, 600, 580, 840, 26, (226, 228, 232), (158, 162, 168), 255)
    for yy in range(630, 830, 26):
        line(312, yy, 568, yy, 255, 255, 255, 18)
    rounded_rect(352, 604, 428, 620, 6, 52, 54, 58, 255)
    rounded_rect(468, 604, 544, 620, 6, 52, 54, 58, 255)
    rounded_rect(578, 700, 592, 736, 5, 120, 124, 130, 255)
    circle(585, 718, 9, 90, 94, 100, 255)
    circle(440, 748, 27, 240, 241, 243, 255)
    ring(440, 748, 27, 27, 3, 120, 124, 130, 255)
    line(440, 748, 458, 728, 200, 40, 35, 255)
    circle(440, 748, 4, 90, 94, 100, 255)
    circle(548, 668, 6, 220, 45, 35, 255)
    circle(546, 666, 2, 255, 150, 140, 255)
    draw_text(361, 668, "TOAST-AIR", 3, 52, 54, 58, 255)
    draw_text(381, 792, "MODEL P-01", 2, 90, 94, 100, 255)
    canopy()
    rim = (522, 606, 700, 794, 878)
    top = ((612, 327), (648, 318), (684, 309), (721, 300), (757, 291))
    for i in range(5):
        line(rim[i], 170, top[i][0], top[i][1], 90, 85, 80, 220)
    toast()


def main():
    scene()
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out, exist_ok=True)
    save_png(os.path.join(out, "entry.png"))


main()
