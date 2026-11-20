import { HelpCircle, ShieldCheck } from "lucide-react";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

export type Confidence = "sure" | "unsure";

/** After picking an answer, lock it in by saying how sure you are (S or G on the keyboard). The gap between how
    sure students feel and what they get right is where the learning is: see services/calibration.py. */
export function ConfidenceLock({ ready, onLock, compact }: { ready: boolean; onLock: (c: Confidence) => void; compact?: boolean }) {
  useEffect(() => {
    if (!ready) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "TEXTAREA" || (e.target as HTMLElement)?.tagName === "INPUT") return;
      if (e.key === "s" || e.key === "S") onLock("sure");
      if (e.key === "g" || e.key === "G") onLock("unsure");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ready, onLock]);
  const t = useT();
  return (
    <div className={cn("flex flex-wrap items-center gap-2 rounded-xl border border-line bg-elev/60", compact ? "mt-3 p-2" : "mt-4 p-3", !ready && "opacity-50")}>
      <span className={cn("font-medium text-fg-soft", compact ? "text-xs" : "text-[13px]")}>{t(ready ? "Lock it in. How sure are you?" : "Pick an answer, then say how sure you are")}</span>
      <span className="flex-1" />
      <Button size="sm" variant="primary" className="min-h-10 sm:min-h-0" disabled={!ready} onClick={() => onLock("sure")} icon={<ShieldCheck className="h-3.5 w-3.5" />}>{t("Sure")} <kbd className="ml-1 hidden text-[10px] sm:inline">S</kbd></Button>
      <Button size="sm" variant="secondary" className="min-h-10 sm:min-h-0" disabled={!ready} onClick={() => onLock("unsure")} icon={<HelpCircle className="h-3.5 w-3.5" />}>{t("Guessing")} <kbd className="ml-1 hidden text-[10px] sm:inline">G</kbd></Button>
    </div>
  );
}

/** What to say once the answer is shown, by how sure the student was. */
export function verdict(correct: boolean, c: Confidence | null): { tone: "ok" | "bad" | "warn"; text: string } {
  if (correct) return c === "unsure"
    ? { tone: "warn", text: "Right, though you were guessing. Read why it's right so next time you know it." }
    : { tone: "ok", text: "Spot on." };
  return c === "sure"
    ? { tone: "bad", text: "You were sure, and it's wrong: a blind spot. These are the mistakes that stick best once fixed, so read the explanation now." }
    : { tone: "bad", text: "Not quite: added to your redo queue." };
}
