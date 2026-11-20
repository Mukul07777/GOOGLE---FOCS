import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Bot, CheckCheck, Flag, HandHeart, Lightbulb, MailCheck, MessageCircleQuestion, MessagesSquare, PenLine, School, Send, ThumbsUp, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, EmptyState, Input, Segmented, Select, Skeleton, Textarea } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { AskBoard, AskPost, AskVerification } from "@/lib/types";
import { cn, subjectColor, timeAgo } from "@/lib/utils";
import { useT } from "@/lib/i18n";

const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work. Try again.");

function Byline({ p }: { p: AskPost }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
      <span className="font-medium text-fg-soft">{p.ai && <Bot className="mr-1 inline h-3 w-3" />}{p.by}</span>
      {p.senior ? <Badge tone="ok"><BadgeCheck className="h-3 w-3" />Senior · {p.senior}</Badge> : null}
      {p.ai && (p.checked ? <Badge tone="ok"><CheckCheck className="h-3 w-3" />{p.checked}</Badge> : <Badge tone="warn">Not checked by a senior yet</Badge>)}
      {p.accepted && <Badge tone="accent"><CheckCheck className="h-3 w-3" />Settled the question</Badge>}
      {p.helped > 0 && <span className="inline-flex items-center gap-1"><HandHeart className="h-3 w-3" />Helped {p.helped} {p.helped === 1 ? "junior" : "juniors"}</span>}
      {p.created_at && <span>{timeAgo(p.created_at)}</span>}
    </div>
  );
}

function Actions({ p }: { p: AskPost }) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["campus-ask"] });
  const vote = useMutation({ mutationFn: () => api.askVote(p.id), onSuccess: refresh, onError: failed });
  const report = useMutation({ mutationFn: () => api.askReport(p.id), onSuccess: () => { refresh(); toast.success("Reported. Thanks."); }, onError: failed });
  const remove = useMutation({ mutationFn: () => api.askRemove(p.id), onSuccess: () => { refresh(); toast.success("Removed"); }, onError: failed });
  return (
    <div className="flex items-center gap-1">
      <Button size="sm" variant={p.voted ? "success" : "ghost"} onClick={() => vote.mutate()} icon={<ThumbsUp className="h-3.5 w-3.5" />} title="This helped">{p.votes || ""}</Button>
      {p.mine ? <Button size="icon-sm" variant="ghost" aria-label="Remove" title="Remove" onClick={() => remove.mutate()}><Trash2 className="h-3.5 w-3.5" /></Button>
        : <Button size="icon-sm" variant="ghost" aria-label="Report" title="Rude, wrong or off-topic" onClick={() => report.mutate()}><Flag className="h-3.5 w-3.5" /></Button>}
    </div>
  );
}

/** The asker: "this settled it". It counts for the answer's author on the leaderboard. */
function Accept({ a }: { a: AskPost }) {
  const qc = useQueryClient();
  const t = useT();
  const accept = useMutation({ mutationFn: () => api.askAccept(a.id), onSuccess: () => qc.invalidateQueries({ queryKey: ["campus-ask"] }), onError: failed });
  return (
    <Button size="sm" variant={a.accepted ? "success" : "ghost"} loading={accept.isPending} onClick={() => accept.mutate()} aria-pressed={a.accepted}
      icon={<CheckCheck className="h-3.5 w-3.5" />} title="Mark the answer that settled your question">{t(a.accepted ? "Settled it" : "This settled it")}</Button>
  );
}

