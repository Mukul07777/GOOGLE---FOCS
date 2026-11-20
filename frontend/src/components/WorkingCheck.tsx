import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Camera, Check, CornerDownRight, GitBranch, GraduationCap, Lightbulb, MessageCircle, Send, Sparkles, X } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Markdown } from "@/components/Markdown";
import { photoImage } from "@/components/RoughPad";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Input } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { TutorTurn, WorkingCheck } from "@/lib/types";
import { cn } from "@/lib/utils";

const failed = (fallback: string) => (e: unknown) => toast.error(e instanceof ApiError ? e.message : fallback);
const nth = (n: number) => `${n}${n % 10 === 1 && n % 100 !== 11 ? "st" : n % 10 === 2 && n % 100 !== 12 ? "nd" : n % 10 === 3 && n % 100 !== 13 ? "rd" : "th"}`;

export interface WorkingQuestion {
  question: string; options?: string[] | null; answer?: number | null; chosen?: number | null;
  chapterId?: string | null; topic?: string | null; subject?: string | null;
  /** a correct worked solution, when the page has one: the checker compares against it */
  solution?: string | null;
}

/** "Check my working" for one question: hand it the rough page as a picture, get the checked working back. */
export function useCheckWorking(q: WorkingQuestion | null) {
  return useMutation({
    mutationFn: ({ image, source }: { image: Blob; source: "pad" | "photo" }) => api.checkWorking(image, q ?? { question: "" }, source),
    onError: failed("Couldn't read your working right now. Try again in a minute."),
  });
}

/** "Check my paper working": take or pick a photo of the working on paper, no pad needed. */
export function PhotoCheckButton({ onPhoto, loading, className }: { onPhoto: (image: Blob) => void; loading?: boolean; className?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const picked = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    const image = await photoImage(f);
    if (image) onPhoto(image); else toast.error("That photo is too big. Try again with a smaller one.");
  };
  return (
    <>
      <input ref={input} type="file" accept="image/*" capture="environment" className="hidden" onChange={picked} />
      <Button size="sm" variant="secondary" className={className} loading={loading} onClick={() => input.current?.click()}
        icon={<Camera className="h-3.5 w-3.5" />} title="Take a photo of your working on paper">Check my paper working</Button>
    </>
  );
}

