import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight, BookOpen, Check, ChevronDown, ClipboardCheck, Clock, Flag, Hourglass, Layers, ListChecks, Lock, Moon, Play, Plus, RotateCcw,
  ShieldAlert, Sigma, Target, Undo2, X,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { NotesReader } from "@/components/DetailedNotes";
import { ScrollX } from "@/components/ScrollX";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, EmptyState, Label, ProgressBar, ProgressRing, Segmented, Skeleton } from "@/components/ui/primitives";
import { api, ApiError, type LastDayBody } from "@/lib/api";
import { useFocus } from "@/lib/focus";
import type { LastDayChapter, LastDayPlan, SyllabusChapter, SyllabusTree } from "@/lib/types";
import { useAuth } from "@/stores/auth";
import { cn, formatMinutes, hasTests, subjectColor, shownName } from "@/lib/utils";
import { useT } from "@/lib/i18n";

type Scope = LastDayPlan["scope"];
const WEIGHT_TONE = { high: "bad", medium: "warn", low: "neutral" } as const;
const today = () => new Date().toLocaleDateString("en-CA");  // local YYYY-MM-DD

/** How the student has set the page up; kept on this device so tomorrow's test is still there after a reload. */
interface Setup {
  scope: Scope; subject: string; hours: number;
  /** the chapters in tomorrow's test */
  picked: string[];
  /** chapter id → the topics of it that are coming (a chapter not listed here: all of it) */
  topics: Record<string, string[]>;
  /** chapters added to today's list by hand / taken off it */
  include: string[]; exclude: string[];
  /** everything important in the syllabus, or only what has been studied */
  cover: LastDayPlan["cover"];
  /** questions in the test that ends the day */
  count: number;
}
const SETUP_KEY = "focs-lastday-setup";
const FRESH: Setup = { scope: "all", subject: "", hours: 6, picked: [], topics: {}, include: [], exclude: [], cover: "important", count: 15 };
const loadSetup = (): Setup => { try { return { ...FRESH, ...JSON.parse(localStorage.getItem(SETUP_KEY) ?? "{}") }; } catch { return FRESH; } };

/** A choice's name, shorter on a phone so a row of choices fits without sliding. */
const fit = (full: string, brief: string) => <><span className="sm:hidden">{brief}</span><span className="hidden sm:inline">{full}</span></>;

