import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Eye, Hourglass, Layers, RotateCcw, Sigma } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Markdown } from "@/components/Markdown";
import { ReadAloud } from "@/components/ReadAloud";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { asFormula, displayStyle } from "@/lib/math";
import type { WaitTask } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

/** What each wait is for: the steps Focs really takes (described, not timed: no made-up progress bar) and how long
    it usually is. */
const WAITS = {
  doubt: { title: "Focs is answering", steps: ["Reads this lecture's board notes", "Writes the answer in your mode and language"], usual: "5–20 s" },
  practice: { title: "Writing your practice set", steps: ["Writes questions at your level from the material", "Works out each answer and its solution"], usual: "15–40 s" },
  notes: { title: "Writing these notes for the first time", steps: ["Nobody has opened this topic yet, so it's written now", "A second model re-solves the worked example and checks the formulas", "Then it's kept: next time it opens instantly, for everyone"], usual: "about 20 s" },
  revision: { title: "Writing the revision sheet", steps: ["Reads every board of the lecture, and what the teacher said", "Writes the overview, formula sheet and common mistakes", "Makes flashcards from it"], usual: "15–40 s" },
  translation: { title: "Saying it in your language", steps: ["Says the same steps and answer again", "Checks every formula and number came through unchanged"], usual: "5–20 s" },
  "test-result": { title: "Reading your test result", steps: ["Reads the marks and every wrong question", "Places each one in its chapter and topic"], usual: "10–30 s" },
} as const;
export type WaitKind = keyof typeof WAITS;

/** A wait turned into a bridge: what the system is doing, and one useful thing from the student's own material
    (a due flashcard, a question to redo, a formula) to do meanwhile. Needs no AI, so it works while the AI is busy. */
export function WaitBridge({ kind, topic, compact, className }: { kind: WaitKind; topic?: string | null; compact?: boolean; className?: string }) {
  const w = WAITS[kind];
  const t = useT();
  const [started] = useState(Date.now());
  const [now, setNow] = useState(Date.now());
  const [skip, setSkip] = useState("");
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const { data: task } = useQuery({ queryKey: ["wait-task", topic ?? "", skip], queryFn: () => api.waitTask(topic ?? "", skip), staleTime: 60_000 });
  const secs = Math.round((now - started) / 1000);
  const next = () => task && task.kind !== "none" && setSkip(`${task.kind}:${task.id}`);

  return (
    <div className={cn("rounded-2xl border border-line bg-bg-soft/60", compact ? "p-3" : "p-4", className)}>
      <div className="flex items-start gap-3" role="status" aria-live="polite">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent"><Hourglass className="h-4 w-4 animate-pulse" /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 text-sm font-semibold">{t(w.title)}<span className="font-mono text-xs font-normal tabular-nums text-muted">{secs}s · usually {w.usual}</span></div>
          {!compact && <ol className="mt-1 space-y-0.5 text-xs text-muted">{w.steps.map((s, i) => <li key={i}>{i + 1}. {s}</li>)}</ol>}
          {compact && <div className="text-xs text-muted">{w.steps.join(", then ").toLowerCase().replace(/^./, (c) => c.toUpperCase())}.</div>}
        </div>
      </div>
      {task && task.kind !== "none" && <div className={cn("border-t border-line", compact ? "mt-3 pt-3" : "mt-4 pt-4")}><Task task={task} onNext={next} /></div>}
    </div>
  );
}

function Task({ task, onNext }: { task: Exclude<WaitTask, { kind: "none" }>; onNext: () => void }) {
  const [shown, setShown] = useState(false);
  const t = useT();
  useEffect(() => setShown(false), [task]);
  const review = useMutation({ mutationFn: (grade: "again" | "good") => api.reviewCard(task.id, grade), onSuccess: onNext });
  const label = (icon: React.ReactNode, text: string) => (
    <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-accent">{icon}{t(text)}{task.topic && <span className="font-normal normal-case tracking-normal text-muted">· {task.topic}</span>}</div>
  );
  if (task.kind === "card") return (
    <div>
      {label(<Layers className="h-3 w-3" />, "Meanwhile, a flashcard that's due")}
      <Markdown className="text-sm font-medium">{task.front}</Markdown>
      {shown ? (
        <>
          <Markdown className="mt-1.5 text-sm text-fg-soft">{task.back}</Markdown>
          <div className="mt-2 flex gap-2">
            <Button size="sm" variant="secondary" loading={review.isPending && review.variables === "again"} onClick={() => review.mutate("again")}>{t("Didn't know it")}</Button>
            <Button size="sm" variant="primary" loading={review.isPending && review.variables === "good"} onClick={() => review.mutate("good")}>{t("Knew it")}</Button>
          </div>
        </>
      ) : <Button size="sm" className="mt-2" onClick={() => setShown(true)} icon={<Eye className="h-3.5 w-3.5" />}>{t("Think, then show the answer")}</Button>}
    </div>
  );
  if (task.kind === "redo") return (
    <div>
      {label(<RotateCcw className="h-3 w-3" />, "Meanwhile, one you got wrong before")}
      <Markdown className="text-sm">{displayStyle(task.question)}</Markdown>
      <div className="mt-2 flex flex-wrap gap-2">
        <Link to="/app/practice"><Button size="sm" icon={<ArrowRight className="h-3.5 w-3.5" />}>{t("Solve it in the redo queue")}</Button></Link>
        <Button size="sm" variant="ghost" onClick={onNext}>{t("Another")}</Button>
      </div>
    </div>
  );
  return (
    <div>
      {label(<Sigma className="h-3 w-3" />, "Meanwhile, say this formula and what each letter means")}
      <Markdown className="text-sm">{asFormula(task.formula)}</Markdown>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <ReadAloud text={task.formula} label="Hear it" />
        <Button size="sm" variant="ghost" onClick={onNext}>{t("Another")}</Button>
      </div>
    </div>
  );
}
