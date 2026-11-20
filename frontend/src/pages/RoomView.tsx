import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, ArrowUp, BookmarkPlus, Bot, Check, Copy, Crown, Hand, HandHelping, Link2, Loader2, MapPinned, MessageSquare, Play, Power, ScanText, Sparkles,
  Target, Trophy, Users, Waves, X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Markdown } from "@/components/Markdown";
import { ConfidenceLock, type Confidence } from "@/components/ConfidenceLock";
import { DoubtBoard } from "@/components/room/DoubtBoard";
import { REACTIONS, ReactionBadge, reactionOf } from "@/components/room/reactions";
import { RoomNotes } from "@/components/room/RoomNotes";
import { RoomTimer, type TimerState } from "@/components/room/RoomTimer";
import type { ChatMsg, Member, NoteTaker, Score } from "@/components/room/types";
import { SyncedYouTube, type HostAction, type VideoState } from "@/components/SyncedYouTube";
import { Button } from "@/components/ui/button";
import { Badge, Card, Input, Segmented } from "@/components/ui/primitives";
import { useFocus } from "@/lib/focus";
import { api, ApiError } from "@/lib/api";
import { displayStyle } from "@/lib/math";
import type { ConfusionMeter, Note, RoomBoard } from "@/lib/types";
import { cn, LETTERS } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { useAuth } from "@/stores/auth";

interface LiveQuiz { id: string; question: string; options: string[]; deadline: number; seconds: number; server_now: number; answered: number }
interface QuizResult { id: string; answer_index: number; explanation: string; counts: number[]; correct_names: string[]; answered: number;
  leaderboard: Score[] }

const EMPTY_VIDEO: VideoState = { id: null, title: null, playing: false, position: 0, updated_at: 0, server_now: 0 };

