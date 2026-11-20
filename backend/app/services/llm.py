"""Thin client for OpenAI-compatible chat endpoints (Groq, Gemini, OpenAI, Together, Ollama…).

The chain is every model of the primary provider (LLM_MODEL, comma-separated), then every model
of the optional fallback provider (LLM_FALLBACK_* / GEMINI_API_KEY). Free-tier limits on Groq and
Gemini are per model, so a rate-limited model hands over to the next one immediately and is put
on a cooldown until its limit resets. One account per provider — Groq's limits are shared by all
keys of an account, and its terms forbid spreading usage over multiple accounts.

Every caller also has an offline fallback, so Focs keeps working (in a reduced mode) when no
provider is reachable at all.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.services import ledger

log = logging.getLogger("focs.llm")


class LLMUnavailable(RuntimeError):
    pass


def ensure_budget() -> None:
    """Refuse an AI call for a free account once free accounts have spent the day's budget: the caller falls back to its
    offline answer, as when the provider is down. Paying students, and work done for nobody in particular (the shared
    question bank, background jobs), carry on."""
    user_id = ledger.current_user.get()
    if user_id is not None and ledger.over_budget() and not ledger.pays(user_id):
        raise LLMUnavailable("today's AI budget for free accounts is used up")


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str

    @property
    def local(self) -> bool:
        return "localhost" in self.base_url or "127.0.0.1" in self.base_url

    @property
    def usable(self) -> bool:
        return bool(self.api_key) or self.local

    @property
    def reasoning_model(self) -> bool:
        return "gpt-oss" in self.model or ("qwen3" in self.model and "groq.com" in self.base_url)


def _models(value: str) -> list[str]:
    return [m.strip() for m in (value or "").split(",") if m.strip()]


CLAUDE_BASE_URL = "claude"  # sentinel: not a real endpoint, routes _call to the Anthropic SDK instead of httpx


def light_models() -> set[str]:
    """The cheaper models a light job (board notes, pop quizzes) tries first."""
    return set(_models(settings.GEMINI_LIGHT_MODEL if settings.gemini_first else settings.LLM_LIGHT_MODEL))


def providers() -> list[Provider]:
    gemini_key = settings.gemini_api_key
    if settings.GOOGLE_ONLY:  # Google's models only, with or without a key: a missing key means no AI, never another provider
        return [p for p in (Provider(f"gemini:{m}", settings.LLM_FALLBACK_BASE_URL, gemini_key, m)
                            for m in _models(settings.GEMINI_MODEL)) if p.usable]
    if settings.gemini_first:  # Google first: every Gemini model, then (unless GOOGLE_ONLY) the others when all are busy
        chain = [Provider(f"gemini:{m}", settings.LLM_FALLBACK_BASE_URL, gemini_key, m) for m in _models(settings.GEMINI_MODEL)]
        if not settings.GOOGLE_ONLY:
            chain += [Provider(f"primary:{m}", settings.LLM_BASE_URL, settings.llm_api_key, m) for m in _models(settings.LLM_MODEL)]
        else:
            return [p for p in chain if p.usable]
    else:
        chain = [Provider(f"primary:{m}", settings.LLM_BASE_URL, settings.llm_api_key, m) for m in _models(settings.LLM_MODEL)]
        if gemini_key or "localhost" in settings.LLM_FALLBACK_BASE_URL:
            chain += [Provider(f"fallback:{m}", settings.LLM_FALLBACK_BASE_URL, gemini_key, m)
                      for m in _models(settings.LLM_FALLBACK_MODEL)]
    if settings.ANTHROPIC_API_KEY:
        # paid, so it only ever runs once every free provider above has failed
        chain += [Provider(f"claude:{m}", CLAUDE_BASE_URL, settings.ANTHROPIC_API_KEY, m)
                  for m in _models(settings.CLAUDE_MODEL)]
    return [p for p in chain if p.usable]


class RateLimited(LLMUnavailable):
    def __init__(self, message: str, retry_after: float):
        super().__init__(message)
        self.retry_after = retry_after


# (base_url, model) -> monotonic time until which that model is skipped after a 429
_cooldown: dict[tuple[str, str], float] = {}
_cooldown_lock = threading.Lock()
MIN_COOLDOWN, MAX_COOLDOWN = 20.0, 3600.0


def _retry_after(response: httpx.Response) -> float:
    """Seconds until the limit resets, from Retry-After or Groq's x-ratelimit-reset-* headers."""
    for header in ("retry-after", "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens"):
        raw = response.headers.get(header)
        if not raw:
            continue
        try:
            return float(raw)
        except ValueError:  # Groq style durations such as "2m59.56s" or "7.66s"
            m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", raw.strip())
            if m and any(m.groups()):
                h, mi, sec = (float(g) if g else 0.0 for g in m.groups())
                return h * 3600 + mi * 60 + sec
    return 60.0


