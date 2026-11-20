import { ArrowLeft, ArrowRight, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";

/** One stop on the tour: the control it points at (a data-tour value) and what it says. No target: a card in the middle. */
export interface TourStep { target?: string; title: string; body: string }

/** What each sidebar section is for, keyed by its route. Sections a student doesn't have are left out of their tour. */
const NAV_HELP: Record<string, string> = {
  "/app": "Your home: today's study time, streak, what's due and where to pick up.",
  "/app/plan": "Your study plan for today, this week and month by month, built from your goal and the time you have.",
  "/app/prep": "The whole syllabus, chapter by chapter, with how far you've got in each.",
  "/app/studio": "Open a lecture (YouTube or any tab) and Focs reads the board and listens to the teacher, writing notes as it goes.",
  "/app/library": "Every lecture you've captured, with its notes, summary and what the teacher said. Search it all here.",
  "/app/practice": "Practice questions made from your own notes and topics.",
  "/app/snap": "Stuck on a question? Take a photo of it and get a step-by-step solution.",
  "/app/mock": "Full timed tests in the real exam's pattern, with a report of where you lost marks.",
  "/app/weak": "Add a test result and Focs finds the topics you keep getting wrong, then helps you fix them.",
  "/app/campus": "Ask seniors who have already cleared your exam or course.",
  "/app/mentors": "Book a call or chat with a mentor.",
  "/app/revise": "The day before a test: what to revise first, and what you can safely leave.",
  "/app/flashcards": "Cards made from your notes, shown again just before you'd forget them. The number is how many are due.",
  "/app/rooms": "Study with friends in a room: a shared timer and live quizzes.",
  "/app/classes": "Classes your teacher has set up, with their lectures and tests.",
  "/app/leaderboard": "See how your study streak compares with others. You can hide yourself in Settings.",
};

export function buildTourSteps(nav: { to: string; label: string }[]): TourStep[] {
  return [
    { title: "Welcome to Focs 👋", body: "A quick tour of the controls. Use the arrow keys or the buttons, and Esc to skip." },
    { target: "start", title: "Start a lecture", body: "The main button. Start here whenever you watch a class, and it changes to \"Return to live lecture\" while one is running." },
    ...nav.filter((n) => NAV_HELP[n.to]).map((n) => ({ target: `nav:${n.to}`, title: n.label, body: NAV_HELP[n.to] })),
    { target: "more", title: "More sections", body: "On a phone the rest of the sections are in this menu." },
    { target: "search", title: "Search or jump anywhere", body: "Type what you want to do (\"mock test\", \"flashcards\", \"dark theme\") and press Enter. Ctrl + K opens it from any page." },
    { target: "bell", title: "Notifications", body: "Replies from seniors and mentors, test results and reminders show up here." },
    { target: "theme", title: "Light or dark", body: "Switch the theme whenever you like." },
    { target: "usage", title: "Your AI allowance", body: "How much of today's and this week's AI use is left. Tap it for the details." },
    { target: "profile", title: "Your profile and settings", body: "Your exam, language, daily goal and account. The arrow beside it signs you out." },
    { target: "help", title: "Need this again?", body: "Tap ? any time to replay this tour. That's it, happy studying!" },
  ];
}

/** The target as it is on screen now (the sidebar exists twice on phones: the hidden desktop one and the drawer). */
function findTarget(target?: string): HTMLElement | null {
  if (!target) return null;
  for (const el of document.querySelectorAll<HTMLElement>(`[data-tour="${CSS.escape(target)}"]`)) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) return el;
  }
  return null;
}

const PAD = 6;
const CARD_W = 320;

