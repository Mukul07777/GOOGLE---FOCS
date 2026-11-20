import { Check } from "lucide-react";
import type { ReactNode } from "react";
import { Label } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

/* The building blocks of the set-your-goal steps, shared by the entrance-exam and the college versions. */

export function Choice({ on, onClick, children, className }: { on: boolean; onClick: () => void; children: ReactNode; className?: string }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={on}
      className={cn("relative rounded-2xl border p-4 text-left transition",
        on ? "border-accent/60 bg-accent-soft shadow-[var(--glow)]" : "border-line bg-elev/50 hover:border-line-strong", className)}>
      {on && <Check className="absolute right-3 top-3 h-4 w-4 stroke-[2.5] text-accent" />}
      {children}
    </button>
  );
}

export function Hours({ label, value, onChange, min, hint }: { label: string; value: number; onChange: (v: number) => void; min: number; hint: string }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <Label className="mb-0">{label}</Label>
        <span className="text-2xl font-semibold tabular-nums">{value}<span className="ml-1 text-sm font-normal text-muted">h</span></span>
      </div>
      <input type="range" min={min} max={14} step={0.5} value={value} onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[var(--accent)]" aria-label={label} />
      <p className="mt-1 text-xs text-muted">{hint}</p>
    </div>
  );
}