/** The checked working: each step read back, the first wrong one marked, slip or gap, the root behind it, and the tutor. */
export function WorkingCheckCard({ check, onClose, className }: { check: WorkingCheck; onClose?: () => void; className?: string }) {
  const [showFix, setShowFix] = useState(false);
  const [asking, setAsking] = useState(false);
  const navigate = useNavigate();
  const trace = useMutation({
    mutationFn: (chapterId: string) => api.gapStart(chapterId),
    onSuccess: (t) => navigate(`/app/roots?trace=${t.id}`),
    onError: failed("Couldn't start the trace right now"),
  });
  const right = check.verdict === "right";
  const wrongAt = check.first_wrong;
  const fp = check.fingerprint;
  const again = check.again;

  return (
    <div className={cn("rounded-xl border border-line bg-bg-soft p-4", className)} aria-live="polite">
      <div className="flex items-start gap-2.5">
        <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg", right ? "bg-ok/15 text-ok" : "bg-bad/15 text-bad")}>
          {right ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Your working, checked</div>
          <div className="text-[15px] font-semibold">
            {right ? "Every step holds." : wrongAt !== null ? `Step ${wrongAt + 1} is where it went wrong` : check.verdict === "incomplete" ? "Right so far, but it stops early" : "Something went wrong"}
          </div>
          {check.error_label && <Badge tone={check.careless ? "warn" : "bad"} className="mt-1.5">{check.careless ? "Slip" : "Gap"} · {check.error_label}</Badge>}
        </div>
        {onClose && <button type="button" onClick={onClose} className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-muted hover:bg-elev-2 hover:text-fg" aria-label="Close the check"><X className="h-4 w-4" /></button>}
      </div>

      <ol className="mt-3 space-y-1.5">
        {check.steps.map((s, i) => {
          const isWrong = i === wrongAt, after = wrongAt !== null && i > wrongAt;
          return (
            <li key={i} className={cn("flex items-start gap-2.5 rounded-lg border px-3 py-2 text-[14px]",
              isWrong ? "border-bad/60 bg-bad/10" : after ? "border-line opacity-60" : "border-line bg-panel")}>
              <span className={cn("mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md text-[11px] font-semibold",
                isWrong ? "bg-bad text-white" : s.ok && !after ? "bg-ok/15 text-ok" : "bg-elev-2 text-muted")}>{i + 1}</span>
              <Markdown className="min-w-0 flex-1 [&_p]:m-0">{s.text}</Markdown>
              {isWrong && <span className="shrink-0 text-[11px] font-semibold text-bad">first slip</span>}
              {after && i === wrongAt + 1 && <span className="shrink-0 text-[11px] text-muted">follows from it</span>}
            </li>
          );
        })}
      </ol>

      {!right && (
        <div className="mt-3 space-y-2">
          {check.what_went_wrong && <Markdown className="text-[14px]">{check.what_went_wrong}</Markdown>}
          {check.hint && (
            <div className="flex gap-2 rounded-lg border border-accent/30 bg-accent-soft px-3 py-2 text-[13.5px]">
              <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-accent" /><Markdown className="[&_p]:m-0">{check.hint}</Markdown>
            </div>
          )}
          {check.fix && (showFix
            ? <div className="flex gap-2 text-[14px]"><CornerDownRight className="mt-1 h-4 w-4 shrink-0 text-ok" /><Markdown className="[&_p]:m-0">{check.fix}</Markdown></div>
            : <button type="button" onClick={() => setShowFix(true)} className="text-[13px] font-medium text-accent hover:underline">Tried it? Show the corrected step</button>)}
        </div>
      )}

      {check.careless && (
        <p className="mt-3 text-[13px] text-muted">
          A slip, not a gap: your idea was right.{fp.careless_share !== null && fp.mistakes >= 3 && ` ${fp.careless_share}% of the mistakes Focs has checked for you are slips like this, so slow down at the ${(fp.kinds.find((k) => k.careless)?.label ?? "arithmetic").toLowerCase().replace(" slip", "")} step.`}
        </p>
      )}

      {check.root && (
        <div className="mt-3 rounded-xl border border-warn/40 bg-warn/10 p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-warn"><GitBranch className="h-3.5 w-3.5" /> The root behind this step</div>
          <div className="mt-1 text-[14.5px] font-semibold">{check.root.idea}</div>
          <div className="text-[12.5px] text-muted">
            {check.root.cls ? `Class ${check.root.cls} · ` : ""}{check.root.name}
            {again && again.times > 1 && <> · <b className="text-fg">the {nth(again.times)} time</b> this root has tripped you</>}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {again?.trace ? (
              <Button size="sm" variant="primary" onClick={() => navigate(`/app/roots?trace=${again.trace!.id}`)} icon={<ArrowRight className="h-3.5 w-3.5" />}>
                {again.trace.status === "fixed" ? "Revisit your fix" : "Open your trace"}
              </Button>
            ) : check.chapter && (
              <Button size="sm" variant="primary" loading={trace.isPending} onClick={() => trace.mutate(check.chapter!.id)} icon={<Sparkles className="h-3.5 w-3.5" />}>Fix the root in 5 minutes</Button>
            )}
          </div>
        </div>
      )}
      {!check.root && !right && !check.careless && check.chapter && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[13px] text-muted">
          {check.earlier_idea && <span>Looks like <b className="text-fg">{check.earlier_idea}</b> is shaky.</span>}
          <Button size="sm" variant="secondary" loading={trace.isPending} onClick={() => trace.mutate(check.chapter!.id)} icon={<GitBranch className="h-3.5 w-3.5" />}>
            Trace {check.chapter.name} to its root
          </Button>
        </div>
      )}

      <div className="mt-3 border-t border-line pt-3">
        {asking ? <TutorChat checkId={check.id} starters={right ? ["Is there a faster way?", "Give me a harder one like this"] : ["Why is this step wrong?", "Explain the idea from scratch", "Give me a similar question"]} />
          : <Button size="sm" variant="ghost" onClick={() => setAsking(true)} icon={<MessageCircle className="h-3.5 w-3.5" />}>Ask the tutor about this step</Button>}
      </div>
    </div>
  );
}

/** The personal tutor: knows the student's root gaps and slips, and the step (``checkId``) or chapter (``chapterId``). */
export function TutorChat({ checkId, chapterId, starters = [], placeholder = "Ask anything about this…" }: {
  checkId?: number; chapterId?: string; starters?: string[]; placeholder?: string;
}) {
  const [turns, setTurns] = useState<TutorTurn[]>([]);
  const [text, setText] = useState("");
  const ask = useMutation({
    mutationFn: (q: string) => api.tutor({ question: q, history: turns, check_id: checkId ?? null, chapter_id: chapterId ?? null }),
    onSuccess: (r, q) => setTurns((t) => [...t, { role: "user", content: q }, { role: "assistant", content: r.answer }]),
    onError: failed("The tutor is busy right now. Try again in a minute."),
  });
  const send = (q: string) => { if (q.trim() && !ask.isPending) { ask.mutate(q.trim()); setText(""); } };

  return (
    <div className="space-y-2.5">
      {turns.map((t, i) => (
        <div key={i} className={cn("flex gap-2", t.role === "user" && "justify-end")}>
          {t.role === "assistant" && <span className="mt-1 grid h-6 w-6 shrink-0 place-items-center rounded-md bg-fg text-bg"><GraduationCap className="h-3.5 w-3.5" /></span>}
          <div className={cn("max-w-[88%] rounded-xl px-3 py-2 text-[14px]", t.role === "user" ? "bg-elev-2" : "border border-line bg-panel")}>
            {t.role === "user" ? t.content : <Markdown className="[&_p:last-child]:mb-0">{t.content}</Markdown>}
          </div>
        </div>
      ))}
      {ask.isPending && <div className="text-[13px] text-muted">The tutor is thinking…</div>}
      {turns.length === 0 && starters.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {starters.map((s) => <button key={s} type="button" onClick={() => send(s)} disabled={ask.isPending}
            className="rounded-full border border-line px-3 py-1 text-[12.5px] text-fg-soft hover:border-line-strong hover:text-fg disabled:opacity-50">{s}</button>)}
        </div>
      )}
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} aria-label="Ask the tutor" maxLength={1500} />
        <Button type="submit" variant="primary" size="icon" loading={ask.isPending} disabled={!text.trim()} aria-label="Send"><Send className="h-4 w-4" /></Button>
      </form>
    </div>
  );
}

