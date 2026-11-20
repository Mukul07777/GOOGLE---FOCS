import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen, Check, ChevronDown, ChevronLeft, ChevronRight, ClipboardCheck, Clock, FileText, Layers, ListChecks, Mic, NotebookPen,
  PlayCircle, Radio, RotateCcw, Search, Settings2, Sparkles, Target, X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { CollegeSetupDialog } from "@/components/CollegeSetup";
import { SchoolSubjectsDialog } from "@/components/SchoolSubjects";
import { NotesReader } from "@/components/DetailedNotes";
import { TeachBack } from "@/components/TeachBack";
import { TodayPlan, usePlan } from "@/components/TodayPlan";
import { Button } from "@/components/ui/button";
import { Badge, Card, EmptyState, Input, ProgressBar, ProgressRing, Segmented, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { SyllabusChapter, SyllabusTree } from "@/lib/types";
import { canTest, cn, COLLEGES, slug, subjectColor, timeAgo, shownName } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { useT } from "@/lib/i18n";

type Filter = "all" | "11" | "12" | "high" | "todo" | "done";
const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" }, { value: "11", label: "Class 11" }, { value: "12", label: "Class 12" },
  { value: "high", label: "High weightage" }, { value: "todo", label: "To do" }, { value: "done", label: "Done" },
];
const WEIGHT_TONE = { high: "bad", medium: "warn", low: "neutral" } as const;

const subjectOf = (id: string, tree: SyllabusTree) => tree.subjects.find((s) => id.startsWith(`${slug(s.name)}.`))?.name;

function youtubeEmbed(url: string): string | null {
  const m = url.match(/(?:youtu\.be\/|v=|embed\/|shorts\/)([\w-]{11})/);
  return m ? `https://www.youtube-nocookie.com/embed/${m[1]}` : null;
}

function matches(c: SyllabusChapter, filter: Filter, q: string) {
  if (filter === "11" && c.class !== 11) return false;
  if (filter === "12" && c.class !== 12) return false;
  if (filter === "high" && c.weightage !== "high") return false;
  if (filter === "todo" && c.done >= c.total) return false;
  if (filter === "done" && c.done < c.total) return false;
  if (!q) return true;
  const s = q.toLowerCase();
  return c.name.toLowerCase().includes(s) || c.topics.some((t) => t.name.toLowerCase().includes(s));
}

/** Optimistically flip a topic in the cached syllabus, so ticking feels instant. */
function patchTopic(tree: SyllabusTree, topicId: string, done: boolean): SyllabusTree {
  return {
    ...tree,
    stats: { ...tree.stats, done_topics: tree.stats.done_topics + (done ? 1 : -1) },
    subjects: tree.subjects.map((s) => ({
      ...s,
      units: s.units.map((u) => ({
        ...u,
        chapters: u.chapters.map((c) => {
          if (!c.topics.some((t) => t.id === topicId)) return c;
          const topics = c.topics.map((t) => (t.id === topicId ? { ...t, done } : t));
          return { ...c, topics, done: topics.filter((t) => t.done).length };
        }),
      })),
    })),
  };
}

