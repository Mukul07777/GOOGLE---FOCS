import { useQuery } from "@tanstack/react-query";
import { Clock, Crosshair, Flame, Route, ShieldCheck, Timer } from "lucide-react";
import { useParams } from "react-router-dom";
import { Logo } from "@/components/common";
import { StatTile, WeekBars } from "@/components/ProgressBits";
import { Badge, Card, CardHeader, ProgressBar, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { formatMinutes, subjectColor } from "@/lib/utils";

/** What a parent sees from the link their child gave them: this week at a glance. No sign-in, nothing to change. */
export default function ParentView() {
  const { token = "" } = useParams();
  const { data: d, isLoading, error } = useQuery({ queryKey: ["parent-view", token], queryFn: () => api.parentView(token), retry: false, refetchInterval: 5 * 60_000 });

  return (
    <div className="mx-auto min-h-dvh max-w-2xl px-4 pb-[calc(2rem+env(safe-area-inset-bottom))] pt-[calc(2rem+env(safe-area-inset-top))]">
      <Logo className="mb-8" />
      {isLoading ? <div className="space-y-4"><Skeleton className="h-20" /><Skeleton className="h-64" /></div> : error || !d ? (
        <Card className="p-8 text-center">
          <div className="text-lg font-semibold">This link doesn't work any more</div>
          <p className="mt-2 text-sm text-muted">{error instanceof ApiError && error.status !== 404 ? error.message : "It was turned off or replaced. Ask your child for the new one."}</p>
        </Card>
      ) : (
        <div className="space-y-4">
          <div>
            <Badge tone="accent">{d.exam}</Badge>
            <h1 className="mt-2 text-[36px]">{d.name}'s week on Focs</h1>
            <p className="mt-1 text-sm text-muted">{d.today_minutes >= d.goal_minutes ? `Today's goal of ${formatMinutes(d.goal_minutes)} is done.`
              : d.today_minutes ? `${formatMinutes(d.today_minutes)} studied today, of a ${formatMinutes(d.goal_minutes)} goal.` : `Nothing studied yet today. The daily goal is ${formatMinutes(d.goal_minutes)}.`}</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <StatTile label="This week" value={formatMinutes(d.week_minutes)} hint="studied in the last 7 days" icon={<Clock className="h-3.5 w-3.5" />} />
            <StatTile label="Streak" value={<>{d.streak}<span className="text-base text-muted"> day{d.streak === 1 ? "" : "s"}</span></>} hint="in a row" icon={<Flame className="h-3.5 w-3.5" />} />
          </div>
          <Card>
            <CardHeader title="Day by day" icon={<Clock className="h-4 w-4" />} subtitle="A brighter bar is a day the daily goal was met." />
            <div className="p-5"><WeekBars days={d.days} goal={d.goal_minutes} tall /></div>
          </Card>
          <Card>
            <CardHeader title="Syllabus" icon={<Route className="h-4 w-4" />} subtitle={d.syllabus.total ? `${d.syllabus.done} of ${d.syllabus.total} topics finished` : "No syllabus chosen yet"} />
            <div className="p-5"><ProgressBar value={d.syllabus.percent ?? 0} /><div className="mt-2 text-sm font-semibold">{d.syllabus.percent ?? 0}% done</div></div>
          </Card>
          <Card>
            <CardHeader title="Tests" icon={<Timer className="h-4 w-4" />} subtitle={`${d.tests_week} taken this week`} />
            <div className="space-y-1.5 p-5 text-sm">
              {d.last_test ? <p>Last test: <span className="font-semibold">{d.last_test.title}</span>, {d.last_test.score} out of {d.last_test.max} <span className="text-muted">({d.last_test.percent}%)</span></p>
                : <p className="text-muted">No test taken yet.</p>}
              {d.accuracy_week !== null && <p className="text-fg-soft">{d.questions_week} practice questions this week, {d.accuracy_week}% right.</p>}
            </div>
          </Card>
          <Card>
            <CardHeader title="Chapters that need work" icon={<Crosshair className="h-4 w-4" />} subtitle="Where marks were lost in tests and not yet won back." />
            <div className="flex flex-wrap gap-2 p-5">
              {d.weak.length ? d.weak.map((w) => <Badge key={w.id} dot={subjectColor(w.subject)}>{w.chapter}</Badge>) : <span className="text-sm text-muted">None open right now.</span>}
              {d.weak_count > d.weak.length && <span className="text-xs text-muted">and {d.weak_count - d.weak.length} more</span>}
            </div>
          </Card>
          <p className="flex gap-2 px-1 text-xs leading-relaxed text-muted"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
            {d.name} shared this page with you. It is a summary only: it can't change anything, and it doesn't show notes, doubts or answers. {d.name} can turn the link off at any time.</p>
        </div>
      )}
    </div>
  );
}
