import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight, ArrowUpToLine, CalendarDays, ChevronDown, EyeOff, Flag, Hourglass, Info, ListOrdered, Pencil, PinOff, Sparkles, Target, Timer,
  TriangleAlert, Trophy, Undo2,
} from "lucide-react";
import { createContext, useContext, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { EditPlanDialog } from "@/components/EditPlan";
import { GoalPrompt, TodayPlan, usePlan } from "@/components/TodayPlan";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, ProgressBar, ProgressRing, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { MentorNote, PlanMonth, PlanWeek, StudyPlan } from "@/lib/types";
import { cn, examLabel, subjectColor, shownName } from "@/lib/utils";
import { useT } from "@/lib/i18n";

const TRACK = { jee_main: "JEE Main", jee_advanced: "JEE Main + Advanced", neet: "NEET UG", college: "B.Tech", gate: "GATE", cbse: "School", placement: "Placements", ssc_cgl: "SSC CGL" } as const;
/** Plans that test one subject at a time (a semester, the boards, placements): there is no full mock. */
const useCollegePlan = () => { const plan = usePlan().data; return plan?.subject_tests ?? ["college", "school"].includes(plan?.kind ?? ""); };
const STATUS: Record<StudyPlan["status"], { label: string; tone: "ok" | "accent" | "warn" | "bad" | "neutral" }> = {
  done: { label: "Syllabus covered", tone: "ok" }, comfortable: { label: "Comfortable", tone: "ok" },
  on_track: { label: "On track", tone: "ok" }, tight: { label: "Tight", tone: "warn" },
  behind: { label: "Priority mode", tone: "warn" }, past: { label: "Exam passed", tone: "neutral" },
};
const monthName = (key: string) => new Date(`${key}-01T00:00:00`).toLocaleDateString(undefined, { month: "long", year: "numeric" });
const shortDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
const longDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });

function Mentor({ note }: { note: MentorNote }) {
  const icon = { good: <Sparkles className="h-4 w-4 text-ok" />, warn: <TriangleAlert className="h-4 w-4 text-warn" />, info: <Info className="h-4 w-4 text-accent-2" /> }[note.tone];
  return (
    <div className={cn("flex gap-3 rounded-xl border p-4", note.tone === "warn" ? "border-warn/25 bg-warn/[0.07]" : note.tone === "good" ? "border-ok/25 bg-ok/[0.06]" : "border-line bg-bg-soft")}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div><div className="text-sm font-semibold">{note.title}</div><p className="mt-0.5 text-[13px] leading-relaxed text-fg-soft">{note.text}</p></div>
    </div>
  );
}

function Chip({ subject, children }: { subject: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-bg-soft px-2.5 py-1 text-xs">
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: subjectColor(subject) }} />{children}
    </span>
  );
}

type ChapterAction = "next" | "unpin" | "skip" | "restore";
/** Set while the student is rearranging the plan: the chapters they pinned, and how to act on one. */
const Reorder = createContext<{ pinned: string[]; busy: string | null; act: (chapterId: string, action: ChapterAction) => void } | null>(null);

function ChapterActions({ id, name }: { id: string; name: string }) {
  const reorder = useContext(Reorder);
  if (!reorder) return null;
  const isNext = reorder.pinned.includes(id);
  const button = "grid h-7 w-7 place-items-center rounded-md text-muted transition hover:bg-elev-2 hover:text-fg disabled:opacity-40";
  return (
    <span className="ml-auto flex shrink-0 items-center gap-0.5 pl-2">
      {isNext ? (
        <button type="button" className={button} disabled={reorder.busy === id} onClick={() => reorder.act(id, "unpin")}
          title="Back to the mentor's order" aria-label={`Put ${name} back in the mentor's order`}><PinOff className="h-3.5 w-3.5" /></button>
      ) : (
        <button type="button" className={button} disabled={reorder.busy === id} onClick={() => reorder.act(id, "next")}
          title="Study this next" aria-label={`Study ${name} next`}><ArrowUpToLine className="h-3.5 w-3.5" /></button>
      )}
      <button type="button" className={button} disabled={reorder.busy === id} onClick={() => reorder.act(id, "skip")}
        title="Leave out of my plan" aria-label={`Leave ${name} out of my plan`}><EyeOff className="h-3.5 w-3.5" /></button>
    </span>
  );
}

