import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FileText, Flag, ListChecks, Loader2, NotebookPen, Plus, School, Sparkles, ThumbsUp, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { AskSeniors } from "@/components/CampusAsk";
import { useAuth } from "@/stores/auth";
import { PageHeader } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, EmptyState, Input, Label, Segmented, Select, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { IN_APP } from "@/lib/server";
import type { CampusItem } from "@/lib/types";
import { cn, isBoards, subjectColor, timeAgo, usesCourses } from "@/lib/utils";

const EXAM_KIND = { mid: "Mid-sem", end: "End-sem", quiz: "Quiz", other: "Paper" } as const;
const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work. Try again.");

function ShareDialog({ open, onClose, onShared, subjects, catalogue }: {
  open: boolean; onClose: () => void; onShared: (subject: string) => void; subjects: string[]; catalogue: string[];
}) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState<"paper" | "notes">("paper");
  const [subject, setSubject] = useState(subjects[0] ?? "");
  const [title, setTitle] = useState("");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [examKind, setExamKind] = useState<keyof typeof EXAM_KIND>("end");
  const share = useMutation({
    mutationFn: () => api.campusShare({ file: file!, kind, subject, title, year: kind === "paper" ? Number(year) : undefined, exam_kind: kind === "paper" ? examKind : undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["campus"] }); toast.success("Shared. Thank you: the next student starts ahead."); setFile(null); setTitle(""); onShared(subject); onClose(); },
    onError: failed,
  });
  const others = catalogue.filter((c) => !subjects.includes(c));
  return (
    <Dialog open={open} onClose={onClose} title="Share with your campus" subtitle="A past paper or your own notes for a course. Share only what is yours to share.">
      <div className="space-y-4">
        <Segmented value={kind} onChange={setKind} options={[{ value: "paper", label: "A past paper" }, { value: "notes", label: "My notes" }]} />
        <button type="button" onClick={() => input.current?.click()}
          className="flex w-full items-center gap-3 rounded-xl border border-dashed border-line-strong bg-bg-soft p-4 text-left transition hover:border-accent/60">
          <Upload className="h-5 w-5 shrink-0 text-accent" />
          <span className="min-w-0 flex-1 text-sm">{file ? <span className="block truncate font-medium">{file.name}</span> : <>Choose a PDF or a photo <span className="text-muted">· up to 15 MB</span></>}</span>
        </button>
        <input ref={input} type="file" accept="application/pdf,image/*" hidden onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <div>
          <Label>Course</Label>
          <Select value={subject} onChange={(e) => setSubject(e.target.value)}>
            <optgroup label="Your subjects">{subjects.map((s) => <option key={s}>{s}</option>)}</optgroup>
            <optgroup label="Other courses">{others.map((s) => <option key={s}>{s}</option>)}</optgroup>
          </Select>
        </div>
        <div>
          <Label>Title</Label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={160} placeholder={kind === "paper" ? "e.g. End-sem paper, December 2025" : "e.g. Unit 3: deadlocks, handwritten"} />
        </div>
        {kind === "paper" && (
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Year</Label><Input type="number" min={2000} max={2100} value={year} onChange={(e) => setYear(e.target.value)} /></div>
            <div><Label>Exam</Label>
              <Select value={examKind} onChange={(e) => setExamKind(e.target.value as keyof typeof EXAM_KIND)}>
                {Object.entries(EXAM_KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            </div>
          </div>
        )}
        <Button variant="primary" className="w-full" disabled={!file || title.trim().length < 3 || !subject} loading={share.isPending} onClick={() => share.mutate()}>Share it</Button>
      </div>
    </Dialog>
  );
}

function QuestionsDialog({ item, onClose }: { item: CampusItem | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["campus-questions", item?.id], enabled: !!item, retry: false, staleTime: Infinity,
    queryFn: async () => { const r = await api.campusQuestions(item!.id); qc.invalidateQueries({ queryKey: ["usage"] }); return r; },
  });
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const explain = useMutation({
    mutationFn: (q: { no: string; text: string }) => api.ask({ question: `From a ${item!.subject} university paper: ${q.text}\nWrite the answer that gets full marks.`, mode: "explain", history: [] }),
    onSuccess: (r, q) => setAnswers((a) => ({ ...a, [q.no + q.text]: r.answer })),
    onError: failed,
  });
  return (
    <Dialog open={!!item} onClose={onClose} wide title={item?.title} subtitle={item ? `${item.subject} · questions read from the paper by AI: check them against the file` : undefined}>
      {isLoading && <div className="flex items-center gap-3 py-10 text-sm text-muted"><Loader2 className="h-5 w-5 animate-spin text-accent" />Reading the paper. The first time takes about half a minute.</div>}
      {error && <p className="py-6 text-sm text-fg-soft">{error instanceof ApiError ? error.message : "Couldn't read that paper."}</p>}
      {data && !data.questions.length && <p className="py-6 text-sm text-muted">No questions could be read from this file. Open the file itself instead.</p>}
      <div className="space-y-3">
        {data?.questions.map((q) => {
          const key = q.no + q.text;
          return (
            <div key={key} className="rounded-xl border border-line bg-bg-soft p-4">
              <div className="mb-1.5 flex items-center gap-2 text-xs font-semibold text-accent">Q{q.no}{q.marks !== null && <Badge>{q.marks} marks</Badge>}</div>
              <Markdown className="text-fg [&_p]:my-0">{q.text}</Markdown>
              {answers[key] ? <div className="mt-3 border-t border-line pt-3"><Markdown>{answers[key]}</Markdown></div> : (
                <Button size="sm" variant="secondary" className="mt-3" loading={explain.isPending && explain.variables?.text === q.text}
                  onClick={() => explain.mutate(q)} icon={<Sparkles className="h-3.5 w-3.5" />}>Show how to answer it</Button>
              )}
            </div>
          );
        })}
      </div>
    </Dialog>
  );
}