function useRoom(code: string) {
  const token = useAuth((s) => s.token);
  const [connected, setConnected] = useState(false);
  const [me, setMe] = useState<{ id: number; host: boolean } | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [video, setVideo] = useState<VideoState>(EMPTY_VIDEO);
  const [reason, setReason] = useState("init");
  const [topic, setTopic] = useState("");
  const [skew, setSkew] = useState(0);
  const [quiz, setQuiz] = useState<LiveQuiz | null>(null);
  const [myAnswer, setMyAnswer] = useState<number | null>(null);
  const [result, setResult] = useState<QuizResult | null>(null);
  const [leaderboard, setLeaderboard] = useState<Score[]>([]);
  const [closed, setClosed] = useState<string | null>(null);
  const [reactions, setReactions] = useState<{ id: number; emoji: string; user?: string }[]>([]);
  const [noteTaker, setNoteTaker] = useState<NoteTaker | null>(null);
  const [timer, setTimer] = useState<TimerState | null>(null);
  const [confusion, setConfusion] = useState<ConfusionMeter | null>(null);  // the host's live meter
  const [lostAck, setLostAck] = useState<{ until: number; board: RoomBoard | null } | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const qc = useQueryClient();

  useEffect(() => {
    let stop = false;
    let retry = 0;
    let timeout: ReturnType<typeof setTimeout>;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      // the sign-in token goes as the first message, never in the URL (server and proxy logs keep URLs)
      const sock = new WebSocket(`${proto}://${location.host}/api/rooms/ws/${code}`);
      ws.current = sock;
      sock.onopen = () => { sock.send(JSON.stringify({ type: "auth", token: token ?? "" })); setConnected(true); retry = 0; };
      sock.onmessage = (ev) => {
        const m = JSON.parse(ev.data);
        if (m.server_now || m.video?.server_now) setSkew((m.server_now ?? m.video.server_now) - Date.now() / 1000);
        switch (m.type) {
          case "welcome":
            setMe(m.you); setMessages(m.history ?? []); setVideo(m.video); setReason("welcome"); setTopic(m.topic ?? "");
            setLeaderboard(m.leaderboard ?? []); setQuiz(m.quiz); setMyAnswer(m.my_answer ?? null); setNoteTaker(m.note_taker ?? null); setTimer(m.timer ?? null);
            setConfusion(m.confusion ?? null); break;
          case "confusion": setConfusion(m.meter); break;
          case "lost_ack":
            setLostAck({ until: Date.now() + m.wait * 1000, board: m.board ?? null });
            if (m.ok) toast.success(m.board ? `Sent. The host sees it on board ${m.board.number}: ${m.board.topic}` : "Sent to the host");
            else toast(`You can tap again in ${m.wait}s`);
            break;
          case "presence": setMembers(m.members); break;
          case "chat": case "system": case "ai": setMessages((x) => [...x.slice(-150), m]); break;
          case "video": setVideo(m.video); setReason(m.reason ?? "update"); break;
          case "topic": setTopic(m.topic); break;
          case "doubt": setMessages((x) => x.map((msg) => (msg.id === m.doubt.id ? m.doubt : msg))); break;
          case "leaderboard": setLeaderboard(m.leaderboard); break;
          case "note_taker": setNoteTaker(m.note_taker); break;
          case "timer": setTimer(m.timer); break;
          case "note":  // a board was read for the room: add it, or replace the note that grew
            qc.setQueryData<Note[]>(["room-notes", code], (list = []) =>
              list.some((n) => n.id === m.note.id) ? list.map((n) => (n.id === m.note.id ? m.note : n)) : [...list, m.note]);
            break;
          case "quiz": setQuiz(m.quiz); setMyAnswer(null); setResult(null); break;
          case "quiz_progress": setQuiz((q) => (q && q.id === m.id ? { ...q, answered: m.answered } : q)); break;
          case "quiz_result": setResult(m.result); setLeaderboard(m.result.leaderboard); break;
          case "reaction": {
            const id = Math.random();
            setReactions((r) => [...r, { id, emoji: m.emoji, user: m.user }]);
            setTimeout(() => setReactions((r) => r.filter((x) => x.id !== id)), 2600);
            break;
          }
          case "error": toast.error(m.text); break;
          case "closed": setClosed("The host closed this room."); break;
        }
      };
      sock.onclose = (ev) => {
        setConnected(false);
        if (stop) return;
        if ([4401, 4404, 4409].includes(ev.code)) return setClosed(ev.reason || "Can't join this room");
        timeout = setTimeout(connect, Math.min(8000, 800 * 2 ** retry++));
      };
    };
    connect();
    const ping = setInterval(() => ws.current?.readyState === 1 && ws.current.send(JSON.stringify({ type: "ping" })), 25_000);
    return () => { stop = true; clearTimeout(timeout); clearInterval(ping); ws.current?.close(); };
  }, [code, token, qc]);

  const send = useCallback((msg: Record<string, unknown>) => {
    if (ws.current?.readyState === 1) ws.current.send(JSON.stringify(msg));
  }, []);
  return { connected, me, members, messages, video, reason, topic, skew, quiz, myAnswer, setMyAnswer, result, setResult,
    setQuiz, leaderboard, closed, reactions, noteTaker, timer, confusion, lostAck, send };
}

