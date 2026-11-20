from __future__ import annotations


def levenshtein(a, b) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def score(preds: list[str], gts: list[str]) -> dict:
    """Character error rate, word error rate and exact-line accuracy."""
    char_err = sum(levenshtein(p, g) for p, g in zip(preds, gts))
    char_tot = sum(max(1, len(g)) for g in gts)
    word_err = sum(levenshtein(p.split(), g.split()) for p, g in zip(preds, gts))
    word_tot = sum(max(1, len(g.split())) for g in gts)
    exact = sum(p == g for p, g in zip(preds, gts))
    n = max(1, len(gts))
    return {
        "cer": round(char_err / char_tot, 4),
        "wer": round(word_err / word_tot, 4),
        "line_acc": round(exact / n, 4),
        "n": len(gts),
    }
