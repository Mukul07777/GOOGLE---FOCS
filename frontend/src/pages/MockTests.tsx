import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarClock, CircleAlert, Clock3, Crosshair, FileText, History, Play, Sparkles, Target, Timer, Trash2, Trophy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Link, useNavigate } from "react-router-dom";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChapterTestCard } from "@/components/ChapterTestCard";
import { PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, EmptyState, ProgressBar, Segmented, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { pay, PaymentCancelled } from "@/lib/checkout";
import type { MockOffer, MockSummary } from "@/lib/types";
import { clockAt, cn, formatDate, formatDuration, formatMinutes, subjectColor, shownName } from "@/lib/utils";
import { useT } from "@/lib/i18n";

const SUBJECT_SHORT: Record<string, string> = { Physics: "P", Chemistry: "C", Mathematics: "M" };

function QuotaPill({ left, unlimited, limit, resetsAt, free_left, credits }: { left: number | null; unlimited: boolean; limit: number | null; resetsAt: string | null; free_left?: number | null; credits?: number }) {
  if (unlimited) return <Badge tone="ok">Unlimited mocks</Badge>;
  const free = free_left ?? left;
  return (
    <>
      {free ? <Badge tone="accent">{free} of {limit} free left this week</Badge> : !credits && <Badge tone="warn">Next free mock unlocks {clockAt(resetsAt)}</Badge>}
      {!!credits && <Badge tone="ok">{credits} bought mock{credits > 1 ? "s" : ""} left</Badge>}
    </>
  );
}

/** Full mocks bought one at a time or as a pack, with Pro as the other way to get more. */
function BuyMocks({ offers, canBuy }: { offers: MockOffer[]; canBuy: boolean }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const buy = useMutation({
    mutationFn: async (pack: MockOffer["id"]) => pay(await api.buyMocks(pack)),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mock-meta"] }); qc.invalidateQueries({ queryKey: ["usage"] }); toast.success("Done: your mock is ready to prepare."); },
    onError: (e) => { if (!(e instanceof PaymentCancelled)) toast.error(e instanceof Error ? e.message : "The payment didn't go through."); },
  });
  if (!canBuy) return null;
  return (
    <>
      {offers.map((o, i) => (
        <Button key={o.id} variant={i === 0 ? "primary" : "secondary"} size="lg" loading={buy.isPending && buy.variables === o.id} disabled={buy.isPending}
          onClick={() => buy.mutate(o.id)} icon={i === 0 ? <Sparkles className="h-4 w-4" /> : undefined}>
          {o.count === 1 ? `Buy 1 mock · ₹${o.price_inr}` : `${o.count} mocks · ₹${o.price_inr}`}
        </Button>
      ))}
      <Button variant="ghost" size="lg" onClick={() => navigate("/app/settings#plan")}>Or get Pro: unlimited</Button>
    </>
  );
}

function ScoreTrend({ tests }: { tests: MockSummary[] }) {
  const tr = useT();
  const data = tests.filter((t) => t.kind === "full" && t.status === "submitted" && t.score !== null).reverse()
    .map((t, i) => ({ name: `#${i + 1}`, score: t.score, ...Object.fromEntries(t.subjects.map((s) => [s.subject, s.score])) }));
  if (data.length < 2) return null;
  const subjects = [...new Set(tests.filter((t) => t.kind === "full").flatMap((t) => t.subjects.map((s) => s.subject)))];
  return (
    <Card>
      <CardHeader title={tr("Score trend")} icon={<Trophy className="h-4 w-4" />} subtitle={tr("Total and subject-wise marks across your mocks")} />
      <div className="h-64 px-2 pb-4">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 10, right: 16, left: -10, bottom: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 12 }} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 12 }} />
            <Tooltip contentStyle={{ background: "var(--panel)", border: "1px solid var(--line-strong)", borderRadius: 12 }} />
            <Legend iconType="plainline" iconSize={14} wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="score" name="Total" stroke="var(--accent)" strokeWidth={2.5} dot={{ r: 3 }} />
            {subjects.map((s) => (
              <Line key={s} type="monotone" dataKey={s} stroke={subjectColor(s)} strokeWidth={1.5} dot={false} strokeDasharray="4 3" />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

/** Class 10 and 12: a timed board-style paper on all of one subject. */
function BoardMockCard({ subjects, busy }: { subjects: string[]; busy: boolean }) {
  const tr = useT();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [subject, setSubject] = useState(subjects[0] ?? "");
  const start = useMutation({
    mutationFn: () => api.createBoardMock(subject),
    onSuccess: (t) => { qc.invalidateQueries({ queryKey: ["mocks"] }); navigate(`/app/mock/${t.id}`); },
  });
  return (
    <Card className="overflow-hidden">
      <CardHeader title={tr("Mock board exam")} icon={<Trophy className="h-4 w-4" />}
        subtitle="A timed paper on the whole subject, every chapter of this year's CBSE syllabus: 50 questions in 90 minutes." />
      <div className="space-y-4 px-5 pb-5 pt-4">
        <div className="flex flex-wrap gap-2">
          {subjects.map((s) => (
            <button key={s} type="button" aria-pressed={subject === s} onClick={() => setSubject(s)}
              className={cn("flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition",
                subject === s ? "border-accent/60 bg-accent-soft" : "border-line bg-bg-soft hover:border-line-strong")}>
              <span className="h-2 w-2 rounded-full" style={{ background: subjectColor(s) }} />{s}
            </button>
          ))}
        </div>
        <Button variant="primary" loading={start.isPending} disabled={!subject || busy} onClick={() => start.mutate()} icon={<Sparkles className="h-4 w-4" />}>
          Prepare my {subject} board paper
        </Button>
        {start.error && <p className="text-sm text-bad">{start.error instanceof ApiError ? start.error.message : "Couldn't prepare the paper. Try again."}</p>}
      </div>
    </Card>
  );
}

export default function MockTests() {
  const tr = useT();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: meta, error: metaError } = useQuery({ queryKey: ["mock-meta"], queryFn: api.mockMeta, staleTime: 0, retry: false });
  const { data: plans } = useQuery({ queryKey: ["plans"], queryFn: () => api.plans() });
  const canBuy = !!plans?.payments; // no Upgrade button where Pro can't be bought (payments not set up yet)
  const { data: tests, isLoading } = useQuery({
    queryKey: ["mocks"], queryFn: api.mocks,
    refetchInterval: (q) => (q.state.data?.some((t) => t.status === "preparing") ? 2000 : false),
  });
  const [pattern, setPattern] = useState<string | null>(null);
  const chosen = meta?.patterns.find((p) => p.id === (pattern ?? meta.default));

  const create = useMutation({
    mutationFn: () => api.createMock(chosen!.id),
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ["mocks"] });
      navigate(`/app/mock/${t.id}`);  // (a paper still being written opens on its warm-up)
    },
  });
  const discard = useMutation({ mutationFn: api.discardMock, onSuccess: () => qc.invalidateQueries({ queryKey: ["mocks"] }) });

  const running = tests?.find((t) => t.status === "in_progress");
  const pending = tests?.filter((t) => t.status === "ready" || t.status === "preparing" || (t.status === "failed" && !t.started_at)) ?? [];
  const done = tests?.filter((t) => t.status === "submitted") ?? [];
  const outOfMocks = !!meta && !meta.quota.unlimited && !meta.quota.left && !pending.some((t) => t.status === "ready" && t.kind === "full");
  const best = done.filter((t) => t.kind === "full").reduce<MockSummary | null>((b, t) => (!b || (t.score ?? 0) > (b.score ?? 0) ? t : b), null);
  const college = meta?.exam === "college" || meta?.exam === "cbse";  // a semester, the boards: tests are on one subject, there is no full mock
  const gate = meta?.exam === "gate";
  const ssc = meta?.exam === "ssc_cgl";

  // 404: UPSC, CA, other (never another exam's papers); 403: a school class without tests (only Class 10 and 12 have them)
  if (metaError instanceof ApiError && (metaError.status === 404 || metaError.status === 403)) {
    return (
      <EmptyState icon={<Timer className="h-6 w-6" />} title={metaError.status === 403 ? "Tests open in Class 10 and Class 12" : "Tests follow your exam's syllabus"} body={metaError.message}
        action={<Link to="/app/settings"><Button variant="secondary">{tr("Open Settings")}</Button></Link>} />
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader eyebrow={tr("Exam practice")} title={tr(college ? "Tests" : "Full mock tests")}
        subtitle={college
          ? tr("Timed MCQ tests on any of your subjects: one chapter, a few, or the whole subject. An exam screen, then your score, weak chapters and time use.")
          : gate ? "A full GATE paper: 65 questions for 100 marks in 3 hours, General Aptitude and your subjects in their usual proportions, with negative marking and a full analysis."
          : meta?.exam === "ssc_cgl"
          ? tr("SSC CGL papers in the current pattern: Tier-I (100 questions in an hour, +2 / −0.5) or Tier-II Paper-I, with real past-paper questions in English and Hindi, figures included.")
          : meta?.exam === "neet"
          ? tr("Real NEET conditions: 180 questions in 3 h 20 min, NTA-style screen, +4 / −1 marking, and a full analysis when you submit.")
          : tr("Real JEE Main conditions: 3 hours, NTA-style screen, +4 / −1 marking, and a full analysis when you submit.")}
        actions={<Link to="/app/weak?add=1"><Button variant="secondary" icon={<Crosshair className="h-4 w-4" />}>{tr("Add a test taken elsewhere")}</Button></Link>} />

      {running && (
        <Card className="ring-gradient flex flex-wrap items-center gap-4 p-5">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-bad/15 text-bad"><Timer className="h-5 w-5" /></div>
          <div className="min-w-0 flex-1 basis-48">
            <div className="font-semibold">{running.title} is running</div>
            <div className="text-sm text-muted">{formatDuration(running.remaining_sec ?? 0)} left on the clock — the timer keeps running like the real exam.</div>
          </div>
          <Button variant="primary" onClick={() => navigate(`/exam/${running.id}`)} icon={<Play className="h-4 w-4" />}>{tr("Resume test")}</Button>
        </Card>
      )}

      {!college && <Card className="overflow-hidden">
        <div className="grid gap-6 p-5 sm:p-6 md:grid-cols-[1.3fr_1fr]">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="accent"><Target className="h-3 w-3" /> {meta?.exam === "neet" ? "NEET UG" : ssc ? "SSC CGL" : gate ? "GATE" : "JEE Main"}</Badge>
              {meta && <QuotaPill {...meta.quota} resetsAt={meta.quota.resets_at} />}
            </div>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight">{chosen?.name ?? "Full mock"}</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-muted">{chosen?.description}</p>
            {meta && meta.patterns.length > 1 && (
              <Segmented className="mt-4 flex-wrap" value={chosen?.id ?? meta.default ?? ""} onChange={setPattern}
                options={meta.patterns.map((p) => ({ value: p.id, label: ({ jee_main_30: "Main pre-2025 · 90 Q", jee_main_25: "Main · 75 Q", jee_advanced: "Advanced · 48 Q" } as Record<string, string>)[p.id] ?? p.short }))} />
            )}
            <div className="mt-5 flex flex-wrap gap-2">
              {outOfMocks ? (meta?.quota.offers?.length ? <BuyMocks offers={meta.quota.offers} canBuy={canBuy} /> : canBuy && (
                <Button variant="primary" size="lg" onClick={() => navigate("/app/settings#plan")} icon={<Sparkles className="h-4 w-4" />}>
                  Get more mocks with Pro
                </Button>
              )) : (
                <Button variant="primary" size="lg" loading={create.isPending} disabled={!chosen || !!running}
                  onClick={() => create.mutate()} icon={<Sparkles className="h-4 w-4" />}>
                  {pending.some((t) => t.status === "ready" && t.pattern === chosen?.id) ? "Open my paper" : "Prepare my paper"}
                </Button>
              )}
            </div>
            <p className="mt-2 text-xs text-muted">
              {outOfMocks
                ? `You've taken this week's free mock. The next free one unlocks ${clockAt(meta?.quota.resets_at)}${canBuy ? (meta?.quota.offers?.length ? ". A bought mock never runs out; chapter tests below are free." : " — Pro has unlimited mocks.") : ". Chapter tests below don't count towards it."}`
                : meta && !meta.quota.unlimited && !meta.quota.free_left && meta.quota.credits
                  ? `This week's free mock is used, so starting this one uses ${meta.quota.credits > 1 ? `1 of your ${meta.quota.credits} bought mocks` : "your bought mock"}.`
                  : "Reading the instructions is free — a mock only counts once you press Start."}
            </p>
          </div>
          {chosen ? (
            <div className="grid grid-cols-2 gap-3 self-start">
              {[
                [FileText, `${chosen.total_questions}`, "questions"],
                [Clock3, formatMinutes(chosen.duration_min), "duration"],
                [Trophy, `${chosen.max_score}`, "maximum marks"],
                [CircleAlert, gate ? "−⅓ / −⅔" : ssc ? (chosen.id === "ssc_cgl_t2" ? "+3 / −1" : "+2 / −0.5") : "+4 / −1", gate ? "for a wrong 1 / 2-mark answer" : "marking"],
              ].map(([Icon, big, small]) => {
                const I = Icon as typeof FileText;
                return (
                  <div key={String(small)} className="rounded-2xl border border-line bg-bg-soft p-4">
                    <I className="h-4 w-4 text-accent" />
                    <div className="mt-2 text-lg font-semibold">{String(big)}</div>
                    <div className="text-xs text-muted">{String(small)}</div>
                  </div>
                );
              })}
            </div>
          ) : <Skeleton className="h-48" />}
        </div>
      </Card>}

      {pending.map((t) => (
        <Card key={t.id} className="flex flex-wrap items-center gap-4 p-5">
          <div className={cn("grid h-11 w-11 place-items-center rounded-xl", t.status === "failed" ? "bg-bad/15 text-bad" : "bg-accent-soft text-accent")}>
            {t.status === "failed" ? <CircleAlert className="h-5 w-5" /> : <FileText className="h-5 w-5" />}
          </div>
          <div className="min-w-0 flex-1 basis-48">
            <div className="font-semibold">{shownName(t.title)}</div>
            {t.status === "preparing" && (
              <>
                <div className="text-sm text-muted">Writing and double-checking fresh questions for you… {t.progress}%</div>
                <ProgressBar value={t.progress} className="mt-2 max-w-sm" />
              </>
            )}
            {t.status === "ready" && (
              <div className="text-sm text-muted">
                Your paper is ready. Read the instructions, then start when you have {t.kind === "full" && t.duration_min >= 180 ? "3 quiet hours" : `${t.duration_min} quiet minutes`}.
              </div>
            )}
            {t.status === "failed" && <div className="text-sm text-bad">{t.error}</div>}
          </div>
          {t.status === "ready" && <Button variant="primary" onClick={() => navigate(`/app/mock/${t.id}`)} icon={<ArrowRight className="h-4 w-4" />}>{tr("Instructions")}</Button>}
          <Button variant="ghost" size="icon" title="Discard" aria-label="Discard paper" loading={discard.isPending && discard.variables === t.id}
            onClick={() => discard.mutate(t.id)}><Trash2 className="h-4 w-4" /></Button>
        </Card>
      ))}

      {meta?.board_mock && <BoardMockCard subjects={Object.keys(meta.syllabus)} busy={!!running} />}

      {meta && <ChapterTestCard meta={meta} busy={!!running} />}

      <ScoreTrend tests={tests ?? []} />

      <Card>
        <CardHeader title={tr("Your record")} icon={<History className="h-4 w-4" />}
          subtitle={done.length ? `${done.length} test${done.length === 1 ? "" : "s"}${best ? ` · best full mock ${best.score} / ${best.max_score}` : ""}`
            : college ? "Every test you take is saved here with its analysis" : "Every mock and chapter test you take is saved here with its analysis"} />
        {isLoading && <div className="space-y-2 p-5"><Skeleton className="h-14" /><Skeleton className="h-14" /></div>}
        {!isLoading && !done.length && (
          <EmptyState className="py-12" icon={<CalendarClock className="h-6 w-6" />} title={tr(college ? "No tests yet" : "No mocks yet")}
            body={college ? "Test a chapter you've just finished, or a whole subject before its exam. Focs shows your score, weak chapters and time use."
              : "Take your first full mock under exam conditions — Focs shows your score, subject split, weak chapters and time use."} />
        )}
        <div className="divide-y divide-line">
          {done.map((t) => (
            <button key={t.id} onClick={() => navigate(`/app/mock/${t.id}`)}
              className="flex w-full flex-wrap items-center gap-4 px-5 py-4 text-left transition hover:bg-elev-2/50">
              <div className="w-20 shrink-0">
                <div className="text-xl font-semibold tabular-nums">{t.score}</div>
                <div className="text-xs text-muted">/ {t.max_score}</div>
              </div>
              <div className="min-w-0 flex-1 basis-40">
                <div className="flex items-center gap-2 truncate text-sm font-medium">{shownName(t.title)}{t.kind === "chapter" && <Badge>{t.pattern_name.startsWith("Subject") ? "subject" : "chapter"}</Badge>}</div>
                <div className="text-xs text-muted">{formatDate(t.submitted_at, true)} · {t.accuracy ?? 0}% accuracy · {formatDuration(t.time_sec ?? 0)} used</div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {t.subjects.map((s) => (
                  <span key={s.subject} className="rounded-lg border border-line bg-bg-soft px-2 py-1 text-xs tabular-nums" title={s.subject}>
                    <span className="font-semibold" style={{ color: subjectColor(s.subject) }}>{SUBJECT_SHORT[s.subject] ?? s.subject[0]}</span> {s.score}
                  </span>
                ))}
              </div>
              <ArrowRight className="h-4 w-4 text-muted" />
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}
