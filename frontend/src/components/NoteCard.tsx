import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, ChevronRight, Layers, MessageCircleQuestion, MoreHorizontal, Pencil, Pin, RefreshCw, Trash2, X, Mic } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { BoardImage } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { NoteBlocks } from "@/components/NoteBlocks";
import { ReadAloud } from "@/components/ReadAloud";
import { NotesReader } from "@/components/DetailedNotes";
import { Button } from "@/components/ui/button";
import { Badge, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { Note } from "@/lib/types";
import { cn, formatClock, subjectColor, langAttr } from "@/lib/utils";

function Menu({ items }: { items: { label: string; icon: React.ReactNode; onClick: () => void; danger?: boolean }[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  return (
    <div ref={ref} className="relative">
      <Button variant="ghost" size="icon-sm" onClick={() => setOpen(!open)} aria-label="More actions"><MoreHorizontal className="h-4 w-4" /></Button>
      {open && (
        <div className="panel absolute right-0 top-9 z-20 w-52 p-1.5">
          {items.map((it) => (
            <button key={it.label} onClick={() => { setOpen(false); it.onClick(); }}
              className={cn("flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] hover:bg-elev-2 pointer-coarse:py-3", it.danger ? "text-bad" : "text-fg-soft hover:text-fg")}>
              {it.icon}{it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function NoteCard({ note, index, onZoom, highlight, onAsk }: {
  note: Note; index?: number; onZoom?: (src: string) => void; highlight?: boolean; onAsk?: (note: Note) => void;
}) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.ai_notes ?? "");

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["session", note.session_id] });
    qc.invalidateQueries({ queryKey: ["notes"] });
  };
  const update = useMutation({
    mutationFn: (b: { ai_notes?: string; is_pinned?: boolean }) => api.updateNote(note.id, b),
    onSuccess: () => { invalidate(); setEditing(false); },
  });
  const regen = useMutation({ mutationFn: () => api.regenerateNote(note.id), onSuccess: () => { invalidate(); toast.success("Notes regenerated"); } });
  const remove = useMutation({ mutationFn: () => api.deleteNote(note.id), onSuccess: () => { invalidate(); toast.success("Board removed"); } });
  const cards = useMutation({
    mutationFn: () => api.generateCards({ note_id: note.id, count: 5 }),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ["card-stats"] }); toast.success(`${c.length} flashcards added to your deck`); },
  });
  const [detailOpen, setDetailOpen] = useState(false);
  const detailed = useQuery({
    queryKey: ["note-detailed", note.id, note.updated_at], queryFn: () => api.noteDetailed(note.id), enabled: detailOpen,
    staleTime: Infinity, retry: false,
  });
  const writtenNow = detailed.data?.written_now;
  useEffect(() => { if (writtenNow) qc.invalidateQueries({ queryKey: ["usage"] }); }, [writtenNow, qc]);

  return (
    <motion.article id={`note-${note.id}`} layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className={cn("panel @container scroll-mt-16 overflow-hidden transition", highlight && "ring-2 ring-accent/40")}>
      <div className="flex items-start gap-3 px-5 pt-4">
        {typeof index === "number" && (
          <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-elev-2 font-mono text-xs text-muted">{index}</div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[15px] font-semibold tracking-tight">{note.topic || "Board notes"}</h3>
            {note.is_pinned && <Pin className="h-3.5 w-3.5 fill-warn text-warn" />}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span>{formatClock(note.captured_at)}{note.updated_at ? " · updated" : ""}</span>
            {note.subject && <Badge dot={subjectColor(note.subject)}>{note.subject}</Badge>}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon-sm" title={note.is_pinned ? "Unpin" : "Pin"} onClick={() => update.mutate({ is_pinned: !note.is_pinned })}>
            <Pin className={cn("h-4 w-4", note.is_pinned && "fill-warn text-warn")} />
          </Button>
          <Menu items={[
            ...(onAsk ? [{ label: "Ask a doubt about this", icon: <MessageCircleQuestion className="h-4 w-4" />, onClick: () => onAsk(note) }] : []),
            { label: "Make flashcards", icon: <Layers className="h-4 w-4" />, onClick: () => cards.mutate() },
            { label: "Edit notes", icon: <Pencil className="h-4 w-4" />, onClick: () => { setDraft(note.ai_notes ?? ""); setEditing(true); } },
            { label: "Regenerate with AI", icon: <RefreshCw className="h-4 w-4" />, onClick: () => regen.mutate() },
            { label: "Delete board", icon: <Trash2 className="h-4 w-4" />, danger: true, onClick: () => confirm("Delete this board and its notes?") && remove.mutate() },
          ]} />
        </div>
      </div>

      <div className={cn("grid gap-4 p-5", note.has_image && "@xl:grid-cols-[minmax(0,1fr)_220px]")}>
        <div className="min-w-0">
          {editing ? (
            <div className="space-y-2">
              <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} className="min-h-56 font-mono text-[13px]" />
              <div className="flex justify-end gap-2">
                <Button size="sm" variant="ghost" icon={<X className="h-3.5 w-3.5" />} onClick={() => setEditing(false)}>Cancel</Button>
                <Button size="sm" variant="primary" icon={<Check className="h-3.5 w-3.5" />} loading={update.isPending} onClick={() => update.mutate({ ai_notes: draft })}>Save</Button>
              </div>
            </div>
          ) : (
            <div lang={langAttr(note.language)}><NoteBlocks markdown={note.ai_notes || "_No notes_"} /></div>
          )}
          {!editing && note.ai_notes && <ReadAloud text={[note.ai_notes, note.spoken_md].filter(Boolean).join("\n\n")} className="-ml-2 mt-1" />}
          {note.spoken_md && !editing && (
            <div className="note-block note-spoken" lang={langAttr(note.language)}>
              <h4 className="note-label"><Mic className="h-3.5 w-3.5" strokeWidth={1.75} />What the teacher said</h4>
              <Markdown className="text-[13.5px]">{note.spoken_md}</Markdown>
            </div>
          )}
          {regen.isPending && <div className="mt-2 text-xs text-muted">Regenerating…</div>}
        </div>
        {note.has_image && (
          <BoardImage noteId={note.id} version={note.updated_at ?? note.captured_at} onClick={onZoom} className="aspect-video w-full rounded-xl border border-line bg-black object-contain @xl:w-[220px]" />
        )}
      </div>

      {/* optional: the detailed version of these notes, fetched when the student opens it, read in the reader */}
      <button type="button" onClick={() => setDetailOpen(true)}
        className="group flex w-full items-center gap-3 border-t border-line bg-accent-soft/30 px-5 py-3 text-left transition hover:bg-accent-soft/60">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent"><BookOpen className="h-4 w-4" /></span>
        <span className="min-w-0 flex-1">
          <span className="block text-[13.5px] font-semibold">Detailed notes</span>
          <span className="block text-xs text-muted">The full explanation, a solved exam question and common mistakes</span>
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-fg" />
      </button>
      <NotesReader open={detailOpen} onClose={() => setDetailOpen(false)} query={detailed} title={note.topic} />
    </motion.article>
  );
}
