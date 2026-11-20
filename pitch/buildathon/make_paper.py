"""A phone photo of a student's rough working on notebook paper (blue ink, a slight tilt, desk around it).

    python buildathon/make_paper.py   -> public/bt/paper.jpg (what the film uploads) and public/bt/paper-flat.png

The working makes the classic torque mistake: r F cos(theta) instead of r F sin(theta).
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "bt"
FONT = "C:/Windows/Fonts/Inkfree.ttf"
INK = (28, 48, 132)
random.seed(7)

W, H = 1500, 1900
LINE = 74


def paper() -> Image.Image:
    im = Image.new("RGB", (W, H), (250, 248, 240))
    d = ImageDraw.Draw(im)
    for y in range(230, H, LINE):
        d.line([(0, y), (W, y)], fill=(176, 200, 226), width=2)
    d.line([(150, 0), (150, H)], fill=(226, 140, 140), width=3)
    # paper grain
    noise = Image.effect_noise((W, H), 9).convert("L")
    im = Image.blend(im, Image.merge("RGB", (noise, noise, noise)), 0.05)
    return im


def write(d: ImageDraw.ImageDraw, x: int, row: int, text: str, size: int = 62, jitter: float = 3.0):
    f = ImageFont.truetype(FONT, size)
    y = 230 + row * LINE - size - 4
    for ch in text:
        dy = random.uniform(-jitter, jitter)
        d.text((x, y + dy), ch, font=f, fill=INK)
        x += d.textlength(ch, font=f) + random.uniform(-0.6, 1.2)
    return x


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    im = paper()
    d = ImageDraw.Draw(im)
    write(d, 190, 1, "Q. F = 10 N on a 2 m spanner, at 30°.  Torque = ?", 54)
    # a little diagram: spanner, force at 30 degrees, the angle marked
    ox, oy = 260, 520
    d.line([(ox, oy), (ox + 520, oy)], fill=INK, width=7)
    d.ellipse([ox - 22, oy - 22, ox + 22, oy + 22], outline=INK, width=6)
    fx, fy = ox + 520, oy
    a = math.radians(30)
    d.line([(fx, fy), (fx + 230 * math.cos(a), fy - 230 * math.sin(a))], fill=INK, width=6)
    tip = (fx + 230 * math.cos(a), fy - 230 * math.sin(a))
    d.polygon([tip, (tip[0] - 34, tip[1] + 2), (tip[0] - 14, tip[1] + 30)], fill=INK)
    d.arc([fx - 80, fy - 80, fx + 80, fy + 80], start=-30, end=0, fill=INK, width=4)
    f = ImageFont.truetype(FONT, 46)
    d.text((fx + 92, fy - 50), "30°", font=f, fill=INK)
    d.text((ox + 220, oy + 14), "r = 2 m", font=f, fill=INK)
    d.text((tip[0] + 10, tip[1] - 40), "F = 10 N", font=f, fill=INK)

    write(d, 190, 9, "1)   τ = r F cos θ")
    write(d, 190, 10, "2)   τ = 2 × 10 × cos 30°")
    write(d, 190, 11, "3)   τ = 20 × 0.866")
    write(d, 190, 12, "4)   τ = 17.3 N·m")
    x = write(d, 190, 14, "Ans:  (B)  17.3 N m", 66)
    d.ellipse([170, 230 + 13 * LINE + 2, x + 24, 230 + 14 * LINE + 16], outline=INK, width=4)
    write(d, 900, 17, "- Riya (sample)", 44, 2)

    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im.save(OUT / "paper-flat.png")

    # the phone photo: a desk, the page tilted a little, soft light from the top left
    desk = Image.new("RGB", (1800, 2300), (120, 98, 78))
    grain = Image.effect_noise(desk.size, 22).convert("L").filter(ImageFilter.GaussianBlur(1.2))
    desk = Image.blend(desk, Image.merge("RGB", (grain, grain, grain)), 0.12)
    page = im.rotate(-3.2, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0))
    mask = Image.new("L", im.size, 255).rotate(-3.2, expand=True, resample=Image.BICUBIC)
    shadow = Image.new("RGBA", desk.size, (0, 0, 0, 0))
    sh = Image.new("RGBA", page.size, (0, 0, 0, 120))
    shadow.paste(sh, (165, 215), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))
    desk = Image.alpha_composite(desk.convert("RGBA"), shadow)
    desk.paste(page, (140, 180), mask)
    light = Image.radial_gradient("L").resize(desk.size).point(lambda v: 255 - int(v * 0.45))
    desk = Image.composite(desk, Image.new("RGBA", desk.size, (30, 24, 18, 255)), light)
    desk.convert("RGB").resize((1350, 1725), Image.LANCZOS).save(OUT / "paper.jpg", quality=88)
    print("wrote", OUT / "paper.jpg")


if __name__ == "__main__":
    main()
