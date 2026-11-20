"""Text helpers shared by the live pipeline and the offline fallbacks."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# Things that show up when a whole browser window is captured instead of a lecture.
_JUNK_PATTERNS = [
    r"https?://", r"www\.", r"\blocalhost\b", r"127\.0\.0", r"\.(com|in|org|io|app)\b",
    r"\bswagger\b", r"\bsubscribe\b", r"\bnotifications?\b", r"\bnew tab\b", r"\bbookmarks?\b",
    r"\bsign in\b", r"\bshare\b\s*$", r"^\s*[x×]\s*\|", r"\|\s*[x×+]\s*\|", r"\bviews?\b.*\bago\b",
]
_JUNK_RE = re.compile("|".join(_JUNK_PATTERNS), re.IGNORECASE)
_MATH_CHARS = set("=+−-×÷/^√∫∑πθλμΔ∞≤≥≠≈±∝→²³₁₂")

SUBJECT_KEYWORDS = {
    "Physics": "force velocity acceleration momentum energy work power torque friction gravity gravitation wave "
               "frequency current voltage resistance magnetic electric field charge capacitor lens refraction "
               "thermodynamics heat temperature pressure stress strain elasticity oscillation shm photon nucleus "
               "projectile kinematics newton inertia potential flux induction optics doppler",
    "Chemistry": "mole molarity reaction equilibrium acid base ph oxidation reduction redox electron orbital "
                 "bond hybridisation hybridization organic alkane alkene alkyne benzene ester ketone aldehyde "
                 "enthalpy entropy gibbs catalyst electrolysis electrochemistry periodic ionic covalent salt "
                 "compound isomer nucleophile carbocation polymer solution colligative kinetics titration",
    "Mathematics": "integral derivative differentiation integration limit matrix determinant vector function "
                   "equation polynomial quadratic parabola ellipse hyperbola circle probability permutation "
                   "combination binomial sequence series trigonometry sin cos tan log logarithm theorem "
                   "domain range continuity differential locus conic",
    "Biology": "cell dna rna gene protein enzyme photosynthesis respiration mitosis meiosis chromosome "
               "evolution ecosystem organism tissue hormone neuron blood heart kidney digestion plant animal "
               "species inheritance mendel bacteria virus reproduction",
    "Computer Science": "algorithm array linked list tree graph stack queue complexity recursion dynamic "
                        "programming function class object pointer loop compiler database sql network "
                        "process thread memory",
    "Economics": "demand supply market gdp inflation monetary fiscal policy price elasticity cost revenue "
                 "profit bank interest tax budget trade",
}
_SUBJECT_SETS = {s: set(words.split()) for s, words in SUBJECT_KEYWORDS.items()}


def is_junk_line(line: str) -> bool:
    s = line.strip()
    if len(s) < 2:
        return True
    if _JUNK_RE.search(s):
        return True
    alnum = sum(ch.isalnum() for ch in s)
    if alnum / max(1, len(s)) < 0.35 and not (set(s) & _MATH_CHARS):
        return True
    return False


def clean_ocr(text: str) -> str:
    """Drop UI chrome / garbage lines and normalise whitespace."""
    lines = []
    for raw in (text or "").splitlines():
        line = " ".join(raw.split())
        if line and not is_junk_line(line):
            lines.append(line)
    return "\n".join(lines)


def normalized_lines(text: str) -> list[str]:
    # relations stay: "x > 2" and "x < 2" are different boards
    return [re.sub(r"[^a-z0-9=+\-*/^()<>≤≥≠]", "", l.lower()) for l in (text or "").splitlines() if l.strip()]


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, " ".join(normalized_lines(a)), " ".join(normalized_lines(b))).ratio()


def containment(old: str, new: str) -> float:
    """Fraction of ``old``'s characters that reappear, in order, in ``new``.

    High containment + more text = the teacher kept writing on the same board. Compared as one
    character stream rather than line by line, because OCR may split or merge lines between frames.
    """
    a = "".join(normalized_lines(old))
    b = "".join(normalized_lines(new))
    if len(a) < 4 or not b:
        return 0.0
    matched = sum(block.size for block in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return matched / len(a)


# Handwriting on a pen tablet is read a little differently in every frame: lines come back in another order, split in
# other places, with a few characters changed. Compared as one ordered string (similarity, containment), five frames of
# one board in a PW maths lecture scored 0.51-0.65 and each became a "new board" with its own paid notes. Their
# 3-character pieces barely change, whatever the order. Measured on that lecture: frames of one board share 0.71-0.81
# of the smaller one's pieces (0.51-0.67 of all of them); different boards at most 0.44 (0.22).
MIN_GRAMS = 20  # shorter than this (a heading, a stray mark) there is too little to tell


def _grams(text: str) -> set[str]:
    flat = " ".join(normalized_lines(text))
    return {flat[i:i + 3] for i in range(len(flat) - 2)}


def same_board(a: str, b: str) -> bool:
    """Two readings of one board, however differently the OCR ordered or garbled them."""
    ga, gb = _grams(a), _grams(b)
    if len(ga) < MIN_GRAMS or len(gb) < MIN_GRAMS:
        return False
    shared = len(ga & gb)
    return shared / min(len(ga), len(gb)) >= 0.7 and shared / len(ga | gb) >= 0.45


def guess_subject(text: str) -> str:
    words = set(re.findall(r"[a-z]+", (text or "").lower()))
    best, best_hits = "General", 0
    for subject, keys in _SUBJECT_SETS.items():
        hits = len(words & keys)
        if hits > best_hits:
            best, best_hits = subject, hits
    return best


def topic_tokens(topic: str) -> set[str]:
    stop = {"and", "of", "the", "a", "an", "in", "to", "for", "on", "with", "introduction", "basics", "part"}
    return {w for w in re.findall(r"[a-z0-9]+", (topic or "").lower()) if w not in stop}


def topics_differ(a: str | None, b: str | None) -> bool:
    ta, tb = topic_tokens(a or ""), topic_tokens(b or "")
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) < 0.25


def has_math(text: str) -> bool:
    return bool(set(text) & _MATH_CHARS)
