"""Answer options and short answers that are certain to render, whatever the model wrote."""
from __future__ import annotations

import re
from typing import Any

_PLAIN_CMDS = {r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥", r"\ne": "≠", r"\neq": "≠", r"\pm": "±", r"\cdot": "·",
               r"\times": "×", r"\infty": "∞", r"\pi": "π", r"\theta": "θ", r"\alpha": "α", r"\beta": "β", r"\to": "→",
               r"\cup": "∪", r"\cap": "∩", r"\circ": "°", r"\,": " ", r"\;": " ", r"\!": "", r"\ ": " "}
_FRAC = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_STYLE = re.compile(r"\\(?:displaystyle|textstyle)\s*")
_PAREN_PAIR = re.compile(r"\\\((.+?)\\\)")
_BRACKET_PAIR = re.compile(r"\\\[(.+?)\\\]")
_LONE = re.compile(r"\\([\[\]()])")
_NEEDS_MATH = re.compile(r"\\[A-Za-z]|[\^_]\{")
_INTERVAL = re.compile(r"[^,]*,[^,]*")


def balanced(s: str) -> bool:
    """Braces pair up, dollars come in twos and every \\left has its \\right: what KaTeX needs to draw a formula."""
    depth = 0
    for ch in s.replace("\\{", "").replace("\\}", ""):
        depth += (ch == "{") - (ch == "}")
        if depth < 0:
            return False
    return depth == 0 and s.replace("$$", "").count("$") % 2 == 0 and s.count("\\left") == s.count("\\right")


def plain(s: str) -> str:
    """A formula as readable text, for when it can't be drawn: 7/2 for \\frac{7}{2}, ≤ for \\le, no dollars or braces."""
    s = s.replace("$", "")
    for _ in range(3):
        s = _FRAC.sub(lambda m: f"({m[1]})/({m[2]})" if len(m[1]) > 1 or len(m[2]) > 1 else f"{m[1]}/{m[2]}", s)
    s = re.sub(r"\\(?:displaystyle|textstyle|left|right|mathrm|text|mathbf)(?![A-Za-z])", "", s)
    for cmd in sorted(_PLAIN_CMDS, key=len, reverse=True):
        s = s.replace(cmd, _PLAIN_CMDS[cmd])
    s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"√(\1)", s)
    s = re.sub(r"\^\{([^{}]*)\}", r"^\1", s).replace("{", "").replace("}", "")
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def _square(m: re.Match[str]) -> str:
    inner = m[1]
    # "\[-1, 6\]" is an interval whose brackets were written as delimiters; "\[x^2\]" is display maths
    return f"[{inner}]" if _INTERVAL.fullmatch(inner.strip()) else f"${inner}$"


def clean_option(text: Any) -> str:
    """An option that is certain to render: a bracket the model wrote as a LaTeX delimiter (an interval "[-7/2, 19\\]"
    lost its closing bracket that way) is put back, a bare formula gets its dollars, and maths that still wouldn't
    draw (unbalanced braces) becomes plain text."""
    s = _STYLE.sub("", str(text).strip()).replace("\\tfrac", "\\frac").replace("\\dfrac", "\\frac")
    s = _PAREN_PAIR.sub(lambda m: f"${m[1]}$", s)
    s = _BRACKET_PAIR.sub(_square, s)
    s = _LONE.sub(r"\1", s)
    if "$" not in s and _NEEDS_MATH.search(s):
        s = f"${s}$"
    return s if balanced(s) else plain(s)
