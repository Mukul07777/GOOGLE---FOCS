import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, MessageSquareText, RotateCcw, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { AnswerInput } from "@/components/AnswerInput";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { ProgressRing } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { Evaluation } from "@/lib/types";
import { cn } from "@/lib/utils";

/** How a written or spoken answer was graded: the score, what was covered, what was missing. */
export function EvaluationCard({ evaluation, modelAnswer, className }: { evaluation: Evaluation; modelAnswer?: string; className?: string }) {
  return (
    <div className={cn("grid gap-4 rounded-xl border border-line bg-bg-soft p-4 sm:grid-cols-[auto_1fr]", className)}>
      <ProgressRing value={evaluation.score * 10} size={76} color={evaluation.score >= 6 ? "var(--ok)" : "var(--warn)"}>
        <div className="text-center"><div className="text-lg font-semibold">{evaluation.score}</div><div className="text-[10px] text-muted">out of 10</div></div>
      </ProgressRing>
      <div className="min-w-0 space-y-2 text-sm">
        <div className="font-semibold">{evaluation.grade}</div>
        {evaluation.feedback && <Markdown className="text-sm text-fg-soft [&_p]:my-0">{evaluation.feedback}</Markdown>}
        {evaluation.points_covered.map((p) => <div key={p} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-ok" /><Markdown className="text-sm text-fg-soft [&_p]:my-0">{p}</Markdown></div>)}
        {evaluation.points_missed.map((p) => <div key={p} className="flex gap-2"><X className="mt-0.5 h-4 w-4 shrink-0 text-bad" /><Markdown className="text-sm text-fg-soft [&_p]:my-0">{p}</Markdown></div>)}
      </div>
      {modelAnswer && (
        <details className="sm:col-span-2">
          <summary className="cursor-pointer text-sm font-medium text-accent">Model answer</summary>
          <Markdown className="mt-2 text-sm">{modelAnswer}</Markdown>
        </details>
      )}
    </div>
  );
}

/** "Explain it in your own words": the student says or types what they understood of a topic and gets it checked
    against what was taught (the lecture's boards, or the topic's note in the library). */
export function TeachBack({ topic, topicId, sessionId, subject, className, footer }: {
  topic: string; topicId?: string; sessionId?: number; subject?: string; className?: string;
  /** shown next to the buttons once the explanation is graded (e.g. "Continue lecture") */
  footer?: ReactNode;
}) {
  const qc = useQueryClient();
  const [answer, setAnswer] = useState("");
  const grade = useMutation({
    mutationFn: () => api.teachBack({ topic, answer, topic_id: topicId, session_id: sessionId, subject }),
    onSuccess: () => { for (const key of ["usage", "redo", "overview"]) qc.invalidateQueries({ queryKey: [key] }); },
  });
  const result = grade.data;

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex gap-2.5 text-sm leading-relaxed text-fg-soft">
        <MessageSquareText className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <p>Explain <b className="font-semibold text-fg">{topic}</b> in your own words, as if you were teaching a friend: what it is, the rule or formula behind it, and one example.</p>
      </div>
      {result ? (
        <>
          <div className="rounded-xl border border-line bg-bg-soft px-3.5 py-2.5 text-sm leading-relaxed text-fg-soft">{answer}</div>
          <EvaluationCard evaluation={result} />
          <div className="flex flex-wrap justify-end gap-2">
            <Button size="sm" variant="ghost" icon={<RotateCcw className="h-3.5 w-3.5" />} onClick={() => grade.reset()}>Explain it again</Button>
            {footer}
          </div>
        </>
      ) : (
        <>
          <AnswerInput value={answer} onChange={setAnswer} hint={topic} minHeight="min-h-28" disabled={grade.isPending}
            placeholder="Say it out loud or type it. Don't worry about perfect sentences." />
          {grade.error && <p className="text-xs text-warn" role="alert">{grade.error instanceof ApiError ? grade.error.message : "Couldn't check that. Try again."}</p>}
          <div className="flex flex-wrap justify-end gap-2">
            {footer}
            <Button size="sm" variant="primary" disabled={answer.trim().length < 12} loading={grade.isPending} onClick={() => grade.mutate()}>
              Check my explanation
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
