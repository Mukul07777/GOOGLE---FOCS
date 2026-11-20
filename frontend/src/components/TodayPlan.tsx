import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BookOpen, Check, ClipboardCheck, Coffee, Crosshair, ListTodo, PenLine, Plus, RotateCcw, Sparkles, Timer, Trash2, Undo2, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, Input, ProgressRing, Select, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { PlanTask, StudyPlan, TodayPlan as Today } from "@/lib/types";
import { canTest, cn, formatMinutes, isCollege, subjectColor } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { useT } from "@/lib/i18n";

const KIND: Record<PlanTask["kind"], { icon: ReactNode; label: string }> = {
  learn: { icon: <BookOpen className="h-4 w-4" />, label: "Learn" },
  practice: { icon: <PenLine className="h-4 w-4" />, label: "Practise" },
  revise: { icon: <RotateCcw className="h-4 w-4" />, label: "Revise" },
  test: { icon: <ClipboardCheck className="h-4 w-4" />, label: "Test" },
  mock: { icon: <Timer className="h-4 w-4" />, label: "Mock" },
  custom: { icon: <ListTodo className="h-4 w-4" />, label: "Yours" },
  fix: { icon: <Crosshair className="h-4 w-4" />, label: "Fix" },
};
const MINUTES = [15, 30, 45, 60, 90, 120];

export function usePlan() {
  return useQuery({ queryKey: ["prep-plan"], queryFn: api.prepPlan, staleTime: 60_000 }); // null: no goal set yet
}

/** Set your goal: the way in to the plan, for JEE, NEET and B.Tech students who haven't yet. */
export function GoalPrompt({ className }: { className?: string }) {
  const t = useT();
  const college = useAuth((s) => isCollege(s.user?.exam_target));
  return (
    <Card className={cn("relative overflow-hidden p-6", className)}>
      <Sparkles className="h-5 w-5 text-accent" />
      <h3 className="mt-3 text-lg font-semibold">{t("Get your personal plan")}</h3>
      <p className="mt-1 text-sm text-muted">
        {college ? t("Tell us your college, your semester's subjects and your hours. You get a week-by-week plan up to your exams and a list for every day, like a mentor would make.")
          : t("Tell us your goal, your class and your hours. You get a month-by-month plan and a list for every day, like a mentor would make.")}
      </p>
      <Link to="/onboarding"><Button variant="primary" className="mt-4" icon={<ArrowRight className="h-4 w-4" />}>{t("Set my goal · 2 min")}</Button></Link>
    </Card>
  );
}

