import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck, Layers, Plus, Search, Sparkles, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, EmptyState, Input, Kbd, Label, ProgressBar, Segmented, Skeleton, Textarea } from "@/components/ui/primitives";
import { useFocus } from "@/lib/focus";
import { api } from "@/lib/api";
import type { CardStats, Flashcard, Grade } from "@/lib/types";
import { cn, dueLabel } from "@/lib/utils";
import { useT } from "@/lib/i18n";

const GRADE_UI: { grade: Grade; label: string; key: string; cls: string }[] = [
  { grade: "again", label: "Again", key: "1", cls: "border-bad/30 bg-bad/10 text-bad hover:bg-bad/20" },
  { grade: "hard", label: "Hard", key: "2", cls: "border-warn/30 bg-warn/10 text-warn hover:bg-warn/20" },
  { grade: "good", label: "Good", key: "3", cls: "border-ok/30 bg-ok/10 text-ok hover:bg-ok/20" },
  { grade: "easy", label: "Easy", key: "4", cls: "border-accent-2/30 bg-accent-2/10 text-accent-2 hover:bg-accent-2/20" },
];

function Review() {
  const tr = useT();
  const qc = useQueryClient();
  const { data: due, isLoading } = useQuery({ queryKey: ["cards", "due"], queryFn: () => api.cards({ due: true }), refetchOnMount: "always" });
  const [queue, setQueue] = useState<Flashcard[] | null>(null);
  const [flipped, setFlipped] = useState(false);
  const [done, setDone] = useState(0);
  useEffect(() => { if (due && queue === null) setQueue(due); }, [due, queue]);

  const review = useMutation({
    mutationFn: ({ card, grade }: { card: Flashcard; grade: Grade }) => api.reviewCard(card.id, grade),
    onSuccess: (updated, { card: before, grade }) => {
      // The counts move with the rating straight away; the server's own numbers follow.
      qc.setQueryData<CardStats>(["card-stats"], (s) => {
        if (!s) return s;
        const learning = (c: Flashcard) => !!c.last_reviewed_at && c.repetitions < 2;
        const mature = (c: Flashcard) => c.interval_days >= 21;
        return {
          ...s,
          due: new Date(updated.due_at) > new Date() ? Math.max(0, s.due - 1) : s.due,
          new: before.last_reviewed_at ? s.new : Math.max(0, s.new - 1),
          learning: Math.max(0, s.learning + Number(learning(updated)) - Number(learning(before))),
          mature: Math.max(0, s.mature + Number(mature(updated)) - Number(mature(before))),
        };
      });
      setQueue((q) => {
        if (!q) return q;
        const rest = q.slice(1);
        return grade === "again" ? [...rest, updated] : rest; // relearn at the end of this sitting
      });
      if (grade !== "again") setDone((d) => d + 1);
      setFlipped(false);
      qc.invalidateQueries({ queryKey: ["card-stats"] });
    },
  });
  const card = queue?.[0];
  const swiped = useRef(false);  // a swipe ends in a click: it isn't a flip

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!card || review.isPending) return;
      if (e.code === "Space") { e.preventDefault(); setFlipped((f) => !f); }
      const g = GRADE_UI.find((x) => x.key === e.key);
      if (g && flipped) review.mutate({ card, grade: g.grade });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, flipped, review]);

  if (isLoading || queue === null) return <Skeleton className="mx-auto h-80 max-w-2xl" />;
  if (!card)
    return (
      <EmptyState icon={<CalendarCheck className="h-6 w-6" />} title={done ? `Session complete — ${done} cards reviewed` : tr("All caught up")}
        body="Cards come back exactly when you're about to forget them. Capture more lectures to grow your deck."
        action={<Link to="/app/studio"><Button variant="primary">Start a lecture</Button></Link>} />
    );

  const total = done + queue.length;
  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center gap-3 text-sm text-muted">
        <span>{done} / {total}</span><ProgressBar value={(100 * done) / Math.max(1, total)} className="flex-1" />
      </div>
      <div className="flip-card cursor-pointer" role="button" tabIndex={0} aria-pressed={flipped} aria-label={flipped ? "Showing the answer. Flip back to the question" : "Showing the question. Flip to see the answer"}
        onClick={() => { if (swiped.current) swiped.current = false; else setFlipped(!flipped); }} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); setFlipped(!flipped); } }}>
        {/* entrance animation and 3D flip live on separate elements: motion's inline transform would override rotateY */}
        <motion.div key={card.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="touch-pan-y"
          drag={flipped && !review.isPending ? "x" : false} dragSnapToOrigin dragElastic={0.6} dragConstraints={{ left: 0, right: 0 }}
          onDragEnd={(_, info) => {
            if (Math.abs(info.offset.x) > 8) {  // (a mouse drag ends in a click, a finger's doesn't: don't let it swallow the next tap)
              swiped.current = true;
              setTimeout(() => { swiped.current = false; }, 50);
            }
            if (Math.abs(info.offset.x) > 90) review.mutate({ card, grade: info.offset.x > 0 ? "good" : "again" });
          }}>
        <div className={cn("flip-inner relative min-h-80", flipped && "flipped")}>
          <div className="flip-face panel absolute inset-0 flex flex-col p-8">
            <div className="flex items-center gap-2 text-xs text-muted">
              {card.topic && <Badge>{card.topic}</Badge>}{card.repetitions === 0 && <Badge tone="accent">new</Badge>}
            </div>
            <div className="flex flex-1 items-center justify-center text-center"><Markdown className="text-xl text-fg">{card.front}</Markdown></div>
            <div className="text-center text-xs text-muted"><span className="pointer-coarse:hidden">Click or press <Kbd>Space</Kbd> to reveal</span><span className="hidden pointer-coarse:inline">{tr("Tap to reveal")}</span></div>
          </div>
          <div className="flip-face flip-back panel absolute inset-0 flex flex-col bg-elev p-8">
            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Answer</div>
            <div className="flex flex-1 items-center justify-center text-center"><Markdown className="text-lg text-fg">{card.back}</Markdown></div>
            <div className="hidden text-center text-xs text-muted pointer-coarse:block">{tr("Swipe right if you knew it, left to see it again")}</div>
          </div>
        </div>
        </motion.div>
      </div>
      <div className={cn("mt-5 grid grid-cols-4 gap-2 transition", !flipped && "pointer-events-none opacity-30")}>
        {GRADE_UI.map((g) => (
          <button key={g.grade} disabled={review.isPending} onClick={() => review.mutate({ card, grade: g.grade })}
            className={cn("rounded-xl border px-2 py-3 text-center transition", g.cls)}>
            <div className="text-sm font-semibold">{tr(g.label)}</div>
            <div className="mt-0.5 text-[11px] opacity-80">{card.intervals[g.grade]}<span className="pointer-coarse:hidden"> · <span className="font-mono">{g.key}</span></span></div>
          </button>
        ))}
      </div>
    </div>
  );
}