function Page({ id, n }: { id: number; n: number }) {
  const { data, error } = useQuery({ queryKey: ["campus-page", id, n], queryFn: () => api.campusPage(id, n), staleTime: Infinity, gcTime: Infinity, retry: 1 });
  if (error) return <p className="py-6 text-center text-sm text-muted">Page {n} couldn't be opened.</p>;
  return data ? <img src={data} alt={`Page ${n}`} className="w-full rounded-xl border border-line bg-white" /> : <Skeleton className="aspect-[3/4] w-full" />;
}

/** A shared file read inside Focs, page by page (the app cannot hand a PDF to another tab). */
function ReaderDialog({ item, onClose }: { item: CampusItem | null; onClose: () => void }) {
  const [shown, setShown] = useState(3);
  const pages = item?.pages ?? 1;
  return (
    <Dialog open={!!item} onClose={() => { setShown(3); onClose(); }} wide title={item?.title} subtitle={item ? `${item.subject} · ${pages} page${pages === 1 ? "" : "s"}` : undefined}>
      {item && (
        <div className="space-y-3">
          {Array.from({ length: Math.min(shown, pages) }, (_, i) => <Page key={i} id={item.id} n={i + 1} />)}
          {shown < pages && <Button variant="secondary" className="w-full" onClick={() => setShown(shown + 4)}>Show more pages ({pages - shown} left)</Button>}
        </div>
      )}
    </Dialog>
  );
}