/** "Physics, Chemistry and Mathematics" */
const listed = (names: string[]) => (names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`);

/** A step of the page: a number and a name in wide capitals, like the lookbook's section heads. */
function Step({ n, children }: { n: string; children: ReactNode }) {
  return <div className="hud mb-3 text-muted"><span className="tabular-nums">{n}</span>{children}</div>;
}

/** How much of the paper a chapter carries: three bars, all of them for high weightage. */
function WeightMark({ weightage, className }: { weightage: "high" | "medium" | "low"; className?: string }) {
  const n = { high: 3, medium: 2, low: 1 }[weightage];
  return (
    <span aria-hidden className={cn("inline-flex shrink-0 items-end gap-[2px]", className)}>
      {[1, 2, 3].map((i) => <span key={i} className={cn("w-[3px] bg-current", i > n && "opacity-25")} style={{ height: 3 + 2 * i }} />)}
    </span>
  );
}

function ChapterCard({ c, index, onRemove }: { c: LastDayChapter; index: number; onRemove: () => void }) {
  const tr = useT();
  const qc = useQueryClient();
  const navigate = useNavigate();
  // one reader for the chapter's capsule and for the notes of any of its topics
  const [reading, setReading] = useState<{ topic?: { id: string; name: string } } | null>(null);
  const capsule = useQuery({ queryKey: ["capsule", c.id], queryFn: () => api.chapterCapsule(c.id), enabled: !!reading && !reading.topic, staleTime: Infinity, retry: false });
  const topicId = reading?.topic?.id ?? "";
  const topicNotes = useQuery({ queryKey: ["topic-notes", topicId], queryFn: () => api.topicNotes(topicId), enabled: !!topicId, staleTime: Infinity, retry: false });
  const writtenNow = capsule.data?.written_now || topicNotes.data?.written_now;
  useEffect(() => { if (writtenNow) qc.invalidateQueries({ queryKey: ["usage"] }); }, [writtenNow, qc]);
  // The tick shows the moment it is tapped: the list on screen is changed first, the server is told in the
  // background, and only a failed save puts the tick back.
  const revised = useMutation({
    mutationFn: (done: boolean) => api.setRevised(c.id, done),
    onMutate: async (done) => {
      await qc.cancelQueries({ queryKey: ["last-day"] });
      const before = qc.getQueriesData<LastDayPlan>({ queryKey: ["last-day"] });
      qc.setQueriesData<LastDayPlan>({ queryKey: ["last-day"] }, (p) => {
        const mine = p?.chapters.find((x) => x.id === c.id);
        if (!p || !mine || mine.revised_today === done) return p;
        return { ...p, revised: p.revised + (done ? 1 : -1), chapters: p.chapters.map((x) => (x.id === c.id ? { ...x, revised_today: done } : x)) };
      });
      return { before };
    },
    onError: (_e, _done, ctx) => {
      ctx?.before.forEach(([key, data]) => qc.setQueryData(key, data));
      toast.error("Couldn't save that. Check your connection.");
    },
    onSettled: () => { for (const key of ["last-day", "prep-plan", "prep-syllabus"]) qc.invalidateQueries({ queryKey: [key] }); },
  });
  const examTarget = useAuth((s) => s.user?.exam_target);
  const test = useMutation({
    mutationFn: () => api.createChapterTest(c.subject, [c.name], 15),
    onSuccess: (t) => navigate(`/app/mock/${t.id}`),
  });
  const ranked = c.topics.some((t) => t.asked);
  const part = c.topics.length < c.topic_count;  // the day (and its test) covers part of the chapter
  const heading = c.topics_chosen ? `The ${c.topics.length === 1 ? "topic" : `${c.topics.length} topics`} that ${c.topics.length === 1 ? "is" : "are"} coming`
    : c.quick && ranked ? `Its ${c.topics.length === 1 ? "most-asked topic" : `${c.topics.length} most-asked topics`}`
    : ranked ? "Topics · most asked first" : "Topics";
  return (
    <Card className={cn("overflow-hidden transition", c.revised_today && "opacity-70")}>
      <div className="flex items-start gap-3 p-4 sm:p-5">
        <button type="button" onClick={() => revised.mutate(!c.revised_today)}
          aria-label={c.revised_today ? `Mark ${c.name} as not revised` : `Mark ${c.name} as revised`}
          className={cn("mt-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-full sm:h-7 sm:w-7 pointer-coarse:h-10 pointer-coarse:w-10 border-2 text-xs font-semibold tabular-nums transition",
            c.revised_today ? "border-ok bg-ok text-white" : "border-line-strong text-muted hover:border-fg hover:text-fg")}>
          {c.revised_today ? <Check className="h-4 w-4" strokeWidth={3} /> : index}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1">
              <h3 className={cn("text-[15px] font-semibold tracking-tight", c.revised_today && "line-through")}>{shownName(c.name)}</h3>
              <span className="inline-flex items-center gap-1 text-xs text-muted"><Clock className="h-3 w-3" />{formatMinutes(c.minutes)}</span>
            </div>
            <button type="button" onClick={onRemove} title="Take off today's list" aria-label={`Take ${c.name} off today's list`}
              className="-mr-1.5 -mt-1 grid h-10 w-10 shrink-0 sm:h-7 sm:w-7 pointer-coarse:h-10 pointer-coarse:w-10 place-items-center rounded-sm text-muted/70 transition hover:bg-elev-2 hover:text-fg"><X className="h-3.5 w-3.5" /></button>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge dot={subjectColor(c.subject)}>{c.subject}</Badge>
            {c.added && <Badge tone="accent">added by you</Badge>}
            {c.reasons.map((r, i) => (
              <Badge key={r} tone={i === 0 ? WEIGHT_TONE[c.weightage] : /weak spot/.test(r) || (/in your tests/.test(r) && (c.accuracy ?? 100) < 60) ? "warn" : "neutral"}>{r}</Badge>
            ))}
          </div>

          <div className="mt-3">
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{heading} · tap one for its notes</div>
            <div className="flex flex-wrap gap-1.5">
              {c.topics.map((t) => (
                <span key={t.id} className={cn("inline-flex max-w-full items-center overflow-hidden rounded-sm border text-xs",
                  t.asked ? "border-line-strong bg-panel" : "border-line bg-bg-soft")}>
                  <button type="button" onClick={() => setReading({ topic: t })} title={t.asked ? `Most asked · notes: ${t.name}` : `Detailed notes: ${t.name}`}
                    className={cn("flex min-w-0 items-center gap-1.5 py-3 pl-2.5 pr-2 text-left sm:py-1.5 pointer-coarse:py-3 transition hover:bg-elev-2 hover:text-fg",
                      t.asked ? "font-medium text-fg" : "text-fg-soft")}>
                    {t.asked && <span className="h-1.5 w-1.5 shrink-0 bg-fg" aria-label="Most asked:" />}
                    <span className="min-w-0 break-words">{t.name}</span>
                  </button>
                  <button type="button" onClick={() => navigate(`/app/practice?topic=${encodeURIComponent(t.id)}`)} title={`Practise: ${t.name}`} aria-label={`Practise ${t.name}`}
                    className="grid h-full w-10 shrink-0 place-items-center border-l sm:w-7 pointer-coarse:w-10 border-line text-muted transition hover:bg-accent-soft hover:text-fg"><Target className="h-3 w-3" /></button>
                </span>
              ))}
              {part && !c.topics_chosen && (
                <span className="self-center px-1 text-xs text-muted">+{c.topic_count - c.topics.length} more, not for today</span>
              )}
            </div>
            {c.quick && (
              <p className="mt-2.5 border-l-2 border-line-strong pl-3 text-xs leading-relaxed text-muted">
                New to you: read the capsule and {ranked ? "these topics" : "the must-knows"}, nothing more.
              </p>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => setReading({})} icon={<BookOpen className="h-3.5 w-3.5" />}>{tr("Revision capsule")}</Button>
            {hasTests(examTarget) && <Button size="sm" variant="ghost" loading={test.isPending} onClick={() => test.mutate()} icon={<ClipboardCheck className="h-3.5 w-3.5" />}>15-question test</Button>}
          </div>
        </div>
      </div>
      {reading?.topic
        ? <NotesReader open onClose={() => setReading(null)} query={topicNotes} title={reading.topic.name} />
        : <NotesReader open={!!reading} onClose={() => setReading(null)} query={capsule} label="Revision capsule" title={shownName(c.name)} />}
    </Card>
  );
}