def _cool(p: Provider, seconds: float) -> None:
    with _cooldown_lock:
        _cooldown[(p.base_url, p.model)] = time.monotonic() + max(MIN_COOLDOWN, min(seconds, MAX_COOLDOWN))


def _cooling(p: Provider) -> bool:
    return _cooling_for(p) > 0


def _cooling_for(p: Provider) -> float:
    """Seconds until a rate-limited model may be tried again (0 when it's free)."""
    with _cooldown_lock:
        return max(0.0, _cooldown.get((p.base_url, p.model), 0.0) - time.monotonic())


# A light background job (board notes during a lecture) waits this long for the cheap model rather than
# paying several times more for a bigger one: its limits usually reset within seconds. Nobody is watching a
# spinner for those; a student who pressed a button is never kept waiting this way.
LIGHT_WAIT_S = 25.0


def reset_cooldowns() -> None:
    with _cooldown_lock:
        _cooldown.clear()


def next_free_in(skip: frozenset[str] = frozenset()) -> float:
    """Seconds until one of the configured models (outside ``skip``) may be tried again: 0 when one is free now,
    and 0 when none is configured (waiting would not help)."""
    return min((_cooling_for(p) for p in providers() if p.model not in skip), default=0.0)


class LLMClient:
    def __init__(self) -> None:
        self._client: httpx.Client | None = None
        self._claude: Any | None = None

    @property
    def available(self) -> bool:
        return bool(providers())

    @property
    def models(self) -> list[str]:
        return [p.model for p in providers()]

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS)
        return self._client

    @property
    def claude(self) -> Any:
        if self._claude is None:
            from anthropic import Anthropic  # imported lazily: only paying, Claude-configured deployments need it

            self._claude = Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=settings.LLM_TIMEOUT_SECONDS)
        return self._claude

    def _call_claude(self, p: Provider, messages: list[dict[str, str]], max_tokens: int, temperature: float,
                     json_mode: bool, feature: str) -> str:
        import anthropic as _anthropic

        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system") or None
        turns = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
        if json_mode:
            hint = "Reply with a single valid JSON object and nothing else - no prose, no code fences."
            system = f"{system}\n\n{hint}" if system else hint
        try:
            resp = self.claude.messages.create(model=p.model, system=system, messages=turns,
                                                max_tokens=max_tokens, temperature=temperature)
        except _anthropic.RateLimitError as exc:
            wait = float(getattr(exc, "response", None) and exc.response.headers.get("retry-after", 0) or 30)
            _cool(p, wait)
            raise RateLimited(f"{p.name} is rate-limited for ~{int(wait)}s", wait) from exc
        except _anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise httpx.HTTPStatusError(f"{exc.status_code} from {p.name}", request=httpx.Request("POST", "claude"),
                                             response=httpx.Response(exc.status_code, request=httpx.Request("POST", "claude"))) from exc
            raise LLMUnavailable(f"{p.name} rejected the request ({exc.status_code}): {str(exc)[:300]}") from exc
        content = "".join(block.text for block in resp.content if block.type == "text").strip()
        if not content:
            raise LLMUnavailable(f"{p.name} returned an empty answer")
        ledger.record(feature, p.model, {"prompt_tokens": resp.usage.input_tokens, "completion_tokens": resp.usage.output_tokens})
        return content

    def _call(self, p: Provider, messages: list[dict[str, str]], max_tokens: int, temperature: float,
              json_mode: bool, last_resort: bool, effort: str = "low", feature: str = "other") -> str:
        if p.base_url == CLAUDE_BASE_URL:
            return self._call_claude(p, messages, max_tokens, temperature, json_mode, feature)
        body: dict[str, Any] = {"model": p.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if p.reasoning_model:
            # Reasoning models think before answering: keep reasoning out of `content` and leave
            # token room for it (reasoning counts against max_tokens).
            body["max_tokens"] = max_tokens + (1024 if effort == "low" else 4096)
            if "gpt-oss" in p.model:
                body["reasoning_effort"] = effort
                if "groq.com" in p.base_url:
                    body["include_reasoning"] = False
            else:  # Qwen3 on Groq
                body["reasoning_format"] = "hidden"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {p.api_key}"} if p.api_key else {}
        url = p.base_url.rstrip("/") + "/chat/completions"

        last_error: Exception | None = None
        for attempt in range(3 if last_resort else 1):
            try:
                r = self.client.post(url, json=body, headers=headers)
                if r.status_code == 429:
                    wait = _retry_after(r)
                    _cool(p, wait)
                    raise RateLimited(f"{p.name} is rate-limited for ~{int(wait)}s", wait)
                if r.status_code == 503:  # "model overloaded" - give it a short rest
                    _cool(p, 30)
                    raise RateLimited(f"{p.name} is overloaded", 30)
                if r.status_code == 404:  # model retired or not enabled for this key
                    _cool(p, MAX_COOLDOWN)
                    raise LLMUnavailable(f"{p.name} is not available (404)")
                if r.status_code >= 500:
                    raise httpx.HTTPStatusError(f"{r.status_code} from {p.name}", request=r.request, response=r)
                if r.status_code >= 400:
                    detail = r.text[:300]
                    if json_mode and "response_format" in detail and "response_format" in body:
                        body.pop("response_format")  # provider/model without JSON mode: retry once without it
                        return self._call_once(url, body, headers, p, feature)
                    # bad key / unknown model / etc. won't fix itself on retry
                    raise LLMUnavailable(f"{p.name} rejected the request ({r.status_code}): {detail}")
                data = r.json()
                content = data["choices"][0]["message"].get("content") or ""
                if not content.strip():
                    raise LLMUnavailable(f"{p.name} returned an empty answer")
                ledger.record(feature, p.model, data.get("usage"))
                return content.strip()
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last_error = exc
                if last_resort and attempt < 2:
                    wait = 1.5 * (attempt + 1)
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                        wait = float(exc.response.headers.get("retry-after", wait) or wait)
                    log.warning("LLM %s failed (attempt %d): %s", p.name, attempt + 1, exc)
                    time.sleep(min(wait, 8))
        raise LLMUnavailable(f"{p.name} unreachable: {last_error}")

    def _call_once(self, url: str, body: dict, headers: dict, p: Provider, feature: str) -> str:
        r = self.client.post(url, json=body, headers=headers)
        if r.status_code >= 400:
            raise LLMUnavailable(f"{p.name} rejected the request ({r.status_code}): {r.text[:300]}")
        data = r.json()
        content = data["choices"][0]["message"].get("content") or ""
        if not content.strip():
            raise LLMUnavailable(f"{p.name} returned an empty answer")
        ledger.record(feature, p.model, data.get("usage"))
        return content.strip()

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int = 900, temperature: float = 0.3,
             json_mode: bool = False, effort: str = "low", tier: str = "standard", feature: str = "other") -> str:
        return self.chat_with_model(messages, max_tokens=max_tokens, temperature=temperature,
                                    json_mode=json_mode, effort=effort, tier=tier, feature=feature)[0]

    def chat_with_model(self, messages: list[dict[str, str]], *, max_tokens: int = 900, temperature: float = 0.3,
                        json_mode: bool = False, effort: str = "low", skip: frozenset[str] = frozenset(),
                        tier: str = "standard", feature: str = "other", patient: bool = False) -> tuple[str, str]:
        """Like chat, but also says which model answered. ``skip`` keeps those models out of the chain
        (an independent second opinion must come from a different model). ``tier="light"`` tries the cheaper
        LLM_LIGHT_MODEL first, and with ``patient`` (background jobs) waits briefly for it when it's rate-limited;
        ``feature`` labels the call in the cost ledger."""
        ensure_budget()
        configured = [p for p in providers() if p.model not in skip]
        light = light_models() if tier == "light" else set()
        wait_for = light if patient else set()
        if light:
            configured.sort(key=lambda p: p.model not in light)  # stable: the rest keep their order
            cheap = [p for p in configured if p.model in wait_for]
            soonest = min((_cooling_for(p) for p in cheap), default=0.0)
            if cheap and 0 < soonest <= LIGHT_WAIT_S:
                time.sleep(soonest + 0.2)  # the cheap model frees up in a moment: worth the wait
        if not configured:
            raise LLMUnavailable("No LLM API key configured")
        chain = [p for p in configured if not _cooling(p)]
        if not chain:
            raise LLMUnavailable("All configured models are rate-limited right now")
        errors = []
        for i, p in enumerate(chain):
            waited = False
            while True:
                try:
                    content = self._call(p, messages, max_tokens, temperature, json_mode,
                                         last_resort=i == len(chain) - 1, effort=effort, feature=feature)
                    return content, p.model
                except RateLimited as exc:
                    if p.model in wait_for and not waited and exc.retry_after <= LIGHT_WAIT_S:
                        log.info("%s — waiting for it instead of a bigger model", exc)
                        time.sleep(exc.retry_after + 0.2)
                        waited = True
                        continue
                    errors.append(str(exc))
                except LLMUnavailable as exc:
                    errors.append(str(exc))
                break
            if i < len(chain) - 1:
                log.warning("%s — switching to %s", errors[-1], chain[i + 1].name)
        raise LLMUnavailable("; ".join(errors))

    def json(self, messages: list[dict[str, str]], **kwargs) -> dict[str, Any]:
        return self.json_with_model(messages, **kwargs)[0]

    def json_with_model(self, messages: list[dict[str, str]], **kwargs) -> tuple[dict[str, Any], str]:
        """Ask for a JSON object. Provider JSON mode is only the fallback: it validates the output and silently
        deletes every backslash that isn't a valid JSON escape — "\\frac", "\\pm", "\\alpha" all lose theirs —
        while our own parser (parse_json) keeps LaTeX intact."""
        if messages and messages[0].get("role") == "system":
            messages = [{**messages[0], "content": messages[0]["content"] + _ESCAPE_HINT}, *messages[1:]]
        raw, model = self.chat_with_model(messages, **kwargs)
        try:
            return parse_json(raw), model
        except LLMUnavailable:
            pass
        # the next model, still without JSON mode: a JSON-mode retry of board notes came back with "ge0", "cup" and
        # "infty" for \ge, \cup and \infty (2026-10-19)
        log.info("%s answered without valid JSON; asking the next model", model)
        try:
            raw, other = self.chat_with_model(messages, **{**kwargs, "skip": frozenset(kwargs.get("skip", ())) | {model}})
            return parse_json(raw), other
        except LLMUnavailable:
            log.info("no valid JSON from the next model either; retrying in JSON mode")
        raw, model = self.chat_with_model(messages, json_mode=True, **kwargs)
        return parse_json(raw), model


