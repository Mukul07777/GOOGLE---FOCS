"""Deterministic fallbacks used when no LLM is reachable.

They are intentionally simple, but they keep every feature usable offline: notes are
organised OCR, quizzes are cloze questions built from your own notes, and so on.
"""
from __future__ import annotations

import random
import re
from collections import Counter
from typing import Any

from app.services.math_text import clean_option
from app.services.text_utils import clean_ocr, guess_subject, has_math

OFFLINE_NOTE = "> _Quick notes, read straight off the board: the AI couldn't rewrite these just now (it was busy, or your AI allowance is used up)._"
_STOP = set("""the a an and or of to in on for with from by is are was were be been this that these those it its as
at into than then there their which what when where who how why can will would should could may might must also not
no yes if else so such each any all both more most other some only own same too very just using use used we you they
he she i our your his her them us let given find value hence therefore thus
key ideas idea formulas formula worked example exam tip notes board overview concepts concept""".split())


def _lines(md: str) -> list[str]:
    out = []
    for raw in (md or "").splitlines():
        line = re.sub(r"^[#>*\-\d.)\s]+", "", raw).strip()
        line = line.replace("**", "").replace("`", "")
        if len(line) > 3:
            out.append(line)
    return out


def _key_terms(text: str, k: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z\-']{3,}", text)
    counts = Counter(w for w in words if w.lower() not in _STOP)
    return [w for w, _ in counts.most_common(k)]


def _formula_lines(lines: list[str]) -> list[str]:
    return [l for l in lines if "=" in l and has_math(l) and len(l) <= 90]


def notes(cleaned_ocr: str) -> dict[str, Any]:
    lines = [l for l in clean_ocr(cleaned_ocr).splitlines() if len(l) > 2]
    if not lines:
        return {"is_lecture": False, "source": "offline"}
    formulas = _formula_lines(lines)
    ideas = [l for l in lines if l not in formulas]
    heading = next((l for l in lines if 1 <= len(l.split()) <= 6 and sum(c.isalpha() for c in l) > len(l) * 0.6), None)
    subject = guess_subject(cleaned_ocr)
    topic = (heading or f"{subject} board").strip(" :-")[:60]
    parts = []
    if ideas:
        parts.append("### Key ideas\n" + "\n".join(f"- {l}" for l in ideas[:14]))
    if formulas:
        parts.append("### Formulas\n" + "\n".join(f"- `{f}`" for f in formulas[:10]))
    parts.append(OFFLINE_NOTE)
    return {
        "is_lecture": True, "topic": topic, "subject": subject, "notes_md": "\n\n".join(parts),
        "key_terms": _key_terms(cleaned_ocr, 8), "formulas": formulas[:10], "source": "offline",
    }


def checkpoint(prev_notes_md: str, prev_topic: str) -> dict[str, Any] | None:
    q = quiz(prev_notes_md, n_mcq=1, n_tf=0, n_subj=0)
    if not q["mcq"]:
        return None
    m = q["mcq"][0]
    return {"question": m["q"], "options": m["options"], "answer_index": m["answer_index"],
            "explanation": m["explanation"], "topic": prev_topic, "source": "offline"}


# Prompt scaffolding, table rows and "mistake" lines are not facts a question can be built from.
_NOT_FACT = re.compile(r"^(syllabus topic|chapter|topic|subject|class|mistake|common mistake|note|no notes)\b[^:]{0,20}:", re.I)


def _fact_lines(material: str) -> list[str]:
    out = []
    for raw in (material or "").splitlines():
        if raw.strip().startswith("|") or raw.strip().startswith("#"):
            continue
        out.extend(l for l in _lines(raw) if not _NOT_FACT.match(l) and len(l.split()) >= 4)
    return out


def quiz(material: str, n_mcq: int = 5, n_tf: int = 3, n_subj: int = 1) -> dict[str, Any]:
    rng = random.Random(len(material))
    lines = _fact_lines(material)
    terms = _key_terms("\n".join(lines), 24)
    mcq: list[dict[str, Any]] = []
    for line in lines:
        if len(mcq) >= n_mcq:
            break
        present = [t for t in terms if re.search(rf"\b{re.escape(t)}\b", line)]
        if not present or len(terms) < 4:
            continue
        answer = present[0]
        stem = answer.lower().rstrip("s")
        distractors = [t for t in terms if t.lower().rstrip("s") != stem]
        rng.shuffle(distractors)
        options = distractors[:3] + [answer]
        rng.shuffle(options)
        blanked = re.sub(rf"\b{re.escape(answer)}\b", "_____", line, count=1)
        mcq.append({"q": f"Fill in the blank: {blanked}", "options": options,
                    "answer_index": options.index(answer), "explanation": f"From the notes: “{line}”"})

    tf: list[dict[str, Any]] = []
    swaps = [("+", "-"), ("×", "/"), ("²", "³"), ("increases", "decreases"), ("directly", "inversely")]
    for line in _formula_lines(lines) + lines:
        if len(tf) >= n_tf:
            break
        if rng.random() < 0.5:
            tf.append({"statement": line, "answer": True, "explanation": "This is exactly what your notes state."})
            continue
        for a, b in swaps:
            if a in line:
                tf.append({"statement": line.replace(a, b, 1), "answer": False,
                           "explanation": f"The correct statement is: {line}"})
                break

    subj = []
    if n_subj and lines:
        topic = terms[0] if terms else "this topic"
        subj.append({"q": f"Explain {topic} in your own words, with one example.",
                     "key_points": lines[:3], "model_answer": " ".join(lines[:4])})
    return {"topic": terms[0] if terms else "Practice", "subject": guess_subject(material),
            "mcq": mcq, "true_false": tf, "subjective": subj, "source": "offline"}


def key_points(reference_md: str, k: int = 6) -> list[str]:
    """The lines of some notes worth checking an explanation against: bullets and sentences, not headings or tables."""
    out = []
    for raw in (reference_md or "").splitlines():
        if raw.lstrip().startswith(("#", "|", ">")):
            continue
        line = re.sub(r"^[*\-\d.)\s]+", "", raw).replace("**", "").replace("`", "").strip()
        if len(line.split()) >= 4:
            out.append(line[:200])
    return out[:k]


def evaluate(answer: str, key_points: list[str]) -> dict[str, Any]:
    ans_words = set(re.findall(r"[a-z0-9]+", answer.lower()))
    covered, missed = [], []
    for kp in key_points:
        kw = {w for w in re.findall(r"[a-z0-9]+", kp.lower()) if w not in _STOP and len(w) > 2}
        (covered if kw and len(kw & ans_words) / len(kw) >= 0.4 else missed).append(kp)
    score = round(10 * len(covered) / max(1, len(key_points)))
    grade = "Excellent" if score >= 8 else "Good" if score >= 6 else "Needs work" if score >= 3 else "Incorrect"
    return {"score": score, "grade": grade, "points_covered": covered, "points_missed": missed,
            "feedback": "Scored offline by keyword overlap with the key points. Check the points you missed.",
            "source": "offline"}


def companion(question: str, context_md: str) -> str:
    q_words = {w for w in re.findall(r"[a-z]+", question.lower()) if w not in _STOP and len(w) > 2}
    scored = []
    for line in _lines(context_md):
        overlap = len(q_words & set(re.findall(r"[a-z]+", line.lower())))
        if overlap:
            scored.append((overlap, line))
    scored.sort(reverse=True)
    if not scored:
        return ("The AI tutor can't answer right now: it's busy, or your AI allowance is used up. "
                "Try again in a few minutes.")
    snippets = "\n".join(f"- {l}" for _, l in scored[:4])
    return f"The AI tutor can't answer right now, but here is what your board notes say about this:\n\n{snippets}"


def summary(notes_list: list[dict[str, str]]) -> dict[str, Any]:
    topics = [n.get("topic") or "Board" for n in notes_list]
    all_md = "\n".join(n.get("notes_md", "") for n in notes_list)
    # boards overlap as the teacher writes, so dedupe formulas ignoring spacing/case
    seen: dict[str, str] = {}
    for f in _formula_lines(_lines(all_md)):
        seen.setdefault(re.sub(r"\s+", "", f).lower(), f)
    formulas = list(seen.values())
    unique_topics = list(dict.fromkeys(topics))
    md = "## Overview\nThis lecture covered: " + ", ".join(unique_topics) + "."
    ideas = [l for l in dict.fromkeys(_lines(all_md)) if l not in formulas and not l.startswith("Offline mode")
             and len(l.split()) >= 3][:8]
    if ideas:
        md += "\n\n## Key concepts\n" + "\n".join(f"- {l}" for l in ideas)
    if formulas:
        rows = "\n".join(f"| `{f.replace('|', '/')}` | – | – |" for f in formulas)
        md += "\n\n## Formula sheet\n| Formula | Meaning | Use when |\n| --- | --- | --- |\n" + rows
    md += "\n\n" + OFFLINE_NOTE
    return {"title": unique_topics[0] if unique_topics else "Lecture summary", "subject": guess_subject(all_md),
            "summary_md": md, "key_formulas": formulas[:20], "flashcards": flashcards(all_md)[:8], "source": "offline"}


def flashcards(material: str) -> list[dict[str, str]]:
    cards = []
    for line in _lines(material):
        if "=" in line and has_math(line) and len(line) < 80:
            lhs, rhs = line.split("=", 1)
            if lhs.strip() and rhs.strip():
                cards.append({"front": f"Complete the relation: {lhs.strip()} = ?", "back": rhs.strip()})
        elif ":" in line:
            head, tail = line.split(":", 1)
            if 2 <= len(head.split()) <= 8 and len(tail.strip()) > 8:
                cards.append({"front": f"{head.strip()}?", "back": tail.strip()})
    seen, unique = set(), []
    for c in cards:
        if c["front"] not in seen:
            seen.add(c["front"]); unique.append(c)
    return unique


def sanitize_cards(cards: Any) -> list[dict[str, str]]:
    out = []
    for c in cards if isinstance(cards, list) else []:
        if isinstance(c, dict) and str(c.get("front", "")).strip() and str(c.get("back", "")).strip():
            out.append({"front": str(c["front"]).strip()[:500], "back": str(c["back"]).strip()[:1000]})
    return out


def sanitize_quiz(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce LLM quiz output into the exact schema the UI expects; drop malformed items."""
    strip_prefix = lambda s: re.sub(r"^\s*(?:\(?[A-Da-d][).:]|[A-Da-d]\s*-)\s*", "", str(s)).strip()
    mcq = []
    for m in data.get("mcq", []) or []:
        try:
            opts = [strip_prefix(o) for o in m.get("options") or m.get("opts") or []][:4]
            idx = int(m.get("answer_index", m.get("ans", 0)))
            if len(opts) == 4 and 0 <= idx < 4 and m.get("q"):
                mcq.append({"q": str(m["q"]), "options": opts, "answer_index": idx, "explanation": str(m.get("explanation", ""))})
        except (TypeError, ValueError, AttributeError):
            continue
    tf = []
    for t in data.get("true_false", []) or []:
        if isinstance(t, dict) and t.get("statement") is not None:
            ans = t.get("answer", t.get("ans"))
            if isinstance(ans, str):
                ans = ans.strip().lower() in ("true", "t", "yes")
            tf.append({"statement": str(t["statement"]), "answer": bool(ans), "explanation": str(t.get("explanation", ""))})
    subj = []
    for s in data.get("subjective", []) or []:
        if isinstance(s, dict) and s.get("q"):
            subj.append({"q": str(s["q"]), "key_points": [str(k) for k in s.get("key_points", [])][:6],
                         "model_answer": str(s.get("model_answer", ""))})
    return {"topic": str(data.get("topic") or "Practice")[:80], "subject": str(data.get("subject") or "General")[:40],
            "mcq": mcq, "true_false": tf, "subjective": subj}