function ChapterRow({ c, open, onToggle, onTopic, onTick, highlight, college }: {
  c: SyllabusChapter; open: boolean; onToggle: () => void; onTopic: (id: string) => void;
  onTick: (topicId: string, done: boolean) => void; highlight: boolean; college: boolean;
}) {
  const tr = useT();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const examTarget = useAuth((s) => s.user?.exam_target);
  const finished = c.done >= c.total;
  const revise = useMutation({
    mutationFn: () => api.setRevised(c.id, true),
    onSuccess: () => { toast.success(`Revision of ${c.name} logged`); qc.invalidateQueries({ queryKey: ["prep-syllabus"] }); qc.invalidateQueries({ queryKey: ["prep-plan"] }); },
  });
  const test = useMutation({
    mutationFn: () => api.createChapterTest(c.subject, [c.name], 15),
    onSuccess: (t) => navigate(`/app/mock/${t.id}`),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start the test"),
  });
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (highlight) ref.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [highlight]);
  return (
    <div ref={ref} className={cn("border-t border-line first:border-t-0", highlight && "bg-accent-soft/40")}>
      <button type="button" onClick={onToggle} className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-elev-2/50">
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted transition", !open && "-rotate-90")} />
        {finished ? (
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-ok text-white"><Check className="h-3.5 w-3.5" strokeWidth={3} /></span>
        ) : (
          <span className="shrink-0" title={`${Math.round((100 * c.done) / c.total)}% done`}>
            <ProgressRing value={(100 * c.done) / c.total} size={24} stroke={3} />
          </span>
        )}
        <span className="min-w-0 flex-1">
          <span className="block text-[14.5px] font-medium">{shownName(c.name)}</span>
          <span className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11.5px] text-muted">
            {!college && <span>Class {c.class}</span>}
            <span>{c.done}/{c.total} topics</span>
            <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{Math.round(c.hours)} h</span>
            {c.revisions > 0 && <span className="flex items-center gap-1 text-ok"><RotateCcw className="h-3 w-3" />revised {c.revisions}×</span>}
          </span>
        </span>
        <Badge tone={WEIGHT_TONE[c.weightage]} className="hidden sm:inline-flex">{c.weightage}</Badge>
      </button>
      {open && (
        <div className="pb-3 pl-[52px] pr-4">
          <ProgressBar value={(100 * c.done) / c.total} tone={finished ? "ok" : "accent"} className="mb-2" />
          <div className="divide-y divide-line/60">
            {c.topics.map((t) => (
              <div key={t.id} className="group flex items-center gap-3 py-2">
                <button type="button" onClick={() => onTick(t.id, !t.done)} aria-label={t.done ? `Mark ${t.name} as not studied` : `Mark ${t.name} as studied`}
                  className={cn("grid h-5 w-5 shrink-0 place-items-center rounded-md border transition",
                    t.done ? "border-ok bg-ok text-white" : "border-line-strong hover:border-accent")}>
                  {t.done && <Check className="h-3 w-3" strokeWidth={3} />}
                </button>
                <button type="button" onClick={() => onTopic(t.id)} className={cn("flex min-w-0 flex-1 items-center gap-2 text-left text-[13.5px] hover:text-accent", t.done && "text-muted")}>
                  <FileText className="h-3.5 w-3.5 shrink-0 text-muted" />
                  <span className="min-w-0 break-words">{t.name}</span>
                  {t.video && <PlayCircle className="h-3.5 w-3.5 shrink-0 text-accent" />}
                </button>
              </div>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {canTest(c.subject, examTarget) ? (
              <Button size="sm" variant="secondary" loading={test.isPending} onClick={() => test.mutate()} icon={<ClipboardCheck className="h-3.5 w-3.5" />}>
                Chapter test{c.questions ? ` · ${c.questions} Q ready` : ""}
              </Button>
            ) : (
              <Link to="/app/practice"><Button size="sm" variant="secondary" icon={<ClipboardCheck className="h-3.5 w-3.5" />}>{tr("Practise")}</Button></Link>
            )}
            {finished && (
              <Button size="sm" variant="ghost" loading={revise.isPending} onClick={() => revise.mutate()} icon={<RotateCcw className="h-3.5 w-3.5" />}>
                Revised today
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function TopicSheet({ topicId, onClose, onOpen, onTick }: {
  topicId: string; onClose: () => void; onOpen: (id: string) => void; onTick: (id: string, done: boolean) => void;
}) {
  const navigate = useNavigate();
  const examTarget = useAuth((s) => s.user?.exam_target);
  const { data: t, isLoading } = useQuery({ queryKey: ["prep-topic", topicId], queryFn: () => api.topicDetail(topicId) });
  // detailed notes are given when asked for, and open in the reader
  const [reading, setReading] = useState(false);
  const [explaining, setExplaining] = useState<string | null>(null);
  useEffect(() => setReading(false), [topicId]);
  const notes = useQuery({
    queryKey: ["topic-notes", topicId], queryFn: () => api.topicNotes(topicId), enabled: reading,
    staleTime: Infinity, gcTime: Infinity, retry: false,
  });
  const qc = useQueryClient();
  const writtenNow = notes.data?.written_now;
  useEffect(() => {  // a note written just now used some AI allowance, and the topic now shows as having notes
    if (writtenNow) { qc.invalidateQueries({ queryKey: ["usage"] }); qc.invalidateQueries({ queryKey: ["prep-syllabus"] }); }
  }, [writtenNow, qc]);
  const idx = t ? t.chapter.topics.findIndex((x) => x.id === t.id) : -1;
  const prev = t && idx > 0 ? t.chapter.topics[idx - 1] : null;
  const next = t && idx >= 0 && idx < t.chapter.topics.length - 1 ? t.chapter.topics[idx + 1] : null;
  const embed = t?.video ? youtubeEmbed(t.video) : null;
  const test = useMutation({
    mutationFn: () => api.createChapterTest(t!.chapter.subject, [t!.chapter.name], 15),
    onSuccess: (m) => navigate(`/app/mock/${m.id}`),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start the test"),
  });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !reading && onClose();  // Esc closes the reader first
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, reading]);
  return (
    <>
      <NotesReader open={reading} onClose={() => setReading(false)} query={notes} title={t?.name} />
      <motion.div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
      <motion.aside role="dialog" aria-label={t?.name ?? "Topic"} className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-line bg-bg shadow-2xl"
        initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 30, stiffness: 300 }}>
        <div className="flex items-center gap-2 border-b border-line px-5 py-3">
          <div className="min-w-0 flex-1 truncate text-xs text-muted">
            {t ? <><span style={{ color: subjectColor(t.chapter.subject) }}>{t.chapter.subject}</span> › {t.chapter.name}</> : "…"}
          </div>
          <Button size="icon-sm" variant="ghost" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></Button>
        </div>
        {isLoading || !t ? <div className="space-y-3 p-5"><Skeleton className="h-8" /><Skeleton className="h-48" /></div> : (
          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
            <div>
              <h2 className="text-xl font-semibold tracking-tight">{t.name}</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant={t.done ? "success" : "primary"} onClick={() => onTick(t.id, !t.done)} icon={<Check className="h-3.5 w-3.5" />}>
                  {t.done ? "Studied" : "Mark as studied"}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => navigate(`/app/practice?topic=${encodeURIComponent(t.id)}`)} icon={<Target className="h-3.5 w-3.5" />}>
                  Practise this topic
                </Button>
                {canTest(t.chapter.subject, examTarget) && (
                  <Button size="sm" variant="secondary" loading={test.isPending} onClick={() => test.mutate()} icon={<ClipboardCheck className="h-3.5 w-3.5" />}>
                    Chapter test{t.questions ? ` · ${t.questions} Q` : ""}
                  </Button>
                )}
              </div>
            </div>

            <section>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><PlayCircle className="h-4 w-4 text-accent" />Lecture</h3>
              {embed ? (
                <div className="aspect-video overflow-hidden rounded-xl border border-line bg-black">
                  <iframe src={embed} title={t.name} className="h-full w-full" allow="accelerometer; encrypted-media; picture-in-picture" allowFullScreen />
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-line-strong p-4 text-sm text-muted">
                  The Focs lecture for this topic is coming soon. Watching one elsewhere?{" "}
                  <Link to="/app/studio" className="font-medium text-accent hover:underline">Start a live lecture</Link> and Focs writes the notes as you watch.
                </div>
              )}
            </section>

            <section>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><BookOpen className="h-4 w-4 text-accent" />Detailed notes</h3>
              <button type="button" onClick={() => setReading(true)}
                className="group flex w-full items-center gap-4 rounded-xl border border-accent/30 bg-accent-soft/50 p-4 text-left transition hover:border-accent/60 hover:bg-accent-soft">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-gradient-brand text-brand-fg"><BookOpen className="h-5 w-5" /></span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold">{t.notes_ready || notes.data ? "Open the detailed notes" : "Get the detailed notes"}</span>
                  <span className="mt-0.5 block text-[13px] leading-relaxed text-muted">
                    Core ideas, formulas, a solved exam question, common mistakes and how {t.kind === "college" || t.kind === "gate" ? "exams ask" : "the exam asks"} it{t.notes_ready || notes.data ? "." : ". Written for you in about 20 seconds."}
                  </span>
                </span>
                <ChevronRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-fg" />
              </button>
            </section>

            <section>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><Mic className="h-4 w-4 text-accent" />Explain it back</h3>
              {explaining === topicId ? (
                <Card className="p-4"><TeachBack key={t.id} topic={t.name} topicId={t.id} subject={t.chapter.subject} /></Card>
              ) : (
                <div className="flex flex-col items-start gap-3 rounded-xl border border-line bg-bg-soft p-4 sm:flex-row sm:items-center">
                  <p className="flex-1 text-sm text-muted">The quickest test of whether a topic has stuck: say it in your own words, out loud or typed, and Focs checks it.</p>
                  <Button size="sm" variant="secondary" onClick={() => setExplaining(topicId)} icon={<Mic className="h-3.5 w-3.5" />}>Explain this topic</Button>
                </div>
              )}
            </section>

            <section>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><NotebookPen className="h-4 w-4 text-accent" />From your lectures</h3>
              {t.your_notes.length ? (
                <div className="space-y-1.5">
                  {t.your_notes.map((n) => (
                    <Link key={n.id} to={`/app/library/${n.session_id}`} className="flex items-center gap-2 rounded-lg border border-line bg-bg-soft px-3 py-2 text-sm hover:border-line-strong">
                      <FileText className="h-3.5 w-3.5 shrink-0 text-muted" /><span className="min-w-0 flex-1 truncate">{n.topic || "Board notes"}</span>
                      {n.captured_at && <span className="text-xs text-muted">{timeAgo(n.captured_at)}</span>}
                    </Link>
                  ))}
                </div>
              ) : <p className="text-sm text-muted">Nothing captured on this yet. Board notes from your live lectures on it will show up here.</p>}
            </section>
          </div>
        )}
        {t && (
          <div className="flex items-center justify-between border-t border-line px-5 py-3">
            <Button size="sm" variant="ghost" disabled={!prev} onClick={() => prev && onOpen(prev.id)} icon={<ChevronLeft className="h-4 w-4" />}>Previous</Button>
            <span className="text-xs text-muted">{idx + 1} / {t.chapter.topics.length}</span>
            <Button size="sm" variant="ghost" disabled={!next} onClick={() => next && onOpen(next.id)}>Next <ChevronRight className="h-4 w-4" /></Button>
          </div>
        )}
      </motion.aside>
    </>
  );
}

export default function PrepHub() {
  const tr = useT();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const topicId = params.get("topic");
  const chapterParam = params.get("chapter");
  // college: null is the student's own subjects; a number looks at that semester of the plan
  const [semester, setSemester] = useState<number | null>(null);
  const [settingUp, setSettingUp] = useState(false);
  const treeKey = useMemo(() => (semester === null ? ["prep-syllabus"] : ["prep-syllabus", semester]), [semester]);
  const { data: tree, isLoading, error } = useQuery({ queryKey: treeKey, queryFn: () => api.prepSyllabus(undefined, semester), placeholderData: (prev) => prev });
  const { data: plan } = usePlan();
  const [subject, setSubject] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());

  // deep links (?chapter= / ?topic=) open the right subject and chapter
  useEffect(() => {
    if (!tree) return;
    const id = chapterParam ?? topicId?.split(".").slice(0, 2).join(".");
    const s = id ? subjectOf(id, tree) : null;
    if (s) setSubject(s);
    if (id) setOpen((o) => new Set(o).add(id));
  }, [tree, chapterParam, topicId]);
  // (another semester has other subjects: the one picked before may not be there)
  useEffect(() => { if (tree && subject && !tree.subjects.some((s) => s.name === subject)) setSubject(null); }, [tree, subject]);

  const tick = useMutation({
    mutationFn: ({ id, done }: { id: string; done: boolean }) => api.setTopicDone(id, done),
    onMutate: ({ id, done }) => {
      qc.setQueryData<SyllabusTree>(treeKey, (t) => (t ? patchTopic(t, id, done) : t));
      qc.setQueryData(["prep-topic", id], (d: object | undefined) => (d ? { ...d, done } : d));
    },
    onSettled: () => { qc.invalidateQueries({ queryKey: ["prep-plan"] }); qc.invalidateQueries({ queryKey: ["prep-syllabus"] }); },
    onSuccess: (_, { id, done }) => {
      // a topic just studied: the moment to practise it (one toast, replaced as more topics are ticked)
      if (done) toast.success("Marked as studied", { id: "practise-topic", action: { label: "Practise it", onClick: () => navigate(`/app/practice?topic=${encodeURIComponent(id)}`) } });
    },
    onError: () => toast.error("Couldn't save that. Check your connection."),
  });

  const current = tree?.subjects.find((s) => s.name === (subject ?? tree.subjects[0]?.name)) ?? tree?.subjects[0];
  const subjectStats = useMemo(() => Object.fromEntries((tree?.subjects ?? []).map((s) => {
    const ch = s.units.flatMap((u) => u.chapters);
    const total = ch.reduce((n, c) => n + c.total, 0);
    return [s.name, total ? (100 * ch.reduce((n, c) => n + c.done, 0)) / total : 0];
  })), [tree]);

  if (error instanceof ApiError && error.status === 404) {
    return <EmptyState icon={<Layers className="h-6 w-6" />} title="The Prep Hub covers JEE, NEET, GATE, B.Tech, placements and school" body={error.message}
      action={<Link to="/app/settings"><Button variant="primary">Open settings</Button></Link>} />;
  }
  if (isLoading || !tree || !current) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-96" /></div>;

  const overall = (100 * tree.stats.done_topics) / Math.max(1, tree.stats.topics);
  const college = tree.college;
  const plain = tree.kind !== "entrance";  // one class, or no classes at all: nothing to filter or label by class
  const courses = tree.kind === "college" || tree.kind === "gate";  // a subject is a course, described by its "about" line
  const filters = plain ? FILTERS.filter((x) => x.value !== "11" && x.value !== "12") : FILTERS;
  const collegeName = college ? COLLEGES.find((c) => c.id === college.college)?.name : null;
  const toggle = (id: string) => setOpen((o) => { const n = new Set(o); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const openTopic = (id: string) => setParams((p) => { p.set("topic", id); return p; });
  const closeTopic = () => setParams((p) => { p.delete("topic"); return p; }, { replace: true });

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title={tree.name}
        eyebrow={college ? `Prep Hub · ${college.semester ? `Semester ${college.semester}` : "B.Tech"}${collegeName && college.college !== "other" ? ` · ${collegeName}'s plan` : ""}` : tr("Prep Hub")}
        subtitle={<span className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="flex items-center gap-1.5"><Layers className="h-3.5 w-3.5" />{tree.stats.chapters} {tr("chapters")}</span>
          <span className="flex items-center gap-1.5"><ListChecks className="h-3.5 w-3.5" />{tree.stats.topics} {tr("topics")}</span>
          <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" />~{tree.stats.hours} {tr("h of study")}</span>
          {tree.stats.questions > 0 && <span className="flex items-center gap-1.5"><ClipboardCheck className="h-3.5 w-3.5" />{tree.stats.questions} {tr("practice questions")}</span>}
        </span>}
        actions={<div className="flex flex-wrap gap-2">
          {(college || tree.choices) && <Button variant="secondary" onClick={() => setSettingUp(true)} icon={<Settings2 className="h-4 w-4" />}>{tr("My subjects")}</Button>}
          {plan ? <Link to="/app/plan"><Button variant="secondary" icon={<Sparkles className="h-4 w-4" />}>{tr("My plan")}</Button></Link>
            : <Link to="/onboarding"><Button variant="primary" icon={<Sparkles className="h-4 w-4" />}>{tr("Get my plan")}</Button></Link>}
        </div>} />

      {college && (
        <div className="mb-4 space-y-3">
          {!college.set_up && (
            <button type="button" onClick={() => setSettingUp(true)}
              className="flex w-full items-center gap-3 rounded-2xl border border-accent/30 bg-accent-soft/50 p-4 text-left transition hover:border-accent/60">
              <Settings2 className="h-5 w-5 shrink-0 text-accent" />
              <span className="min-w-0 flex-1 text-sm"><b>These are a typical first semester's subjects.</b> Tell Focs your college and semester to see your own.</span>
              <ChevronRight className="h-4 w-4 shrink-0 text-muted" />
            </button>
          )}
          <div className="-mx-1 overflow-x-auto px-1">
            <Segmented size="sm" value={semester === null ? "mine" : String(semester)} onChange={(v) => setSemester(v === "mine" ? null : Number(v))}
              options={[{ value: "mine", label: tr("My subjects") }, ...[1, 2, 3, 4, 5, 6, 7, 8].map((n) => ({ value: String(n), label: `Sem ${n}` }))]} />
          </div>
          {semester !== null && (
            <p className="px-1 text-xs text-muted">
              Semester {semester} in {collegeName && college.college !== "other" ? `${collegeName}'s` : "the typical"} plan. Read ahead or revise here; to study these, add them under My subjects.
            </p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_360px]">
        <div className="min-w-0 space-y-4">
          <Card className="p-4">
            <div className="flex items-center gap-4">
              <div className="min-w-0 flex-1">
                <div className="mb-1.5 flex justify-between text-[13px]"><span className="font-medium">Syllabus covered</span><span className="tabular-nums text-muted">{tree.stats.done_topics} / {tree.stats.topics} topics · {Math.round(overall)}%</span></div>
                <ProgressBar value={overall} />
              </div>
            </div>
            <div className={cn("mt-4 grid gap-2", tree.subjects.length > 3 ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-3", tree.subjects.length > 9 && "lg:grid-cols-4")}>
              {tree.subjects.map((s) => (
                <button key={s.name} type="button" onClick={() => setSubject(s.name)}
                  className={cn("min-w-0 rounded-xl border p-2.5 text-left transition sm:p-3", s.name === current.name ? "border-accent/50 bg-accent-soft" : "border-line bg-bg-soft hover:border-line-strong")}>
                  <div className="flex min-w-0 items-center gap-2 text-[13px] font-semibold sm:text-sm"><span className="hidden h-2 w-2 shrink-0 rounded-full sm:block" style={{ background: subjectColor(s.name) }} /><span className="line-clamp-2 leading-tight">{s.name === "Mathematics" ? <><span className="sm:hidden">Maths</span><span className="hidden sm:inline">{s.name}</span></> : s.name}</span></div>
                  <div className="mt-1 text-xs text-muted">{Math.round(subjectStats[s.name] ?? 0)}% done</div>
                </button>
              ))}
            </div>
          </Card>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search ${current.name} chapters and topics`} className="pl-9" />
            </div>
            <div className="-mx-1 overflow-x-auto px-1"><Segmented size="sm" value={filter} onChange={setFilter} options={filters.map((f) => ({ ...f, label: tr(f.label) }))} /></div>
          </div>

          {current.units.map((u) => {
            const chapters = u.chapters.filter((c) => matches(c, filter, q));
            if (!chapters.length) return null;
            const done = u.chapters.reduce((n, c) => n + c.done, 0), total = u.chapters.reduce((n, c) => n + c.total, 0);
            return (
              <Card key={u.name} className="overflow-hidden">
                <div className="flex items-center justify-between border-b border-line bg-bg-soft/60 px-4 py-2.5">
                  <span className="min-w-0 text-sm font-semibold">{courses ? current.about || current.name : u.name}</span>
                  <span className="shrink-0 pl-3 text-xs text-muted">{Math.round((100 * done) / total)}% · {u.chapters.length} {u.chapters.length === 1 ? "chapter" : "chapters"}</span>
                </div>
                {chapters.map((c) => (
                  <ChapterRow key={c.id} c={c} open={open.has(c.id) || !!q} onToggle={() => toggle(c.id)} onTopic={openTopic} college={plain}
                    highlight={chapterParam === c.id} onTick={(id, d) => tick.mutate({ id, done: d })} />
                ))}
              </Card>
            );
          })}
          {current.units.every((u) => !u.chapters.some((c) => matches(c, filter, q))) && (
            <EmptyState icon={<Search className="h-6 w-6" />} title={tr("Nothing matches")} body={tr("Try another filter or search term.")} />
          )}
          <p className="px-1 text-xs leading-relaxed text-muted">{tree.about}</p>
        </div>

        <div className="space-y-4 xl:sticky xl:top-4 xl:self-start">
          <TodayPlan />
          <Card className="p-4 text-[13px]">
            <div className="mb-2 font-semibold">How to use the Prep Hub</div>
            <ul className="space-y-1.5 text-muted">
              <li className="flex gap-2"><Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok" />Tick a topic once you've studied it and solved its questions. Your plan adjusts.</li>
              <li className="flex gap-2"><RotateCcw className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />Finished chapters come back for revision after a week, a month and three months.</li>
              <li className="flex gap-2"><Radio className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent-2" />Watching a lecture? Run it through Live lecture and the notes land on its topic.</li>
            </ul>
            <div className="mt-3 flex items-center gap-2 border-t border-line pt-3 text-xs text-muted">
              Weightage: <Badge tone="bad">high</Badge><Badge tone="warn">medium</Badge><Badge>low</Badge>
            </div>
          </Card>
        </div>
      </div>

      <AnimatePresence>
        {topicId && <TopicSheet key="sheet" topicId={topicId} onClose={closeTopic} onOpen={openTopic} onTick={(id, d) => tick.mutate({ id, done: d })} />}
      </AnimatePresence>
      {college && <CollegeSetupDialog open={settingUp} onClose={() => { setSettingUp(false); setSemester(null); }} />}
      {tree.choices && <SchoolSubjectsDialog open={settingUp} onClose={() => setSettingUp(false)} all={tree.choices} mine={tree.subjects.map((s) => s.name)} />}
    </div>
  );
}
