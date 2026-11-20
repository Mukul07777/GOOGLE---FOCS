import { Crosshair, Sparkles } from "lucide-react";
import { Markdown } from "@/components/Markdown";
import { Card, CardHeader } from "@/components/ui/primitives";
import type { Calibration } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Confidence vs reality: how sure the student was against what they got right, with the blind spots (sure and
    wrong) first. Shown after a lecture and on Weak spots. */
export function CalibrationCard({ c, title = "Confidence vs reality", subtitle }: { c: Calibration; title?: string; subtitle?: string }) {
  const cells = [
    { key: "sure_right", label: "Sure, and right", hint: "you know these", tone: "border-ok/30 bg-ok/5 text-ok" },
    { key: "sure_wrong", label: "Sure, and wrong", hint: "blind spots: start here", tone: "border-bad/40 bg-bad/10 text-bad" },
    { key: "guess_right", label: "Guessed, and right", hint: "you know more than you think", tone: "border-warn/30 bg-warn/5 text-warn" },
    { key: "guess_wrong", label: "Guessed, and wrong", hint: "you knew to doubt these", tone: "border-line bg-bg-soft text-fg-soft" },
  ] as const;
  return (
    <Card>
      <CardHeader title={title} icon={<Crosshair className="h-4 w-4" />}
        subtitle={subtitle ?? `${c.answers} answers locked in as sure or guessing${c.sure_accuracy !== null ? ` · right ${c.sure_accuracy}% of the time when sure` : ""}${c.guess_accuracy !== null ? `, ${c.guess_accuracy}% when guessing` : ""}`} />
      <div className="space-y-4 p-5">
        {c.headline && <p className={cn("rounded-xl px-3.5 py-2.5 text-[14px] font-medium", c.blind_spots.length ? "bg-bad/10 text-fg" : "bg-ok/10 text-fg")}>{c.headline}</p>}
        <div className="grid grid-cols-2 gap-2" role="table" aria-label="Sure or guessing, against right or wrong">
          {cells.map((x) => (
            <div key={x.key} role="cell" className={cn("rounded-xl border px-3 py-2.5", x.tone)}>
              <div className="text-2xl font-semibold tabular-nums">{c.grid[x.key]}</div>
              <div className="text-[12.5px] font-medium text-fg">{x.label}</div>
              <div className="text-[11.5px] text-muted">{x.hint}</div>
            </div>
          ))}
        </div>
        {c.blind_spots.length > 0 && (
          <div>
            <div className="mb-1.5 text-[11.5px] font-semibold uppercase tracking-[0.12em] text-bad">Blind spots</div>
            <ul className="space-y-2">
              {c.blind_spots.slice(0, 5).map((b) => (
                <li key={b.id} className="rounded-xl border border-line bg-bg-soft px-3 py-2 text-[13px]">
                  <div className="font-semibold">{b.topic || "A question"}{b.subject ? <span className="font-normal text-muted"> · {b.subject}</span> : null}</div>
                  <Markdown className="line-clamp-2 text-muted [&_p]:my-0">{b.question}</Markdown>
                </li>
              ))}
            </ul>
          </div>
        )}
        {c.hidden_strengths.length > 0 && (
          <p className="flex gap-2 text-[13px] text-muted"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
            Right while guessing: {Array.from(new Set(c.hidden_strengths.map((h) => h.topic).filter(Boolean))).slice(0, 4).join(", ")}. Worth a quick read so the guess becomes knowing.</p>
        )}
      </div>
    </Card>
  );
}
