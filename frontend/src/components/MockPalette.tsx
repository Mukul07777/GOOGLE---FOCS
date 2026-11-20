import { Check } from "lucide-react";
import type { MockResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

/** NTA question-palette states */
export type PaletteState = "not_visited" | "not_answered" | "answered" | "marked" | "answered_marked";

export function paletteState(r: MockResponse | undefined): PaletteState {
  if (!r?.v) return "not_visited";
  const answered = r.a !== null && r.a !== undefined && r.a !== "";
  if (r.m) return answered ? "answered_marked" : "marked";
  return answered ? "answered" : "not_answered";
}

export const PALETTE_LABEL: Record<PaletteState, string> = {
  not_visited: "Not visited",
  not_answered: "Not answered",
  answered: "Answered",
  marked: "Marked for review",
  answered_marked: "Answered & marked for review",
};

export function PaletteBadge({ state, children, active, className, onClick }: {
  state: PaletteState; children?: React.ReactNode; active?: boolean; className?: string; onClick?: () => void;
}) {
  const look: Record<PaletteState, string> = {
    not_visited: "border-line-strong bg-elev-2 text-fg-soft rounded-md",
    not_answered: "border-bad/60 bg-bad text-white rounded-t-xl rounded-b-md",
    answered: "border-ok/60 bg-ok text-white rounded-b-xl rounded-t-md",
    marked: "border-[#8b5cf6] bg-[#7c3aed] text-white rounded-full",
    answered_marked: "border-[#8b5cf6] bg-[#7c3aed] text-white rounded-full",
  };
  const Tag = onClick ? "button" : "span";
  return (
    <Tag onClick={onClick} type={onClick ? "button" : undefined}
      className={cn("relative grid h-9 w-9 shrink-0 place-items-center border text-[12.5px] font-semibold tabular-nums transition",
        look[state], onClick && "hover:brightness-110", active && "ring-2 ring-accent ring-offset-2 ring-offset-bg", className)}>
      {children}
      {state === "answered_marked" && (
        <span className="absolute -bottom-0.5 -right-0.5 grid h-3.5 w-3.5 place-items-center rounded-full bg-ok text-white ring-2 ring-bg">
          <Check className="h-2.5 w-2.5" strokeWidth={3} />
        </span>
      )}
    </Tag>
  );
}

export function PaletteLegend({ counts, compact }: { counts?: Partial<Record<PaletteState, number>>; compact?: boolean }) {
  const order: PaletteState[] = ["answered", "not_answered", "not_visited", "marked", "answered_marked"];
  return (
    <div className={cn("grid gap-2", compact ? "grid-cols-2 text-[11.5px]" : "text-[13px] sm:grid-cols-2")}>
      {order.map((s) => (
        <div key={s} className={cn("flex items-center gap-2", s === "answered_marked" && "col-span-full")}>
          <PaletteBadge state={s} className={compact ? "h-7 w-7 text-[11px]" : undefined}>{counts ? counts[s] ?? 0 : ""}</PaletteBadge>
          <span className="text-fg-soft">
            {PALETTE_LABEL[s]}
            {s === "answered_marked" && <span className="text-muted"> (will be evaluated)</span>}
          </span>
        </div>
      ))}
    </div>
  );
}