/** A senior on Focs's AI draft: right as it is, or a correction (which becomes their own answer). */
function CheckDraft({ draft }: { draft: AskPost }) {
  const qc = useQueryClient();
  const [fixing, setFixing] = useState(false);
  const t = useT();
  const [text, setText] = useState("");
  const check = useMutation({
    mutationFn: (verdict: "right" | "fix") => api.askCheck(draft.id, verdict, verdict === "fix" ? text.trim() : undefined),
    onSuccess: (_, verdict) => { qc.invalidateQueries({ queryKey: ["campus-ask"] }); toast.success(verdict === "right" ? "Marked as checked by a senior" : "Correction posted"); },
    onError: failed,
  });
  return (
    <div className="mt-3 rounded-lg border border-line bg-bg/60 p-3">
      <div className="text-xs font-medium text-fg-soft">{t("You've done this course: is Focs's answer right?")}</div>
      {fixing ? (
        <div className="mt-2 space-y-2">
          <Textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} maxLength={1500} aria-label="Your correction"
            placeholder="What's wrong in it, and what's right. This posts as your answer." />
          <div className="flex gap-2">
            <Button size="sm" variant="primary" disabled={text.trim().length < 10} loading={check.isPending} onClick={() => check.mutate("fix")} icon={<Send className="h-3.5 w-3.5" />}>{t("Post correction")}</Button>
            <Button size="sm" variant="ghost" onClick={() => setFixing(false)}>{t("Cancel")}</Button>
          </div>
        </div>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          <Button size="sm" variant="primary" loading={check.isPending && check.variables === "right"} onClick={() => check.mutate("right")} icon={<CheckCheck className="h-3.5 w-3.5" />}>{t("It's right")}</Button>
          <Button size="sm" onClick={() => setFixing(true)} icon={<PenLine className="h-3.5 w-3.5" />}>{t("Fix it")}</Button>
        </div>
      )}
    </div>
  );
}

function Question({ q, open: startOpen = false, canCheck = false }: { q: AskPost; open?: boolean; canCheck?: boolean }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(startOpen);
  const t = useT();
  const [text, setText] = useState("");
  const answer = useMutation({
    mutationFn: () => api.askAnswer(q.id, text.trim()),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["campus-ask"] }); setText(""); setOpen(false); toast.success("Answered. You just saved a junior an evening."); },
    onError: failed,
  });
  const answers = q.answers ?? [];
  const humanAnswers = answers.filter((a) => !a.ai).length;
  return (
    <Card className="p-5">
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent"><MessageCircleQuestion className="h-4 w-4" /></span>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-1.5">
            <Badge dot={subjectColor(q.subject)}>{q.subject}</Badge>
            {q.chapter && <Badge>{q.chapter}</Badge>}
          </div>
          <p className="whitespace-pre-wrap text-[14.5px] font-medium leading-relaxed">{q.body}</p>
          <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2"><Byline p={q} /><Actions p={q} /></div>
        </div>
      </div>
      {answers.length > 0 && (
        <div className="mt-3 space-y-2.5 border-l-2 border-line pl-4 sm:ml-12">
          {answers.map((a) => (
            <div key={a.id} className={cn("rounded-xl border p-3.5", a.accepted ? "border-accent/40 bg-accent-soft/40" : a.senior || a.checked ? "border-ok/25 bg-ok/5"
              : a.ai ? "border-warn/30 bg-warn/5" : "border-line bg-bg-soft")}>
              {a.ai ? <Markdown className="text-[13.5px]">{a.body}</Markdown> : <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed">{a.body}</p>}
              <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2">
                <Byline p={a} />
                <div className="flex items-center gap-1">
                  {q.mine && <Accept a={a} />}
                  <Actions p={a} />
                </div>
              </div>
              {a.ai && !a.checked && canCheck && <CheckDraft draft={a} />}
            </div>
          ))}
        </div>
      )}
      <div className="mt-3 sm:ml-12">
        {open ? (
          <div className="space-y-2">
            <Textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} maxLength={1500} placeholder="What you'd have wanted to know: which units, what the paper asks, how to revise it." />
            <div className="flex gap-2">
              <Button size="sm" variant="primary" disabled={text.trim().length < 2} loading={answer.isPending} onClick={() => answer.mutate()} icon={<Send className="h-3.5 w-3.5" />}>{t("Post answer")}</Button>
              <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>{t("Cancel")}</Button>
            </div>
          </div>
        ) : !q.mine && <button onClick={() => setOpen(true)} className="text-[13px] font-medium text-accent hover:underline">{t(humanAnswers ? "Add an answer" : "Answer this")}</button>}
      </div>
    </Card>
  );
}