/** Past papers and notes shared by students of the same course: your college's shelf first, every college's on request. */
function Shelf({ tabs }: { tabs: React.ReactNode }) {
  const qc = useQueryClient();
  const [subject, setSubject] = useState("");
  const [kind, setKind] = useState<"all" | "paper" | "notes">("all");
  const [scope, setScope] = useState<"mine" | "all">("mine");
  const [sharing, setSharing] = useState(false);
  const [reading, setReading] = useState<CampusItem | null>(null);
  const [viewing, setViewing] = useState<CampusItem | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ["campus", subject, kind, scope], queryFn: () => api.campus({ subject: subject || undefined, kind: kind === "all" ? undefined : kind, scope }),
    placeholderData: (prev) => prev, retry: false,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["campus"] });
  // (the tab is opened on the click itself, before the file arrives: a browser blocks one opened later)
  const open = useMutation({
    mutationFn: async (id: number) => {
      const tab = window.open("", "_blank");
      try {
        const url = await api.campusFile(id);
        if (tab) tab.location.href = url; else window.location.href = url;
      } catch (e) { tab?.close(); throw e; }
    },
    onError: failed,
  });
  const vote = useMutation({ mutationFn: (id: number) => api.campusVote(id), onSuccess: refresh, onError: failed });
  const report = useMutation({ mutationFn: (id: number) => api.campusReport(id), onSuccess: () => { refresh(); toast.success("Reported. Thanks for keeping the shelf clean."); }, onError: failed });
  const remove = useMutation({ mutationFn: (id: number) => api.campusRemove(id), onSuccess: () => { refresh(); toast.success("Removed"); }, onError: failed });

  if (error instanceof ApiError && error.status === 404) {
    return <EmptyState icon={<School className="h-6 w-6" />} title="Campus is for B.Tech and GATE students" body={error.message}
      action={<Link to="/app/settings"><Button variant="primary">Open settings</Button></Link>} />;
  }
  if (isLoading || !data) return <div className="mx-auto max-w-5xl space-y-4"><Skeleton className="h-24" /><Skeleton className="h-72" /></div>;
  const named = data.college !== "other";

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow={<span className="flex items-center gap-1.5"><School className="h-3.5 w-3.5" />Campus{named ? ` · ${data.college_name}` : ""}</span>}
        title="Past papers and notes, from students like you"
        subtitle="Shared by students taking the same courses. Open a paper, see its questions one by one, and add yours for the next batch."
        actions={<>{tabs}<Button variant="primary" onClick={() => setSharing(true)} icon={<Plus className="h-4 w-4" />}>Share a paper or notes</Button></>} />

      <Card className="mb-4 flex flex-col gap-3 p-4 lg:flex-row lg:items-center">
        <Select value={subject} onChange={(e) => setSubject(e.target.value)} className="lg:max-w-xs" aria-label="Course">
          <option value="">All my subjects</option>
          <optgroup label="Your subjects">{data.subjects.map((s) => <option key={s}>{s}</option>)}</optgroup>
          <optgroup label="Other courses">{data.catalogue.filter((c) => !data.subjects.includes(c)).map((s) => <option key={s}>{s}</option>)}</optgroup>
        </Select>
        <Segmented size="sm" value={kind} onChange={setKind} options={[{ value: "all", label: "Everything" }, { value: "paper", label: "Past papers" }, { value: "notes", label: "Notes" }]} />
        <span className="hidden flex-1 lg:block" />
        {named && <Segmented size="sm" value={scope} onChange={setScope} options={[{ value: "mine", label: data.college_name }, { value: "all", label: "All colleges" }]} />}
      </Card>

      {!data.items.length ? (
        <EmptyState icon={<FileText className="h-6 w-6" />} title="Nothing here yet"
          body={named && scope === "mine" ? `No one from ${data.college_name} has shared anything for this yet. Be the first, or look at all colleges.` : "Be the first to share a past paper or your notes for this."}
          action={<div className="flex gap-2"><Button variant="primary" onClick={() => setSharing(true)}>Share something</Button>
            {named && scope === "mine" && <Button onClick={() => setScope("all")}>All colleges</Button>}</div>} />
      ) : (
        <div className="space-y-2.5">
          {data.items.map((i) => (
            <Card key={i.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
              <span className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-xl", i.kind === "paper" ? "bg-accent-soft text-accent" : "bg-accent-2/10 text-accent-2")}>
                {i.kind === "paper" ? <FileText className="h-5 w-5" /> : <NotebookPen className="h-5 w-5" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold">{i.title}</div>
                <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-muted">
                  <Badge dot={subjectColor(i.subject)}>{i.subject}</Badge>
                  {i.kind === "paper" && <span>{EXAM_KIND[i.exam_kind ?? "other"]}{i.year ? ` ${i.year}` : ""}</span>}
                  <span>{i.pages} page{i.pages === 1 ? "" : "s"}</span>
                  <span>by {i.mine ? "you" : i.by}{scope === "all" && i.college !== "other" ? ` · ${i.college.toUpperCase()}` : ""}</span>
                  {i.created_at && <span>{timeAgo(i.created_at)}</span>}
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                <Button size="sm" variant="primary" loading={open.isPending && open.variables === i.id} onClick={() => (IN_APP ? setViewing(i) : open.mutate(i.id))} icon={<ExternalLink className="h-3.5 w-3.5" />}>Open</Button>
                {i.kind === "paper" && <Button size="sm" variant="secondary" onClick={() => setReading(i)} icon={<ListChecks className="h-3.5 w-3.5" />}>Questions</Button>}
                <Button size="sm" variant={i.voted ? "success" : "ghost"} onClick={() => vote.mutate(i.id)} icon={<ThumbsUp className="h-3.5 w-3.5" />} title="This helped">{i.votes || ""}</Button>
                {i.mine ? <Button size="icon-sm" variant="ghost" aria-label="Remove" title="Remove" onClick={() => remove.mutate(i.id)}><Trash2 className="h-3.5 w-3.5" /></Button>
                  : <Button size="icon-sm" variant="ghost" aria-label="Report" title="Wrong course, unreadable, or not theirs to share" onClick={() => report.mutate(i.id)}><Flag className="h-3.5 w-3.5" /></Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
      <p className="mt-4 px-1 text-xs leading-relaxed text-muted">Files are shared by students and are not checked by Focs. If one is wrong or shouldn't be here, report it: two reports take it down.</p>
      <ShareDialog open={sharing} onClose={() => setSharing(false)} onShared={(s) => { if (!data.subjects.includes(s)) setSubject(s); }} subjects={data.subjects} catalogue={data.catalogue} />
      <QuestionsDialog item={reading} onClose={() => setReading(null)} />
      <ReaderDialog item={viewing} onClose={() => setViewing(null)} />
    </div>
  );
}

/** Campus: the shelf of shared papers and notes, and "Ask a senior" (?tab=ask, with a course and chapter to start on). */
export default function Campus() {
  const [params, setParams] = useSearchParams();
  const courses = useAuth((s) => usesCourses(s.user?.exam_target));  // JEE/NEET aspirants have no shelf of papers: just Ask a senior
  const school = useAuth((s) => isBoards(s.user?.exam_target));
  if (school) {  // (not in a school student's menu: someone who followed a link)
    return <EmptyState className="mt-16" icon={<School className="h-6 w-6" />} title="Campus is for college students and JEE/NEET aspirants"
      body="Your Prep Hub, chapter tests and mentors cover your class. Ask Focs anything from a chapter with Ask with a photo."
      action={<Link to="/app/prep"><Button variant="primary">Open your Prep Hub</Button></Link>} />;
  }
  const tab = params.get("tab") === "ask" || !courses ? "ask" : "files";
  const tabs = <Segmented value={tab} onChange={(t) => setParams(t === "ask" ? { tab: "ask" } : {}, { replace: true })}
    options={[{ value: "files", label: "Papers & notes" }, { value: "ask", label: "Ask a senior" }]} />;
  return tab === "ask" ? <AskSeniors subject={params.get("subject") ?? ""} chapter={params.get("chapter") ?? ""} tabs={courses ? tabs : null} /> : <Shelf tabs={tabs} />;
}
