import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Camera, Check, CheckCircle2, ClipboardList, PenLine, RotateCcw, Sparkles, Target, Trophy, X, XCircle } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { AnswerInput } from "@/components/AnswerInput";
import { PageHeader } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { EvaluationCard } from "@/components/TeachBack";
import { Button } from "@/components/ui/button";
import { RoughPad } from "@/components/RoughPad";
import { useCheckWorking, WorkingCheckCard } from "@/components/WorkingCheck";
import { Badge, Card, CardHeader, EmptyState, Kbd, Label, ProgressBar, ProgressRing, Segmented, Select, Skeleton, Textarea } from "@/components/ui/primitives";
import { useFocus } from "@/lib/focus";
import { api, ApiError } from "@/lib/api";
import type { Evaluation, MCQ, Quiz, Subjective, TrueFalse, WeakCheckResult, WorkingCheck } from "@/lib/types";
import { cn, hasSyllabus as examHasSyllabus, LETTERS, timeAgo, shownName } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { ConfidenceLock, verdict, type Confidence } from "@/components/ConfidenceLock";
import { WaitBridge } from "@/components/WaitBridge";
import { CostHint } from "@/components/UsageMeter";
import { useT } from "@/lib/i18n";

type Item = { kind: "mcq"; data: MCQ } | { kind: "tf"; data: TrueFalse } | { kind: "subjective"; data: Subjective };
interface Result { correct: boolean; score?: number }

/* ---------------------------------------------------------------- setup */
type Source = "lecture" | "topic" | "text";