function Composer({ board, chapter: startChapter }: { board: AskBoard; chapter: string }) {
  const qc = useQueryClient();
  const [kind, setKind] = useState<"question" | "tip">("question");
  const [chapter, setChapter] = useState(board.chapters.includes(startChapter) ? startChapter : "");
  const [body, setBody] = useState("");
  const tip = kind === "tip" && !!board.senior;
  const t = useT();
  const post = useMutation({
    mutationFn: () => api.askPost({ subject: board.subject, kind: tip ? "tip" : "question", body: body.trim(), chapter: chapter || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campus-ask"] }); setBody("");
      toast.success(tip ? "Tip shared. The next batch thanks you." : "Asked. Seniors who did this course will see it.");
    },
    onError: failed,
  });
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-center gap-2">
        {board.senior ? (
          <>
            <Segmented size="sm" value={kind} onChange={setKind} options={[{ value: "question", label: t("Ask a question") }, { value: "tip", label: t("Leave a tip") }]} />
            <Badge tone="ok"><BadgeCheck className="h-3 w-3" />You're a senior here · {board.senior}</Badge>
          </>
        ) : <div className="text-sm font-semibold">Ask students who've done {board.subject}</div>}
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,14rem)_1fr]">
        <Select value={chapter} onChange={(e) => setChapter(e.target.value)} aria-label="Chapter">
          <option value="">{t("The whole course")}</option>
          {board.chapters.map((c) => <option key={c}>{c}</option>)}
        </Select>
        <Textarea rows={3} value={body} onChange={(e) => setBody(e.target.value)} maxLength={1500}
          placeholder={tip ? `What should a junior know about ${chapter || board.subject}? Which units matter, what the paper asks, what you would do differently.`
            : `e.g. What should I focus on in ${chapter || board.subject} for the exam? Which questions keep coming?`} />
      </div>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="text-[11.5px] text-muted">{t("Your first name and initial are shown, never your email.")}</span>
        <Button variant="primary" size="sm" disabled={body.trim().length < 10} loading={post.isPending} onClick={() => post.mutate()} icon={<Send className="h-3.5 w-3.5" />}>
          {t(tip ? "Share tip" : "Ask")}
        </Button>
      </div>
    </Card>
  );
}

/** A B.Tech student proves they're at their college (a one-time code to the college email): their answers then carry a
    senior badge, they can check Focs's drafts, and they hear about new questions on courses they've done. */
function Verify({ v }: { v: AskVerification }) {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(v.pending);
  const start = useMutation({
    mutationFn: () => api.askVerifyStart(email.trim()),
    onSuccess: (r) => {
      setSent(true);
      if (r.dev_code) { setCode(r.dev_code); toast(`Email isn't set up on this server, so here's the code: ${r.dev_code}`); }
      else toast.success("Code sent. Check your college inbox.");
    },
    onError: failed,
  });
  const confirm = useMutation({
    mutationFn: () => api.askVerifyConfirm(code.trim()),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["campus-ask"] }); toast.success("Verified. Your answers now show you've done the course."); },
    onError: failed,
  });
  return (
    <Card className="mb-6 p-5">
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent"><MailCheck className="h-4 w-4" /></span>
        <div className="min-w-0 flex-1">
          <div className="font-semibold">Verify your college email to answer as a senior</div>
          <p className="mt-0.5 text-sm text-muted">Juniors trust an answer more when they know you've done the course. Use {v.domains.join(" or ")}; we only check it's yours, and never show it.</p>
          {!sent ? (
            <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); start.mutate(); }}>
              <Input type="email" className="h-9 max-w-xs" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@college.ac.in" aria-label="College email" autoComplete="email" />
              <Button size="sm" variant="primary" type="submit" disabled={!email.includes("@")} loading={start.isPending}>Send code</Button>
            </form>
          ) : (
            <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); confirm.mutate(); }}>
              <Input className="h-9 w-36 font-mono tracking-[0.3em]" value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))} inputMode="numeric"
                placeholder="6-digit code" aria-label="Code from the email" autoComplete="one-time-code" />
              <Button size="sm" variant="primary" type="submit" disabled={code.length !== 6} loading={confirm.isPending}>Verify</Button>
              <Button size="sm" variant="ghost" type="button" onClick={() => { setSent(false); setCode(""); }}>Use another email</Button>
            </form>
          )}
        </div>
      </div>
    </Card>
  );
}

