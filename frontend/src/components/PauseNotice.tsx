import { PauseCircle } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn, formatPaused } from "@/lib/utils";

export function useNow(on: boolean): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!on) return;
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [on]);
  return now;
}

/** A calm strip that says how long the lecture has been paused, and that the session is still open. */
export function PauseNotice({ since, looks, body, action, className }: {
  since: number; looks?: boolean; body?: string; action?: { label: string; onClick: () => void }; className?: string;
}) {
  const now = useNow(true);
  const d = formatPaused((now - since) / 1000);
  return (
    <div role="status" aria-live="off" className={cn("flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-line bg-bg-soft px-4 py-3 text-sm", className)}>
      <PauseCircle className="h-5 w-5 shrink-0 text-warn" />
      <div className="min-w-0 flex-1 basis-56">
        <div className="font-medium text-fg">{looks ? `Your lecture looks paused: no change for ${d}.` : `Paused for ${d}`}</div>
        <div className="text-xs text-muted">{body ?? (looks ? "Focs is keeping this session open." : "Your session stays open. Press play to carry on.")}</div>
      </div>
      {action && <Button size="sm" variant="secondary" onClick={action.onClick}>{action.label}</Button>}
    </div>
  );
}

/** Fills the stage when there is nothing to show (share stopped, lecture ended), so it is never a black box. */
export function StageCard({ icon, title, children, tip, actions }: { icon: ReactNode; title: string; children: ReactNode; tip?: string; actions: ReactNode }) {
  return (
    <div className="relative z-10 grid place-items-center bg-bg-soft px-5 py-8 text-center">
      <div className="max-w-md">
        <div className="mx-auto grid h-10 w-10 place-items-center text-muted">{icon}</div>
        <div className="mt-2 font-medium text-fg">{title}</div>
        <p className="mt-1 text-sm leading-relaxed text-fg-soft">{children}</p>
        {tip && <p className="mt-2 text-xs leading-relaxed text-muted">{tip}</p>}
        <div className="mt-4 flex flex-wrap justify-center gap-2">{actions}</div>
      </div>
    </div>
  );
}
