import { ArrowDown, BookOpen, Brain, Check, Columns2, Compass, Eye, Lightbulb, ListChecks, PenLine, Printer, Rocket, Sigma, Target, TriangleAlert, Workflow, X, Zap } from "lucide-react";
import { useId, useMemo, useRef, useState, type ComponentType, type ReactNode } from "react";
import { Markdown } from "@/components/Markdown";
import { displayStyle } from "@/lib/math";
import { printNode } from "@/lib/print";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Section {
  heading: string;
  body: string;
}

const KINDS: { match: RegExp; icon: ComponentType<{ className?: string }>; color: string }[] = [
  { match: /overview|summary|in one line/i, icon: Compass, color: "var(--accent)" },
  { match: /concept|key idea|core idea|key point/i, icon: Brain, color: "var(--accent-2)" },
  { match: /lecture map/i, icon: Compass, color: "var(--accent)" },
  { match: /compare|difference/i, icon: Columns2, color: "var(--accent-2)" },
  { match: /key terms/i, icon: BookOpen, color: "var(--warn)" },
  { match: /formula/i, icon: Sigma, color: "var(--warn)" },
  { match: /mistake|pitfall/i, icon: TriangleAlert, color: "var(--bad)" },
  { match: /trick|memory|mnemonic|intuition/i, icon: Lightbulb, color: "var(--ok)" },
  { match: /self.?check|quiz|test yourself/i, icon: ListChecks, color: "var(--accent)" },
  { match: /how it works|derivation|mechanism/i, icon: Workflow, color: "var(--accent-2)" },
  { match: /worked example|example/i, icon: PenLine, color: "var(--accent)" },
  { match: /asks it|exam pointer|in the exam/i, icon: Target, color: "var(--bad)" },
  { match: /recap/i, icon: Zap, color: "var(--ok)" },
  { match: /practi|next/i, icon: Rocket, color: "var(--ok)" },
];

function kindOf(heading: string) {
  return KINDS.find((k) => k.match.test(heading)) ?? { icon: BookOpen, color: "var(--muted)" };
}