function Setup({ onReady }: { onReady: (q: Quiz) => void }) {
  const tr = useT();
  const [params, setParams] = useSearchParams();
  const preset = params.get("session");
  const presetTopic = params.get("topic");  // "Practise this topic" from the Prep Hub
  const hasSyllabus = useAuth((s) => examHasSyllabus(s.user?.exam_target));
  const [source, setSource] = useState<Source>(presetTopic ? "topic" : "lecture");
  const [sessionId, setSessionId] = useState<string>(preset ?? "");
  const [topicId, setTopicId] = useState(presetTopic ?? "");
  const [text, setText] = useState("");
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  // these papers have no True / False or written answers, so a set in their pattern starts as MCQs only
  const mcqOnly = useAuth((s) => ["jee", "neet", "ssc_cgl"].includes(s.user?.exam_target ?? ""));
  const [nMcq, setNMcq] = useState(presetTopic && !mcqOnly ? "3" : "5");
  const [nTf, setNTf] = useState(mcqOnly ? "0" : presetTopic ? "2" : "3");
  const [nSub, setNSub] = useState(mcqOnly ? "0" : "1");
  const { data: sessions } = useQuery({ queryKey: ["sessions"], queryFn: () => api.sessions({ limit: 200 }) });
  const { data: tree } = useQuery({ queryKey: ["prep-syllabus"], queryFn: () => api.prepSyllabus(), enabled: hasSyllabus, staleTime: 60_000 });
  const chapters = useMemo(() => (tree?.subjects ?? []).flatMap((s) => s.units.flatMap((u) => u.chapters)), [tree]);
  const chapter = chapters.find((c) => c.topics.some((t) => t.id === topicId)) ?? null;
  const withNotes = (sessions ?? []).filter((s) => s.note_count > 0);
  useEffect(() => { if (!sessionId && withNotes[0]) setSessionId(String(withNotes[0].id)); }, [withNotes, sessionId]);
  // no lectures captured yet: open on a syllabus topic (or on pasting material) rather than an empty picker
  const noLectures = sessions !== undefined && !withNotes.length;
  useEffect(() => { if (noLectures && !preset && !presetTopic) setSource(hasSyllabus ? "topic" : "text"); }, [noLectures, preset, presetTopic, hasSyllabus]);
  // nothing picked yet: the topic the student most likely means is the first one they haven't finished
  useEffect(() => {
    if (topicId || !chapters.length) return;
    const next = chapters.flatMap((c) => c.topics).find((t) => !t.done) ?? chapters[0].topics[0];
    setTopicId(next.id);
  }, [chapters, topicId]);

  const gen = useMutation({
    mutationFn: () => api.generateQuiz({
      ...(source === "lecture" ? { session_id: Number(sessionId) } : source === "topic" ? { topic_id: topicId } : { text }),
      difficulty, n_mcq: Number(nMcq), n_tf: Number(nTf), n_subjective: Number(nSub),
    }),
    onSuccess: onReady,
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't build the practice set. Try again."),
  });
  // arriving from "Practise this topic": the set is what they asked for, so start writing it straight away
  const autoStarted = useRef(false);
  useEffect(() => {
    if (!presetTopic || autoStarted.current) return;
    autoStarted.current = true;
    gen.mutate();
    setParams((p) => { p.delete("topic"); return p; }, { replace: true });
  }, [presetTopic, gen, setParams]);
  const ready = source === "lecture" ? !!sessionId : source === "topic" ? !!topicId : text.trim().length >= 40;
  // why Generate can't be pressed yet, said under it rather than leaving a grey button
  const blocked = Number(nMcq) + Number(nTf) + Number(nSub) === 0 ? "Pick at least one question: set MCQs, True / False or Written above 0."
    : ready ? null
    : source === "lecture" ? "Choose a lecture with notes first."
    : source === "topic" ? "Choose a topic first."
    : `Paste at least 40 characters of material (${text.trim().length} so far).`;

  return (
    <Card className="min-w-0 p-4 sm:p-6">
      <div className="mb-5 flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-brand text-brand-fg"><Sparkles className="h-5 w-5" /></div>
        <div>
          <h2 className="font-semibold">{tr("Build a practice set")}</h2>
          <p className="text-[13px] text-muted">{tr("Questions written from exactly what you studied, in your exam's pattern.")}</p>
        </div>
      </div>
      <div className="-mx-1 overflow-x-auto px-1">
        <Segmented value={source} onChange={setSource} options={[
          { value: "lecture" as Source, label: tr("From a lecture") },
          ...(hasSyllabus ? [{ value: "topic" as Source, label: tr("A syllabus topic") }] : []),
          { value: "text" as Source, label: tr("Paste material") },
        ]} />
      </div>
      <div className="mt-4">
        {source === "topic" ? (
          chapters.length ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 [&>*]:min-w-0">
              <div>
                <Label>{tr("Chapter")}</Label>
                <Select aria-label="Chapter" value={chapter?.id ?? ""} onChange={(e) => setTopicId(chapters.find((c) => c.id === e.target.value)?.topics[0].id ?? "")}>
                  {(tree?.subjects ?? []).map((s) => (
                    <optgroup key={s.name} label={s.name}>
                      {s.units.flatMap((u) => u.chapters).map((c) => <option key={c.id} value={c.id}>{shownName(c.name)}</option>)}
                    </optgroup>
                  ))}
                </Select>
              </div>
              <div>
                <Label>{tr("Topic")}</Label>
                <Select aria-label="Topic" value={topicId} onChange={(e) => setTopicId(e.target.value)}>
                  {(chapter?.topics ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}{t.done ? " · studied" : ""}</option>)}
                </Select>
              </div>
            </div>
          ) : <Skeleton className="h-[68px]" />
        ) : source === "lecture" ? (
          withNotes.length ? (
            <Select aria-label="Lecture" value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
              {withNotes.map((s) => <option key={s.id} value={s.id}>{s.title || "Untitled lecture"} · {s.note_count} boards · {timeAgo(s.started_at)}</option>)}
            </Select>
          ) : (
            <div className="rounded-xl border border-line bg-bg-soft p-4 text-sm text-muted">No lectures with notes yet. <Link to="/app/studio" className="text-accent">Capture one</Link> or paste material instead.</div>
          )
        ) : (
          <Textarea value={text} onChange={(e) => setText(e.target.value)} className="min-h-40" placeholder="Paste notes, a textbook paragraph or a list of formulas…" />
        )}
      </div>
      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="sm:col-span-4">
          <Label>{tr("Difficulty")}</Label>
          <Segmented value={difficulty} onChange={setDifficulty} options={[{ value: "easy", label: tr("Warm-up") }, { value: "medium", label: tr("Exam level") }, { value: "hard", label: tr("Advanced") }]} />
        </div>
        {([["MCQs", nMcq, setNMcq, ["0", "3", "5", "8", "10"]], ["True / False", nTf, setNTf, ["0", "2", "3", "5"]], ["Written or spoken", nSub, setNSub, ["0", "1", "2", "3"]]] as const).map(([l, v, set, opts]) => (
          <div key={l}>
            <Label>{tr(l)}</Label>
            <Select aria-label={l} value={v} onChange={(e) => set(e.target.value)}>{opts.map((o) => <option key={o}>{o}</option>)}</Select>
          </div>
        ))}
        <div className="flex items-end">
          <Button variant="primary" className="w-full" loading={gen.isPending} disabled={!!blocked}
            aria-describedby="generate-why" onClick={() => gen.mutate()}>{tr("Generate")}</Button>
        </div>
      </div>
      <div id="generate-why" className="mt-2 sm:text-right">
        {blocked ? <p className="text-[12px] text-warn">{blocked}</p> : <CostHint action="practice_set" />}
      </div>
      {gen.isPending && (
        <WaitBridge kind="practice" className="mt-4" topic={source === "topic" ? chapter?.topics.find((t) => t.id === topicId)?.name ?? chapter?.name : null} />
      )}
    </Card>
  );
}

