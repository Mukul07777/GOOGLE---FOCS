import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Minus, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Segmented, Select } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { StudyPlan } from "@/lib/types";
import { cn } from "@/lib/utils";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const fmtDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const hoursText = (h: number) => `${Number.isInteger(h) ? h : h.toFixed(1)} h`;
const localIso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function Stepper({ label, value, onChange, compact }: { label: string; value: number; onChange: (v: number) => void; compact?: boolean }) {
  const step = (by: number) => onChange(Math.max(0, Math.min(16, Math.round((value + by) * 2) / 2)));
  const button = "grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line bg-elev-2 text-fg-soft transition hover:border-line-strong hover:text-fg disabled:opacity-40";
  return (
    <div className={cn("rounded-xl border border-line bg-bg-soft", compact ? "flex flex-col items-center gap-1.5 px-1 py-2" : "flex items-center gap-3 p-3")}>
      <span className={cn("font-medium", compact ? "text-xs text-muted" : "flex-1 text-sm")}>{label}</span>
      <div className={cn("flex items-center", compact ? "flex-col gap-1" : "gap-2")}>
        {compact && <button type="button" className={button} onClick={() => step(0.5)} disabled={value >= 16} aria-label={`More hours on ${label}`}><Plus className="h-3.5 w-3.5" /></button>}
        {!compact && <button type="button" className={button} onClick={() => step(-0.5)} disabled={value <= 0} aria-label={`Fewer hours on ${label}`}><Minus className="h-3.5 w-3.5" /></button>}
        <span className={cn("whitespace-nowrap text-center font-semibold tabular-nums", compact ? "text-sm" : "w-14 text-base", value === 0 && "text-muted")}>
          {!compact ? hoursText(value) : value === 0 ? "Off" : <>{Number.isInteger(value) ? value : value.toFixed(1)}<span className="hidden font-normal text-muted sm:inline"> h</span></>}
        </span>
        {compact && <button type="button" className={button} onClick={() => step(-0.5)} disabled={value <= 0} aria-label={`Fewer hours on ${label}`}><Minus className="h-3.5 w-3.5" /></button>}
        {!compact && <button type="button" className={button} onClick={() => step(0.5)} disabled={value >= 16} aria-label={`More hours on ${label}`}><Plus className="h-3.5 w-3.5" /></button>}
      </div>
    </div>
  );
}

/** Edit the plan where it is shown: study hours (two numbers, or day by day), the exam date, the goal. Saving rebuilds
    the whole plan around the change. */