/** How the student loses marks, from their checked rough work: careless slips or gaps in ideas. Hidden until there is some. */
export function MistakeFingerprintCard() {
  const { data } = useQuery({ queryKey: ["working-fingerprint"], queryFn: api.workingFingerprint });
  if (!data || data.mistakes === 0) return null;
  const top = data.kinds.slice(0, 5);
  const most = Math.max(...top.map((k) => k.count));
  return (
    <Card>
      <CardHeader title="How you lose marks" icon={<Sparkles className="h-4 w-4" />}
        subtitle={`From the last ${data.checked} solutions Focs checked for you`} />
      <div className="px-5 pb-5">
        <div className="flex h-3 overflow-hidden rounded-full bg-elev-2" aria-hidden>
          <div className="bg-warn" style={{ width: `${(100 * data.slips) / data.mistakes}%` }} />
          <div className="bg-bad" style={{ width: `${(100 * data.gaps) / data.mistakes}%` }} />
        </div>
        <p className="mt-2 text-[13.5px]">
          <b>{data.careless_share}%</b> careless slips <span className="text-muted">(the idea was right)</span> · <b>{100 - (data.careless_share ?? 0)}%</b> gaps in an idea
          <span className="text-muted"> {data.slips > data.gaps ? "— slowing down will win you more marks than new chapters." : "— fixing the roots will win you more than more practice."}</span>
        </p>
        <ul className="mt-3 space-y-1.5">
          {top.map((k) => (
            <li key={k.type} className="flex items-center gap-3 text-[13px]">
              <span className="w-40 shrink-0 truncate">{k.label}</span>
              <span className="h-2 flex-1 rounded-full bg-elev-2"><span className={cn("block h-2 rounded-full", k.careless ? "bg-warn" : "bg-bad")} style={{ width: `${(100 * k.count) / most}%` }} /></span>
              <span className="w-6 text-right tabular-nums text-muted">{k.count}</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
