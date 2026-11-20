import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CalendarDays, Clock, Loader2, Target } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CollegeSetup } from "@/components/CollegeSetup";
import { Backdrop } from "@/components/Backdrop";
import { Logo } from "@/components/common";
import { Choice, Hours } from "@/components/PlanSteps";
import { Button } from "@/components/ui/button";
import { Input, Label, Segmented, Switch } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { Standing, StudyGoal } from "@/lib/types";
import { cn, examLabel, subjectColor } from "@/lib/utils";
import { useAuth } from "@/stores/auth";

const LEVELS: { value: Standing; label: string }[] = [
  { value: "none", label: "Not yet" }, { value: "partial", label: "Halfway" }, { value: "done", label: "Done" },
];
const STEPS = ["College & subjects", "Your exams", "Goal", "Your time", "Where you stand"];

const fmtDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const daysTo = (iso: string) => Math.ceil((new Date(`${iso}T00:00:00`).getTime() - Date.now()) / 86_400_000);

/** A B.Tech student's set-up: college, semester and subjects, the exams they are working towards, the grade they
    want, their hours and how far each subject has got. The plan it builds covers this semester's subjects. */
export default function CollegeOnboarding() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const { data: opts } = useQuery({ queryKey: ["prep-options"], queryFn: api.prepOptions, staleTime: 3_600_000 });
  const { data: existing, isFetched } = useQuery({ queryKey: ["prep-goal"], queryFn: api.prepGoal });
  const { data: setup } = useQuery({ queryKey: ["prep-college", null, null], queryFn: () => api.prepCollege() });
  const editing = !!existing && existing.track === "college";
  const [step, setStep] = useState(0);
  useEffect(() => { window.scrollTo(0, 0); }, [step]);  // each step starts at its heading (a phone would keep the last scroll)
  const [g, setG] = useState({ exam_date: "", target: "", dream: "", weekday_hours: 2.5, weekend_hours: 5, standing: {} as StudyGoal["standing"] });
  const [applyStanding, setApplyStanding] = useState(false);
  const [customDate, setCustomDate] = useState(false);

  useEffect(() => {
    if (existing && existing.track === "college") {
      setG({ exam_date: existing.exam_date, target: existing.target, dream: existing.dream ?? "", weekday_hours: existing.weekday_hours,
        weekend_hours: existing.weekend_hours, standing: existing.standing ?? {} });
    }
  }, [existing]);
  const dates = opts?.college.dates ?? [];
  const targets = opts?.targets.college ?? [];
  const target = targets.find((t) => t.id === g.target);
  const subjects = useMemo(() => setup?.subjects ?? [], [setup?.subjects]);
  useEffect(() => {  // sensible defaults: the coming end-semester exams, the second goal on the list
    if (!opts) return;
    setG((x) => ({ ...x, exam_date: x.exam_date && daysTo(x.exam_date) > 0 ? x.exam_date : opts.college.default_date,
      target: targets.some((t) => t.id === x.target) ? x.target : targets[1]?.id ?? targets[0]?.id ?? "" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts]);

  const weekly = 5 * g.weekday_hours + 2 * g.weekend_hours;
  const daily = weekly / 7;
  // with the exams under ten weeks away the semester is past half-way: assume classes have got that far too
  const usual: Standing = g.exam_date && daysTo(g.exam_date) < 70 ? "partial" : "none";
  const level = (s: string): Standing => g.standing[s]?.all ?? usual;
  const standing = useMemo(() => Object.fromEntries(subjects.map((s) => [s, { all: g.standing[s]?.all ?? usual }])) as StudyGoal["standing"],
    [subjects, g.standing, usual]);
  const save = useMutation({
    mutationFn: () => api.setPrepGoal({
      track: "college", class_level: String(setup!.semester), exam_date: g.exam_date, target: g.target, dream: g.dream.trim() || null,
      weekday_hours: g.weekday_hours, weekend_hours: g.weekend_hours, coaching: "self", standing, apply_standing: !editing || applyStanding,
    }),
    onSuccess: (plan) => {
      qc.setQueryData(["prep-plan"], plan);
      qc.setQueryData(["prep-goal"], plan.goal);
      ["prep-syllabus", "me", "overview"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      toast.success(editing ? "Plan updated" : "Your plan is ready");
      navigate("/app/plan", { replace: true });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't save your goal"),
  });

  if (!opts || !isFetched || !setup) {
    return <div className="grid min-h-dvh place-items-center bg-bg"><Loader2 className="h-6 w-6 animate-spin text-muted" /></div>;
  }
  const canNext = [true, !!g.exam_date && daysTo(g.exam_date) > 0, !!g.target, weekly > 0, true][step];
  const next = () => (step < STEPS.length - 1 ? setStep(step + 1) : save.mutate());

  return (
    <div className="flex min-h-dvh flex-col pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]">
      <Backdrop scene="plain" />
      <header className="flex items-center justify-between px-5 py-5 sm:px-10">
        <Logo />
        <button type="button" onClick={() => navigate(editing ? "/app/plan" : "/app")} className="py-2 text-sm text-muted hover:text-fg">
          {editing ? "Cancel" : "Skip for now"}
        </button>
      </header>
      <div className="mx-auto w-full max-w-2xl flex-1 px-5 pb-10">
        <div className="mb-8">
          <div className="mb-2 flex justify-between text-xs text-muted">
            <span>Step {step + 1} of {STEPS.length} · {STEPS[step]}</span>
            <span>{examLabel(user?.exam_target)}{setup.semester ? ` · Semester ${setup.semester}` : ""}</span>
          </div>
          <div className="flex gap-1.5">
            {STEPS.map((s, i) => <div key={s} className={cn("h-1.5 flex-1 rounded-full transition", i <= step ? "bg-accent" : "bg-elev-2")} />)}
          </div>
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={step} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.18 }}>
            {step === 0 && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">Where are you studying {setup.branch.short}?</h1>
                <p className="mt-2 text-sm text-muted">Your subjects, plan, tests and revision are built around this semester. Wrong branch? Change it in Settings.</p>
                <CollegeSetup className="mt-6" submitLabel="Continue" onSaved={() => setStep(1)} />
              </section>
            )}

            {step === 1 && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">Which exams are you working towards?</h1>
                <p className="mt-2 flex items-center gap-2 text-sm text-muted"><CalendarDays className="h-4 w-4 shrink-0 text-accent" />
                  These dates are typical, not your college's. Put in the first day of your own date sheet when it is out.</p>
                <div className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {dates.map((d) => (
                    <Choice key={d.date} on={!customDate && g.exam_date === d.date} onClick={() => { setCustomDate(false); setG({ ...g, exam_date: d.date }); }} className="p-3.5">
                      <span className="block text-sm font-semibold">{d.label}</span>
                      <span className="text-[13px] text-muted">around {fmtDate(d.date)} · {daysTo(d.date)} days</span>
                    </Choice>
                  ))}
                  <Choice on={customDate || !dates.some((d) => d.date === g.exam_date)} onClick={() => setCustomDate(true)} className="p-3.5">
                    <span className="block text-sm font-semibold">My own date</span>
                    {customDate || !dates.some((d) => d.date === g.exam_date) ? (
                      <Input type="date" className="mt-2 h-9" value={g.exam_date} onClick={(e) => e.stopPropagation()}
                        onChange={(e) => { setCustomDate(true); setG({ ...g, exam_date: e.target.value }); }} />
                    ) : <span className="text-[13px] text-muted">A class test, a quiz, your real date sheet</span>}
                  </Choice>
                </div>
                {!!g.exam_date && daysTo(g.exam_date) <= 0 && <p className="mt-3 text-xs text-warn">Pick a date from tomorrow onwards.</p>}
              </section>
            )}

            {step === 2 && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">What are you aiming for this semester?</h1>
                <p className="mt-2 text-sm text-muted">Be honest. Your plan and its reality checks are built around this.</p>
                <div className="mt-6 grid gap-2.5">
                  {targets.map((t) => (
                    <Choice key={t.id} on={g.target === t.id} onClick={() => setG({ ...g, target: t.id })} className="flex items-center gap-4 p-3.5">
                      <Target className={cn("h-5 w-5 shrink-0", g.target === t.id ? "text-accent" : "text-muted")} />
                      <span className="flex-1"><span className="block font-semibold">{t.label}</span><span className="text-[13px] text-muted">{t.hint}</span></span>
                      <span className="mr-6 hidden text-xs text-muted sm:block">~{t.hours} h a day</span>
                    </Choice>
                  ))}
                </div>
                <div className="mt-6">
                  <Label hint="optional">What is it for?</Label>
                  <Input value={g.dream} onChange={(e) => setG({ ...g, dream: e.target.value })} maxLength={120}
                    placeholder="e.g. a 9 CGPA, a summer internship, GATE 2028" />
                  <p className="mt-1.5 text-xs text-muted">It goes at the top of your plan. It helps on the hard days.</p>
                </div>
              </section>
            )}

            {step === 3 && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">How much time can you give?</h1>
                <p className="mt-2 text-sm text-muted">Self-study outside classes, labs and assignments. A plan you can keep beats an ambitious one you can't.</p>
                <div className="mt-6 space-y-6 rounded-2xl border border-line bg-bg-soft p-5">
                  <Hours label="On college days" value={g.weekday_hours} min={0.5} onChange={(v) => setG({ ...g, weekday_hours: v })} hint="Monday to Friday" />
                  <Hours label="On weekends and holidays" value={g.weekend_hours} min={0} onChange={(v) => setG({ ...g, weekend_hours: v })} hint="Saturday and Sunday" />
                </div>
                <div className={cn("mt-4 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm",
                  target && daily + 0.5 < target.hours ? "border-warn/30 bg-warn/10" : "border-ok/30 bg-ok/10")}>
                  <Clock className={cn("mt-0.5 h-4 w-4 shrink-0", target && daily + 0.5 < target.hours ? "text-warn" : "text-ok")} />
                  <span>
                    That's <b>{weekly} h a week</b> ({daily.toFixed(1)} h a day on average).{" "}
                    {target && (daily + 0.5 < target.hours
                      ? <>Students who get <b>{target.label}</b> usually manage about {target.hours} h a day. Your plan will show exactly what fits.</>
                      : <>That's what <b>{target.label}</b> usually takes.</>)}
                  </span>
                </div>
              </section>
            )}

            {step === 4 && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">How far has each subject got?</h1>
                <p className="mt-2 text-sm text-muted">Rough is fine: what your classes have covered and you have kept up with. You can tick exact topics in the Prep Hub afterwards.</p>
                <div className="mt-6 overflow-hidden rounded-2xl border border-line">
                  {subjects.map((s) => (
                    <div key={s} className="flex flex-col gap-2.5 border-b border-line p-4 last:border-0 sm:flex-row sm:items-center">
                      <div className="flex min-w-0 flex-1 items-center gap-2 text-sm font-semibold">
                        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: subjectColor(s) }} /><span className="truncate">{s}</span>
                      </div>
                      <Segmented size="sm" value={level(s)} onChange={(v) => setG({ ...g, standing: { ...g.standing, [s]: { all: v } } })} options={LEVELS} />
                    </div>
                  ))}
                </div>
                {editing && (
                  <div className="mt-4 rounded-xl border border-line bg-bg-soft p-3">
                    <Switch checked={applyStanding} onChange={setApplyStanding} label="Also tick these chapters in my Prep Hub (chapters you've ticked yourself stay as they are)" />
                  </div>
                )}
              </section>
            )}
          </motion.div>
        </AnimatePresence>

        {/* the first step saves itself (its own Continue button), so the subjects below are the ones just chosen */}
        {step > 0 && (
          <div className="mt-10 flex items-center justify-between">
            <Button variant="ghost" onClick={() => setStep(step - 1)} icon={<ArrowLeft className="h-4 w-4" />}>Back</Button>
            <Button variant="primary" size="lg" onClick={next} disabled={!canNext} loading={save.isPending}>
              {step < STEPS.length - 1 ? <>Continue <ArrowRight className="h-4 w-4" /></> : editing ? "Update my plan" : "Build my plan"}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
