import { Camera, Check, Mic, Sparkles, Target, X } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Markdown } from "@/components/Markdown";
import { ConfidenceLock, verdict, type Confidence } from "@/components/ConfidenceLock";
import { TeachBack } from "@/components/TeachBack";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { displayStyle } from "@/lib/math";
import type { Checkpoint } from "@/lib/types";
import { cn, formatDuration, LETTERS } from "@/lib/utils";

export interface LiveQuestion extends Checkpoint {
  kind: "checkpoint" | "pop";
}

/* ---------------------------------------------------------------- the question itself */
export function QuizCard({ q, picked, onPick, compact, confidence }: {
  q: LiveQuestion; picked: number | null; onPick: (i: number, c: Confidence) => void; compact?: boolean; confidence?: Confidence | null;
}) {
  const [chosen, setChosen] = useState<number | null>(null);
  useEffect(() => setChosen(null), [q]);
  const lock = useCallback((c: Confidence) => { if (chosen !== null && picked === null) onPick(chosen, c); }, [chosen, picked, onPick]);
  const said = picked !== null ? verdict(picked === q.answer_index, confidence ?? null) : null;
  return (
    <div>
      <Markdown className={cn("text-fg", compact ? "text-[14px]" : "text-[15px]")}>{q.question}</Markdown>
      <div className={cn("space-y-2", compact ? "mt-3" : "mt-4")}>
        {q.options.map((o, i) => {
          const state = picked === null ? (chosen === i ? "chosen" : "idle") : i === q.answer_index ? "right" : i === picked ? "wrong" : "dim";
          return (
            <button key={i} onClick={() => picked === null && setChosen(i)} disabled={picked !== null} aria-pressed={chosen === i}
              className={cn("flex w-full items-center gap-3 rounded-xl border text-left transition", compact ? "px-3 py-2 text-[13px]" : "px-3.5 py-3 text-sm",
                state === "idle" && "border-line bg-bg-soft hover:border-accent/50", state === "chosen" && "border-accent bg-accent-soft",
                state === "right" && "border-ok/50 bg-ok/10", state === "wrong" && "border-bad/50 bg-bad/10", state === "dim" && "border-line opacity-50")}>
              <span className={cn("grid shrink-0 place-items-center rounded-lg border text-xs font-semibold", compact ? "h-6 w-6" : "h-7 w-7",
                state === "right" ? "border-ok bg-ok text-white" : state === "wrong" ? "border-bad bg-bad text-white" : "border-line-strong")}>
                {state === "right" ? <Check className="h-3.5 w-3.5" /> : state === "wrong" ? <X className="h-3.5 w-3.5" /> : LETTERS[i]}
              </span>
              <Markdown className={compact ? "text-[13px]" : "text-sm"}>{displayStyle(o)}</Markdown>
            </button>
          );
        })}
      </div>
      {picked === null && <ConfidenceLock ready={chosen !== null} onLock={lock} compact={compact} />}
      {picked !== null && said && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className={cn("rounded-xl border border-line bg-bg-soft", compact ? "mt-3 p-3" : "mt-4 p-4")}>
          <div className={cn("mb-1 text-sm font-semibold", said.tone === "ok" ? "text-ok" : said.tone === "warn" ? "text-warn" : "text-bad")}>{said.text}</div>
          <Markdown className="text-[13px]">{q.explanation}</Markdown>
        </motion.div>
      )}
    </div>
  );
}

export function LiveQuizDialog({ q, picked, onPick, onClose, sessionId, subject, confidence }: {
  q: LiveQuestion | null; picked: number | null; onPick: (i: number, c: Confidence) => void; onClose: () => void; confidence?: Confidence | null;
  /** the lecture the question came from: lets the student explain the topic back instead, checked against its boards */
  sessionId?: number; subject?: string | null;
}) {
  const [explain, setExplain] = useState(false);
  useEffect(() => setExplain(false), [q]);
  if (!q) return null;
  return (
    <Dialog open onClose={onClose}
      title={<span className="flex items-center gap-2"><Target className="h-5 w-5 text-accent" />{q.kind === "pop" ? "Pop quiz" : "Checkpoint"}</span>}
      subtitle={q.kind === "pop" ? `Quick check on “${q.topic}”` : `The lecture moved on from “${q.topic}”. Quick check before you continue:`}>
      {explain ? (
        <TeachBack topic={q.topic} sessionId={sessionId} subject={subject ?? undefined}
          footer={<Button size="sm" variant="ghost" onClick={onClose}>Continue lecture</Button>} />
      ) : (
        <>
          <QuizCard q={q} picked={picked} onPick={onPick} confidence={confidence} />
          <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
            {sessionId && picked === null
              ? <Button variant="ghost" size="sm" onClick={() => setExplain(true)} icon={<Mic className="h-3.5 w-3.5" />}>Explain it in my own words instead</Button>
              : <span />}
            <Button variant={picked === null ? "ghost" : "primary"} onClick={onClose}>{picked === null ? "Skip" : "Continue lecture"}</Button>
          </div>
        </>
      )}
    </Dialog>
  );
}

