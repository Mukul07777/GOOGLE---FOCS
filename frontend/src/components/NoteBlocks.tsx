import { BookMarked, Columns2, Lightbulb, ListOrdered, PenLine, Sigma, Sparkles, Workflow, type LucideIcon } from "lucide-react";
import { useMemo } from "react";
import { Markdown } from "@/components/Markdown";
import { cn } from "@/lib/utils";

const KINDS: { match: RegExp; style: string; icon: LucideIcon }[] = [
  { match: /definition|meaning|paribhasha|परिभाषा/i, style: "note-definition", icon: BookMarked },
  { match: /formula|सूत्र|फ़ॉर्मूला|फॉर्मूला/i, style: "note-formulas", icon: Sigma },
  { match: /derivation|proof|व्युत्पत्ति|प्रमाण/i, style: "note-steps", icon: Workflow },
  { match: /worked example|example|solved|udaharan|उदाहरण/i, style: "note-example", icon: PenLine },
  { match: /steps|method|process|चरण|विधि/i, style: "note-steps", icon: ListOrdered },
  { match: /compare|difference| vs\.? |tulna|तुलना|अंतर/i, style: "note-compare", icon: Columns2 },
  { match: /\btip\b|remember|टिप|सुझाव/i, style: "note-tip", icon: Lightbulb },
];
const IDEAS = { style: "note-ideas", icon: Sparkles };

function split(md: string): { lead: string; blocks: { heading: string; body: string }[]; tail: string } {
  const blocks: { heading: string; body: string }[] = [];
  const lead: string[] = [];
  for (const line of md.split("\n")) {
    const h = /^#{2,4}\s+(.+)$/.exec(line);
    if (h) blocks.push({ heading: h[1].replace(/[#*]/g, "").trim(), body: "" });
    else if (blocks.length) blocks[blocks.length - 1].body += line + "\n";
    else lead.push(line);
  }
  // a closing "> ..." line speaks of the whole note, not of the last block (the offline notice)
  const last = blocks[blocks.length - 1];
  const closing = last && /\n\s*\n((?:>[^\n]*\n?)+)\s*$/.exec(last.body);
  if (closing) last.body = last.body.slice(0, closing.index);
  return { lead: lead.join("\n").trim(), blocks: blocks.filter((b) => b.body.trim()), tail: closing?.[1] ?? "" };
}

/** A board's notes, each kind of content in its own form: the shape follows what the board held. Notes written before
 *  the shapes existed read the same way. */
export function NoteBlocks({ markdown, className }: { markdown: string; className?: string }) {
  const { lead, blocks, tail } = useMemo(() => split(markdown), [markdown]);
  return (
    <div className={cn("note-blocks", className)}>
      {lead && <Markdown className={cn(blocks.length && lead.length < 240 && "note-lead")}>{lead}</Markdown>}
      {blocks.map((b, i) => {
        const kind = KINDS.find((k) => k.match.test(b.heading)) ?? IDEAS;
        const Icon = kind.icon;
        return (
          <section key={i} className={cn("note-block", kind.style)}>
            <h4 className="note-label"><Icon className="h-3.5 w-3.5" strokeWidth={1.75} />{b.heading}</h4>
            <Markdown>{b.body}</Markdown>
          </section>
        );
      })}
      {tail && <Markdown>{tail}</Markdown>}
    </div>
  );
}