function AllCards() {
  const tr = useT();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [front, setFront] = useState("");
  const [back, setBack] = useState("");
  const { data, isLoading } = useQuery({ queryKey: ["cards", "all"], queryFn: () => api.cards() });
  const remove = useMutation({ mutationFn: api.deleteCard, onSuccess: () => { qc.invalidateQueries({ queryKey: ["cards"] }); qc.invalidateQueries({ queryKey: ["card-stats"] }); } });
  const create = useMutation({
    mutationFn: () => api.createCard({ front, back }),
    onSuccess: () => { setOpen(false); setFront(""); setBack(""); qc.invalidateQueries({ queryKey: ["cards"] }); qc.invalidateQueries({ queryKey: ["card-stats"] }); },
  });
  const list = (data ?? []).filter((c) => `${c.front} ${c.back} ${c.topic ?? ""}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div>
      <div className="mb-4 flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search cards" className="pl-10" />
        </div>
        <Button variant="primary" onClick={() => setOpen(true)} icon={<Plus className="h-4 w-4" />}>{tr("New card")}</Button>
      </div>
      {isLoading && <div className="grid grid-cols-1 gap-3 md:grid-cols-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-32" />)}</div>}
      {data?.length === 0 && <EmptyState icon={<Layers className="h-6 w-6" />} title={tr("No cards yet")} body="End a lecture or use “Make flashcards” on any board to build your deck." />}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {list.map((c) => (
          <Card key={c.id} className="group p-4">
            <div className="flex items-start justify-between gap-2">
              <Markdown className="text-sm font-medium text-fg">{c.front}</Markdown>
              <button onClick={() => remove.mutate(c.id)} className="rounded-lg p-1.5 text-muted opacity-0 transition hover:bg-elev-2 hover:text-bad group-hover:opacity-100 [@media(hover:none)]:p-2.5 [@media(hover:none)]:opacity-100" aria-label="Delete card">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
            <Markdown className="mt-2 border-t border-line pt-2 text-[13px]">{c.back}</Markdown>
            <div className="mt-3 flex items-center gap-2 text-[11px] text-muted">
              {c.topic && <Badge>{c.topic}</Badge>}
              <span className={cn("ml-auto", new Date(c.due_at) <= new Date() && "text-accent")}>{dueLabel(c.due_at)}</span>
            </div>
          </Card>
        ))}
      </div>
      <Dialog open={open} onClose={() => setOpen(false)} title={tr("New flashcard")} subtitle="Markdown and LaTeX ($E=mc^2$) are supported.">
        <div className="space-y-3">
          <div><Label>{tr("Front")}</Label><Textarea value={front} onChange={(e) => setFront(e.target.value)} placeholder="What is the moment of inertia of a ring about its axis?" /></div>
          <div><Label>{tr("Back")}</Label><Textarea value={back} onChange={(e) => setBack(e.target.value)} placeholder="$I = MR^2$" /></div>
          <div className="flex justify-end"><Button variant="primary" disabled={!front.trim() || !back.trim()} loading={create.isPending} onClick={() => create.mutate()}>{tr("Add card")}</Button></div>
        </div>
      </Dialog>
    </div>
  );
}

export default function Flashcards() {
  const tr = useT();
  useFocus("flashcards", true, true);
  const [tab, setTab] = useState<"review" | "all">("review");
  const { data: stats } = useQuery({ queryKey: ["card-stats"], queryFn: api.cardStats });
  return (
    <div>
      <PageHeader title={tr("Flashcards")} eyebrow={<span className="flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" />{tr("Spaced repetition")}</span>}
        subtitle={tr("Reviewed at exactly the moment you'd forget — the most efficient way to remember.")}
        actions={<Segmented value={tab} onChange={setTab} options={[{ value: "review", label: `${tr("Review")}${stats?.due ? ` · ${stats.due}` : ""}` }, { value: "all", label: tr("All cards") }]} />} />
      <div className={cn("mb-6 grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5", tab === "review" ? "hidden sm:grid" : "grid")}>
        {([["Due now", stats?.due, "text-accent"], ["New", stats?.new, "text-accent-2"], ["Learning", stats?.learning, "text-warn"], ["Well known", stats?.mature, "text-ok"], ["Total", stats?.total, "text-fg"]] as const).map(([l, v, c]) => (
          <Card key={l} className="p-4"><div className={cn("text-2xl font-semibold", c)}>{v ?? "–"}</div><div className="text-xs text-muted">{tr(l)}</div></Card>
        ))}
      </div>
      {tab === "review" ? <Review /> : <AllCards />}
    </div>
  );
}
