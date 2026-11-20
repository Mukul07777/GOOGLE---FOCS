import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BookOpen, CalendarDays, Camera, Clock, Flame, Hourglass, Layers, Radio, RotateCcw, Snowflake, Target, TrendingDown } from "lucide-react";
import { motion } from "motion/react";
import { Link } from "react-router-dom";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { YearHeatmap } from "@/components/YearHeatmap";
import { MentorNudge } from "@/components/MentorNudge";
import { RealGap } from "@/components/RealGap";
import { NextSteps } from "@/components/NextSteps";
import { GoalPrompt, TodayPlan, usePlan } from "@/components/TodayPlan";
import { Button } from "@/components/ui/button";
import { CountUp } from "@/components/ui/live";
import { Badge, Card, CardHeader, EmptyState, ProgressBar, ProgressRing, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { StudyPlan } from "@/lib/types";
import { cn, examLabel, formatMinutes, greeting, hasSyllabus, subjectColor, timeAgo } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { useT } from "@/lib/i18n";

function Stat({ icon, label, value, sub, children, accent }: {
  icon: React.ReactNode; label: string; value: React.ReactNode; sub?: React.ReactNode; children?: React.ReactNode; accent?: string;
}) {
  return (
    <Card className="flex items-center justify-between gap-4 p-5">
      <div className="min-w-0">
        <div className="flex items-center gap-2 whitespace-nowrap text-[13px] text-muted">
          <span className={cn("grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-elev-2", accent)}>{icon}</span>{label}
        </div>
        <div className="figure mt-3 text-[40px]">{value}</div>
        {sub && <div className="mt-1.5 text-xs text-muted">{sub}</div>}
      </div>
      {children}
    </Card>
  );
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-line-strong bg-elev px-3 py-2 text-xs shadow-xl">
      <div className="mb-1 font-medium">{label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 text-fg-soft">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />{p.name}: <b className="text-fg">{p.value ?? "—"}{p.name === "Accuracy" ? "%" : " min"}</b>
        </div>
      ))}
    </div>
  );
}

const FREEZE_HELP = "Streak freeze: one missed day a week is covered automatically, so a single off day never resets your streak.";

function StreakNote({ streak, best, atRisk, freezesLeft }: { streak: number; best: number; atRisk: boolean; freezesLeft: number }) {
  const days = (n: number) => `${n} ${n === 1 ? "day" : "days"}`;
  if (!streak) return <>{best ? `Best ${days(best)} · start a new one today` : "Study today to start one"}</>;
  const freeze = (
    <span className="inline-flex items-center gap-0.5 whitespace-nowrap" title={FREEZE_HELP}>
      <Snowflake className="h-3 w-3 text-accent-2" />{freezesLeft ? "freeze ready" : "freeze used"}
    </span>
  );
  if (atRisk) return <span className="text-warn">Study today to keep it{freezesLeft ? <> · {freeze}</> : null}</span>;
  return <>Best {days(best)} · {freeze}</>;
}

