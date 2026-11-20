import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Printer, Search, Sigma } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Card, EmptyState, Input, Segmented, Skeleton } from "@/components/ui/primitives";
import { useFocus } from "@/lib/focus";
import { api } from "@/lib/api";
import { asFormula } from "@/lib/math";
import { printNode } from "@/lib/print";
import { subjectColor } from "@/lib/utils";

/** Every formula from your board notes in one place — grouped by subject and topic, searchable, printable. */
export default function FormulaBook() {
  useFocus("revision", true, true);
  const { data, isLoading } = useQuery({ queryKey: ["formula-book"], queryFn: api.formulaBook });
  const [subject, setSubject] = useState("all");
  const [q, setQ] = useState("");
  const sheet = useRef<HTMLDivElement>(null);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data ?? [])
      .filter((s) => subject === "all" || s.subject === subject)
      .map((s) => ({
        ...s,
        topics: s.topics
          .map((t) => ({ ...t, formulas: t.formulas.filter((f) => !needle || f.text.toLowerCase().includes(needle) || t.topic.toLowerCase().includes(needle)) }))
          .filter((t) => t.formulas.length),
      }))
      .filter((s) => s.topics.length);
  }, [data, subject, q]);
  const total = (data ?? []).reduce((n, s) => n + s.count, 0);

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <PageHeader eyebrow="Revise" title="Formula book"
        subtitle={total ? `${total} formulas from your lectures, grouped by topic — perfect for the night before.` : "Formulas from your board notes collect here automatically."}
        actions={total > 0 && (
          <Button icon={<Printer className="h-4 w-4" />} onClick={() => sheet.current && printNode(sheet.current, "Formula book")}>Print / Save PDF</Button>
        )} />

      {!!data?.length && (
        <div className="flex flex-wrap items-center gap-3">
          <Segmented size="sm" value={subject} onChange={setSubject}
            options={[{ value: "all", label: "All" }, ...data.map((s) => ({ value: s.subject, label: `${s.subject} · ${s.count}` }))]} />
          <div className="relative min-w-[220px] flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search formulas or topics…" className="h-9 pl-9" />
          </div>
        </div>
      )}

      {isLoading && <Skeleton className="h-72" />}
      {data && !data.length && (
        <Card><EmptyState className="py-14" icon={<Sigma className="h-6 w-6" />} title="No formulas yet"
          body="Capture a lecture — every formula the teacher writes is collected here, ready to revise."
          action={<Link to="/app/studio"><Button variant="primary">Start a lecture</Button></Link>} /></Card>
      )}
      {data && !!data.length && !shown.length && <p className="py-10 text-center text-sm text-muted">No formula matches “{q}”.</p>}

      <div ref={sheet} className="space-y-5">
        {shown.map((s) => (
          <Card key={s.subject} className="overflow-hidden">
            <div className="flex items-center gap-2 border-b border-line px-5 py-3">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: subjectColor(s.subject) }} />
              <h2 className="font-semibold">{s.subject}</h2>
            </div>
            <div className="divide-y divide-line">
              {s.topics.map((t) => (
                <div key={t.topic} className="break-inside-avoid px-5 py-4">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold text-fg-soft">{t.topic}</h3>
                    <Link to={`/app/library/${t.formulas[0].session_id}`} className="no-print inline-flex items-center gap-1 text-xs text-muted hover:text-accent">
                      Lecture <ArrowRight className="h-3 w-3" />
                    </Link>
                  </div>
                  <ul className="space-y-1.5">
                    {t.formulas.map((f) => (
                      <li key={f.note_id + f.text} className="rounded-lg bg-bg-soft px-3 py-2">
                        <Markdown className="text-[14px]">{asFormula(f.text)}</Markdown>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
