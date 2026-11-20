import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Layers3, Zap } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge, Card, Segmented } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { MockMeta } from "@/lib/types";
import { cn, subjectColor } from "@/lib/utils";

const MAX_CHAPTERS = 6;

/** Pick a subject and up to six chapters; a short NTA-style test is ready in seconds (or written fresh if needed).
    A B.Tech student picks one of their subjects: no chapter picked means the whole subject. */
export function ChapterTestCard({ meta, busy }: { meta: MockMeta; busy: boolean }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const college = meta.exam === "college" || meta.exam === "gate";  // subjects are courses: a whole one can be tested
  const plain = college || meta.exam === "cbse";  // one mark a question, nothing off for a wrong answer
  const subjects = Object.keys(meta.syllabus);
  const [picked, setSubject] = useState(subjects[0]);
  const subject = subjects.includes(picked) ? picked : subjects[0];  // (their subjects can change under this card)
  const [chapters, setChapters] = useState<string[]>([]);
  const [count, setCount] = useState("15");
  const stock = meta.chapter_stock[subject] ?? {};
  const all = meta.syllabus[subject] ?? [];
  const most = college ? all.length : MAX_CHAPTERS;
  const whole = college && chapters.length === 0;

  const toggle = (c: string) =>
    setChapters((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : cur.length < most ? [...cur, c] : cur));
  const create = useMutation({
    mutationFn: () => api.createChapterTest(subject, chapters, Number(count)),
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ["mocks"] });
      navigate(`/app/mock/${t.id}`);
    },
  });
  const covered = whole ? all : chapters;
  const ready = covered.length > 0 && covered.reduce((n, c) => n + (stock[c] ?? 0), 0) >= Number(count);
  const n = Number(count);  // the same times as the server's chapter_pattern
  const minutes = plain ? Math.max(10, Math.round(n * 1.5)) : meta.exam === "neet" ? Math.max(5, Math.round(n * 1.1))
    : meta.exam === "ssc_cgl" ? Math.max(5, Math.round(n * 0.6)) : n * 2;

  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-lg font-semibold"><Layers3 className="h-5 w-5 text-accent-2" />{college ? "Test a subject" : "Chapter test"}</div>
          <p className="mt-1 text-sm text-muted">
            {college ? "The whole subject before its exam, or just the chapters you've finished. Timed, with your score, weak chapters and time use at the end."
              : "Practise just what you studied today — same exam screen, marking and analysis. Doesn't use your weekly mock."}
          </p>
        </div>
        {!college && <Segmented size="sm" value={subject} onChange={(s) => { setSubject(s); setChapters([]); }}
          options={subjects.map((s) => ({ value: s, label: s }))} />}
      </div>
      {college && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {subjects.map((s) => (
            <button key={s} type="button" aria-pressed={s === subject} onClick={() => { setSubject(s); setChapters([]); }}
              className={cn("inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-[13px] font-medium transition",
                s === subject ? "border-accent/60 bg-accent-soft" : "border-line bg-bg-soft text-fg-soft hover:border-line-strong")}>
              <span className="h-2 w-2 rounded-full" style={{ background: subjectColor(s) }} />{s}
            </button>
          ))}
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-1.5">
        {college && (
          <button type="button" onClick={() => setChapters([])}
            className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-2 min-h-9 text-[12.5px] font-medium transition",
              whole ? "border-transparent text-white" : "border-line bg-bg-soft text-fg-soft hover:border-line-strong")}
            style={whole ? { background: subjectColor(subject) } : undefined}>
            {whole && <Check className="h-3 w-3" />}Whole subject
          </button>
        )}
        {all.map((c) => {
          const on = chapters.includes(c);
          return (
            <button key={c} type="button" onClick={() => toggle(c)}
              className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-2 min-h-9 text-[12.5px] transition",
                on ? "border-transparent text-white" : "border-line bg-bg-soft text-fg-soft hover:border-line-strong",
                !on && chapters.length >= most && "opacity-40")}
              style={on ? { background: subjectColor(subject) } : undefined}>
              {on && <Check className="h-3 w-3" />}{c}
              {(stock[c] ?? 0) >= 5 && !on && <Zap className="h-3 w-3 text-ok" aria-label="ready instantly" />}
            </button>
          );
        })}
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Segmented value={count} onChange={setCount}
          options={meta.chapter_sizes.map((n) => ({ value: String(n), label: `${n} Q` }))} />
        <span className="text-xs text-muted">{minutes} minutes · {plain ? "1 mark each, no negative marking" : "+4 / −1"}</span>
        <span className="flex-1" />
        {covered.length > 0 && !ready && <Badge tone="warn">Fresh questions will be written (uses AI allowance)</Badge>}
        <Button variant="primary" disabled={!covered.length || busy} loading={create.isPending} onClick={() => create.mutate()}>
          {whole ? "Start subject test" : "Start chapter test"}
        </Button>
      </div>
      {create.isError && <p className="mt-2 text-xs text-bad">{create.error instanceof Error ? create.error.message : "Couldn't start the test."}</p>}
      <p className="mt-2 text-[11.5px] text-muted">
        <Zap className="mr-1 inline h-3 w-3 text-ok" />ready instantly · {college ? "pick chapters, or leave it on the whole subject" : `pick up to ${MAX_CHAPTERS} chapters`}
      </p>
    </Card>
  );
}
