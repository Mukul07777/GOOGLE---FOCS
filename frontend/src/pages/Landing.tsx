import {
  ArrowDown, ArrowLeft, ArrowRight, ArrowUp, BrainCircuit, Check, GraduationCap, HeartHandshake, Languages, Layers, MessageCircleQuestion, Moon, Plus, Presentation, Radio,
  ScanText, ShieldCheck, Sparkles, Sun, Target, Timer, User, Users, Volume2, Wallet, Zap,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo, LogoMark } from "@/components/common";
import { Button } from "@/components/ui/button";
import { CountUp, useTilt } from "@/components/ui/live";
import { Badge, Segmented } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { PlansInfo, PriceSector, ProPass } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";
import { BRIDGE, BRIDGE_LINE, LANES, SITE } from "@/lib/site";

/* The landing page, laid out like a fashion lookbook: a thin black strip, a centred wordmark header, the name set huge
   with the live demo beneath it, a black band of who it is for, a split banner, a row of promises, and a
   "best of" grid. Monochrome throughout: stone paper, black ink, square edges, wide capitals. */

const EASE = [0.16, 1, 0.3, 1] as const;
const rise = (delay = 0) => ({ initial: { opacity: 0, y: 18 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.9, ease: EASE, delay } });
const reveal = (delay = 0) => ({
  initial: { opacity: 0, y: 16 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: "-60px" }, transition: { duration: 0.8, ease: EASE, delay },
});

const BOARD_LINES = ["Rotational Motion", "τ = r × F", "L = Iω", "τ = dL/dt", "I = Σ mr²  (discrete)"];
/** What FocsOCR reports for each line as it reads it (the demo's confidence read-outs). */
const READ = ["0.99", "0.97", "0.98", "0.96", "0.94"];
const NOTE_BLOCKS = [
  { h: "Key ideas", body: "Torque is the rotational analogue of force; it changes angular momentum." },
  { h: "Formulas", body: "τ = r × F   ·   L = Iω   ·   τ = dL/dt" },
  { h: "Exam tip", body: "If net external torque is zero, L is conserved — skater & diver problems." },
];

/** The live demo: a board being read line by line, notes writing themselves, then a checkpoint. In the hero it sits
    beneath the wordmark, clear of it, so the name always reads whole. */
