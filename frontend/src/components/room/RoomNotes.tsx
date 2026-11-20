import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookmarkPlus, Camera, CircleStop, Loader2, Pause, Play, ScanText, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { boardChanged, isCaptureSupported, LectureCapture } from "@/lib/capture";
import type { FrameStatus, Note } from "@/lib/types";
import { steadyInterval } from "@/lib/focus";
import { formatClock } from "@/lib/utils";
import type { NoteTaker } from "./types";

const STATUS: Partial<Record<FrameStatus | "reading", string>> = {
  reading: "Reading the board…", created: "New board captured", updated: "Board grew — notes updated",
  unchanged: "Board unchanged", duplicate: "Same board — nothing new", no_text: "No writing on the board yet",
  not_lecture: "Not lecture content", busy: "Still reading the last board",
  growing: "Following the board — its notes come when the teacher moves on",
};

/**
 * Shared board notes: one member shares this tab (cropped to the player), Focs reads the board off the video,
 * and the notes appear for everyone in the room as they're written.
 */
export function RoomNotes({ code, notes, noteTaker, myId, isHost, frameRef, hasVideo }: {
  code: string;
  notes: Note[];
  noteTaker: NoteTaker | null;
  myId?: number;
  isHost: boolean;
  frameRef: RefObject<HTMLDivElement | null>;
  hasVideo: boolean;
}) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const capture = useRef<LectureCapture | null>(null);
  const session = useRef<number | null>(null);
  const lastSig = useRef<Uint8Array | null>(null);
  const inflight = useRef(false);
  const settleAt = useRef<number | null>(null); // a growing board gets written up once it's still past this time
  const [taking, setTaking] = useState(false);
  const [paused, setPaused] = useState(false); // the tab stays shared; boards just aren't read until resumed
  const [status, setStatus] = useState<string>("");
  const [starting, setStarting] = useState(false);

  const stopLocal = useCallback(() => {
    capture.current?.stop();
    capture.current = null;
    session.current = null;
    lastSig.current = null;
    settleAt.current = null;
    setTaking(false);
    setPaused(false);
    setStatus("");
  }, []);

  const start = async (takeOver = false) => {
    const frame = frameRef.current;
    if (!frame) return;
    setStarting(true);
    const c = new LectureCapture();
    try {
      await c.startThisTab(frame); // must run inside the click
    } catch {
      setStarting(false);
      return toast.message("Sharing cancelled — choose “This tab” to take notes for the room.");
    }
    try {
      const { session_id } = await api.startRoomNotes(code, takeOver);
      capture.current = c;
      session.current = session_id;
      c.onEnded = () => { stopLocal(); void api.stopRoomNotes(code).catch(() => undefined); };
      setTaking(true);
      setStatus("Watching the board…");
    } catch (e) {
      c.stop();
      toast.error(e instanceof ApiError ? e.message : "Couldn't start taking notes");
    } finally {
      setStarting(false);
    }
  };

  const stop = () => {
    stopLocal();
    void api.stopRoomNotes(code).catch(() => undefined);
  };

  // someone else took over: our capture stops
  useEffect(() => {
    if (taking && noteTaker && noteTaker.id !== myId) {
      stopLocal();
      toast.message(`${noteTaker.name} is taking notes for the room now.`);
    }
  }, [noteTaker, myId, taking, stopLocal]);
  useEffect(() => () => capture.current?.stop(), []);

  // every 4 s: only boards that changed are read
  useEffect(() => {
    if (!taking || paused) return;
    return steadyInterval(async () => {
      const c = capture.current;
      if (!c?.active || inflight.current || !session.current) return;
      const sig = c.peek();
      const unchanged = !!lastSig.current && !boardChanged(sig, lastSig.current);
      const settle = unchanged && settleAt.current !== null && Date.now() >= settleAt.current;
      if (unchanged && !settle) return settleAt.current === null ? setStatus(STATUS.unchanged!) : undefined;
      const grab = settle ? null : await c.grab();
      if (!settle && !grab) return;
      inflight.current = true;
      setStatus(STATUS.reading!);
      try {
        // the teacher stopped writing: one write-up of the finished board (the room gets it over the socket)
        const res = grab ? await api.sendFrame(session.current, grab.blob) : await api.settleBoard(session.current);
        if (grab && res.status !== "busy") lastSig.current = grab.signature;
        if (res.status === "growing") settleAt.current = Date.now() + (res.settle_after ?? 20) * 1000;
        else if (res.status !== "busy") settleAt.current = null;
        setStatus(STATUS[res.status] ?? "");
      } catch (e) {
        setStatus(e instanceof ApiError ? e.message : "Couldn't read that frame");
      } finally {
        inflight.current = false;
      }
    }, 4000);
  }, [taking, paused]);

  const togglePause = () => {
    lastSig.current = null; // on resume the board on screen is read afresh
    settleAt.current = null;
    setStatus(paused ? "Watching the board…" : "Paused");
    setPaused(!paused);
  };

  const save = useMutation({
    mutationFn: () => api.saveRoomNotes(code),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["overview"] });
      toast.success(`${r.notes} board${r.notes === 1 ? "" : "s"} saved to your library`, {
        action: { label: "Open", onClick: () => navigate(`/app/library/${r.session_id}`) },
      });
    },
  });

  const someoneElse = noteTaker && noteTaker.id !== myId;
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="space-y-2 border-b border-line p-3">
        {taking ? (
          <div className="flex items-center gap-2 rounded-xl border border-ok/30 bg-ok/10 px-3 py-2 text-xs">
            {!paused && <span className="live-dot" />}
            <span className="flex-1 text-fg-soft">{paused ? "Notes paused" : "You're taking notes for the room"} · {status}</span>
            <Button size="sm" variant="ghost" onClick={togglePause}
              icon={paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}>{paused ? "Resume" : "Pause"}</Button>
            <Button size="sm" variant="ghost" onClick={stop} icon={<CircleStop className="h-3.5 w-3.5" />}>Stop</Button>
          </div>
        ) : someoneElse ? (
          <div className="flex items-center gap-2 rounded-xl border border-line bg-bg-soft px-3 py-2 text-xs text-muted">
            <ScanText className="h-3.5 w-3.5 text-accent" />
            <span className="flex-1"><b className="text-fg">{noteTaker!.name}</b> is taking notes for everyone</span>
            {isHost && <Button size="sm" variant="ghost" loading={starting} onClick={() => start(true)}>Take over</Button>}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-line-strong p-3 text-center">
            <p className="text-xs leading-relaxed text-muted">
              One person shares this tab and Focs reads the board straight off the video — everyone gets the notes live.
            </p>
            <Button size="sm" variant="primary" className="mt-2" loading={starting} disabled={!hasVideo || !isCaptureSupported()}
              onClick={() => start(false)} icon={<Camera className="h-3.5 w-3.5" />}>
              Take notes for the room
            </Button>
            {!hasVideo && <p className="mt-1.5 text-[11px] text-muted">Starts once a lecture is playing.</p>}
          </div>
        )}
        {notes.length > 0 && (
          <Button size="sm" variant="secondary" className="w-full" loading={save.isPending} onClick={() => save.mutate()}
            icon={<BookmarkPlus className="h-3.5 w-3.5" />}>Save all {notes.length} to my library</Button>
        )}
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {!notes.length && (
          <div className="py-10 text-center text-sm text-muted">
            <Sparkles className="mx-auto mb-2 h-5 w-5 text-accent" />
            Board notes from the lecture appear here for everyone.
          </div>
        )}
        <AnimatePresence initial={false}>
          {[...notes].reverse().map((n, i) => (
            <motion.article key={n.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="panel p-4">
              <div className="mb-2 flex items-center gap-2">
                <span className="grid h-6 w-6 place-items-center rounded-md bg-elev-2 font-mono text-[11px] text-muted">{notes.length - i}</span>
                <span className="min-w-0 flex-1 truncate text-sm font-semibold">{n.topic || "Board notes"}</span>
                {n.subject && <Badge>{n.subject}</Badge>}
                <span className="text-[11px] text-muted">{formatClock(n.captured_at)}</span>
              </div>
              <Markdown className="text-[13.5px]">{n.ai_notes || "_No notes_"}</Markdown>
            </motion.article>
          ))}
        </AnimatePresence>
        {taking && status === STATUS.reading && (
          <div className="flex items-center gap-2 text-xs text-muted"><Loader2 className="h-3.5 w-3.5 animate-spin" />Reading the board…</div>
        )}
      </div>
    </div>
  );
}