/* ---------------------------------------------------------------- runner */
function OptionButton({ label, text, state, onClick, kbd }: { label: string; text: string; state: "idle" | "chosen" | "right" | "wrong" | "dim"; onClick: () => void; kbd?: string }) {
  const open = state === "idle" || state === "chosen";  // (a chosen answer can still be changed until it's locked in)
  return (
    <button onClick={onClick} disabled={!open} aria-pressed={state === "chosen"}
      className={cn("group flex w-full items-center gap-3 rounded-xl border px-4 py-3.5 text-left transition",
        state === "idle" && "border-line bg-bg-soft hover:-translate-y-px hover:border-accent/50", state === "chosen" && "border-accent bg-accent-soft",
        state === "right" && "border-ok/50 bg-ok/10", state === "wrong" && "border-bad/50 bg-bad/10", state === "dim" && "border-line opacity-50")}>
      <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg border text-sm font-semibold",
        state === "right" ? "border-ok bg-ok text-white" : state === "wrong" ? "border-bad bg-bad text-white" : "border-line-strong group-hover:border-accent/60")}>
        {state === "right" ? <Check className="h-4 w-4" /> : state === "wrong" ? <X className="h-4 w-4" /> : label}
      </span>
      <Markdown className="flex-1 text-[14.5px] text-fg">{text}</Markdown>
      {kbd && open && <span className="hidden sm:inline-flex"><Kbd>{kbd}</Kbd></span>}
    </button>
  );
}

