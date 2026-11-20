import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, BarChart3, BookOpenCheck, Check, CircleAlert, Clock3, Flag, Lightbulb, ListChecks, Play, Target, X,
} from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { Markdown } from "@/components/Markdown";
import { LanguageToggle, OptionFigure, optionFigure, QuestionFigures, shownIn, usePaperLanguage, type PaperLanguage } from "@/components/QuestionMedia";
import { PaletteLegend } from "@/components/MockPalette";
import { Solution } from "@/components/Explain";
import { GapMapCard, Warmup } from "@/components/TestBridge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, CardHeader, EmptyState, ProgressBar, ProgressRing, Segmented, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { displayStyle } from "@/lib/math";
import type { MockDetail, MockQuestion, MockResult } from "@/lib/types";
import { cn, formatDate, formatDuration, formatMinutes, subjectColor, shownName } from "@/lib/utils";

const OUTCOME_COLOR = { correct: "var(--ok)", incorrect: "var(--bad)", unattempted: "var(--line-strong)" } as const;

/* ================================================================== preparing / instructions */
function Instructions({ test }: { test: MockDetail }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [agreed, setAgreed] = useState(false);
  const p = test.pattern_info!;
  const start = useMutation({
    mutationFn: () => api.startMock(test.id),
    onSuccess: (t) => {
      qc.setQueryData(["mock", test.id], t);
      qc.invalidateQueries({ queryKey: ["mocks"] });
      qc.invalidateQueries({ queryKey: ["usage"] });
      navigate(`/exam/${test.id}`);
    },
  });
  const begin = () => {
    document.documentElement.requestFullscreen?.().catch(() => undefined); // needs this click; the exam works without it
    start.mutate();
  };

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <Link to="/app/mock" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft className="h-4 w-4" /> {test.kind === "full" ? "Mock tests" : "Tests"}</Link>
      <Card className="overflow-hidden">
        <div className="border-b border-line bg-bg-soft px-6 py-5">
          <Badge tone="accent"><BookOpenCheck className="h-3 w-3" /> General instructions</Badge>
          <h1 className="mt-3 text-[30px]">{shownName(test.title)}</h1>
          <p className="mt-1 text-sm text-muted">{p.name} · {formatMinutes(p.duration_min)} · {p.max_score} marks</p>
        </div>
        <div className="grid gap-6 p-6 md:grid-cols-[1.25fr_1fr]">
          <ol className="list-decimal space-y-2.5 pl-5 text-[14px] leading-relaxed text-fg-soft marker:text-muted">
            <li>The clock is set on the server and runs for <b className="text-fg">{formatMinutes(p.duration_min)}</b> from the moment you start — closing the tab does not stop it. When it reaches zero the paper is submitted automatically.</li>
            {p.subject_counts ? (  // subjects with their own numbers of questions (GATE, a last-day test)
              <li>
                {p.subjects.length > 1
                  ? <>The paper has {p.subjects.length} subjects: {p.subjects.map((s) => `${s} (${p.subject_counts![s] ?? 0} questions)`).join(", ")}. Switch subjects with the tabs at the top.</>
                  : <>This {p.subjects[0]} test{p.chapters.length ? ` on ${p.chapters.join(", ")}` : ""} has {p.subject_counts[p.subjects[0]] ?? p.total_questions} questions.</>}
              </li>
            ) : (
              <li>
                {p.subjects.length > 1
                  ? <>The paper has {p.subjects.length} subjects — {p.subjects.join(", ")} — each with </>
                  : <>This {p.subjects[0]} test{p.chapters.length ? ` on ${p.chapters.join(", ")}` : ""} has </>}
                {p.sections.filter((s) => s.count).map((s) => `${s.count} ${s.qtype === "mcq" ? "MCQs" : "numerical questions"}`).join(" and ")}.
                {p.subjects.length > 1 && " Switch subjects with the tabs at the top."}
              </li>
            )}
            <li>Choosing an option does not save it. Press <b className="text-fg">Save & Next</b> to save your answer, or <b className="text-fg">Save & Mark for Review</b> to save it and come back later.</li>
            <li>Answers marked for review <b className="text-fg">are evaluated</b>. A question that is only marked (with no answer) is not.</li>
            {p.notes.map((n) => <li key={n}>{n}</li>)}
            <li>Answers are saved to your account as you go, so a refresh or a dropped connection doesn't lose them.</li>
          </ol>
          <div className="space-y-5">
            <div>
              <div className="mb-2.5 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Question palette</div>
              <PaletteLegend />
            </div>
            <div>
              <div className="mb-2.5 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Marking scheme (per subject)</div>
              <div className="overflow-hidden rounded-xl border border-line text-[13px]">
                {p.sections.map((s) => (
                  <div key={s.key} className="flex items-center justify-between gap-3 border-b border-line px-3 py-2.5 last:border-0">
                    <span className="text-fg-soft">{s.label}</span>
                    <span className="shrink-0 tabular-nums"><span className="text-ok">+{s.correct}</span> / <span className="text-bad">{s.wrong}</span></span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-3 border-t border-line bg-bg-soft px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex cursor-pointer items-center gap-2.5 text-sm">
            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="h-4 w-4 accent-[var(--accent)]" />
            I have read and understood the instructions.
          </label>
          <Button variant="primary" size="lg" disabled={!agreed} loading={start.isPending} onClick={begin} icon={<Play className="h-4 w-4" />}>
            I am ready to begin
          </Button>
        </div>
      </Card>
    </div>
  );
}

/* ================================================================== result */
function SubjectCard({ s }: { s: MockResult["subjects"][number] }) {
  return (
    <div className="rounded-2xl border border-line bg-bg-soft p-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm font-semibold"><span className="h-2.5 w-2.5 rounded-full" style={{ background: subjectColor(s.subject) }} />{s.subject}</span>
        <span className="text-lg font-semibold tabular-nums">{s.score}<span className="text-xs font-normal text-muted"> / {s.max}</span></span>
      </div>
      <ProgressBar value={(100 * Math.max(0, s.score)) / s.max} className="mt-3" />
      <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded-lg bg-ok/10 py-1.5"><div className="font-semibold text-ok">{s.correct}</div><div className="text-muted">correct</div></div>
        <div className="rounded-lg bg-bad/10 py-1.5"><div className="font-semibold text-bad">{s.incorrect}</div><div className="text-muted">wrong</div></div>
        <div className="rounded-lg bg-elev-2 py-1.5"><div className="font-semibold">{s.unattempted}</div><div className="text-muted">left</div></div>
      </div>
      <div className="mt-3 space-y-1 text-xs text-muted">
        {s.sections.map((sec) => (
          <div key={sec.key} className="flex justify-between"><span>{sec.label.split("·")[0].trim()} · {sec.label.split("·")[1]?.trim()}</span><span className="tabular-nums text-fg-soft">{sec.score} / {sec.max}</span></div>
        ))}
        <div className="flex justify-between"><span>Accuracy · time</span><span className="tabular-nums text-fg-soft">{s.accuracy}% · {formatDuration(s.time_sec)}</span></div>
      </div>
    </div>
  );
}

function ReportDialog({ q, onClose }: { q: MockQuestion | null; onClose: () => void }) {
  const [reason, setReason] = useState("Answer key looks wrong");
  const report = useMutation({
    mutationFn: () => api.reportQuestion(q!.id, reason),
    onSuccess: () => { toast.success("Thanks — we'll check it. Questions reported twice are pulled from new papers."); onClose(); },
  });
  return (
    <Dialog open={!!q} onClose={onClose} title="Report a problem" subtitle={q ? `Question ${q.no} · ${q.subject}` : ""}>
      <div className="space-y-2">
        {["Answer key looks wrong", "Question is unclear or missing data", "Formatting is broken", "Out of the syllabus"].map((r) => (
          <label key={r} className={cn("flex cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-2.5 text-sm transition",
            reason === r ? "border-accent/50 bg-accent-soft" : "border-line hover:border-line-strong")}>
            <input type="radio" name="reason" checked={reason === r} onChange={() => setReason(r)} className="accent-[var(--accent)]" />{r}
          </label>
        ))}
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant="primary" loading={report.isPending} onClick={() => report.mutate()} icon={<Flag className="h-4 w-4" />}>Send report</Button>
      </div>
    </Dialog>
  );
}

function ReviewCard({ q, row, onReport, lang }: { q: MockQuestion; row: MockResult["questions"][number] | undefined; onReport: () => void; lang: PaperLanguage }) {
  const text = shownIn(q, lang);
  const [open, setOpen] = useState(row?.outcome === "incorrect");
  const outcome = row?.outcome ?? "unattempted";
  const yours = row?.answer ?? null;
  return (
    <div className="panel p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="grid h-7 min-w-7 place-items-center rounded-lg bg-elev-2 px-1.5 font-mono font-semibold">{q.no}</span>
        <Badge dot={subjectColor(q.subject)}>{q.subject}</Badge>
        <Badge>Section {q.section}</Badge>
        {q.chapter && <span className="text-muted">{q.chapter}</span>}
        {q.difficulty && <span className="text-muted">· {q.difficulty}</span>}
        {q.paper && <Badge tone="cyan">PYQ · {q.paper}</Badge>}
        <span className="flex-1" />
        {row?.marked && <Badge tone="accent">marked</Badge>}
        {row?.confidence === "sure" && outcome === "incorrect" && <Badge tone="bad">Blind spot: you were sure</Badge>}
        {row?.confidence === "unsure" && outcome === "correct" && <Badge tone="warn">Right, but guessed</Badge>}
        <span className="text-muted"><Clock3 className="mr-1 inline h-3 w-3" />{formatDuration(row?.time_sec ?? 0)}</span>
        <Badge tone={outcome === "correct" ? "ok" : outcome === "incorrect" ? "bad" : "neutral"}>
          {outcome === "correct" ? `+${row?.marks}` : outcome === "incorrect" ? `${row?.marks}` : "0"} · {outcome === "unattempted" ? "not answered" : outcome}
        </Badge>
      </div>
      <Markdown className="mt-3 text-[14.5px] text-fg">{text.question}</Markdown>
      <QuestionFigures q={q} className="mt-3" />
      {q.qtype === "mcq" && text.options ? (
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {text.options.map((o, i) => {
            const pic = optionFigure(q, i);
            const right = String(i) === q.answer, picked = yours === String(i);
            return (
              <div key={i} className={cn("flex items-center gap-2.5 rounded-xl border px-3 py-2 text-sm",
                right ? "border-ok/50 bg-ok/10" : picked ? "border-bad/50 bg-bad/10" : "border-line")}>
                <span className={cn("grid h-6 w-6 shrink-0 place-items-center rounded-md border text-[11px] font-semibold",
                  right ? "border-ok bg-ok text-white" : picked ? "border-bad bg-bad text-white" : "border-line-strong")}>
                  {right ? <Check className="h-3 w-3" /> : picked ? <X className="h-3 w-3" /> : i + 1}
                </span>
                {pic && <OptionFigure src={pic} n={i + 1} />}
                {o && <Markdown className="text-sm">{displayStyle(o)}</Markdown>}
                {picked && <span className="ml-auto shrink-0 text-[11px] text-muted">your answer</span>}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          <span className={cn("rounded-xl border px-3 py-2", outcome === "correct" ? "border-ok/50 bg-ok/10" : outcome === "incorrect" ? "border-bad/50 bg-bad/10" : "border-line")}>
            Your answer: <b className="tabular-nums">{yours ?? "—"}</b>
          </span>
          <span className="rounded-xl border border-ok/50 bg-ok/10 px-3 py-2">Correct answer: <b className="tabular-nums">{q.answer}</b></span>
        </div>
      )}
      <div className="mt-3 flex items-center gap-3">
        <button onClick={() => setOpen(!open)} className="text-[13px] font-medium text-accent hover:underline">{open ? "Hide solution" : "Show solution"}</button>
        <span className="flex-1" />
        <button onClick={onReport} className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg"><Flag className="h-3 w-3" /> Report a problem</button>
      </div>
      {open && q.solution && (
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="mt-2 rounded-xl border border-line bg-bg-soft p-4">
          <Solution q={q} />
        </motion.div>
      )}
    </div>
  );
}

function Result({ test }: { test: MockDetail }) {
  const r = test.result!;
  const t = r.total;
  const qs = test.questions ?? [];
  const [lang, setLang] = usePaperLanguage();
  const rows = useMemo(() => new Map(r.questions.map((x) => [x.id, x])), [r]);
  // open on the wrong answers, or on every solution when there are none (a blank paper used to open on "Nothing here")
  const [filter, setFilter] = useState<"all" | "incorrect" | "unattempted" | "correct" | "marked">(
    () => (r.questions.some((x) => x.outcome === "incorrect") ? "incorrect" : "all"));
  const [subject, setSubject] = useState<string>("all");
  const [reporting, setReporting] = useState<MockQuestion | null>(null);
  const shown = qs.filter((q) => {
    const row = rows.get(q.id);
    if (subject !== "all" && q.subject !== subject) return false;
    if (filter === "all") return true;
    if (filter === "marked") return !!row?.marked;
    return row?.outcome === filter;
  });
  const timeData = r.questions.map((x, i) => ({ no: i + 1, min: +(x.time_sec / 60).toFixed(1), outcome: x.outcome, subject: x.subject }));

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <Link to="/app/mock" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft className="h-4 w-4" /> {test.kind === "full" ? "Mock tests" : "Tests"}</Link>
      <Card className="noise relative overflow-hidden p-6">
        <div className="relative flex flex-col gap-6 md:flex-row md:items-center">
          <ProgressRing value={(100 * Math.max(0, t.score)) / t.max} size={128} stroke={10}>
            <div className="text-center"><div className="text-3xl font-semibold tabular-nums">{t.score}</div><div className="text-xs text-muted">of {t.max}</div></div>
          </ProgressRing>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">Result</div>
            <h1 className="mt-1 text-[30px]">{shownName(test.title)}</h1>
            <p className="mt-1 text-sm text-muted">{test.pattern_name} · submitted {formatDate(test.submitted_at, true)}</p>
            <Link to="/app/mock" className="no-print inline-flex min-h-10 items-center text-sm font-medium text-accent hover:underline">Take another test</Link>
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
              {[
                ["Correct", t.correct, "text-ok"], ["Wrong", t.incorrect, "text-bad"], ["Not answered", t.unattempted, ""],
                ["Accuracy", `${t.accuracy}%`, ""], ["Time used", formatDuration(t.time_sec), ""],
              ].map(([label, value, tone]) => (
                <div key={String(label)} className="rounded-xl border border-line bg-bg-soft/80 px-3 py-2">
                  <div className={cn("text-lg font-semibold tabular-nums", String(tone))}>{String(value)}</div>
                  <div className="text-[11.5px] text-muted">{String(label)}</div>
                </div>
              ))}
            </div>
            {t.negative > 0 && <p className="mt-3 text-xs text-bad">−{t.negative} marks lost to negative marking</p>}
            {!!test.tab_switches && <p className="mt-1 text-xs text-warn">You left the test window {test.tab_switches} time{test.tab_switches === 1 ? "" : "s"}.</p>}
          </div>
        </div>
      </Card>

      {test.gap_map && <GapMapCard map={test.gap_map} />}

      {/* a test on one subject: its card sits with the advice below instead of alone in a row of three */}
      {r.subjects.length > 1 && <div className="grid grid-cols-1 gap-3 md:grid-cols-3">{r.subjects.map((s) => <SubjectCard key={s.subject} s={s} />)}</div>}

      <div className={cn("grid gap-5", r.subjects.length === 1 ? "lg:grid-cols-[0.8fr_1fr_1.15fr]" : "md:grid-cols-[1fr_1.15fr]")}>
        {r.subjects.length === 1 && <SubjectCard s={r.subjects[0]} />}
        <Card>
          <CardHeader title="What to fix next" icon={<Lightbulb className="h-4 w-4" />} />
          <ul className="space-y-2.5 p-5 text-[13.5px] leading-relaxed text-fg-soft">
            {r.insights.map((i) => <li key={i} className="flex gap-2"><Target className="mt-0.5 h-4 w-4 shrink-0 text-accent" />{i}</li>)}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Weakest chapters" icon={<ListChecks className="h-4 w-4" />} subtitle="Marks per chapter, worst first" />
          <div className="max-h-64 divide-y divide-line overflow-y-auto">
            {r.chapters.filter((c) => c.attempted || c.unattempted).slice(0, 12).map((c) => (
              <div key={c.subject + c.chapter} className="flex items-center gap-3 px-5 py-2 text-[13px]">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: subjectColor(c.subject) }} />
                <span className="min-w-0 flex-1 truncate">{c.chapter}</span>
                <span className="shrink-0 text-xs text-muted">{c.correct} right · {c.incorrect} wrong · {c.unattempted} left</span>
                <span className={cn("w-10 shrink-0 text-right font-semibold tabular-nums", c.score < 0 ? "text-bad" : c.score > 0 ? "text-ok" : "text-muted")}>{c.score > 0 ? `+${c.score}` : c.score}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Time per question" icon={<BarChart3 className="h-4 w-4" />} subtitle="Minutes spent on each question — green right, red wrong, grey left" />
        <div className="h-48 px-2 pb-3">
          <ResponsiveContainer>
            <BarChart data={timeData} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
              <XAxis dataKey="no" tickLine={false} axisLine={false} interval={9} tick={{ fill: "var(--muted)", fontSize: 11 }} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} />
              <Tooltip cursor={{ fill: "var(--elev-2)" }} contentStyle={{ background: "var(--panel)", border: "1px solid var(--line-strong)", borderRadius: 12 }}
                formatter={(v) => [`${v} min`, "Time"]} labelFormatter={(n) => `Q${n} · ${timeData[Number(n) - 1]?.subject ?? ""}`} />
              <Bar dataKey="min" radius={[3, 3, 0, 0]}>
                {timeData.map((d) => <Cell key={d.no} fill={OUTCOME_COLOR[d.outcome]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold tracking-tight">Review answers</h2>
          <div className="flex flex-wrap gap-2">
            {qs.some((x) => x.hindi?.question) && <LanguageToggle value={lang} onChange={setLang} />}
            <Segmented size="sm" value={subject} onChange={setSubject} options={[{ value: "all", label: "All" }, ...r.subjects.map((s) => ({ value: s.subject, label: s.subject }))]} />
            <Segmented size="sm" value={filter} onChange={setFilter} options={[
              { value: "all", label: "All" }, { value: "incorrect", label: `Wrong · ${t.incorrect}` }, { value: "unattempted", label: `Left · ${t.unattempted}` },
              { value: "correct", label: `Right · ${t.correct}` }, { value: "marked", label: "Marked" },
            ]} />
          </div>
        </div>
        {!shown.length && <Card className="p-8 text-center text-sm text-muted">Nothing here — try another filter.</Card>}
        {shown.slice(0, 40).map((q) => <ReviewCard key={q.id} q={q} row={rows.get(q.id)} lang={lang} onReport={() => setReporting(q)} />)}
        {shown.length > 40 && <p className="text-center text-xs text-muted">Showing 40 of {shown.length} — narrow the filter to see the rest.</p>}
      </div>
      <ReportDialog q={reporting} onClose={() => setReporting(null)} />
    </div>
  );
}

/* ================================================================== page */
export default function MockView() {
  const { id } = useParams();
  const testId = Number(id);
  const navigate = useNavigate();
  const { data: test, isLoading, error } = useQuery({
    queryKey: ["mock", testId], queryFn: () => api.mock(testId),
    refetchInterval: (q) => (q.state.data?.status === "preparing" ? 2000 : false),
  });

  if (error && !test) return <EmptyState icon={<ListChecks className="h-6 w-6" />} title="Test not found" body="This test isn't yours, or it was deleted." action={<Link to="/app/mock"><Button>All tests</Button></Link>} />;
  if (isLoading || !test) return <div className="mx-auto max-w-4xl space-y-4"><Skeleton className="h-10 w-48" /><Skeleton className="h-96" /></div>;
  if (test.status === "submitted" && test.result) return <Result test={test} />;
  if (test.status === "ready" && test.pattern_info) return <Instructions test={test} />;
  if (test.status === "preparing") return <Warmup test={test} />;
  return (
    <div className="mx-auto max-w-xl">
      <Card className="p-8 text-center">
        {test.status === "in_progress" && (
          <>
            <Clock3 className="mx-auto h-8 w-8 text-bad" />
            <h1 className="mt-3 text-[26px]">This {test.kind === "full" ? "mock" : "test"} is running</h1>
            <p className="mt-1 text-sm text-muted">{formatDuration(test.remaining_sec ?? 0)} left on the clock.</p>
            <Button variant="primary" className="mt-4" onClick={() => navigate(`/exam/${test.id}`)} icon={<Play className="h-4 w-4" />}>Resume test</Button>
          </>
        )}
        {test.status === "failed" && (
          <>
            <CircleAlert className="mx-auto h-8 w-8 text-bad" />
            <h1 className="mt-3 text-[26px]">Couldn't prepare this paper</h1>
            <p className="mt-1 text-sm text-muted">{test.error}</p>
            <Button className="mt-4" onClick={() => navigate("/app/mock")}>{test.kind === "full" ? "Back to mock tests" : "Back to tests"}</Button>
          </>
        )}
      </Card>
    </div>
  );
}