export function EditPlanDialog({ plan, open, onClose }: { plan: StudyPlan; open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: opts } = useQuery({ queryKey: ["prep-options"], queryFn: api.prepOptions, staleTime: 3_600_000 });
  const [mode, setMode] = useState<"two" | "days">("two");
  const [weekday, setWeekday] = useState(5);
  const [weekend, setWeekend] = useState(8);
  const [days, setDays] = useState<number[]>([5, 5, 5, 5, 5, 8, 8]);
  const [examDate, setExamDate] = useState("");
  const [target, setTarget] = useState("");
  const [dream, setDream] = useState("");

  useEffect(() => {  // start from the plan as it is, every time the dialog opens
    if (!open) return;
    setMode(plan.hours.custom_days ? "days" : "two");
    setWeekday(Math.round(plan.hours.weekday * 2) / 2);
    setWeekend(Math.round(plan.hours.weekend * 2) / 2);
    setDays(plan.hours.by_day);
    setExamDate(plan.exam_date);
    setTarget(plan.target.id);
    setDream(plan.goal.dream ?? "");
  }, [open, plan]);

  const byDay = mode === "days" ? days : [weekday, weekday, weekday, weekday, weekday, weekend, weekend];
  const weekly = byDay.reduce((a, b) => a + b, 0);
  const college = plan.kind === "college";
  const targets = opts?.targets[plan.goal.group ?? (plan.goal.exam as "jee" | "neet")] ?? [];
  const usual = targets.find((t) => t.id === target)?.hours;
  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1);
  const latest = new Date(); latest.setFullYear(latest.getFullYear() + 3);
  const dateOk = !!examDate && examDate >= localIso(tomorrow) && examDate <= localIso(latest);
  const track = plan.goal.track;
  const choices = (college ? opts?.college.dates.map((d) => d.date)
    : track === "gate" || track === "cbse" || track === "placement" || track === "ssc_cgl" ? opts?.rounds[track === "cbse" ? plan.goal.exam : track]?.map((d) => d.date)
      : track !== "college" ? opts?.date_choices[track] : null) ?? [];

  const save = useMutation({
    mutationFn: () => api.editPlan({
      ...(mode === "days" ? { day_hours: days } : { weekday_hours: weekday, weekend_hours: weekend }),
      exam_date: examDate, target, dream,
    }),
    onSuccess: (next) => {
      qc.setQueryData(["prep-plan"], next);
      for (const key of ["prep-goal", "me", "overview"]) qc.invalidateQueries({ queryKey: [key] });
      toast.success("Plan rebuilt around your changes");
      onClose();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't save your plan. Try again."),
  });

  return (
    <Dialog open={open} onClose={onClose} wide title="Edit your plan" subtitle="Change anything here and the whole plan is rebuilt around it.">
      <div className="space-y-6">
        <section>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <Label className="mb-0">Study hours</Label>
            <Segmented size="sm" value={mode} onChange={(m) => { if (m === "days") setDays(byDay); setMode(m); }}
              options={[{ value: "two", label: "Weekdays and weekends" }, { value: "days", label: "Day by day" }]} />
          </div>
          {mode === "two" ? (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Stepper label="Monday to Friday" value={weekday} onChange={setWeekday} />
              <Stepper label="Saturday and Sunday" value={weekend} onChange={setWeekend} />
            </div>
          ) : (
            <div className="grid grid-cols-7 gap-1.5">
              {DAYS.map((d, i) => <Stepper key={d} compact label={d} value={days[i]} onChange={(v) => setDays(days.map((x, k) => (k === i ? v : x)))} />)}
            </div>
          )}
          <p className={cn("mt-2 text-xs", weekly < 1 ? "text-warn" : "text-muted")}>
            {weekly < 1 ? "A plan needs at least an hour of study in the week."
              : <>{hoursText(weekly)} a week, about {hoursText(Math.round((weekly / 7) * 10) / 10)} a day
                {usual ? `. Students who reach this goal usually study about ${usual} h a day, ${college ? "outside classes" : "classes included"}.` : "."}</>}
          </p>
        </section>

        <section>
          <Label htmlFor="plan-exam-date">Exam date</Label>
          <div className="flex flex-wrap items-center gap-2">
            {choices.map((d) => (
              <button key={d} type="button" onClick={() => setExamDate(d)} aria-pressed={examDate === d}
                className={cn("h-9 rounded-lg border px-3 text-[13px] font-medium transition",
                  examDate === d ? "border-accent/60 bg-accent-soft text-fg" : "border-line bg-bg-soft text-fg-soft hover:border-line-strong")}>
                {fmtDate(d)}
              </button>
            ))}
            <Input id="plan-exam-date" type="date" value={examDate} min={localIso(tomorrow)} max={localIso(latest)}
              onChange={(e) => setExamDate(e.target.value)} className="h-9 w-auto" />
          </div>
          {!dateOk && <p className="mt-2 text-xs text-warn">Pick a date from tomorrow up to three years from now.</p>}
        </section>

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="plan-target">Goal</Label>
            <Select id="plan-target" value={target} onChange={(e) => setTarget(e.target.value)}>
              {targets.length ? targets.map((t) => <option key={t.id} value={t.id}>{t.label}</option>) : <option value={target}>{plan.target.label}</option>}
            </Select>
          </div>
          <div>
            <Label htmlFor="plan-dream" hint="optional">Dream college</Label>
            <Input id="plan-dream" value={dream} onChange={(e) => setDream(e.target.value)} maxLength={120} placeholder="IIT Bombay CSE, AIIMS Delhi…" />
          </div>
        </section>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <Link to="/onboarding" className="text-xs text-muted hover:text-fg">{college ? "Change semester, subjects or what you've already covered" : "Change exam, class or what you've already covered"}</Link>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button variant="primary" loading={save.isPending} disabled={weekly < 1 || !dateOk} onClick={() => save.mutate()}>Save and rebuild</Button>
          </div>
        </div>
      </div>
    </Dialog>
  );
}
