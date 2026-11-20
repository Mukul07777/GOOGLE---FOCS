import { Bot, Check, CheckCircle2, Clock3, Hand, Loader2, MessageCircleReply, Sparkles } from "lucide-react";
import { useState } from "react";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Badge, Segmented } from "@/components/ui/primitives";
import { cn, timeAgo } from "@/lib/utils";
import { clockOf, type ChatMsg } from "./types";

/**
 * The room's doubt board: every doubt with "me too" votes, replies from classmates, an accepted answer
 * (+5 points to whoever helped), an AI answer on request, and the moment in the video it was asked.
 */
export function DoubtBoard({ messages, myId, isHost, send, onAskAi, askingId, onJump, onRaise }: {
  messages: ChatMsg[];
  myId?: number;
  isHost: boolean;
  send: (msg: Record<string, unknown>) => void;
  onAskAi: (doubt: ChatMsg) => void;
  askingId: string | null;
  onJump: (seconds: number) => void;
  onRaise: () => void;
}) {
  const [filter, setFilter] = useState<"open" | "all">("open");
  const ai = new Map(messages.filter((m) => m.type === "ai" && m.doubt_id).map((m) => [m.doubt_id!, m]));
  const doubts = messages
    .filter((m) => m.kind === "doubt" && (filter === "all" || !m.resolved))
    .sort((a, b) => Number(!!a.resolved) - Number(!!b.resolved) || (b.votes?.length ?? 0) - (a.votes?.length ?? 0) || b.at - a.at);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
        <Segmented size="sm" value={filter} onChange={setFilter} options={[{ value: "open", label: "Open" }, { value: "all", label: "All" }]} />
        <Button size="sm" variant="secondary" onClick={onRaise} icon={<Hand className="h-3.5 w-3.5" />}>Raise a doubt</Button>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {!doubts.length && (
          <p className="py-10 text-center text-sm text-muted">
            {filter === "open" ? "No open doubts. Raise one — classmates can answer, upvote or ask Focs." : "No doubts yet."}
          </p>
        )}
        {doubts.map((d) => (
          <DoubtCard key={d.id} d={d} ai={ai.get(d.id!)} myId={myId} isHost={isHost} send={send}
            onAskAi={() => onAskAi(d)} asking={askingId === d.id} onJump={onJump} />
        ))}
      </div>
    </div>
  );
}

function DoubtCard({ d, ai, myId, isHost, send, onAskAi, asking, onJump }: {
  d: ChatMsg; ai?: ChatMsg; myId?: number; isHost: boolean; send: (msg: Record<string, unknown>) => void;
  onAskAi: () => void; asking: boolean; onJump: (seconds: number) => void;
}) {
  const [replying, setReplying] = useState(false);
  const [reply, setReply] = useState("");
  const votes = d.votes ?? [];
  const mine = votes.includes(myId ?? -1);
  const canAccept = isHost || d.user_id === myId;
  const submit = () => {
    if (!reply.trim()) return;
    send({ type: "reply", id: d.id, text: reply.trim() });
    setReply("");
    setReplying(false);
  };

  return (
    <div className={cn("rounded-2xl border p-3", d.resolved ? "border-line bg-bg-soft/60" : "border-warn/30 bg-warn/5")}>
      <div className="flex items-center gap-2 text-[11.5px] text-muted">
        <span className="font-medium text-fg-soft">{d.user_id === myId ? "You" : d.user}</span>
        <span>· {timeAgo(new Date(d.at * 1000).toISOString())}</span>
        {d.video_at != null && (
          isHost ? (
            <button onClick={() => onJump(d.video_at!)} className="inline-flex items-center gap-1 rounded-md bg-elev-2 px-1.5 py-0.5 text-accent hover:underline" title="Jump the room's video here">
              <Clock3 className="h-3 w-3" />{clockOf(d.video_at)}
            </button>
          ) : <span className="inline-flex items-center gap-1"><Clock3 className="h-3 w-3" />{clockOf(d.video_at)}</span>
        )}
        <span className="flex-1" />
        {d.resolved && <Badge tone="ok"><CheckCircle2 className="h-3 w-3" />resolved</Badge>}
      </div>
      <div className="mt-1.5 text-sm font-medium">{d.text}</div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <button onClick={() => send({ type: "vote", id: d.id })}
          className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium transition",
            mine ? "border-warn/50 bg-warn/15 text-warn" : "border-line text-muted hover:text-fg")}>
          <Hand className="h-3 w-3" /> Me too{votes.length ? ` · ${votes.length}` : ""}
        </button>
        <button onClick={() => setReplying(!replying)} className="inline-flex items-center gap-1 rounded-full border border-line px-2.5 py-1 text-xs text-muted hover:text-fg">
          <MessageCircleReply className="h-3 w-3" /> Answer
        </button>
        {!ai && !d.ai_answer_id && (
          <button onClick={onAskAi} disabled={asking}
            className="inline-flex items-center gap-1 rounded-full border border-accent/40 px-2.5 py-1 text-xs font-medium text-accent hover:bg-accent-soft disabled:opacity-60">
            {asking ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />} Ask Focs
          </button>
        )}
        {canAccept && (
          <button onClick={() => send({ type: "resolve", id: d.id })} className="ml-auto text-xs text-muted hover:text-fg">
            {d.resolved ? "Reopen" : "Mark resolved"}
          </button>
        )}
      </div>

      {(d.replies ?? []).map((r) => (
        <div key={r.id} className={cn("mt-2 rounded-xl border px-3 py-2 text-[13px]", r.accepted ? "border-ok/40 bg-ok/10" : "border-line bg-bg-soft")}>
          <div className="mb-0.5 flex items-center gap-2 text-[11px] text-muted">
            <span className="font-medium text-fg-soft">{r.user_id === myId ? "You" : r.user}</span>
            {r.accepted && <span className="inline-flex items-center gap-1 text-ok"><Check className="h-3 w-3" />accepted answer</span>}
            <span className="flex-1" />
            {canAccept && !r.accepted && r.user_id !== d.user_id && (
              <button onClick={() => send({ type: "accept", id: d.id, reply_id: r.id })} className="font-medium text-ok hover:underline">Accept (+5 to {r.user.split(" ")[0]})</button>
            )}
          </div>
          {r.text}
        </div>
      ))}

      {ai && (
        <div className="mt-2 rounded-xl border border-accent/25 bg-accent-soft/40 px-3 py-2">
          <div className="mb-1 flex items-center gap-1.5 text-[11px] text-muted"><Bot className="h-3 w-3 text-accent" />Focs answered</div>
          <Markdown className="text-[13px]">{ai.answer ?? ""}</Markdown>
        </div>
      )}

      {replying && (
        <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <input autoFocus value={reply} onChange={(e) => setReply(e.target.value)} maxLength={800} placeholder="Explain it in your words…"
            className="h-9 flex-1 rounded-xl border border-line bg-bg-soft px-3 text-sm outline-none focus:border-accent/50" />
          <Button size="sm" type="submit" variant="primary" disabled={!reply.trim()}>Send</Button>
        </form>
      )}
    </div>
  );
}