export function GuidedTour({ steps, open, onClose }: { steps: TourStep[]; open: boolean; onClose: () => void }) {
  const t = useT();
  // steps whose control isn't on this screen (desktop-only or phone-only) are skipped; the centred ones always show
  const [shown, setShown] = useState<TourStep[]>([]);
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (!open) return;
    setShown(steps.filter((s) => !s.target || findTarget(s.target)));
    setI(0);
  }, [open, steps]);

  const step = shown[i];
  const measure = useCallback(() => {
    const el = findTarget(step?.target);
    setRect(el ? el.getBoundingClientRect() : null);
  }, [step]);

  useLayoutEffect(() => {
    if (!open || !step) return;
    findTarget(step.target)?.scrollIntoView({ block: "nearest" });
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => { window.removeEventListener("resize", measure); window.removeEventListener("scroll", measure, true); };
  }, [open, step, measure]);

  const last = i === shown.length - 1;
  const next = useCallback(() => (last ? onClose() : setI((n) => n + 1)), [last, onClose]);
  const back = useCallback(() => setI((n) => Math.max(0, n - 1)), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight" || e.key === "Enter") { e.preventDefault(); next(); }
      else if (e.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, next, back, onClose]);

  const card = useMemo(() => {
    const vw = window.innerWidth, vh = window.innerHeight;
    const w = Math.min(CARD_W, vw - 32);
    if (!rect) return { left: (vw - w) / 2, top: vh / 2 - 110, width: w };
    // beside the control when there's room (the sidebar), else below it, else above it
    if (rect.right + 16 + w < vw && rect.width < vw / 2 && rect.left < vw / 3) {
      return { left: rect.right + 16, top: Math.max(16, Math.min(rect.top - 8, vh - 240)), width: w };
    }
    const left = Math.max(16, Math.min(rect.left + rect.width / 2 - w / 2, vw - w - 16));
    return rect.bottom + 230 < vh ? { left, top: rect.bottom + 14, width: w } : { left, top: Math.max(16, rect.top - 230), width: w };
  }, [rect]);

  return (
    <AnimatePresence>
      {open && step && (
        <motion.div className="fixed inset-0 z-[80]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          role="dialog" aria-modal="true" aria-label={t("Guided tour")}>
          {/* the dimmed page, with a window cut around the control being explained */}
          {rect ? (
            <motion.div className="pointer-events-none absolute rounded-lg ring-2 ring-accent"
              style={{ boxShadow: "0 0 0 9999px rgba(0,0,0,0.6)" }}
              animate={{ left: rect.left - PAD, top: rect.top - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 }}
              transition={{ type: "spring", stiffness: 380, damping: 34 }} />
          ) : <div className="absolute inset-0 bg-black/60" />}
          <div className="absolute inset-0" onClick={(e) => e.stopPropagation()} />

          <motion.div key={i} className="panel absolute p-4 shadow-xl" style={card}
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}>
            <div className="mb-1 flex items-start gap-2">
              <div className="flex-1 font-display text-[15px] font-semibold">{t(step.title)}</div>
              <button onClick={onClose} className="rounded p-1 text-muted hover:text-fg" aria-label={t("Skip tour")}><X className="h-4 w-4" /></button>
            </div>
            <p className="text-[13px] leading-relaxed text-fg-soft">{t(step.body)}</p>
            <div className="mt-4 flex items-center gap-2">
              <span className="text-[11.5px] text-muted">{i + 1} / {shown.length}</span>
              <div className="flex-1" />
              {i === 0 ? (
                <Button variant="ghost" size="sm" onClick={onClose}>{t("Skip")}</Button>
              ) : (
                <Button variant="ghost" size="sm" onClick={back} icon={<ArrowLeft className="h-4 w-4" />}>{t("Back")}</Button>
              )}
              <Button variant="primary" size="sm" onClick={next} icon={last ? undefined : <ArrowRight className="h-4 w-4" />}>
                {t(last ? "Done" : i === 0 ? "Show me" : "Next")}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** Seen once per account on this device; the ? button replays it. */
const seenKey = (userId?: number) => `focs.tour.done.${userId ?? "anon"}`;
export function tourSeen(userId?: number): boolean {
  try { return localStorage.getItem(seenKey(userId)) === "1"; } catch { return true; }
}
export function markTourSeen(userId?: number) {
  try { localStorage.setItem(seenKey(userId), "1"); } catch { /* private window: it just shows again next time */ }
}
