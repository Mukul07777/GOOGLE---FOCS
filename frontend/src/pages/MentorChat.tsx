import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BadgeCheck, CalendarCheck, Clock, Crosshair, Flag, Flame, Lock, Send, Timer } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { toast } from "sonner";
import { CallsPanel } from "@/components/MentorCalls";
import { StatTile, WeekBars } from "@/components/ProgressBits";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, CardHeader, Skeleton, Switch, Textarea } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { MentorMessage, MentorshipDetail, ProgressSummary } from "@/lib/types";
import { cn, formatMinutes, subjectColor, timeAgo } from "@/lib/utils";
import { Initials } from "@/pages/Mentors";

const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work. Try again.");

/** A week of Focs progress: what a check-in carries, and what a mentor sees of their student now. */
function Week({ p, compact }: { p: ProgressSummary; compact?: boolean }) {
  return (
    <div className="space-y-3">
      <div className={cn("grid gap-2", compact ? "grid-cols-2" : "grid-cols-2")}>
        <StatTile label="This week" value={formatMinutes(p.week_minutes)} hint={`goal ${formatMinutes(p.goal_minutes)} a day`} icon={<Clock className="h-3.5 w-3.5" />} />
        <StatTile label="Streak" value={`${p.streak} day${p.streak === 1 ? "" : "s"}`} hint="in a row" icon={<Flame className="h-3.5 w-3.5" />} />
      </div>
      <WeekBars days={p.days} goal={p.goal_minutes} />
      <div className="space-y-1 text-[13px]">
        <p className="flex gap-2"><Timer className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" />
          {p.last_test ? <span>Last test: <b>{p.last_test.score}/{p.last_test.max}</b> ({p.last_test.percent}%) · {p.last_test.title}</span> : <span className="text-muted">No test yet</span>}</p>
        {p.accuracy_week !== null && <p className="pl-5.5 text-fg-soft">{p.questions_week} practice questions, {p.accuracy_week}% right · {p.tests_week} test{p.tests_week === 1 ? "" : "s"} this week</p>}
        {p.syllabus.total > 0 && <p className="pl-5.5 text-fg-soft">Syllabus {p.syllabus.percent}% done ({p.syllabus.done} of {p.syllabus.total} topics)</p>}
      </div>
      {p.weak.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-[0.12em] text-muted"><Crosshair className="h-3 w-3" />Weak chapters</div>
          <div className="flex flex-wrap gap-1.5">{p.weak.map((w) => <Badge key={w.id} dot={subjectColor(w.subject)}>{w.chapter}</Badge>)}
            {p.weak_count > p.weak.length && <span className="text-xs text-muted">+{p.weak_count - p.weak.length} more</span>}</div>
        </div>
      )}
    </div>
  );
}

