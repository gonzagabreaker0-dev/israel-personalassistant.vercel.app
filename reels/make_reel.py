"""Render a 30-second vertical (1080x1920) reel from a single campus photo.

Usage: python3 make_reel.py <photo.jpg> <out.mp4>
"""
import math
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H, FPS, SECONDS = 1080, 1920, 30, 30
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
GOLD = (255, 200, 40)
GREEN = (0, 110, 50)

# (start, end, text lines) — captions fade in/out within their window
CAPTIONS = [
    (0.6, 5.5, ["CARAGA STATE", "UNIVERSITY"], 110, "title"),
    (6.0, 12.0, ["Campus Life"], 90, "lower"),
    (12.5, 19.5, ["Under the", "acacia trees"], 90, "lower"),
    (20.0, 25.5, ["Sports  •  Friends  •  Memories"], 50, "lower"),
]

# Camera keyframes: (time, center_x 0..1, center_y 0..1, zoom). zoom=1 shows
# the full photo height (minus the phone watermark strip at the bottom).
KEYS = [
    (0, 0.60, 0.42, 1.55),
    (6, 0.45, 0.50, 1.25),
    (12, 0.22, 0.52, 1.35),
    (19, 0.75, 0.45, 1.30),
    (25, 0.50, 0.50, 1.00),
    (30, 0.50, 0.50, 1.08),
]


def ease(t):
    return t * t * (3 - 2 * t)


def camera(t):
    for (t0, x0, y0, z0), (t1, x1, y1, z1) in zip(KEYS, KEYS[1:]):
        if t <= t1:
            k = ease((t - t0) / (t1 - t0))
            return x0 + (x1 - x0) * k, y0 + (y1 - y0) * k, z0 + (z1 - z0) * k
    return KEYS[-1][1:]


def fade(t, start, end, d=0.6):
    if t < start or t > end:
        return 0.0
    return min(1.0, (t - start) / d, (end - t) / d)


def draw_caption(frame, lines, size, style, alpha, t, start):
    font = ImageFont.truetype(FONT_BOLD, size)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rise = int((1 - ease(min(1.0, (t - start) / 0.8))) * 60)
    line_h = int(size * 1.15)
    block_h = line_h * len(lines)
    top = (H // 2 - block_h // 2 - 250 if style == "title" else H - 520) + rise
    a = int(255 * alpha)
    if style != "title":
        widest = max(d.textlength(s, font=font) for s in lines)
        pad = 40
        d.rounded_rectangle(
            [W / 2 - widest / 2 - pad, top - 25, W / 2 + widest / 2 + pad, top + block_h + 25],
            radius=28, fill=(*GREEN, int(190 * alpha)),
        )
    for i, s in enumerate(lines):
        x = (W - d.textlength(s, font=font)) / 2
        y = top + i * line_h
        d.text((x + 4, y + 5), s, font=font, fill=(0, 0, 0, int(160 * alpha)))
        d.text((x, y), s, font=font, fill=(*(GOLD if style == "title" else (255, 255, 255)), a))
    if style == "title":
        bar_w = int(500 * ease(min(1.0, (t - start) / 1.2)))
        y = top + block_h + 30
        d.rectangle([W / 2 - bar_w / 2, y, W / 2 + bar_w / 2, y + 10], fill=(*GOLD, a))
        sub = ImageFont.truetype(FONT_REG, 46)
        s = "Caraga Region, Philippines"
        d.text(((W - d.textlength(s, font=sub)) / 2, y + 40), s, font=sub, fill=(255, 255, 255, a))
    frame.alpha_composite(layer)


def end_card(frame, t):
    a = fade(t, 25.6, 31, d=0.8)
    if a == 0:
        return
    overlay = Image.new("RGBA", (W, H), (0, 40, 20, int(170 * a)))
    frame.alpha_composite(overlay)
    d = ImageDraw.Draw(frame)
    big = ImageFont.truetype(FONT_BOLD, 120)
    mid = ImageFont.truetype(FONT_BOLD, 62)
    small = ImageFont.truetype(FONT_REG, 48)
    pulse = 1 + 0.03 * math.sin(t * 4)
    big = ImageFont.truetype(FONT_BOLD, int(120 * pulse))
    rows = [
        ("CSU PRIDE", big, GOLD, H / 2 - 220),
        ("Proud to be a CSUan!", mid, (255, 255, 255), H / 2 - 40),
        ("#CaragaStateU  #CSU  #CampusLife", small, (220, 255, 220), H / 2 + 80),
    ]
    for s, f, col, y in rows:
        x = (W - d.textlength(s, font=f)) / 2
        d.text((x + 4, y + 5), s, font=f, fill=(0, 0, 0, int(150 * a)))
        d.text((x, y), s, font=f, fill=(*col, int(255 * a)))


class Leaves:
    def __init__(self, n=28, seed=7):
        rnd = random.Random(seed)
        self.items = [
            dict(x=rnd.uniform(0, W), y=rnd.uniform(-H, H), vy=rnd.uniform(70, 160),
                 sway=rnd.uniform(20, 60), ph=rnd.uniform(0, 6.28), r=rnd.uniform(10, 22),
                 col=rnd.choice([(120, 160, 60), (170, 140, 70), (90, 140, 50)]))
            for _ in range(n)
        ]

    def draw(self, frame, t):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for p in self.items:
            y = (p["y"] + p["vy"] * t) % (H + 200) - 100
            x = p["x"] + p["sway"] * math.sin(t * 1.5 + p["ph"])
            r = p["r"]
            ang = t * 2 + p["ph"]
            dx, dy = r * math.cos(ang), r * 0.45 * math.sin(ang)
            d.ellipse([x - abs(dx) - 4, y - r * 0.4 - abs(dy), x + abs(dx) + 4, y + r * 0.4 + abs(dy)],
                      fill=(*p["col"], 200))
        frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1)))


def main(src, out):
    photo = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    pw, ph = photo.size
    photo = photo.crop((0, 0, pw, int(ph * 0.92)))  # drop phone watermark strip
    pw, ph = photo.size
    # Gentle grade: a bit more contrast and saturation for a reel look
    from PIL import ImageEnhance
    photo = ImageEnhance.Color(photo).enhance(1.25)
    photo = ImageEnhance.Contrast(photo).enhance(1.1)

    vignette = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vignette)
    for i in range(60):
        vd.rectangle([i * 6, i * 10, W - i * 6, H - i * 10], fill=int(i * 255 / 60))
    vignette = vignette.filter(ImageFilter.GaussianBlur(80))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    dark.putalpha(Image.eval(vignette, lambda v: int((255 - v) * 0.55)))

    leaves = Leaves()
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo", "-t", str(SECONDS),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", "-movflags", "+faststart", out],
        stdin=subprocess.PIPE,
    )
    for i in range(FPS * SECONDS):
        t = i / FPS
        cx, cy, z = camera(t)
        ch = ph / z
        cw = ch * W / H
        x0 = min(max(cx * pw - cw / 2, 0), pw - cw)
        y0 = min(max(cy * ph - ch / 2, 0), ph - ch)
        frame = photo.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)).convert("RGBA")
        frame.alpha_composite(dark)
        leaves.draw(frame, t)
        for start, end, lines, size, style in CAPTIONS:
            a = fade(t, start, end)
            if a:
                draw_caption(frame, lines, size, style, a, t, start)
        end_card(frame, t)
        black = min(1.0, max(0.0, 1 - t / 0.5))  # fade in from black
        if black:
            frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * black))))
        ff.stdin.write(frame.convert("RGB").tobytes())
    ff.stdin.close()
    sys.exit(ff.wait())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
