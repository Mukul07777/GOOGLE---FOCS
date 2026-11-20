import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, BookOpen, Camera, Clock, MonitorPlay, Pin, Search, Sigma, X } from "lucide-react";
import { motion } from "motion/react";
import { useDeferredValue, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Lightbox, PageHeader } from "@/components/common";
import { NoteCard } from "@/components/NoteCard";
import { Button } from "@/components/ui/button";
import { Badge, EmptyState, Input, Segmented, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { cn, formatDate, formatMinutes, subjectColor } from "@/lib/utils";
import { useT } from "@/lib/i18n";

export default function Library() {
  const tr = useT();
  const [q, setQ] = useState("");
  const query = useDeferredValue(q.trim());
  const [subject, setSubject] = useState<string>("All");
  const [view, setView] = useState<"lectures" | "pinned">("lectures");
  const [zoom, setZoom] = useState<string | null>(null);

  const { data: sessions, isLoading } = useQuery({ queryKey: ["sessions"], queryFn: () => api.sessions({ limit: 200 }) });
  const searching = query.length >= 2;
  const { data: results, isFetching } = useQuery({
    queryKey: ["notes", "search", query, view],
    queryFn: () => api.notes({ q: searching ? query : undefined, pinned: view === "pinned" ? true : undefined, limit: 40 }),
    enabled: searching || view === "pinned",
  });

  const subjects = useMemo(() => ["All", ...Array.from(new Set((sessions ?? []).map((s) => s.subject || "General")))], [sessions]);
  const visible = (sessions ?? []).filter((s) => (subject === "All" || (s.subject || "General") === subject) && (s.note_count > 0 || s.is_active));

  return (
    <div>
      <PageHeader title={tr("Library")} subtitle={tr("Every lecture you've captured, searchable down to a single formula.")}
        actions={<>
          <Link to="/app/formulas"><Button icon={<Sigma className="h-4 w-4" />}>{tr("Formula book")}</Button></Link>
          <Link to="/app/studio"><Button variant="primary" icon={<MonitorPlay className="h-4 w-4" />}>{tr("New lecture")}</Button></Link>
        </>} />

      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search all notes — try “torque” or “PV = nRT”" className="pl-10 pr-10" />
          {q && <button onClick={() => setQ("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-fg" aria-label="Clear"><X className="h-4 w-4" /></button>}
        </div>
        <Segmented value={view} onChange={setView} options={[
          { value: "lectures", label: tr("Lectures"), icon: <BookOpen className="h-3.5 w-3.5" /> },
          { value: "pinned", label: tr("Pinned"), icon: <Pin className="h-3.5 w-3.5" /> },
        ]} />
      </div>

      {searching || view === "pinned" ? (
        <div className="space-y-3">
          <div className="text-sm text-muted">{isFetching ? "Searching…" : `${results?.total ?? 0} ${searching ? `boards match “${query}”` : "pinned boards"}`}</div>
          {results?.items.map((n) => (
            <div key={n.id}>
              <Link to={`/app/library/${n.session_id}`} className="mb-1.5 inline-flex items-center gap-1 text-xs text-muted hover:text-accent">
                Open lecture <ArrowUpRight className="h-3 w-3" />
              </Link>
              <NoteCard note={n} onZoom={setZoom} />
            </div>
          ))}
          {results && results.total === 0 && (
            <EmptyState icon={searching ? <Search className="h-6 w-6" /> : <Pin className="h-6 w-6" />}
              title={tr(searching ? "No boards match" : "Nothing pinned yet")}
              body={tr(searching ? "Try a different word or formula." : "Pin important boards from any lecture to find them here.")} />
          )}
        </div>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap gap-2">
            {subjects.map((s) => (
              <button key={s} onClick={() => setSubject(s)}
                className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[13px] transition pointer-coarse:py-2.5",
                  subject === s ? "border-accent/50 bg-accent-soft text-fg" : "border-line text-muted hover:text-fg")}>
                {s !== "All" && <span className="h-2 w-2 rounded-full" style={{ background: subjectColor(s) }} />}{s}
              </button>
            ))}
          </div>
          {isLoading && <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-44" />)}</div>}
          {!isLoading && visible.length === 0 && (
            <EmptyState icon={<BookOpen className="h-6 w-6" />} title={tr("No lectures here yet")}
              body={tr("Start a live lecture or upload a board photo — your notes will be organised here automatically.")}
              action={<Link to="/app/studio"><Button variant="primary">{tr("Start a lecture")}</Button></Link>} />
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {visible.map((s, i) => (
              <motion.div key={s.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i * 0.03, 0.3) }}>
                <Link to={`/app/library/${s.id}`} className="panel group relative flex h-full flex-col overflow-hidden p-5 transition hover:-translate-y-0.5 hover:border-line-strong">
                  <div className="absolute inset-x-0 top-0 h-1" style={{ background: subjectColor(s.subject) }} />
                  <div className="flex items-start justify-between gap-3">
                    <Badge dot={subjectColor(s.subject)}>{s.subject || "General"}</Badge>
                    {s.is_active ? <Badge tone="bad"><span className="live-dot scale-75" />Live</Badge> : s.source === "upload" ? <Camera className="h-4 w-4 text-muted" /> : <MonitorPlay className="h-4 w-4 text-muted" />}
                  </div>
                  <h3 className="mt-4 line-clamp-2 text-[15px] font-semibold leading-snug tracking-tight">{s.title || "Untitled lecture"}</h3>
                  <div className="mt-auto flex items-center gap-3 pt-5 text-xs text-muted">
                    <span>{formatDate(s.started_at)}</span>
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{formatMinutes(s.duration_min)}</span>
                    <span className="ml-auto rounded-md bg-elev-2 px-1.5 py-0.5 font-medium text-fg-soft">{s.note_count} boards</span>
                  </div>
                  {s.summary && <div className="mt-3 rounded-lg bg-accent-soft px-2 py-1 text-[11px] font-medium text-accent">Revision sheet ready</div>}
                </Link>
              </motion.div>
            ))}
          </div>
        </>
      )}
      <Lightbox src={zoom} onClose={() => setZoom(null)} />
    </div>
  );
}
