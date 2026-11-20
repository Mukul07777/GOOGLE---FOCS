import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CalendarDays, Clock, Loader2, Target } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Backdrop } from "@/components/Backdrop";
import { Logo } from "@/components/common";
import { Choice, Hours } from "@/components/PlanSteps";
import { SchoolSubjects } from "@/components/SchoolSubjects";
import { Button } from "@/components/ui/button";
import { Input, Label, Segmented, Switch } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { Standing, StudyGoal } from "@/lib/types";
import { cn, examLabel, isBoards, isPlacement, isSsc, subjectColor } from "@/lib/utils";
import { useAuth } from "@/stores/auth";

const LEVELS: { value: Standing; label: string }[] = [
  { value: "none", label: "Not yet" }, { value: "partial", label: "Halfway" }, { value: "done", label: "Done" },
];
const fmtDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const daysTo = (iso: string) => Math.ceil((new Date(`${iso}T00:00:00`).getTime() - Date.now()) / 86_400_000);

/** Setting a goal for GATE (the paper is in the profile), for placements, or for a school class (which first asks for
    the subjects): the date to be ready by, what they are aiming for, their hours and how far each subject has got. */
export default function SimpleOnboarding() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const school = isBoards(user?.exam_target);
  const placement = isPlacement(user?.exam_target);
  const ssc = isSsc(user?.exam_target);
  const { data: opts } = useQuery({ queryKey: ["prep-options"], queryFn: api.prepOptions, staleTime: 3_600_000 });
  const { data: existing, isFetched } = useQuery({ queryKey: ["prep-goal"], queryFn: api.prepGoal });
  const { data: tree } = useQuery({ queryKey: ["prep-syllabus"], queryFn: () => api.prepSyllabus() });
  const group = school ? "cbse" : placement ? "placement" : ssc ? "ssc_cgl" : "gate";
  const editing = !!existing && existing.group === group;
  const steps = [...(school ? ["Your subjects"] : []), "Your exam", "Goal", "Your time", "Where you stand"];
  const [step, setStep] = useState(0);
  useEffect(() => { window.scrollTo(0, 0); }, [step]);  // each step starts at its heading
  const [g, setG] = useState({ exam_date: "", target: "", dream: "", weekday_hours: 4, weekend_hours: 7, standing: {} as StudyGoal["standing"] });
  const [applyStanding, setApplyStanding] = useState(false);
  const [customDate, setCustomDate] = useState(false);

  useEffect(() => {
    if (existing && existing.group === group) {
      setG({ exam_date: existing.exam_date, target: existing.target, dream: existing.dream ?? "", weekday_hours: existing.weekday_hours,
        weekend_hours: existing.weekend_hours, standing: existing.standing ?? {} });
    }
  }, [existing, group]);
  const exam = tree?.exam ?? "";
  const dates = opts?.rounds[school ? exam : group] ?? [];
  const targets = opts?.targets[group] ?? [];
  // a younger class studies less: the same share of the board-class hours the server plans with (planner.school_hours_share)
  const n = exam.startsWith("cbse_") ? Number(exam.slice(5)) : 12;
  const share = n <= 2 ? 0.25 : n <= 5 ? 0.4 : n <= 8 ? 0.6 : n <= 10 ? 0.85 : 1;
  const scaled = (h: number) => Math.round(h * share * 2) / 2;
  const found = targets.find((t) => t.id === g.target);
  const target = found && { ...found, hours: scaled(found.hours) };
  const subjects = useMemo(() => (tree?.subjects ?? []).map((s) => s.name), [tree]);
  const cls = exam.startsWith("cbse_") ? exam.slice(5) : "12";
  const key = school ? cls : "all";  // how far a subject has got: by class at school, as a whole for a GATE subject
  useEffect(() => {  // sensible defaults: the main exam of the year, the second goal on the list
    if (!opts || !dates.length) return;
    const main = dates.find((d) => /Board|Final|GATE|season|Tier-I$/.test(d.label)) ?? dates[0];
    setG((x) => ({ ...x, ...(editing || share === 1 ? {} : { weekday_hours: Math.max(0.5, scaled(4)), weekend_hours: scaled(7) }), exam_date: x.exam_date && daysTo(x.exam_date) > 0 ? x.exam_date : main.date,
      target: targets.some((t) => t.id === x.target) ? x.target : targets[1]?.id ?? targets[0]?.id ?? "" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts, exam]);

  const weekly = 5 * g.weekday_hours + 2 * g.weekend_hours;
  const daily = weekly / 7;
  const level = (s: string): Standing => (g.standing[s] as Record<string, Standing> | undefined)?.[key] ?? "none";
  const standing = useMemo(() => Object.fromEntries(subjects.map((s) => [s, { [key]: level(s) }])) as StudyGoal["standing"],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [subjects, g.standing, key]);
  const save = useMutation({
    mutationFn: () => api.setPrepGoal({
      track: group, class_level: school ? cls : "dropper", exam_date: g.exam_date, target: g.target, dream: g.dream.trim() || null,
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

  if (!opts || !isFetched || !tree) {
    return <div className="grid min-h-dvh place-items-center"><Loader2 className="h-6 w-6 animate-spin text-muted" /></div>;
  }
  const name = steps[step];
  const canNext = name === "Your exam" ? !!g.exam_date && daysTo(g.exam_date) > 0 : name === "Goal" ? !!g.target : name === "Your time" ? weekly > 0 : true;
  const next = () => (step < steps.length - 1 ? setStep(step + 1) : save.mutate());

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
            <span>Step {step + 1} of {steps.length} · {placement && name === "Your exam" ? "Your placements" : name}</span><span>{examLabel(user?.exam_target)}</span>
          </div>
          <div className="flex gap-1.5">
            {steps.map((s, i) => <div key={s} className={cn("h-1.5 flex-1 rounded-full transition", i <= step ? "bg-accent" : "bg-elev-2")} />)}
          </div>
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={step} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.18 }}>
            {name === "Your subjects" && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">{Number(cls) >= 11 ? "Which stream are you in?" : "Which subjects do you have?"}</h1>
                <p className="mt-2 text-sm text-muted">Class {cls}, from the NCERT books. Your Prep Hub, plan and tests cover the ones you tick. Wrong class? Change it in Settings.</p>
                <div className="mt-6"><SchoolSubjects all={tree.choices ?? subjects} mine={subjects} submitLabel="Continue" ask={!editing} onSaved={() => setStep(1)} /></div>
              </section>
            )}

            {name === "Your exam" && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">{school ? "Which exam are you working towards?" : placement ? "When do placements start for you?" : ssc ? "Which SSC CGL stage are you aiming at?" : "When is your GATE?"}</h1>
                <p className="mt-2 flex items-center gap-2 text-sm text-muted"><CalendarDays className="h-4 w-4 shrink-0 text-accent" />
                  {school ? "These dates are typical. Put in your own date sheet's first day when you have it."
                    : placement ? "Most colleges open the season in August of the final year, with internship drives after it. Put in your own college's date when you know it."
                      : ssc ? "Approximate dates: SSC's own exam calendar fixes each year's Tier-I and Tier-II. Change it once the notice is out."
                      : "GATE is held over the first two weekends of February. Change the date once your paper's slot is announced."}</p>
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
                    ) : <span className="text-[13px] text-muted">{school ? "A unit test, your school's date sheet" : placement ? "Your college's first drive, an off-campus interview" : ssc ? "Another SSC exam, a test series" : "Next year's attempt, a test series"}</span>}
                  </Choice>
                </div>
              </section>
            )}

            {name === "Goal" && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">What are you aiming for?</h1>
                <p className="mt-2 text-sm text-muted">Be ambitious and honest. Your plan and its reality checks are built around this.</p>
                <div className="mt-6 grid gap-2.5">
                  {targets.map((t) => (
                    <Choice key={t.id} on={g.target === t.id} onClick={() => setG({ ...g, target: t.id })} className="flex items-center gap-4 p-3.5">
                      <Target className={cn("h-5 w-5 shrink-0", g.target === t.id ? "text-accent" : "text-muted")} />
                      <span className="flex-1"><span className="block font-semibold">{t.label}</span><span className="text-[13px] text-muted">{t.hint}</span></span>
                      <span className="mr-6 hidden text-xs text-muted sm:block">~{scaled(t.hours)} h a day</span>
                    </Choice>
                  ))}
                </div>
                <div className="mt-6">
                  <Label hint="optional">What is it for?</Label>
                  <Input value={g.dream} onChange={(e) => setG({ ...g, dream: e.target.value })} maxLength={120}
                    placeholder={school ? (Number(cls) <= 8 ? "e.g. Top marks in Maths, reading every day" : Number(cls) <= 10 ? "e.g. 95% in the boards, science in Class 11" : "e.g. SRCC, a 95 in Physics, JEE next year") : placement ? "e.g. SDE at a product company, a 12 LPA offer" : ssc ? "e.g. Income Tax Inspector, ASO in a ministry" : "e.g. IISc M.Tech, IOCL, IIT Bombay CSE"} />
                </div>
              </section>
            )}

            {name === "Your time" && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">How much time can you give?</h1>
                <p className="mt-2 text-sm text-muted">{school ? "Self-study and tuition, not school hours." : placement ? "Preparation outside your classes and labs." : "Self-study and coaching, outside college or work."} A plan you can keep beats an ambitious one you can't.</p>
                <div className="mt-6 space-y-6 rounded-2xl border border-line bg-bg-soft p-5">
                  <Hours label={school ? "On school days" : placement ? "On college days" : "On working days"} value={g.weekday_hours} min={0.5} onChange={(v) => setG({ ...g, weekday_hours: v })} hint="Monday to Friday" />
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
              </section>
            )}

            {name === "Where you stand" && (
              <section>
                <h1 className="text-[30px] sm:text-[38px]">How much have you covered?</h1>
                <p className="mt-2 text-sm text-muted">Rough is fine. You can tick exact topics in the Prep Hub afterwards.</p>
                <div className="mt-6 overflow-hidden rounded-2xl border border-line">
                  {subjects.map((s) => (
                    <div key={s} className="flex flex-col gap-2.5 border-b border-line p-4 last:border-0 sm:flex-row sm:items-center">
                      <div className="flex min-w-0 flex-1 items-center gap-2 text-sm font-semibold">
                        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: subjectColor(s) }} /><span className="truncate">{s}</span>
                      </div>
                      <Segmented size="sm" value={level(s)} onChange={(v) => setG({ ...g, standing: { ...g.standing, [s]: { [key]: v } } })} options={LEVELS} />
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

        {name !== "Your subjects" && (
          <div className="mt-10 flex items-center justify-between">
            <Button variant="ghost" onClick={() => setStep(step - 1)} disabled={step === 0} icon={<ArrowLeft className="h-4 w-4" />}>Back</Button>
            <Button variant="primary" size="lg" onClick={next} disabled={!canNext} loading={save.isPending}>
              {step < steps.length - 1 ? <>Continue <ArrowRight className="h-4 w-4" /></> : editing ? "Update my plan" : "Build my plan"}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