function TaskRow({ task, onToggle, onRemove, busy }: { task: PlanTask; onToggle: () => void; onRemove: () => void; busy: boolean }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const examTarget = useAuth((s) => s.user?.exam_target);
  const own = task.kind === "custom";
  const test = useMutation({
    mutationFn: () => api.createChapterTest(task.subject!, [task.chapter!], task.kind === "test" ? 20 : 15),
    onSuccess: (t) => { qc.invalidateQueries({ queryKey: ["mocks"] }); navigate(`/app/mock/${t.id}`); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start the test"),
  });
  const action = (() => {
    switch (task.kind) {
      case "custom": return null;
      case "fix": return { label: "Open", run: () => navigate("/app/weak") };
      case "learn": return { label: "Open", run: () => navigate(`/app/prep?topic=${encodeURIComponent(task.topics![0].id)}`) };
      case "revise": return { label: "Open", run: () => navigate(`/app/prep?chapter=${encodeURIComponent(task.chapter_id!)}`) };
      case "mock": return { label: "Start", run: () => navigate("/app/mock") };
      default:
        return canTest(task.subject, examTarget)
          ? { label: "Start", run: () => test.mutate() }
          : { label: "Practise", run: () => navigate("/app/practice") };
    }
  })();
  const sub = task.kind === "fix"
    ? ["Weak spot from your test", task.chapter !== task.title ? task.chapter : task.subject, formatMinutes(task.minutes), task.more ? `${task.more} more after it` : null].filter(Boolean).join(" · ")
    : [task.subject, task.kind === "learn" || task.kind === "practice" ? task.chapter : null, formatMinutes(task.minutes)].filter(Boolean).join(" · ");
  return (
    <div className={cn("group flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-line bg-bg-soft py-2.5 pl-3 pr-1.5 transition", task.done && "opacity-60")}>
      <button type="button" onClick={onToggle} disabled={busy} aria-label={task.done ? "Mark as not done" : "Mark as done"}
        className={cn("relative grid h-6 w-6 shrink-0 place-items-center rounded-full border-2 transition before:absolute before:-inset-2.5 before:content-['']",
          task.done ? "border-ok bg-ok text-white" : "border-line-strong hover:border-accent")}>
        {task.done && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
      </button>
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-elev-2" style={{ color: task.subject ? subjectColor(task.subject) : undefined }}>
        {KIND[task.kind].icon}
      </span>
      <div className="min-w-0 flex-1 basis-44">
        <div className={cn("text-sm font-medium sm:line-clamp-1", task.done && "line-through")}>
          <span className="text-muted">{KIND[task.kind].label}: </span>{task.title}
        </div>
        <div className="text-xs text-muted">{sub}</div>
      </div>
      <span className="ml-auto flex shrink-0 items-center gap-1">
      {!task.done && action && <Button size="sm" variant="ghost" onClick={action.run} loading={test.isPending}>{action.label}</Button>}
      {(own || !task.done) && (
        <button type="button" onClick={onRemove} disabled={busy} title={own ? "Remove this task" : "Not today (it stays in your plan)"}
          aria-label={own ? `Remove ${task.title}` : `Take ${task.title} off today's list`}
          className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-muted/70 transition hover:bg-elev-2 hover:text-fg pointer-coarse:h-10 pointer-coarse:w-10">
          {own ? <Trash2 className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
        </button>
      )}
      </span>
    </div>
  );
}

function AddTask({ onAdd, busy }: { onAdd: (title: string, minutes: number) => Promise<unknown>; busy: boolean }) {
  const [open, setOpen] = useState(false);
  const college = useAuth((s) => isCollege(s.user?.exam_target));
  const [title, setTitle] = useState("");
  const [minutes, setMinutes] = useState("30");
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
        className="flex w-full items-center gap-2 rounded-xl border border-dashed border-line-strong px-3 py-2.5 text-left text-[13px] font-medium text-muted transition hover:border-accent/50 hover:text-fg">
        <Plus className="h-4 w-4" />Add your own task
      </button>
    );
  }
  const submit = async () => {
    if (!title.trim()) return;
    await onAdd(title, Number(minutes));
    setTitle("");
    setOpen(false);
  };
  return (
    <form onSubmit={(e) => { e.preventDefault(); void submit(); }} className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-bg-soft p-2">
      <Input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} maxLength={160} placeholder={college ? "An assignment, a lab file, a quiz…" : "School homework, a coaching test…"}
        aria-label="Task" className="h-9 min-w-40 flex-1" onKeyDown={(e) => e.key === "Escape" && setOpen(false)} />
      <Select value={minutes} onChange={(e) => setMinutes(e.target.value)} aria-label="How long" className="h-9 w-[104px]">
        {MINUTES.map((m) => <option key={m} value={m}>{formatMinutes(m)}</option>)}
      </Select>
      <Button type="submit" size="sm" variant="primary" disabled={!title.trim()} loading={busy}>Add</Button>
      <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
    </form>
  );
}

/** Today's list from the mentor plan, and the student's to edit: tick tasks off (learning ticks its topics, revising
    logs the revision), take a planned task off today's list, add tasks of their own. */
