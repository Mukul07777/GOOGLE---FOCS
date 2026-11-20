import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Accessibility, Check, Copy, Cpu, Download, Gauge, GraduationCap, HeartHandshake, KeyRound, Moon, ShieldCheck, Sparkles, Sun, Trash2, User as UserIcon, Wifi, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, CardHeader, Input, Label, ProgressBar, Segmented, Skeleton, Switch } from "@/components/ui/primitives";
import { LanguagePicker } from "@/components/Explain";
import { ReadAloud } from "@/components/ReadAloud";
import { useA11y } from "@/stores/a11y";
import type { Language, ProPass } from "@/lib/types";
import { meterTone, resetLine, useUsage } from "@/components/UsageMeter";
import { api } from "@/lib/api";
import { CollegeSetup } from "@/components/CollegeSetup";
import { clockAt, cn, downloadResponse, EXAMS, formatDate, SIGNUP_EXAMS, examGroup, formatMinutes, isCollege, SUB_EXAMS, subExamOf, targetFor } from "@/lib/utils";
import { pay, PaymentCancelled } from "@/lib/checkout";
import { chooseServer, IN_APP } from "@/lib/server";
import { copyText } from "@/pages/Classes";
import { useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";
import { useT } from "@/lib/i18n";

function UsageCard() {
  const tr = useT();
  const { data: u } = useUsage();
  if (!u) return <Skeleton className="h-56" />;
  const meters = [
    { label: tr("Lecture notes today"), hint: "No daily cap on lecture time", m: u.lecture, hours: u.window_hours, time: true },
    { label: u.window_hours === 24 ? "Doubts & practice today" : `Every ${u.window_hours} hours`, hint: "Opens with your first AI action", m: u.window, hours: u.window_hours },
    { label: tr("This week"), hint: "A weekly cap on top", m: u.week, hours: 24 * 7 },
  ];
  const pro = u.limits.pro;
  return (
    <Card id="usage" className="scroll-mt-20">
      <CardHeader title={tr("AI allowance")} icon={<Gauge className="h-4 w-4" />}
        subtitle={u.window_hours === 24 ? "Your AI allowance is a study day: it refreshes a day after you start using it. Offline answers are always free."
          : `Your AI allowance refreshes ${u.window_hours} hours after you start using it. Offline answers are always free.`} />
      <div className="grid gap-3 p-5 md:grid-cols-2">
        {meters.map(({ label, hint, m, hours, time }) => (
          <div key={label} className="rounded-2xl border border-line bg-bg-soft p-4">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium">{label}</span>
              <span className="text-xs tabular-nums text-muted">
                {m.unlimited ? "Unlimited" : time ? `${formatMinutes(m.used)} / ${formatMinutes(m.limit ?? 0)}` : `${m.used} / ${m.limit}`}
              </span>
            </div>
            {!m.unlimited && <ProgressBar value={m.pct} tone={meterTone(m.pct)} className="mt-3" />}
            <div className="mt-2 text-xs text-muted">{m.unlimited ? hint : resetLine(m, hours)}</div>
          </div>
        ))}
        <div className="rounded-2xl border border-line bg-bg-soft p-4">
          <div className="flex items-baseline justify-between">
            <span className="text-sm font-medium">Full mock tests</span>
            <span className="text-xs tabular-nums text-muted">{u.mocks.unlimited ? "Unlimited" : `${u.mocks.used} / ${u.mocks.limit} this week`}</span>
          </div>
          {!u.mocks.unlimited && <ProgressBar value={100 * u.mocks.used / Math.max(1, u.mocks.limit ?? 1)} tone={u.mocks.left ? "accent" : "bad"} className="mt-3" />}
          <div className="mt-2 text-xs text-muted">
            {u.mocks.unlimited ? "No weekly cap" : u.mocks.left ? `${u.mocks.left} left — counted when you start one` : `Next one unlocks ${clockAt(u.mocks.resets_at)}`}
          </div>
        </div>
      </div>
      <div className="grid gap-5 border-t border-line p-5 md:grid-cols-[1.4fr_1fr]">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted">What uses it</div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[13px]">
            {u.costs.map((c) => (
              <div key={c.action} className="flex justify-between gap-2 border-b border-line/60 py-1">
                <span className="text-fg-soft">{c.label}</span><span className="tabular-nums text-muted">{c.cost}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-line bg-bg-soft p-4 text-[13px]">
          <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted">If you run out</div>
          <ul className="space-y-1.5 text-fg-soft">
            <li>• Your live lecture never stops — past today's lecture hours, boards get basic notes until the next day.</li>
            <li>• Revision sheets are still written at the end of a lecture.</li>
            <li>• Flashcard reviews, your library and mock tests don't use AI allowance.</li>
            <li>• A lecture another Focs student already captured is free: its boards don't use your allowance.</li>
          </ul>
          {!u.captions.unlimited && (
            <p className="mt-3 text-xs text-muted">Lecture captions: {u.captions.used} of {u.captions.limit} minutes used this week
              {u.captions.resets_at ? `, back ${clockAt(u.captions.resets_at)}` : ""}. Past that, the board notes carry on without captions.</p>
          )}
          {u.plan === "free" && (
            <p className="mt-3 text-xs text-muted">Pro: AI notes for up to {formatMinutes(u.lecture_limits.pro ?? 0)} of lecture a day, and {pro.window} units
              {u.window_hours === 24 ? " a day" : ` every ${u.window_hours} h`} for doubts and practice.</p>
          )}
          {u.fair_use_pct !== null && u.fair_use_pct >= 50 && (
            <p className="mt-3 text-xs text-muted">Fair use: {u.fair_use_pct}% of your plan's AI for the last 30 days. Past it, AI gives basic answers until older use drops off.</p>
          )}
        </div>
      </div>
    </Card>
  );
}

/** The parent link: a private page showing this student's week, for whoever they give it to. */
function ParentCard() {
  const tr = useT();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["parent-link"], queryFn: api.parentLink });
  const set = (d: { token: string | null; created_at: string | null }) => qc.setQueryData(["parent-link"], d);
  const make = useMutation({ mutationFn: api.makeParentLink, onSuccess: (d) => { set(d); toast.success("Link ready. Send it to your parent."); } });
  const revoke = useMutation({ mutationFn: api.revokeParentLink, onSuccess: () => { set({ token: null, created_at: null }); toast.success("Link turned off"); } });
  const url = data?.token ? `${window.location.origin}/p/${data.token}` : "";
  return (
    <Card id="parent" className="scroll-mt-20">
      <CardHeader title={tr("Parent link")} icon={<HeartHandshake className="h-4 w-4" />}
        subtitle="A private page for a parent: your study time this week, syllabus progress, tests and weak chapters. Not your notes or doubts." />
      <div className="space-y-3 p-5">
        {url ? (
          <>
            <div className="flex gap-2">
              <Input readOnly value={url} aria-label="Parent link" onFocus={(e) => e.target.select()} className="font-mono text-xs" />
              <Button variant="primary" onClick={() => copyText(url, "Link copied")} icon={<Copy className="h-4 w-4" />}>{tr("Copy")}</Button>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <span className="flex-1">Anyone with this link can see the page, without signing in.</span>
              <Button size="sm" variant="ghost" loading={make.isPending} onClick={() => make.mutate()}>{tr("Make a new link")}</Button>
              <Button size="sm" variant="ghost" loading={revoke.isPending} onClick={() => revoke.mutate()}>{tr("Turn it off")}</Button>
            </div>
          </>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <p className="min-w-0 flex-1 basis-48 text-sm text-fg-soft">Off. Nobody else can see your progress.</p>
            <Button variant="secondary" loading={make.isPending} onClick={() => make.mutate()}>{tr("Create a link")}</Button>
          </div>
        )}
      </div>
    </Card>
  );
}

/** In the app: which Focs server it is showing, and a way to point it at another. */
function ServerCard() {
  return (
    <Card>
      <CardHeader title="Server" icon={<Wifi className="h-4 w-4" />} subtitle="The Focs this app shows. Your account, notes and tests live there." />
      <div className="flex flex-wrap items-center gap-3 p-5">
        <span className="min-w-0 flex-1 basis-48 truncate font-mono text-[13px] text-fg-soft">{window.location.origin}</span>
        <Button variant="secondary" onClick={chooseServer}>Change</Button>
      </div>
    </Card>
  );
}

function DataCard() {
  const tr = useT();
  const navigate = useNavigate();
  const logout = useAuth((s) => s.logout);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ password: "", confirm: "" });
  const exportData = useMutation({
    mutationFn: async () => downloadResponse(await api.exportData(), "focs-my-data.json"),
    onSuccess: () => toast.success("Your data is downloading"),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteAccount(form),
    onSuccess: () => {
      logout();
      navigate("/", { replace: true });
      toast.success("Your account and all its data were deleted.");
    },
  });
  return (
    <Card>
      <CardHeader title={tr("Your data")} icon={<ShieldCheck className="h-4 w-4" />}
        subtitle={tr("Your notes are yours. Take a copy any time, or delete everything.")} />
      <div className="grid gap-3 p-5 sm:grid-cols-2">
        <div className="rounded-xl border border-line bg-bg-soft p-4">
          <div className="text-sm font-medium">Download my data</div>
          <p className="mt-1 text-xs text-muted">Every lecture, board note, revision sheet, flashcard, answer, doubt and mock — one JSON file.</p>
          <Button size="sm" className="mt-3" loading={exportData.isPending} onClick={() => exportData.mutate()} icon={<Download className="h-3.5 w-3.5" />}>{tr("Download")}</Button>
        </div>
        <div className="rounded-xl border border-bad/25 bg-bad/5 p-4">
          <div className="text-sm font-medium">{tr("Delete my account")}</div>
          <p className="mt-1 text-xs text-muted">Permanently removes your account, notes, board snapshots and progress. This can't be undone.</p>
          <Button size="sm" variant="danger" className="mt-3" onClick={() => setOpen(true)} icon={<Trash2 className="h-3.5 w-3.5" />}>{tr("Delete account")}</Button>
        </div>
      </div>
      <Dialog open={open} onClose={() => !remove.isPending && setOpen(false)} title={tr("Delete your account?")}
        subtitle="Everything goes: lectures, notes, snapshots, flashcards, mocks and rooms you host. Download your data first if you want a copy.">
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); remove.mutate(); }}>
          <div><Label>{tr("Your password")}</Label><Input type="password" autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
          <div><Label>Type DELETE to confirm</Label><Input value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} placeholder="DELETE" /></div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>{tr("Keep my account")}</Button>
            <Button type="submit" variant="danger" loading={remove.isPending} disabled={form.confirm !== "DELETE" || !form.password}>Delete everything</Button>
          </div>
        </form>
      </Dialog>
    </Card>
  );
}

