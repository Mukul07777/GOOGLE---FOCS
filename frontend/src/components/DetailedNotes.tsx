import { useMutation, type UseQueryResult } from "@tanstack/react-query";
import { Check, ClipboardCheck, Clock, Eye, FileQuestion, Flag, LibraryBig, Loader2, Printer, RefreshCw, ScanText, Target, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Markdown } from "@/components/Markdown";
import { ReadAloud } from "@/components/ReadAloud";
import { SheetSections, splitSections } from "@/components/RevisionSheet";
import { ScrollX } from "@/components/ScrollX";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { displayStyle } from "@/lib/math";
import { printNode } from "@/lib/print";
import type { DetailedNotes as Notes, ExamQuestion } from "@/lib/types";
import { canTest, cn, LETTERS, usesCourses, langAttr } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { WaitBridge } from "@/components/WaitBridge";

const WORDS_A_MINUTE = 180;  // a careful read, formulas included

/* ---------------------------------------------------------------- exam questions that come with a note */
function QuestionCard({ q, index }: { q: ExamQuestion; index: number }) {
  const [picked, setPicked] = useState<number | null>(null);
  const [shown, setShown] = useState(false);
  const mcq = q.qtype === "mcq" && !!q.options?.length;
  const right = Number(q.answer);
  const revealed = shown || picked !== null;
  return (
    <div className="rounded-xl border border-line bg-bg-soft p-4">
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <span className="grid h-6 w-6 place-items-center rounded-md bg-accent-soft text-xs font-semibold text-accent">{index}</span>
        {q.real ? <Badge tone="accent">{q.paper}</Badge> : <Badge>Exam-style question</Badge>}
        {q.difficulty && <Badge tone={q.difficulty === "hard" ? "bad" : q.difficulty === "easy" ? "ok" : "warn"}>{q.difficulty}</Badge>}
      </div>
      <Markdown className="text-fg">{displayStyle(q.question)}</Markdown>
      {mcq && (
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {q.options!.map((o, i) => {
            const state = !revealed ? "idle" : i === right ? "right" : i === picked ? "wrong" : "dim";
            return (
              <button key={i} type="button" disabled={revealed} onClick={() => setPicked(i)}
                className={cn("flex items-center gap-2.5 rounded-lg border px-3 py-2 text-left transition",
                  state === "idle" && "border-line bg-panel hover:border-accent/50", state === "right" && "border-ok/50 bg-ok/10",
                  state === "wrong" && "border-bad/50 bg-bad/10", state === "dim" && "border-line opacity-60")}>
                <span className={cn("grid h-6 w-6 shrink-0 place-items-center rounded-md border text-xs font-semibold",
                  state === "right" ? "border-ok bg-ok text-white" : state === "wrong" ? "border-bad bg-bad text-white" : "border-line-strong")}>
                  {state === "right" ? <Check className="h-3.5 w-3.5" /> : state === "wrong" ? <X className="h-3.5 w-3.5" /> : LETTERS[i]}
                </span>
                <Markdown className="min-w-0 flex-1 [&_p]:my-0">{displayStyle(o)}</Markdown>
              </button>
            );
          })}
        </div>
      )}
      {!revealed && (
        <button type="button" onClick={() => setShown(true)} className="no-print mt-3 inline-flex items-center gap-1.5 text-[13px] font-medium text-accent hover:underline">
          <Eye className="h-3.5 w-3.5" />{mcq ? "Show the answer and solution" : "Show the answer"}
        </button>
      )}
      <div className={cn("mt-3 border-t border-line pt-3", !revealed && "print-only")}>
        {picked !== null && <div className={cn("mb-1 text-sm font-semibold", picked === right ? "text-ok" : "text-bad")}>{picked === right ? "Correct." : "Not this one."}</div>}
        <div className="text-sm font-semibold text-fg">Answer: {mcq ? `(${LETTERS[right] ?? "?"})` : q.answer}</div>
        {q.solution && <Markdown className="mt-1">{q.solution}</Markdown>}
      </div>
    </div>
  );
}

function ExamQuestions({ questions, anchor, topical }: { questions: ExamQuestion[]; anchor: string; topical: boolean }) {
  const real = questions.some((q) => q.real);
  const offTopic = topical && questions.every((q) => q.match === "chapter");
  return (
    <section id={anchor} className="panel scroll-mt-4 overflow-hidden p-5" style={{ borderLeft: "3px solid var(--accent)" }}>
      <h3 className="mb-1 flex items-center gap-2 text-[15px] font-semibold tracking-tight">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent-soft text-accent"><FileQuestion className="h-4 w-4" /></span>
        {real ? "Asked in the exam" : "Try an exam-style question"}
      </h3>
      <p className="mb-3 text-[13px] text-muted">
        {offTopic ? "No past question on exactly this topic in the question bank yet. These are from the same chapter."
          : !real ? "Try it before opening the solution."
          : questions.every((q) => q.real) ? "Real past questions on this. Try each one before opening its solution."
          : "Real past questions first, then exam-style ones. Try each before opening its solution."}
      </p>
      <div className="space-y-3">{questions.map((q, i) => <QuestionCard key={q.id} q={q} index={i + 1} />)}</div>
    </section>
  );
}

