import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { ProgressBar } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { Usage, UsageMeter as Meter } from "@/lib/types";
import { clockAt, cn, formatMinutes, timeUntil } from "@/lib/utils";

export function useUsage() {
  return useQuery({ queryKey: ["usage"], queryFn: api.usage, refetchInterval: 60_000, staleTime: 20_000 });
}

/** The limit that binds first: the study day's allowance, or the weekly cap when that one is fuller. */
export function bindingMeter(u: Usage): { meter: Meter; weekly: boolean } {
  const weekly = !u.week.unlimited && u.week.pct > u.window.pct;
  return { meter: weekly ? u.week : u.window, weekly };
}

/** What an AI action will take from the allowance, said before the student presses the button. */
export function CostHint({ action, times = 1, className }: { action: string; times?: number; className?: string }) {
  const { data: u } = useUsage();
  const cost = u?.costs.find((c) => c.action === action)?.cost;
  if (!u || !cost) return null;
  const { meter, weekly } = bindingMeter(u);
  if (meter.unlimited || !meter.limit) return null;
  const pct = Math.max(1, Math.round((100 * cost * times) / meter.limit));
  const after = Math.min(100, meter.pct + pct);
  return (
    <p className={cn("text-[12px] text-muted", after >= 100 && "text-warn", className)}>
      Uses about {pct}% of your {weekly ? "weekly" : spanLabel(u.window_hours).toLowerCase()} AI allowance
      {after >= 100 ? ": more than you have left" : ` (${meter.pct}% → ${after}%)`}
    </p>
  );
}

export const meterTone = (pct: number) => (pct >= 100 ? "bad" : pct >= 80 ? "warn" : "accent") as "bad" | "warn" | "accent";

/** "Daily" for a 24-hour allowance, else "5-hour" and so on. */
export const spanLabel = (windowHours: number) => (windowHours === 24 ? "Daily" : `${windowHours}-hour`);

export function resetLine(m: Meter, windowHours: number) {
  if (!m.used || !m.resets_at) {
    const span = windowHours === 24 ? "a day" : windowHours === 168 ? "a week" : `${windowHours} h`;
    return `Refreshes ${span} after you start using it`;
  }
  return m.pct >= 100 ? `Back at ${clockAt(m.resets_at)}` : `Resets in ${timeUntil(m.resets_at)}`;
}

export function SidebarUsage({ onNavigate }: { onNavigate?: () => void }) {
  const { data: u } = useUsage();
  if (!u || (u.window.unlimited && u.week.unlimited)) return null;
  const { meter, weekly } = bindingMeter(u);
  const free = u.plan === "free";
  return (
    <Link to="/app/settings#usage" onClick={onNavigate}
      className={cn("mb-3 block rounded-2xl border p-3 transition hover:bg-elev-2",
        meter.pct >= 100 ? "border-bad/30 bg-bad/5" : free ? "ring-gradient bg-elev" : "border-line bg-panel/60")}>
      <div className="flex items-center justify-between text-[12.5px]">
        <span className="font-medium">{weekly ? "Weekly" : spanLabel(u.window_hours)} AI allowance</span>
        <span className={cn("tabular-nums", meter.pct >= 80 ? "text-warn" : "text-muted")}>{meter.pct}% used</span>
      </div>
      <ProgressBar value={meter.pct} tone={meterTone(meter.pct)} className="mt-2" />
      <div className="mt-1.5 hidden text-[11.5px] text-muted lg:block">{resetLine(meter, u.window_hours)}</div>
      {!u.lecture.unlimited && u.lecture.used > 0 && (
        <div className={cn("mt-1.5 text-[11.5px]", u.lecture.pct >= 100 ? "font-medium text-warn" : "text-muted")}>
          Lecture notes today: {formatMinutes(u.lecture.used)} of {formatMinutes(u.lecture.limit ?? 0)}
        </div>
      )}
      {u.fair_use_pct !== null && u.fair_use_pct >= 80 && (  // a heavy month: say so before the fair-use limit arrives
        <div className="mt-1.5 text-[11.5px] font-medium text-warn">{u.fair_use_pct}% of this month's fair use</div>
      )}
      {free && (
        <div className="mt-2 hidden items-center gap-1.5 text-[11.5px] font-medium text-accent lg:flex">
          <Sparkles className="h-3 w-3" /> Pro: {formatMinutes(u.lecture_limits.pro ?? 0)} of lecture notes a day
        </div>
      )}
    </Link>
  );
}
