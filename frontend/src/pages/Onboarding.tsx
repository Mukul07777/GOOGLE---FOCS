import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Atom, CalendarDays, Clock, GraduationCap, Loader2, Stethoscope, Target } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Backdrop } from "@/components/Backdrop";
import { Logo } from "@/components/common";
import { Choice, Hours } from "@/components/PlanSteps";
import { Button } from "@/components/ui/button";
import { Input, Label, Segmented, Switch } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import CollegeOnboarding from "@/pages/OnboardingCollege";
import SimpleOnboarding from "@/pages/OnboardingSimple";
import type { ClassLevel, EntranceTrack, Standing, StudyGoal } from "@/lib/types";
import { cn, examGroup, subjectColor } from "@/lib/utils";
import { useAuth } from "@/stores/auth";

const TRACK_UI: Record<EntranceTrack, { icon: ReactNode; blurb: string }> = {
  jee_main: { icon: <Atom className="h-5 w-5" />, blurb: "NITs, IIITs and state colleges" },
  jee_advanced: { icon: <GraduationCap className="h-5 w-5" />, blurb: "Main first, then Advanced for the IITs" },
  neet: { icon: <Stethoscope className="h-5 w-5" />, blurb: "MBBS, BDS and AYUSH" },
};
const CLASSES: { id: ClassLevel; label: string; hint: string }[] = [
  { id: "11", label: "Class 11", hint: "Two years to go" },
  { id: "12", label: "Class 12", hint: "Boards and the exam this year" },
  { id: "dropper", label: "Dropper", hint: "A full year for the exam" },
];
const LEVELS: { value: Standing; label: string }[] = [
  { value: "none", label: "Not yet" }, { value: "partial", label: "Halfway" }, { value: "done", label: "Done" },
];
const STEPS = ["Exam", "Class & date", "Goal", "Your time", "Where you stand"];

const fmtDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const daysTo = (iso: string) => Math.ceil((new Date(`${iso}T00:00:00`).getTime() - Date.now()) / 86_400_000);
const sessionName = (track: EntranceTrack, iso: string) =>
  track === "neet" ? "NEET UG" : new Date(`${iso}T00:00:00`).getMonth() === 0 ? "JEE Main session 1" : "JEE Main session 2";

/** Two minutes after signing up: goal, time and where they stand → a mentor plan. Also "Edit my goal" later.
    A B.Tech student gets the college version: college, semester and subjects, then their exams. */
export default function Onboarding() {
  const group = useAuth((s) => examGroup(s.user?.exam_target));
  return group === "college" ? <CollegeOnboarding /> : group === "gate" || group === "cbse" || group === "coding" || group === "ssc_cgl" ? <SimpleOnboarding /> : <EntranceOnboarding />;
}