/** Settings → Accessibility: kept on this device, applied to every page at once. */
function AccessibilityCard() {
  const tr = useT();
  const a = useA11y();
  const row = (label: string, hint: string, checked: boolean, key: "spacing" | "legible" | "contrast" | "reduceMotion") => (
    <div className="flex items-center gap-3 py-2.5">
      <div className="min-w-0 flex-1"><div className="text-sm font-medium">{label}</div><div className="text-xs text-muted">{hint}</div></div>
      <Switch checked={checked} onChange={(v) => a.set({ [key]: v })} label={label} />
    </div>
  );
  return (
    <Card id="accessibility" className="scroll-mt-20">
      <CardHeader title={tr("Accessibility")} icon={<Accessibility className="h-4 w-4" />} subtitle={tr("Kept on this device. Every page follows it at once.")} />
      <div className="space-y-1 px-5 pb-5">
        <div className="flex flex-wrap items-center gap-3 py-2.5">
          <div className="min-w-0 flex-1 basis-48"><div className="text-sm font-medium">Text size</div><div className="text-xs text-muted">Everything in Focs grows, not just the notes</div></div>
          <Segmented size="sm" value={String(a.textScale)} onChange={(v) => a.set({ textScale: Number(v) })}
            options={[{ value: "1", label: "100%" }, { value: "1.15", label: "115%" }, { value: "1.3", label: "130%" }, { value: "1.5", label: "150%" }]} />
        </div>
        {row("Wider spacing", "More room between lines and letters, easier with dyslexia", a.spacing, "spacing")}
        {row("Legible font", "Atkinson Hyperlegible, made so letters like I, l and 1 never look alike", a.legible, "legible")}
        {row("Stronger contrast", "Darker secondary text and borders, thicker focus outlines", a.contrast, "contrast")}
        {row("Less motion", "No sliding, fading or filling in, whatever the device is set to", a.reduceMotion, "reduceMotion")}
        <div className="flex flex-wrap items-center gap-3 py-2.5">
          <div className="min-w-0 flex-1 basis-48">
            <div className="text-sm font-medium">Read-aloud speed</div>
            <div className="text-xs text-muted">Notes, answers and solutions have a Read aloud button; formulas are read as words</div>
          </div>
          <Segmented size="sm" value={String(a.speechRate)} onChange={(v) => a.set({ speechRate: Number(v) })}
            options={[{ value: "0.8", label: tr("Slow") }, { value: "1", label: tr("Normal") }, { value: "1.2", label: tr("Fast") }, { value: "1.4", label: tr("Faster") }]} />
          <ReadAloud label="Try it" text={String.raw`The range of a projectile is $R = \frac{u^2 \sin 2\theta}{g}$.`} />
        </div>
        <div className="flex justify-end pt-1"><Button size="sm" variant="ghost" onClick={a.reset}>{tr("Reset to default")}</Button></div>
      </div>
    </Card>
  );
}