_ESCAPE_HINT = ("\n\nThe reply must be valid JSON: inside strings escape every LaTeX backslash, "
                "e.g. write \"$\\\\alpha = \\\\frac{\\\\omega}{t}$\".")

# LaTeX commands whose first letter is also a JSON escape letter (b f n r t u). In model output
# "\tau" means the command, not TAB + "au"; "\frac" is not form-feed + "rac".
_LATEX_COMMANDS = frozenset(
    "beta bar bf big Big bigg binom boldsymbol bot bullet bmod frac forall flat nabla ne neq nu not neg ni "
    "newline nexists nleq ngeq rho right rightarrow rightleftharpoons rm rangle rceil rfloor tau theta times "
    "text textbf textit textrm tan tanh tfrac to top triangle tilde therefore underline uparrow updownarrow "
    "upsilon unit underbrace".split()
)
_HEX = frozenset("0123456789abcdefABCDEF")
_BS = "\\"


def repair_latex_escapes(text: str) -> str:
    """Double the backslash of LaTeX commands and invalid escapes; keep genuine JSON escapes."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch != _BS or i + 1 >= n:
            out.append(ch)
            i += 1
            continue
        nxt = text[i + 1]
        if nxt in '"/' or nxt == _BS:  # \" \/ \\ are already fine
            out.append(text[i:i + 2])
            i += 2
            continue
        word_match = re.match(r"[A-Za-z]+", text[i + 1:])
        word = word_match.group(0) if word_match else ""
        if nxt in "bfnrtu" and word in _LATEX_COMMANDS:
            out.append(_BS * 2)  # literal backslash; the command letters are copied next
            i += 1
            continue
        if nxt == "u" and i + 6 <= n and all(c in _HEX for c in text[i + 2:i + 6]):
            out.append(text[i:i + 6])  # ²
            i += 6
            continue
        if nxt in "bfnrt":  # real newline / tab / ...
            out.append(text[i:i + 2])
            i += 2
            continue
        out.append(_BS * 2)  # invalid JSON escape such as \mathbf or \( : keep it literal
        i += 1
    return "".join(out)


_CMD = ("mathbf|mathrm|mathit|mathcal|boldsymbol|frac|dfrac|tfrac|times|cdot|div|pm|mp|tau|theta|omega|Omega|alpha|"
        "beta|gamma|delta|Delta|epsilon|varepsilon|lambda|mu|nu|pi|rho|sigma|Sigma|phi|varphi|psi|eta|kappa|chi|sqrt|"
        "sum|int|oint|prod|lim|vec|hat|bar|dot|ddot|left|right|text|textbf|quad|qquad|leq|geq|neq|ne|approx|infty|"
        "partial|nabla|propto|rightarrow|leftarrow|Rightarrow|leftrightarrow|rightleftharpoons|to|boxed|circ|angle|"
        "perp|parallel|sin|cos|tan|log|ln|exp|overline|underline|lvert|rvert|langle|rangle|cdots|ldots|hbar|ell")
_DOUBLED = re.compile(r"(?<!\\)\\\\(?=(?:" + _CMD + r")(?![A-Za-z]))")

# JSON modes drop backslashes that aren't valid JSON escapes ("$\alpha$" arrives as "$alpha$"). Inside math a bare
# command name is never meant literally, so put the backslash back. Names that double as ordinary subscripts
# (int, exp, max...) are deliberately left out; \text{...} contents are never touched.
_BARE = ("alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|lambda|mu|nu|xi|pi|rho|sigma|"
         "tau|upsilon|phi|varphi|chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Phi|Psi|Omega|displaystyle|cdot|"
         "times|div|pm|mp|leq|geq|neq|approx|infty|partial|nabla|propto|rightarrow|leftarrow|Rightarrow|"
         "leftrightarrow|hbar|quad|qquad|cdots|ldots|sin|cos|tan")
_BRACED = "frac|dfrac|tfrac|sqrt|mathbf|mathrm|mathit|mathcal|boldsymbol|vec|hat|overline|underline"
_BARE_RE = re.compile(r"(?<![\\A-Za-z])(" + _BARE + r")(?![A-Za-z])")
_BRACED_RE = re.compile(r"(?<![\\A-Za-z])(" + _BRACED + r")(?=[{\d])")
_TEXT_GROUP = re.compile(r"(\\?text(?:bf|it|rm)?\{[^{}]*\})")
_MATH = re.compile(r"(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)")


def _restore_math(segment: str) -> str:
    parts = _TEXT_GROUP.split(segment)
    for i, part in enumerate(parts):
        if i % 2:  # a \text{...} group: only its own backslash may be missing
            parts[i] = part if part.startswith("\\") else "\\" + part
        else:
            parts[i] = _BRACED_RE.sub(r"\\\1", _BARE_RE.sub(r"\\\1", part))
    return "".join(parts)


def restore_backslashes(text: str) -> str:
    return _MATH.sub(lambda m: _restore_math(m.group(0)), text)


_COMMAND_NAME = re.compile(r"(?:" + _BARE + "|" + _BRACED + r"|text|textbf|textit|textrm)")
_LABELLED = re.compile(r"([^\\:$]{2,40}):(\*\*)?\s+(.+)$")


def _looks_like_formula(s: str) -> bool:
    if "$" in s:
        return False
    core = _TEXT_GROUP.sub(" ", s)
    if not re.search(r"\\[A-Za-z]|[=^_]", core):
        return False
    prose = [w for w in re.findall(r"(?<![\\A-Za-z])[A-Za-z]{3,}(?![A-Za-z])", core) if not _COMMAND_NAME.fullmatch(w)]
    return len(prose) < 3


def wrap_formula_bullets(md: str) -> str:
    """Bullets under a "Formulas" heading sometimes arrive as bare LaTeX; wrap them in $...$ so they render."""
    out, in_formulas = [], False
    for line in md.split("\n"):
        heading = re.match(r"\s*#{1,6}\s+(.*)", line)
        bullet = re.match(r"(\s*[-*]\s+)(.+)$", line)
        if heading:
            in_formulas = "formula" in heading.group(1).lower()
        elif in_formulas and bullet:
            body = bullet.group(2).strip()
            labelled = _LABELLED.match(body)
            if labelled and _looks_like_formula(labelled.group(3)):
                line = f"{bullet.group(1)}{labelled.group(1)}:{labelled.group(2) or ''} ${labelled.group(3)}$"
            elif _looks_like_formula(body):
                line = f"{bullet.group(1)}${body}$"
        out.append(line)
    return "\n".join(out)


_OVERESCAPED = re.compile(r"(?<!\\)\\\\(?=[A-Za-z]{2,})")  # a doubled command: the whole string was escaped twice
_RUN = re.compile(r"\\{2,}")
_LITERAL_NEWLINE = re.compile(r"\\n(?=\s|$)")  # "\n" left as two characters (never a LaTeX command: those are \nu, \neq…)


# \[ ... \] and \( ... \): LaTeX's own delimiters, which some models prefer; the notes renderer reads only $ and $$
_DISPLAY = re.compile(r"(?<!\\)\\\[(.+?)\\\]", re.S)
_INLINE = re.compile(r"(?<!\\)\\\(([^\n]+?)\\\)")


def _dollars(s: str) -> str:
    s = _DISPLAY.sub(lambda m: f"$${m.group(1).strip()}$$", s)
    return _INLINE.sub(lambda m: f"${m.group(1).strip()}$", s)


def _fix_str(s: str) -> str:
    s = _dollars(s)
    if _OVERESCAPED.search(s):
        s = _RUN.sub(lambda m: "\\" * (len(m.group(0)) // 2), s)  # \\begin -> \begin, \\\\ -> \\ (row break)
    else:
        s = _DOUBLED.sub(lambda _: "\\", s)
    return restore_backslashes(_LITERAL_NEWLINE.sub("\n", s))


def fix_latex(value: Any) -> Any:
    """Undo doubled backslashes (models sometimes escape twice: \\\\mathbf, \\\\begin{pmatrix}) and restore the
    ones JSON mode dropped, recursively. A real LaTeX line break (\\\\ followed by a space or newline) is kept."""
    if isinstance(value, str):
        return _fix_str(value)
    if isinstance(value, list):
        return [fix_latex(v) for v in value]
    if isinstance(value, dict):
        return {k: fix_latex(v) for k, v in value.items()}
    return value


def parse_json(raw: str) -> dict[str, Any]:
    """Parse model output that should be JSON but may be wrapped in prose or code fences."""
    text = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    text = repair_latex_escapes(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise LLMUnavailable("Model did not return JSON") from exc
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMUnavailable(f"Model returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMUnavailable("Model returned JSON that is not an object")
    return fix_latex(data)


llm = LLMClient()