function EntranceOnboarding() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const { data: opts } = useQuery({ queryKey: ["prep-options"], queryFn: api.prepOptions, staleTime: 3_600_000 });
  const { data: existing, isFetched } = useQuery({ queryKey: ["prep-goal"], queryFn: api.prepGoal });
  const editing = !!existing;
  const first = user?.exam_target === "neet" ? 1 : 0;  // NEET has one track: nothing to pick on the first step
  const [step, setStep] = useState(first);
  useEffect(() => { window.scrollTo(0, 0); }, [step]);  // each step starts at its heading (a phone would keep the last scroll)
  const [g, setG] = useState<Omit<StudyGoal, "exam" | "track" | "class_level"> & { track: EntranceTrack; class_level: ClassLevel }>({
    track: user?.exam_target === "neet" ? "neet" : "jee_main", class_level: "12", exam_date: "", target: "",
    dream: "", weekday_hours: 5, weekend_hours: 8, coaching: "self", standing: {},
  });
  const [applyStanding, setApplyStanding] = useState(false);
  const [customDate, setCustomDate] = useState(false);

  useEffect(() => {  // (a goal left from a B.Tech semester isn't this wizard's to edit: start afresh)
    if (existing && (existing.track === "jee_main" || existing.track === "jee_advanced" || existing.track === "neet")) {
      setG({ ...existing, track: user?.exam_target === "neet" ? "neet" : existing.track, class_level: existing.class_level as ClassLevel, dream: existing.dream ?? "" });
    }
  }, [existing, user?.exam_target]);
  const exam = g.track === "neet" ? "neet" : "jee";
  const targets = useMemo(() => opts?.targets[exam] ?? [], [opts, exam]);
  const target = targets.find((t) => t.id === g.target);
  const subjects = opts?.subjects[exam] ?? [];
  const choices = opts?.date_choices[g.track] ?? [];

  // sensible defaults as the student picks: the next exam for their class, a goal for their exam
  useEffect(() => {
    if (!opts || (existing && g.track === existing.track && g.class_level === existing.class_level)) return;
    setG((x) => ({ ...x, exam_date: opts.default_dates[x.track][x.class_level] }));
    setCustomDate(false);
  }, [opts, g.track, g.class_level, existing]);
  useEffect(() => {
    if (targets.length && !targets.some((t) => t.id === g.target)) setG((x) => ({ ...x, target: targets[1]?.id ?? targets[0].id }));
  }, [targets, g.target]);

  const weekly = 5 * g.weekday_hours + 2 * g.weekend_hours;
  const daily = weekly / 7;
  const save = useMutation({
    mutationFn: (goal: Parameters<typeof api.setPrepGoal>[0]) => api.setPrepGoal(goal),
    onSuccess: (plan) => {
      qc.setQueryData(["prep-plan"], plan);
      qc.setQueryData(["prep-goal"], plan.goal);
      ["prep-syllabus", "me", "overview"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      toast.success(editing ? "Plan updated" : "Your plan is ready");
      navigate("/app/plan", { replace: true });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't save your goal"),
  });

  const canNext = [true, !!g.exam_date && daysTo(g.exam_date) > 0, !!g.target, weekly > 0, true][step];
  const level = (s: string, cls: "11" | "12"): Standing => g.standing[s]?.[cls] ?? (cls === "11" && g.class_level !== "11" ? "partial" : "none");
  const setLevel = (s: string, cls: "11" | "12", v: Standing) => setG((x) => ({ ...x, standing: { ...x.standing, [s]: { ...x.standing[s], [cls]: v } } }));
  // fill in the defaults shown, so what is saved is what the student saw
  const withStanding = useMemo(() => {
    const st: StudyGoal["standing"] = {};
    for (const s of subjects) st[s] = { "11": level(s, "11"), ...(g.class_level !== "11" ? { "12": level(s, "12") } : {}) };
    return st;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subjects, g.standing, g.class_level]);

  const next = () => {
    if (step < STEPS.length - 1) return setStep(step + 1);
    save.mutate({ ...g, standing: withStanding, dream: g.dream?.trim() || null, apply_standing: !editing || applyStanding });
  };

  if (!opts || !isFetched) {
    return <div className="grid min-h-dvh place-items-center bg-bg"><Loader2 className="h-6 w-6 animate-spin text-muted" /></div>;
  }

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
            <span>Step {step + 1 - first} of {STEPS.length - first} · {STEPS[step]}</span>
            <span>{editing ? "Editing your goal" : "Takes about 2 minutes"}</span>
          </div>
          <div className="flex gap-1.5">
            {STEPS.slice(first).map((s, i) => <div key={s} className={cn("h-1.5 flex-1 rounded-full transition", i + first <= step ? "bg-accent" : "bg-elev-2")} />)}
          </div>
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={step} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.18 }}>
            {step === 0 && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">Which exam are you preparing for?</h1>
                <p className="mt-2 text-sm text-muted">Your syllabus, plan and practice are built around it.</p>
                <div className="mt-6 grid gap-3">
                  {opts.tracks.filter((t) => t.exam === (user?.exam_target === "neet" ? "neet" : "jee")).map((t) => (  // a JEE student's tracks are JEE's
                    <Choice key={t.id} on={g.track === t.id} onClick={() => setG({ ...g, track: t.id, standing: {} })} className="flex items-center gap-4">
                      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-elev-2 text-accent">{TRACK_UI[t.id].icon}</span>
                      <span><span className="block font-semibold">{t.label}</span><span className="text-[13px] text-muted">{TRACK_UI[t.id].blurb}</span></span>
                    </Choice>
                  ))}
                </div>
              </section>
            )}

            {step === 1 && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">Where are you right now?</h1>
                <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {CLASSES.map((c) => (
                    <Choice key={c.id} on={g.class_level === c.id} onClick={() => setG({ ...g, class_level: c.id, standing: {} })}>
                      <span className="block font-semibold">{c.label}</span><span className="text-[13px] text-muted">{c.hint}</span>
                    </Choice>
                  ))}
                </div>
                <h2 className="mt-8 flex items-center gap-2 font-semibold"><CalendarDays className="h-4 w-4 text-accent" />Your exam</h2>
                <p className="mt-1 text-[13px] text-muted">Dates are approximate until NTA announces them. You can change this any time.</p>
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {choices.map((d) => (
                    <Choice key={d} on={!customDate && g.exam_date === d} onClick={() => { setCustomDate(false); setG({ ...g, exam_date: d }); }} className="p-3.5">
                      <span className="block text-sm font-semibold">{sessionName(g.track, d)}</span>
                      <span className="text-[13px] text-muted">{fmtDate(d)} · {daysTo(d)} days</span>
                    </Choice>
                  ))}
                  <Choice on={customDate} onClick={() => setCustomDate(true)} className="p-3.5">
                    <span className="block text-sm font-semibold">Another date</span>
                    {customDate ? (
                      <Input type="date" className="mt-2 h-9" value={g.exam_date} onClick={(e) => e.stopPropagation()}
                        onChange={(e) => setG({ ...g, exam_date: e.target.value })} />
                    ) : <span className="text-[13px] text-muted">Pick it yourself</span>}
                  </Choice>
                </div>
              </section>
            )}

            {step === 2 && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">What are you aiming for?</h1>
                <p className="mt-2 text-sm text-muted">Be ambitious and honest. Your plan and its reality checks are built around this.</p>
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
                  <Label hint="optional">Your dream college</Label>
                  <Input value={g.dream ?? ""} onChange={(e) => setG({ ...g, dream: e.target.value })} maxLength={120}
                    placeholder={exam === "neet" ? "e.g. AIIMS Delhi, MAMC" : "e.g. IIT Bombay CSE, NIT Trichy"} />
                  <p className="mt-1.5 text-xs text-muted">We'll put it at the top of your plan. It helps on the hard days.</p>
                </div>
              </section>
            )}

            {step === 3 && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">How much time can you give?</h1>
                <p className="mt-2 text-sm text-muted">Include coaching classes and self-study, not school. A plan you can keep beats an ambitious one you can't.</p>
                <div className="mt-6 space-y-6 rounded-2xl border border-line bg-bg-soft p-5">
                  <Hours label="On school / college days" value={g.weekday_hours} min={0.5} onChange={(v) => setG({ ...g, weekday_hours: v })} hint="Monday to Friday" />
                  <Hours label="On weekends and holidays" value={g.weekend_hours} min={0} onChange={(v) => setG({ ...g, weekend_hours: v })} hint="Saturday and Sunday" />
                </div>
                <div className={cn("mt-4 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm",
                  target && daily + 0.5 < target.hours ? "border-warn/30 bg-warn/10" : "border-ok/30 bg-ok/10")}>
                  <Clock className={cn("mt-0.5 h-4 w-4 shrink-0", target && daily + 0.5 < target.hours ? "text-warn" : "text-ok")} />
                  <span>
                    That's <b>{weekly} h a week</b> ({daily.toFixed(1)} h a day on average).{" "}
                    {target && (daily + 0.5 < target.hours
                      ? <>Students who reach <b>{target.label}</b> usually manage about {target.hours} h a day. Your plan will show exactly what fits.</>
                      : <>That's what <b>{target.label}</b> usually takes.</>)}
                  </span>
                </div>
                <div className="mt-6">
                  <Label>Coaching</Label>
                  <Segmented value={g.coaching} onChange={(v) => setG({ ...g, coaching: v })}
                    options={[{ value: "self", label: "Self-study" }, { value: "online", label: "Online" }, { value: "offline", label: "Offline institute" }]} />
                </div>
              </section>
            )}

            {step === 4 && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">How much have you covered?</h1>
                <p className="mt-2 text-sm text-muted">Rough is fine. You can tick exact topics in the Prep Hub afterwards.</p>
                <div className="mt-6 overflow-hidden rounded-2xl border border-line">
                  {subjects.map((s) => (
                    <div key={s} className="flex flex-col gap-3 border-b border-line p-4 last:border-0 sm:flex-row sm:items-center">
                      <div className="flex w-32 items-center gap-2 font-semibold"><span className="h-2.5 w-2.5 rounded-full" style={{ background: subjectColor(s) }} />{s}</div>
                      <div className="flex flex-1 flex-col gap-2">
                        {(g.class_level === "11" ? (["11"] as const) : (["11", "12"] as const)).map((cls) => (
                          <div key={cls} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                            <span className="w-16 text-xs text-muted">Class {cls}</span>
                            <Segmented size="sm" value={level(s, cls)} onChange={(v) => setLevel(s, cls, v)} options={LEVELS} />
                          </div>
                        ))}
                      </div>
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

        <div className="mt-10 flex items-center justify-between">
          <Button variant="ghost" onClick={() => setStep(step - 1)} disabled={step === first} icon={<ArrowLeft className="h-4 w-4" />}>Back</Button>
          <Button variant="primary" size="lg" onClick={next} disabled={!canNext} loading={save.isPending}>
            {step < STEPS.length - 1 ? <>Continue <ArrowRight className="h-4 w-4" /></> : editing ? "Update my plan" : "Build my plan"}
          </Button>
        </div>
      </div>
    </div>
  );
}
