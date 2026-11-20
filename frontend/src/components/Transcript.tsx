import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Mic } from "lucide-react";
import { useEffect, useState } from "react";
import { Markdown } from "@/components/Markdown";
import { Card, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { cn, formatDuration } from "@/lib/utils";

const WHY = { allowance: "this window's AI allowance is used up", busy: "the AI is busy" } as const;

/** What the teacher said in a lecture: a summary of the talk, with the exact words (the captions, kept; the audio
    itself never was) a tap away. */
export function Transcript({ sessionId }: { sessionId: number }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(true);
  const [exact, setExact] = useState(false);
  const { data } = useQuery({ queryKey: ["transcript", sessionId], queryFn: () => api.transcript(sessionId), staleTime: 60_000 });
  const pieces = data?.segments.length ?? 0;
  // keyed by the number of pieces: more speech since the last summary asks for a new one
  const summary = useQuery({ queryKey: ["talk-summary", sessionId, pieces], queryFn: () => api.talkSummary(sessionId),
    enabled: open && pieces > 0, staleTime: Infinity, retry: false });
  useEffect(() => { if (summary.data?.source === "ai") qc.invalidateQueries({ queryKey: ["usage"] }); }, [summary.data, qc]);
  if (!data || !pieces) return null;

  const minutes = Math.max(1, Math.round(data.segments.reduce((n, s) => n + Math.max(0, s.end_s - s.start_s), 0) / 60));
  const md = summary.data?.summary_md;
  const missing = !summary.isPending && !md;  // nothing to show instead of the words: show the words
  return (
    <Card className="overflow-hidden">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-3 px-5 py-4 text-left">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent-2/10 text-accent-2"><Mic className="h-4 w-4" /></span>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">What the teacher said</span>
          <span className="block text-xs text-muted">Summary of about {minutes} min of talk · the audio was never stored</span>
        </span>
        <ChevronDown className={cn("h-4 w-4 text-muted transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-line bg-bg-soft/40 p-5">
          {summary.isPending ? (
            <div className="space-y-2" aria-busy>
              <p className="text-sm text-muted">Summarising what the teacher said…</p>
              <Skeleton className="h-4 w-11/12" /><Skeleton className="h-4 w-4/5" /><Skeleton className="h-4 w-3/4" />
            </div>
          ) : md ? (
            <>
              <Markdown>{md}</Markdown>
              {summary.data?.stale && summary.data.reason && (
                <p className="mt-3 text-xs text-muted">This covers the talk up to an earlier point: {WHY[summary.data.reason]}, so it wasn't brought up to date.</p>
              )}
            </>
          ) : (
            <p className="text-sm text-muted">
              Couldn't summarise the talk right now{summary.data?.reason ? `: ${WHY[summary.data.reason]}` : ""}. Here are the teacher's exact words instead.
            </p>
          )}
          {!missing && (
            <button type="button" onClick={() => setExact(!exact)} aria-expanded={exact} className="mt-4 text-xs font-medium text-muted underline-offset-2 hover:text-fg hover:underline">
              {exact ? "Hide the exact words" : `Show the exact words (${pieces} pieces)`}
            </button>
          )}
          {(exact || missing) && (
            // a scrolling box: focusable, so the keyboard can scroll it too
            <div role="region" aria-label="The teacher's exact words" tabIndex={0} className="mt-3 max-h-[28rem] overflow-y-auto rounded-lg">
              <ol className="space-y-2">
                {data.segments.map((s) => (
                  <li key={s.id} className="flex gap-3 text-[14px] leading-relaxed">
                    <span className="w-12 shrink-0 pt-0.5 text-right font-mono text-xs tabular-nums text-muted">{formatDuration(s.start_s)}</span>
                    <span lang={s.language === "hi" ? "hi" : undefined}>{s.text}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
