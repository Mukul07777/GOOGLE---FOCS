"""Contact sheet of a clip at given seconds: python buildathon/sheet.py <clip> <out.png> t1 t2 ..."""
import subprocess, sys
from pathlib import Path
import imageio_ffmpeg
from PIL import Image
FF = imageio_ffmpeg.get_ffmpeg_exe()
clip, out, *ts = sys.argv[1:]
src = Path(__file__).resolve().parents[1] / "public" / "clips" / f"{clip}.mp4"
tiles = []
for i, t in enumerate(ts):
    f = Path(out).with_name(f"_t{i}.png")
    subprocess.run([FF, "-loglevel", "error", "-y", "-ss", t, "-i", str(src), "-frames:v", "1", "-vf", "scale=720:-1", str(f)], check=True)
    im = Image.open(f); im.load(); tiles.append(im.copy()); im.close(); f.unlink()
cols = 2; w, h = tiles[0].size; rows = (len(tiles) + 1) // 2
sheet = Image.new("RGB", (w * cols, h * rows), "white")
for i, im in enumerate(tiles): sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(out)
