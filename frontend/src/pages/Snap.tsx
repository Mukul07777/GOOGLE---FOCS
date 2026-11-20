import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, Check, CircleAlert, FileUp, Languages, Lightbulb, PenLine, RotateCcw, Sparkles, X } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { LanguagePicker } from "@/components/Explain";
import { WaitBridge } from "@/components/WaitBridge";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Badge, Card, Input, Label, ProgressRing, Segmented, Textarea } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { Language, MarkedAnswer, SolvedDoubt } from "@/lib/types";
import { useAuth } from "@/stores/auth";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

type Mode = "doubt" | "answer";
const MAX_FILES = 4;

function Photos({ files, onChange }: { files: File[]; onChange: (f: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const add = (list: FileList | null) => onChange([...files, ...Array.from(list ?? [])].slice(0, MAX_FILES));
  return (
    <div>
      <button type="button" onClick={() => input.current?.click()}
        onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); add(e.dataTransfer.files); }}
        className="flex w-full flex-col items-center gap-2 rounded-2xl border border-dashed border-line-strong bg-bg-soft px-4 py-8 text-center transition hover:border-accent/60">
        <span className="grid h-11 w-11 place-items-center rounded-xl bg-accent-soft text-accent"><Camera className="h-5 w-5" /></span>
        <span className="text-sm font-semibold">Take a photo or choose one</span>
        <span className="text-xs text-muted">JPEG, PNG or PDF · up to {MAX_FILES} pages · straight on, in good light</span>
      </button>
      <input ref={input} type="file" accept="image/*,application/pdf" capture="environment" multiple hidden
        onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      {files.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {files.map((f, i) => (
            <span key={`${f.name}-${i}`} className="inline-flex items-center gap-2 rounded-lg border border-line bg-bg-soft py-1 pl-2.5 pr-1 text-xs">
              <FileUp className="h-3.5 w-3.5 text-muted" /><span className="max-w-40 truncate">{f.name}</span>
              <button type="button" aria-label={`Remove ${f.name}`} onClick={() => onChange(files.filter((_, j) => j !== i))}
                className="rounded p-1 text-muted hover:bg-elev-2 hover:text-bad"><X className="h-3 w-3" /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Solved({ d }: { d: SolvedDoubt }) {
  // solved in English (the most reliable), said again in the student's language on request (kept once written)
  const preferred = useAuth((s) => s.user?.language) ?? "en";
  const [language, setLanguage] = useState<Language>(preferred);
  const other = language !== "en";
  const { data, isLoading, error } = useQuery({
    queryKey: ["explain-doubt", d.id, language], enabled: other, retry: false, staleTime: Infinity,
    queryFn: () => api.explainDoubt(d.id, language as Exclude<Language, "en">),
  });
  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-wrap items-center gap-2">
        {d.subject && <Badge tone="accent">{d.subject}</Badge>}{d.topic && <Badge>{d.topic}</Badge>}
        <div className="ml-auto flex items-center gap-2">
          <Languages className="h-3.5 w-3.5 text-muted" />
          <LanguagePicker value={language} onChange={setLanguage} />
        </div>
      </div>
      <Markdown className="text-fg">{d.question}</Markdown>
      {other && isLoading && <WaitBridge kind="translation" topic={d.topic} compact />}
      {other && error && <p className="text-[13px] text-bad">{error instanceof ApiError ? error.message : "Couldn't explain it in that language."}</p>}
      {other && data && <Markdown>{data.solution}</Markdown>}
      {!other && <>
      {d.idea && (
        <div className="flex gap-3 rounded-xl border border-accent/25 bg-accent-soft/50 p-3.5">
          <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-accent" /><Markdown className="[&_p]:my-0">{d.idea}</Markdown>
        </div>
      )}
      <ol className="space-y-2.5">
        {d.steps.map((s, i) => (
          <li key={i} className="flex gap-3">
            <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-elev-2 text-xs font-semibold text-fg-soft">{i + 1}</span>
            <Markdown className="min-w-0 flex-1 [&_p]:my-0">{s}</Markdown>
          </li>
        ))}
      </ol>
      <div className="rounded-xl border border-ok/30 bg-ok/10 p-3.5">
        <div className="text-xs font-semibold uppercase tracking-[0.1em] text-ok">Answer</div>
        <Markdown className="mt-1 text-fg [&_p]:my-0">{d.answer}</Markdown>
      </div>
      {d.watch_out && <p className="flex gap-2 text-[13px] text-muted"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warn" />{d.watch_out}</p>}
      </>}
      <p className="text-xs text-muted">Saved with your doubts. Solved by AI: if a step looks off, check it against your textbook.</p>
    </Card>
  );
}

function Marked({ m }: { m: MarkedAnswer }) {
  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-center gap-4">
        <ProgressRing value={m.percent} size={72} stroke={7} color={m.percent >= 60 ? "var(--ok)" : "var(--warn)"}>
          <span className="text-sm font-semibold">{m.marks}<span className="text-muted">/{m.max_marks}</span></span>
        </ProgressRing>
        <div className="min-w-0 flex-1">
          <div className="text-lg font-semibold">{m.percent >= 80 ? "A strong answer" : m.percent >= 60 ? "Mostly there" : "Marks left on the table"}</div>
          {m.question && <p className="mt-0.5 line-clamp-2 text-[13px] text-muted">{m.question}</p>}
        </div>
      </div>
      {m.got_right.length > 0 && (
        <div>
          <div className="mb-1.5 text-sm font-semibold">What earned marks</div>
          <ul className="space-y-1.5">{m.got_right.map((g, i) => (
            <li key={i} className="flex gap-2 text-sm text-fg-soft"><Check className="mt-0.5 h-4 w-4 shrink-0 text-ok" /><span>{g}</span></li>))}
          </ul>
        </div>
      )}
      {m.lost.length > 0 && (
        <div>
          <div className="mb-1.5 text-sm font-semibold">Where marks were lost</div>
          <div className="space-y-2">{m.lost.map((l, i) => (
            <div key={i} className="rounded-xl border border-warn/25 bg-warn/[0.07] p-3 text-sm">
              <div className="flex items-center justify-between gap-3 font-medium"><span>{l.where || "In the answer"}</span>{l.marks > 0 && <Badge tone="warn">−{l.marks}</Badge>}</div>
              <p className="mt-1 text-[13px] text-fg-soft">{l.why}</p>
            </div>))}
          </div>
        </div>
      )}
      {m.model_answer && (
        <div>
          <div className="mb-1.5 text-sm font-semibold">An answer that gets full marks</div>
          <div className="rounded-xl border border-line bg-bg-soft p-4"><Markdown>{m.model_answer}</Markdown></div>
        </div>
      )}
      {m.next_time && <p className="flex gap-2 text-[13px] text-muted"><Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-accent" />{m.next_time}</p>}
      <p className="text-xs text-muted">Marked by AI as an examiner would. Your teacher's marking is the one that counts.</p>
    </Card>
  );
}

/** Ask with a photo: a question you are stuck on is solved step by step; a handwritten answer is marked. */
export default function Snap() {
  const tr = useT();
  const qc = useQueryClient();
  const [mode, setMode] = useState<Mode>("doubt");
  const [files, setFiles] = useState<File[]>([]);
  const [note, setNote] = useState("");
  const [question, setQuestion] = useState("");
  const [marks, setMarks] = useState("5");
  const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Couldn't read that photo. Try again.");
  const solve = useMutation({ mutationFn: () => api.snapDoubt(files, note), onError: failed, onSuccess: () => qc.invalidateQueries({ queryKey: ["usage"] }) });
  const mark = useMutation({ mutationFn: () => api.snapAnswer(files, question, Number(marks) || 5), onError: failed, onSuccess: () => qc.invalidateQueries({ queryKey: ["usage"] }) });
  const busy = solve.isPending || mark.isPending;
  const result = mode === "doubt" ? solve.data : mark.data;
  const again = () => { setFiles([]); setNote(""); setQuestion(""); solve.reset(); mark.reset(); };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow={<span className="flex items-center gap-1.5"><Camera className="h-3.5 w-3.5" />{tr("Ask with a photo")}</span>}
        title={tr(mode === "doubt" ? "Stuck on a question? Snap it." : "Get your written answer marked")}
        subtitle={tr(mode === "doubt" ? "From a book, a paper or a screen. You get the idea behind it, every step, and the answer."
          : "Photograph an answer you wrote by hand. You get marks like an examiner's, where they were lost, and an answer worth full marks.")} />
      <Segmented className="mb-5" value={mode} onChange={(m) => { setMode(m); }} options={[
        { value: "doubt", label: tr("Solve a question"), icon: <Sparkles className="h-3.5 w-3.5" /> },
        { value: "answer", label: tr("Mark my answer"), icon: <PenLine className="h-3.5 w-3.5" /> },
      ]} />

      {result ? (
        <div className="space-y-4">
          {mode === "doubt" ? <Solved d={solve.data!} /> : <Marked m={mark.data!} />}
          <Button variant="secondary" onClick={again} icon={<RotateCcw className="h-4 w-4" />}>{tr(mode === "doubt" ? "Ask another" : "Mark another answer")}</Button>
        </div>
      ) : (
        <Card className={cn("space-y-4 p-5", busy && "opacity-80")}>
          <Photos files={files} onChange={setFiles} />
          {mode === "doubt" ? (
            <div>
              <Label hint="optional">Anything to add?</Label>
              <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={400} placeholder="e.g. question 14 only, or: I get stuck after the second step" />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_120px]">
              <div>
                <Label hint="if it isn't in the photo">The question</Label>
                <Textarea value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={1500} placeholder="Type or paste the question you answered" className="min-h-20" />
              </div>
              <div>
                <Label>Out of</Label>
                <Input type="number" min={1} max={100} value={marks} onChange={(e) => setMarks(e.target.value)} />
              </div>
            </div>
          )}
          <Button variant="primary" size="lg" disabled={!files.length} loading={busy} onClick={() => (mode === "doubt" ? solve.mutate() : mark.mutate())}
            icon={mode === "doubt" ? <Sparkles className="h-4 w-4" /> : <PenLine className="h-4 w-4" />}>
            {tr(busy ? "Reading your photo…" : mode === "doubt" ? "Solve it" : "Mark it")}
          </Button>
        </Card>
      )}
    </div>
  );
}