/** The last seven days at a glance: a filled dot for every day studied, today ringed. */
function WeekDots({ days, atRisk, title }: { days: { date: string; active: boolean }[]; atRisk: boolean; title?: string }) {
  return (
    <div className="flex shrink-0 items-end gap-1" title={title} aria-label={`${days.filter((d) => d.active).length} of the last 7 days studied`}>
      {days.map((d, i) => {
        const today = i === days.length - 1;
        return (
          <div key={d.date} className="flex flex-col items-center gap-1">
            <span className={cn("h-2 w-2 rounded-full", d.active ? "bg-warn" : "bg-elev-2",
              today && !d.active && (atRisk ? "ring-2 ring-warn/60" : "ring-2 ring-line-strong"))} />
            <span className={cn("text-[9.5px] leading-none", today ? "font-semibold text-fg-soft" : "text-muted")}>
              {new Date(`${d.date}T00:00:00`).toLocaleDateString(undefined, { weekday: "narrow" })}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function PlanGlance({ plan }: { plan: StudyPlan }) {
  const tr = useT();
  const first = plan.mentor[0];
  const behind = plan.expected_now !== null && plan.completion + 0.5 < plan.expected_now;
  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium uppercase tracking-[0.12em] text-accent">{plan.target.label}</div>
          <h3 className="mt-1 truncate text-lg font-semibold">{plan.goal.dream ? `Road to ${plan.goal.dream}` : "Your plan"}</h3>
          <p className="text-xs text-muted">{plan.status === "past" ? "Your exam date has passed" : plan.days_left === 1 ? "Your exam is tomorrow" : `${plan.days_left} days to your exam`}</p>
        </div>
        <ProgressRing value={plan.completion} size={64}><span className="text-xs font-semibold">{Math.round(plan.completion)}%</span></ProgressRing>
      </div>
      {plan.expected_now !== null && (
        <p className={cn("mt-3 text-[13px]", behind ? "text-warn" : "text-ok")}>
          Syllabus {Math.round(plan.completion)}% · plan expected {Math.round(plan.expected_now)}% by today
        </p>
      )}
      {first && (
        <div className="mt-3 rounded-xl border border-line bg-bg-soft p-3">
          <div className="text-[13px] font-semibold">{first.title}</div>
          <p className="mt-0.5 line-clamp-3 text-xs leading-relaxed text-muted">{first.text}</p>
        </div>
      )}
      <Link to="/app/plan" className="mt-auto pt-4"><Button variant="secondary" className="w-full" icon={<ArrowRight className="h-4 w-4" />}>{tr("Open my plan")}</Button></Link>
    </Card>
  );
}

/** JEE, NEET and B.Tech students: today's list from their plan comes first. */
function PlanStrip() {
  const { data: plan } = usePlan();
  if (plan === null) return <GoalPrompt />;
  const near = plan && plan.status !== "past" && plan.days_left <= 7;  // the last week: revision, not new chapters
  return (
    <div className="space-y-4">
      {near && (
        <Link to="/app/revise" className="group flex items-center gap-4 rounded-2xl border border-warn/30 bg-warn/[0.07] p-4 transition hover:border-warn/50">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-warn/15 text-warn"><Hourglass className="h-5 w-5" /></span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold">{plan.days_left <= 1 ? "Your exam is tomorrow" : `${plan.days_left} days to your exam`}</span>
            <span className="block text-[13px] text-muted">Open last-day revision: everything important in your syllabus, most marks first, and a test on it at the end.</span>
          </span>
          <ArrowRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-fg" />
        </Link>
      )}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">
        <TodayPlan />
        {plan ? <PlanGlance plan={plan} /> : <Skeleton className="h-64" />}
      </div>
    </div>
  );
}

const ACTIVITY_LABEL: Record<string, string> = {
  lecture: "Live lectures", mock: "Mock tests", practice: "Practice", flashcards: "Flashcards", room: "Study rooms", revision: "Revising notes",
};

function TodayBreakdown({ byActivity }: { byActivity: Record<string, number> }) {
  const rows = Object.entries(byActivity).sort((a, b) => b[1] - a[1]);
  const total = rows.reduce((n, [, m]) => n + m, 0);
  if (!total) return <p className="py-6 text-center text-sm text-muted">Nothing yet today — lectures, mocks, practice, flashcards and rooms all count.</p>;
  return (
    <div className="space-y-2.5">
      {rows.map(([a, m]) => (
        <div key={a}>
          <div className="mb-1 flex justify-between text-[13px]"><span>{ACTIVITY_LABEL[a] ?? a}</span><span className="tabular-nums text-muted">{formatMinutes(m)}</span></div>
          <ProgressBar value={(100 * m) / total} />
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const tr = useT();
  const user = useAuth((s) => s.user);
  const { data, isLoading } = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const { data: active } = useQuery({ queryKey: ["active-session"], queryFn: api.activeSession });
  const first = user?.full_name?.split(" ")[0] ?? "";
  const goalPct = data ? Math.round((100 * data.today_minutes) / Math.max(1, data.daily_goal_min)) : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
        <div>
          <div className="flex items-center gap-2 text-sm text-muted">
            {new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}
            <Badge tone="accent">{examLabel(user?.exam_target)}</Badge>
          </div>
          <h1 className="mt-1.5 text-[36px]">{tr(greeting())}, {first}.</h1>
        </div>
      </div>

      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="panel noise relative overflow-hidden p-6 sm:p-8">
        <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="max-w-xl">
            {active ? (
              <>
                <div className="flex items-center gap-2 text-sm font-medium text-bad"><span className="live-dot" /> Lecture in progress</div>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight">{active.title || "Untitled lecture"}</h2>
                <p className="mt-2 text-sm text-fg-soft">{active.note_count} boards captured so far. Jump back in to keep your notes in sync.</p>
              </>
            ) : (
              <>
                {/* the AI layer reports in: the board reader is warmed up and waiting */}
                <div className="hud mb-3">Ready to read the board</div>
                <h2 className="text-2xl font-semibold tracking-tight">{tr("Watching a lecture today?")}</h2>
                <p className="mt-2 text-sm leading-relaxed text-fg-soft">
                  {tr("Share the lecture tab and Focs will read the board, write your notes and check your understanding as you go.")}
                </p>
              </>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to="/app/studio"><Button variant="primary" size="lg" icon={<Radio className="h-4 w-4" />}>{tr(active ? "Resume lecture" : "Start live lecture")}</Button></Link>
            {!active && <Link to="/app/studio?mode=photo"><Button variant="secondary" size="lg" icon={<Camera className="h-4 w-4" />}>{tr("Board photo")}</Button></Link>}
          </div>
        </div>
      </motion.div>

      <MentorNudge />
      <RealGap />
      {hasSyllabus(user?.exam_target) && <PlanStrip />}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading || !data ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[118px]" />)
        ) : (
          <>
            <Stat icon={<Flame className="h-4 w-4 text-warn" />} label={tr("Study streak")} value={<><CountUp value={data.streak} /><span className="ml-1 text-base font-normal text-muted">{data.streak === 1 ? "day" : "days"}</span></>}
              sub={<StreakNote streak={data.streak} best={data.best_streak} atRisk={data.streak_at_risk} freezesLeft={data.freezes_left} />}>
              <WeekDots days={data.heatmap.slice(-7)} atRisk={data.streak_at_risk}
                title={data.frozen_days ? `A freeze saved your streak on ${data.frozen_days} missed day${data.frozen_days === 1 ? "" : "s"}` : undefined} />
            </Stat>
            <Stat icon={<Clock className="h-4 w-4 text-accent" />} label={tr("Today's focus")} value={formatMinutes(data.today_minutes)} sub={`Goal ${formatMinutes(data.daily_goal_min)} · ${formatMinutes(data.week_minutes)} this week`}>
              <ProgressRing value={goalPct} size={62}><span className="text-xs font-semibold">{Math.min(goalPct, 999)}%</span></ProgressRing>
            </Stat>
            <Stat icon={<Target className="h-4 w-4 text-ok" />} label={tr("Quiz accuracy")} value={data.accuracy === null ? "—" : <><CountUp value={data.accuracy} />%</>}
              sub={`${data.totals.questions} questions answered`}>
              {data.redo_count > 0 && <Link to="/app/practice"><Badge tone="warn"><RotateCcw className="h-3 w-3" />{data.redo_count} to redo</Badge></Link>}
            </Stat>
            <Stat icon={<Layers className="h-4 w-4 text-accent-2" />} label={tr("Cards due")} value={<CountUp value={data.due_cards} />} sub={`${data.totals.flashcards} cards in your deck`}>
              {data.due_cards > 0 && <Link to="/app/flashcards"><Button size="sm" variant="secondary">{tr("Review")} <ArrowRight className="h-3.5 w-3.5" /></Button></Link>}
            </Stat>
          </>
        )}
      </div>

      <Card>
        <CardHeader title={tr("Study activity")} icon={<CalendarDays className="h-4 w-4" />}
          subtitle={data && !data.study_days_year ? "Every day you study fills in a square — lectures, mocks, practice and rooms all count"
            : data ? `${data.study_days_year} study ${data.study_days_year === 1 ? "day" : "days"} in the last year · best streak ${data.best_streak} ${data.best_streak === 1 ? "day" : "days"}` : "Your year of study"} />
        <div className="px-5 pb-5 pt-4">{data ? <YearHeatmap days={data.heatmap} /> : <Skeleton className="h-32" />}</div>
      </Card>

      <NextSteps />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardHeader title={tr("This week")} subtitle={tr("Minutes studied and quiz accuracy")} />
          <div className="h-[260px] px-2 pb-4 pt-2">
            {data ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={data.week} margin={{ top: 10, right: 12, left: -12, bottom: 0 }}>
                  <defs>
                    <linearGradient id="bar" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.95} />
                      <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.35} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke="var(--line)" />
                  <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 12 }} />
                  <YAxis yAxisId="m" allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 12 }} />
                  <YAxis yAxisId="a" orientation="right" domain={[0, 100]} hide />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--elev-2)", radius: 8 }} />
                  <Bar yAxisId="m" dataKey="minutes" name="Minutes" fill="url(#bar)" radius={[8, 8, 3, 3]} maxBarSize={38} />
                  <Line yAxisId="a" dataKey="accuracy" name="Accuracy" stroke="var(--accent-2)" strokeWidth={2.5} dot={{ r: 3, fill: "var(--accent-2)" }} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            ) : <Skeleton className="h-full" />}
          </div>
        </Card>
        <Card>
          <CardHeader title={tr("Today")} subtitle={tr("Where your focus time went")} />
          <div className="px-5 pb-5 pt-4">
            {data ? <TodayBreakdown byActivity={data.today_by_activity} /> : <Skeleton className="h-28" />}
            <div className="mt-4 grid grid-cols-3 gap-3 text-center">
              {[["Lectures", data?.totals.sessions], ["Boards", data?.totals.notes], ["Doubts", data?.totals.doubts]].map(([l, v]) => (
                <div key={String(l)} className="rounded-xl border border-line bg-bg-soft py-3">
                  <div className="text-lg font-semibold">{v ?? "–"}</div>
                  <div className="text-[11.5px] text-muted">{l}</div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardHeader title={tr("Recent lectures")} action={<Link to="/app/library" className="inline-flex min-h-10 items-center text-[13px] text-accent hover:underline">{tr("View all")}</Link>} />
          <div className="p-3">
            {data && data.recent_sessions.length === 0 && (
              <EmptyState icon={<BookOpen className="h-6 w-6" />} title={tr("No lectures yet")} body={tr("Start your first live lecture — your notes will appear here.")} />
            )}
            {data?.recent_sessions.map((s) => (
              <Link key={s.id} to={`/app/library/${s.id}`} className="group flex items-center gap-4 rounded-xl px-3 py-3 transition hover:bg-elev-2">
                <div className="h-10 w-1 rounded-full" style={{ background: subjectColor(s.subject) }} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{s.title || "Untitled lecture"}</div>
                  <div className="mt-0.5 text-xs text-muted">{s.subject || "General"} · {s.note_count} boards · {formatMinutes(s.duration_min)}</div>
                </div>
                {s.is_active && <Badge tone="bad"><span className="live-dot scale-75" />Live</Badge>}
                <div className="text-xs text-muted">{timeAgo(s.started_at)}</div>
                <ArrowRight className="h-4 w-4 text-muted opacity-0 transition group-hover:opacity-100" />
              </Link>
            ))}
            {!data && <div className="space-y-2 p-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>}
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title={tr("Needs attention")} icon={<TrendingDown className="h-4 w-4" />} subtitle={tr("Topics where you slip most")} />
            <div className="space-y-3 p-5">
              {data?.weak_topics.length === 0 && <p className="text-sm text-muted">Answer a few checkpoints and practice sets — your weak spots will show up here.</p>}
              {data?.weak_topics.map((t) => (
                <div key={t.topic}>
                  <div className="mb-1.5 flex justify-between text-sm"><span className="truncate pr-3">{t.topic}</span><span className="text-muted">{t.accuracy}%</span></div>
                  <ProgressBar value={t.accuracy} tone={t.accuracy < 40 ? "bad" : t.accuracy < 70 ? "warn" : "ok"} />
                </div>
              ))}
            </div>
          </Card>
          <Card>
            <CardHeader title={tr("Subjects")} />
            <div className="flex flex-wrap gap-2 p-5">
              {data?.subjects.length === 0 && <p className="text-sm text-muted">Nothing yet.</p>}
              {data?.subjects.map((s) => (
                <div key={s.subject} className="flex items-center gap-2 rounded-xl border border-line bg-bg-soft px-3 py-2 text-sm">
                  <span className="h-2 w-2 rounded-full" style={{ background: subjectColor(s.subject) }} />
                  {s.subject}<span className="text-xs text-muted">{s.notes} boards{s.accuracy !== null ? ` · ${s.accuracy}%` : ""}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
