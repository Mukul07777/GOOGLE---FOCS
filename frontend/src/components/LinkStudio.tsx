import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleStop, Lightbulb, Loader2, MessageCircleQuestion, Sparkles, Target } from "lucide-react";
import { AnimatePresence } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Companion, type FocusNote } from "@/components/Companion";
import type { Confidence } from "@/components/ConfidenceLock";
import { Lightbox } from "@/components/common";
import { FocusBar, FocusButton, NotesSheet, useLectureFocus, useUnseen } from "@/components/LectureFocus";
import { LiveQuizDialog, type LiveQuestion } from "@/components/LiveQuiz";
import { NoteCard } from "@/components/NoteCard";
import { loadApi, type YTPlayer } from "@/components/SyncedYouTube";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Card, EmptyState, Segmented, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useFocus } from "@/lib/focus";
import type { SessionEnd, StudySession } from "@/lib/types";
import { cn, formatDuration } from "@/lib/utils";

const PLAYING = 1;
const ENDED = 0;
const CLIP_S = 150;      // a note per two and a half minutes watched
const MIN_FLUSH_S = 45;  // a shorter stretch (paused, skipped ahead) waits to grow, unless the lecture ends
const LOOK_S = 2;        // how often the player is looked at

function videoId(url: string | null): string | null {
  const m = (url ?? "").match(/[?&]v=([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

const clock = (s: number) => {
  const t = Math.max(0, Math.floor(s));
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
};

type Status = { kind: "loading" | "ready" | "writing" | "wrote" | "nothing" | "allowance" | "error"; text?: string };

/**
 * Lecture by link: the YouTube lecture plays here, inside Focs. Phones can't share a tab, so this is how a phone gets
 * live notes: every couple of minutes watched, that stretch of the video is written up (the server's AI watches the
 * same stretch: board and voice). Rewinding costs nothing; skipping ahead starts a new stretch.
 */
export function LinkStudio({ session: initial, onEnded }: { session: StudySession; onEnded: (r: SessionEnd) => void }) {
  const qc = useQueryClient();
  const [session] = useState(initial);
  const vid = videoId(session.video_url);
  const hostRef = useRef<HTMLDivElement>(null);
  const player = useRef<YTPlayer | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "loading" });
  const [playing, setPlaying] = useState(false);
  const [stretch, setStretch] = useState(0);  // seconds watched since the last note
  const clipStart = useRef<number | null>(null);
  const lastPos = useRef<number | null>(null);
  const queue = useRef<[number, number][]>([]);
  const sending = useRef(false);
  const ending = useRef(false);
  const mounted = useRef(true);
  const watchedSecs = useRef(0);
  const posKey = `focs-link-pos-${session.id}`;

  const [quiz, setQuiz] = useState<LiveQuestion | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [confidence, setConfidence] = useState<Confidence | null>(null);
  const [quizEvery, setQuizEvery] = useState<"off" | "5" | "10">(() => {
    try { return (localStorage.getItem("focs-quiz-every") as "off" | "5" | "10") || "5"; } catch { return "5"; }
  });
  const lastQuizAt = useRef(0);
  const quizRef = useRef<LiveQuestion | null>(null);
  quizRef.current = quiz;
  const [popLoading, setPopLoading] = useState(false);
  const [tab, setTab] = useState<"notes" | "ask">("notes");
  const [focusNote, setFocusNote] = useState<FocusNote | null>(null);
  const [zoom, setZoom] = useState<string | null>(null);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [lastNoteId, setLastNoteId] = useState<number | null>(null);
  const { focus, canFocus, setFocus } = useLectureFocus();
  const [sheet, setSheet] = useState(false);
  const focusRef = useRef(focus);
  focusRef.current = focus;

  const { data: detail } = useQuery({ queryKey: ["session", session.id], queryFn: () => api.session(session.id) });
  const notes = [...(detail?.notes ?? [])].reverse();
  const notesCount = detail?.notes.length ?? 0;
  const unseen = useUnseen(notesCount, sheet || !focus);
  useEffect(() => () => { mounted.current = false; }, []);
  useFocus("lecture", playing);

  const showQuiz = useCallback((q: LiveQuestion) => {
    setPicked(null);
    setConfidence(null);
    setQuiz(q);
    lastQuizAt.current = watchedSecs.current;
  }, []);

  /* -------- the stretches watched go to the server one at a time; a busy AI gets the same stretch again later */
  const pump = useCallback(async () => {
    if (sending.current) return;
    const next = queue.current.shift();
    if (!next) return;
    sending.current = true;
    setStatus({ kind: "writing", text: `${clock(next[0])}–${clock(next[1])}` });
    try {
      const r = await api.sendClip(session.id, next[0], next[1]);
      if (!mounted.current) return;
      if (r.status === "created" && r.note) {
        setLastNoteId(r.note.id);
        qc.invalidateQueries({ queryKey: ["session", session.id] });
        if (!ending.current && !focusRef.current) toast.success(`New notes: ${r.note.topic ?? "lecture notes"}`);  // focus mode: a dot on Notes, nothing over the lecture
        setStatus({ kind: "wrote", text: r.note.topic ?? undefined });
        if (r.checkpoint && !quizRef.current && !ending.current) showQuiz({ ...r.checkpoint, kind: "checkpoint" });
      } else if (r.status === "busy") {
        setStatus({ kind: "error", text: "The AI is busy. Trying that part again in a moment." });
        setTimeout(() => { queue.current.unshift(next); void pump(); }, 30_000);
      } else if (r.status === "allowance") {
        setStatus({ kind: "allowance" });
      } else {
        setStatus({ kind: r.status === "nothing" ? "nothing" : "wrote" });
      }
    } catch (e) {
      setStatus({ kind: "error", text: e instanceof ApiError ? e.message : "Couldn't write notes for that part" });
    } finally {
      sending.current = false;
      if (queue.current.length) void pump();
    }
  }, [session.id, qc, showQuiz]);

  const flush = useCallback((minimum: number) => {
    const s = clipStart.current, e = lastPos.current;
    if (s === null || e === null || e - s < minimum) return;
    queue.current.push([s, e]);
    clipStart.current = e;
    setStretch(0);
    void pump();
  }, [pump]);

  /* -------- the player */
  useEffect(() => {
    if (!vid || !hostRef.current) return;
    let cancelled = false;
    const el = document.createElement("div");
    hostRef.current.innerHTML = "";
    hostRef.current.appendChild(el);
    let start = 0;
    try { start = Number(localStorage.getItem(posKey)) || 0; } catch { /* private mode */ }
    void loadApi().then(() => {
      if (cancelled || !window.YT) return;
      player.current = new window.YT.Player(el, {
        videoId: vid, width: "100%", height: "100%",
        playerVars: { rel: 0, modestbranding: 1, playsinline: 1, start: Math.floor(start) },
        events: {
          onReady: () => setStatus({ kind: "ready" }),
          onStateChange: (e: { data: number }) => {
            setPlaying(e.data === PLAYING);
            if (e.data === ENDED) flush(10);
            else if (e.data !== PLAYING) flush(MIN_FLUSH_S);
          },
          onError: () => setStatus({ kind: "error", text: "This video can't be played here (it may be private or blocked from embedding)." }),
        },
      });
    });
    return () => { cancelled = true; player.current?.destroy(); player.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vid]);

  // every two seconds: how far the lecture has played, and whether a stretch is ready to be written up
  useEffect(() => {
    const t = setInterval(() => {
      const p = player.current;
      if (!p || ending.current) return;
      let pos: number;
      try { pos = p.getCurrentTime(); } catch { return; }
      const isPlaying = p.getPlayerState() === PLAYING;
      if (!isPlaying) { lastPos.current = pos; return; }
      const rate = p.getPlaybackRate() || 1;
      const prev = lastPos.current;
      if (clipStart.current === null || prev === null) clipStart.current = pos;
      else if (pos < prev - 3 || pos > prev + LOOK_S * rate + 6) {
        // jumped: what was watched before the jump is one stretch, and a new one starts here
        flush(MIN_FLUSH_S);
        clipStart.current = pos;
      } else {
        watchedSecs.current += LOOK_S;
      }
      lastPos.current = pos;
      try { localStorage.setItem(posKey, String(Math.floor(pos))); } catch { /* private mode */ }
      setStretch(pos - (clipStart.current ?? pos));
      if (pos - (clipStart.current ?? pos) >= CLIP_S) flush(CLIP_S);
      // timed pop quizzes, counted in lecture actually watched
      const due = quizEvery !== "off" && watchedSecs.current - lastQuizAt.current >= Number(quizEvery) * 60;
      if (due && notesCount > 0 && !quizRef.current && !popLoadingRef.current) void popQuiz();
    }, LOOK_S * 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flush, quizEvery, notesCount]);

  /* -------- quizzes */
  const popLoadingRef = useRef(false);
  const popQuiz = async (manual = false) => {
    if (popLoadingRef.current) return;
    popLoadingRef.current = true;
    setPopLoading(true);
    try {
      const q = await api.sessionPopQuiz(session.id);
      if (mounted.current && !quizRef.current) { player.current?.pauseVideo(); showQuiz({ ...q, kind: "pop" }); }
    } catch (e) {
      lastQuizAt.current = watchedSecs.current - Math.max(0, Number(quizEvery) * 60 - 60);
      if (manual) toast.message(e instanceof Error ? e.message : "Couldn't write a question right now.");
    } finally {
      popLoadingRef.current = false;
      setPopLoading(false);
    }
  };
  const answerQuiz = (i: number, c: Confidence) => {
    if (!quiz || picked !== null) return;
    setPicked(i);
    setConfidence(c);
    api.attempt({ question: quiz.question, q_type: quiz.kind, correct: i === quiz.answer_index, topic: quiz.topic,
      subject: session.subject ?? "", session_id: session.id, confidence: c }).catch(() => undefined);
  };
  const closeQuiz = () => { setQuiz(null); setPicked(null); lastQuizAt.current = watchedSecs.current; };
  const changeQuizEvery = (v: "off" | "5" | "10") => {
    setQuizEvery(v);
    lastQuizAt.current = watchedSecs.current;
    try { localStorage.setItem("focs-quiz-every", v); } catch { /* private mode */ }
  };

  const end = useMutation({
    mutationFn: async () => {
      player.current?.pauseVideo();
      flush(20);  // the last few minutes watched belong in the revision sheet too
      ending.current = true;
      for (let i = 0; (sending.current || queue.current.length) && i < 240; i++) await new Promise((r) => setTimeout(r, 250));
      return api.endSession(session.id);
    },
    onError: () => { ending.current = false; },
    onSuccess: (r) => {
      try { localStorage.removeItem(posKey); } catch { /* private mode */ }
      qc.invalidateQueries({ queryKey: ["active-session"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
      qc.invalidateQueries({ queryKey: ["card-stats"] });
      onEnded(r);
    },
  });

  const left = Math.max(0, CLIP_S - stretch);
  const line: Record<Status["kind"], string> = {
    loading: "Loading the lecture…",
    ready: "Press play. Notes are written as you watch.",
    writing: `Writing notes for ${status.text ?? "the last part"}…`,
    wrote: status.text ? `Notes added: ${status.text}` : "Up to date",
    nothing: "No teaching in that part, so no notes",
    allowance: "Today's lecture time is used up. The video plays on; notes resume with your next allowance.",
    error: status.text ?? "Something went wrong",
  };
  const calm = ["ready", "wrote", "nothing"].includes(status.kind);  // nothing to report: say where the next notes are
  const shown = calm && playing ? `Watching · next notes in ${formatDuration(left)}`
    : calm && status.kind !== "ready" ? `Paused · ${line[status.kind]}` : line[status.kind];

  if (!vid) return <Card className="p-6 text-sm text-muted">This lecture has no video link. End it and start again with a YouTube link.</Card>;

  return (
    <div className="space-y-4">
      <div className={cn("flex gap-3", focus ? "items-center justify-between" : "flex-col md:flex-row md:items-center md:justify-between")}>
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-bad">
            <span className="live-dot" /> Live · from a link
          </div>
          <h1 className={cn("mt-1 leading-tight", focus ? "truncate text-[18px]" : "line-clamp-2 text-[22px] sm:text-[30px]")}>{session.title || "Untitled lecture"}</h1>
        </div>
        <div className="flex gap-2 self-start md:self-auto">
          {canFocus && !focus && <FocusButton onClick={() => setFocus(true)} />}
          <Button variant="danger" size={focus ? "sm" : undefined} onClick={() => setConfirmEnd(true)} icon={<CircleStop className="h-4 w-4" />}>End lecture</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          {/* focus mode: the lecture stays at the top while anything below it scrolls */}
          <Card className={cn("overflow-hidden", focus && "sticky top-0 z-30")}>
            <div className="relative aspect-video w-full bg-black">
              <div ref={hostRef} className="absolute inset-0 [&>iframe]:h-full [&>iframe]:w-full" />
            </div>
            <div className="flex items-center gap-2 border-t border-line px-4 py-3 text-sm" role="status" aria-live="polite">
              {status.kind === "writing" ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-accent-2" />
                : <span className={cn("h-2 w-2 shrink-0 rounded-full", playing ? "bg-ok" : status.kind === "error" || status.kind === "allowance" ? "bg-warn" : "bg-muted")} />}
              <span className={cn("min-w-0 flex-1", status.kind === "error" || status.kind === "allowance" ? "text-warn" : "text-fg-soft")}>{shown}</span>
              <span className="hidden shrink-0 text-xs text-muted sm:inline">{notesCount} {notesCount === 1 ? "note" : "notes"}</span>
            </div>
            {playing && (
              <div className="h-1 bg-elev-2" aria-hidden="true">
                <div className="h-full bg-gradient-brand transition-[width] duration-1000" style={{ width: `${Math.min(100, (100 * stretch) / CLIP_S)}%` }} />
              </div>
            )}
            {focus && (
              <div className="border-t border-line pt-2">
                <FocusBar notes={notesCount} unseen={unseen} onNotes={() => { setTab("notes"); setSheet(true); }} onAsk={() => { setTab("ask"); setSheet(true); }}
                  onQuiz={() => void popQuiz(true)} quizLoading={popLoading} quizDisabled={!notesCount} onExit={() => setFocus(false)} />
              </div>
            )}
          </Card>

          {!focus && <Card className="p-4">
            <div className="flex flex-wrap items-center gap-3">
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent"><Target className="h-4 w-4" /></div>
              <div className="min-w-0 flex-1 basis-48">
                <div className="text-sm font-semibold">Pop quizzes</div>
                <div className="text-xs text-muted">{!notesCount ? "Start after the first notes are written" : quizEvery === "off" ? "Off: tap “Quiz me now” whenever you like" : popLoading ? "Writing a question…" : "The video pauses for each one"}</div>
              </div>
              <Segmented size="sm" value={quizEvery} onChange={changeQuizEvery} options={[
                { value: "off", label: "Off" }, { value: "5", label: "5 min" }, { value: "10", label: "10 min" },
              ]} />
            </div>
            <Button size="sm" variant="secondary" className="mt-3" onClick={() => void popQuiz(true)} loading={popLoading} disabled={!notesCount}
              icon={<Target className="h-3.5 w-3.5" />}>Quiz me now</Button>
          </Card>}
        </div>

        <NotesSheet focus={focus} open={sheet} onClose={() => setSheet(false)} className="contents">
        <Card className={cn("flex flex-col overflow-hidden", focus ? "min-h-0 flex-1 rounded-none border-0" : "h-[70dvh] min-h-[420px] xl:sticky xl:top-4 xl:h-[calc(100dvh-190px)] xl:min-h-[560px]")}>
          <div className="border-b border-line px-3 py-2.5">
            <Segmented value={tab} onChange={setTab} options={[
              { value: "notes", label: `Notes${notesCount ? ` · ${notesCount}` : ""}`, icon: <Sparkles className="h-3.5 w-3.5" /> },
              { value: "ask", label: "Ask a doubt", icon: <MessageCircleQuestion className="h-3.5 w-3.5" /> },
            ]} />
          </div>
          <div className={cn("min-h-0 flex-1 space-y-3 overflow-y-auto bg-bg-soft/40 p-3 sm:p-4", tab !== "notes" && "hidden")}>
            {!detail && <><Skeleton className="h-40" /><Skeleton className="h-40" /></>}
            {detail && notes.length === 0 && (
              <EmptyState icon={<Lightbulb className="h-6 w-6" />} title="Your notes will appear here"
                body="Play the lecture. Every couple of minutes, Focs writes up what the teacher wrote and said." />
            )}
            <AnimatePresence initial={false}>
              {notes.map((n, i) => <NoteCard key={n.id} note={n} index={notes.length - i} onZoom={setZoom} highlight={n.id === lastNoteId}
                onAsk={(note) => { setFocusNote({ id: note.id, topic: note.topic }); setTab("ask"); }} />)}
            </AnimatePresence>
          </div>
          <Companion sessionId={session.id} focus={focusNote} onClearFocus={() => setFocusNote(null)} className={cn("min-h-0 flex-1", tab !== "ask" && "hidden")} />
        </Card>
        </NotesSheet>
      </div>

      <LiveQuizDialog q={quiz} picked={picked} onPick={answerQuiz} onClose={closeQuiz} sessionId={session.id} subject={session.subject} confidence={confidence} />
      <Lightbox src={zoom} onClose={() => setZoom(null)} />
      <Dialog open={confirmEnd} onClose={() => !end.isPending && setConfirmEnd(false)} title="End this lecture?"
        subtitle="Focs writes up the last part you watched, then a revision sheet and flashcards from all of it.">
        {end.isPending ? (
          <div className="space-y-3 py-2">
            <div className="flex items-center gap-2 text-sm text-fg-soft"><Sparkles className="h-4 w-4 animate-pulse text-accent" />Writing your revision sheet…</div>
            <Skeleton className="h-3 w-4/5" /><Skeleton className="h-3 w-3/5" />
          </div>
        ) : (
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmEnd(false)}>Keep watching</Button>
            <Button variant="primary" onClick={() => end.mutate()}>End & summarise</Button>
          </div>
        )}
      </Dialog>
    </div>
  );
}