function OwnRow({ to, icon, label, value }: { to: string; icon: ReactNode; label: string; value: string }) {
  return (
    <Link to={to} className="group flex items-center gap-3 rounded-sm border border-line bg-bg-soft px-3 py-2.5 transition hover:border-line-strong">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-sm bg-elev-2 text-fg">{icon}</span>
      <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{label}</span><span className="block text-xs text-muted">{value}</span></span>
      <ArrowRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-fg" />
    </Link>
  );
}

function Checklist({ items }: { items: LastDayPlan["checklist"] }) {
  const key = `focs-lastday-${today()}`;  // ticks are for today only
  const [done, setDone] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem(key) ?? "[]"); } catch { return []; } });
  const toggle = (id: string) => {
    const next = done.includes(id) ? done.filter((d) => d !== id) : [...done, id];
    setDone(next);
    try { localStorage.setItem(key, JSON.stringify(next)); } catch { /* private mode */ }
  };
  return (
    <div className="space-y-1.5">
      {items.map((it) => {
        const on = done.includes(it.id);
        return (
          <button key={it.id} type="button" onClick={() => toggle(it.id)} role="checkbox" aria-checked={on}
            className="flex w-full items-start gap-3 rounded-sm px-2 py-2 text-left transition hover:bg-elev-2/60">
            <span className={cn("mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-sm border transition", on ? "border-ok bg-ok text-white" : "border-line-strong")}>
              {on && <Check className="h-3 w-3" strokeWidth={3} />}
            </span>
            <span className={cn("text-[13px] leading-relaxed", on ? "text-muted line-through" : "text-fg-soft")}>{it.text}</span>
          </button>
        );
      })}
    </div>
  );
}

