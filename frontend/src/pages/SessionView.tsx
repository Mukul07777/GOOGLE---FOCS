import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, ChevronDown, Download, Layers, MessageCircleQuestion, MonitorPlay, Pencil, Sparkles, Target, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { Note } from "@/lib/types";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Companion } from "@/components/Companion";
import { Lightbox } from "@/components/common";
import { NoteCard } from "@/components/NoteCard";
import { RevisionSheet } from "@/components/RevisionSheet";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, EmptyState, Skeleton } from "@/components/ui/primitives";
import { useFocus } from "@/lib/focus";
import { api } from "@/lib/api";
import { cn, downloadResponse, formatDate, formatMinutes, subjectColor } from "@/lib/utils";
import { Transcript } from "@/components/Transcript";
import { WaitBridge } from "@/components/WaitBridge";

/** A long lecture: every board by name, to jump to the one you want instead of scrolling through them all. */
function BoardOutline({ notes }: { notes: Note[] }) {
  const [open, setOpen] = useState(false);
  return (
    <Card className="overflow-hidden">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex min-h-12 w-full items-center justify-between gap-3 px-5 py-3 text-left">
        <span className="text-sm font-semibold">All {notes.length} boards</span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted transition", open && "rotate-180")} />
      </button>
      {open && (
        <ol className="border-t border-line">
          {notes.map((n, i) => (
            <li key={n.id} className="border-b border-line last:border-0">
              <button onClick={() => document.getElementById(`note-${n.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" })}
                className="flex min-h-11 w-full items-center gap-3 px-5 py-2 text-left text-[13.5px] hover:bg-elev-2">
                <span className="w-6 shrink-0 text-xs tabular-nums text-muted">{i + 1}</span>{n.topic || "Board notes"}
              </button>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

export default function SessionView() {
  useFocus("revision", true, true);
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [zoom, setZoom] = useState<string | null>(null);
  const [summaryOpen, setSummaryOpen] = useState(true);
  const [askOpen, setAskOpen] = useState(false);
  const { data: s, isLoading, error } = useQuery({ queryKey: ["session", id], queryFn: () => api.session(id), enabled: Number.isFinite(id) });
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState("");
  const rename = useMutation({
    mutationFn: (title: string) => api.updateSession(id, { title }),
    onSuccess: () => {
      setRenaming(false);
      qc.invalidateQueries({ queryKey: ["session", id] });
      qc.invalidateQueries({ queryKey: ["sessions"] });
      toast.success("Lecture renamed");
    },
    onError: () => toast.error("Couldn't rename it. Try again."),
  });

  const summarise = useMutation({
    mutationFn: () => api.endSession(id),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["session", id] });
      qc.invalidateQueries({ queryKey: ["active-session"] });
      toast.success(r.flashcards_created ? `Revision sheet ready · ${r.flashcards_created} flashcards added` : "Revision sheet ready");
    },
  });
  const cards = useMutation({
    mutationFn: () => api.generateCards({ session_id: id, count: 10 }),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ["card-stats"] }); toast.success(`${c.length} flashcards added`); },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteSession(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["sessions"] }); toast.success("Lecture deleted"); navigate("/app/library"); },
  });
  const exportMd = useMutation({ mutationFn: async () => downloadResponse(await api.exportSession(id), "focs-notes.md") });

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-64" /><Skeleton className="h-64" /></div>;
  if (error || !s) return <EmptyState icon={<Sparkles className="h-6 w-6" />} title="Lecture not found" action={<Link to="/app/library"><Button>Back to library</Button></Link>} />;

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="min-w-0 space-y-5">
        <div>
          <Link to="/app/library" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft className="h-4 w-4" />Library</Link>
          <div className="mt-3 flex flex-col gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge dot={subjectColor(s.subject)}>{s.subject || "General"}</Badge>
                {s.is_active && <Badge tone="bad"><span className="live-dot scale-75" />Live now</Badge>}
                <span className="text-xs text-muted">{formatDate(s.started_at, true)} · {formatMinutes(s.duration_min)} · {s.notes.length} boards</span>
              </div>
              {renaming ? (
                <form className="mt-2 flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); const t = draft.trim(); if (t && t !== s.title) rename.mutate(t); else setRenaming(false); }}>
                  <input autoFocus value={draft} maxLength={120} onChange={(e) => setDraft(e.target.value)} aria-label="Lecture name"
                    onKeyDown={(e) => e.key === "Escape" && setRenaming(false)}
                    className="min-w-0 flex-1 rounded-sm border border-line-strong bg-panel px-3 py-1.5 font-display text-[24px] outline-none focus:border-fg sm:text-[28px]" />
                  <Button type="submit" variant="primary" size="icon" loading={rename.isPending} disabled={!draft.trim()} aria-label="Save name"><Check className="h-4 w-4" /></Button>
                  <Button type="button" variant="ghost" size="icon" onClick={() => setRenaming(false)} aria-label="Cancel"><X className="h-4 w-4" /></Button>
                </form>
              ) : (
                <div className="group mt-2 flex items-start gap-2">
                  <h1 className="min-w-0 break-words text-[30px] sm:text-[34px]">{s.title || "Untitled lecture"}</h1>
                  <Button variant="ghost" size="icon-sm" className="mt-2 shrink-0 text-muted hover:text-fg" title="Rename lecture" aria-label="Rename lecture"
                    onClick={() => { setDraft(s.title ?? ""); setRenaming(true); }}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {s.is_active && <Link to="/app/studio"><Button variant="primary" icon={<MonitorPlay className="h-4 w-4" />}>Resume</Button></Link>}
              <Link to={`/app/practice?session=${s.id}`}><Button variant={s.is_active ? "secondary" : "primary"} icon={<Target className="h-4 w-4" />}>Practice</Button></Link>
              <Button onClick={() => cards.mutate()} loading={cards.isPending} disabled={!s.notes.length} icon={<Layers className="h-4 w-4" />}>Flashcards</Button>
              <Button onClick={() => exportMd.mutate()} loading={exportMd.isPending} icon={<Download className="h-4 w-4" />}>Export</Button>
              <Button variant="ghost" size="icon" onClick={() => confirm("Delete this lecture and all its boards? Flashcards you made are kept.") && remove.mutate()} aria-label="Delete lecture">
                <Trash2 className="h-4 w-4 text-bad" />
              </Button>
            </div>
          </div>
        </div>

        {s.summary ? (
          <Card className="overflow-hidden">
            <button onClick={() => setSummaryOpen(!summaryOpen)} className="flex w-full items-center justify-between px-5 py-4 text-left">
              <span className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="h-4 w-4 text-accent" />Revision sheet</span>
              <ChevronDown className={cn("h-4 w-4 text-muted transition", summaryOpen && "rotate-180")} />
            </button>
            {summaryOpen && <div className="border-t border-line bg-bg-soft/40 p-4 sm:p-5"><RevisionSheet printTitleOnly markdown={s.summary} title={s.title} meta={`${s.subject || "General"} · ${s.notes.length} boards`} /></div>}
          </Card>
        ) : s.notes.length > 0 && !s.is_active && (
          <Card className="flex flex-col items-start justify-between gap-3 p-5 sm:flex-row sm:items-center">
            <div>
              <div className="text-sm font-semibold">No revision sheet yet</div>
              <div className="text-xs text-muted">Summarise the whole lecture into key concepts, a formula sheet and flashcards.</div>
            </div>
            <Button variant="primary" loading={summarise.isPending} onClick={() => summarise.mutate()} icon={<Sparkles className="h-4 w-4" />}>Create revision sheet</Button>
          </Card>
        )}
        {summarise.isPending && <WaitBridge kind="revision" topic={s.title} />}

        <Transcript sessionId={s.id} />

        {s.notes.length === 0 ? (
          <EmptyState icon={<MonitorPlay className="h-6 w-6" />} title="No boards captured" body="This lecture has no notes yet." />
        ) : (
          <div className="space-y-4">
            {s.notes.length >= 6 && <BoardOutline notes={s.notes} />}
            {s.notes.map((n, i) => <NoteCard key={n.id} note={n} index={i + 1} onZoom={setZoom} />)}
          </div>
        )}
      </div>

      <aside className="hidden xl:block">
        <Card className="sticky top-4 flex h-[calc(100dvh-120px)] flex-col overflow-hidden">
          <div className="border-b border-line px-4 py-3 text-sm font-semibold">Ask about this lecture</div>
          <Companion sessionId={s.id} className="min-h-0 flex-1" />
        </Card>
      </aside>
      <Button variant="primary" size="icon" className="fixed bottom-[calc(5rem+env(safe-area-inset-bottom))] right-4 z-20 h-12 w-12 rounded-full shadow-2xl xl:hidden" onClick={() => setAskOpen(true)} aria-label="Ask a doubt"><MessageCircleQuestion className="h-5 w-5" /></Button>
      <Dialog open={askOpen} onClose={() => setAskOpen(false)} title="Ask about this lecture">
        <Companion sessionId={s.id} className="h-[60dvh]" />
      </Dialog>
      <Lightbox src={zoom} onClose={() => setZoom(null)} />
    </div>
  );
}
