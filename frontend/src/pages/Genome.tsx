import { useQuery } from "@tanstack/react-query";
import { Dna, GitBranch, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/common";
import { Badge, Card, CardHeader, EmptyState, Skeleton } from "@/components/ui/primitives";
import { api, type GenomeNode } from "@/lib/api";
import { cn } from "@/lib/utils";

/* The Gap Genome: every shared root-cause chain drawn as one map, from the exam chapters on the right down to the
   school chapters they really rest on, Class 6 on the left. Node size: how many exam chapters rest on it. A ring:
   real students whose trace ended there. The weights come only from real traces, so an empty map says so. */

// fixed hues that read on both the light and the dark theme
const SUBJECT_TONE: Record<string, string> = {
  Physics: "#3b74e0", Mathematics: "#23a26d", Chemistry: "#e0862b", Biology: "#d04f86", Science: "#8b66d6",
};
const tone = (s: string | null) => SUBJECT_TONE[s ?? ""] ?? "var(--muted)";
const COL_W = 150, ROW_H = 38, PAD = 28;

function column(n: GenomeNode): number {
  if (n.kind === "exam" && !n.underpins) return 7;            // the exam chapter a student is stuck on
  return n.cls ? Math.max(0, Math.min(6, n.cls - 6)) : 6;      // Class 6..12
}

function GenomeMap({ nodes, edges, focus, onFocus }: {
  nodes: GenomeNode[]; edges: { from: string; to: string; weight: number }[];
  focus: string | null; onFocus: (id: string | null) => void;
}) {
  const layout = useMemo(() => {
    const cols: GenomeNode[][] = Array.from({ length: 8 }, () => []);
    nodes.forEach((n) => cols[column(n)].push(n));
    cols.forEach((c) => c.sort((a, b) => (a.subject ?? "").localeCompare(b.subject ?? "") || b.underpins - a.underpins));
    const pos = new Map<string, { x: number; y: number }>();
    cols.forEach((c, i) => c.forEach((n, j) => pos.set(n.id, { x: PAD + i * COL_W + 50, y: PAD + 30 + j * ROW_H })));
    const rows = Math.max(1, ...cols.map((c) => c.length));
    return { pos, w: PAD * 2 + 8 * COL_W, h: PAD * 2 + 30 + rows * ROW_H };
  }, [nodes]);

  const linked = useMemo(() => {
    if (!focus) return null;
    const s = new Set([focus]);
    edges.forEach((e) => { if (e.from === focus) s.add(e.to); if (e.to === focus) s.add(e.from); });
    return s;
  }, [focus, edges]);

  const heads = ["Class 6", "Class 7", "Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Exam chapter"];
  return (
    <div className="max-w-full overflow-x-auto">
      <svg width={layout.w} height={layout.h} role="img" aria-label="Map of exam chapters and the school chapters they rest on"
        className="block" onClick={() => onFocus(null)}>
        {heads.map((h, i) => (
          <text key={h} x={PAD + i * COL_W + 50} y={PAD} textAnchor="middle" fontSize={11} fill="var(--muted)"
            style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>{h}</text>
        ))}
        {edges.map((e) => {
          const a = layout.pos.get(e.from), b = layout.pos.get(e.to);
          if (!a || !b) return null;
          const on = !linked || (linked.has(e.from) && linked.has(e.to) && (e.from === focus || e.to === focus));
          const mx = (a.x + b.x) / 2;
          return <path key={e.from + e.to} d={`M${a.x},${a.y} C${mx},${a.y} ${mx},${b.y} ${b.x},${b.y}`} fill="none"
            stroke={on ? "var(--fg-soft)" : "var(--line)"} strokeOpacity={focus ? (on ? 0.8 : 0.5) : 0.3} strokeWidth={on ? 1 + e.weight : 1} />;
        })}
        {nodes.map((n) => {
          const p = layout.pos.get(n.id)!;
          const r = 5 + Math.min(9, n.underpins * 2.2);
          const dim = linked && !linked.has(n.id);
          return (
            <g key={n.id} transform={`translate(${p.x},${p.y})`} className="cursor-pointer" opacity={dim ? 0.25 : 1}
              onClick={(ev) => { ev.stopPropagation(); onFocus(n.id === focus ? null : n.id); }}>
              <title>{`${n.name} (${n.subject ?? ""}${n.cls ? `, Class ${n.cls}` : ""}): ${n.underpins} exam chapters rest on it, ${n.roots} real root gaps`}</title>
              {n.roots > 0 && <circle r={r + 5} fill="none" stroke="var(--bad)" strokeWidth={2} />}
              <circle r={r} fill={tone(n.subject)} stroke="var(--bg)" strokeWidth={1.5} />
              <text x={0} y={r + 11} textAnchor="middle" fontSize={10} fill="var(--fg-soft)">
                {n.name.length > 22 ? n.name.slice(0, 21) + "…" : n.name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default function Genome() {
  const { data, isLoading } = useQuery({ queryKey: ["genome"], queryFn: api.genome });
  const [focus, setFocus] = useState<string | null>(null);
  const top = data?.top[0];
  const picked = focus ? data?.nodes.find((n) => n.id === focus) : null;

  return (
    <div className="min-w-0">
      <PageHeader eyebrow="Root cause, for everyone" title="Gap Genome"
        subtitle="Every exam chapter Focs has traced, put together into one map of what it really rests on. The big nodes on the left are the school chapters that hold up the most of JEE and NEET." />

      {isLoading || !data ? <Skeleton className="h-96" /> : !data.exam_chapters ? (
        <Card><EmptyState icon={<Dna size={20} />} title="No chapters traced yet"
          body={<>Trace a chapter on <Link className="underline" to="/app/roots">Root cause</Link> and it appears here.</>} /></Card>
      ) : (
        <div className="grid min-w-0 grid-cols-1 gap-5 [&>*]:min-w-0">
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Exam chapters mapped" value={data.exam_chapters} />
            <Stat label="School chapters they rest on" value={data.foundations} />
            <Stat label="Real students traced" value={data.students}
              note={data.students ? `${data.rooted} root gaps found` : "No real traces yet: the map's shape is ready, the weights come from students"} />
          </div>

          {top && (
            <Card className="p-5">
              <div className="eyebrow mb-2">Load-bearing chapter</div>
              <p className="font-display text-[20px] leading-snug">
                <b>{top.name}</b> ({top.cls ? `Class ${top.cls}` : "Class 11-12"} {top.subject}) holds up{" "}
                <b>{top.underpins} exam chapters</b>. A student weak here struggles in all of them, and coaching re-teaches each one separately.
              </p>
            </Card>
          )}

          <Card>
            <CardHeader icon={<GitBranch size={16} />} title="The map"
              subtitle="Tap a chapter to see what it rests on and what rests on it. A red ring means real students' traces ended there." />
            <div className="p-3">
              <GenomeMap nodes={data.nodes} edges={data.edges} focus={focus} onFocus={setFocus} />
            </div>
            <div className="flex flex-wrap gap-3 px-5 pb-5 text-[12px] text-muted">
              {Object.entries(SUBJECT_TONE).map(([s, c]) => (
                <span key={s} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />{s}</span>
              ))}
            </div>
          </Card>

          {picked && (
            <Card className="p-5">
              <div className="flex flex-wrap items-center gap-2">
                <b>{picked.name}</b>
                <Badge>{picked.cls ? `Class ${picked.cls}` : "Exam"} · {picked.subject}</Badge>
                {picked.roots > 0 && <Badge tone="bad">{picked.roots} real root gaps · {picked.fixed} fixed</Badge>}
              </div>
              <p className="mt-2 text-[14px] text-muted">
                {picked.underpins ? `${picked.underpins} exam chapters rest on this.` : "An exam chapter: the lines show what it rests on."}
              </p>
            </Card>
          )}

          <Card>
            <CardHeader icon={<Users size={16} />} title="Most load-bearing school chapters" subtitle="Fix one of these and several exam chapters get easier at once." />
            <ol className="divide-y divide-line px-5 pb-3">
              {data.top.map((n, i) => (
                <li key={n.id} className="flex items-center gap-3 py-2.5 text-[14px]">
                  <span className="w-5 text-muted">{i + 1}</span>
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: tone(n.subject) }} />
                  <span className="min-w-0 flex-1 truncate">{n.name}</span>
                  <span className="text-muted">{n.cls ? `Class ${n.cls}` : ""}</span>
                  <span className={cn("w-28 text-right font-semibold")}>{n.underpins} exam ch.</span>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <Card className="p-4">
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{label}</div>
      <div className="mt-1 font-display text-[30px] leading-none">{value}</div>
      {note && <div className="mt-1.5 text-[12px] text-muted">{note}</div>}
    </Card>
  );
}
