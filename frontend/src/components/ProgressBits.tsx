import type { ReactNode } from "react";
import { cn, formatMinutes } from "@/lib/utils";

const DAY = ["S", "M", "T", "W", "T", "F", "S"];

/** The last seven days of study as bars, today last. A day that met the daily goal is in the accent colour. */
export function WeekBars({ days, goal = 0, className, tall }: { days: number[]; goal?: number; className?: string; tall?: boolean }) {
  const top = Math.max(goal, ...days, 1);
  const today = new Date().getDay();
  return (
    <div className={cn("flex items-end gap-1", className)} role="img" aria-label={`Study time over the last 7 days: ${days.map(formatMinutes).join(", ")}`}>
      {days.map((m, i) => (
        <div key={i} className="flex flex-1 flex-col items-center gap-1" title={formatMinutes(m)}>
          <div className={cn("flex w-full items-end rounded-md bg-elev-2", tall ? "h-24" : "h-8")}>
            <div className={cn("w-full rounded-md", goal && m >= goal ? "bg-accent" : "bg-accent/45")} style={{ height: `${m ? Math.max(8, (100 * m) / top) : 0}%` }} />
          </div>
          {tall && <span className={cn("text-[10px]", i === 6 ? "font-semibold text-fg" : "text-muted")}>{DAY[(today + i + 1) % 7]}</span>}
        </div>
      ))}
    </div>
  );
}

export function StatTile({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="panel rounded-2xl p-4">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted">{icon}{label}</div>
      <div className="figure mt-2 text-[38px]">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </div>
  );
}
