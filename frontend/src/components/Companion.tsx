import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, Bot, Check, Copy, Lightbulb, Maximize2, ScanText, Sparkles, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/Markdown";
import { ReadAloud } from "@/components/ReadAloud";
import { ScrollX } from "@/components/ScrollX";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Segmented } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { WaitBridge } from "@/components/WaitBridge";
import { CostHint } from "@/components/UsageMeter";

type Mode = "explain" | "steps" | "simple" | "socratic" | "hinglish";
export interface FocusNote { id: number; topic: string | null }
interface Msg { role: "user" | "assistant"; content: string; source?: string }

const PROMPTS = ["Explain the current board", "Give me a solved example", "Why does this formula work?", "What mistakes do students make here?"];

export function Companion({ sessionId, className, focus, onClearFocus }: {
  sessionId?: number; className?: string; focus?: FocusNote | null; onClearFocus?: () => void;
}) {
  const [mode, setMode] = useState<Mode>("explain");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [full, setFull] = useState<string | null>(null);
  const [live, setLive] = useState<string | null>(null);  // the answer so far, while it is being written  // an answer opened at full width
  const [copied, setCopied] = useState<number | null>(null);
  const copy = (text: string, i: number) => {
    navigator.clipboard?.writeText(text).then(() => { setCopied(i); setTimeout(() => setCopied(null), 1500); }).catch(() => undefined);
  };
  const scroller = useRef<HTMLDivElement>(null);
  const seeded = useRef(false);
  const qc = useQueryClient();

  // coming back to a lecture: bring back the doubts already asked in it
  const { data: past } = useQuery({ queryKey: ["doubts", sessionId], queryFn: () => api.doubts(sessionId), enabled: !!sessionId, staleTime: Infinity });
  useEffect(() => {
    if (seeded.current || !past) return;
    seeded.current = true;
    if (!past.length) return;
    const earlier = past.slice(0, 10).reverse().flatMap((d): Msg[] => [{ role: "user", content: d.question }, { role: "assistant", content: d.answer }]);
    setMessages((m) => (m.length ? m : earlier));
  }, [past]);

  const ask = useMutation({
    mutationFn: (question: string) =>
      api.askStream({ question, session_id: sessionId, note_id: focus?.id, mode, history: messages.slice(-6).map(({ role, content }) => ({ role, content })) }, setLive),
    onSuccess: (res) => {
      setLive(null);
      setMessages((m) => [...m, { role: "assistant", content: res.answer, source: res.source }]);
      qc.invalidateQueries({ queryKey: ["doubts", sessionId] });
      qc.invalidateQueries({ queryKey: ["usage"] });  // the allowance meter shows what this doubt took
    },
    onError: (_e, question) => {
      setLive(null);
      // keep what the student typed so they can just press send again
      setMessages((m) => m.slice(0, -1));
      setInput((cur) => cur || question);
    },
  });

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, ask.isPending, live]);

  const send = (q: string) => {
    const question = q.trim();
    if (!question || ask.isPending) return;
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    ask.mutate(question);
  };

  return (
    <div className={cn("flex min-h-0 flex-col", className)}>
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
        <div className="min-w-0 flex-1">
          <ScrollX quiet>
            <Segmented size="sm" value={mode} onChange={setMode} options={[
              { value: "explain", label: "Explain" }, { value: "steps", label: "Step-by-step" }, { value: "simple", label: "Simple" },
              { value: "socratic", label: "Hint only" }, { value: "hinglish", label: "Hinglish" },
            ]} />
          </ScrollX>
        </div>
        {messages.length > 0 && <button className="shrink-0 text-xs text-muted hover:text-fg" onClick={() => setMessages([])}>Clear</button>}
      </div>

      <div ref={scroller} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-accent-soft text-accent"><Sparkles className="h-5 w-5" /></div>
            <div className="mt-3 text-sm font-semibold">Ask a doubt, mid-lecture</div>
            <p className="mt-1 max-w-xs text-xs text-muted">Focs has these notes in front of it. {mode === "socratic" ? "Socratic mode guides you to the answer." : ""}</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {PROMPTS.map((p) => (
                <button key={p} onClick={() => send(p)} className="rounded-full border border-line bg-bg-soft px-3 py-1.5 text-xs text-fg-soft transition hover:border-accent/40 hover:text-fg">
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className={cn("flex gap-2.5", m.role === "user" && "justify-end")}>
            {m.role === "assistant" && <div className="mt-1 hidden h-7 w-7 shrink-0 place-items-center rounded-full bg-gradient-brand text-brand-fg sm:grid"><Bot className="h-3.5 w-3.5" /></div>}
            {/* min-w-0: the bubble may never be wider than the panel, whatever is inside it (tables slide instead) */}
            <div className={cn("min-w-0 rounded-2xl px-3.5 py-2.5 text-sm",
              m.role === "user" ? "max-w-[88%] rounded-br-md bg-gradient-brand text-brand-fg [overflow-wrap:anywhere]" : "flex-1 rounded-tl-md border border-line bg-bg-soft")}>
              {m.role === "user" ? m.content : <Markdown className="text-[13.5px]">{m.content}</Markdown>}
              {m.source === "offline" && <Badge tone="warn" className="mt-2"><Lightbulb className="h-3 w-3" />from your notes only</Badge>}
              {m.role === "assistant" && (
                <div className="mt-2 flex items-center gap-1 border-t border-line pt-1.5 text-[11.5px] text-muted">
                  <button type="button" onClick={() => setFull(m.content)} className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 hover:bg-elev-2 hover:text-fg">
                    <Maximize2 className="h-3 w-3" />Full view
                  </button>
                  <ReadAloud text={m.content} className="px-1.5 text-[11.5px]" />
                  <button type="button" onClick={() => copy(m.content, i)} className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 hover:bg-elev-2 hover:text-fg">
                    {copied === i ? <><Check className="h-3 w-3 text-ok" />Copied</> : <><Copy className="h-3 w-3" />Copy</>}
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        ))}
        {ask.isPending && (
          <div className="flex gap-2.5">
            <div className="grid h-7 w-7 place-items-center rounded-full bg-gradient-brand text-brand-fg"><Bot className="h-3.5 w-3.5" /></div>
            {live
              ? <div aria-live="polite" aria-busy="true" className="min-w-0 flex-1 rounded-2xl rounded-tl-md border border-line bg-bg-soft px-3.5 py-2.5 text-sm">
                  <Markdown className="text-[13.5px]">{live}</Markdown>
                </div>
              : <WaitBridge kind="doubt" compact className="min-w-0 flex-1" />}
          </div>
        )}
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="border-t border-line p-3">
        {focus && (
          <div className="mb-2 flex items-center gap-2 rounded-lg bg-accent-soft px-2.5 py-1.5 text-xs text-accent">
            <ScanText className="h-3.5 w-3.5 shrink-0" />
            <span className="min-w-0 flex-1 truncate">About this board: <b>{focus.topic || "Board notes"}</b></span>
            <button type="button" onClick={onClearFocus} aria-label="Ask about the whole lecture" className="rounded p-0.5 hover:bg-accent/15"><X className="h-3 w-3" /></button>
          </div>
        )}
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-bg-soft p-1.5 focus-within:border-accent/50">
          <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={1} enterKeyHint="send" placeholder="Ask anything about this lecture…"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
            className="field-sizing-content max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted" />
          <Button type="submit" variant="primary" size="icon-sm" disabled={!input.trim()} loading={ask.isPending} aria-label="Send">
            {!ask.isPending && <ArrowUp className="h-4 w-4" />}
          </Button>
        </div>
        {input.trim() && <CostHint action="doubt" className="mt-1.5 px-1" />}
      </form>
      <Dialog open={full !== null} onClose={() => setFull(null)} wide title="Answer" className="sm:max-w-4xl">
        <Markdown className="text-[15px] leading-7">{full ?? ""}</Markdown>
      </Dialog>
    </div>
  );
}