export function TodayPlan({ className, compact }: { className?: string; compact?: boolean }) {
  const qc = useQueryClient();
  const college = useAuth((s) => isCollege(s.user?.exam_target));
  const { data: plan, isLoading } = usePlan();
  const apply = (today: Today) => qc.setQueryData<StudyPlan | null>(["prep-plan"], (p) => (p ? { ...p, today } : p));
  const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Couldn't update today's list");
  // a tick shows at once; the server's answer (which also ticks the topics a task covers) replaces it a moment later
  const check = useMutation({
    mutationFn: ({ key, done }: { key: string; done: boolean }) => api.checkTask(key, done),
    onMutate: async ({ key, done }) => {
      await qc.cancelQueries({ queryKey: ["prep-plan"] });
      const before = qc.getQueryData<StudyPlan | null>(["prep-plan"]);
      qc.setQueryData<StudyPlan | null>(["prep-plan"], (p) => (p?.today ? { ...p, today: { ...p.today, tasks: p.today.tasks.map((x) => (x.key === key ? { ...x, done } : x)) } } : p));
      return { before };
    },
    onSuccess: (today: Today) => {
      apply(today);
      qc.invalidateQueries({ queryKey: ["prep-syllabus"] });
      if (today.tasks.length && today.tasks.every((t) => t.done)) toast.success(`Today's plan done. That's how ${college ? "grades" : "ranks"} are built.`);
    },
    onError: (e, _task, ctx) => {
      if (ctx) qc.setQueryData(["prep-plan"], ctx.before);
      failed(e);
    },
  });
  const hide = useMutation({
    mutationFn: ({ key, hidden }: { key: string; hidden: boolean }) => api.hideTask(key, hidden),
    onSuccess: apply, onError: failed,
  });
  const add = useMutation({ mutationFn: (b: { title: string; minutes: number }) => api.addTask(b), onSuccess: apply, onError: failed });
  const remove = useMutation({ mutationFn: (id: number) => api.removeTask(id), onSuccess: apply, onError: failed });

  if (plan === null) return <GoalPrompt className={className} />;
  if (isLoading || !plan) return <Skeleton className={cn("h-64", className)} />;
  const today = plan.today;
  if (!today) return null;
  const done = today.tasks.filter((t) => t.done).length;
  const pct = today.tasks.length ? (100 * done) / today.tasks.length : 0;
  const hidden = today.hidden ?? [];
  const busyKey = hide.isPending ? hide.variables?.key : remove.isPending ? `custom:${remove.variables}` : null;
  return (
    <Card className={cn("p-5", className)}>
      <div className="mb-4 flex items-center gap-4">
        <ProgressRing value={pct} size={52} stroke={5}><span className="text-[11px] font-semibold">{done}/{today.tasks.length}</span></ProgressRing>
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold">Today's plan</h3>
          <p className="text-xs text-muted">{today.minutes ? `${formatMinutes(today.minutes)} planned` : "Rest day"} · from your mentor plan</p>
        </div>
        {!compact && <Link to="/app/plan" className="text-xs font-medium text-accent hover:underline">Full plan</Link>}
      </div>
      <div className="space-y-2">
        {today.tasks.map((t) => (
          <TaskRow key={t.key} task={t} busy={busyKey === t.key}
            onToggle={() => check.mutate({ key: t.key, done: !t.done })}
            onRemove={() => (t.kind === "custom" ? remove.mutate(Number(t.key.split(":")[1])) : hide.mutate({ key: t.key, hidden: true }))} />
        ))}
        {!today.tasks.length && today.note && (
          <div className="flex items-center gap-3 rounded-xl border border-dashed border-line-strong p-4 text-sm text-muted">
            <Coffee className="h-4 w-4 shrink-0" />{today.note}
          </div>
        )}
        <AddTask busy={add.isPending} onAdd={(title, minutes) => add.mutateAsync({ title, minutes }).catch(() => undefined)} />
      </div>
      {hidden.length > 0 && (
        <div className="mt-3 space-y-1 border-t border-line pt-3 text-xs text-muted">
          <div className="font-medium">Not today ({hidden.length}). They stay in your plan.</div>
          {hidden.map((h) => (
            <div key={h.key} className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate">{h.title}</span>
              <button type="button" onClick={() => hide.mutate({ key: h.key, hidden: false })} disabled={hide.isPending}
                className="inline-flex shrink-0 items-center gap-1 font-medium text-accent hover:underline disabled:opacity-60">
                <Undo2 className="h-3 w-3" />Put back
              </button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