/** The syllabus tomorrow covers, chapter by chapter: tap chapters in or out, or a whole subject at once. */
function SyllabusPicker({ tree, picked, onChange }: { tree: SyllabusTree; picked: string[]; onChange: (ids: string[]) => void }) {
  const on = new Set(picked);
  const order = tree.subjects.flatMap((s) => s.units.flatMap((u) => u.chapters.map((c) => c.id)));
  const set = (ids: string[], value: boolean) => {
    const next = new Set(on);
    ids.forEach((id) => (value ? next.add(id) : next.delete(id)));
    onChange(order.filter((id) => next.has(id)));  // in the syllabus's own order
  };
  return (
    <div className="max-h-[22rem] space-y-5 overflow-y-auto rounded-sm border border-line bg-bg-soft p-3 sm:p-4">
      {tree.subjects.map((s) => {
        const ids = s.units.flatMap((u) => u.chapters.map((c) => c.id));
        const n = ids.filter((id) => on.has(id)).length;
        return (
          <div key={s.name}>
            <div className="mb-2 flex items-center gap-2">
              <span className="h-2 w-2 shrink-0" style={{ background: subjectColor(s.name) }} />
              <span className="min-w-0 truncate font-display text-[12px] font-semibold uppercase tracking-[0.14em]">{s.name}</span>
              <span className="shrink-0 text-xs tabular-nums text-muted">{n}/{ids.length}</span>
              <span className="flex-1" />
              <button type="button" onClick={() => set(ids, n < ids.length)}
                className="shrink-0 font-display text-[11px] font-medium uppercase tracking-[0.12em] text-muted transition hover:text-fg">
                {n < ids.length ? "All of it" : "None"}
              </button>
            </div>
            {s.units.map((u) => (
              <div key={u.name} className="mb-2.5 last:mb-0">
                {s.units.length > 1 && <div className="mb-1.5 text-[11px] text-muted">{u.name}</div>}
                <div className="flex flex-wrap gap-1.5">
                  {u.chapters.map((c) => {
                    const sel = on.has(c.id);
                    return (
                      <button key={c.id} type="button" aria-pressed={sel} onClick={() => set([c.id], !sel)} title={`${c.weightage[0].toUpperCase()}${c.weightage.slice(1)} weightage`}
                        className={cn("inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-1 text-xs transition pointer-coarse:py-2.5",
                          sel ? "border-fg bg-fg text-bg" : "border-line text-fg-soft hover:border-line-strong hover:text-fg")}>
                        <WeightMark weightage={c.weightage} />{shownName(c.name)}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

/** For a chapter in tomorrow's test: which of its topics are coming (all of them unless narrowed down). */
function TopicPicker({ chapter, chosen, onChange, onRemove }: {
  chapter: SyllabusChapter; chosen: string[] | undefined; onChange: (ids: string[] | undefined) => void; onRemove: () => void;
}) {
  const [open, setOpen] = useState(!!chosen);
  const all = chapter.topics.map((t) => t.id);
  const on = new Set(chosen ?? all);
  const toggle = (id: string) => {
    const next = all.filter((t) => (t === id ? !on.has(t) : on.has(t)));
    onChange(next.length === 0 || next.length === all.length ? undefined : next);  // none ticked means the whole chapter again
  };
  return (
    <div className="rounded-sm border border-line bg-panel">
      <div className="flex items-center gap-2 px-3 py-2">
        <span className="h-1.5 w-1.5 shrink-0" style={{ background: subjectColor(chapter.subject) }} />
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <span className="min-w-0 truncate text-[13px] font-medium">{shownName(chapter.name)}</span>
          <span className="shrink-0 text-xs text-muted">{chosen ? `${chosen.length} of ${all.length} topics` : `all ${all.length} topics`}</span>
          <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 text-muted transition", open && "rotate-180")} />
        </button>
        <button type="button" onClick={onRemove} aria-label={`Remove ${chapter.name} from the test`} className="grid h-6 w-6 shrink-0 place-items-center rounded-sm text-muted hover:bg-elev-2 hover:text-fg"><X className="h-3.5 w-3.5" /></button>
      </div>
      {open && (
        <div className="border-t border-line px-3 py-2.5">
          <div className="mb-2 flex items-center gap-3 text-xs text-muted">
            Tick only the topics that are coming
            {chosen && <button type="button" onClick={() => onChange(undefined)} className="font-medium text-fg underline-offset-2 hover:underline">All topics</button>}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {chapter.topics.map((t) => {
              const ticked = on.has(t.id) && !!chosen;
              return (
                <button key={t.id} type="button" aria-pressed={ticked} onClick={() => (chosen ? toggle(t.id) : onChange([t.id]))}
                  className={cn("inline-flex items-center gap-1 rounded-sm border px-2.5 py-1 text-xs transition pointer-coarse:py-2.5",
                    ticked ? "border-fg bg-fg font-medium text-bg" : "border-line text-fg-soft hover:border-line-strong")}>
                  {ticked && <Check className="h-3 w-3" />}{t.name}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/** The end of the day: a test on exactly what was revised, unlocked once the list is ticked off. */
function FinalTest({ plan, body, count, onCount }: { plan: LastDayPlan; body: LastDayBody; count: number; onCount: (n: number) => void }) {
  const tr = useT();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const total = plan.chapters.length;
  const done = plan.revised;
  const unlocked = total > 0 && done >= total;
  const part = plan.chapters.filter((c) => c.topics.length < c.topic_count).length;
  const subjects = [...new Set(plan.chapters.map((c) => c.subject))];
  const size = plan.test_sizes.includes(count) ? count : plan.test_sizes[1] ?? plan.test_sizes[0];
  const start = useMutation({
    mutationFn: () => api.lastDayTest({ ...body, count: size }),
    onSuccess: (t) => {
      for (const key of ["last-day", "mocks"]) qc.invalidateQueries({ queryKey: [key] });
      navigate(`/app/mock/${t.id}`);
    },
  });
  const last = plan.final_test;
  const open = last && last.status !== "failed" ? last : null;  // a paper of today's still to take, or its result
  const pct = open?.max_score ? (100 * Math.max(0, open.score ?? 0)) / open.max_score : 0;

  return (
    <Card className={cn("relative overflow-hidden", unlocked && !open && "border-fg")}>
      <div className="p-5 sm:p-6">
        <Step n="04">{tr("Final test")}</Step>
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 max-w-xl">
            <h2 className="text-[22px] leading-tight sm:text-[26px]">A test on exactly what you revised</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              Questions on the {total} chapter{total === 1 ? "" : "s"} of your list{subjects.length > 1 ? ` across ${listed(subjects)}` : ""}
              {part ? `, and in the ${part} you revise in part, only on their listed topics` : ""}. Timed and marked like the real
              paper; what you get wrong goes to your weak spots.
            </p>
          </div>
          {open?.status === "submitted" && (
            <div className="flex shrink-0 items-center gap-3">
              <ProgressRing value={pct} size={64} stroke={5}>
                <span className="text-[11px] font-semibold tabular-nums">{open.score}/{open.max_score}</span>
              </ProgressRing>
              <div className="text-xs text-muted">Today's result<div className="text-sm font-semibold text-fg">{open.accuracy ?? 0}% right</div></div>
            </div>
          )}
        </div>

        {open && open.status !== "submitted" ? (
          <div className="mt-5 flex flex-col gap-3 rounded-sm border border-line bg-bg-soft p-4 sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1 text-sm">
              {open.status === "preparing" && <>Your test is being written{open.progress ? ` · ${open.progress}%` : ""}. Look over what it covers while you wait.</>}
              {open.status === "ready" && <>Your test is ready: {open.count} questions on today's list.</>}
              {open.status === "in_progress" && <>Your test is running. The clock doesn't stop when you leave.</>}
            </div>
            <Button variant="primary" onClick={() => navigate(open.status === "in_progress" ? `/exam/${open.id}` : `/app/mock/${open.id}`)}
              icon={<Play className="h-4 w-4" />}>{open.status === "in_progress" ? "Resume" : "Open the test"}</Button>
          </div>
        ) : (
          <div className="mt-5 space-y-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <span className="text-[13px] font-medium text-fg-soft">Questions</span>
              <Segmented size="sm" value={String(size)} onChange={(v) => onCount(Number(v))}
                options={plan.test_sizes.map((n) => ({ value: String(n), label: String(n) }))} />
              <span className="text-xs text-muted">about {formatMinutes(plan.test_minutes[String(size)] ?? size * 2)}</span>
            </div>
            {unlocked ? (
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="primary" size="lg" loading={start.isPending} onClick={() => start.mutate()} icon={<Flag className="h-4 w-4" />}>
                  {open ? "Take another final test" : "Start the final test"}
                </Button>
                {open && <Button variant="ghost" onClick={() => navigate(`/app/mock/${open.id}`)}>{tr("See today's result")}</Button>}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-3 text-sm">
                  <Lock className="h-4 w-4 shrink-0 text-muted" />
                  <span className="min-w-0 flex-1">Unlocks when your list is done · <b className="tabular-nums">{done} of {total}</b> revised</span>
                </div>
                <ProgressBar value={total ? (100 * done) / total : 0} />
                <div className="flex flex-wrap items-center gap-3">
                  <button type="button" onClick={() => start.mutate()} disabled={start.isPending} className="link-line text-muted hover:text-fg disabled:opacity-50">
                    {start.isPending ? "Making it…" : "Take it now anyway"}
                  </button>
                  {open && <button type="button" onClick={() => navigate(`/app/mock/${open.id}`)} className="link-line text-muted hover:text-fg">{tr("Today's result")}</button>}
                </div>
              </div>
            )}
            {last?.status === "failed" && <p className="text-xs text-warn">The last one couldn't be written: the AI was busy. Try again in a few minutes.</p>}
          </div>
        )}
      </div>
    </Card>
  );
}

/** One day left before the exam, a subject test or a class test: what to revise, in what order, for how long, and a
    test on it at the end. The student picks the syllabus (all of it, a subject, or chapters and their topics) and
    everything important in it is laid out, most marks first, the most-asked topics of every chapter first. */
export default function LastDay() {
  const tr = useT();
  useFocus("revision", true, true);
  const examTarget = useAuth((s) => s.user?.exam_target);
  const [setup, setSetup] = useState<Setup>(loadSetup);
  const [allLeave, setAllLeave] = useState(false);
  const [allNext, setAllNext] = useState(false);
  const change = (patch: Partial<Setup>) => setSetup((s) => {
    const next = { ...s, ...patch };
    try { localStorage.setItem(SETUP_KEY, JSON.stringify(next)); } catch { /* private mode */ }
    return next;
  });
  const { scope, subject, hours, picked, cover } = setup;
  const { data: tree } = useQuery({ queryKey: ["prep-syllabus"], queryFn: () => api.prepSyllabus(), staleTime: 60_000 });
  const body: LastDayBody = {
    hours, subject: scope === "subject" ? subject : undefined, chapters: scope === "chapters" ? picked : [],
    topics: scope === "chapters" ? picked.flatMap((c) => setup.topics[c] ?? []) : [], include: setup.include, exclude: setup.exclude, cover,
  };
  const { data: plan, error, isFetching, refetch } = useQuery({
    queryKey: ["last-day", body], queryFn: () => api.lastDay(body), placeholderData: keepPreviousData, retry: false,
    staleTime: 10 * 60_000,  // the same syllabus gives the same plan: going back and forth shouldn't load it again
  });
  const college = plan?.kind === "college" || plan?.kind === "school";  // an exam is one subject's paper
  useEffect(() => {  // a subject that is gone (another semester's, another exam's) falls back to the first one
    if (plan && !plan.subjects.includes(subject)) change({ subject: plan.subjects[0] ?? "" });
  }, [plan, subject]);
  // a college exam is one subject's paper: unless the student has chosen otherwise, that is what tomorrow is
  useEffect(() => { if (college && !localStorage.getItem(SETUP_KEY)) change({ scope: "subject" }); }, [college]);
  const byId = useMemo(() => new Map((tree?.subjects ?? []).flatMap((s) => s.units.flatMap((u) => u.chapters)).map((c) => [c.id, c])), [tree]);

  if (error instanceof ApiError && error.status === 404) {
    return <EmptyState icon={<Hourglass className="h-6 w-6" />} title="Last-day revision follows your exam's syllabus" body={error.message}
      action={<Link to="/app/settings"><Button variant="primary">Open settings</Button></Link>} />;
  }
  if (!plan && error) {
    return <EmptyState icon={<Hourglass className="h-6 w-6" />} title="Couldn't load your revision plan"
      body={error instanceof Error ? error.message : "Check your connection and try again."}
      action={<Button variant="primary" onClick={() => refetch()}>{tr("Try again")}</Button>} />;
  }
  if (!plan) return (
    <div className="mx-auto max-w-6xl space-y-4" aria-busy="true">
      <div className="flex items-center gap-2 text-sm text-muted" role="status">
        <Hourglass className="h-4 w-4 animate-pulse" />
        Laying out your revision. The first time for a syllabus, Focs ranks its most-asked topics, which can take a few seconds.
      </div>
      <Skeleton className="h-28" /><Skeleton className="h-96" />
    </div>
  );

  const days = plan.days_left;
  const pct = plan.chapters.length ? (100 * plan.revised) / plan.chapters.length : 0;
  const choosing = scope === "chapters" && !picked.length;
  const remove = (id: string) => change({ exclude: [...setup.exclude.filter((c) => c !== id), id], include: setup.include.filter((c) => c !== id) });
  const add = (id: string) => change({ include: [...setup.include.filter((c) => c !== id), id], exclude: setup.exclude.filter((c) => c !== id) });
  const edited = setup.include.length + setup.exclude.length > 0;
  const ranked = plan.chapters.some((c) => c.topics.some((t) => t.asked));
  const inSyllabus = scope === "subject" ? tree?.subjects.find((s) => s.name === subject) : null;
  const chapterCount = (s: SyllabusTree["subjects"][number]) => s.units.reduce((n, u) => n + u.chapters.length, 0);
  const syllabusLine = !tree ? null
    : scope === "all" ? `${tree.subjects.reduce((n, s) => n + chapterCount(s), 0)} chapters across ${tree.subjects.map((s) => s.name).join(", ")}`
    : scope === "subject" ? (inSyllabus ? `${chapterCount(inSyllabus)} chapters of ${inSyllabus.name}` : null)
    : `${picked.length} chapter${picked.length === 1 ? "" : "s"} picked`;
  const next = allNext ? plan.if_time : plan.if_time.slice(0, 12);
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader eyebrow={<span className="flex items-center gap-1.5"><Hourglass className="h-3.5 w-3.5" />{tr("Last-day revision")}</span>}
        title={tr(days === 1 ? "Your exam is tomorrow" : days === 0 ? "Exam day" : "One day left, used well")}
        subtitle="Pick the syllabus. Everything important in it that's likely to come is laid out for you, most marks first, and the day ends with a test on exactly that."
        actions={days !== null && days > 1 ? <Badge tone="accent">{days} days to your exam</Badge> : undefined} />

      <Card className="mb-5 p-4 sm:p-5">
        <Step n="01">{tr("Syllabus")}</Step>
        <div className="min-w-0">
          <Label>What does tomorrow's paper cover?</Label>
          <ScrollX quiet>
            <Segmented value={scope} onChange={(v) => change({ scope: v })} options={[
              { value: "all", label: college ? fit("All my subjects", "All subjects") : "Full syllabus" },
              { value: "subject", label: college ? fit("One subject's paper", "One paper") : fit("One subject", "A subject") },
              { value: "chapters", label: fit("Chosen chapters", "Chapters") },
            ]} />
          </ScrollX>
          {scope === "subject" && (
            <div className="mt-3"><ScrollX quiet><Segmented value={subject} onChange={(v) => change({ subject: v })} options={plan.subjects.map((s) => ({ value: s, label: s }))} /></ScrollX></div>
          )}
          {syllabusLine && <p className="mt-2.5 text-xs text-muted">{syllabusLine}</p>}
        </div>
        {scope === "chapters" && (
          <div className="mt-4 space-y-4">
            {tree ? <SyllabusPicker tree={tree} picked={picked} onChange={(ids) => {
              const keep = new Set(ids);
              change({ picked: ids, topics: Object.fromEntries(Object.entries(setup.topics).filter(([id]) => keep.has(id))) });
            }} /> : <Skeleton className="h-40" />}
            {picked.length > 0 && tree && (
              <div>
                <Label hint={<button type="button" onClick={() => change({ picked: [], topics: {} })} className="text-xs text-muted hover:text-fg">Clear</button>}>
                  In the test · {picked.length} chapter{picked.length === 1 ? "" : "s"} · narrow one down to the topics that are coming
                </Label>
                <div className="grid items-start gap-2 md:grid-cols-2">
                  {picked.map((id) => byId.get(id)).filter((c): c is SyllabusChapter => !!c).map((c) => (
                    <TopicPicker key={c.id} chapter={c} chosen={setup.topics[c.id]}
                      onRemove={() => { const { [c.id]: _gone, ...rest } = setup.topics; change({ picked: picked.filter((p) => p !== c.id), topics: rest }); }}
                      onChange={(ids) => {
                        const { [c.id]: _old, ...rest } = setup.topics;
                        change({ topics: ids ? { ...rest, [c.id]: ids } : rest });
                      }} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        <div className="hairline my-5" />
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[auto_1fr]">
          <div className="min-w-0">
            <Step n="02">{tr("Time today")}</Step>
            <ScrollX quiet>
              <Segmented value={String(hours)} onChange={(v) => change({ hours: Number(v) })} options={plan.hour_choices.map((h) => ({ value: String(h), label: `${h} h` }))} />
            </ScrollX>
          </div>
          <div className="min-w-0">
            <Step n="03">{tr("What goes on the list")}</Step>
            <ScrollX quiet>
              <Segmented value={cover} onChange={(v) => change({ cover: v })} options={[
                { value: "important", label: tr("Everything important") }, { value: "studied", label: fit("Only what I've studied", "Studied only") },
              ]} />
            </ScrollX>
            <p className="mt-2 text-xs leading-relaxed text-muted">
              {cover === "important"
                ? "Every chapter that carries marks, studied or not. The ones new to you get their most-asked topics only."
                : "Nothing new: chapters you haven't studied wait under “Leave these today”."}
            </p>
          </div>
        </div>
      </Card>

      <div className={cn("grid grid-cols-1 gap-5 transition-opacity lg:grid-cols-[1.5fr_1fr]", isFetching && "opacity-70")}>
        <div className="min-w-0 space-y-3">
          {choosing ? (
            <EmptyState icon={<ListChecks className="h-6 w-6" />} title={tr("Pick the chapters in tomorrow's test")} body="Tap them above, or a whole subject at once, then narrow each one down to the topics that are coming if you know them." />
          ) : plan.chapters.length === 0 ? (
            cover === "studied" ? (
              <EmptyState icon={<BookOpen className="h-6 w-6" />} title={tr("Nothing to revise here yet")}
                body="“Only what I've studied” works from topics ticked in the Prep Hub, lectures you captured and weak spots from your tests. Switch to everything important to get the chapters that carry the most marks."
                action={<Button variant="primary" onClick={() => change({ cover: "important" })}>{tr("Show everything important")}</Button>} />
            ) : (
              <EmptyState icon={<BookOpen className="h-6 w-6" />} title={tr("Everything is off today's list")}
                body="You took every chapter off. Put them back to see the day again."
                action={<Button variant="primary" onClick={() => change({ include: [], exclude: [] })} icon={<Undo2 className="h-4 w-4" />}>{tr("Put them back")}</Button>} />
            )
          ) : (
            <>
              <Card className="flex items-center gap-4 p-4 sm:p-5">
                <ProgressRing value={pct} size={56} stroke={5}><span className="text-[11px] font-semibold tabular-nums">{plan.revised}/{plan.chapters.length}</span></ProgressRing>
                <div className="min-w-0 flex-1">
                  <h2 className="font-semibold">Your revision order</h2>
                  <p className="text-xs leading-relaxed text-muted">
                    {plan.chapters.length} chapter{plan.chapters.length === 1 ? "" : "s"}, about {formatMinutes(plan.minutes.chapters)} of reading
                    {plan.scope === "all" ? `, worth about ${plan.paper_share}% of the paper` : ""}. Most marks first; tick each one as you finish it.
                  </p>
                  {ranked && (
                    <p className="mt-1.5 flex items-center gap-1.5 text-xs text-muted">
                      <span className="h-1.5 w-1.5 shrink-0 bg-fg" />Most asked: the topics exams ask most often, as judged by AI
                    </p>
                  )}
                </div>
                {edited && <Button size="sm" variant="ghost" onClick={() => change({ include: [], exclude: [] })} icon={<Undo2 className="h-3.5 w-3.5" />}>{tr("Reset")}</Button>}
              </Card>
              {plan.chapters.map((c, i) => <ChapterCard key={c.id} c={c} index={i + 1} onRemove={() => remove(c.id)} />)}
              {hasTests(examTarget) && <FinalTest plan={plan} body={body} count={setup.count} onCount={(n) => change({ count: n })} />}
            </>
          )}
          {!choosing && plan.if_time.length > 0 && (
            <Card className="p-4 sm:p-5">
              <div className="text-sm font-semibold">Add to today</div>
              <p className="mt-0.5 text-xs text-muted">Next in line by marks. Tap one to put it on today's list.</p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {next.map((c) => (
                  <button key={c.id} type="button" onClick={() => add(c.id)} title={c.quick ? `Not studied yet · add ${c.name}` : `Add ${c.name}`}
                    className="inline-flex items-center gap-1.5 rounded-sm border border-line bg-bg-soft py-1 pl-2.5 pr-2 text-xs pointer-coarse:py-2.5 text-fg-soft transition hover:border-line-strong hover:text-fg">
                    <span className="h-1.5 w-1.5" style={{ background: subjectColor(c.subject) }} />{shownName(c.name)}
                    <WeightMark weightage={c.weightage} className="text-muted" /><Plus className="h-3 w-3" />
                  </button>
                ))}
                {plan.if_time.length > 12 && (
                  <button type="button" onClick={() => setAllNext(!allNext)} aria-expanded={allNext}
                    className="px-2.5 py-1 text-xs font-medium text-muted transition hover:text-fg pointer-coarse:py-3">
                    {allNext ? "Show fewer" : `+${plan.if_time.length - 12} more`}
                  </button>
                )}
              </div>
            </Card>
          )}
          {plan.removed.length > 0 && (
            <Card className="p-4 sm:p-5">
              <div className="text-sm font-semibold">Taken off today's list</div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {plan.removed.map((c) => (
                  <button key={c.id} type="button" onClick={() => change({ exclude: setup.exclude.filter((x) => x !== c.id) })}
                    className="inline-flex items-center gap-1.5 rounded-sm border border-line bg-bg-soft py-1 pl-2.5 pr-2 text-xs pointer-coarse:py-2.5 text-muted transition hover:border-line-strong hover:text-fg">
                    {shownName(c.name)}<Undo2 className="h-3 w-3" />
                  </button>
                ))}
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <Card>
            <CardHeader title={tr("Start with your own mistakes")} icon={<Target className="h-4 w-4" />} subtitle={`About ${formatMinutes(plan.minutes.own)}: what you got wrong is what you're most likely to get wrong again`} />
            <div className="space-y-2 px-5 pb-5 pt-4">
              {plan.own.weak > 0 && <OwnRow to="/app/weak" icon={<ShieldAlert className="h-4 w-4" />} label="Weak spots from your tests" value={`${plan.own.weak} topic${plan.own.weak === 1 ? "" : "s"} still to clear`} />}
              <OwnRow to="/app/practice" icon={<RotateCcw className="h-4 w-4" />} label="Redo queue" value={plan.own.redo ? `${plan.own.redo} question${plan.own.redo === 1 ? "" : "s"} you got wrong` : "Empty. Nothing waiting"} />
              <OwnRow to="/app/formulas" icon={<Sigma className="h-4 w-4" />} label="Formula book" value={plan.own.formulas ? `${plan.own.formulas} formulas from your lectures` : "Fills up as you capture lectures"} />
              <OwnRow to="/app/flashcards" icon={<Layers className="h-4 w-4" />} label="Flashcards" value={plan.own.cards_due ? `${plan.own.cards_due} due for review` : "None due today"} />
            </div>
          </Card>

          {plan.leave_count > 0 && (
            <Card>
              <CardHeader title={tr("Leave these today")} icon={<ShieldAlert className="h-4 w-4" />}
                subtitle={`${plan.leave_count} chapter${plan.leave_count === 1 ? "" : "s"} you haven't studied. Starting one the day before costs more marks than it earns. Studied one outside Focs? Tap it to add it to today`} />
              <div className="flex flex-wrap gap-1.5 px-5 pb-5 pt-4">
                {(allLeave ? plan.leave : plan.leave.slice(0, 10)).map((c) => (
                  <button key={c.id} type="button" onClick={() => add(c.id)} title={`Add ${c.name} to today's list`}
                    className="inline-flex items-center gap-1.5 rounded-sm border border-line bg-bg-soft py-1 pl-2.5 pr-2 text-xs pointer-coarse:py-2.5 text-fg-soft transition hover:border-line-strong hover:text-fg">
                    <span className="h-1.5 w-1.5" style={{ background: subjectColor(c.subject) }} />{shownName(c.name)}<Plus className="h-3 w-3" />
                  </button>
                ))}
                {plan.leave.length > 10 && (
                  <button type="button" onClick={() => setAllLeave(!allLeave)} aria-expanded={allLeave}
                    className="px-2.5 py-1 text-xs font-medium text-muted transition hover:text-fg pointer-coarse:py-3">
                    {allLeave ? "Show fewer" : `+${plan.leave.length - 10} more`}
                  </button>
                )}
              </div>
            </Card>
          )}

          <Card>
            <CardHeader title={tr("Before you sleep")} icon={<Moon className="h-4 w-4" />} subtitle={tr("The night before decides more than the last chapter does")} />
            <div className="px-3 pb-4 pt-3"><Checklist items={plan.checklist} /></div>
          </Card>
        </div>
      </div>
    </div>
  );
}