function Runner({ quiz, onDone }: { quiz: Quiz; onDone: (r: Result[], items: Item[]) => void }) {
  const tr = useT();
  const items: Item[] = useMemo(() => [
    ...quiz.mcq.map((d) => ({ kind: "mcq" as const, data: d })),
    ...quiz.true_false.map((d) => ({ kind: "tf" as const, data: d })),
    ...quiz.subjective.map((d) => ({ kind: "subjective" as const, data: d })),
  ], [quiz]);
  const [i, setI] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);  // picked but not locked in yet
  const [confidence, setConfidence] = useState<Confidence | null>(null);
  const [results, setResults] = useState<Result[]>([]);
  const [answer, setAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const item = items[i];
  const answered = picked !== null || evaluation !== null;
  const [rough, setRough] = useState(false);  // rough work under the question, a page per question
  const [roughKey] = useState(() => `focs-rough-practice-${Date.now()}`);  // this set's own pages
  // the rough page, read and checked (after answering), with the question it belongs to: a check still on its way
  // when the student moves on must not land under the next question
  const [work, setWork] = useState<{ check: WorkingCheck; at: number } | null>(null);
  const checkWork = useCheckWorking(item ? {
    question: item.kind === "tf" ? item.data.statement : item.data.q, topic: quiz.topic, subject: quiz.subject,
    options: item.kind === "mcq" ? item.data.options : item.kind === "tf" ? ["True", "False"] : null,
    answer: item.kind === "mcq" ? item.data.answer_index : item.kind === "tf" ? (item.data.answer ? 0 : 1) : null,
    chosen: picked,
  } : null);

  const record = (correct: boolean, question: string, q_type: string, score?: number, c?: Confidence) => {
    setResults((r) => [...r, { correct, score }]);
    if (q_type !== "subjective") {
      api.attempt({ question, q_type, correct, topic: quiz.topic, subject: quiz.subject, session_id: quiz.session_id, confidence: c }).catch(() => undefined);
    }
  };
  const choose = (k: number) => { if (!answered && item) setChosen(k); };
  const lock = (c: Confidence) => {
    if (answered || !item || chosen === null) return;
    setPicked(chosen);
    setConfidence(c);
    if (item.kind === "mcq") record(chosen === item.data.answer_index, item.data.q, "mcq", undefined, c);
    if (item.kind === "tf") record((chosen === 0) === item.data.answer, item.data.statement, "true_false", undefined, c);
  };
  const grade = useMutation({
    mutationFn: () => api.evaluate({
      question: (item as { data: Subjective }).data.q, student_answer: answer, key_points: (item as { data: Subjective }).data.key_points,
      model_answer: (item as { data: Subjective }).data.model_answer, topic: quiz.topic, subject: quiz.subject, session_id: quiz.session_id,
    }),
    onSuccess: (ev) => { setEvaluation(ev); record(ev.score >= 6, (item as { data: Subjective }).data.q, "subjective", ev.score); },
  });
  // maths is slow to type: a photo of the written answer is read and graded the same way
  const photoInput = useRef<HTMLInputElement>(null);
  const gradePhoto = useMutation({
    mutationFn: (photo: File) => api.evaluatePhoto({
      question: (item as { data: Subjective }).data.q, key_points: (item as { data: Subjective }).data.key_points,
      model_answer: (item as { data: Subjective }).data.model_answer, topic: quiz.topic, subject: quiz.subject, session_id: quiz.session_id,
    }, photo),
    onSuccess: (ev) => { setEvaluation(ev); record(ev.score >= 6, (item as { data: Subjective }).data.q, "subjective", ev.score); },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Couldn't read that photo. Try again."),
  });
  const next = (latest: Result[] = results) => {
    if (i + 1 >= items.length) return onDone(latest, items);
    setI(i + 1); setPicked(null); setChosen(null); setConfidence(null); setAnswer(""); setEvaluation(null); setWork(null); checkWork.reset();
  };
  const skip = () => {
    const latest = [...results, { correct: false, score: 0 }];
    setResults(latest);
    next(latest);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === "TEXTAREA") return;
      if (!answered && item?.kind === "mcq" && ["1", "2", "3", "4"].includes(e.key)) choose(Number(e.key) - 1);
      if (!answered && item?.kind === "tf" && (e.key === "t" || e.key === "f")) choose(e.key === "t" ? 0 : 1);
      if (answered && e.key === "Enter") next();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!item) return <EmptyState icon={<ClipboardList className="h-6 w-6" />} title={tr("No questions could be generated")} body="Try a lecture with more boards, or paste more material." />;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2">
        <Badge tone="accent">{quiz.topic}</Badge>
        <span className="whitespace-nowrap text-sm text-muted">Question {i + 1} of {items.length}</span>
        <ProgressBar value={(100 * i) / items.length} className="min-w-[8rem] flex-1 basis-full sm:basis-auto" />
        <Button size="sm" variant={rough ? "primary" : "secondary"} aria-pressed={rough} onClick={() => setRough(!rough)} icon={<PenLine className="h-3.5 w-3.5" />}>Rough</Button>
      </div>
      {quiz.notice && <p role="status" className="mb-4 rounded-xl border border-warn/40 bg-bg-soft px-4 py-3 text-[13px] text-fg-soft">{quiz.notice}</p>}
      <AnimatePresence mode="wait">
        <motion.div key={i} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.2 }}>
          <Card className="p-6 sm:p-8">
            <div className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-muted">
              {item.kind === "mcq" ? "Multiple choice" : item.kind === "tf" ? "True or false" : "Written or spoken answer"}
            </div>
            <Markdown className="text-[17px] leading-relaxed text-fg">{item.kind === "tf" ? item.data.statement : item.data.q}</Markdown>

            <div className="mt-6 space-y-2.5">
              {item.kind === "mcq" && item.data.options.map((o, k) => (
                <OptionButton key={k} label={LETTERS[k]} text={o} kbd={String(k + 1)} onClick={() => choose(k)}
                  state={picked === null ? (chosen === k ? "chosen" : "idle") : k === item.data.answer_index ? "right" : k === picked ? "wrong" : "dim"} />
              ))}
              {item.kind === "tf" && (["True", "False"] as const).map((o, k) => {
                const correctIdx = item.data.answer ? 0 : 1;
                return <OptionButton key={o} label={o[0]} text={o} kbd={o[0]} onClick={() => choose(k)}
                  state={picked === null ? (chosen === k ? "chosen" : "idle") : k === correctIdx ? "right" : k === picked ? "wrong" : "dim"} />;
              })}
              {item.kind !== "subjective" && picked === null && <ConfidenceLock ready={chosen !== null} onLock={lock} />}
              {item.kind === "subjective" && !evaluation && (
                <>
                  <AnswerInput value={answer} onChange={setAnswer} hint={item.data.q} disabled={grade.isPending}
                    placeholder="Write your answer like you would in the exam, or say it out loud…" />
                  <input ref={photoInput} type="file" accept="image/*" capture="environment" className="hidden" aria-label="Photo of your answer"
                    onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) gradePhoto.mutate(f); }} />
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button variant="ghost" onClick={skip} disabled={gradePhoto.isPending}>{tr("Skip")}</Button>
                    <Button variant="secondary" loading={gradePhoto.isPending} disabled={grade.isPending} onClick={() => photoInput.current?.click()}
                      icon={<Camera className="h-4 w-4" />}>{tr(gradePhoto.isPending ? "Reading your answer…" : "Photo of my answer")}</Button>
                    <Button variant="primary" disabled={answer.trim().length < 8 || gradePhoto.isPending} loading={grade.isPending} onClick={() => grade.mutate()} icon={<PenLine className="h-4 w-4" />}>{tr("Grade my answer")}</Button>
                  </div>
                </>
              )}
            </div>

            {answered && (
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-6 space-y-4">
                {item.kind !== "subjective" ? (
                  <div className="rounded-xl border border-line bg-bg-soft p-4">
                    {(() => {
                      const ok = !!results[results.length - 1]?.correct;
                      const said = verdict(ok, confidence);
                      return (
                        <div className={cn("mb-1 flex items-center gap-2 text-sm font-semibold", said.tone === "ok" ? "text-ok" : said.tone === "warn" ? "text-warn" : "text-bad")}>
                          {ok ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}{said.text}
                        </div>
                      );
                    })()}
                    {item.data.explanation && <Markdown className="text-sm">{item.data.explanation}</Markdown>}
                  </div>
                ) : evaluation && (
                  <>
                    {evaluation.read_answer && (
                      <div className="rounded-xl border border-line bg-bg-soft p-4">
                        <div className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-muted">What Focs read in your photo</div>
                        <Markdown className="text-sm">{evaluation.read_answer}</Markdown>
                      </div>
                    )}
                    <EvaluationCard evaluation={evaluation} modelAnswer={item.data.model_answer} />
                  </>
                )}
                {work?.at === i && <WorkingCheckCard check={work.check} onClose={() => setWork(null)} />}
                {work?.at !== i && !rough && (
                  <button type="button" onClick={() => setRough(true)} className="inline-flex items-center gap-1.5 text-[13px] font-medium text-accent hover:underline">
                    <PenLine className="h-3.5 w-3.5" /> Write your working on the rough pad: Focs finds the exact step that went wrong
                  </button>
                )}
                <div className="flex justify-end">
                  <Button variant="primary" onClick={() => next()}>{i + 1 >= items.length ? "See results" : "Next question"} <ArrowRight className="h-4 w-4" /><span className="hidden sm:inline-flex"><Kbd>↵</Kbd></span></Button>
                </div>
              </motion.div>
            )}
          </Card>
        </motion.div>
      </AnimatePresence>
      {rough && <>
        <div aria-hidden className="h-[50dvh]" />{/* room to scroll the question above the pad */}
        <RoughPad storageKey={roughKey} page={String(i)} onClose={() => setRough(false)} className="fixed inset-x-0 bottom-0 z-40 shadow-2xl"
          onCheck={answered ? (image) => { const at = i; checkWork.mutate(image, { onSuccess: (check) => setWork({ check, at }) }); } : undefined} checking={checkWork.isPending} />
      </>}
    </div>
  );
}