function Bubble({ m, other }: { m: MentorMessage; other: string }) {
  if (m.kind === "checkin") {
    const snap = m.snapshot && "week_minutes" in m.snapshot ? m.snapshot : null;
    return (
      <div className={cn("max-w-[34rem] rounded-2xl border border-accent/30 bg-accent-soft/40 p-4", m.mine && "ml-auto")}>
        <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold"><CalendarCheck className="h-4 w-4 text-accent" />Weekly check-in
          <span className="text-xs font-normal text-muted">· {m.mine ? "you" : other} · {timeAgo(m.created_at)}</span></div>
        {m.body && <p className="mb-3 whitespace-pre-wrap text-[14px] leading-relaxed">{m.body}</p>}
        {snap ? <Week p={snap} compact /> : <p className="flex items-center gap-1.5 text-xs text-muted"><Lock className="h-3 w-3" />Progress kept private</p>}
      </div>
    );
  }
  return (
    <div className={cn("flex", m.mine ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[34rem] rounded-2xl px-4 py-2.5", m.mine ? "rounded-br-md bg-accent text-accent-fg" : "rounded-bl-md border border-line bg-elev")}>
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed">{m.body}</p>
        <div className={cn("mt-0.5 text-[10.5px]", m.mine ? "text-accent-fg/70" : "text-muted")}>{timeAgo(m.created_at)}</div>
      </div>
    </div>
  );
}

function ReportDialog({ open, onClose, id }: { open: boolean; onClose: () => void; id: number }) {
  const [reason, setReason] = useState("");
  const report = useMutation({ mutationFn: () => api.mentorReport(id, reason.trim()), onSuccess: () => { toast.success("Reported. Focs will read this conversation."); onClose(); }, onError: failed });
  return (
    <Dialog open={open} onClose={onClose} title="Report this conversation" subtitle="Focs staff will read it. A mentor you report takes no new students until it's looked at.">
      <div className="space-y-3">
        <Textarea rows={4} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} placeholder="What happened? e.g. asked for my number, rude, asked for money." />
        <Button variant="danger" className="w-full" disabled={reason.trim().length < 3} loading={report.isPending} onClick={() => report.mutate()}>Send report</Button>
      </div>
    </Dialog>
  );
}

function Composer({ c }: { c: MentorshipDetail }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const send = useMutation({
    mutationFn: (checkin: boolean) => api.mentorSend(c.id, { body: text.trim(), checkin }),
    onSuccess: (_, checkin) => { setText(""); qc.invalidateQueries({ queryKey: ["mentorship", c.id] }); qc.invalidateQueries({ queryKey: ["mentorships"] }); if (checkin) toast.success("Check-in sent."); },
    onError: failed,
  });
  const student = c.role === "student";
  return (
    <Card className="p-4">
      {student && c.checkin_due && (
        <p className="mb-2 flex items-center gap-1.5 text-[13px] text-accent"><CalendarCheck className="h-4 w-4" />Your weekly check-in is due: write two lines on your week and send it as a check-in.</p>
      )}
      <Textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} maxLength={2000}
        placeholder={student ? "How did the week go? What's stuck? What do you want to ask?" : "Your advice for this week: what to change, what to keep, one thing to try."} />
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 basis-48 text-[11.5px] text-muted">Phone numbers and emails are hidden. Keep it on Focs.</span>
        {student && <Button size="sm" variant={c.checkin_due ? "primary" : "secondary"} loading={send.isPending && send.variables} onClick={() => send.mutate(true)}
          icon={<CalendarCheck className="h-3.5 w-3.5" />} title="Adds your week from Focs: study time, tests and weak chapters">Send as weekly check-in</Button>}
        <Button size="sm" variant={student && c.checkin_due ? "secondary" : "primary"} disabled={!text.trim()} loading={send.isPending && !send.variables}
          onClick={() => send.mutate(false)} icon={<Send className="h-3.5 w-3.5" />}>Send</Button>
      </div>
    </Card>
  );
}

