import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Clock, Copy, Crosshair, Flame, Presentation, Route, Trash2, UserMinus, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { StatTile, WeekBars } from "@/components/ProgressBits";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, EmptyState, ProgressBar, Segmented, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { ClassStudent } from "@/lib/types";
import { formatMinutes, subjectColor } from "@/lib/utils";
import { copyText } from "@/pages/Classes";

type Sort = "name" | "study" | "syllabus";
const SORTS: Record<Sort, (a: ClassStudent, b: ClassStudent) => number> = {
  name: (a, b) => a.name.localeCompare(b.name),
  study: (a, b) => a.week_minutes - b.week_minutes,
  syllabus: (a, b) => (a.syllabus.percent ?? 0) - (b.syllabus.percent ?? 0),
};

function StudentRow({ s, onRemove }: { s: ClassStudent; onRemove: () => void }) {
  return (
    <div className="grid items-center gap-x-5 gap-y-3 border-t border-line px-5 py-4 first:border-t-0 md:grid-cols-[minmax(0,1.3fr)_150px_minmax(0,1fr)_minmax(0,1fr)_auto]">
      <div className="min-w-0">
        <div className="flex items-center gap-2"><span className="truncate font-semibold">{s.name}</span>
          {s.streak > 1 && <span className="inline-flex shrink-0 items-center gap-0.5 text-xs text-warn"><Flame className="h-3 w-3" />{s.streak}</span>}</div>
        <div className="mt-0.5 truncate text-xs text-muted">{s.exam}{s.last_active ? ` · last here ${new Date(s.last_active).toLocaleDateString(undefined, { day: "numeric", month: "short" })}` : " · not opened yet"}</div>
      </div>
      <div>
        <WeekBars days={s.days} goal={s.goal_minutes} />
        <div className="mt-1 text-xs text-muted"><span className="font-semibold text-fg">{formatMinutes(s.week_minutes)}</span> this week</div>
      </div>
      <div>
        <div className="mb-1 flex justify-between text-xs text-muted"><span>Syllabus</span><span className="font-semibold text-fg">{s.syllabus.percent ?? 0}%</span></div>
        <ProgressBar value={s.syllabus.percent ?? 0} />
        <div className="mt-1 text-xs text-muted">{s.last_test ? <>Last test <span className="font-semibold text-fg">{s.last_test.percent}%</span></> : "No test yet"}
          {s.accuracy_week !== null && <> · {s.accuracy_week}% right on {s.questions_week} Qs</>}</div>
      </div>
      <div className="min-w-0 text-xs">
        {s.weak_count ? <><div className="font-medium text-warn">{s.weak_count} weak chapter{s.weak_count === 1 ? "" : "s"}</div>
          <div className="mt-0.5 line-clamp-2 text-muted">{s.weak.map((w) => w.chapter).join(", ")}</div></> : <span className="text-muted">No open weak spots</span>}
      </div>
      <Button size="icon-sm" variant="ghost" aria-label={`Remove ${s.name} from the class`} title="Remove from the class" onClick={onRemove}><UserMinus className="h-3.5 w-3.5" /></Button>
    </div>
  );
}