/* ---------------------------------------------------------------- the reader */
function Loading({ what }: { what: string }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 1800);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 py-24 text-center text-sm text-muted">
      {slow ? <WaitBridge kind="notes" className="w-full text-left" /> : <><Loader2 className="h-6 w-6 animate-spin text-accent" />{`Opening the ${what}…`}</>}
    </div>
  );
}

/** Detailed notes (or a revision capsule) in a view made for reading: one wide column, a bar to jump between
    sections, how long the read is, the exam questions that go with the note, and a way straight to a test on it. */
export function NotesReader({ open, onClose, query, label = "Detailed notes", title }: {
  open: boolean; onClose: () => void; query: UseQueryResult<Notes>; label?: string;
  /** shown while the note loads */
  title?: string | null;
}) {
  const navigate = useNavigate();
  const examTarget = useAuth((s) => s.user?.exam_target);
  const college = usesCourses(examTarget);
  const uid = `notes-${useId().replace(/:/g, "")}`;
  const notes = query.data;
  const sections = useMemo(() => (notes ? splitSections(notes.notes_md) : []), [notes]);
  const minutes = useMemo(() => (notes ? Math.max(1, Math.round(notes.notes_md.split(/\s+/).length / WORDS_A_MINUTE)) : 0), [notes]);
  const page = useRef<HTMLDivElement>(null);
  // a test on what was just read: a practice set on the topic, or a chapter test on its chapter
  const topicId = notes?.source === "library" ? notes.topic_id : undefined;
  const chapterTest = notes?.source === "library" && !!notes.chapter && canTest(notes.subject, examTarget);
  const practise = () => { onClose(); navigate(`/app/practice?topic=${encodeURIComponent(topicId!)}`); };
  const test = useMutation({
    mutationFn: () => api.createChapterTest(notes!.subject!, [notes!.chapter!], 15),
    onSuccess: (t) => { onClose(); navigate(`/app/mock/${t.id}`); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start the test"),
  });
  const report = useMutation({
    mutationFn: () => api.reportTopicNotes(notes!.topic_id!),
    onSuccess: () => toast.success("Thanks. Notes that several students flag are checked and written again."),
    onError: () => toast.error("Couldn't send that. Try again."),
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [open, onClose]);

  const library = notes?.source === "library";
  const meta = notes && library ? [notes.subject, notes.chapter !== notes.title ? notes.chapter : null].filter(Boolean).join(" › ") : "";
  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  const icon = "grid h-9 w-9 place-items-center rounded-lg text-fg-soft transition hover:bg-elev-2 hover:text-fg disabled:opacity-35";

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[55] flex justify-center sm:p-5" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/65 backdrop-blur-sm" onClick={onClose} />
          <motion.div role="dialog" aria-modal="true" aria-label={notes?.title ?? title ?? label}
            className="relative z-10 flex h-full w-full max-w-4xl flex-col overflow-hidden border-line bg-bg shadow-2xl sm:rounded-2xl sm:border"
            initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 12, opacity: 0 }} transition={{ type: "spring", stiffness: 380, damping: 34 }}>
            <header className="flex items-start gap-2 border-b border-line bg-panel px-4 py-3 sm:px-6 sm:py-4">
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">{label}</div>
                <h2 className="mt-0.5 text-lg font-semibold leading-snug tracking-tight sm:text-xl">{notes?.title ?? title ?? ""}</h2>
                {(meta || minutes > 0) && (
                  <div className="mt-0.5 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-xs text-muted">
                    {meta && <span>{meta}</span>}
                    {minutes > 0 && <span className="inline-flex items-center gap-1"><Clock className="h-3 w-3" />{minutes} min read</span>}
                  </div>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-1">
                {(topicId || chapterTest) && (
                  <Button size="sm" variant="primary" loading={test.isPending} onClick={() => (topicId ? practise() : test.mutate())}
                    icon={topicId ? <Target className="h-3.5 w-3.5" /> : <ClipboardCheck className="h-3.5 w-3.5" />}
                    title={topicId ? "A practice set on exactly this topic" : "A 15-question test on this chapter"}>
                    <span className="hidden sm:inline">{topicId ? "Test this topic" : "Chapter test"}</span><span className="sm:hidden">Test</span>
                  </Button>
                )}
                {notes && <ReadAloud text={notes.notes_md} label="Listen" />}
                <button type="button" className={cn(icon, "hidden sm:grid")} disabled={!notes} title="Print or save as PDF" aria-label="Print or save as PDF"
                  onClick={() => page.current && printNode(page.current, notes?.title ?? label)}><Printer className="h-4 w-4" /></button>
                <button type="button" className={icon} onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
              </div>
            </header>

            {notes && sections.length > 1 && (
              <nav className="border-b border-line bg-panel/60 px-4 py-2 sm:px-6" aria-label="Sections">
                <ScrollX quiet>
                  <div className="flex w-max gap-1.5">
                    {sections.map((s, i) => (
                      <button key={i} type="button" onClick={() => jump(`${uid}-${i}`)}
                        className="whitespace-nowrap rounded-full border border-line bg-bg-soft px-3 py-1 text-xs font-medium text-fg-soft transition hover:border-accent/50 hover:text-fg">
                        {s.heading}
                      </button>
                    ))}
                    {!!notes.questions?.length && (
                      <button type="button" onClick={() => jump(`${uid}-pyq`)}
                        className="whitespace-nowrap rounded-full border border-accent/40 bg-accent-soft px-3 py-1 text-xs font-medium text-accent transition hover:border-accent/70">
                        {notes.questions.some((q) => q.real) ? "Past questions" : "Exam-style questions"} · {notes.questions.length}
                      </button>
                    )}
                  </div>
                </ScrollX>
              </nav>
            )}

            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6 sm:py-6">
              {notes ? (
                <div className="mx-auto max-w-3xl">
                  <div ref={page} className="notes-reader space-y-4">
                    <div className="print-only">
                      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">{label}</div>
                      <h2 className="mt-1 text-xl font-semibold tracking-tight">{notes.title}</h2>
                      {meta && <div className="mt-0.5 text-xs text-muted">{meta}</div>}
                    </div>
                    {notes.language_note && <p className="no-print rounded-xl border border-warn/30 bg-warn/10 px-3 py-2 text-[13px] text-fg-soft">{notes.language_note}</p>}
                    <div lang={langAttr(notes.language)}><SheetSections markdown={notes.notes_md} anchor={uid} display /></div>
                    {!!notes.questions?.length && <ExamQuestions questions={notes.questions} anchor={`${uid}-pyq`} topical={!!notes.topic_id} />}
                  </div>
                  {(topicId || chapterTest) && (
                    <div className="no-print mt-4 flex flex-col gap-3 rounded-2xl border border-accent/30 bg-accent-soft/50 p-4 sm:flex-row sm:items-center">
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-semibold">Read it? Now check it has stuck.</div>
                        <p className="mt-0.5 text-[13px] text-muted">
                          {topicId ? "A short practice set on exactly this topic" : "A timed test on this chapter"}
                          {topicId && chapterTest ? `, or a timed test on the whole chapter (${notes.chapter}).` : "."}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        {topicId && <Button size="sm" variant="primary" onClick={practise} icon={<Target className="h-3.5 w-3.5" />}>Practise this topic</Button>}
                        {chapterTest && (
                          <Button size="sm" variant={topicId ? "secondary" : "primary"} loading={test.isPending} onClick={() => test.mutate()}
                            icon={<ClipboardCheck className="h-3.5 w-3.5" />}>Chapter test · 15 Q</Button>
                        )}
                      </div>
                    </div>
                  )}
                  <div className="mt-5 flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-1 text-xs leading-relaxed text-muted">
                    <span className="flex min-w-0 flex-1 basis-64 gap-1.5">
                      {library ? <LibraryBig className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <ScanText className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
                      <span>
                        {library ? `From the Focs notes library: written by AI for this syllabus ${notes.topic_id ? "topic" : "chapter"}` : "Written by AI from this board"}
                        {notes.checked ? ", then checked by a second model." : "."} If something looks off, go with your {college ? "professor or the textbook" : "teacher or NCERT"}.
                      </span>
                    </span>
                    {library && notes.topic_id && (
                      <button type="button" disabled={report.isPending || report.isSuccess} onClick={() => report.mutate()}
                        className="inline-flex items-center gap-1 font-medium text-fg-soft hover:text-fg disabled:opacity-60">
                        <Flag className="h-3 w-3" />{report.isSuccess ? "Reported" : "Report a mistake"}
                      </button>
                    )}
                  </div>
                </div>
              ) : query.error ? (
                <div className="mx-auto mt-16 flex max-w-md flex-col items-center gap-4 text-center text-sm text-fg-soft">
                  <p>{query.error instanceof ApiError ? query.error.message : `Couldn't open the ${label.toLowerCase()}.`}</p>
                  <Button size="sm" variant="secondary" onClick={() => query.refetch()} icon={<RefreshCw className="h-3.5 w-3.5" />}>Try again</Button>
                </div>
              ) : <Loading what={label.toLowerCase()} />}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
