import { chooseServer, IN_APP } from "@/lib/server";
import { ArrowRight, BadgeCheck, Eye, EyeOff, IndianRupee, Layers, Presentation, ScanText, Target } from "lucide-react";
import { motion } from "motion/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Backdrop } from "@/components/Backdrop";
import { GoogleButton } from "@/components/GoogleButton";
import { Logo } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { LoginCode, TokenResponse } from "@/lib/types";
import { cn, COLLEGES, SIGNUP_EXAMS, examGroup, hasSyllabus, isCollege, SUB_EXAMS, subExamOf, targetFor } from "@/lib/utils";
import { useAuth } from "@/stores/auth";

/** The email inside a Google ID token, only to show whose account is being made (the server checks the token). */
function googleEmail(credential: string): string {
  try {
    const part = credential.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return String(JSON.parse(atob(part)).email ?? "");
  } catch {
    return "";
  }
}

/** Each of the three reasons gets a lit tile: Focs gold, then the AI layer's periwinkle and violet. */
const NOTE_TILE = ["bg-gradient-brand text-brand-fg", "bg-accent text-accent-fg", "bg-accent-lo text-accent-fg"];

/** Why mentor on Focs: the mentor sign-up's side panel. */
const MENTOR_POINTS = [
  [BadgeCheck, "Verified by Focs", "send your qualifications once; students see the badge"],
  [IndianRupee, "Your price", "for private calls and for every master session you post"],
  [Presentation, "Master sessions", "teach many students at once, live on video"],
] as const;

