import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { cn, formatMinutes } from "@/lib/utils";

export interface HeatDay { date: string; minutes: number; actions: number; active: boolean }

/** One hue, getting stronger: more study always reads as a darker square. */
const FILLS = [
  "var(--elev-2)",
  "color-mix(in oklab, var(--accent) 28%, var(--elev-2))",
  "color-mix(in oklab, var(--accent) 52%, var(--elev-2))",
  "color-mix(in oklab, var(--accent) 76%, var(--elev-2))",
  "var(--accent)",
];
const LEGEND = ["No study", "Under 15 min", "15–45 min", "45–90 min", "90 min +"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const GAP = 3, MIN_CELL = 11, MAX_CELL = 16, DAY_COL = 28;

/** Intensity from focus minutes; a day with only quick actions (a few flashcards) still shows. */
function level(d: HeatDay) {
  if (d.minutes >= 90) return 4;
  if (d.minutes >= 45) return 3;
  if (d.minutes >= 15) return 2;
  return d.minutes > 0 || d.actions > 0 || d.active ? 1 : 0;
}

const parse = (iso: string) => new Date(`${iso}T00:00:00`);

/** A year of study, like GitHub's contribution graph: one square per day, weeks as columns (Monday on top). */
export function YearHeatmap({ days }: { days: HeatDay[] }) {
  const wrap = useRef<HTMLDivElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [tip, setTip] = useState<{ d: HeatDay; x: number; y: number } | null>(null);
  const today = days[days.length - 1]?.date;

  const weeks = useMemo(() => {
    const first = days[0] ? (parse(days[0].date).getDay() + 6) % 7 : 0; // Monday = 0
    const padded: (HeatDay | null)[] = [...Array(first).fill(null), ...days];
    const out: (HeatDay | null)[][] = [];
    for (let i = 0; i < padded.length; i += 7) out.push(padded.slice(i, i + 7));
    return out;
  }, [days]);

  // squares grow to fill a wide card and stop shrinking on a phone (it scrolls instead)
  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const cell = width ? Math.max(MIN_CELL, Math.min(MAX_CELL, Math.floor((width - DAY_COL - GAP * weeks.length) / weeks.length))) : 13;

  // a month label over the first week of each month, skipped when it would collide with the next one
  const labels = useMemo(() => {
    const starts = weeks.map((w, i) => {
      const m = parse(w.find(Boolean)!.date).getMonth();
      const prev = i > 0 ? parse(weeks[i - 1].find(Boolean)!.date).getMonth() : -1;
      return m !== prev ? MONTHS[m] : "";
    });
    return starts.map((l, i) => (l && starts.slice(i + 1, i + 3).some(Boolean) ? "" : l));
  }, [weeks]);

  useEffect(() => { scroller.current?.scrollTo({ left: scroller.current.scrollWidth }); }, [days, cell]); // start at today on phones

  const show = (d: HeatDay, el: HTMLElement) => {
    const box = wrap.current!.getBoundingClientRect(), r = el.getBoundingClientRect();
    const x = Math.min(Math.max(r.left - box.left + r.width / 2, 90), box.width - 90); // keep the tooltip inside the card
    setTip({ d, x, y: r.top - box.top });
  };

  return (
    <div ref={wrap} className="relative" onMouseLeave={() => setTip(null)}>
      <div className="flex">
        <div className="shrink-0 text-[10px] text-muted" style={{ width: DAY_COL, paddingTop: 17 }}>
          {["Mon", "", "Wed", "", "Fri", "", ""].map((l, i) => (
            <div key={i} style={{ height: cell, lineHeight: `${cell}px`, marginBottom: GAP }}>{l}</div>
          ))}
        </div>
        <div ref={scroller} className="min-w-0 flex-1 overflow-x-auto pb-1" onScroll={() => setTip(null)}>
          <div className="relative mb-[5px] h-3 text-[10px] text-muted" style={{ width: weeks.length * (cell + GAP) }}>
            {labels.map((l, i) => l && <span key={i} className="absolute leading-3" style={{ left: i * (cell + GAP) }}>{l}</span>)}
          </div>
          <div className="flex w-max" style={{ gap: GAP }}>
            {weeks.map((w, i) => (
              <div key={i} className="flex flex-col" style={{ gap: GAP }}>
                {w.map((d, j) => (d ? (
                  <button key={j} type="button" aria-label={`${d.date}: ${d.minutes} minutes`}
                    onMouseEnter={(e) => show(d, e.currentTarget)} onFocus={(e) => show(d, e.currentTarget)} onClick={(e) => show(d, e.currentTarget)}
                    className={cn("rounded-[3px] outline-none transition hover:ring-2 hover:ring-accent/50 focus-visible:ring-2 focus-visible:ring-accent",
                      d.date === today && "ring-1 ring-fg/60")}
                    style={{ width: cell, height: cell, background: FILLS[level(d)] }} />
                ) : <div key={j} style={{ width: cell, height: cell }} />))}
              </div>
            ))}
          </div>
        </div>
      </div>
      {tip && (
        <div className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg border border-line-strong bg-elev px-2.5 py-1.5 text-xs shadow-xl"
          style={{ left: tip.x, top: tip.y - 6 }}>
          <b>{tip.d.minutes ? `${formatMinutes(tip.d.minutes)} focused` : tip.d.active || tip.d.actions ? "Studied" : "No study"}</b>
          {tip.d.actions > 0 && <span className="text-muted"> · {tip.d.actions} {tip.d.actions === 1 ? "action" : "actions"}</span>}
          <span className="text-muted"> · {tip.d.date === today ? "Today" : parse(tip.d.date).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" })}</span>
        </div>
      )}
      <div className="mt-2 flex items-center justify-end gap-1 text-[10.5px] text-muted">
        Less {FILLS.map((f, i) => <span key={f} title={LEGEND[i]} className="rounded-[3px]" style={{ width: 11, height: 11, background: f }} />)} More
      </div>
    </div>
  );
}
