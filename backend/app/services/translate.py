"""Focs's English content said again in Hindi or Hinglish, with a check that nothing that matters changed.

Notes are written once in English and shared between students; a translation is made the first time a student who
reads Hindi or Hinglish needs it, then kept. A translation counts only if every formula and every number in it is the
same as in the English (checked without AI: a formula the model "tidied" is a wrong formula). If not, it is tried
once more, and after that the student gets the English with a notice, never a broken translation or an error.
"""
from __future__ import annotations

import logging
import re

from app.services.ai import _exam, language_rule
from app.services.llm import LLMUnavailable, fix_latex, llm, restore_backslashes

log = logging.getLogger("focs.translate")

_FORMULA = re.compile(r"\$\$.+?\$\$|\$[^$\n]+?\$", re.S)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")
NAMES = {"hi": "Hindi", "hinglish": "Hinglish"}
TRANSLATE_RULE = {
    "hi": ("Write the translation in Hindi, in Devanagari script: every sentence, heading and bullet point. A technical "
           "term may keep its English name in brackets after the Hindi (प्रतिरोध (resistance))."),
    "hinglish": ("Write the translation in Hinglish: Hindi sentences in Roman script, with technical terms in English "
                 "(\"Yahan acceleration constant hai, isliye...\"). Every sentence, heading and bullet point. "
                 "A teacher's respectful tone: no slang such as yo, bro or yaar."),
}
_LETTERS = re.compile(r"[A-Za-z\u0900-\u097F]")
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_WORDS = re.compile(r"[a-z]+")


def in_language(source: str, translated: str, language: str | None) -> bool:
    """Is the answer really in the student's language? The cheap model sometimes hands the English back unchanged,
    which keeps every formula and so passed faithful(): a Hindi student was shown English labelled Hindi. Hindi must
    be mostly Devanagari (formulas and units stay Latin); Hinglish must have changed a good share of the words."""
    text = re.sub(r"\$[^$]*\$", " ", translated)  # LaTeX is Latin in every language
    if language == "hi":
        letters = len(_LETTERS.findall(text))
        return letters == 0 or len(_DEVANAGARI.findall(text)) >= 0.4 * letters
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
