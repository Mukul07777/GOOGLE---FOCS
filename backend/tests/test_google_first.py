"""Google first: with a Gemini key, every text call tries Gemini's models before anything else, light jobs try the
cheap Gemini first, and GOOGLE_ONLY (the hackathon build) never calls Groq, Claude or Groq's speech-to-text at all."""
from app.core.config import settings
from app.services import llm, speech, vision


def _keys(monkeypatch, *, gemini="g-key", groq="q-key", claude="", google_only=False, first=True):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", gemini)
    monkeypatch.setattr(settings, "GROQ_API_KEY", groq)
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", claude)
    monkeypatch.setattr(settings, "GOOGLE_ONLY", google_only)
    monkeypatch.setattr(settings, "GEMINI_FIRST", first)


def test_gemini_answers_first_and_the_others_only_back_it_up(monkeypatch):
    _keys(monkeypatch, claude="c-key")
    names = [p.name for p in llm.providers()]
    gemini = [n for n in names if n.startswith("gemini:")]
    assert names[:len(gemini)] == gemini and len(gemini) == len(settings.GEMINI_MODEL.split(","))
    assert any(n.startswith("primary:") for n in names) and names[-1].startswith("claude:")
    assert llm.light_models() == {"gemini-3.1-flash-lite"}


def test_google_only_calls_nothing_else(monkeypatch):
    _keys(monkeypatch, claude="c-key", google_only=True)
    assert all(p.name.startswith("gemini:") for p in llm.providers())
    assert all(not m.startswith("groq:") for m in vision.models()) and vision.models()
    assert speech._provider() is None and not speech.available()


def test_without_a_gemini_key_groq_stays_first(monkeypatch):
    _keys(monkeypatch, gemini="")
    assert [p.name for p in llm.providers()][0].startswith("primary:")
    _keys(monkeypatch, first=False)
    assert [p.name for p in llm.providers()][0].startswith("primary:")  # the old order, when asked for


def test_a_busy_gemini_hands_over_and_google_only_never_does(monkeypatch):
    import httpx

    from app.services.llm import llm as client, reset_cooldowns
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if "googleapis" in request.url.host:
            return httpx.Response(429, json={"error": "busy"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "from groq"}}]})

    _keys(monkeypatch)
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-a")
    monkeypatch.setattr(settings, "LLM_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setattr(client, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        assert client.chat([{"role": "user", "content": "hi"}]) == "from groq"
        assert "googleapis" in seen[0] and "groq" in seen[-1]
        reset_cooldowns()
        seen.clear()
        monkeypatch.setattr(settings, "GOOGLE_ONLY", True)
        try:
            client.chat([{"role": "user", "content": "hi"}])
            raise AssertionError("Google only must not fall back")
        except llm.LLMUnavailable:
            pass
        assert seen and all("googleapis" in h for h in seen)
    finally:
        monkeypatch.setattr(client, "_client", None)
        reset_cooldowns()
