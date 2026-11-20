import { Coffee, Pause, Play, RotateCcw, Timer } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { clockOf } from "./types";

export interface TimerState {
  mode: "focus" | "break";
  duration: number;
  running: boolean;
  ends_at: number | null;
  remaining: number;
  by: string | null;
  paused?: boolean;
}

/** The room's shared focus timer: everyone sees the same countdown; anyone can start, pause or take a break. */
export function RoomTimer({ timer, skew, send }: { timer: TimerState | null; skew: number; send: (msg: Record<string, unknown>) => void }) {
  const [now, setNow] = useState(Date.now());
  const announced = useRef<number | null>(null);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, []);

  const left = !timer ? 0 : timer.running && timer.ends_at ? Math.max(0, timer.ends_at - (now / 1000 + skew)) : timer.remaining;
  useEffect(() => {
    if (!timer?.running || !timer.ends_at || left > 0 || announced.current === timer.ends_at) return;
    announced.current = timer.ends_at;
    toast.success(timer.mode === "focus" ? "Focus session done — take a 5-minute break together." : "Break's over — back to the lecture!");
  }, [left, timer]);
  if (!timer) return null;

  const start = (minutes?: number, mode?: "focus" | "break") => send({ type: "timer", action: "start", minutes, mode });
  const pct = timer.duration ? 100 * (1 - left / timer.duration) : 0;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-bg-soft px-3 py-2">
      <div className={cn("grid h-9 w-9 place-items-center rounded-lg", timer.mode === "focus" ? "bg-accent-soft text-accent" : "bg-ok/15 text-ok")}>
        {timer.mode === "focus" ? <Timer className="h-4 w-4" /> : <Coffee className="h-4 w-4" />}
      </div>
      <div className="min-w-[120px]">
        <div className="font-mono text-lg font-semibold tabular-nums leading-none">{clockOf(left)}</div>
        <div className="mt-1 text-[11px] text-muted">
          {timer.mode === "focus" ? "Focus" : "Break"}{timer.running ? " · running" : timer.paused ? " · paused" : ""}
          {timer.by && ` · ${timer.by}`}
        </div>
      </div>
      <div className="h-1.5 min-w-[80px] flex-1 overflow-hidden rounded-full bg-elev-2">
        <div className={cn("h-full rounded-full transition-[width] duration-500", timer.mode === "focus" ? "bg-gradient-brand" : "bg-ok")} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex gap-1.5">
        {timer.running ? (
          <Button size="sm" variant="secondary" onClick={() => send({ type: "timer", action: "pause" })} icon={<Pause className="h-3.5 w-3.5" />}>Pause</Button>
        ) : timer.paused && left > 0 ? (
          <Button size="sm" variant="secondary" onClick={() => start()} icon={<Play className="h-3.5 w-3.5" />}>Resume</Button>
        ) : (
          <Button size="sm" variant="secondary" onClick={() => start(25, "focus")} icon={<Play className="h-3.5 w-3.5" />}>Focus 25</Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => start(5, "break")} icon={<Coffee className="h-3.5 w-3.5" />}>Break</Button>
        <Button size="icon-sm" variant="ghost" onClick={() => send({ type: "timer", action: "reset" })} aria-label="Reset timer"><RotateCcw className="h-3.5 w-3.5" /></Button>
      </div>
    </div>
  );
}
