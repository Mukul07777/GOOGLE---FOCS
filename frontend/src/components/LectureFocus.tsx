import { ChevronDown, Eye, EyeOff, MessageCircleQuestion, Sparkles, Target } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useBackClose } from "@/lib/overlay";
import { cn } from "@/lib/utils";

const KEY = "focs-lecture-focus";
const SMALL = "(max-width: 1279px)";  // phones and tablets: one column, the notes would sit under the video

/**
 * Focus mode for a lecture on a phone or tablet: the lecture fills the top, and the notes, doubts and quiz settings get
 * out of the way (Focs keeps writing them). They open from the bottom like a video app's comments, over the lecture,
 * which plays on. On by default on small screens; the student's choice is remembered. Big screens never use it: the
 * notes sit beside the lecture there.
 */
export function useLectureFocus() {
  const [small, setSmall] = useState(() => typeof window !== "undefined" && window.matchMedia?.(SMALL).matches);
  const [chosen, setChosen] = useState<boolean>(() => {
    try { return localStorage.getItem(KEY) !== "off"; } catch { return true; }
  });
  useEffect(() => {
    const m = window.matchMedia?.(SMALL);
    if (!m) return;
    const on = () => setSmall(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  const set = (v: boolean) => {
    setChosen(v);
    try { localStorage.setItem(KEY, v ? "on" : "off"); } catch { /* private mode */ }
  };
  return { focus: !!small && chosen, canFocus: !!small, setFocus: set };
}

/** New notes since the sheet was last open: a dot on the Notes button instead of a toast over the lecture. */
export function useUnseen(count: number, open: boolean) {
  const [seen, setSeen] = useState(count);
  useEffect(() => { if (open) setSeen(count); }, [open, count]);
  return Math.max(0, count - seen);
}

/** The slim bar under the lecture in focus mode: notes, a doubt, a quiz now, and leaving focus. */
export function FocusBar({ notes, unseen, onNotes, onAsk, onQuiz, quizLoading, quizDisabled, onExit }: {
  notes: number; unseen: number; onNotes: () => void; onAsk: () => void; onQuiz: () => void;
  quizLoading?: boolean; quizDisabled?: boolean; onExit: () => void;
}) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none]">
      <Button size="sm" variant="secondary" onClick={onNotes} icon={<Sparkles className="h-3.5 w-3.5" />} className="relative shrink-0">
        Notes{notes ? ` · ${notes}` : ""}
        {unseen > 0 && <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-accent" aria-label={`${unseen} new`} />}
      </Button>
      <Button size="sm" variant="ghost" onClick={onAsk} icon={<MessageCircleQuestion className="h-3.5 w-3.5" />} className="shrink-0">Doubt</Button>
      <Button size="sm" variant="ghost" onClick={onQuiz} loading={quizLoading} disabled={quizDisabled} icon={<Target className="h-3.5 w-3.5" />} className="shrink-0">Quiz me</Button>
      <div className="flex-1" />
      <button type="button" onClick={onExit} title="Show everything (leave focus mode)" aria-label="Show everything (leave focus mode)"
        className="grid h-10 w-10 shrink-0 place-items-center rounded-lg text-muted transition hover:bg-elev-2 hover:text-fg">
        <EyeOff className="h-4 w-4" />
      </button>
    </div>
  );
}

/** Back into focus mode from the full view, on small screens. */
export function FocusButton({ onClick }: { onClick: () => void }) {
  return <Button size="sm" variant="secondary" onClick={onClick} icon={<Eye className="h-3.5 w-3.5" />}>Focus on the lecture</Button>;
}

/**
 * The notes panel. In focus mode it is a sheet from the bottom (kept mounted, so a half-typed doubt survives closing
 * it) and Back closes it; otherwise it renders in place with the classes it is given.
 */
export function NotesSheet({ focus, open, onClose, className, children }: {
  focus: boolean; open: boolean; onClose: () => void; className: string; children: ReactNode;
}) {
  useBackClose(focus && open, onClose);
  if (!focus) return <div className={className}>{children}</div>;
  return (
    <>
      <div aria-hidden className={cn("fixed inset-0 z-40 bg-black/30 transition-opacity", open ? "opacity-100" : "pointer-events-none opacity-0")} onClick={onClose} />
      <div role="dialog" aria-label="Lecture notes" aria-hidden={!open} inert={!open}
        className={cn("fixed inset-x-0 bottom-0 z-50 flex h-[62dvh] flex-col overflow-hidden rounded-t-2xl border border-line bg-panel shadow-2xl transition-transform duration-300",
          open ? "translate-y-0" : "translate-y-full")}>
        <button type="button" onClick={onClose} className="flex w-full items-center justify-center gap-1 py-2 text-xs text-muted" aria-label="Close notes, back to the lecture">
          <span className="h-1 w-10 rounded-full bg-line-strong" /><ChevronDown className="h-4 w-4" />
        </button>
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      </div>
    </>
  );
}