function WeekRow({ w }: { w: PlanWeek }) {
  const college = useCollegePlan();
  const reorder = useContext(Reorder);
  return (
    <div className="rounded-xl border border-line bg-bg-soft p-3.5">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span className="font-semibold text-fg">{shortDate(w.start)} – {shortDate(w.end)}</span>
        <span>· {Math.round(w.hours)} h</span>
        {w.questions > 0 && <span>· ~{w.questions} questions</span>}
        {w.mocks > 0 && <Badge tone="accent">{w.mocks} {college ? "subject test" : "full mock"}{w.mocks > 1 ? "s" : ""}</Badge>}
        {w.phase === "revision" && <Badge tone="cyan">Revision</Badge>}
      </div>
      {w.learn.length > 0 && (
        <div className="space-y-1.5">
          {w.learn.map((i) => (
            <div key={i.chapter_id} className="flex items-start gap-2 text-[13px]">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: subjectColor(i.subject) }} />
              <span className="min-w-0">
                <Link to={`/app/prep?chapter=${encodeURIComponent(i.chapter_id)}`} className="font-medium hover:text-accent">{i.chapter}</Link>
                {i.finishes && <span className="ml-1.5 text-[11px] font-medium text-ok">finish</span>}
                {reorder?.pinned.includes(i.chapter_id) && <span className="ml-1.5 text-[11px] font-medium text-accent">your pick</span>}
                <span className="text-muted"> · {i.hours} h{i.topics.length ? ` · ${i.topics.slice(0, 3).join(", ")}${i.topics.length > 3 ? "…" : ""}` : ""}</span>
              </span>
              <ChapterActions id={i.chapter_id} name={i.chapter} />
            </div>
          ))}
        </div>
      )}
      {(w.revise.length > 0 || w.chapter_tests.length > 0) && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {w.revise.length > 0 && <span>Revise: {w.revise.slice(0, 4).map((c) => c.name).join(", ")}{w.revise.length > 4 ? ` +${w.revise.length - 4}` : ""}</span>}
          {w.chapter_tests.length > 0 && <span>Chapter tests: {w.chapter_tests.map((c) => c.name).join(", ")}</span>}
        </div>
      )}
    </div>
  );
}

