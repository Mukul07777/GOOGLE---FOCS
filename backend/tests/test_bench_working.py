"""scripts/bench_working.py: labelled handwritten solutions in, honest numbers out (exact step, slip vs gap, no false alarms)."""
import importlib.util
import io
import sys
from pathlib import Path

from PIL import Image

from app.services import vision

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bench_working.py"


def test_the_benchmark_counts_exact_steps_and_kinds(tmp_path, monkeypatch):
    for name in ("a.png", "b.png", "c.png"):
        buf = io.BytesIO()
        Image.new("RGB", (200, 120), "white").save(buf, format="PNG")
        (tmp_path / name).write_bytes(buf.getvalue())
    (tmp_path / "labels.csv").write_text(
        "file,question,options,answer,chosen,first_wrong,kind\n"
        'a.png,"Torque?","10|17.3|20|5",A,B,2,gap\n'
        'b.png,"Current?",,,,3,slip\n'
        'c.png,"Range?",,,,right,\n', encoding="utf-8")
    answers = iter([
        {"verdict": "wrong", "first_wrong": 1, "error_type": "concept", "steps": [{"text": "s1", "ok": True}, {"text": "s2", "ok": False}]},
        {"verdict": "wrong", "first_wrong": 0, "error_type": "arithmetic", "steps": [{"text": "s1", "ok": False}, {"text": "s2"}, {"text": "s3"}]},
        {"verdict": "right", "steps": [{"text": "s1", "ok": True}]},
    ])
    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "models", lambda: ["gemini-test"])
    monkeypatch.setattr(vision, "read_json", lambda *a, **k: next(answers))
    spec = importlib.util.spec_from_file_location("bench_working", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(sys, "argv", ["bench_working.py", str(tmp_path)])
    mod.main()
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Found the exact wrong step:** 1/2 = 50%" in summary  # a: step 2 found; b: said 1, truth 3
    assert "no false alarm): 1/1" in summary and "Slip told apart from a gap in an idea: 2/2" in summary
    assert (tmp_path / "results.csv").read_text(encoding="utf-8").count("\n") == 4


def test_fermat_becomes_a_labelled_folder_and_is_scored_on_catching_mistakes(tmp_path, monkeypatch):
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), "white").save(buf, format="PNG")
    records = [{"orig_q": "Solve $2x+3=7$", "orig_a": "x = 2", "image": {"bytes": buf.getvalue()}, "has_error": True},
               {"orig_q": "Area of a 4 cm square?", "orig_a": "16 cm^2", "image": buf.getvalue(), "has_error": False},
               {"orig_q": "", "orig_a": "", "image": buf.getvalue(), "has_error": True}]  # no question: left out
    spec = importlib.util.spec_from_file_location("bench_working", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.fermat_to_folder(records, tmp_path) == 2
    labels = (tmp_path / "labels.csv").read_text(encoding="utf-8")
    assert "fermat0001.jpg,Solve $2x+3=7$,,,,wrong,,x = 2" in labels and "fermat0002.jpg" in labels and ",right,," in labels
    prompts = []
    answers = iter([{"verdict": "wrong", "first_wrong": 1, "error_type": "arithmetic", "steps": [{"text": "a"}, {"text": "b"}]},
                    {"verdict": "right", "steps": [{"text": "a", "ok": True}]}])
    monkeypatch.setattr(vision, "available", lambda: True)
    monkeypatch.setattr(vision, "models", lambda: ["gemini-test"])
    monkeypatch.setattr(vision, "read_json", lambda imgs, prompt, *a, **k: prompts.append(prompt) or next(answers))
    monkeypatch.setattr(sys, "argv", ["bench_working.py", str(tmp_path)])
    mod.main()
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Caught that the working has a mistake: 1/1" in summary and "no false alarm): 1/1" in summary
    assert "Found the exact wrong step:** –" in summary  # FERMAT doesn't say which line
    assert all("paper" in p.lower() for p in prompts)  # .jpg pictures are checked as photos of paper