/* ---------------------------------------------------------------- floating mini window (Document Picture-in-Picture) */
interface DocumentPip {
  requestWindow(options?: { width?: number; height?: number }): Promise<Window>;
}
const pipApi = () => (window as unknown as { documentPictureInPicture?: DocumentPip }).documentPictureInPicture;

export function usePipWindow() {
  const [container, setContainer] = useState<HTMLElement | null>(null);
  const [win, setWin] = useState<Window | null>(null);
  const supported = typeof window !== "undefined" && !!pipApi();

  const open = useCallback(async () => {
    const api = pipApi();
    if (!api) return;
    const w = await api.requestWindow({ width: 380, height: 560 });
    // bring the app's styles (Tailwind, fonts, KaTeX) into the new document
    document.querySelectorAll<HTMLLinkElement | HTMLStyleElement>('link[rel="stylesheet"], style').forEach((node) => {
      if (node instanceof HTMLLinkElement) {
        const link = w.document.createElement("link");
        link.rel = "stylesheet";
        link.href = node.href;
        w.document.head.appendChild(link);
      } else {
        w.document.head.appendChild(node.cloneNode(true));
      }
    });
    w.document.title = "Focs — live";
    w.document.documentElement.dataset.theme = document.documentElement.dataset.theme ?? "dark";
    w.document.body.style.margin = "0";
    w.document.body.style.background = "var(--bg)";
    const root = w.document.createElement("div");
    w.document.body.appendChild(root);
    w.addEventListener("pagehide", () => { setContainer(null); setWin(null); });
    setWin(w);
    setContainer(root);
  }, []);

  const close = useCallback(() => win?.close(), [win]);
  useEffect(() => () => { win?.close(); }, [win]);
  return { supported, open, close, isOpen: !!container, portal: (node: ReactNode) => (container ? createPortal(node, container) : null) };
}

const DOT: Record<string, string> = {
  "text-muted": "bg-fg-soft/40", "text-ok": "bg-ok", "text-warn": "bg-warn", "text-bad": "bg-bad", "text-accent-2": "bg-accent-2",
};

export function MiniPanel({ elapsed, status, statusTone, notesCount, lastTopic, quiz, picked, onPick, onDismissQuiz, nextQuizIn, onQuizNow,
  quizLoading, onCapture, paused, caption, confidence }: {
  elapsed: number; status: string; statusTone: string; notesCount: number; lastTopic?: string | null;
  quiz: LiveQuestion | null; picked: number | null; onPick: (i: number, c: Confidence) => void; onDismissQuiz: () => void; confidence?: Confidence | null;
  nextQuizIn: number | null; onQuizNow: () => void; quizLoading: boolean; onCapture: () => void; paused: boolean;
  /** the teacher's latest words (the voice lane) */ caption?: string | null;
}) {
  return (
    <div className="flex min-h-[100dvh] flex-col gap-3 bg-bg p-3 font-sans text-fg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-bad">
          <span className="live-dot" /> Live · {formatDuration(elapsed)}
        </div>
        <span className="text-xs text-muted">{notesCount} {notesCount === 1 ? "note" : "notes"}</span>
      </div>
      <div className="rounded-xl border border-line bg-panel px-3 py-2 text-xs">
        <span className={cn("mr-1.5 inline-block h-2 w-2 rounded-full", paused ? "bg-warn" : DOT[statusTone] ?? "bg-ok")} />
        <span className={statusTone}>{paused ? "Paused" : status}</span>
        {lastTopic && <div className="mt-1 truncate text-[13px] font-medium text-fg">Last board: {lastTopic}</div>}
      </div>
      {caption && <div className="rounded-xl border border-line bg-panel px-3 py-2 text-[13px] leading-snug" aria-live="polite">“{caption}”</div>}
      {quiz ? (
        <div className="panel ring-gradient flex-1 overflow-y-auto bg-elev p-3">
          <div className="mb-2 flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.12em] text-accent">
            <span className="flex items-center gap-1.5"><Target className="h-3.5 w-3.5" />{quiz.kind === "pop" ? "Pop quiz" : "Checkpoint"}</span>
            <button onClick={onDismissQuiz} className="rounded p-1 text-muted hover:text-fg" aria-label="Close quiz"><X className="h-3.5 w-3.5" /></button>
          </div>
          <QuizCard q={quiz} picked={picked} onPick={onPick} compact confidence={confidence} />
          {picked !== null && <Button size="sm" variant="primary" className="mt-3 w-full" onClick={onDismissQuiz}>Continue lecture</Button>}
        </div>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-line p-4 text-center">
          <Sparkles className="h-6 w-6 text-accent" />
          <div className="mt-2 text-sm font-medium">Keep watching — Focs is taking notes</div>
          <div className="mt-1 text-xs text-muted">
            {nextQuizIn === null ? "Pop quizzes are off" : nextQuizIn <= 0 ? "Pop quiz coming up…" : `Next pop quiz in ${formatDuration(nextQuizIn)}`}
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <Button size="sm" variant="secondary" onClick={onQuizNow} loading={quizLoading} icon={<Target className="h-3.5 w-3.5" />}>Quiz me now</Button>
        <Button size="sm" variant="secondary" onClick={onCapture} icon={<Camera className="h-3.5 w-3.5" />}>Capture now</Button>
      </div>
    </div>
  );
}