/* ---------------------------------------------------------------- results + redo */
function Results({ results, items, onAgain, check }: { results: Result[]; items: Item[]; onAgain: () => void; check: WeakCheckResult | null }) {
  const tr = useT();
  const correct = results.filter((r) => r.correct).length;
  const pct = Math.round((100 * correct) / Math.max(1, results.length));
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      {check?.weak && (  // this topic was a weak spot from a test: the set doubled as its re-check
        <Link to="/app/weak" className={cn("flex items-center gap-3 rounded-2xl border p-4 transition",
          check.cleared ? "border-ok/30 bg-ok/[0.07] hover:border-ok/50" : "border-warn/30 bg-warn/[0.07] hover:border-warn/50")}>
          <span className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-xl", check.cleared ? "bg-ok/15 text-ok" : "bg-warn/15 text-warn")}>
            {check.cleared ? <CheckCircle2 className="h-5 w-5" /> : <Target className="h-5 w-5" />}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold">{check.cleared ? "Weak spot cleared" : "This weak spot isn't clear yet"}</span>
            <span className="block text-[13px] text-muted">
              {check.cleared ? `${check.percent}% on a topic your test showed as weak. It's off your fix-it plan.`
                : !check.enough_questions ? "Too few questions to tell. Try a set of four or more on this topic."
                : `${check.percent}% here; ${check.needed}% clears it. Read the detailed notes once more, then try another set.`}
            </span>
          </span>
          <ArrowRight className="h-4 w-4 shrink-0 text-muted" />
        </Link>
      )}
      <Card className="noise relative overflow-hidden p-8 text-center">
        <div className="relative flex flex-col items-center">
          <ProgressRing value={pct} size={128} stroke={10}>
            <div><div className="text-3xl font-semibold">{pct}%</div><div className="text-xs text-muted">{correct}/{results.length}</div></div>
          </ProgressRing>
          <h2 className="mt-5 flex items-center gap-2 text-xl font-semibold">
            <Trophy className="h-5 w-5 text-warn" />{tr(pct >= 80 ? "Exam ready." : pct >= 50 ? "Solid — revise the misses." : "Good start. Review and retry.")}
          </h2>
          <div className="mt-5 flex gap-2">
            <Button variant="primary" onClick={onAgain} icon={<RotateCcw className="h-4 w-4" />}>{tr("New set")}</Button>
            <Link to="/app/flashcards"><Button>{tr("Review flashcards")}</Button></Link>
          </div>
        </div>
      </Card>
      <Card className="divide-y divide-line">
        {items.map((it, k) => (
          <div key={k} className="flex items-start gap-3 px-5 py-3.5">
            {results[k]?.correct ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-ok" /> : <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-bad" />}
            <Markdown className="line-clamp-2 flex-1 text-sm">{it.kind === "tf" ? it.data.statement : it.data.q}</Markdown>
          </div>
        ))}
      </Card>
    </div>
  );
}