/** A teacher's view of one class: who studied this week, how far each student is, and where the class is stuck. */
export default function ClassView() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [sort, setSort] = useState<Sort>("name");
  const { data, isLoading, error } = useQuery({ queryKey: ["class", id], queryFn: () => api.classDashboard(id), retry: false, refetchInterval: 60_000 });
  const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work. Try again.");
  const removeStudent = useMutation({ mutationFn: (uid: number) => api.removeClassStudent(id, uid), onError: failed,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["class", id] }); qc.invalidateQueries({ queryKey: ["classes"] }); } });
  const removeClass = useMutation({ mutationFn: () => api.removeClass(id), onError: failed,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["classes"] }); toast.success("Class removed"); navigate("/app/classes"); } });
  const students = useMemo(() => [...(data?.students ?? [])].sort(SORTS[sort]), [data, sort]);

  if (error) return <EmptyState icon={<Presentation className="h-6 w-6" />} title="That class isn't here" body={error instanceof ApiError ? error.message : undefined}
    action={<Link to="/app/classes"><Button variant="primary">All classes</Button></Link>} />;
  if (isLoading || !data) return <div className="mx-auto max-w-6xl space-y-4"><Skeleton className="h-24" /><Skeleton className="h-28" /><Skeleton className="h-72" /></div>;
  const t = data.totals;

  return (
    <div className="mx-auto max-w-6xl">
      <Link to="/app/classes" className="mb-3 inline-flex items-center gap-1 text-xs text-muted hover:text-fg"><ArrowLeft className="h-3.5 w-3.5" />All classes</Link>
      <PageHeader eyebrow={<span className="flex items-center gap-1.5"><Presentation className="h-3.5 w-3.5" />Class</span>} title={data.name}
        subtitle="Each student chose to share this by joining. It shows their week and progress, never their notes or doubts."
        actions={<div className="flex gap-2">
          <Button variant="secondary" onClick={() => copyText(data.code, "Code copied")} icon={<Copy className="h-4 w-4" />}>Code <span className="font-mono tracking-widest">{data.code}</span></Button>
          <Button variant="ghost" aria-label="Remove this class" title="Remove this class" loading={removeClass.isPending}
            onClick={() => { if (window.confirm(`Remove "${data.name}"? Students stop sharing their progress with you.`)) removeClass.mutate(); }}><Trash2 className="h-4 w-4" /></Button>
        </div>} />

      {!t.students ? (
        <EmptyState icon={<Users className="h-6 w-6" />} title="No students yet"
          body={<>Give your students the code <span className="font-mono font-semibold tracking-widest text-fg">{data.code}</span>. They enter it under Classes, Join a class.</>}
          action={<Button variant="primary" onClick={() => copyText(data.code, "Code copied")}>Copy the code</Button>} />
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="Students" value={t.students} icon={<Users className="h-3.5 w-3.5" />} />
            <StatTile label="Studied this week" value={<>{t.active_week}<span className="text-base text-muted"> of {t.students}</span></>} icon={<Flame className="h-3.5 w-3.5" />} />
            <StatTile label="Average study time" value={formatMinutes(t.avg_week_minutes)} hint="per student, last 7 days" icon={<Clock className="h-3.5 w-3.5" />} />
            <StatTile label="Average syllabus done" value={t.avg_syllabus === null ? "–" : `${t.avg_syllabus}%`} icon={<Route className="h-3.5 w-3.5" />} />
          </div>
          {data.weakest.length > 0 && (
            <Card className="mb-4">
              <CardHeader title="Where the class is stuck" icon={<Crosshair className="h-4 w-4" />} subtitle="Chapters students lost marks on in their tests and haven't cleared yet. Worth a revision class." />
              <div className="flex flex-wrap gap-2 p-5">
                {data.weakest.map((w) => (
                  <span key={w.id} className="inline-flex items-center gap-2 rounded-xl border border-line bg-bg-soft px-3 py-2 text-sm">
                    <span className="h-2 w-2 rounded-full" style={{ background: subjectColor(w.subject) }} /><span className="font-medium">{w.chapter}</span>
                    <Badge tone="warn">{w.students} student{w.students === 1 ? "" : "s"}</Badge>
                  </span>
                ))}
              </div>
            </Card>
          )}
          <Card>
            <CardHeader title="Students" icon={<Users className="h-4 w-4" />}
              action={<Segmented size="sm" value={sort} onChange={setSort} options={[{ value: "name", label: "A to Z" }, { value: "study", label: "Least study first" }, { value: "syllabus", label: "Furthest behind" }]} />} />
            <div className="mt-3">
              {students.map((s) => <StudentRow key={s.user_id} s={s} onRemove={() => { if (window.confirm(`Remove ${s.name} from this class?`)) removeStudent.mutate(s.user_id); }} />)}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