export default function Auth({ mode }: { mode: "login" | "signup" | "mentor-signup" }) {
  const mentor = mode === "mentor-signup";
  const signup = mode === "signup" || mentor;
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const setAuth = useAuth((s) => s.setAuth);
  // a new student who pressed Continue with Google on the sign-in page: their Google sign-in is kept, and only the
  // profile is asked for (no name, email or password, and no second press of Google's button)
  const location = useLocation();
  const pending = signup && !mentor ? (location.state as { google?: string } | null)?.google ?? null : null;
  // no exam chosen at first: with JEE picked in advance, a student who went straight to Continue with Google became a
  // JEE student without ever seeing the choice
  const [form, setForm] = useState({ full_name: "", email: "", password: "", exam_target: "" });
  const [college, setCollege] = useState("");  // B.Tech students: where they study (they pick their semester next)
  const [consent, setConsent] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<LoginCode | null>(null);  // the right password: now the code from their email
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 5 * 60_000 });

  /** Signed in or signed up: into the app, or the goal set-up for a new account. */
  const finish = (res: TokenResponse, isNew: boolean) => {
    const next = params.get("next");
    // a mentor goes to their own dashboard (their application is the first thing there); a new JEE, NEET or B.Tech
    // student goes straight to setting their goal: their plan is the first thing they get
    const isMentor = res.user.role === "mentor";
    const home = isMentor ? "/mentor" : isNew && hasSyllabus(res.user.exam_target) ? "/onboarding" : "/app";
    const dest = next && next.startsWith(isMentor ? "/mentor" : "/app") ? next : home;
    setAuth(res.access_token, res.user, dest); // the guest-only guard redirects there as soon as the token lands
    toast.success(isNew ? `Welcome to Focs, ${res.user.full_name.split(" ")[0]}!` : `Welcome back, ${res.user.full_name.split(" ")[0]}`, { position: "bottom-center" });
    navigate(dest, { replace: true });
  };

  /** Continue with Google: the server checks Google's token. On sign-up the exam and the Terms come along. */
  const withGoogle = async (credential: string) => {
    setError(null);
    setLoading(true);
    try {
      const res = await api.google({ credential, ...(signup ? { accepted_terms: consent, exam_target: form.exam_target,
        ...(isCollege(form.exam_target) && college ? { college } : {}) } : {}) });
      finish(res, !!res.created);
    } catch (err) {
      if (!signup && err instanceof ApiError && err.status === 404) {
        return navigate("/signup", { replace: true, state: { google: credential } });
      }
      if (pending && err instanceof ApiError && err.status === 401) {  // Google's token lasts an hour: sign in again
        toast.error("Your Google sign-in expired. Continue with Google again.");
        return navigate("/signup", { replace: true, state: null });
      }
      setError(err instanceof Error ? err.message : "Google sign-in didn't work. Try again.");
    } finally {
      setLoading(false);
    }
  };
  const googleId = !mentor && !IN_APP ? health?.google_client_id : null;  // the app shell's web view can't show Google's pop-up
  const noExam = signup && !mentor && !form.exam_target;
  const googleReady = !signup || (consent && !noExam);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (noExam) return setError("Pick what you're preparing for: your plan, notes and tests are built for it.");
    if (signup && !consent) return setError("Please tick the box above to accept the Terms and Privacy Policy.");
    if (pending) return withGoogle(pending);
    setError(null);
    setLoading(true);
    try {
      const res = mentor
        ? await api.register({ full_name: form.full_name, email: form.email, password: form.password, accepted_terms: consent, role: "mentor" })
        : signup
          ? await api.register({ ...form, accepted_terms: consent, ...(isCollege(form.exam_target) && college ? { college } : {}) })
          : await api.login({ email: form.email, password: form.password });
      if ("code_required" in res) return setStep(res);
      finish(res, signup);
    } catch (err) {
      if (!signup && err instanceof ApiError && err.status === 409) {
        // the admin ID typed here: the admin panel has its own sign-in
        return navigate("/admin/login", { replace: true, state: { username: form.email } });
      }
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="grid min-h-dvh grid-cols-1 pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] lg:grid-cols-[1fr_1.05fr]">
      <Backdrop scene="auth" />
      <div className="flex min-w-0 flex-col px-5 py-8 sm:px-12">
        <Link to="/" className="inline-flex min-h-10 items-center"><Logo /></Link>
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            {mentor && <div className="eyebrow mb-4">For mentors</div>}
            <h1 className="text-[36px]">{mentor ? "Become a Focs mentor" : step ? "Check your email" : pending ? "One more step" : signup ? "Create your account" : "Welcome back"}</h1>
            <p className="mt-2 text-sm text-muted">
              {step ? <>We sent a 6-digit {signup ? "verification" : "sign-in"} code to <b className="text-fg">{step.sent_to}</b>. {signup
                  ? "It proves this email is yours, and keeps your account safe."
                  : "It keeps your account safe even if someone learns your password."}</>
                : mentor ? "Guide students preparing for an exam you've cleared. Create your mentor account, then send your qualifications for review."
                : pending ? `You're new to Focs, so tell us what you're preparing for${googleEmail(pending) ? ` (${googleEmail(pending)})` : ""}. Your plan, notes and tests are built for it.`
                : signup ? "Free forever for students. Takes 20 seconds." : "Sign in to pick up where you left off. Students and mentors sign in here."}
            </p>

            {step ? <LoginCodeStep step={step} onStep={setStep} onDone={(res) => finish(res, signup)} onBack={() => setStep(null)} /> : <>
            <form onSubmit={submit} className="mt-8 space-y-4">
              {signup && !pending && (
                <div>
                  <Label htmlFor="auth-name">Full name</Label>
                  <Input id="auth-name" value={form.full_name} onChange={set("full_name")} placeholder="Asha Verma" autoComplete="name" required autoFocus />
                </div>
              )}
              {!pending && <><div>
                <Label htmlFor="auth-email">Email</Label>
                <Input id="auth-email" type="email" value={form.email} onChange={set("email")} placeholder="you@example.com" autoComplete="email" required autoFocus={!signup} />
              </div>
              <div>
                <Label hint={signup ? "8+ characters" : health?.email ? <Link to="/forgot-password" className="-my-2 inline-block py-2 text-accent hover:underline">Forgot password?</Link> : undefined} htmlFor="auth-password">Password</Label>
                <div className="relative">
                  <Input id="auth-password" type={showPw ? "text" : "password"} value={form.password} onChange={set("password")} className="pr-11"
                    autoComplete={signup ? "new-password" : "current-password"} minLength={signup ? 8 : undefined} required />
                  <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-1 top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center text-muted hover:text-fg" aria-label={showPw ? "Hide password" : "Show password"} aria-pressed={showPw}>
                    {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div></>}
              {signup && !mentor && (
                <div>
                  <Label>I'm preparing for</Label>
                  <div role="group" aria-label="I'm preparing for" className="grid grid-cols-3 gap-2">
                    {SIGNUP_EXAMS.map((ex) => (
                      <button type="button" key={ex.id} aria-label={`${ex.label}: ${ex.hint}`} aria-pressed={examGroup(form.exam_target) === ex.id}
                        onClick={() => { setForm({ ...form, exam_target: targetFor(ex.id, form.exam_target) }); setError(null); }}
                        className={cn("rounded-xl border px-2 py-2.5 text-left transition",
                          examGroup(form.exam_target) === ex.id
                            ? "border-accent/60 bg-accent-soft shadow-[var(--glow)]"
                            : "border-line bg-elev/50 hover:border-line-strong")}>
                        <div className="text-[13px] font-semibold">{ex.label}</div>
                        <div className="text-[11px] leading-snug text-muted">{ex.hint}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {signup && !mentor && SUB_EXAMS[examGroup(form.exam_target)] && (
                <div className="space-y-3 rounded-xl border border-line bg-bg-soft p-3">
                  <div>
                    <Label>{SUB_EXAMS[examGroup(form.exam_target)].label}</Label>
                    <div className="flex flex-wrap gap-1.5">
                      {SUB_EXAMS[examGroup(form.exam_target)].options.map((b) => (
                        <button type="button" key={b.id} title={b.name} aria-label={b.name} aria-pressed={subExamOf(form.exam_target) === b.id} onClick={() => setForm({ ...form, exam_target: b.id })}
                          className={cn("rounded-lg border px-3 py-1.5 text-[13px] font-semibold transition",
                            subExamOf(form.exam_target) === b.id ? "border-accent/60 bg-accent-soft text-fg" : "border-line bg-elev/50 hover:border-line-strong")}>
                          {b.short}
                        </button>
                      ))}
                    </div>
                  </div>
                  {isCollege(form.exam_target) && <div>
                    <Label hint="optional">Your college</Label>
                    <div className="flex flex-wrap gap-1.5">
                      {COLLEGES.map((c) => (
                        <button type="button" key={c.id} aria-pressed={college === c.id} onClick={() => setCollege(college === c.id ? "" : c.id)}
                          className={cn("rounded-lg border px-3 py-1.5 text-[13px] font-medium transition",
                            college === c.id ? "border-accent/60 bg-accent-soft text-fg" : "border-line bg-elev/50 text-fg-soft hover:border-line-strong")}>
                          {c.name}
                        </button>
                      ))}
                    </div>
                  </div>}
                </div>
              )}
              {signup && (
                <label className="flex cursor-pointer items-start gap-2.5 text-[13px] leading-relaxed text-fg-soft">
                  <input type="checkbox" checked={consent} aria-label={mentor ? "I agree to the Terms and Privacy Policy, and I'm 18 or older" : "I agree to the Terms and Privacy Policy, and I'm 18 or older or my parent or guardian agrees"} onChange={(e) => setConsent(e.target.checked)}
                    className="mt-0.5 h-5 w-5 shrink-0 accent-[var(--accent)]" />
                  <span>
                    I agree to the <Link to="/terms" target="_blank" className="text-accent underline underline-offset-2">Terms</Link> and{" "}
                    <Link to="/privacy" target="_blank" className="text-accent underline underline-offset-2">Privacy Policy</Link>.{" "}
                    {mentor ? "I'm 18 or older, and I'll keep conversations with students on Focs."
                      : "I'm 18 or older, or my parent/guardian agrees too."}
                  </span>
                </label>
              )}
              {error && <div className="rounded-xl border border-bad/25 bg-bad/10 px-3.5 py-2.5 text-sm text-bad">{error}</div>}
              <Button type="submit" variant="primary" size="lg" loading={loading} className="w-full">
                {mentor ? "Create mentor account" : pending ? "Create my account" : signup ? "Create account" : "Sign in"} {!loading && <ArrowRight className="h-4 w-4" />}
              </Button>
            </form>
            {googleId && !pending && (
              <div className="mt-5">
                <div className="mb-4 flex items-center gap-3 text-xs text-muted"><span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" /></div>
                <div className={cn(!googleReady && "pointer-events-none opacity-50")} aria-disabled={!googleReady}>
                  <GoogleButton clientId={googleId} signup={signup} onCredential={withGoogle} />
                </div>
                {!googleReady && <p className="mt-2 text-center text-xs text-muted">
                  {noExam && !consent ? "Pick what you're preparing for and accept the Terms above to continue with Google."
                    : noExam ? "Pick what you're preparing for above to continue with Google."
                      : "Accept the Terms above to continue with Google."}
                </p>}
              </div>
            )}
            </>}
            {IN_APP && (
              <p className="mt-5 text-center text-xs text-muted">
                Connected to <span className="font-mono text-fg-soft">{window.location.host}</span> ·{" "}
                <button type="button" className="text-accent hover:underline" onClick={chooseServer}>change</button>
              </p>
            )}
            <p className="mt-6 text-center text-sm text-muted">
              {signup ? "Already have an account? " : "New to Focs? "}
              <Link to={signup ? "/login" : "/signup"} className="-my-2 inline-block py-2 font-medium text-accent hover:underline">{signup ? "Sign in" : "Create an account"}</Link>
            </p>
            <p className="mt-2 text-center text-sm text-muted">
              {mentor ? <>Preparing for an exam? <Link to="/signup" className="font-medium text-accent underline underline-offset-2">Create a student account</Link></>
                : <>Cleared an exam? <Link to="/mentor/signup" className="-my-2 inline-block py-2 font-medium text-accent hover:underline">Become a mentor</Link></>}
            </p>
          </motion.div>
        </div>
      </div>

      <div className="relative hidden overflow-hidden border-l border-line lg:block">
        <div className="relative flex h-full flex-col justify-center px-14">
          <div className="eyebrow mb-4">{mentor ? "Why mentor on Focs" : "Why students switch"}</div>
          <h2 className="max-w-xl text-[40px] leading-[1.08]">
            {mentor ? <>You cleared it.<br /><span className="font-serif text-[1.14em] font-normal italic tracking-[-0.01em] text-gradient">Now guide someone through it.</span></>
              : <>Stop copying the board.<br /><span className="font-serif text-[1.14em] font-normal italic tracking-[-0.01em] text-gradient">Start understanding it.</span></>}
          </h2>
          <div className="mt-10 max-w-md space-y-3">
            {(mentor ? MENTOR_POINTS : [
              [ScanText, "Reads chalk, marker, pen-tablet & slides", "with FocsOCR, trained for lecture boards"],
              [Target, "Checks you when the topic changes", "one sharp question, right on time"],
              [Layers, "Remembers for you", "spaced-repetition flashcards from every lecture"],
            ] as const).map(([Icon, t, s], i) => {
              const I = Icon as typeof ScanText;
              return (
                <motion.div key={String(t)} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 + i * 0.08 }}
                  className="panel lift flex items-center gap-4 p-4">
                  <div className={cn("grid h-10 w-10 place-items-center rounded-xl shadow-[inset_0_1px_0_rgb(255_255_255/0.4),0_6px_18px_-8px_var(--ai-glow)]", NOTE_TILE[i])}><I className="h-5 w-5" /></div>
                  <div><div className="text-sm font-semibold">{String(t)}</div><div className="text-xs text-muted">{String(s)}</div></div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/** The second step of a password sign-in: the 6-digit code from the account's email. */
function LoginCodeStep({ step, onStep, onDone, onBack }: {
  step: LoginCode; onStep: (s: LoginCode) => void; onDone: (res: TokenResponse) => void; onBack: () => void;
}) {
  const [code, setCode] = useState("");
  const [wait, setWait] = useState(step.resend_after);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait(wait - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  const verify = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      onDone(await api.loginVerify({ challenge: step.challenge, code }));
    } catch (err) {
      setCode("");
      if (err instanceof ApiError && err.status === 401) {  // the sign-in expired: start again
        toast.error(err.message);
        return onBack();
      }
      setError(err instanceof Error ? err.message : "That didn't work. Try again.");
    } finally {
      setBusy(false);
    }
  };
  const resend = async () => {
    setError(null);
    try {
      const next = await api.loginResend(step.challenge);
      onStep(next);
      setWait(next.resend_after);
      toast.success(`A new code is on its way to ${next.sent_to}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't send a new code. Try again.");
    }
  };

  return (
    <form onSubmit={verify} className="mt-8 space-y-4">
      <div>
        <Label>Sign-in code</Label>
        <Input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric"
          autoComplete="one-time-code" placeholder="6 digits" aria-label="Sign-in code" autoFocus required
          className="text-center font-mono text-xl tracking-[0.5em]" />
      </div>
      {error && <div className="rounded-xl border border-bad/25 bg-bad/10 px-3.5 py-2.5 text-sm text-bad">{error}</div>}
      <Button type="submit" variant="primary" size="lg" loading={busy} disabled={code.length !== 6} className="w-full">
        Verify and sign in {!busy && <ArrowRight className="h-4 w-4" />}
      </Button>
      <div className="flex items-center justify-between text-sm">
        <button type="button" onClick={onBack} className="text-muted hover:text-fg">Use another account</button>
        <button type="button" onClick={resend} disabled={wait > 0} className="text-accent hover:underline disabled:text-muted disabled:no-underline">
          {wait > 0 ? `Send a new code in ${wait}s` : "Send a new code"}
        </button>
      </div>
      <p className="text-xs text-muted">Can't find it? Check spam or promotions. The code works for 10 minutes.</p>
    </form>
  );
}
