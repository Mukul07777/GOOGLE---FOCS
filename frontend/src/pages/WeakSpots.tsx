import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen, Check, CircleCheckBig, ClipboardCheck, Crosshair, FileUp, Minus, Plus, RotateCcw, ScanText, Target, Trash2, Undo2, X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { NotesReader } from "@/components/DetailedNotes";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, CardHeader, EmptyState, Input, Label, Select, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { SyllabusChapter, WeakDraft, WeakDraftItem, WeakOverview, WeakSpot } from "@/lib/types";
import { canTest, cn, formatDate, isCollege, subjectColor } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { CalibrationCard } from "@/components/CalibrationCard";
import { WaitBridge } from "@/components/WaitBridge";
import { useT } from "@/lib/i18n";

const today = () => new Date().toLocaleDateString("en-CA");
const pct = (score: number | null, max: number | null) => (score !== null && max ? Math.round((100 * score) / max) : null);

/* ---------------------------------------------------------------- adding a test */
function WeakRow({ item, chapter, onChange, onRemove }: {
  item: WeakDraftItem; chapter: SyllabusChapter | undefined; onChange: (patch: Partial<WeakDraftItem>) => void; onRemove: () => void;
}) {
  const step = "grid h-7 w-7 place-items-center rounded-md border border-line bg-elev-2 text-fg-soft transition hover:border-line-strong disabled:opacity-40";
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-bg-soft p-2.5">
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: subjectColor(item.subject) }} />
      <div className="min-w-40 flex-1">
        <div className="truncate text-[13px] font-medium">{item.chapter}</div>
        {item.note && <div className="truncate text-[11px] text-muted">{item.note}</div>}
      </div>
      <Select value={item.topic_id ?? ""} aria-label={`Topic of ${item.chapter}`} className="h-8 w-full min-w-0 text-xs sm:w-56"
        onChange={(e) => onChange({ topic_id: e.target.value || null, topic: chapter?.topics.find((t) => t.id === e.target.value)?.name ?? null })}>
        <option value="">The whole chapter</option>
        {(chapter?.topics ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
      </Select>
      <div className="flex items-center gap-1.5" title="Questions you lost on it">
        <button type="button" className={step} disabled={item.misses <= 1} onClick={() => onChange({ misses: item.misses - 1 })} aria-label="One question fewer"><Minus className="h-3 w-3" /></button>
        <span className="w-12 text-center text-xs tabular-nums"><b className="text-sm">{item.misses}</b> lost</span>
        <button type="button" className={step} disabled={item.misses >= 50} onClick={() => onChange({ misses: item.misses + 1 })} aria-label="One question more"><Plus className="h-3 w-3" /></button>
      </div>
      <button type="button" onClick={onRemove} aria-label={`Remove ${item.chapter}`} className="grid h-7 w-7 place-items-center rounded-md text-muted hover:bg-elev-2 hover:text-fg"><X className="h-3.5 w-3.5" /></button>
    </div>
  );
}