function LiveDemo() {
  const [step, setStep] = useState(0);
  const tilt = useTilt<HTMLDivElement>(2);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => (s + 1) % 12), 1100);
    return () => clearInterval(t);
  }, []);
  const lines = Math.min(step, BOARD_LINES.length);
  const notes = step >= 6 ? Math.min(step - 5, NOTE_BLOCKS.length) : 0;
  const checkpoint = step >= 9;

  return (
    <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1.1, ease: EASE, delay: 0.25 }}
      className="relative mx-auto max-w-[54rem] text-left">
      <div ref={tilt} className="tilt">
        <div className="panel relative overflow-hidden p-2 sm:p-3">
          <div className="flex items-center gap-2 px-2 pb-3 pt-1">
            {[0, 1, 2].map((i) => <span key={i} className="h-2 w-2 bg-fg/20" />)}
            <div className="caps ml-3 flex items-center gap-2 text-[11px] text-muted"><span className="live-dot" /> Live · Physics — Rotational Motion</div>
            <span className="hud ml-auto hidden text-muted sm:inline-flex">ai layer · on</span>
          </div>
          <div className="grid gap-2 sm:gap-3 md:grid-cols-[1.25fr_1fr]">
            <div className="relative aspect-[16/10] overflow-hidden" style={{ background: "radial-gradient(ellipse at 30% 20%, #2c2c2b, #141414 72%)" }}>
              <div className="scanline" />
              <span aria-hidden className="brackets inset-3 [--ai:#f2f0eb] [animation:lock-on_0.9s_var(--ease-out-expo)_0.6s_both]" />
              <div className="absolute inset-0 p-6 sm:p-8">
                {BOARD_LINES.map((l, i) => (
                  <motion.div key={l} initial={{ opacity: 0 }} animate={{ opacity: i < lines ? 1 : 0 }} transition={{ duration: 0.5 }}
                    className={cn("chalk relative mb-3 w-fit text-lg sm:text-2xl", i === 0 && "mb-5 text-xl underline decoration-white/40 underline-offset-8 sm:text-3xl")}>
                    {l}
                    {i < lines && step > i + 1 && (
                      <motion.span initial={{ opacity: 0, scale: 1.08 }} animate={{ opacity: 1, scale: 1 }}
                        className="absolute -inset-x-2 -inset-y-1 border border-white/55 bg-white/[0.04]">
                        <span className="absolute -right-2 -top-3 bg-[#f2f0eb] px-1 py-px font-mono text-[11px] font-bold not-italic leading-none text-[#0d0d0d]">{READ[i]}</span>
                      </motion.span>
                    )}
                  </motion.div>
                ))}
              </div>
              <div className="absolute bottom-3 left-3 flex gap-2">
                <span className="hud bg-black/60 px-2 py-1.5 text-white/90">focsocr · 0.4 s</span>
                <span className="hud bg-black/60 px-2 py-1.5 text-white/70 [&::before]:hidden">chalkboard</span>
              </div>
            </div>
            <div className="relative flex flex-col gap-2 border border-line bg-bg-soft p-4">
              <div className="mb-1 flex items-center justify-between">
                <div className="caps text-[11px] font-semibold">Notes</div>
                <Badge><Sparkles className="h-3 w-3" /> AI</Badge>
              </div>
              {notes === 0 && <div className="space-y-2 pt-1">{[80, 60, 70].map((w) => <div key={w} className="skeleton h-3" style={{ width: `${w}%` }} />)}</div>}
              <AnimatePresence>
                {NOTE_BLOCKS.slice(0, notes).map((b) => (
                  <motion.div key={b.h} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="border border-line bg-panel p-3">
                    <div className="caps text-[11px] font-medium text-muted">{b.h}</div>
                    <div className="mt-1 text-[13px] leading-relaxed text-fg-soft">{b.body}</div>
                  </motion.div>
                ))}
              </AnimatePresence>
              <AnimatePresence>
                {checkpoint && (
                  <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="band mt-auto p-3">
                    <div className="caps flex items-center gap-2 text-[11px] font-semibold"><Target className="h-3.5 w-3.5" /> Checkpoint — new topic detected</div>
                    <div className="mt-1.5 text-[13px]">If net torque is zero, which quantity is conserved?</div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/** Exams Focs prepares for, gliding past in a ruled strip under the hero (the second copy only closes the loop). */
const EXAMS = ["JEE Main", "JEE Advanced", "NEET UG", "SSC CGL", "CBSE Class 1-12", "B.Tech", "Placements"];

function ExamStrip() {
  return (
    <div className="border-y border-line">
      <div className="mx-auto flex max-w-[1400px] items-center gap-6 px-5 py-4 sm:px-8">
        <span className="caps hidden shrink-0 text-[11px] font-medium text-muted sm:block">Built for</span>
        <div className="marquee min-w-0 flex-1">
          <div className="marquee-track">
            {[0, 1].map((copy) => (
              <div key={copy} aria-hidden={copy === 1 || undefined} className="flex shrink-0 items-center">
                {EXAMS.map((e) => (
                  <span key={e} className="caps flex items-center whitespace-nowrap px-6 text-[12.5px] font-medium text-fg">
                    {e}<span className="ml-12 h-1 w-1 bg-fg/40" />
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const FEATURES = [
  { icon: ScanText, title: "Reads any board", body: "FocsOCR — our own model, trained on chalkboards, whiteboards, pen-tablet and slide lectures, with Greek letters and math symbols built in." },
  { icon: BrainCircuit, title: "Notes that write themselves", body: "Clean, exam-oriented notes with LaTeX formulas — updated as the teacher keeps writing, never duplicated." },
  { icon: Target, title: "Pop quizzes", body: "A quick question every few minutes of lecture — and one whenever the topic changes — right over the video you're watching." },
  { icon: MessageCircleQuestion, title: "Doubt solver", body: "Ask mid-lecture. It knows what's on the board and can answer directly or coach you Socratically." },
  { icon: Timer, title: "Full mock tests", body: "Your exam's real pattern, timing and marking on an exam-style screen — then your score, weak chapters and time use." },
  { icon: Layers, title: "Flashcards that remember", body: "Every lecture becomes spaced-repetition cards, scheduled for exactly when you'd forget." },
  { icon: Users, title: "Study rooms", body: "Watch a YouTube lecture together, race through live MCQs and clear doubts as a group." },
  { icon: Zap, title: "Private & light", body: "Only the board region you select leaves your device, and only when it changes." },
];
/** The tones of the "best of" tiles, in turn: the lookbook's grey photographs, without the photographs. */
const TILES = [
  "bg-elev-2 text-fg",
  "bg-[color-mix(in_oklab,var(--fg)_16%,var(--bg))] text-fg",
  "band",
  "bg-bg-soft text-fg",
];

/* What the pricing section shows until the server's plans arrive (kept in step with backend/app/core/config.py):
   each kind of student's passes at the launch offer, the regular price struck through. */
const pass = (id: ProPass["id"], label: string, days: number, price_inr: number, regular_inr: number, save_pct: number, fair_use_hours: number): ProPass =>
  ({ id, label, days, price_inr, regular_inr, save_pct, fair_use_hours, per_month_inr: Math.round((price_inr / days) * 30) });
const FALLBACK_PASSES: Record<PriceSector, ProPass[]> = {
  exam: [pass("month", "1 month", 30, 249, 359, 0, 95), pass("semester", "6 months", 180, 1449, 1899, 3, 90), pass("year", "1 year", 365, 2849, 3599, 6, 90)],
  college: [pass("month", "1 month", 30, 199, 299, 0, 75), pass("semester", "6 months", 180, 1099, 1599, 8, 70), pass("year", "1 year", 365, 2199, 2999, 9, 70)],
  school: [pass("month", "1 month", 30, 149, 249, 0, 55), pass("semester", "6 months", 180, 799, 1299, 11, 50), pass("year", "1 year", 365, 1599, 2499, 12, 50)],
  ssc: [pass("month", "1 month", 30, 299, 399, 0, 115), pass("semester", "6 months", 180, 1699, 2099, 5, 110), pass("year", "1 year", 365, 3299, 3999, 9, 105)],
};
const FALLBACK_SECTORS: PlansInfo["sectors"] = [
  { id: "exam", label: "JEE / NEET", hint: "Entrance exams" },
  { id: "college", label: "College", hint: "B.Tech & placements" },
  { id: "school", label: "School", hint: "Class 1 to 12 (CBSE)" },
  { id: "ssc", label: "SSC CGL", hint: "Government jobs" },
];
/** "or ₹1,449 for 6 months · ₹2,849 for 1 year": the longer passes, under the monthly price */
const longerPasses = (passes: ProPass[]) =>
  passes.filter((x) => x.id !== "month").map((x) => `₹${x.price_inr.toLocaleString("en-IN")} for ${x.label}`).join(" · ");
type PriceCard = { name: string; price: string; regular?: string; period: string; hot?: boolean; note?: string; features: string[] };
const fallbackCards = (sector: PriceSector): PriceCard[] => {
  const passes = FALLBACK_PASSES[sector];
  const hours = Math.min(...passes.map((x) => x.fair_use_hours ?? 0));
  return [
    { name: "Starter", price: "₹0", period: "forever", features: ["Live board capture & AI notes for 30 minutes of lecture a day (basic notes after it: a lecture never stops)", "Lectures another Focs student already captured: free, outside your allowance", "Lecture captions: 30 minutes a week", "1 full mock test a week (5 more for ₹29)", "Pop quizzes, doubts & flashcards", "Study rooms up to 5 friends"] },
    { name: "Pro", price: `₹${passes[0].price_inr}`, regular: `₹${passes[0].regular_inr}`, period: "/month", hot: true, note: `or ${longerPasses(passes)}`, features: [`AI notes for up to 7 hours of lecture a day, however much the teacher writes (fair use: about ${hours} hours every 30 days)`, "6× Starter's daily AI for doubts, quizzes and practice", "Lectures another Focs student already captured: free, outside your allowance", "Lecture captions: 3 hours a week", "Unlimited full mock tests with full analysis", "AI practice sets & subjective answer grading", "Doubt solver with Socratic mode", "Study rooms up to 50"] },
    { name: "Institute", price: "Custom", period: "", features: ["Everything in Pro, no usage caps", "Batch analytics for teachers", "Custom exam patterns", "SSO & admin controls"] },
  ];
};

const FAQ = [
  ["Which lectures does it work with?", "Anything you can play in a browser tab — YouTube, Physics Wallah, Unacademy, college recordings, Zoom/Meet in the browser. For offline classes, snap a photo of the board."],
  ["Is it free?", "Yes. Starter is free for good: live board notes for half an hour of lecture a day, doubts, quizzes, flashcards and a full mock test a week (5 more for ₹29). Pro is {pro} a month{longer} for {kind} students{offer}, for up to 7 hours of lecture notes a day, 6× the AI for doubts and practice, more caption time and unlimited mock tests. A lecture another Focs student already captured is free on both. Nothing renews by itself: you pay only when you choose to."],
  ["Does it work on my phone?", "Board photos and classroom mode (the phone's camera on a real board) work on any phone. Following a lecture you watch online needs a laptop or desktop browser such as Chrome or Edge, because phones can't share a tab."],
  ["Is my screen recorded?", "No video is stored. Focs samples a frame every few seconds, only from the tab and region you choose, and skips frames where the board hasn't changed."],
  ["What makes the OCR different?", "Generic OCR is trained on documents. FocsOCR is trained on lecture boards — chalk grain, marker glare, dark pen-tablet canvases, compressed video — and it knows symbols like θ, Σ, ∫, √ and subscripts."],
];

/** FocsOCR in four numbers, each with where it comes from (ml/README.md: the training run and the charset). */
const STATS = [
  { n: 1.7, decimals: 1, suffix: "M+", label: "board lines read in training", source: "FocsOCR training run" },
  { n: 6, label: "board styles, from chalk to pen-tablet", source: "FocsOCR training data" },
  { n: 191, label: "symbols, Greek and maths included", source: "FocsOCR character set" },
  { n: 0, label: "frames sent while the board is idle", source: "Focs capture" },
];

/** The row of promises under the banner ("fast delivery, easy returns…"), each one something Focs already does. */
const PROMISES = [
  { icon: Radio, title: "Live notes", body: "Within seconds of the board" },
  { icon: Languages, title: "Your language", body: "Hindi, Hinglish or English" },
  { icon: ShieldCheck, title: "Private by design", body: "Only the board leaves your device" },
  BRIDGE ? { icon: Volume2, title: "Read aloud", body: "Formulas said as words" } : { icon: Wallet, title: "Free for students", body: "No card. No install." },
];

/* ---------------------------------------------------------------- the two sides and the bridge */
const SIDES = [
  {
    where: "At the board", title: "The teacher", icon: Presentation, tile: "bg-fg text-bg",
    lines: ["Writes on the board and talks over it", "Moves at the syllabus's speed, not the class's", "Teaches in one language", "Can't see who got lost at minute 12"],
  },
  {
    where: "At the desk", title: "The student", icon: GraduationCap, tile: "border border-fg text-fg",
    lines: ["Needs the lecture at their own pace", "Thinks best in their own language", "Reads in their own way: by ear, by eye or both", "Won't raise a hand in a class of 200"],
  },
];

/** The one line, with "the confusion back" underlined: the half of the bridge nobody else builds. */
function BridgeLine() {
  const key = "the confusion back";
  const at = BRIDGE_LINE.indexOf(key);
  if (at < 0) return <>{BRIDGE_LINE}</>;
  return <>{BRIDGE_LINE.slice(0, at)}<span className="underline decoration-[0.06em] underline-offset-[0.16em]">{key}</span>{BRIDGE_LINE.slice(at + key.length)}</>;
}

function SideCard({ side }: { side: (typeof SIDES)[number] }) {
  const Icon = side.icon;
  return (
    <div className="panel lift p-6 text-left">
      <div className="caps text-[11px] font-medium text-muted">{side.where}</div>
      <h3 className="mt-3 flex items-center gap-3 text-xl uppercase tracking-[0.04em]">
        <span className={cn("grid h-9 w-9 shrink-0 place-items-center", side.tile)}><Icon className="h-4 w-4" /></span>
        {side.title}
      </h3>
      <ul className="mt-5 space-y-2.5 text-[14.5px] leading-snug text-fg-soft">
        {side.lines.map((l) => (
          <li key={l} className="flex gap-2.5"><span className="mt-[0.55em] h-1 w-1 shrink-0 bg-fg" />{l}</li>
        ))}
      </ul>
    </div>
  );
}

/** Between the two sides: the four lanes, three carrying the lecture to the student and one carrying confusion back.
    Pointing at a lane picks out it and its card below. */
function Lanes({ on, setOn }: { on: string | null; setOn: (k: string | null) => void }) {
  return (
    <div className="relative flex flex-col items-center gap-3 py-2 lg:gap-2.5 lg:py-0">
      <span aria-hidden className="lane-down absolute inset-y-0 left-1/2 w-px -translate-x-1/2 lg:hidden" />
      <div className="relative z-10 mb-2 flex flex-col items-center px-3 py-1 max-lg:bg-bg">
        <LogoMark className="h-10 w-10" />
        <span className="hud mt-3 text-fg">bridge · live</span>
      </div>
      {LANES.map((l) => (
        <div key={l.key} className={cn("lane relative flex w-full items-center justify-center", l.toTeacher && "lane-back")}
          data-on={on === l.key || undefined} onMouseEnter={() => setOn(l.key)} onMouseLeave={() => setOn(null)}>
          <span aria-hidden className="lane-line hidden lg:block" />
          <span className="sticker relative z-10 cursor-default text-fg">
            {l.toTeacher ? <><ArrowUp className="h-3.5 w-3.5 lg:hidden" /><ArrowLeft className="hidden h-3.5 w-3.5 lg:block" /></>
              : <><ArrowDown className="h-3.5 w-3.5 lg:hidden" /><ArrowRight className="hidden h-3.5 w-3.5 lg:block" /></>}
            <span>{l.title}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

function TwoSides() {
  const [on, setOn] = useState<string | null>(null);
  return (
    <div id="lanes" className="mx-auto max-w-6xl scroll-mt-28 px-5 sm:px-8">
      <div className="grid items-center gap-6 lg:grid-cols-[1fr_minmax(240px,0.8fr)_1fr] lg:gap-0">
        <SideCard side={SIDES[0]} />
        <Lanes on={on} setOn={setOn} />
        <SideCard side={SIDES[1]} />
      </div>
      <div className="mt-10 grid gap-px border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
        {LANES.map((l) => (
          <div key={l.key} className={cn("bg-bg p-6 text-left transition-colors", on === l.key && "bg-panel")}
            onMouseEnter={() => setOn(l.key)} onMouseLeave={() => setOn(null)}>
            <div className="caps text-[11px] font-medium text-muted">{l.toTeacher ? "← to the teacher" : "→ to the student"}</div>
            <h3 className="mt-3 flex flex-wrap items-center gap-2 text-[15px] font-semibold uppercase tracking-[0.08em]">{l.title}{!l.ready && <Badge>being built</Badge>}</h3>
            <p className="mt-2 text-[13.5px] leading-relaxed text-muted">{l.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

const LEDE = "A lecture moves at the teacher's speed, in the teacher's language. Focs carries the board to the student, at their pace and in their language, and carries the student's confusion back to the teacher, pinned to the exact board.";
const HERO_LEDE = "Focs watches the board with you. It reads it with its own OCR model, writes exam-ready notes, quizzes you the moment the topic changes, and turns every lecture into flashcards that remember what you forget.";

/* ---------------------------------------------------------------- header */
const SECTIONS = BRIDGE
  ? [{ id: "bridge", label: "The bridge" }, { id: "features", label: "Features" }, { id: "how", label: "How it works" }, { id: "faq", label: "FAQ" }]
  : [{ id: "top", label: "Home" }, { id: "bridge", label: "The bridge" }, { id: "features", label: "Features" }, { id: "how", label: "How it works" }, { id: "pricing", label: "Pricing" }];

/** The thin black strip above everything ("FREE DELIVERY ON ORDERS…"). */
function TopStrip() {
  const { theme, toggle } = useTheme();
  return (
    <div className="band">
      <div className="caps mx-auto flex h-9 max-w-[1400px] items-center justify-center gap-4 px-4 text-[11px] font-medium sm:justify-between sm:px-8">
        {/* phones: centred on its own (the links are hidden); tablets and up: on the left, the links on the right */}
        <span className="min-w-0 truncate text-center sm:text-left">{BRIDGE ? "The lecture to the student · the confusion back to the teacher" : "Focs — Focus on Cognitive Studies"}</span>
        <nav className="hidden items-center gap-3 sm:flex">
          <Link to="/privacy" className="inline-flex h-9 items-center hover:opacity-70">Privacy</Link>
          <span aria-hidden className="text-band-muted">|</span>
          <Link to="/terms" className="inline-flex h-9 items-center hover:opacity-70">Terms</Link>
          <span aria-hidden className="text-band-muted">|</span>
          <button onClick={toggle} className="caps -my-2 px-2 py-2.5 hover:opacity-70">{theme === "dark" ? "Stone" : "Ink"}</button>
        </nav>
      </div>
    </div>
  );
}

/** The wordmark in the middle, the sections on the left (the one being read underlined), sign-in and the call to
    action on the right, and a rule of ink along its foot showing how far down the page you are. Owns its scroll
    listener, so scrolling re-renders only the header. */
function LandingHeader({ cta }: { cta: string }) {
  const token = useAuth((s) => s.token);
  const { theme, toggle } = useTheme();
  const [active, setActive] = useState(SECTIONS[0].id);
  const ink = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let frame = 0;
    const read = () => {
      frame = 0;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      if (ink.current) ink.current.style.transform = `scaleX(${max > 0 ? Math.min(1, window.scrollY / max) : 0})`;
      let current = SECTIONS[0].id;
      for (const s of SECTIONS) {
        const el = document.getElementById(s.id);
        if (el && el.getBoundingClientRect().top <= 160) current = s.id;
      }
      setActive(current);
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(read); };
    read();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <header className="glass-bar sticky top-[env(safe-area-inset-top)] z-40 border-b border-line">
      {/* phones and tablets: the logo on the left, the actions on the right; wide screens: the sections, the logo
          centred, the actions */}
      <div className="relative mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-3 px-4 sm:px-8 lg:grid lg:grid-cols-[1fr_auto_1fr] lg:gap-4">
        <div ref={ink} aria-hidden className="scroll-ink !top-auto bottom-[-1px]" style={{ transform: "scaleX(0)" }} />
        <nav aria-label="Sections" className="hidden items-center gap-7 lg:flex">
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`} aria-current={active === s.id ? "true" : undefined}
              className={cn("nav-chip", active === s.id && "nav-chip-on")}>{s.label}</a>
          ))}
        </nav>
        <a href="#top" aria-label="Focs, back to the top" className="inline-flex min-h-10 shrink-0 items-center lg:col-start-2 lg:justify-self-center"><Logo /></a>
        <div className="flex items-center justify-end gap-1 sm:gap-2">
          <Button variant="ghost" size="icon-sm" onClick={toggle} aria-label={theme === "dark" ? "Switch to Stone (light)" : "Switch to Ink (dark)"}
            title={theme === "dark" ? "Stone" : "Ink"}>
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          {!token && (
            <Link to="/login" aria-label="Sign in" className="caps inline-flex h-10 min-w-10 items-center justify-center gap-1.5 px-2 text-[11px] font-medium text-fg hover:opacity-70">
              <User className="h-4 w-4" /> <span className="hidden sm:inline">Sign in</span>
            </Link>
          )}
          <Link to={cta}><Button variant="primary" size="sm">{token ? "Open app" : "Get started"}</Button></Link>
        </div>
      </div>
    </header>
  );
}

/** A section's opening, rising into view as it is reached. */
function SectionHead({ id, eyebrow, title, children, center, action }: {
  id?: string; eyebrow: string; title: ReactNode; children?: ReactNode; center?: boolean; action?: ReactNode;
}) {
  return (
    <motion.div id={id} {...reveal()} className={cn("scroll-mt-28", center ? "mx-auto max-w-3xl text-center" : "flex flex-wrap items-end justify-between gap-6")}>
      <div className={cn(!center && "max-w-3xl")}>
        <div className="eyebrow">{eyebrow}</div>
        <h2 className="display-caps mt-6 text-[34px] sm:text-[48px]">{title}</h2>
        {children && <p className={cn("mt-5 max-w-2xl text-base leading-relaxed text-fg-soft", center && "mx-auto")}>{children}</p>}
      </div>
      {action}
    </motion.div>
  );
}

/* ---------------------------------------------------------------- hero */
function Hero({ cta }: { cta: string }) {
  return (
    <section className="relative isolate overflow-hidden">
      <div className="mx-auto max-w-[1400px] px-5 pt-10 sm:px-8 sm:pt-14">
        <div className="flex items-start justify-between gap-8">
          <motion.div {...rise()} className="max-w-[21rem]">
            <h1 className="caps text-[12.5px] font-medium leading-[2] tracking-[0.3em] text-fg">
              {BRIDGE ? BRIDGE_LINE : "Every lecture, understood."}
            </h1>
            <span aria-hidden className="mt-3 block h-px w-10 bg-fg" />
            <p className="mt-6 text-[14px] leading-relaxed text-fg-soft">{BRIDGE ? LEDE : HERO_LEDE}</p>
          </motion.div>
          <motion.div {...rise(0.1)} className="hidden shrink-0 text-right sm:block">
            <div className="caps text-[11px] font-medium leading-[2] tracking-[0.3em] text-fg">New<br />FocsOCR<br />Real boards</div>
            <span aria-hidden className="ml-auto mt-3 block h-px w-10 bg-fg" />
          </motion.div>
        </div>

        {/* the name set huge and whole, nothing laid over it */}
        <motion.div aria-hidden {...rise(0.05)}
          className="mt-10 select-none text-center font-display text-[31vw] font-medium uppercase leading-[0.8] tracking-[-0.035em] text-fg sm:mt-8 lg:text-[min(27vw,390px)]">
          Focs
        </motion.div>

        <div className="flex flex-col gap-6 pt-10 sm:flex-row sm:items-end sm:justify-between sm:pt-12">
          <motion.div {...rise(0.2)} className="flex flex-wrap items-center gap-6">
            <Link to={cta}><Button variant="primary" size="lg">{BRIDGE ? "Try it on a lecture" : "Start free"}</Button></Link>
            <a href="#how" className="link-line inline-flex min-h-11 items-center">See how it works</a>
          </motion.div>
          <motion.div {...rise(0.25)} className="max-w-[16rem] sm:text-right">
            <div className="caps text-[11px] font-medium leading-[2] tracking-[0.26em] text-fg">Notes · Quizzes · Flashcards</div>
            <span aria-hidden className="mt-3 block h-px w-10 bg-fg sm:ml-auto" />
          </motion.div>
        </div>

        {/* the demo beneath the name, the way the look follows the title in a lookbook */}
        <div className="pb-14 pt-12 sm:pt-14">
          <LiveDemo />
        </div>
      </div>
      <ExamStrip />
    </section>
  );
}

/* ---------------------------------------------------------------- who it is for (the black band) */
function Audiences({ cta }: { cta: string }) {
  const rows = [
    { icon: GraduationCap, title: "Students", body: "Notes at your own pace, in Hindi, Hinglish or English.", link: "Start learning", to: cta },
    { icon: Presentation, title: "Teachers", body: "See who got lost, and on which board, while you teach.", link: "See the bridge", href: "#bridge" },
    { icon: Users, title: "Seniors", body: "Answer juniors' questions and check Focs's drafts.", link: "See features", href: "#features" },
    { icon: HeartHandshake, title: "Mentors", body: "Cleared the exam? Guide students at your own price, one to one or in master sessions.", link: "Become a mentor", to: "/mentor/signup" },
  ];
  return (
    <section className="band">
      <div className="mx-auto grid max-w-[1400px] gap-10 px-5 py-14 sm:px-8 md:grid-cols-2 md:gap-8 xl:grid-cols-4">
        {rows.map(({ icon: Icon, title, body, link, to, href }, i) => (
          <motion.div key={title} {...reveal(i * 0.06)} className="flex items-center gap-6">
            <div aria-hidden className="band-tile grid h-[120px] w-[92px] shrink-0 place-items-center">
              <Icon className="h-8 w-8" strokeWidth={1.3} />
            </div>
            <div>
              <h3 className="text-[15px] font-medium uppercase tracking-[0.14em]">{title}</h3>
              <p className="mt-2.5 max-w-[15rem] text-[13px] leading-relaxed text-band-muted">{body}</p>
              {to
                ? <Link to={to} className="link-line mt-2 inline-flex min-h-11 items-center gap-1">{link} <ArrowRight className="h-3.5 w-3.5" /></Link>
                : <a href={href} className="link-line mt-2 inline-flex min-h-11 items-center gap-1">{link} <ArrowRight className="h-3.5 w-3.5" /></a>}
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- the gap (the split banner) */
function BridgeBanner() {
  return (
    <section id="bridge" className="scroll-mt-16 bg-elev-2">
      <div className="grid items-stretch lg:grid-cols-2">
        <motion.div {...reveal()} className="w-full px-5 py-16 sm:px-8 lg:ml-auto lg:max-w-[700px] lg:py-24 lg:pr-14">
          <div className="eyebrow">The gap</div>
          <h2 className="display-caps mt-7 text-[32px] leading-[1.02] sm:text-[44px]"><BridgeLine /></h2>
          <p className="mt-6 max-w-xl text-[15px] leading-relaxed text-fg-soft">{LEDE}</p>
          <a href="#lanes" className="mt-9 inline-block"><Button variant="primary" size="lg">Explore the bridge</Button></a>
        </motion.div>
        {/* the board, where a lecture lost the room: a chalk photograph in all but name */}
        <motion.div {...reveal(0.1)} aria-hidden className="relative min-h-[360px] overflow-hidden lg:min-h-[520px]"
          style={{ background: "radial-gradient(ellipse at 35% 25%, #343433, #121212 75%)" }}>
          <div className="absolute inset-0 p-8 sm:p-14">
            <div className="chalk mb-8 w-fit text-2xl underline decoration-white/40 underline-offset-8 sm:text-3xl">Work and energy</div>
            <div className="chalk mb-5 text-xl sm:text-2xl">W = F s cos θ</div>
            <div className="relative mb-5 w-fit">
              <div className="chalk text-xl sm:text-2xl">K = ½ m v²</div>
              <span className="absolute -inset-x-3 -inset-y-1.5 border border-white/60" />
              <span className="caps absolute -right-6 top-1/2 -translate-y-1/2 translate-x-full whitespace-nowrap bg-[#f2f0eb] px-2 py-1 text-[11px] font-semibold text-[#0d0d0d]">
                ← 5 lost here
              </span>
            </div>
            <div className="chalk text-xl sm:text-2xl">W = ΔK</div>
          </div>
          <div className="absolute bottom-6 left-6 flex gap-2">
            <span className="hud bg-black/60 px-2 py-1.5 text-white/90">return lane · live</span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function Promises() {
  return (
    <section className="border-b border-line">
      <div className="mx-auto grid max-w-[1400px] grid-cols-2 gap-x-6 gap-y-8 px-5 py-12 sm:px-8 lg:grid-cols-4">
        {PROMISES.map(({ icon: Icon, title, body }) => (
          <div key={title} className="flex items-center gap-4">
            <Icon className="h-7 w-7 shrink-0" strokeWidth={1.2} />
            <div>
              <div className="font-display text-[12px] font-semibold uppercase tracking-[0.12em]">{title}</div>
              <div className="mt-1 text-[12.5px] text-muted">{body}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- page */
const INSTITUTE_MAIL = `mailto:${SITE.supportEmail}?subject=${encodeURIComponent("Focs for our institute")}`;

export default function Landing() {
  const token = useAuth((s) => s.token);
  const [open, setOpen] = useState<number | null>(0);
  const cta = token ? "/app" : "/signup";
  // prices come from the server (one place to change them); fetched quietly, so a slow API never shows a visitor an error.
  // Each kind of student has its own; a signed-in student first sees theirs (the server picks it while sector is null).
  const [sector, setSector] = useState<PriceSector | null>(null);
  const [live, setLive] = useState<Partial<Record<PriceSector, PlansInfo>>>({});
  useEffect(() => {
    if (sector && live[sector]) return;
    api.plans(sector ?? undefined).then((d) => { setLive((m) => ({ ...m, [d.sector]: d })); setSector((s) => s ?? d.sector); }).catch(() => undefined);
  }, [sector]); // eslint-disable-line react-hooks/exhaustive-deps
  const shown: PriceSector = sector ?? "exam";
  const data = live[shown];
  const sectors = data?.sectors ?? FALLBACK_SECTORS;
  const offer = data ? data.offer : null;
  const passes = data?.passes ?? FALLBACK_PASSES[shown];
  const pro = passes.find((x) => x.id === "month") ?? passes[0];
  const longer = longerPasses(passes);
  const soon = !!data && !data.payments;  // nothing can be bought yet: no offer counter, no "places left"
  const cards: PriceCard[] = data ? data.plans.map((p) => ({
    name: p.name, hot: !!p.highlight, features: p.features,
    price: p.price_inr === null ? "Custom" : `₹${p.price_inr}`, period: p.price_inr === null ? "" : p.price_inr ? `/${p.period}` : p.period,
    regular: p.regular_inr ? `₹${p.regular_inr}` : undefined,
    note: p.id === "pro" ? (soon ? "Coming soon: payments open shortly" : longer ? `or ${longer}` : undefined) : undefined,
  })) : fallbackCards(shown);
  const kind = shown === "exam" ? "JEE / NEET" : shown === "ssc" ? "SSC CGL" : shown;
  const offerNote = pro?.regular_inr ? ` (a launch offer for the first ${offer?.places ?? 200} students; then ₹${pro.regular_inr})` : "";
  const faq = FAQ.map(([q, a]) => [q, a.replace("{pro}", `₹${pro?.price_inr ?? ""}`).replace("{longer}", longer ? ` (or ${longer})` : "")
    .replace("{kind}", kind).replace("{offer}", offerNote)]);
  useEffect(() => {
    // The page is lazy-loaded, so the browser's own jump to #section happens before it exists.
    if (location.hash) setTimeout(() => document.querySelector(location.hash)?.scrollIntoView({ behavior: "smooth" }), 150);
  }, []);

  return (
    <div id="top" className="relative min-h-dvh overflow-x-clip pt-[env(safe-area-inset-top)]">
      {/* a phone's notch / status bar: a solid strip so the page doesn't scroll visibly behind it */}
      <div aria-hidden className="fixed inset-x-0 top-0 z-50 h-[env(safe-area-inset-top)] bg-bg" />
      <TopStrip />
      <LandingHeader cta={cta} />

      <Hero cta={cta} />
      <Audiences cta={cta} />
      <BridgeBanner />
      <Promises />

      <section className="mt-24">
        <TwoSides />
      </section>

      <section className="mx-auto mt-28 max-w-[1400px] px-5 sm:px-8">
        <div className="grid grid-cols-2 border-y border-line md:grid-cols-4">
          {STATS.map((s, i) => (
            <div key={s.label} className={cn("flex flex-col px-5 py-8 sm:px-7", i > 0 && "md:border-l md:border-line", i % 2 === 1 && "border-l border-line md:border-l")}>
              <div className="figure text-[44px] sm:text-[58px]"><CountUp value={s.n} decimals={s.decimals} />{s.suffix}</div>
              <div className="mt-3 text-sm leading-snug text-fg-soft">{s.label}</div>
              <div className="caps mt-auto pt-5 text-[11px] font-medium text-muted">{s.source}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto mt-28 max-w-[1400px] px-5 sm:px-8">
        <SectionHead id="features" eyebrow="Features" title="Best of Focs" action={<a href="#how" className="link-line">How it works</a>} />
        <div className="mt-12 grid gap-x-5 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(({ icon: Icon, title, body }, i) => (
            <motion.div key={title} {...reveal((i % 4) * 0.05)} className="group">
              <div className={cn("relative grid aspect-[16/7] place-items-center overflow-hidden sm:aspect-[4/5] transition-transform duration-500", TILES[i % TILES.length])}>
                <span className="caps absolute left-4 top-4 text-[11px] font-medium opacity-70">0{i + 1}</span>
                <Icon className="h-12 w-12 transition-transform duration-500 group-hover:scale-110" strokeWidth={1.1} />
              </div>
              <h3 className="mt-4 text-[13px] font-semibold uppercase tracking-[0.12em]">{title}</h3>
              <p className="mt-2 text-[13.5px] leading-relaxed text-muted">{body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="mx-auto mt-28 max-w-[1400px] px-5 sm:px-8">
        <SectionHead id="how" eyebrow="How it works" title="Three clicks to your smartest lecture yet" />
        <div className="mt-12 grid grid-cols-1 gap-10 md:grid-cols-3 md:gap-8">
          {[
            ["Share the lecture tab", "Pick the browser tab with your lecture. Drag a box around the board so Focs ignores faces and player controls."],
            ["Just watch", "Focs samples the board, reads it with FocsOCR and keeps the notes in sync. Ask doubts any time; answer checkpoints when the topic shifts."],
            ["Revise in minutes", "End the lecture to get a revision sheet, formula list and flashcards — then a practice set built from exactly what you studied."],
          ].map(([t, b], i) => (
            <motion.div key={t} {...reveal(i * 0.08)} className="border-t border-fg pt-6">
              <div className="figure text-[44px]">0{i + 1}</div>
              <h3 className="mt-5 text-[14px] font-semibold uppercase tracking-[0.1em]">{t}</h3>
              <p className="mt-2.5 text-sm leading-relaxed text-muted">{b}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {!BRIDGE && <section className="mx-auto mt-28 max-w-[1400px] px-5 sm:px-8">
        <SectionHead id="pricing" eyebrow="Pricing" title="Priced for students, not enterprises" />
        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <Segmented value={shown} onChange={(v) => setSector(v)} options={sectors.map((s) => ({ value: s.id, label: s.label }))} />
            <span className="text-sm text-muted">{sectors.find((s) => s.id === shown)?.hint}</span>
          </div>
          {pro?.regular_inr && !soon ? (
            <p className="text-sm font-medium">
              Launch offer for the first {offer?.places ?? 200} students, shared across all courses
              {offer ? ` · ${offer.left === offer.places ? "every place still open" : `${offer.left} places left`}` : ""}
            </p>
          ) : null}
        </div>
        <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-3">
          {cards.map((p) => (
            <div key={p.name} className={cn("relative flex flex-col border p-7", p.hot ? "band border-transparent" : "border-line-strong bg-panel")}>
              {p.hot && <span className="caps absolute right-6 top-6 border border-current px-2 py-1 text-[11px] font-semibold">Most popular</span>}
              <div className={cn("caps text-[11px] font-medium", p.hot ? "text-band-muted" : "text-muted")}>{p.name}</div>
              <div className="mt-5 flex items-baseline gap-1.5">
                <span className="figure text-[48px]">{p.price}</span>
                {p.regular && <s className={cn("text-xl", p.hot ? "text-band-muted" : "text-muted")}><span className="sr-only">Regular price </span>{p.regular}</s>}
                <span className={cn("text-sm", p.hot ? "text-band-muted" : "text-muted")}>{p.period}</span>
              </div>
              {p.note && <div className={cn("mt-1 text-sm", p.hot ? "text-band-muted" : "text-muted")}>{p.note}</div>}
              <ul className="mt-6 flex-1 space-y-2.5 text-sm">
                {p.features.map((f) => (
                  <li key={f} className={cn("flex gap-2.5", p.hot ? "text-band-fg" : "text-fg-soft")}><Check className="mt-0.5 h-4 w-4 shrink-0" />{f}</li>
                ))}
              </ul>
              {p.name === "Institute" ? (
                <a href={INSTITUTE_MAIL} className="mt-8">
                  <Button variant="secondary" className="w-full">Talk to us</Button>
                  <span className="mt-2 block text-center text-xs text-muted">{SITE.supportEmail}</span>
                </a>
              ) : (
                <Link to={cta} className="mt-8">
                  <Button variant={p.hot ? "primary" : "secondary"} className={cn("w-full", p.hot && "border-band-fg bg-band-fg text-band hover:border-band-fg hover:bg-band-fg hover:opacity-85")}>
                    Get started
                  </Button>
                </Link>
              )}
            </div>
          ))}
        </div>
      </section>}

      <section className="mx-auto mt-28 max-w-3xl px-5 sm:px-8">
        <SectionHead id="faq" eyebrow="FAQ" title="Questions" center />
        <div className="mt-12 border-t border-fg">
          {faq.map(([q, a], i) => (
            <div key={q} className="border-b border-line">
              <button onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}
                className="flex w-full items-center justify-between gap-4 py-5 text-left text-[15px] font-medium transition hover:opacity-75">
                {q}
                <Plus className={cn("h-5 w-5 shrink-0 transition-transform duration-300", open === i && "rotate-45")} strokeWidth={1.5} />
              </button>
              <AnimatePresence initial={false}>
                {open === i && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <p className="pb-6 pr-10 text-sm leading-relaxed text-muted">{a}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </section>

      <section className="band mt-28">
        <div className="mx-auto max-w-[1400px] px-5 py-20 text-center sm:px-8 sm:py-24">
          <div className="caps text-[11px] font-medium text-band-muted">Free forever for students</div>
          <h2 className="display-caps mx-auto mt-6 max-w-4xl text-[40px] sm:text-[72px]">Your next lecture starts in 30 seconds.</h2>
          <p className="mx-auto mt-6 max-w-xl text-band-muted">No card. No install.</p>
          <Link to={cta} className="mt-10 inline-block">
            <Button variant="primary" size="lg" className="border-band-fg bg-band-fg text-band hover:border-band-fg hover:bg-band-fg hover:opacity-85">Create your account</Button>
          </Link>
        </div>
      </section>

      <footer className="mx-auto flex max-w-[1400px] flex-col items-center justify-between gap-5 px-5 py-10 text-sm text-muted sm:flex-row sm:px-8">
        <Logo className="text-fg" />
        <div className="caps flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[11px] font-medium">
          <a href={`mailto:${SITE.supportEmail}`} className="inline-flex min-h-11 items-center hover:text-fg">Contact {SITE.supportEmail}</a>
          <Link to="/mentor/signup" className="inline-flex min-h-11 items-center hover:text-fg">Become a mentor</Link>
          <Link to="/privacy" className="inline-flex min-h-11 items-center hover:text-fg">Privacy</Link>
          <Link to="/terms" className="inline-flex min-h-11 items-center hover:text-fg">Terms</Link>
          <span>© {new Date().getFullYear()} Focs. Made for India's students.</span>
        </div>
      </footer>
    </div>
  );
}
