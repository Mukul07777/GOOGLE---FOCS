"""Focs's English content said again in the student's language (Hinglish, Hindi, Marathi, Bengali, Tamil, Telugu or
Gujarati), with a check that nothing that matters changed.

Notes are written once in English and shared between students; a translation is made the first time a student who
reads that language needs it, then kept. A translation counts only if every formula and every number in it is the
same as in the English (checked without AI: a formula the model "tidied" is a wrong formula), and if it is really
written in the language's own script. If not, it is tried once more, and after that the student gets the English
with a notice, never a broken translation or an error.
"""
from __future__ import annotations

import logging
import re

from app.services import ai
from app.services.ai import MOTHER_TONGUES, _exam, language_rule
from app.services.llm import LLMUnavailable, fix_latex, llm, restore_backslashes

log = logging.getLogger("focs.translate")

_FORMULA = re.compile(r"\$\$.+?\$\$|\$[^$\n]+?\$", re.S)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")
NAMES = {"hinglish": "Hinglish", **{code: name for code, (name, _, _) in MOTHER_TONGUES.items()}}
TRANSLATE_RULE = {
    "hinglish": ("Write the translation in Hinglish: Hindi sentences in Roman script, with technical terms in English "
                 "(\"Yahan acceleration constant hai, isliye...\"). Every sentence, heading and bullet point. "
                 "A teacher's respectful tone: no slang such as yo, bro or yaar."),
    **{code: (f"Write the translation in {name}, in {script} script: every sentence, heading and bullet point.{slip} "
              f"A technical term may keep its English name in brackets after the {name}"
              + (" (प्रतिरोध (resistance))." if code == "hi" else "."))
       for code, (name, script, slip) in MOTHER_TONGUES.items()},
}
# Unicode blocks of each script; Latin letters still count, since formulas, units and bracketed terms stay English
SCRIPTS = {"Devanagari": (0x0900, 0x097F), "Bengali": (0x0980, 0x09FF), "Gujarati": (0x0A80, 0x0AFF),
           "Tamil": (0x0B80, 0x0BFF), "Telugu": (0x0C00, 0x0C7F)}


def _chars(first: int, last: int) -> str:
    return f"{chr(first)}-{chr(last)}"


_LETTERS = re.compile(f"[A-Za-z{_chars(0x0900, 0x0D7F)}]")  # Latin and every Indian script: a reply in the wrong one is caught
_IN_SCRIPT = {code: re.compile(f"[{_chars(*SCRIPTS[script])}]") for code, (_, script, _) in MOTHER_TONGUES.items()}
_WORDS = re.compile(r"[a-z]+")
# the words that tell Hindi from Marathi, both in Devanagari: a "Marathi" answer with more Hindi ones is Hindi. Only
# words one language uses and the other doesn't: का is Hindi's "of" but Marathi's "why", होता/होती/होते are in both.
_HINDI_WORDS = {"है", "हैं", "और", "नहीं", "में", "यह", "से", "के", "था", "थी"}
_MARATHI_WORDS = {"आहे", "आहेत", "आणि", "नाही", "हे", "मध्ये", "असते", "असतो", "म्हणून", "किंवा"}


def in_language(source: str, translated: str, language: str | None) -> bool:
    """Is the answer really in the student's language? The cheap model sometimes hands the English back unchanged,
    which keeps every formula and so passed faithful(): a Hindi student was shown English labelled Hindi. A script
    language must be mostly its own script (formulas and units stay Latin), Marathi must not have slipped into Hindi,
    and Hinglish must have changed a good share of the words."""
    text = re.sub(r"\$[^$]*\$", " ", translated)  # LaTeX is Latin in every language
    if language in _IN_SCRIPT:
        letters = len(_LETTERS.findall(text))
        if letters and len(_IN_SCRIPT[language].findall(text)) < 0.4 * letters:
            return False
        if language == "mr":
            words = re.findall(f"[{_chars(*SCRIPTS['Devanagari'])}]+", text)
            return sum(w in _HINDI_WORDS for w in words) <= sum(w in _MARATHI_WORDS for w in words)
        return True
    if language == "hinglish":
        before = set(_WORDS.findall(re.sub(r"\$[^$]*\$", " ", source).lower()))
        after = _WORDS.findall(text.lower())
        return not after or sum(w not in before for w in after) >= 0.2 * len(after)
    return True


ENGLISH_NOTICE = "{name} needs the AI, which is busy right now: showing English."


def signature(md: str) -> tuple[list[str], list[str]]:
    """The parts a translation must not touch: every formula (spacing ignored) and every number outside them."""
    formulas = sorted(re.sub(r"\s+", "", f) for f in _FORMULA.findall(md))
    return formulas, sorted(_NUMBER.findall(_FORMULA.sub(" ", md)))


def faithful(source: str, translated: str) -> bool:
    return bool(translated.strip()) and signature(source) == signature(translated) and len(translated) >= 0.4 * len(source)


def wanted(language: str | None) -> bool:
    return bool(language_rule(language))


def translate(md: str, language: str | None, exam: str | None, what: str = "study notes") -> tuple[str, bool]:
    """(text, translated): the Markdown in the student's language, or the English back with False when the AI is
    unavailable or twice changed a formula or a number."""
    if not wanted(language) or not md.strip():
        return md, not wanted(language)
    name = NAMES.get(language or "", "the student's language")
    # Not the chat rule (language_rule): its "keep technical terms in English" let the model hand back notes, which are
    # mostly technical terms, untranslated; and its chat reminder added a greeting and a takeaway to the notes.
    system = (f"Translate these {what} for a {_exam(exam)} student. {TRANSLATE_RULE[language]} "
              "Keep the Markdown structure (headings, bullets, tables) exactly. Copy every LaTeX expression exactly as "
              "written, with its backslashes and $ signs. Keep every number as digits, unchanged. Do not add, drop or "
              "explain anything. Reply with the translation only.")
    # the language said again after the notes: the model weighs the last message most
    ask = f"Translate into {name}:\n\n{md[:6000]}\n\n(The translation in {name}, every line. Nothing before or after it.)"
    for attempt in range(2):
        try:  # Devanagari takes several times the tokens of English, and the model reasons first: room for both
            out = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": ask}],
                           max_tokens=min(6000, 800 + len(md) * 2), temperature=0.1 if attempt else 0.2, tier="light",
                           feature="translate")
        except LLMUnavailable as exc:
            log.info("translation unavailable: %s", exc)
            return md, False
        out = fix_latex(restore_backslashes(out.strip()))
        if not in_language(md, out, language):
            log.info("translation came back untranslated (attempt %d)", attempt + 1)
            system += f" Your last answer was not in {name}: write every sentence in {name}."
            continue
        if faithful(md, out):
            return out, True
        log.info("translation changed a formula or number (attempt %d)", attempt + 1)
        system += " Your last answer changed a formula or a number: copy them character for character."
    return md, False


def notice(language: str | None) -> str:
    return ENGLISH_NOTICE.format(name=NAMES.get(language or "", "That language"))


def explained(solution: str, question: str, language: str, exam: str | None) -> str | None:
    """A worked solution said again in the student's language, or None when it twice came back in another one (the
    model now and then answers in English, or a Marathi one in Hindi). It is kept for every student after, so it is
    checked first. Raises LLMUnavailable."""
    for _ in range(2):
        text = ai.explain_in(solution, question, language, exam)
        if in_language(solution, text, language):
            return text
    return None