/** Ask a senior: a course's tips from students who've done it, its questions and answers, and what juniors wait on from you. */
export function AskSeniors({ subject: startSubject, chapter, tabs }: { subject: string; chapter: string; tabs: React.ReactNode }) {
  const [subject, setSubject] = useState(startSubject);
  const [scope, setScope] = useState<"mine" | "all">("mine");
  const { data, isLoading, error } = useQuery({
    queryKey: ["campus-ask", subject, scope], queryFn: () => api.askBoard({ subject: subject || undefined, scope }),
    placeholderData: (prev) => prev, retry: false,
  });
  if (error instanceof ApiError && error.status === 404) {
    return <EmptyState icon={<School className="h-6 w-6" />} title="Ask a senior is for B.Tech, GATE, placement, JEE and NEET students" body={error.message}
      action={<Link to="/app/settings"><Button variant="primary">Open settings</Button></Link>} />;
  }
  if (isLoading || !data) return <div className="mx-auto max-w-5xl space-y-4"><Skeleton className="h-24" /><Skeleton className="h-72" /></div>;
  const school = data.shelf === "school";
  const named = !school && data.college !== "other";

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow={<span className="flex items-center gap-1.5"><School className="h-3.5 w-3.5" />Campus{named ? ` · ${data.college_name}` : ""}</span>}
        title="Ask a senior" subtitle={school
          ? `Seniors who cleared ${data.college_name} answer your questions. Focs drafts an answer at once; a senior checks it.`
          : "Students who've already done your courses answer your questions and leave tips for the exam. When you're the senior, answer the ones waiting for you."}
        actions={tabs} />

      {data.verification.needed && <Verify v={data.verification} />}

      {data.waiting.length > 0 && (
        <div className="mb-6 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold"><MessagesSquare className="h-4 w-4 text-accent" />
            Juniors are waiting on you · {data.waiting.length} question{data.waiting.length === 1 ? "" : "s"} on courses you've done</div>
          {data.waiting.slice(0, 5).map((q) => <Question key={q.id} q={q} canCheck />)}
        </div>
      )}

      <Card className="mb-4 flex flex-col gap-3 p-4 lg:flex-row lg:items-center">
        <Select value={data.subject} onChange={(e) => setSubject(e.target.value)} className="lg:max-w-xs" aria-label="Course">
          <optgroup label="Your subjects">{data.subjects.map((s) => <option key={s}>{s}</option>)}</optgroup>
          {data.done.length > 0 && <optgroup label="Courses you've done: answer and leave tips">{data.done.filter((c) => !data.subjects.includes(c)).map((s) => <option key={s}>{s}</option>)}</optgroup>}
          <optgroup label="Other courses">{data.catalogue.filter((c) => !data.subjects.includes(c) && !data.done.includes(c)).map((s) => <option key={s}>{s}</option>)}</optgroup>
        </Select>
        <span className="hidden flex-1 lg:block" />
        {named && <Segmented size="sm" value={scope} onChange={setScope} options={[{ value: "mine", label: data.college_name }, { value: "all", label: "All colleges" }]} />}
      </Card>

      <div className="space-y-4">
        <Composer key={data.subject} board={data} chapter={chapter} />

        {data.tips.length > 0 && (
          <Card>
            <CardHeader title="Tips from seniors" icon={<Lightbulb className="h-4 w-4" />} subtitle={`What students who did ${data.subject} want you to know`} />
            <div className="divide-y divide-line">
              {data.tips.map((t) => (
                <div key={t.id} className="px-5 py-4">
                  {t.chapter && <Badge className="mb-1.5">{t.chapter}</Badge>}
                  <p className="whitespace-pre-wrap text-[14px] leading-relaxed">{t.body}</p>
                  <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2"><Byline p={t} /><Actions p={t} /></div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {data.questions.length ? data.questions.map((q) => <Question key={q.id} q={q} canCheck={!!data.senior} />) : (
          <EmptyState icon={<MessageCircleQuestion className="h-6 w-6" />} title="No questions on this course yet"
            body={named && scope === "mine" ? `Be the first from ${data.college_name} to ask, or look at all colleges.` : "Be the first to ask. Seniors who did this course see new questions on their Campus page."}
            action={named && scope === "mine" ? <Button onClick={() => setScope("all")}>All colleges</Button> : undefined} />
        )}
      </div>
      <p className="mt-4 px-1 text-xs leading-relaxed text-muted">Answers come from students; one marked "Focs (AI draft)" is Focs's own until a senior checks it. Check them against your notes. Two reports take a post down.</p>
    </div>
  );
}