export default function Settings() {
  const tr = useT();
  const { user, setUser, setAuth } = useAuth();
  const { theme, toggle } = useTheme();
  const qc = useQueryClient();
  const [profile, setProfile] = useState({ full_name: "", exam_target: "jee", class_level: "", daily_goal_min: 60, show_on_leaderboard: true, language: "en" as Language });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const { data: health } = useQuery({ queryKey: ["health-details"], queryFn: api.healthDetails });
  const { data: plans } = useQuery({ queryKey: ["plans"], queryFn: () => api.plans() });

  useEffect(() => {
    if (user) setProfile({ full_name: user.full_name, exam_target: user.exam_target ?? "jee", class_level: user.class_level ?? "",
      daily_goal_min: user.daily_goal_min ?? 60, show_on_leaderboard: user.show_on_leaderboard !== false, language: user.language ?? "en" });
  }, [user]);
  useEffect(() => {
    const id = location.hash.slice(1);
    if (id === "plan" || id === "usage") setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }), 150);
  }, []);

  const save = useMutation({
    mutationFn: () => api.updateMe({ ...profile, exam_target: profile.exam_target as never, class_level: profile.class_level || null }),
    onSuccess: (u) => {
      setUser(u);
      // another exam or branch is another syllabus: everything built on it is fetched again
      // (and Pro's price, which follows what the student prepares for)
      ["overview", "prep-college", "prep-syllabus", "prep-plan", "prep-goal", "mock-meta", "last-day", "weak", "plans"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      toast.success("Profile saved");
    },
  });
  const changePw = useMutation({
    mutationFn: () => api.changePassword(pw),
    onSuccess: (r) => { setAuth(r.access_token, r.user); setPw({ current_password: "", new_password: "" }); toast.success("Password updated. Other devices are signed out."); },
  });
  const buyPro = useMutation({
    mutationFn: async (plan: ProPass["id"]) => pay(await api.buyPro(plan)),
    onSuccess: (r) => { setUser(r.user); qc.invalidateQueries({ queryKey: ["usage"] }); toast.success(`You're on Pro until ${formatDate(r.user.pro_until ?? null)}. Book your first mentor call!`); },
    onError: (e) => { if (!(e instanceof PaymentCancelled)) toast.error(e instanceof Error ? e.message : "The payment didn't go through."); },
  });
  const upgrade = useMutation({ mutationFn: api.devUpgrade, onSuccess: (u) => { setUser(u); qc.invalidateQueries({ queryKey: ["usage"] }); toast.success(`You're on ${u.plan === "free" ? "Starter" : u.plan === "pro" ? "Pro" : "Institute"}`); } });

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title={tr("Settings")} subtitle={tr("Your profile, plan and how Focs works for you.")} />
      <div className="space-y-5">
        <Card>
          <CardHeader title={tr("Profile")} icon={<UserIcon className="h-4 w-4" />} subtitle={tr("Focs tailors notes and questions to your exam.")} />
          <div className="space-y-5 p-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div><Label>{tr("Full name")}</Label><Input aria-label="Full name" value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} /></div>
              {!SUB_EXAMS[examGroup(profile.exam_target)] && (
                <div><Label hint={tr("optional")}>{tr("Class / year")}</Label><Input value={profile.class_level} onChange={(e) => setProfile({ ...profile, class_level: e.target.value })} placeholder="Class 12, Dropper…" /></div>
              )}
            </div>
            <div>
              <Label>{tr("Preparing for")}</Label>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                {EXAMS.filter((ex) => SIGNUP_EXAMS.includes(ex) || examGroup(profile.exam_target) === ex.id).map((ex) => (
                  <button key={ex.id} aria-pressed={examGroup(profile.exam_target) === ex.id}
                    onClick={() => setProfile({ ...profile, exam_target: targetFor(ex.id, profile.exam_target) })}
                    className={cn("rounded-xl border px-3 py-2 text-left text-sm transition", examGroup(profile.exam_target) === ex.id ? "border-accent/60 bg-accent-soft" : "border-line bg-bg-soft hover:border-line-strong")}>
                    <div className="font-medium">{ex.label}</div><div className="text-[11px] leading-snug text-muted">{ex.hint}</div>
                  </button>
                ))}
              </div>
              {SUB_EXAMS[examGroup(profile.exam_target)] && (
                <div className="mt-3">
                  <Label>{SUB_EXAMS[examGroup(profile.exam_target)].label}</Label>
                  <div className="flex flex-wrap gap-2">
                    {SUB_EXAMS[examGroup(profile.exam_target)].options.map((b) => (
                      <button key={b.id} aria-pressed={subExamOf(profile.exam_target) === b.id} onClick={() => setProfile({ ...profile, exam_target: b.id })}
                        className={cn("rounded-xl border px-3 py-2 text-left text-sm transition",
                          subExamOf(profile.exam_target) === b.id ? "border-accent/60 bg-accent-soft" : "border-line bg-bg-soft hover:border-line-strong")}>
                        <div className="font-medium">{b.short}</div><div className="truncate text-[11px] text-muted">{b.name}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div>
              <Label hint={formatMinutes(profile.daily_goal_min)}>{tr("Daily study goal")}</Label>
              <input type="range" min={15} max={480} step={15} value={profile.daily_goal_min} onChange={(e) => setProfile({ ...profile, daily_goal_min: Number(e.target.value) })}
                aria-label="Daily study goal" aria-valuetext={formatMinutes(profile.daily_goal_min)} className="w-full accent-[var(--accent)]" />
            </div>
            <div className="flex flex-col gap-3 rounded-xl border border-line bg-bg-soft p-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-medium">Explain things to me in</div>
                <div className="text-xs text-muted">Doubts, notes, test solutions and your coach. Formulas stay as they are.</div>
              </div>
              <LanguagePicker label="Explain things to me in" value={profile.language} onChange={(v) => setProfile({ ...profile, language: v })} className="h-10 text-sm sm:w-56" />
            </div>
            <div className="flex flex-col gap-3 rounded-xl border border-line bg-bg-soft p-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-medium">Show me on leaderboards</div>
                <div className="text-xs text-muted">Others see your first name and initial with your XP — never your email.</div>
              </div>
              <Switch checked={profile.show_on_leaderboard} onChange={(v) => setProfile({ ...profile, show_on_leaderboard: v })} label="Show me on leaderboards" />
            </div>
            <div className="flex justify-end"><Button variant="primary" loading={save.isPending} onClick={() => save.mutate()}>{tr("Save changes")}</Button></div>
          </div>
        </Card>

        {isCollege(user?.exam_target) && (
          <Card id="college" className="scroll-mt-20">
            <CardHeader title="College, semester and subjects" icon={<GraduationCap className="h-4 w-4" />}
              subtitle="Your Prep Hub, plan, tests and revision follow these subjects. Update them when your semester changes." />
            <div className="p-5"><CollegeSetup onSaved={() => toast.success("Subjects updated")} /></div>
          </Card>
        )}
        <ParentCard />
        {IN_APP && <ServerCard />}
        <UsageCard />

        <Card id="plan" className="scroll-mt-20">
          <CardHeader title={tr("Plan")} icon={<Sparkles className="h-4 w-4" />} subtitle={plans?.payments === "razorpay" ? `Pay with UPI, card or netbanking. Pro runs ${plans.pro_days} days at a time, with no auto-renewal.`
            : plans?.payments === "dev" ? "Dev server: payments use a test button and no money moves." : "Payments aren't set up on this server yet."} />
          <div className="grid grid-cols-1 gap-3 p-4 sm:p-5 md:grid-cols-3">
            {plans?.plans.map((p) => {
              const current = (user?.plan ?? "free") === p.id;
              return (
                <div key={p.id} className={cn("flex min-w-0 flex-col rounded-2xl border p-4", current ? "border-accent/50 bg-accent-soft" : "border-line bg-bg-soft", p.highlight && !current && "ring-gradient")}>
                  <div className="flex items-center justify-between"><span className="font-semibold">{p.name}</span>{current && <Badge tone="accent">Current</Badge>}</div>
                  <div className="mt-2 text-2xl font-semibold">
                    {p.price_inr === null ? "Custom" : `₹${p.price_inr}`}
                    {p.regular_inr ? <s className="ml-2 text-base font-normal text-muted"><span className="sr-only">Regular price </span>₹{p.regular_inr}</s> : null}
                    <span className="text-sm font-normal text-muted">{p.price_inr ? `/${p.period}` : ""}</span>
                  </div>
                  {p.id === "pro" && p.regular_inr && plans.offer && plans.payments && (
                    <p className="mt-1 text-xs font-medium text-accent">Launch offer for the first {plans.offer.places} students · {plans.offer.left} places left</p>
                  )}
                  {p.id === "pro" && !plans.payments && <p className="mt-1 text-xs font-medium text-accent">Coming soon: payments open shortly</p>}
                  {p.id === "pro" && <p className="mt-1 text-xs text-muted">{`Price for ${plans.sectors.find((s) => s.id === plans.sector)?.label ?? ""} students: it follows your exam above.`}</p>}
                  <ul className="mt-3 flex-1 space-y-1.5 text-[13px] text-fg-soft">
                    {p.features.slice(0, 4).map((f) => <li key={f} className="flex gap-2"><Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok" />{f}</li>)}
                  </ul>
                  {current && p.id === "pro" && user?.pro_until && <p className="mt-3 text-xs text-muted">Pro until {formatDate(user.pro_until)}</p>}
                  {p.id === "pro" && plans.payments && user?.plan !== "team" && plans.passes.map((pass) => (
                    <Button key={pass.id} size="sm" className={pass.id === "month" ? "mt-4" : "mt-2"} variant={pass.id === "month" ? "primary" : "secondary"}
                      loading={buyPro.isPending && buyPro.variables === pass.id} disabled={buyPro.isPending} onClick={() => buyPro.mutate(pass.id)}>
                      {`${current ? "Add" : "Get"} ${pass.label} · ₹${pass.price_inr.toLocaleString("en-IN")}`}
                      {pass.regular_inr ? <s className="ml-1.5 opacity-60"><span className="sr-only">Regular price </span>₹{pass.regular_inr.toLocaleString("en-IN")}</s> : null}
                      {!pass.regular_inr && pass.save_pct ? ` (save ${pass.save_pct}%)` : ""}
                    </Button>
                  ))}
                  {!current && plans.dev_upgrade && p.id !== "pro" && (
                    <Button size="sm" className="mt-4" variant={p.highlight ? "primary" : "secondary"} loading={upgrade.isPending && upgrade.variables === p.id} onClick={() => upgrade.mutate(p.id)}>
                      Switch (dev mode)
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <Card>
            <CardHeader title={tr("Password")} icon={<KeyRound className="h-4 w-4" />} />
            <form className="space-y-3 p-5" onSubmit={(e) => { e.preventDefault(); changePw.mutate(); }}>
              <Input type="password" placeholder="Current password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} autoComplete="current-password" />
              <Input type="password" placeholder="New password (8+ characters)" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} autoComplete="new-password" minLength={8} />
              <div className="flex justify-end"><Button type="submit" disabled={!pw.current_password || pw.new_password.length < 8} loading={changePw.isPending}>{tr("Update password")}</Button></div>
            </form>
          </Card>
          <Card>
            <CardHeader title={tr("Appearance")} icon={theme === "dark" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />} />
            <div className="grid grid-cols-2 gap-3 p-5">
              {(["light", "dark"] as const).map((t) => (
                <button key={t} onClick={() => theme !== t && toggle()}
                  className={cn("overflow-hidden rounded-sm border text-left transition", theme === t ? "border-fg ring-1 ring-fg" : "border-line hover:border-line-strong")}>
                  {/* a corner of each look, in its own colours whichever is on: the page, a card, a black (or ivory) button */}
                  <div className={cn("relative h-16 overflow-hidden p-2", t === "dark" ? "bg-[#0e0e0d]" : "bg-[#e9e7e3]")}>
                    <div className={cn("relative ml-2 mt-1 w-24 border p-1.5", t === "dark" ? "border-white/10 bg-[#161615]" : "border-black/10 bg-[#f6f5f2]")}>
                      <div className={cn("h-1.5 w-12", t === "dark" ? "bg-[#f2f0eb]/80" : "bg-[#0d0d0d]/80")} />
                      <div className={cn("mt-1.5 h-2 w-10", t === "dark" ? "bg-[#f2f0eb]" : "bg-[#0d0d0d]")} />
                    </div>
                  </div>
                  <div className="px-3 py-2 text-sm font-medium capitalize">{t} <span className="font-normal normal-case text-muted">· {t === "dark" ? "ink" : "stone"}</span></div>
                </button>
              ))}
            </div>
          </Card>
        </div>

        <AccessibilityCard />

        <DataCard />

        <Card>
          <CardHeader title={tr("System status")} icon={<Cpu className="h-4 w-4" />} subtitle="What this Focs server is running with" />
          <div className="grid gap-3 p-5 sm:grid-cols-2">
            <div className="rounded-xl border border-line bg-bg-soft p-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                {health?.llm.available ? <Wifi className="h-4 w-4 text-ok" /> : <WifiOff className="h-4 w-4 text-warn" />} AI notes & tutor
              </div>
              <p className="mt-1.5 text-[13px] text-muted">
                {health?.llm.available ? <>Connected — notes, quizzes and the doubt solver use AI.</> : <>Offline mode. Add <code className="rounded bg-elev-2 px-1 font-mono text-xs">GROQ_API_KEY</code> to <code className="rounded bg-elev-2 px-1 font-mono text-xs">backend/.env</code> and restart for AI-written notes, summaries and grading.</>}
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
