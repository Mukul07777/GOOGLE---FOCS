"""Images the shoot uploads: a mentor's proof (a sample rank card, marked as one) for each sample mentor.

    python make_assets.py    -> pitch/shoot/assets/proof-<key>.png
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "assets"
FONTS = Path("C:/Windows/Fonts")

PROOFS = {
    "aditya": ("Aditya Verma", "JEE (Advanced) 2023", "All India Rank 1,147", "Allotted: IIT Delhi, Electrical Engg."),
    "sneha": ("Sneha Iyer", "JEE (Advanced) 2022", "All India Rank 612", "Allotted: IIT Bombay, Computer Science"),
    "ananya": ("Ananya Rao", "UPSC Civil Services 2024", "Called for Personality Test", "Roll no. 08xxxxx"),
    "meera": ("Meera Nair", "NEET (UG) 2024", "All India Rank 3,402", "Allotted: MAMC, New Delhi"),
    "rohan": ("Rohan Gupta", "JEE (Advanced) 2024", "All India Rank 2,310", "Allotted: IIT Kanpur, Mechanical Engg."),
}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def card(name: str, exam: str, rank: str, line: str) -> Image.Image:
    im = Image.new("RGB", (1200, 760), "#f7f6f2")
    d = ImageDraw.Draw(im)
    d.rectangle([24, 24, 1176, 736], outline="#1b1b1b", width=3)
    d.rectangle([24, 24, 1176, 130], fill="#1b1b1b")
    d.text((60, 52), "SCORE CARD", font=font("arialbd.ttf", 44), fill="#f7f6f2")
    d.text((820, 62), exam, font=font("arial.ttf", 30), fill="#f7f6f2")
    d.rectangle([60, 180, 300, 470], outline="#1b1b1b", width=2)
    d.text((112, 300), "PHOTO", font=font("arial.ttf", 34), fill="#9a9a9a")
    rows = [("Candidate", name), ("Result", rank), ("", line), ("Status", "Qualified")]
    y = 190
    for k, v in rows:
        d.text((350, y), k, font=font("arial.ttf", 26), fill="#6b6b6b")
        d.text((560, y - 4), v, font=font("arialbd.ttf", 34), fill="#1b1b1b")
        y += 80
    # never mistaken for a real document
    d.text((60, 560), "SAMPLE FOR THE FOCS DEMO", font=font("arialbd.ttf", 54), fill="#c0301c")
    d.text((60, 640), "Not a real score card. Real mentors upload theirs; Focs deletes it after review.", font=font("arial.ttf", 26), fill="#6b6b6b")
    return im


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for key, spec in PROOFS.items():
        card(*spec).save(OUT / f"proof-{key}.png")
        print("wrote", OUT / f"proof-{key}.png")
