"""The evidence tools: the real-board benchmark, the learning-study report and cost per lecture hour."""
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from tests.conftest import board_png

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def test_study_report_difference_interval_and_limitations(tmp_path):
    import study_report

    res = study_report.compare([5, 6, 4, 5, 6, 5], [3, 4, 3, 2, 4, 3])
    assert res["diff"] == pytest.approx(5.1667 - 3.1667, abs=1e-3)
    lo, hi = res["ci"]
    assert 0 < lo < res["diff"] < hi  # a clear gap: the interval stays above 0
    assert res["d"] > 1
    assert study_report.compare([5], [3, 4]) is None  # too few to say anything

    csv = tmp_path / "results.csv"
    csv.write_text("participant,group,immediate,next_day,notes\nP01,focs,5,4,\nP02,control,3,,missed day 2\n"
                   "P03,focs,6,5,\nP04,control,4,3,\n", encoding="utf-8")
    text = study_report.report(study_report.load(csv))
    assert "Right after the lecture" in text and "Next day" in text
    assert "pilot" in text  # 4 students: says so
    assert "missed the next-day test" in text
    csv.write_text("participant,group,immediate,next_day\nP01,teacher,5,4\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        study_report.load(csv)


def test_cost_per_lecture_hour_counts_only_calls_during_the_lecture(client):
    import demo_metrics
    from app.core.database import SessionLocal
    from app.models._util import utcnow
    from app.models.llm_call import LlmCall
    from app.models.session import StudySession

    with SessionLocal() as db:
        start = utcnow() - timedelta(hours=3)
        lecture = StudySession(user_id=987654, source="screen", started_at=start, ended_at=start + timedelta(minutes=30), is_active=False)
        db.add(lecture)
        db.add_all([
            LlmCall(user_id=987654, feature="notes", model="m", cost_usd=0.010, created_at=start + timedelta(minutes=5)),
            LlmCall(user_id=987654, feature="revision", model="m", cost_usd=0.005, created_at=start + timedelta(minutes=31)),  # written on ending
            LlmCall(user_id=987654, feature="doubt", model="m", cost_usd=1.0, created_at=start + timedelta(hours=2)),  # after: not this lecture
            LlmCall(user_id=987655, feature="notes", model="m", cost_usd=1.0, created_at=start + timedelta(minutes=5)),  # someone else (an id no test user reaches)
        ])
        db.commit()
        rows = [r for r in demo_metrics.lecture_costs(db, days=1) if r["session_id"] == lecture.id]
    assert len(rows) == 1 and rows[0]["calls"] == 2
    assert rows[0]["usd"] == pytest.approx(0.015)
    s = demo_metrics.summarize_costs(rows, usd_inr=88.0)
    assert s["usd_per_hour"] == pytest.approx(0.03)  # half an hour for $0.015
    assert s["inr_per_hour"] == pytest.approx(2.64)


def test_real_benchmark_drafts_refuses_unchecked_and_scores_checked(tmp_path):
    import benchmark_ocr

    real = tmp_path / "real"
    (real / "screen").mkdir(parents=True)
    lines = ["Ohm's law", "V = I R"]
    (real / "screen" / "nptel-01.png").write_bytes(board_png(lines))
    benchmark_ocr.main(["--draft", str(real)])
    drafted = json.loads((real / "labels.draft.json").read_text(encoding="utf-8"))
    assert drafted[0]["file"] == "screen/nptel-01.png" and drafted[0]["checked"] is False and drafted[0]["style"] == "screen"

    (real / "labels.json").write_text(json.dumps(drafted), encoding="utf-8")
    with pytest.raises(SystemExit, match="draft"):  # never scored against its own guess
        benchmark_ocr.main(["--set", "real", "--bench", str(real), "--out", str(tmp_path)])

    labels = [{**drafted[0], "lines": lines, "checked": True, "source": "https://nptel.ac.in/x", "licence": "CC BY-SA 4.0"}]
    (real / "labels.json").write_text(json.dumps(labels), encoding="utf-8")
    benchmark_ocr.main(["--set", "real", "--bench", str(real), "--out", str(tmp_path)])
    out = json.loads((tmp_path / "benchmark_real.json").read_text(encoding="utf-8"))
    assert out["set"] == "real" and out["images"] == 1 and out["licences"] == {"CC BY-SA 4.0": 1}
    assert "auto" in out["engines"] and out["engines"]["auto"]["cer"] < 0.2