function RedoQueue() {
  const tr = useT();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["redo"], queryFn: api.redo });
  const done = useMutation({ mutationFn: api.redoDone, onSuccess: () => { qc.invalidateQueries({ queryKey: ["redo"] }); qc.invalidateQueries({ queryKey: ["overview"] }); } });
  return (
    <Card>
      <CardHeader title={tr("Redo queue")} subtitle={tr("Questions you got wrong — revisit them")} icon={<RotateCcw className="h-4 w-4" />} />
      <div className="max-h-[560px] space-y-2 overflow-y-auto p-4">
        {data?.length === 0 && <p className="py-6 text-center text-sm text-muted">Nothing to redo. Nice.</p>}
        {data?.map((r) => (
          <div key={r.id} className="group rounded-xl border border-line bg-bg-soft p-3">
            <div className="flex items-center gap-2 text-[11px] text-muted">
              <Badge>{r.q_type}</Badge>{r.topic}<span className="ml-auto">{timeAgo(r.attempted_at)}</span>
            </div>
            <Markdown className="mt-2 line-clamp-3 text-[13px]">{r.question ?? ""}</Markdown>
            <button onClick={() => done.mutate(r.id)} className="mt-2 text-xs font-medium text-accent opacity-80 hover:opacity-100">{tr("Mark as understood")}</button>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function Practice() {
  const tr = useT();
  useFocus("practice", true, true);
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [final, setFinal] = useState<{ results: Result[]; items: Item[] } | null>(null);
  const [check, setCheck] = useState<WeakCheckResult | null>(null);
  const qc = useQueryClient();
  const reset = () => { setQuiz(null); setFinal(null); setCheck(null); };
  const finish = (results: Result[], items: Item[]) => {
    setFinal({ results, items });
    qc.invalidateQueries({ queryKey: ["redo"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
    if (quiz?.topic_id && results.length) {  // a set on a syllabus topic is also the re-check of a weak spot on it
      api.weakCheck(quiz.topic_id, results.filter((r) => r.correct).length, results.length)
        .then((c) => { setCheck(c); if (c.weak) for (const key of ["weak", "prep-plan", "last-day"]) qc.invalidateQueries({ queryKey: [key] }); })
        .catch(() => undefined);
    }
  };

  if (final) return <Results {...final} onAgain={reset} check={check} />;
  if (quiz) return <Runner quiz={quiz} onDone={finish} />;

  return (
    <div>
      <PageHeader title={tr("Practice")} subtitle={tr("An exam-pattern practice set from any lecture or syllabus topic. Answer by tapping, typing or speaking.")} eyebrow={<span className="flex items-center gap-1.5"><Target className="h-3.5 w-3.5" />Active recall</span>} />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Setup onReady={setQuiz} />
        <RedoQueue />
      </div>
    </div>
  );
}