/* ---------------------------------------------------------------- quiz pop-up */
function QuizPopup({ quiz, result, myAnswer, skew, onAnswer, onClose, myId }: {
  quiz: LiveQuiz; result: QuizResult | null; myAnswer: number | null; skew: number; myId?: number;
  onAnswer: (i: number, confidence: Confidence) => void; onClose: () => void;
}) {
  const [now, setNow] = useState(Date.now());
  const [picked, setPicked] = useState<number | null>(null);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 200); return () => clearInterval(t); }, []);
  const left = Math.max(0, quiz.deadline - (now / 1000 + skew));
  const total = result ? result.counts.reduce((a, b) => a + b, 0) || 1 : 1;
  const iWasRight = result && myAnswer === result.answer_index;
  const myScore = result?.leaderboard.find((s) => s.user_id === myId);
  useEffect(() => {
    if (!result) return;
    const t = setTimeout(onClose, 12000);
    return () => clearTimeout(t);
  }, [result, onClose]);

  return (
    <motion.div initial={{ opacity: 0, y: 24, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 16 }}
      className="fixed inset-x-3 bottom-20 z-50 mx-auto max-w-xl sm:bottom-6" role="region" aria-label="Pop quiz" aria-live="assertive">
      <div className="panel ring-gradient overflow-hidden bg-elev shadow-2xl">
        <div className="h-1 bg-elev-2">
          {!result && <div className="h-full bg-gradient-brand transition-[width] duration-200" style={{ width: `${(100 * left) / quiz.seconds}%` }} />}
        </div>
        <div className="p-5">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-accent"><Target className="h-3.5 w-3.5" />Pop quiz</div>
            {result ? (
              <button onClick={onClose} className="rounded-lg p-1 text-muted hover:bg-elev-2 hover:text-fg" aria-label="Close"><X className="h-4 w-4" /></button>
            ) : (
              <span className="font-mono text-sm tabular-nums text-muted">{Math.ceil(left)}s · {quiz.answered} answered</span>
            )}
          </div>
          <Markdown className="text-[15.5px] text-fg">{quiz.question}</Markdown>
          <div className="mt-4 space-y-2">
            {quiz.options.map((o, i) => {
              const chosen = (myAnswer ?? picked) === i;
              const correct = result?.answer_index === i;
              const pct = result ? Math.round((100 * result.counts[i]) / total) : 0;
              return (
                <button key={i} disabled={myAnswer !== null || !!result || left <= 0} onClick={() => setPicked(i)}
                  className={cn("relative flex w-full items-center gap-3 overflow-hidden rounded-xl border px-3.5 py-2.5 text-left text-sm transition",
                    !result && myAnswer === null && "border-line bg-bg-soft hover:border-accent/50",
                    !result && chosen && "border-accent bg-accent-soft",
                    !result && myAnswer !== null && !chosen && "border-line opacity-60",
                    result && correct && "border-ok/60 bg-ok/10",
                    result && !correct && chosen && "border-bad/50 bg-bad/10",
                    result && !correct && !chosen && "border-line opacity-70")}>
                  {result && <span className="absolute inset-y-0 left-0 bg-fg/5" style={{ width: `${pct}%` }} />}
                  <span className={cn("relative grid h-7 w-7 shrink-0 place-items-center rounded-lg border text-xs font-semibold",
                    result && correct ? "border-ok bg-ok text-white" : chosen ? "border-accent text-accent" : "border-line-strong")}>
                    {result && correct ? <Check className="h-3.5 w-3.5" /> : LETTERS[i]}
                  </span>
                  <Markdown className="relative flex-1 text-sm">{displayStyle(o)}</Markdown>
                  {result && <span className="relative text-xs tabular-nums text-muted">{pct}%</span>}
                </button>
              );
            })}
          </div>
          {!result && myAnswer === null && left > 0 && (
            <ConfidenceLock compact ready={picked !== null} onLock={(c) => picked !== null && onAnswer(picked, c)} />
          )}
          {!result && myAnswer !== null && <p className="mt-3 flex items-center gap-2 text-sm text-muted"><Loader2 className="h-4 w-4 animate-spin" />Locked in — waiting for the others…</p>}
          {result && (
            <div className="mt-4 rounded-xl border border-line bg-bg-soft p-3.5">
              <div className={cn("mb-1 text-sm font-semibold", myAnswer === null ? "text-muted" : iWasRight ? "text-ok" : "text-bad")}>
                {myAnswer === null ? "You didn't answer this one." : iWasRight ? `Correct!${myScore ? ` You have ${myScore.points} points.` : ""}` : "Not quite — it's in your redo queue."}
              </div>
              <Markdown className="text-[13.5px]">{result.explanation}</Markdown>
              <div className="mt-2 text-xs text-muted">
                {result.correct_names.length ? `Got it right: ${result.correct_names.join(", ")}` : "Nobody got this one — worth discussing!"}
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

/* ---------------------------------------------------------------- the return lane */
/** A student's anonymous "I'm lost": the host sees a count pinned to the board on screen, never a name. */
function LostButton({ ack, onLost, disabled }: { ack: { until: number; board: RoomBoard | null } | null; onLost: () => void; disabled: boolean }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const wait = ack ? Math.max(0, Math.ceil((ack.until - now) / 1000)) : 0;
  const t = useT();
  return (
    <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-line pt-3">
      <Button variant="secondary" size="sm" onClick={onLost} disabled={disabled || wait > 0} icon={<Waves className="h-3.5 w-3.5" />}
        aria-describedby="lost-help">{wait > 0 ? `${t("I'm lost")} · ${wait}s` : t("I'm lost")}</Button>
      <span id="lost-help" className="text-xs text-muted">{t("Anonymous: the host sees how many are lost, and on which board, never who.")}</span>
    </div>
  );
}

/** The host's live meter: taps in the last minute and the board most of them point at. */
function ConfusionBar({ meter, code }: { meter: ConfusionMeter | null; code: string }) {
  const n = meter?.last_minute ?? 0;
  return (
    <div className={cn("mt-3 flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2 text-sm", n ? "border-warn/50 bg-warn/10" : "border-line")}
      role="status" aria-live="polite">
      <Waves className={cn("h-4 w-4", n ? "text-warn" : "text-muted")} />
      {n ? (
        <span><b>{n} lost</b> in the last minute{meter?.board && <> · most at <b>board {meter.board.number}: {meter.board.topic}</b></>}</span>
      ) : (
        <span className="text-muted">Nobody has tapped "I'm lost"{meter?.total ? ` in the last minute (${meter.total} so far)` : " yet"}.</span>
      )}
      <span className="flex-1" />
      <Link to={`/app/rooms/${code}/report`} className="text-xs font-medium text-accent hover:underline">Open the confusion map</Link>
    </div>
  );
}

/* ---------------------------------------------------------------- page */

export default function RoomView() {
  const code = (useParams().code ?? "").toUpperCase();
  const navigate = useNavigate();
  const user = useAuth((s) => s.user);
  const { data: room } = useQuery({ queryKey: ["room", code], queryFn: () => api.joinRoom(code), retry: false });
  const r = useRoom(code);
  const qc = useQueryClient();
  const isHost = !!r.me?.host;
  const [tab, setTab] = useState<"chat" | "doubts" | "notes" | "board" | "people">("chat");
  const frameRef = useRef<HTMLDivElement>(null);
  useFocus("room", r.connected, !r.video.playing); // a playing lecture counts; otherwise only while you're taking part
  const { data: notes = [] } = useQuery({ queryKey: ["room-notes", code], queryFn: () => api.roomNotes(code), enabled: !!room });
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"message" | "doubt" | "ai">("message");
  const [url, setUrl] = useState("");
  const [topicDraft, setTopicDraft] = useState("");
  const [autoQuiz, setAutoQuiz] = useState<"off" | "5" | "10" | "15">("10");
  const chatRef = useRef<HTMLDivElement>(null);
  const playedSecs = useRef(0); // lecture play time since the last quiz

  useEffect(() => { setTopicDraft(r.topic); }, [r.topic]);
  useEffect(() => { chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" }); }, [r.messages]);

  const saveNotes = useMutation({
    mutationFn: () => api.saveRoomNotes(code),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["overview"] });
      toast.success(`${s.notes} board${s.notes === 1 ? "" : "s"} saved to your library`, {
        action: { label: "Open", onClick: () => navigate(`/app/library/${s.session_id}`) },
      });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't save the notes"),
  });
  const close = useMutation({
    mutationFn: () => api.closeRoom(code),
    onSuccess: () => {
      if (notes.length) // the host goes to the report; their notes are one tap away too
        toast(`Save the ${notes.length} board note${notes.length === 1 ? "" : "s"} to your library?`,
          { duration: 15000, action: { label: "Save", onClick: () => saveNotes.mutate() } });
      navigate(`/app/rooms/${code}/report`);
    },
  });
  const popQuiz = useMutation({
    mutationFn: () => api.roomQuiz(code, 30),
    onSuccess: () => { playedSecs.current = 0; },
  });
  const askAi = useMutation({ mutationFn: ({ q, doubtId }: { q: string; doubtId?: string }) => api.roomAsk(code, q, doubtId) });
  const answered = new Set(r.messages.filter((m) => m.type === "ai").map((m) => m.doubt_id ?? m.question ?? ""));
  const openDoubts = r.messages.filter((m) => m.kind === "doubt" && !m.resolved).length;
  const askAboutDoubt = (d: ChatMsg) => askAi.mutate({ q: d.text ?? "", doubtId: d.id });
  const jumpTo = (seconds: number) => {
    r.send({ type: "video", action: "seek", position: seconds, playing: r.video.playing });
    toast.success("Moved the lecture there for everyone");
  };

  // host: auto pop quiz every N minutes while the lecture plays
  const live = useRef({ playing: false, busy: false, pop: () => {} });
  live.current = { playing: r.video.playing, busy: popQuiz.isPending || (!!r.quiz && !r.result), pop: () => popQuiz.mutate() };
  useEffect(() => { playedSecs.current = 0; }, [autoQuiz]);
  useEffect(() => {
    if (!isHost || autoQuiz === "off") return;
    const t = setInterval(() => {
      if (!live.current.playing) return; // only count time the lecture is actually playing
      playedSecs.current += 5;
      if (playedSecs.current >= Number(autoQuiz) * 60 && !live.current.busy) {
        playedSecs.current = 0;
        live.current.pop();
      }
    }, 5_000);
    return () => clearInterval(t);
  }, [isHost, autoQuiz]);

  const onHostEvent = useCallback((action: HostAction, position: number, playing?: boolean, rate?: number) => {
    r.send({ type: "video", action, position, playing, rate });
  }, [r]);

  const submit = () => {
    const q = text.trim();
    if (!q) return;
    if (mode === "ai") askAi.mutate({ q }, { onError: () => setText((t) => t || q) });
    else r.send({ type: "chat", text: q, kind: mode === "doubt" ? "doubt" : "message" });
    setText("");
  };

  if (r.closed)
    return (
      <div className="mx-auto max-w-md py-20 text-center">
        <h2 className="text-lg font-semibold">{r.closed}</h2>
        {notes.length > 0 && (
          <div className="panel mt-5 p-4">
            <p className="text-sm text-muted">The room took {notes.length} board note{notes.length === 1 ? "" : "s"}. Keep them in your library.</p>
            <Button variant="primary" className="mt-3" loading={saveNotes.isPending} disabled={saveNotes.isSuccess}
              onClick={() => saveNotes.mutate()} icon={<BookmarkPlus className="h-4 w-4" />}>
              {saveNotes.isSuccess ? "Saved to your library" : "Save notes to my library"}
            </Button>
          </div>
        )}
        <Link to="/app/rooms"><Button className="mt-4">Back to rooms</Button></Link>
      </div>
    );

  const copy = (value: string, what: string) => navigator.clipboard.writeText(value).then(() => toast.success(`${what} copied`));
  const liveQuiz = r.quiz && (!r.result || r.result.id === r.quiz.id) ? r.quiz : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 xl:flex-row xl:items-center">
        <div className="min-w-0">
          <Link to="/app/rooms" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft className="h-4 w-4" />Rooms</Link>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <h1 className="truncate text-[30px]">{room?.name ?? "Study room"}</h1>
            <Badge tone={r.connected ? "ok" : "warn"}>{r.connected ? `${r.members.length} here` : "reconnecting…"}</Badge>
            {isHost && <Badge tone="accent"><Crown className="h-3 w-3" />You're the host</Badge>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => copy(code, "Room code")} icon={<Copy className="h-4 w-4" />}><span className="font-mono tracking-widest">{code}</span></Button>
          <Button onClick={() => copy(`${location.origin}/app/rooms/${code}`, "Invite link")} icon={<Link2 className="h-4 w-4" />}>Invite</Button>
          {isHost && <Link to={`/app/rooms/${code}/report`}><Button icon={<MapPinned className="h-4 w-4" />}>Confusion map</Button></Link>}
          {isHost && <Button variant="danger" onClick={() => confirm("Close this room for everyone?") && close.mutate()} icon={<Power className="h-4 w-4" />}>Close room</Button>}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <div className="space-y-3">
          <Card className="relative overflow-hidden p-2">
            {r.video.id ? (
              <SyncedYouTube video={r.video} reason={r.reason} skew={r.skew} isHost={isHost} onHostEvent={onHostEvent} frameRef={frameRef} />
            ) : (
              <div className="grid aspect-video place-items-center rounded-xl bg-[radial-gradient(ellipse_at_center,#1e1e1d,#0a0a0a)] p-6 text-center">
                {isHost ? (
                  <form className="w-full max-w-md" onSubmit={(e) => { e.preventDefault(); r.send({ type: "video", action: "load", url }); }}>
                    <Play className="mx-auto h-10 w-10 text-accent" />
                    <div className="mt-3 font-semibold text-white">Start the lecture</div>
                    <p className="mt-1 text-sm text-white/60">Paste a YouTube link — it will play in sync for everyone here.</p>
                    <div className="mt-4 flex gap-2">
                      <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://youtu.be/…" />
                      <Button type="submit" variant="primary" disabled={!url.trim()}>Load</Button>
                    </div>
                  </form>
                ) : (
                  <div>
                    <Loader2 className="mx-auto h-8 w-8 animate-spin text-white/50" />
                    <div className="mt-3 font-medium text-white">Waiting for the host to start the lecture…</div>
                    <p className="mt-1 text-sm text-white/60">Chat and doubts already work — say hi.</p>
                  </div>
                )}
              </div>
            )}
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 overflow-hidden">
              <AnimatePresence>
                {r.reactions.map((x, i) => {
                  const reaction = reactionOf(x.emoji);
                  return reaction && (
                    <motion.div key={x.id} initial={{ opacity: 0, y: 0 }} animate={{ opacity: [0, 1, 1, 0], y: -160 }} transition={{ duration: 2.4 }}
                      className="absolute bottom-4" style={{ left: `${8 + ((i * 23) % 60)}%` }}><ReactionBadge reaction={reaction} name={x.user} /></motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex flex-wrap items-center gap-2">
              <div className="min-w-0 flex-1 basis-48">
                <div className="truncate text-sm font-semibold">{r.video.title || "No lecture loaded yet"}</div>
                <div className="truncate text-xs text-muted">
                  {r.topic ? `Topic: ${r.topic}` : "No topic set"}
                  {r.video.id && (r.video.captions ? " · Quizzes use what the teacher just said" : " · Quizzes use the title and topic")}
                </div>
              </div>
              {isHost && r.video.id && (
                <Button variant="primary" size="sm" loading={popQuiz.isPending} disabled={!!liveQuiz && !r.result}
                  onClick={() => popQuiz.mutate()} icon={<Target className="h-3.5 w-3.5" />}>Pop quiz now</Button>
              )}
            </div>
            <div className="mt-3"><RoomTimer timer={r.timer} skew={r.skew} send={r.send} /></div>
            {isHost ? <ConfusionBar meter={r.confusion} code={code} /> : <LostButton ack={r.lostAck} onLost={() => r.send({ type: "lost" })} disabled={!r.connected} />}
            {isHost && (
              <div className="mt-3 grid gap-2 border-t border-line pt-3 md:grid-cols-[1fr_1fr_auto]">
                <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); r.send({ type: "video", action: "load", url }); setUrl(""); }}>
                  <Input className="h-9" value={url} onChange={(e) => setUrl(e.target.value)} placeholder={r.video.id ? "Switch to another YouTube link…" : "YouTube link…"} />
                  <Button size="sm" type="submit" disabled={!url.trim()}>Load</Button>
                </form>
                <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); r.send({ type: "topic", topic: topicDraft }); toast.success("Topic updated"); }}>
                  <Input className="h-9" value={topicDraft} onChange={(e) => setTopicDraft(e.target.value)} placeholder="Topic (helps quiz quality)" maxLength={120} />
                  <Button size="sm" type="submit" disabled={topicDraft === r.topic}>Set</Button>
                </form>
                <div className="flex items-center gap-2 text-xs text-muted">
                  Auto quiz
                  <Segmented size="sm" className="max-sm:[&_button]:h-10" value={autoQuiz} onChange={setAutoQuiz} options={[
                    { value: "off", label: "Off" }, { value: "5", label: "5m" }, { value: "10", label: "10m" }, { value: "15", label: "15m" },
                  ]} />
                </div>
              </div>
            )}
          </Card>
        </div>

        <Card className="flex h-[calc(100dvh-180px)] min-h-[520px] flex-col overflow-hidden xl:sticky xl:top-4">
          <div className="overflow-x-auto border-b border-line px-3 py-2.5">
            <Segmented size="sm" className="max-sm:[&_button]:h-10" value={tab} onChange={setTab} options={[
              { value: "chat", label: "Chat", icon: <MessageSquare className="h-3.5 w-3.5" /> },
              { value: "doubts", label: `Doubts${openDoubts ? ` · ${openDoubts}` : ""}`, icon: <Hand className="h-3.5 w-3.5" /> },
              { value: "notes", label: `Notes${notes.length ? ` · ${notes.length}` : ""}`, icon: <ScanText className="h-3.5 w-3.5" /> },
              { value: "board", label: "Ranks", icon: <Trophy className="h-3.5 w-3.5" /> },
              { value: "people", label: `${r.members.length}`, icon: <Users className="h-3.5 w-3.5" /> },
            ]} />
          </div>

          {tab === "doubts" && (
            <DoubtBoard messages={r.messages} myId={user?.id} isHost={isHost} send={r.send}
              onAskAi={askAboutDoubt} askingId={askAi.isPending ? askAi.variables?.doubtId ?? null : null}
              onJump={jumpTo} onRaise={() => { setTab("chat"); setMode("doubt"); }} />
          )}

          {/* always mounted: switching to chat or doubts must not stop the board capture */}
          <div className={tab === "notes" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
            <RoomNotes code={code} notes={notes} noteTaker={r.noteTaker} myId={user?.id} isHost={isHost} frameRef={frameRef} hasVideo={!!r.video.id} />
          </div>

          {tab === "chat" && (
            <>
              <div ref={chatRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
                {r.messages.length === 0 && <p className="py-10 text-center text-sm text-muted">Discuss the lecture here. Raise a doubt, or ask Focs — everyone sees the answer.</p>}
                {r.messages.map((m, i) => {
                  if (m.type === "system") return <div key={i} className="text-center text-[11.5px] text-muted">{m.text}</div>;
                  if (m.type === "ai") return (
                    <div key={m.id ?? i} className="rounded-2xl border border-accent/25 bg-accent-soft/40 p-3">
                      <div className="mb-1.5 flex items-center gap-2 text-xs text-muted">
                        <span className="grid h-5 w-5 place-items-center rounded-full bg-gradient-brand text-brand-fg"><Bot className="h-3 w-3" /></span>
                        <span><b className="text-fg">{m.user}</b> asked Focs</span>
                      </div>
                      <div className="mb-2 text-sm font-medium">{m.question}</div>
                      <Markdown className="text-[13.5px]">{m.answer ?? ""}</Markdown>
                    </div>
                  );
                  const mine = m.user_id === user?.id;
                  return (
                    <div key={m.id ?? i} className={cn("flex flex-col", mine && "items-end")}>
                      <span className="mb-0.5 px-1 text-[11px] text-muted">{mine ? "You" : m.user}{m.kind === "doubt" && " · doubt"}</span>
                      <div className={cn("max-w-[88%] rounded-2xl px-3.5 py-2 text-sm",
                        m.kind === "doubt" ? "border border-warn/40 bg-warn/10" : mine ? "rounded-br-md bg-gradient-brand text-brand-fg" : "rounded-bl-md border border-line bg-bg-soft")}>
                        {m.kind === "doubt" && <Hand className="mr-1.5 inline h-3.5 w-3.5 text-warn" />}{m.text}
                      </div>
                      {m.kind === "doubt" && (
                        <div className="mt-1 flex items-center gap-3 px-1 text-[11.5px]">
                          {answered.has(m.id ?? "") || answered.has(m.text ?? "") ? (
                            <span className="inline-flex items-center gap-1 text-ok"><Check className="h-3 w-3" /> Focs answered</span>
                          ) : (
                            <button onClick={() => askAboutDoubt(m)} disabled={askAi.isPending}
                              className="inline-flex items-center gap-1 font-medium text-accent hover:underline disabled:opacity-50">
                              <Sparkles className="h-3 w-3" /> Ask Focs to answer
                            </button>
                          )}
                          <button onClick={() => setTab("doubts")} className="text-muted hover:text-fg">
                            <Hand className="mr-1 inline h-3 w-3" />{m.votes?.length ?? 0} · {m.replies?.length ?? 0} {m.replies?.length === 1 ? "reply" : "replies"}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
                {askAi.isPending && <div className="flex items-center gap-2 text-xs text-muted"><Loader2 className="h-3.5 w-3.5 animate-spin" />Focs is answering for the room…</div>}
              </div>
              <div className="flex gap-1 border-t border-line px-3 pt-2" role="group" aria-label="React">
                {REACTIONS.map(({ id, label, icon: Icon, color }) => (
                  <button key={id} type="button" title={label} aria-label={label} onClick={() => r.send({ type: "reaction", emoji: id })}
                    className="grid h-10 w-10 place-items-center rounded-lg text-muted transition hover:bg-elev-2 active:scale-90 sm:h-8 sm:w-8">
                    <Icon className="h-4 w-4" style={{ color }} />
                  </button>
                ))}
              </div>
              <div className="space-y-2 p-3">
                {/* the mode switch stays outside the form: its buttons have no type, so inside it Enter "clicked" Message */}
                <Segmented size="sm" className="max-sm:[&_button]:h-10" value={mode} onChange={setMode} options={[
                  { value: "message", label: "Message" }, { value: "doubt", label: "Doubt", icon: <Hand className="h-3.5 w-3.5" /> }, { value: "ai", label: "Ask AI", icon: <Sparkles className="h-3.5 w-3.5" /> },
                ]} />
                <form onSubmit={(e) => { e.preventDefault(); submit(); }} className={cn("flex gap-2 rounded-2xl border bg-bg-soft p-1.5 focus-within:border-accent/50", mode === "ai" ? "border-accent/40" : "border-line")}>
                  <input value={text} onChange={(e) => setText(e.target.value)} maxLength={1000}
                    placeholder={mode === "ai" ? "Ask Focs — the answer is shared with the room" : mode === "doubt" ? "What's confusing you?" : "Message the room…"}
                    className="h-9 flex-1 bg-transparent px-2.5 text-sm outline-none placeholder:text-muted" />
                  <Button type="submit" variant="primary" size="icon-sm" disabled={!text.trim() || !r.connected} loading={askAi.isPending && mode === "ai"} aria-label="Send">
                    <ArrowUp className="h-4 w-4" />
                  </Button>
                </form>
              </div>
            </>
          )}

          {tab === "board" && (
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {r.leaderboard.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted">Points appear after the first pop quiz: 10 for a correct answer, up to +5 for speed, and +5 when your answer to someone's doubt is accepted.</p>
              ) : r.leaderboard.map((s, i) => (
                <div key={s.user_id} className={cn("mb-2 flex items-center gap-3 rounded-xl border px-3 py-2.5", s.user_id === user?.id ? "border-accent/40 bg-accent-soft" : "border-line bg-bg-soft")}>
                  <span className={cn("grid h-7 w-7 place-items-center rounded-full text-xs font-bold", i === 0 ? "bg-warn text-black" : "bg-elev-2")}>{i + 1}</span>
                  <span className="flex-1 truncate text-sm font-medium">{s.name}</span>
                  {!!s.helped && <span className="inline-flex items-center gap-1 text-xs text-ok" title="Doubts they answered"><HandHelping className="h-3.5 w-3.5" />{s.helped}</span>}
                  <span className="text-xs text-muted">{s.correct}/{s.answered}</span>
                  <span className="w-14 text-right font-semibold tabular-nums">{s.points}</span>
                </div>
              ))}
            </div>
          )}

          {tab === "people" && (
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">
              {r.members.map((m) => (
                <div key={m.id} className="flex items-center gap-3 rounded-xl border border-line bg-bg-soft px-3 py-2">
                  <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-brand text-xs font-semibold text-brand-fg">{m.name.slice(0, 1).toUpperCase()}</span>
                  <span className="flex-1 truncate text-sm">{m.name}{m.id === user?.id && <span className="text-muted"> (you)</span>}</span>
                  {r.noteTaker?.id === m.id && <Badge tone="ok"><ScanText className="h-3 w-3" />taking notes</Badge>}
                  {m.host && <Badge tone="accent"><Crown className="h-3 w-3" />host</Badge>}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <AnimatePresence>
        {liveQuiz && (
          <QuizPopup key={liveQuiz.id} quiz={liveQuiz} result={r.result} myAnswer={r.myAnswer} skew={r.skew} myId={user?.id}
            onAnswer={(i, confidence) => { r.setMyAnswer(i); r.send({ type: "answer", quiz_id: liveQuiz.id, choice: i, confidence }); }}
            onClose={() => { r.setQuiz(null); r.setResult(null); }} />
        )}
      </AnimatePresence>
    </div>
  );
}