function MonthCard({ m, weeks, current, open, onToggle }: {
  m: PlanMonth; weeks: PlanWeek[]; current: boolean; open: boolean; onToggle: () => void;
}) {
  const college = useCollegePlan();
  return (
    <div className="relative pl-8">
      <span className={cn("absolute left-[7px] top-6 h-3 w-3 rounded-full border-2", current ? "border-accent bg-accent" : m.phase === "revision" ? "border-accent-2 bg-bg" : "border-line-strong bg-bg")} />
      <Card className={cn("overflow-hidden", current && "ring-1 ring-accent/40")}>
        <button type="button" onClick={onToggle} className="flex w-full items-center gap-3 p-4 text-left">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{monthName(m.month)}</span>
              {current && <Badge tone="accent">This month</Badge>}
              {m.phase !== "learning" && <Badge tone="cyan">{m.phase === "revision" ? (college ? "Revision & tests" : "Revision & mocks") : "Learning → revision"}</Badge>}
            </div>
            <div className="mt-0.5 text-xs text-muted">
              {m.hours} h · {m.finish.length} chapter{m.finish.length === 1 ? "" : "s"} to finish{m.mocks ? ` · ${m.mocks} ${college ? "test" : "mock"}${m.mocks > 1 ? "s" : ""}` : ""} · syllabus {Math.round(m.completion)}% by month end
            </div>
          </div>
          <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted transition", open && "rotate-180")} />
        </button>
        <div className="space-y-3 px-4 pb-4">
          {m.milestones.map((x) => (
            <div key={x} className="flex items-center gap-2 text-[13px] font-medium text-ok"><Flag className="h-3.5 w-3.5" />{x}</div>
          ))}
          {m.finish.length > 0 && (
            <div className="flex flex-wrap gap-1.5">{m.finish.map((c) => <Chip key={c.id} subject={c.subject}>{shownName(c.name)}</Chip>)}</div>
          )}
          {open && (
            <div className="space-y-2 pt-1">
              {m.start.length > 0 && <p className="text-xs text-muted">Also started this month: {m.start.map((c) => c.name).join(", ")}</p>}
              {weeks.map((w) => <WeekRow key={w.start} w={w} />)}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

export default function MyPlan() {
  const tr = useT();
  const { data: plan, isLoading } = usePlan();
  const qc = useQueryClient();
  const [openMonth, setOpenMonth] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [reordering, setReordering] = useState(false);
  const chapter = useMutation({
    mutationFn: ({ id, action }: { id: string; action: ChapterAction }) => api.editPlanChapter(id, action),
    onSuccess: (next, { action }) => {
      qc.setQueryData(["prep-plan"], next);
      toast.success({ next: "It's first in line now", unpin: "Back in the mentor's order", skip: "Left out. Its time goes to the rest of your plan",
        restore: "Back in your plan" }[action]);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't change the plan. Try again."),
  });
  if (plan === null) return <div className="mx-auto max-w-xl pt-6"><GoalPrompt /></div>;
  if (isLoading || !plan) return <div className="space-y-4"><Skeleton className="h-36" /><Skeleton className="h-72" /></div>;

  const g = plan.goal;
  const college = plan.kind === "college";
  const thisMonth = new Date().toISOString().slice(0, 7);
  const status = STATUS[plan.status];
  const ahead = plan.expected_now === null ? null : plan.completion - plan.expected_now;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      {/* goal banner */}
      <Card className="relative overflow-hidden p-6 sm:p-7">
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-accent">
              <Target className="h-3.5 w-3.5" />{plan.kind && plan.kind !== "entrance" ? examLabel(g.exam) : TRACK[g.track]} · {plan.target.label}
            </div>
            <h1 className="mt-2 text-[30px] sm:text-[38px]">{g.dream ? `Road to ${g.dream}` : tr("Your plan")}</h1>
            <p className="mt-1.5 text-sm text-muted">
              {college ? "Exams from" : g.group === "placement" ? "Placements from" : "Exam on"} {longDate(plan.exam_date)} ·{plan.kind === "gate" ? "" : ` ${college ? `Semester ${g.class_level}` : g.class_level === "dropper" ? "Dropper" : `Class ${g.class_level}`} ·`}{" "}
              {plan.hours.custom_days ? `${plan.hours.weekly} h a week, set day by day` : `${plan.hours.weekday} h on ${college || g.group === "placement" ? "college" : plan.kind === "gate" ? "working" : "school"} days, ${plan.hours.weekend} h on weekends`}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link to="/app/prep"><Button size="sm" variant="secondary" icon={<ArrowRight className="h-3.5 w-3.5" />}>{tr("Prep Hub")}</Button></Link>
              <Button size="sm" variant="secondary" onClick={() => setEditing(true)} icon={<Pencil className="h-3.5 w-3.5" />}>{tr("Edit plan")}</Button>
              <Link to="/app/revise"><Button size="sm" variant="ghost" icon={<Hourglass className="h-3.5 w-3.5" />}>{tr("Last-day revision")}</Button></Link>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-5">
            <div className="text-center">
              <div className="text-4xl font-semibold tabular-nums">{Math.max(0, plan.days_left)}</div>
              <div className="text-xs text-muted">{plan.days_left === 1 ? "day to go" : "days to go"}</div>
            </div>
            <ProgressRing value={plan.completion} size={92} stroke={8}>
              <div className="text-center leading-tight"><div className="text-lg font-semibold">{Math.round(plan.completion)}%</div><div className="text-[10px] text-muted">syllabus</div></div>
            </ProgressRing>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader title="Your mentor says" icon={<Sparkles className="h-4 w-4" />}
              action={<Badge tone={status.tone}>{tr(status.label)}</Badge>} />
            <div className="space-y-2.5 px-5 pb-5 pt-4">{plan.mentor.map((n) => <Mentor key={n.title} note={n} />)}</div>
          </Card>

          <Card>
            <CardHeader title="Progress" subtitle={plan.expected_now === null ? "Syllabus covered by subject"
              : `You ${Math.round(plan.completion)}% · your plan expected ${Math.round(plan.expected_now)}% by today`}
              action={ahead !== null && Math.abs(ahead) >= 0.5 ? <Badge tone={ahead >= 0 ? "ok" : "warn"}>{ahead >= 0 ? "Ahead" : "Behind"}</Badge> : undefined} />
            <div className="space-y-3 px-5 pb-5 pt-4">
              {Object.entries(plan.by_subject).map(([s, v]) => (
                <div key={s}>
                  <div className="mb-1 flex justify-between text-[13px]"><span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: subjectColor(s) }} />{s}</span><span className="tabular-nums text-muted">{Math.round(v)}%</span></div>
                  <ProgressBar value={v} />
                </div>
              ))}
              <div className="grid grid-cols-3 gap-3 pt-2 text-center">
                <div className="rounded-xl bg-bg-soft p-3"><div className="text-sm font-semibold">{plan.syllabus_done_on ? shortDate(plan.syllabus_done_on) : "—"}</div><div className="text-[11px] text-muted">syllabus done</div></div>
                <div className="rounded-xl bg-bg-soft p-3"><div className="text-sm font-semibold">{shortDate(plan.revision_from)}</div><div className="text-[11px] text-muted">revision starts</div></div>
                <div className="rounded-xl bg-bg-soft p-3"><div className="text-sm font-semibold">{plan.months.reduce((n, m) => n + m.mocks, 0)}</div><div className="text-[11px] text-muted">{plan.subject_tests ? "subject tests planned" : "full mocks planned"}</div></div>
              </div>
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <TodayPlan compact />
          {plan.weeks[0] && (
            <Card>
              {/* on a Sunday "this week" is a single day: show the week ahead with it */}
              <CardHeader title={tr(plan.weeks[0].hours < plan.hours.weekly * 0.5 && plan.weeks[1] ? "This week and next" : "This week")}
                icon={<CalendarDays className="h-4 w-4" />} subtitle="What your plan covers, week by week" />
              <div className="space-y-2 px-5 pb-5 pt-4">
                <WeekRow w={plan.weeks[0]} />
                {plan.weeks[0].hours < plan.hours.weekly * 0.5 && plan.weeks[1] && <WeekRow w={plan.weeks[1]} />}
              </div>
            </Card>
          )}
        </div>
      </div>

      <section>
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="text-lg font-semibold">{tr("Month by month")}</h2>
            <p className="text-sm text-muted">Rebuilt from your progress every time, so it always fits the time you have left.</p>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <span className="hidden items-center gap-1.5 text-xs text-muted sm:flex"><Timer className="h-3.5 w-3.5" />{plan.hours.weekly} h a week</span>
            {plan.months.length > 0 && (
              <Button size="sm" variant={reordering ? "primary" : "secondary"} onClick={() => setReordering(!reordering)} icon={<ListOrdered className="h-3.5 w-3.5" />}>
                {reordering ? "Done" : "Change the order"}
              </Button>
            )}
          </div>
        </div>
        {reordering && (
          <p className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-accent/25 bg-accent-soft/40 px-3.5 py-2.5 text-[13px] text-fg-soft">
            Open a month and use the buttons beside a chapter:
            <span className="inline-flex items-center gap-1.5"><ArrowUpToLine className="h-3.5 w-3.5 text-accent" />study it next</span>
            <span className="inline-flex items-center gap-1.5"><EyeOff className="h-3.5 w-3.5 text-accent" />leave it out of the plan</span>
          </p>
        )}
        <div className="relative space-y-3 before:absolute before:bottom-4 before:left-[12px] before:top-4 before:w-px before:bg-line">
          <Reorder.Provider value={reordering ? { pinned: plan.pinned, busy: chapter.isPending ? chapter.variables?.id ?? null : null,
            act: (id, action) => chapter.mutate({ id, action }) } : null}>
            {plan.months.map((m) => (
              <MonthCard key={m.month} m={m} current={m.month === thisMonth}
                weeks={plan.weeks.filter((w) => w.start.slice(0, 7) === m.month)}
                open={openMonth === m.month || (openMonth === null && m.month === thisMonth)}
                onToggle={() => setOpenMonth(openMonth === m.month ? "" : m.month)} />
            ))}
          </Reorder.Provider>
          <div className="relative pl-8">
            <span className="absolute left-[5px] top-3 grid h-4 w-4 place-items-center rounded-full bg-ok"><Trophy className="h-2.5 w-2.5 text-white" /></span>
            <div className="pt-2 text-sm font-semibold">Exam day · {longDate(plan.exam_date)}</div>
          </div>
        </div>
        {plan.skipped.length > 0 && (
          <Card className="mt-4 p-5">
            <div className="text-sm font-semibold">Left out of your plan ({plan.skipped.length})</div>
            <p className="mt-0.5 text-xs text-muted">You chose to skip these: about {plan.skipped_weight}% of the {college ? "marks" : "paper"}. Bring one back and the plan makes room for it.</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {plan.skipped.map((c) => (
                <span key={c.id} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-bg-soft py-1 pl-2.5 pr-1 text-xs">
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: subjectColor(c.subject) }} />{shownName(c.name)}
                  <button type="button" disabled={chapter.isPending} onClick={() => chapter.mutate({ id: c.id, action: "restore" })}
                    className="inline-flex items-center gap-1 rounded-full bg-elev-2 px-2 py-0.5 font-medium text-accent hover:bg-accent-soft disabled:opacity-50">
                    <Undo2 className="h-3 w-3" />Bring back
                  </button>
                </span>
              ))}
            </div>
          </Card>
        )}
        {plan.priority_mode && plan.unfinished.length > 0 && (
          <Card className="mt-4 p-5">
            <div className="text-sm font-semibold">Waiting at the end ({plan.unfinished.length})</div>
            <p className="mt-0.5 text-xs text-muted">Lower marks per hour of study. If you get ahead, these come next.</p>
            <div className="mt-3 flex flex-wrap gap-1.5">{plan.unfinished.map((n) => <Badge key={n}>{n}</Badge>)}</div>
          </Card>
        )}
      </section>
      <EditPlanDialog plan={plan} open={editing} onClose={() => setEditing(false)} />
    </div>
  );
}