function AddTestDialog({ open, onClose, reader, maxFiles }: { open: boolean; onClose: () => void; reader: WeakOverview["reader"]; maxFiles: number }) {
  const tr = useT();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [draft, setDraft] = useState<WeakDraft | null>(null);
  const [manual, setManual] = useState(false);
  const [title, setTitle] = useState("");
  const [score, setScore] = useState("");
  const [max, setMax] = useState("");
  const [takenOn, setTakenOn] = useState(today());
  const [weak, setWeak] = useState<WeakDraftItem[]>([]);
  const [pick, setPick] = useState("");
  const reviewing = !!draft || manual;
  const college = useAuth((s) => isCollege(s.user?.exam_target));
  const { data: tree } = useQuery({ queryKey: ["prep-syllabus"], queryFn: () => api.prepSyllabus(), enabled: open, staleTime: 60_000 });
  const chapters = useMemo(() => new Map((tree?.subjects ?? []).flatMap((s) => s.units.flatMap((u) => u.chapters)).map((c) => [c.id, c])), [tree]);

  useEffect(() => {  // a fresh dialog every time
    if (!open) return;
    setFiles([]); setDraft(null); setManual(false); setTitle(""); setScore(""); setMax(""); setTakenOn(today()); setWeak([]); setPick("");
  }, [open]);

  const read = useMutation({
    mutationFn: () => api.weakRead(files),
    onSuccess: (d) => {
      setDraft(d);
      setWeak(d.weak);
      setTitle((t) => t || d.title || "");
      setScore((s) => s || (d.score !== null ? String(d.score) : ""));
      setMax((m) => m || (d.max_score !== null ? String(d.max_score) : ""));
      qc.invalidateQueries({ queryKey: ["usage"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't read that result. Try again, or mark the weak topics yourself."),
  });
  const save = useMutation({
    mutationFn: () => api.weakAddTest({
      title: title.trim() || "Test", taken_on: takenOn || undefined, score: score === "" ? undefined : Number(score), max_score: max === "" ? undefined : Number(max),
      source: draft ? "upload" : "manual", subjects: draft?.subjects ?? [],
      weak: weak.map(({ chapter_id, topic_id, misses, note }) => ({ chapter_id, topic_id, misses, note })),
    }),
    onSuccess: (o) => {
      qc.setQueryData(["weak"], o);
      for (const key of ["prep-plan", "last-day"]) qc.invalidateQueries({ queryKey: [key] });
      toast.success(weak.length ? `Saved. ${weak.length} weak spot${weak.length === 1 ? "" : "s"} added to your plan.` : "Test saved.");
      onClose();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't save the test. Try again."),
  });

  const addFiles = (list: FileList | null) => {
    const ok = Array.from(list ?? []).filter((f) => /^image\/(jpeg|png|webp)$|^application\/pdf$/.test(f.type));
    if (ok.length < (list?.length ?? 0)) toast.error("Only photos, screenshots (JPEG, PNG, WebP) and PDFs can be read.");
    setFiles((cur) => [...cur, ...ok].slice(0, maxFiles));
  };
  const addWeak = () => {
    const ch = chapters.get(pick);
    if (!ch) return;
    setWeak((w) => (w.some((x) => x.chapter_id === ch.id && !x.topic_id) ? w
      : [...w, { chapter_id: ch.id, chapter: ch.name, subject: ch.subject, topic_id: null, topic: null, misses: 1, note: null }]));
    setPick("");
  };
  const numbersOk = (score === "" || max === "" || Number(score) <= Number(max)) && (max === "" || Number(max) > 0);
  const canSave = numbersOk && (weak.length > 0 || score !== "");

  return (
    <Dialog open={open} onClose={onClose} wide className="sm:max-w-3xl" title={tr("Add a test result")}
      subtitle={reviewing ? "Check what was read, fix anything that's off, then save."
        : college ? "A class test, a quiz, a mid-semester or an end-semester paper. Focs finds what it showed you're weak in."
          : "A test you took at coaching, at school or from a book. Focs finds what it showed you're weak in."}>
      <div className="space-y-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto_auto]">
          <div>
            <Label htmlFor="test-title">Test name</Label>
            <Input id="test-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={160} placeholder="Allen Minor Test 4, school pre-board…" />
          </div>
          <div>
            <Label htmlFor="test-score">Marks</Label>
            <div className="flex items-center gap-1.5">
              <Input id="test-score" type="number" inputMode="decimal" value={score} onChange={(e) => setScore(e.target.value)} placeholder="63" className="w-20" aria-label="Marks you got" />
              <span className="text-muted">/</span>
              <Input type="number" inputMode="decimal" value={max} onChange={(e) => setMax(e.target.value)} placeholder="80" className="w-20" aria-label="Total marks" />
            </div>
          </div>
          <div>
            <Label htmlFor="test-date">Taken on</Label>
            <Input id="test-date" type="date" value={takenOn} max={today()} onChange={(e) => setTakenOn(e.target.value)} className="w-auto" />
          </div>
        </div>
        {!numbersOk && <p className="-mt-3 text-xs text-warn">The marks you got can't be more than the total.</p>}

        {!reviewing ? (
          <>
            <div>
              <Label>Your result</Label>
              <button type="button" onClick={() => input.current?.click()}
                onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); addFiles(e.dataTransfer.files); }}
                className="flex w-full flex-col items-center gap-2 rounded-xl border border-dashed border-line-strong bg-bg-soft px-4 py-7 text-center transition hover:border-accent/50">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent-soft text-accent"><FileUp className="h-5 w-5" /></span>
                <span className="text-sm font-medium">Attach the result</span>
                <span className="max-w-md text-xs leading-relaxed text-muted">
                  Screenshots or photos of the score report, the question-wise analysis or the marked paper, or the PDF. Up to {maxFiles} files.
                  The more it shows about which questions went wrong, the better the plan.
                </span>
              </button>
              <input ref={input} type="file" multiple hidden accept="image/jpeg,image/png,image/webp,application/pdf" onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
              {files.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {files.map((f, i) => (
                    <span key={`${f.name}-${i}`} className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-line bg-bg-soft py-1 pl-2.5 pr-1 text-xs">
                      <span className="truncate">{f.name}</span>
                      <button type="button" onClick={() => setFiles(files.filter((_, k) => k !== i))} aria-label={`Remove ${f.name}`} className="grid h-5 w-5 place-items-center rounded text-muted hover:bg-elev-2 hover:text-fg"><X className="h-3 w-3" /></button>
                    </span>
                  ))}
                </div>
              )}
              {reader === "none" && <p className="mt-2 text-xs text-warn">Reading a result needs the AI, which isn't set up on this server. You can still mark the weak topics yourself.</p>}
            </div>
            {read.isPending && (
              <WaitBridge kind="test-result" />
            )}
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4">
              <Button variant="ghost" onClick={() => setManual(true)} disabled={read.isPending}>{tr("I'll mark the weak topics myself")}</Button>
              <Button variant="primary" loading={read.isPending} disabled={!files.length || reader === "none"} onClick={() => read.mutate()} icon={<ScanText className="h-4 w-4" />}>{tr("Read my result")}</Button>
            </div>
          </>
        ) : (
          <>
            {draft && (
              <div className="rounded-xl border border-line bg-bg-soft px-3.5 py-2.5 text-[13px] leading-relaxed text-fg-soft">
                {draft.questions_read > 0
                  ? <>Read <b className="text-fg">{draft.questions_read}</b> question{draft.questions_read === 1 ? "" : "s"}, <b className="text-fg">{draft.wrong_read}</b> wrong or left out, in {weak.length} topic{weak.length === 1 ? "" : "s"}.</>
                  : weak.length ? <>The result names {weak.length} weak area{weak.length === 1 ? "" : "s"}.</> : <>The result shows your marks but not which questions went wrong. Add the chapters you struggled with below.</>}
                {" "}A photo can be misread: check the list.
              </div>
            )}
            <div>
              <Label>Weak topics from this test</Label>
              <div className="space-y-2">
                {weak.map((w, i) => (
                  <WeakRow key={`${w.chapter_id}-${i}`} item={w} chapter={chapters.get(w.chapter_id)}
                    onChange={(patch) => setWeak(weak.map((x, k) => (k === i ? { ...x, ...patch } : x)))} onRemove={() => setWeak(weak.filter((_, k) => k !== i))} />
                ))}
                {!weak.length && <p className="rounded-xl border border-dashed border-line-strong px-3 py-4 text-center text-sm text-muted">No weak topics yet. Add the chapters where you lost marks.</p>}
              </div>
              <div className="mt-2 flex gap-2">
                <Select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Chapter to add" className="h-9 min-w-0 flex-1 text-[13px]">
                  <option value="">Add a chapter you lost marks in…</option>
                  {(tree?.subjects ?? []).map((s) => (
                    <optgroup key={s.name} label={s.name}>{s.units.flatMap((u) => u.chapters).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</optgroup>
                  ))}
                </Select>
                <Button size="sm" variant="secondary" className="h-9" disabled={!pick} onClick={addWeak} icon={<Plus className="h-3.5 w-3.5" />}>{tr("Add")}</Button>
              </div>
            </div>
            {!!draft?.unplaced.length && (
              <div className="rounded-xl border border-warn/25 bg-warn/[0.07] px-3.5 py-2.5 text-[13px] text-fg-soft">
                <div className="font-medium text-fg">Couldn't place {draft.unplaced.length} wrong question{draft.unplaced.length === 1 ? "" : "s"} in the syllabus</div>
                <p className="mt-0.5 text-xs text-muted">If you know their chapters, add them above: {draft.unplaced.slice(0, 6).join(" · ")}{draft.unplaced.length > 6 ? " …" : ""}</p>
              </div>
            )}
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4">
              <Button variant="ghost" onClick={() => { setDraft(null); setManual(false); }}>{tr("Back")}</Button>
              <Button variant="primary" loading={save.isPending} disabled={!canSave} onClick={() => save.mutate()}>{tr("Save and build my fix-it plan")}</Button>
            </div>
          </>
        )}
      </div>
    </Dialog>
  );
}

/* ---------------------------------------------------------------- the fix-it plan */
function SpotCard({ w, index, needed, minQuestions }: { w: WeakSpot; index: number; needed: number; minQuestions: number }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [reading, setReading] = useState(false);
  const notes = useQuery({
    queryKey: w.topic ? ["topic-notes", w.topic.id] : ["capsule", w.chapter.id], enabled: reading, staleTime: Infinity, retry: false,
    queryFn: () => (w.topic ? api.topicNotes(w.topic.id) : api.chapterCapsule(w.chapter.id)),
  });
  const examTarget = useAuth((s) => s.user?.exam_target);
  const test = useMutation({
    mutationFn: () => api.createChapterTest(w.chapter.subject, [w.chapter.name], 15),
    onSuccess: (t) => navigate(`/app/mock/${t.id}`),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start the test"),
  });
  const status = useMutation({
    mutationFn: (s: "open" | "cleared") => api.weakSetStatus(w.id, s),
    onSuccess: (o) => { qc.setQueryData(["weak"], o); for (const key of ["prep-plan", "last-day"]) qc.invalidateQueries({ queryKey: [key] }); },
  });
  const last = w.last_check;
  const lastPct = last && last.total ? Math.round((100 * last.correct) / last.total) : null;
  const practise = () => (w.topic ? navigate(`/app/practice?topic=${encodeURIComponent(w.topic.id)}`) : test.mutate());
  const stepBox = "flex min-w-0 flex-1 basis-44 flex-col gap-2 rounded-xl border border-line bg-bg-soft p-3";
  const stepNo = "grid h-5 w-5 shrink-0 place-items-center rounded-full bg-accent-soft text-[11px] font-semibold text-accent";
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 border-line-strong text-xs font-semibold text-muted">{index}</span>
        <div className="min-w-0 flex-1">
          <h3 className="text-[15px] font-semibold tracking-tight">{w.topic?.name ?? w.chapter.name}</h3>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge dot={subjectColor(w.chapter.subject)}>{w.chapter.subject}</Badge>
            {w.topic ? <Badge>{w.chapter.name}</Badge> : <Badge>whole chapter</Badge>}
            <Badge tone="warn">{w.misses} question{w.misses === 1 ? "" : "s"} lost</Badge>
            {w.test && <span className="text-xs text-muted">in {w.test.title}{w.note ? ` (${w.note})` : ""}</span>}
          </div>
        </div>
        <Button size="sm" variant="ghost" className="shrink-0" loading={status.isPending} onClick={() => status.mutate("cleared")} icon={<Check className="h-3.5 w-3.5" />}>
          <span className="hidden sm:inline">I've got this</span>
        </Button>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <div className={stepBox}>
          <div className="flex items-center gap-2 text-xs font-semibold"><span className={stepNo}>1</span>Understand it</div>
          <Button size="sm" variant="secondary" className="w-full" onClick={() => setReading(true)} icon={<BookOpen className="h-3.5 w-3.5" />}>{w.topic ? "Detailed notes" : "Revision capsule"}</Button>
        </div>
        <div className={stepBox}>
          <div className="flex items-center gap-2 text-xs font-semibold"><span className={stepNo}>2</span>Practise it</div>
          <Button size="sm" variant="secondary" className="w-full" loading={test.isPending} onClick={practise} disabled={!w.topic && !canTest(w.chapter.subject, examTarget)}
            icon={w.topic ? <Target className="h-3.5 w-3.5" /> : <ClipboardCheck className="h-3.5 w-3.5" />}>{w.topic ? "Practice set" : "Chapter test"}</Button>
        </div>
        <div className={stepBox}>
          <div className="flex items-center gap-2 text-xs font-semibold"><span className={stepNo}>3</span>Is it clear now?</div>
          <p className={cn("text-xs leading-relaxed", lastPct !== null && lastPct < needed ? "text-warn" : "text-muted")}>
            {lastPct === null ? `Score ${needed}% or better in step 2 and it clears itself.`
              : last!.total < minQuestions ? `Last check ${last!.correct}/${last!.total}: too few questions to tell. Try a set of ${minQuestions} or more.`
              : `Last check ${last!.correct}/${last!.total} (${lastPct}%). Not yet: ${needed}% clears it. Read the notes again, then retry.`}
          </p>
        </div>
      </div>
      <NotesReader open={reading} onClose={() => setReading(false)} query={notes} label={w.topic ? "Detailed notes" : "Revision capsule"} title={w.topic?.name ?? w.chapter.name} />
    </Card>
  );
}

/** Weak spots: add the result of a test taken anywhere, and work off what it showed, one topic at a time. */
export default function WeakSpots() {
  const tr = useT();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const examTarget = useAuth((s) => s.user?.exam_target);
  const [params, setParams] = useSearchParams();
  const [adding, setAdding] = useState(false);
  const { data, error, isLoading } = useQuery({ queryKey: ["weak"], queryFn: api.weak, retry: false });
  const { data: calibration } = useQuery({ queryKey: ["calibration"], queryFn: () => api.calibration({ days: 30 }), staleTime: 60_000 });
  useEffect(() => {  // "Add a test result" from elsewhere in the app lands here with ?add=1
    if (params.get("add") && data) { setAdding(true); setParams((p) => { p.delete("add"); return p; }, { replace: true }); }
  }, [params, data, setParams]);
  const apply = (o: WeakOverview) => { qc.setQueryData(["weak"], o); for (const key of ["prep-plan", "last-day"]) qc.invalidateQueries({ queryKey: [key] }); };
  const reopen = useMutation({ mutationFn: (id: number) => api.weakSetStatus(id, "open"), onSuccess: apply });
  const removeTest = useMutation({ mutationFn: (id: number) => api.weakRemoveTest(id), onSuccess: (o) => { apply(o); toast.success("Test removed"); } });
  const retest = useMutation({
    mutationFn: ({ subject, chapters }: { subject: string; chapters: string[] }) => api.createChapterTest(subject, chapters, chapters.length > 2 ? 20 : 15),
    onSuccess: (t) => navigate(`/app/mock/${t.id}`),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start the test"),
  });

  if (error instanceof ApiError && error.status === 404) {
    return <EmptyState icon={<Crosshair className="h-6 w-6" />} title="Weak spots follow your exam's syllabus" body={error.message}
      action={<Link to="/app/settings"><Button variant="primary">Open settings</Button></Link>} />;
  }
  if (isLoading || !data) return <div className="mx-auto max-w-5xl space-y-4"><Skeleton className="h-24" /><Skeleton className="h-72" /></div>;

  const bySubject = new Map<string, string[]>();
  for (const w of data.open) if (canTest(w.chapter.subject, examTarget)) bySubject.set(w.chapter.subject, [...new Set([...(bySubject.get(w.chapter.subject) ?? []), w.chapter.name])]);
  const lastTest = data.tests[0];
  const lastPct = lastTest ? pct(lastTest.score, lastTest.max_score) : null;
  const empty = !data.tests.length && !data.open.length && !data.cleared.length;
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow={<span className="flex items-center gap-1.5"><Crosshair className="h-3.5 w-3.5" />{tr("Weak spots")}</span>}
        title={tr("Fix what your tests showed")}
        subtitle={tr("Add the result of any test, taken anywhere. Focs finds the topics that cost you marks, and keeps them in your plan until a re-check shows they're clear.")}
        actions={<Button variant="primary" onClick={() => setAdding(true)} icon={<Plus className="h-4 w-4" />}>{tr("Add a test result")}</Button>} />

      {!!calibration?.answers && <div className="mb-5"><CalibrationCard c={calibration} subtitle={`Your last 30 days: ${calibration.answers} answers locked in as sure or guessing. Sure-and-wrong chapters from tests are weak spots below, counted double.`} /></div>}

      {empty ? (
        <Card className="p-6 sm:p-8">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
            {[["Attach the result", "A screenshot or photo of the score report, the question-wise analysis or the marked paper. Or just type your marks and tick the chapters.", FileUp],
              ["Check what Focs read", "Each wrong question is placed in its chapter and topic. You correct anything it got wrong before it is saved.", ScanText],
              ["Work it off", "Each weak topic gets its notes and its questions, leads your daily plan, and stays until you score 70% on it.", CircleCheckBig]].map(([t, b, Icon], i) => (
              <div key={String(t)}>
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent-soft text-accent"><Icon className="h-5 w-5" /></span>
                <div className="mt-3 text-sm font-semibold">{i + 1}. {String(t)}</div>
                <p className="mt-1 text-[13px] leading-relaxed text-muted">{String(b)}</p>
              </div>
            ))}
          </div>
          <Button variant="primary" className="mt-6" onClick={() => setAdding(true)} icon={<Plus className="h-4 w-4" />}>{tr("Add your first test result")}</Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.6fr_1fr]">
          <div className="min-w-0 space-y-3">
            <div className="grid grid-cols-3 gap-3">
              {[["To fix", data.open.length], ["Cleared", data.cleared.length], ["Last test", lastTest?.score !== null && lastTest?.score !== undefined ? `${lastTest.score}${lastTest.max_score ? `/${lastTest.max_score}` : ""}` : "–"]].map(([l, v]) => (
                <Card key={String(l)} className="min-w-0 p-3 sm:p-4">
                  <div className="text-lg font-semibold tabular-nums tracking-tight sm:text-2xl">{v}</div>
                  <div className="text-xs text-muted">{l}{l === "Last test" && lastPct !== null ? ` · ${lastPct}%` : ""}</div>
                </Card>
              ))}
            </div>
            {data.open.length === 0 ? (
              <EmptyState icon={<CircleCheckBig className="h-6 w-6" />} title={tr("Nothing left to fix")}
                body={tr("Every weak spot from your tests is cleared. Add your next test result when you have it.")} />
            ) : (
              <>
                <div className="flex flex-wrap items-end justify-between gap-2 pt-1">
                  <div>
                    <h2 className="text-lg font-semibold">Your fix-it plan</h2>
                    <p className="text-sm text-muted">Costliest first. One leads your daily plan each day until it's cleared.</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {[...bySubject].map(([subject, chapters]) => (
                      <Button key={subject} size="sm" variant="secondary" icon={<ClipboardCheck className="h-3.5 w-3.5" />}
                        loading={retest.isPending && retest.variables?.subject === subject} onClick={() => retest.mutate({ subject, chapters })}>
                        Re-test weak {subject}
                      </Button>
                    ))}
                  </div>
                </div>
                {data.open.map((w, i) => <SpotCard key={w.id} w={w} index={i + 1} needed={data.limits.clear_percent} minQuestions={data.limits.clear_min} />)}
              </>
            )}
          </div>

          <div className="space-y-4 lg:sticky lg:top-4 lg:self-start">
            <Card>
              <CardHeader title={tr("Your tests")} icon={<ClipboardCheck className="h-4 w-4" />} subtitle={tr("Results you've added")} />
              <div className="space-y-2 px-5 pb-5 pt-4">
                {!data.tests.length && <p className="text-sm text-muted">No tests yet.</p>}
                {data.tests.map((t) => {
                  const p = pct(t.score, t.max_score);
                  return (
                    <div key={t.id} className="group flex items-center gap-3 rounded-xl border border-line bg-bg-soft px-3 py-2.5">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium">{t.title}</div>
                        <div className="text-xs text-muted">
                          {[t.taken_on ? formatDate(`${t.taken_on}T00:00:00`) : null, t.weak ? `${t.weak} weak topic${t.weak === 1 ? "" : "s"}` : null, t.source === "upload" ? "read from the result" : null].filter(Boolean).join(" · ")}
                        </div>
                      </div>
                      {t.score !== null && <div className="shrink-0 text-right"><div className="text-sm font-semibold tabular-nums">{t.score}{t.max_score ? `/${t.max_score}` : ""}</div>{p !== null && <div className="text-[11px] text-muted">{p}%</div>}</div>}
                      <button type="button" aria-label={`Remove ${t.title}`} title="Remove this test"
                        onClick={() => confirm(`Remove "${t.title}" and the open weak spots that came from it?`) && removeTest.mutate(t.id)}
                        className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-muted/70 hover:bg-elev-2 hover:text-bad"><Trash2 className="h-3.5 w-3.5" /></button>
                    </div>
                  );
                })}
              </div>
            </Card>
            {data.cleared.length > 0 && (
              <Card>
                <CardHeader title={tr("Cleared")} icon={<CircleCheckBig className="h-4 w-4" />} subtitle={tr("In the last 30 days")} />
                <div className="space-y-1.5 px-5 pb-5 pt-4">
                  {data.cleared.map((w) => (
                    <div key={w.id} className="flex items-center gap-2 text-[13px]">
                      <Check className="h-3.5 w-3.5 shrink-0 text-ok" />
                      <span className="min-w-0 flex-1 truncate">{w.topic?.name ?? w.chapter.name}</span>
                      {w.last_check && w.last_check.total > 0 && <span className="shrink-0 text-xs tabular-nums text-muted">{w.last_check.correct}/{w.last_check.total}</span>}
                      <button type="button" onClick={() => reopen.mutate(w.id)} disabled={reopen.isPending} title="Not clear after all: put it back"
                        className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-muted hover:bg-elev-2 hover:text-fg"><Undo2 className="h-3 w-3" /></button>
                    </div>
                  ))}
                </div>
              </Card>
            )}
            <Card className="p-4 text-[13px] leading-relaxed text-muted">
              <div className="mb-1.5 flex items-center gap-2 font-semibold text-fg"><RotateCcw className="h-3.5 w-3.5 text-accent" />How a weak spot clears</div>
              A practice set on the topic with {data.limits.clear_percent}% or better ({data.limits.clear_min}+ questions), a chapter test on Focs with {data.limits.clear_percent}% in that chapter, or your own call. Miss it again in the next test and it comes back with more weight.
            </Card>
          </div>
        </div>
      )}
      <AddTestDialog open={adding} onClose={() => setAdding(false)} reader={data.reader} maxFiles={data.limits.files} />
    </div>
  );
}
