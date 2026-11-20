import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, CloudOff, Delete, LayoutGrid, Loader2, Maximize, Minimize, PenLine, Send } from "lucide-react";
import { RoughPad } from "@/components/RoughPad";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { LogoMark } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { LanguageToggle, OptionFigure, optionFigure, QuestionFigures, shownIn, usePaperLanguage } from "@/components/QuestionMedia";
import { PaletteBadge, PaletteLegend, paletteState, type PaletteState } from "@/components/MockPalette";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { displayStyle } from "@/lib/math";
import type { MockDetail, MockQuestion, MockResponse } from "@/lib/types";
import { cn, subjectColor, shownName } from "@/lib/utils";
import { useFocus } from "@/lib/focus";
import { useAuth } from "@/stores/auth";

type Responses = Record<string, MockResponse>;

function clock(sec: number) {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
}

const answered = (r: MockResponse | undefined) => r?.a !== null && r?.a !== undefined && r?.a !== "";

/* ---------------------------------------------------------------- numeric keypad */
function Keypad({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const press = (k: string) => {
    if (k === "back") return onChange(value.slice(0, -1));
    if (k === "clear") return onChange("");
    if (value.length < 6) onChange(value === "0" ? k : value + k);
  };
  return (
    <div className="max-w-[260px]">
      <input value={value} inputMode="numeric" autoComplete="off" aria-label="Your answer" placeholder="Type your answer"
        onChange={(e) => onChange(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))}
        className="h-12 w-full rounded-xl border border-line-strong bg-bg-soft px-4 text-lg font-semibold tabular-nums outline-none focus:border-accent/60" />
      <div className="mt-2 grid grid-cols-3 gap-1.5">
        {["7", "8", "9", "4", "5", "6", "1", "2", "3", "clear", "0", "back"].map((k) => (
          <button key={k} type="button" onClick={() => press(k)}
            className="h-10 rounded-lg border border-line bg-elev-2 text-sm font-semibold transition hover:border-line-strong hover:bg-elev">
            {k === "back" ? <Delete className="mx-auto h-4 w-4" /> : k === "clear" ? <span className="text-xs text-muted">Clear</span> : k}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- palette panel */
function Palette({ questions, responses, idx, subject, onJump, counts, sections }: {
  questions: MockQuestion[]; responses: Responses; idx: number; subject: string; onJump: (i: number) => void;
  counts: Record<PaletteState, number>; sections: { key: string; label: string }[];
}) {
  return (
    <div className="space-y-4">
      <PaletteLegend counts={counts} compact />
      {sections.map((s) => {
        const items = questions.map((q, i) => ({ q, i })).filter(({ q }) => q.subject === subject && q.section === s.key);
        if (!items.length) return null;
        return (
          <div key={s.key}>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{s.label}</div>
            <div className="grid grid-cols-5 gap-2">
              {items.map(({ q, i }) => (
                <PaletteBadge key={q.id} state={paletteState(responses[q.id])} active={i === idx} onClick={() => onJump(i)}>{q.no}</PaletteBadge>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ================================================================== exam */
function Exam({ test }: { test: MockDetail }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const questions = useMemo(() => test.questions ?? [], [test.questions]);
  const [lang, setLang] = usePaperLanguage();
  const bilingual = questions.some((x) => x.hindi?.question);  // an SSC paper: every question in English and Hindi
  const pattern = test.pattern_info!;
  const [idx, setIdx] = useState(() => Math.max(0, Math.min(test.current_index ?? 0, questions.length - 1)));
  const [responses, setResponses] = useState<Responses>(() => {
    const r = { ...(test.responses ?? {}) };
    const first = questions[Math.max(0, Math.min(test.current_index ?? 0, questions.length - 1))];
    if (first) r[first.id] = { ...(r[first.id] ?? { a: null }), v: true };
    return r;
  });
  const q = questions[idx];
  const [rough, setRough] = useState(false);  // the rough pad under the question (a page per question)
  const shown = q ? shownIn(q, lang) : { question: "", options: null };
  const [draft, setDraft] = useState<string | null>(() => responses[q?.id]?.a ?? null);
  const [remaining, setRemaining] = useState(test.remaining_sec ?? 0);
  const [tabSwitches, setTabSwitches] = useState(test.tab_switches ?? 0);
  const [confirm, setConfirm] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [offline, setOffline] = useState(false);
  const [fullscreen, setFullscreen] = useState(!!document.fullscreenElement);
  const finished = useRef(false);
  useFocus("mock", true); // a running paper is focus time, even on another tab (that's flagged separately)

  // latest values for timers and async saves; seconds per question live in a ref so the
  // once-a-second tick doesn't re-render the paper or trigger a save
  const latest = useRef({ responses, idx, tabSwitches });
  latest.current = { responses, idx, tabSwitches };
  const spent = useRef<Record<string, number>>(Object.fromEntries(Object.entries(test.responses ?? {}).map(([k, v]) => [k, v.t ?? 0])));
  const withTime = (r: Responses): Responses =>
    Object.fromEntries(Object.entries(r).map(([k, v]) => [k, { ...v, t: spent.current[k] ?? v.t ?? 0 }]));

  const section = pattern.sections.find((s) => s.key === q?.section);
  const subject = q?.subject ?? pattern.subjects[0];

  /* -------- saving */
  const save = useCallback(async () => {
    if (finished.current) return;
    const { responses: r, idx: i, tabSwitches: ts } = latest.current;
    try {
      const res = await api.saveMock(test.id, { responses: withTime(r), current_index: i, tab_switches: ts });
      setOffline(false);
      if (res.remaining_sec !== null) setRemaining(res.remaining_sec);
      if (res.status === "submitted" && !finished.current) {
        finished.current = true;
        toast.message("Time's up — your paper was submitted.");
        qc.invalidateQueries({ queryKey: ["mocks"] });
        navigate(`/app/mock/${test.id}`, { replace: true });
      }
    } catch {
      setOffline(true); // the 20-second flush retries
    }
  }, [test.id, navigate, qc]);

  const submit = useMutation({
    mutationFn: () => {
      const { responses: r, idx: i, tabSwitches: ts } = latest.current;
      return api.submitMock(test.id, { responses: withTime(r), current_index: i, tab_switches: ts });
    },
    onSuccess: (t) => {
      qc.setQueryData(["mock", test.id], t);
      qc.invalidateQueries({ queryKey: ["mocks"] });
      if (document.fullscreenElement) document.exitFullscreen().catch(() => undefined);
      navigate(`/app/mock/${test.id}`, { replace: true });
    },
    onError: () => { finished.current = false; },
  });

  // debounce saves after every change; flush every 20 s so time spent per question is kept
  const finish = () => {
    if (finished.current) return; // the clock and the button can't both submit
    finished.current = true;
    submit.mutate();
  };

  useEffect(() => {
    const t = setTimeout(() => void save(), 250);
    return () => clearTimeout(t);
  }, [responses, idx, tabSwitches, save]);
  useEffect(() => {
    const t = setInterval(() => void save(), 20_000);
    return () => clearInterval(t);
  }, [save]);

  /* -------- clock: counts down locally, re-synced from the server on every save */
  useEffect(() => {
    const t = setInterval(() => {
      setRemaining((s) => Math.max(0, s - 1));
      const id = questions[latest.current.idx]?.id;
      if (id !== undefined) spent.current[id] = (spent.current[id] ?? 0) + 1;
    }, 1000);
    return () => clearInterval(t);
  }, [questions]);
  useEffect(() => {
    if (remaining <= 0 && !finished.current) {
      toast.message("Time's up — submitting your paper.");
      finish();
    }
  });

  /* -------- leaving the window / the page */
  useEffect(() => {
    const onVis = () => {
      if (document.hidden) {
        setTabSwitches((n) => n + 1);
        void save(); // the tab may be closing: don't lose the answers given in the last moment
      }
      else toast.warning("You left the test window. In the real exam this would be flagged.", { id: "tab-switch" });
    };
    const onUnload = (e: BeforeUnloadEvent) => { if (!finished.current) e.preventDefault(); };
    const onFs = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener("visibilitychange", onVis);
    window.addEventListener("beforeunload", onUnload);
    document.addEventListener("fullscreenchange", onFs);
    return () => {
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("beforeunload", onUnload);
      document.removeEventListener("fullscreenchange", onFs);
    };
  }, [save]);

  /* -------- navigation & NTA actions */
  const go = (i: number) => {
    const next = Math.max(0, Math.min(questions.length - 1, i));
    if (questions[next].subject !== q?.subject || questions[next].section !== q?.section) toast.dismiss("section-full");
    setIdx(next);
    setDraft(latest.current.responses[questions[next].id]?.a ?? null); // an unsaved choice is dropped, like the NTA screen
    setResponses((r) => ({ ...r, [questions[next].id]: { ...(r[questions[next].id] ?? { a: null }), v: true } }));
    setPaletteOpen(false);
  };

  const sectionBFull = (answer: string | null) => {
    if (!section || !answer || section.attempt >= section.count) return false;
    const others = questions.filter((x) => x.subject === q.subject && x.section === q.section && x.id !== q.id && answered(responses[x.id]));
    return others.length >= section.attempt;
  };

  const commit = (mark: boolean, keepDraft: boolean) => {
    const answer = keepDraft ? draft : responses[q.id]?.a ?? null;
    if (keepDraft && answer !== null && answer !== "" && sectionBFull(answer)) {
      // never hold the student on this question: move on without the answer, and say why (one toast, not a pile)
      toast.warning(`Not saved: you've already answered ${section!.attempt} of the ${section!.count} questions in ${q.subject} Section B. Clear one of them to answer this.`, { id: "section-full", position: "bottom-center", style: { marginBottom: 120 } });
      setResponses((r) => ({ ...r, [q.id]: { ...(r[q.id] ?? {}), a: null, m: mark, v: true } }));
      return true;
    }
    setResponses((r) => ({ ...r, [q.id]: { ...(r[q.id] ?? {}), a: answer === "" ? null : answer, m: mark, v: true } }));
    return true;
  };

  const saveNext = () => { if (commit(false, true)) go(idx + 1); };
  const saveMark = () => { if (commit(true, true)) go(idx + 1); };
  const markNext = () => { commit(true, false); go(idx + 1); };
  const clear = () => {
    setDraft(null);
    setResponses((r) => ({ ...r, [q.id]: { ...(r[q.id] ?? {}), a: null, v: true } }));
  };

  // keyboard: 1-4 pick an option, Enter = Save & Next
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (confirm || (e.target as HTMLElement)?.tagName === "INPUT") {
        if (e.key === "Enter" && (e.target as HTMLElement)?.tagName === "INPUT") { e.preventDefault(); saveNext(); }
        return;
      }
      if (q?.qtype === "mcq" && ["1", "2", "3", "4"].includes(e.key)) setDraft(String(Number(e.key) - 1));
      if (e.key === "Enter") { e.preventDefault(); saveNext(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  /* -------- derived */
  const counts = useMemo(() => {
    const c: Record<PaletteState, number> = { not_visited: 0, not_answered: 0, answered: 0, marked: 0, answered_marked: 0 };
    questions.filter((x) => x.subject === subject).forEach((x) => { c[paletteState(responses[x.id])] += 1; });
    return c;
  }, [questions, responses, subject]);
  const summary = useMemo(() => pattern.subjects.map((s) => {
    const c: Record<PaletteState, number> = { not_visited: 0, not_answered: 0, answered: 0, marked: 0, answered_marked: 0 };
    questions.filter((x) => x.subject === s).forEach((x) => { c[paletteState(responses[x.id])] += 1; });
    return { subject: s, ...c };
  }), [pattern.subjects, questions, responses]);
  const unsaved = (draft ?? null) !== (responses[q?.id]?.a ?? null);
  const low = remaining <= 300, warn = remaining <= 900;

  if (!q) return null;
  const firstOf = (s: string) => questions.findIndex((x) => x.subject === s);
  const palette = (
    <Palette questions={questions} responses={responses} idx={idx} subject={subject} onJump={go} counts={counts}
      sections={pattern.sections.map((s) => ({ key: s.key, label: s.label }))} />
  );

  return (
    <div className="flex h-dvh flex-col bg-bg text-fg pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]">
      {/* header */}
      <header className="flex items-center gap-2 border-b border-line bg-bg-soft px-3 py-2 sm:gap-3 sm:px-5">
        <LogoMark className="hidden h-7 w-7 sm:block" />
        <div className="min-w-0 flex-1">
          <div className="line-clamp-2 text-[13px] font-semibold leading-tight sm:truncate sm:text-sm">{shownName(test.title)}</div>
          <div className="hidden truncate text-[11.5px] text-muted sm:block">{pattern.name} · {user?.full_name}</div>
        </div>
        {offline && <span className="hidden items-center gap-1.5 text-xs text-warn sm:flex"><CloudOff className="h-3.5 w-3.5" />Reconnecting — answers kept</span>}
        <button onClick={() => (fullscreen ? document.exitFullscreen() : document.documentElement.requestFullscreen()).catch(() => undefined)}
          className="hidden rounded-lg p-2 text-muted hover:bg-elev-2 hover:text-fg sm:block" title={fullscreen ? "Exit full screen" : "Full screen"}>
          {fullscreen ? <Minimize className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
        </button>
        <div className={cn("rounded-xl border px-2 py-1.5 text-center font-mono text-[15px] font-semibold tabular-nums sm:px-3 sm:text-base",
          low ? "animate-pulse border-bad/50 bg-bad/10 text-bad" : warn ? "border-warn/40 bg-warn/10 text-warn" : "border-line bg-panel")}
          role="timer" aria-label="Time left">
          {clock(remaining)}
        </div>
        <Button variant="primary" size="sm" className="max-sm:px-2.5" onClick={() => setConfirm(true)} icon={<Send className="hidden h-3.5 w-3.5 sm:block" />}>Submit</Button>
      </header>

      {/* subject tabs */}
      <div className="flex items-center gap-1 overflow-x-auto border-b border-line px-3 py-1.5 sm:px-5">
        {pattern.subjects.map((s) => {
          const done = questions.filter((x) => x.subject === s && answered(responses[x.id])).length;
          return (
            <button key={s} onClick={() => go(firstOf(s))}
              className={cn("flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-[13px] font-medium transition",
                s === subject ? "bg-elev-2 text-fg ring-1 ring-line-strong" : "text-muted hover:text-fg")}>
              <span className="h-2 w-2 rounded-full" style={{ background: subjectColor(s) }} />{s}
              <span className="text-[11px] tabular-nums text-muted">{done}/{questions.filter((x) => x.subject === s).length}</span>
            </button>
          );
        })}
        <span className="flex-1" />
        <button onClick={() => setRough(!rough)} aria-pressed={rough}
          className={cn("flex min-h-9 shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] transition", rough ? "bg-elev-2 text-fg ring-1 ring-line-strong" : "text-muted hover:text-fg")}>
          <PenLine className="h-4 w-4" /> Rough
        </button>
        <button onClick={() => setPaletteOpen(true)} className="flex min-h-9 shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] text-muted hover:text-fg lg:hidden">
          <LayoutGrid className="h-4 w-4" /> Questions
        </button>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* question */}
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-8">
            <div className="mx-auto max-w-3xl">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="text-base font-semibold text-fg">Question {q.no}</span>
                <span className="rounded-md bg-elev-2 px-2 py-0.5 text-muted">{section?.label}</span>
                <span className="rounded-md bg-elev-2 px-2 py-0.5 tabular-nums"><span className="text-ok">+{section?.correct}</span> / <span className="text-bad">{section?.wrong}</span></span>
                {q.paper && <span className="rounded-md bg-accent-2/12 px-2 py-0.5 font-medium text-accent-2">PYQ · {q.paper}</span>}
                {bilingual && <LanguageToggle value={lang} onChange={setLang} className="ml-auto" />}
              </div>
              {lang === "hi" && !q.hindi?.question && (
                <p className="mt-3 text-xs text-muted" lang="hi">इस प्रश्न का हिंदी अनुवाद उपलब्ध नहीं है — अंग्रेज़ी में दिखाया गया है।</p>
              )}
              <Markdown className="mt-4 text-[15.5px] leading-relaxed text-fg">{shown.question}</Markdown>
              <QuestionFigures q={q} className="mt-4" />

              {q.qtype === "mcq" && shown.options ? (
                <div className="mt-5 space-y-2.5">
                  {shown.options.map((o, i) => {
                    const pic = optionFigure(q, i);
                    const on = draft === String(i);
                    return (
                      <button key={i} onClick={() => setDraft(String(i))} type="button" aria-pressed={on}
                        className={cn("flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition",
                          on ? "border-accent/70 bg-accent-soft ring-1 ring-accent/40" : "border-line bg-bg-soft hover:border-line-strong")}>
                        <span className={cn("grid h-6 w-6 shrink-0 place-items-center rounded-full border-2 text-[11px] font-semibold",
                          on ? "border-accent bg-accent text-accent-fg" : "border-line-strong text-muted")}>{i + 1}</span>
                        {pic ? <OptionFigure src={pic} n={i + 1} /> : null}
                        {o && <Markdown className="text-[14.5px]">{displayStyle(o)}</Markdown>}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="mt-5"><Keypad value={draft ?? ""} onChange={(v) => setDraft(v === "" ? null : v)} /></div>
              )}
              {draft !== null && (
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
                  How sure are you?
                  {(["sure", "unsure"] as const).map((c) => (
                    <button key={c} type="button" aria-pressed={responses[q.id]?.c === c}
                      onClick={() => setResponses((r) => ({ ...r, [q.id]: { ...(r[q.id] ?? { a: null }), c: r[q.id]?.c === c ? undefined : c } }))}
                      className={cn("min-h-9 rounded-full border px-3 py-1.5 transition", responses[q.id]?.c === c ? "border-accent bg-accent-soft text-fg" : "border-line hover:border-line-strong")}>
                      {c === "sure" ? "Sure" : "Guessing"}
                    </button>
                  ))}
                  <span>Optional, for your gap map, never your marks</span>
                </div>
              )}
              {unsaved && draft !== null && (
                <p className="mt-3 text-xs text-warn">Not saved yet — press Save & Next (or Save & Mark for Review) to keep this answer.</p>
              )}
              {section && section.attempt < section.count && (
                <p className="mt-3 text-xs text-muted">Answer any {section.attempt} of the {section.count} questions in this section.</p>
              )}
            </div>
          </div>

          {rough && <RoughPad storageKey={`focs-rough-${test.id}`} page={String(q.id)} onClose={() => setRough(false)} />}

          {/* NTA action bar */}
          <div className="border-t border-line bg-bg-soft px-3 py-2.5 sm:px-6">
            <div className="mx-auto grid max-w-3xl grid-cols-3 gap-1.5 sm:flex sm:flex-wrap sm:items-center sm:gap-2 max-sm:[&>button]:px-1 max-sm:[&>button]:tracking-[0.02em] [&>button]:min-w-0 [&>button]:pointer-coarse:min-h-11">
              <Button size="sm" variant="success" className="order-2 sm:order-none" onClick={saveNext}>Save & Next</Button>
              <Button size="sm" variant="outline" className="order-4 sm:order-none" onClick={clear}>Clear</Button>
              <Button size="sm" className="order-5 border border-warn/30 bg-warn/12 sm:order-none text-warn hover:bg-warn/20" onClick={saveMark}><span className="xl:hidden">Save & Mark</span><span className="hidden xl:inline">Save & Mark for Review</span></Button>
              <Button size="sm" className="order-6 border border-[#8b5cf6]/40 sm:order-none bg-[#7c3aed]/10 text-[#6d28d9] hover:bg-[#7c3aed]/20 dark:bg-[#7c3aed]/15 dark:text-[#a78bfa] dark:hover:bg-[#7c3aed]/25" onClick={markNext}><span className="xl:hidden">Mark & Next</span><span className="hidden xl:inline">Mark for Review & Next</span></Button>
              <span className="hidden flex-1 sm:block" />
              <Button size="sm" variant="ghost" className="order-1 sm:order-none" disabled={idx === 0} onClick={() => go(idx - 1)} icon={<ChevronLeft className="h-4 w-4" />}>Back</Button>
              <Button size="sm" variant="ghost" className="order-3 sm:order-none" disabled={idx === questions.length - 1} onClick={() => go(idx + 1)}>Next <ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
        </main>

        {/* palette */}
        <aside className="hidden w-[300px] shrink-0 overflow-y-auto border-l border-line bg-bg-soft/50 p-4 lg:block">{palette}</aside>
      </div>

      <Dialog open={paletteOpen} onClose={() => setPaletteOpen(false)} title={`${subject} · questions`}>{palette}</Dialog>

      <Dialog open={confirm} onClose={() => !submit.isPending && setConfirm(false)} wide title="Submit your test?"
        subtitle={`${clock(remaining)} still on the clock. You can't change answers after submitting.`}>
        {/* phones: one block per subject, so no column hides off the side of the dialog */}
        <div className="space-y-2 sm:hidden">
          {summary.map((s) => (
            <div key={s.subject} className="rounded-xl border border-line p-3 text-[13px]">
              <div className="mb-2 font-medium">{s.subject}</div>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1 tabular-nums">
                {([["Answered", s.answered, "text-ok"], ["Not answered", s.not_answered, "text-bad"], ["Marked", s.marked, ""],
                  ["Answered & marked", s.answered_marked, ""], ["Not visited", s.not_visited, "text-muted"]] as const).map(([k, v, c]) => (
                  <div key={k} className="flex justify-between gap-2"><dt className="text-muted">{k}</dt><dd className={c}>{v}</dd></div>
                ))}
              </dl>
            </div>
          ))}
        </div>
        <div className="hidden overflow-x-auto rounded-xl border border-line sm:block">
          <table className="w-full text-[13px]">
            <thead className="bg-bg-soft text-xs text-muted">
              <tr>{["Subject", "Answered", "Not answered", "Marked", "Answered & marked", "Not visited"].map((h) => <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {summary.map((s) => (
                <tr key={s.subject} className="border-t border-line tabular-nums">
                  <td className="px-3 py-2 font-medium">{s.subject}</td>
                  <td className="px-3 py-2 text-ok">{s.answered}</td>
                  <td className="px-3 py-2 text-bad">{s.not_answered}</td>
                  <td className="px-3 py-2">{s.marked}</td>
                  <td className="px-3 py-2">{s.answered_marked}</td>
                  <td className="px-3 py-2 text-muted">{s.not_visited}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirm(false)} disabled={submit.isPending}>Back to the test</Button>
          <Button variant="primary" loading={submit.isPending} onClick={finish} icon={<Send className="h-4 w-4" />}>Submit test</Button>
        </div>
      </Dialog>
    </div>
  );
}

export default function MockExam() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: test, isLoading } = useQuery({ queryKey: ["mock", Number(id)], queryFn: () => api.mock(Number(id)), staleTime: 0 });

  useEffect(() => {
    if (!test) return;
    if (test.status === "submitted" || test.status === "ready" || test.status === "preparing" || test.status === "failed") {
      navigate(`/app/mock/${test.id}`, { replace: true });
    }
  }, [test, navigate]);

  if (isLoading || !test || test.status !== "in_progress" || !test.questions?.length) {
    return (
      <div className="grid h-dvh place-items-center bg-bg">
        <div className="flex items-center gap-2 text-sm text-muted"><Loader2 className="h-4 w-4 animate-spin" />Opening your paper…</div>
        <Skeleton className="hidden" />
      </div>
    );
  }
  return <Exam test={test} />;
}