/** One mentorship: the request, then a conversation that carries on, with a check-in from the student every week. */
export default function MentorChat() {
  const id = Number(useParams().id);
  const back = useLocation().pathname.startsWith("/mentor") ? { to: "/mentor/seekers", label: "Seekers" } : { to: "/app/mentors?tab=mine", label: "Mentors" };
  const qc = useQueryClient();
  const [reporting, setReporting] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const { data: c, isLoading, error } = useQuery({ queryKey: ["mentorship", id], queryFn: () => api.mentorship(id), refetchInterval: 15_000, retry: false });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["mentorship", id] }); qc.invalidateQueries({ queryKey: ["mentorships"] }); };
  const decide = useMutation({ mutationFn: (to: "accept" | "decline" | "end") => api.mentorDecide(id, to), onSuccess: refresh, onError: failed });
  const share = useMutation({ mutationFn: (v: boolean) => api.mentorShare(id, v), onSuccess: refresh, onError: failed });
  const count = c?.messages.length ?? 0;
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [count]);

  if (error) return <Card className="mx-auto max-w-xl p-8 text-center text-sm text-muted">This conversation isn't yours or doesn't exist. <Link to={back.to} className="text-accent">Back to {back.label.toLowerCase()}</Link></Card>;
  if (isLoading || !c) return <div className="mx-auto max-w-5xl space-y-4"><Skeleton className="h-24" /><Skeleton className="h-96" /></div>;
  const student = c.role === "student";
  const first = c.with.split(" ")[0];

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <Link to={back.to} className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft className="h-4 w-4" />{back.label}</Link>
      <Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        <Initials name={c.with} photo={student ? c.mentor.photo : null} className="h-12 w-12" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-lg font-semibold">{c.with}
            {student ? <Badge tone="ok"><BadgeCheck className="h-3 w-3" />Verified mentor</Badge> : <Badge>Your student · {c.exam_label}</Badge>}</div>
          <div className="text-[13px] text-muted">{student ? `${c.credential} · ${c.institution}` : c.goal}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {student && c.status === "active" && (
            <label className="flex items-center gap-2 text-xs text-muted">Share my progress<Switch checked={c.share_progress} onChange={(v) => share.mutate(v)} label="Share my progress" /></label>
          )}
          {(c.status === "active" || (student && c.status === "requested")) && (
            <Button size="sm" variant="ghost" onClick={() => { if (confirm(c.status === "requested" ? "Withdraw your request?" : `End your mentorship with ${first}?`)) decide.mutate("end"); }}>
              {c.status === "requested" ? "Withdraw" : "End"}
            </Button>
          )}
          <Button size="icon-sm" variant="ghost" aria-label="Report" title="Report this conversation" onClick={() => setReporting(true)}><Flag className="h-3.5 w-3.5" /></Button>
        </div>
      </Card>

      <div className={cn("grid grid-cols-1 gap-4", !student && "lg:grid-cols-[1.35fr_1fr]")}>
        <div className="flex flex-col gap-3">
          {/* phones: the conversation first, calls below it */}
          {(c.status === "active" || c.status === "ended") && <div className="order-last lg:order-first"><CallsPanel mentorshipId={c.id} role={c.role} other={c.with} active={c.status === "active"} /></div>}
          <Card className="space-y-3 p-5">
            <div className="rounded-xl border border-line bg-bg-soft p-4">
              <div className="mb-1 text-[11.5px] font-semibold uppercase tracking-[0.12em] text-muted">{student ? "What you asked for" : `What ${first} asked for`}</div>
              <p className="whitespace-pre-wrap text-[14px] leading-relaxed">{c.goal}</p>
            </div>
            {c.status === "requested" && (student
              ? <p className="text-sm text-muted">Waiting for {first} to accept. You'll see the reply here.</p>
              : <div className="flex flex-wrap items-center gap-2"><span className="text-sm text-muted">Accept only if you can reply every week.</span>
                  <Button size="sm" variant="primary" loading={decide.isPending && decide.variables === "accept"} onClick={() => decide.mutate("accept")}>Accept</Button>
                  <Button size="sm" variant="ghost" onClick={() => decide.mutate("decline")}>Decline</Button></div>)}
            {c.status === "declined" && <p className="text-sm text-muted">{student ? `${first} can't take this on right now. Try another mentor.` : "You declined this request."}</p>}
            {c.status === "active" && !c.messages.length && (
              <p className="text-sm text-muted">{student ? `${first} accepted. Start with your first check-in: it shows where you're starting from.` : `Say hello, and ask ${first} for a first check-in.`}</p>
            )}
            {c.messages.map((m) => <Bubble key={m.id} m={m} other={first} />)}
            {c.status === "ended" && <p className="text-center text-xs text-muted">This mentorship has ended.</p>}
            <div ref={end} />
          </Card>
          {c.status === "active" && <Composer c={c} />}
        </div>

        {!student && (
          <Card className="h-fit lg:sticky lg:top-6">
            <CardHeader title={`${first}'s week on Focs`} icon={<Clock className="h-4 w-4" />} subtitle="Live, as shared by your student" />
            <div className="p-5">{c.progress ? <Week p={c.progress} />
              : <p className="flex items-center gap-1.5 text-sm text-muted"><Lock className="h-4 w-4" />{c.status === "active" ? `${first} keeps their progress private.` : "Shown while the mentorship is active."}</p>}</div>
          </Card>
        )}
      </div>
      <ReportDialog open={reporting} onClose={() => setReporting(false)} id={c.id} />
    </div>
  );
}