/** Split on "## " (or legacy "### ") headings; text before the first heading becomes the overview. */
export function splitSections(md: string): Section[] {
  const level = /^## /m.test(md) ? "## " : "### ";
  const sections: Section[] = [];
  let current: Section = { heading: "Overview", body: "" };
  for (const line of md.split("\n")) {
    if (line.startsWith(level)) {
      if (current.body.trim()) sections.push(current);
      current = { heading: line.slice(level.length).replace(/[#*]/g, "").trim(), body: "" };
    } else {
      current.body += line + "\n";
    }
  }
  if (current.body.trim()) sections.push(current);
  return sections;
}

/** "1. Question?\n   Answer: …" pairs; null when the section isn't in that shape. */
function parseSelfCheck(body: string): { q: string; a: string }[] | null {
  const pairs: { q: string; a: string }[] = [];
  const lines = body.split("\n").map((l) => l.trim()).filter(Boolean);
  for (let i = 0; i < lines.length; i++) {
    const q = /^(?:\d+[.)]|-)\s+(.+)$/.exec(lines[i]);
    const a = lines[i + 1] && /^(?:[-*]\s*)?\**answer\**\s*[:：]\**\s*(.+)$/i.exec(lines[i + 1]);
    if (q && a) {
      pairs.push({ q: q[1].replace(/\*\*/g, ""), a: a[1] });
      i++;
    }
  }
  return pairs.length ? pairs : null;
}

/** "Mistake: … Instead: …" bullets (sheets written before v1.3 mark them ❌ … → ✅ …); null for any other shape. */
function parseMistakes(body: string): { wrong: string; right: string }[] | null {
  const pairs: { wrong: string; right: string }[] = [];
  const bullets: string[] = [];  // a bullet may run over several lines ("- Mistake: …" then "  Instead: …")
  for (const line of body.split("\n").map((l) => l.trim()).filter(Boolean)) {
    if (/^[-*]\s/.test(line) || !bullets.length) bullets.push(line);
    else bullets[bullets.length - 1] += ` ${line}`;
  }
  for (const line of bullets) {
    const m = /^[-*]\s*(?:❌|\*\*Mistake:?\*\*:?)\s*(.+?)\s*(?:→\s*✅|✅|\*\*Instead:?\*\*:?)\s*(.+)$/u.exec(line);
    if (!m) return null;
    pairs.push({ wrong: m[1].replace(/\s*(?:→|[-–—:;,])\s*$/, ""), right: m[2] });
  }
  return pairs.length ? pairs : null;
}

function Mistakes({ pairs }: { pairs: { wrong: string; right: string }[] }) {
  return (
    <ul className="space-y-2.5">
      {pairs.map((p, i) => (
        <li key={i} className="overflow-hidden rounded-xl border border-line bg-bg-soft">
          <div className="flex gap-2.5 px-3 py-2.5">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-bad/15 text-bad"><X className="h-3 w-3" strokeWidth={3} /></span>
            <Markdown className="flex-1 text-[14px]">{p.wrong}</Markdown>
          </div>
          <div className="flex gap-2.5 border-t border-line px-3 py-2.5">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-ok/15 text-ok"><Check className="h-3 w-3" strokeWidth={3} /></span>
            <Markdown className="flex-1 text-[14px] text-fg">{p.right}</Markdown>
          </div>
        </li>
      ))}
    </ul>
  );
}

function SelfCheck({ pairs }: { pairs: { q: string; a: string }[] }) {
  const [shown, setShown] = useState<Set<number>>(new Set());
  return (
    <>
    {pairs.length > 2 && (
      <div className="no-print mb-1 flex items-center justify-between gap-3 text-xs text-muted">
        <span>{shown.size} of {pairs.length} answers seen. Say each one before you look.</span>
        {shown.size < pairs.length && <button type="button" onClick={() => setShown(new Set(pairs.map((_, i) => i)))} className="inline-flex min-h-10 shrink-0 items-center font-medium text-fg hover:underline">Show all</button>}
      </div>
    )}
    <ol className="space-y-2.5">
      {pairs.map((p, i) => (
        <li key={i} className="rounded-xl border border-line bg-bg-soft p-3">
          <div className="flex gap-2.5">
            <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md bg-accent-soft text-xs font-semibold text-accent">{i + 1}</span>
            <Markdown className="flex-1 text-[14.5px] text-fg">{p.q}</Markdown>
          </div>
          {shown.has(i) ? (
            <div className="answer no-print mt-2 border-t border-line pt-2 pl-8"><Markdown className="text-sm">{p.a}</Markdown></div>
          ) : (
            <button onClick={() => setShown(new Set(shown).add(i))} className="no-print ml-8 inline-flex min-h-10 items-center gap-1.5 text-xs font-medium text-accent hover:underline">
              <Eye className="h-3.5 w-3.5" /> Show answer
            </button>
          )}
          <div className="print-only mt-2 pl-8"><Markdown className="text-sm">{p.a}</Markdown></div>
        </li>
      ))}
    </ol>
    </>
  );
}

/** "1. **Part** — what it covers" lines of a long lecture's map; null for any other shape. */
function parseMap(body: string): { name: string; about: string }[] | null {
  const items: { name: string; about: string }[] = [];
  for (const line of body.split("\n").map((l) => l.trim()).filter(Boolean)) {
    const m = /^\d+[.)]\s+\*\*(.+?)\*\*\s*(?:[—–:-]\s*)?(.*)$/.exec(line);
    if (!m) return null;
    items.push({ name: m[1], about: m[2] });
  }
  return items.length ? items : null;
}

function LectureMap({ items, onOpen }: { items: { name: string; about: string }[]; onOpen: (part: number) => void }) {
  return (
    <ol className="sheet-map">
      {items.map((p, i) => (
        <li key={i}>
          <button type="button" onClick={() => onOpen(i + 1)} className="group flex w-full items-start gap-3 py-2.5 text-left">
            <span className="sheet-map-n">{i + 1}</span>
            <span className="min-w-0 flex-1">
              <Markdown className="sheet-map-name">{p.name}</Markdown>
              {p.about && <Markdown className="text-[13.5px]">{p.about}</Markdown>}
            </span>
            <ArrowDown className="no-print mt-1 h-3.5 w-3.5 shrink-0 text-muted transition group-hover:translate-y-0.5" />
          </button>
        </li>
      ))}
    </ol>
  );
}

const LEAD = /^(overview|in one line|summary|अवलोकन|सारांश|एक पंक्ति में)$/i;
const SHEET_KINDS = [
  { match: /^## lecture map/im, label: "Full lecture guide" },
  { match: /^## in one line/im, label: "Quick recap" },
];

/** What kind of sheet this is: its size follows how much was studied. */
export const sheetLabel = (markdown: string) => SHEET_KINDS.find((k) => k.match.test(markdown))?.label ?? "Revision sheet";

function sheetFacts(sections: Section[]): string[] {
  const words = sections.reduce((n, s) => n + s.body.split(/\s+/).length, 0);
  const rows = sections.find((s) => /formula/i.test(s.heading))?.body.split("\n").filter((l) => /^\|/.test(l.trim()) && !/^\|\s*:?-/.test(l.trim())).length ?? 0;
  const formulas = Math.max(0, rows - 1);  // (the first row is the table's header)
  const checks = sections.find((s) => /self.?check/i.test(s.heading));
  const questions = checks ? parseSelfCheck(checks.body)?.length ?? 0 : 0;
  return [
    `${Math.max(1, Math.round(words / 180))} min read`,
    ...(formulas ? [`${formulas} ${formulas === 1 ? "formula" : "formulas"}`] : []),
    ...(questions ? [`${questions} ${questions === 1 ? "question" : "questions"}`] : []),
  ];
}

/** The sections of a sheet, each in the form that suits it, numbered like a printed guide. ``anchor``: the reader has
    its own contents, so none here and each card takes an id ("<anchor>-0", …) to jump to; ``display`` sets inline
    fractions at full size, for a page meant to be read rather than glanced at. */
export function SheetSections({ markdown, anchor, display }: { markdown: string; anchor?: string; display?: boolean }) {
  const sections = useMemo(() => splitSections(markdown || ""), [markdown]);
  const own = useId();
  const root = anchor ?? own;
  const go = (i: number) => document.getElementById(`${root}-${i}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  const toPart = (n: number) => {
    const i = sections.findIndex((s) => new RegExp(`^part ${n}\\b`, "i").test(s.heading));
    if (i >= 0) go(i);
  };
  let number = 0;
  return (
    <>
      {!anchor && (
        <div className="no-print flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          {sheetFacts(sections).map((f, i) => <span key={f} className="flex items-center gap-3">{i > 0 && <span className="h-3 w-px bg-line-strong" />}{f}</span>)}
        </div>
      )}
      {!anchor && sections.length >= 5 && (
        <nav className="no-print no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-0.5" aria-label="Sections of this sheet">
          {sections.map((s, i) => (
            <button key={i} type="button" onClick={() => go(i)} className="sheet-jump">{s.heading.replace(/^part (\d+):\s*/i, "$1. ")}</button>
          ))}
        </nav>
      )}
      {sections.map((s, i) => {
        const Icon = kindOf(s.heading).icon;
        const body = display || /formula|सूत्र/i.test(s.heading) ? displayStyle(s.body) : s.body;
        const id = `${root}-${i}`;
        if (LEAD.test(s.heading)) {
          return (
            <section key={i} id={id} className="sheet-lead scroll-mt-4">
              <h3 className="note-label">{s.heading}</h3>
              <Markdown>{body}</Markdown>
            </section>
          );
        }
        const part = /^(?:part|भाग) (\d+):\s*(.+)$/i.exec(s.heading);
        if (!part) number += 1;
        const qa = /self.?check|quiz|test yourself/i.test(s.heading) ? parseSelfCheck(body) : null;
        const mistakes = /mistake|pitfall/i.test(s.heading) ? parseMistakes(body) : null;
        const map = /lecture map/i.test(s.heading) ? parseMap(body) : null;
        return (
          <section key={i} id={id} className="sheet-section panel scroll-mt-4 overflow-hidden">
            <h3 className="sheet-heading">
              <span className="sheet-number">{part ? `Part ${part[1]}` : String(number).padStart(2, "0")}</span>
              <span className="min-w-0 flex-1">{part ? part[2] : s.heading}</span>
              <Icon className="h-4 w-4 shrink-0 self-center text-muted" />
            </h3>
            {qa ? <SelfCheck pairs={qa} /> : mistakes ? <Mistakes pairs={mistakes} /> : map ? <LectureMap items={map} onOpen={toPart} />
              : <Markdown className={cn("sheet-body", /formula|key terms|सूत्र/i.test(s.heading) && "sheet-formulas")}>{body}</Markdown>}
          </section>
        );
      })}
    </>
  );
}

export function RevisionSheet({ markdown, title, meta, className, label, actions, footer, printTitleOnly }: {
  markdown: string; title?: string | null; meta?: string; className?: string; label?: string; actions?: ReactNode; footer?: ReactNode; printTitleOnly?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const name = label ?? sheetLabel(markdown);
  return (
    <div className={cn("space-y-3", className)}>
      <div ref={ref} className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            <div className="note-label">{name}</div>
            {title && <h2 className={cn("mt-1 text-xl font-semibold tracking-tight", printTitleOnly && "print-only")}>{title}</h2>}
            {meta && <div className={cn("mt-0.5 text-xs text-muted", printTitleOnly && "print-only")}>{meta}</div>}
          </div>
          <div className="no-print flex flex-wrap items-center gap-2">
            {actions}
            <Button size="sm" icon={<Printer className="h-3.5 w-3.5" />} onClick={() => ref.current && printNode(ref.current, title || name)}>
              Print / Save PDF
            </Button>
          </div>
        </div>
        <SheetSections markdown={markdown} />
      </div>
      {footer}
    </div>
  );
}
