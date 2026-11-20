import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BadgeCheck, CalendarCheck, Compass, HeartHandshake, Languages, Plus, ShieldCheck, Star, Video } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { StudentSessions } from "@/components/GroupSessions";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, EmptyState, Label, Segmented, Select, Skeleton, Switch, Textarea } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { MentorCard, MentorDirectory, MentorshipList, MentorshipRow } from "@/lib/types";
import { useAuth } from "@/stores/auth";
import { asksSeniors, cn, hasTests, isBoards, isCollege, isGate, isPlacement, timeAgo } from "@/lib/utils";

const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work. Try again.");

/** A mentor's photo (once Focs has checked it), else their initials. The name is always written beside it, so the
 * picture itself needs no alt text. */
export function Initials({ name, photo, className }: { name: string; photo?: string | null; className?: string }) {
  const text = name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  if (photo) return <img src={photo} alt="" loading="lazy" className={cn("h-11 w-11 shrink-0 rounded-full border border-line object-cover", className)} />;
  return <div className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gradient-brand text-sm font-semibold text-brand-fg", className)}>{text || "?"}</div>;
}

const STATUS: Record<MentorshipRow["status"], { label: string; tone: "accent" | "ok" | "neutral" | "warn" }> = {
  requested: { label: "Waiting for a reply", tone: "warn" }, active: { label: "Active", tone: "ok" },
  declined: { label: "Declined", tone: "neutral" }, ended: { label: "Ended", tone: "neutral" },
};

/* ---------------------------------------------------------------- finding a mentor */
/** An example of what to tell a mentor, for the kind of student asking. */
function requestExample(exam: string | null | undefined): string {
  if (isBoards(exam)) return "e.g. Class 10, boards in February. Science is fine but I lose marks in Maths word problems. I want a weekly plan and someone to check on me.";
  if (isCollege(exam)) return "e.g. Semester 5 CSE. DBMS and OS feel shaky before the end-sems and I have a Maths backlog. I want a plan and someone to check on me.";
  if (isGate(exam)) return "e.g. GATE CS in 4 months, working full time. Mocks around 45/100; Algorithms and OS are weak. I want a weekly plan and someone to check on me.";
  if (isPlacement(exam)) return "e.g. Final year, placements in 3 months. Arrays and DP are fine, graphs and system design aren't. I want mock interviews and a plan.";
  if (exam === "neet") return "e.g. Class 12, NEET in 7 months. Mocks around 450/720. Physics takes too long and I lose marks in Biology details. I want a weekly plan and someone to check on me.";
  if (exam === "ssc_cgl") return "e.g. SSC CGL Tier-I in 4 months, working full time. Mocks around 110/200. Quant is slow and General Awareness is weak. I want a weekly plan and someone to check on me.";
  return "e.g. Class 12, JEE in 7 months. Mocks around 120/300. Maths takes too long and I panic in the last hour. I want a weekly plan and someone to check on me.";
}

function RequestDialog({ mentor, onClose }: { mentor: MentorCard | null; onClose: () => void }) {
  const qc = useQueryClient();
  const exam = useAuth((s) => s.user?.exam_target);
  const navigate = useNavigate();
  const [goal, setGoal] = useState("");
  const [share, setShare] = useState(true);
  const send = useMutation({
    mutationFn: () => api.mentorRequest(mentor!.id, { goal: goal.trim(), share_progress: share }),
    onSuccess: (m) => { qc.invalidateQueries({ queryKey: ["mentors"] }); qc.invalidateQueries({ queryKey: ["mentorships"] }); toast.success(`Sent. ${mentor!.name.split(" ")[0]} will reply here.`); onClose(); navigate(`/app/mentors/${m.id}`); },
    onError: failed,
  });
  return (
    <Dialog open={!!mentor} onClose={onClose} title={mentor ? `Ask ${mentor.name.split(" ")[0]} to mentor you` : ""} subtitle={mentor?.credential}>
      <div className="space-y-4">
        <div>
          <Label hint={`${goal.trim().length}/1000`}>Where you are and what you need</Label>
          <Textarea rows={5} value={goal} onChange={(e) => setGoal(e.target.value)} maxLength={1000}
            placeholder={requestExample(exam)} />
        </div>
        <div className="flex items-center justify-between gap-3 rounded-xl border border-line bg-bg-soft p-3">
          <div>
            <div className="text-sm font-medium">Let my mentor see my Focs progress</div>
            <div className="text-xs text-muted">Study time, tests and weak chapters, never your notes or doubts. Change it any time.</div>
          </div>
          <Switch checked={share} onChange={setShare} label="Share my progress with my mentor" />
        </div>
        <Button variant="primary" className="w-full" disabled={goal.trim().length < 20} loading={send.isPending} onClick={() => send.mutate()}>Send request</Button>
      </div>
    </Dialog>
  );
}

function MentorTile({ m, topics, languages, onAsk, dir }: { m: MentorCard; topics: Record<string, string>; languages: Record<string, string>; onAsk: () => void; dir: MentorDirectory }) {
  const full = !m.accepting || m.open_spots === 0;
  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start gap-3">
        <Initials name={m.name} photo={m.photo} className="h-14 w-14 text-base" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5 font-semibold">{m.name}<Badge tone="ok"><BadgeCheck className="h-3 w-3" />Verified</Badge></div>
          <div className="text-[13px] font-medium text-accent">{m.credential}</div>
          <div className="text-xs text-muted">{m.institution}</div>
        </div>
        {m.rating !== null && (
          <div className="shrink-0 text-right">
            <div className="flex items-center gap-1 text-sm font-semibold"><Star className="h-4 w-4 fill-warn text-warn" />{m.rating.toFixed(1)}</div>
            <div className="text-[11px] text-muted">{m.ratings} rating{m.ratings === 1 ? "" : "s"}</div>
          </div>
        )}
      </div>
      {m.qualification && <div className="mt-2 text-xs text-muted">{m.qualification}{m.experience && ` · ${m.experience}`}</div>}
      {m.headline && <p className="mt-3 text-[13.5px] font-medium">{m.headline}</p>}
      {m.about && <p className="mt-1 line-clamp-3 text-[13px] leading-relaxed text-fg-soft">{m.about}</p>}
      <div className="mt-3 flex flex-wrap gap-1.5">{m.topics.map((t) => <Badge key={t}>{topics[t] ?? t}</Badge>)}</div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1"><Video className="h-3.5 w-3.5" />{`${m.has_hours ? `Private ${dir.call_minutes}-min calls` : "Calls, once they set hours"}: ${m.call_price_inr ? `₹${m.call_price_inr}` : "free"}`}</span>
        {m.calls_done > 0 && <span>{m.calls_done} call{m.calls_done === 1 ? "" : "s"} done</span>}
      </div>
      <div className="mt-auto flex flex-wrap items-center gap-3 pt-4">
        <span className="flex items-center gap-1 text-xs text-muted"><Languages className="h-3.5 w-3.5" />{m.languages.map((l) => languages[l] ?? l).join(", ")}</span>
        <span className="text-xs text-muted">{full ? "No free spots" : `${m.open_spots} of ${m.capacity} spots open`}</span>
        <span className="flex-1" />
        {m.with_me === "active" ? <Link to="/app/mentors?tab=mine"><Button size="sm">Your mentor</Button></Link>
          : m.with_me === "requested" ? <Button size="sm" disabled>Request sent</Button>
            : <Button size="sm" variant="primary" disabled={full} onClick={onAsk}>Ask to mentor me</Button>}
      </div>
    </Card>
  );
}

function Find({ dir, exam, setExam }: { dir: MentorDirectory; exam: string; setExam: (e: string) => void }) {
  const seniors = useAuth((s) => asksSeniors(s.user?.exam_target));
  const tests = useAuth((s) => hasTests(s.user?.exam_target));
  const [topic, setTopic] = useState("");
  const [asking, setAsking] = useState<MentorCard | null>(null);
  const shown = dir.mentors.filter((m) => !topic || m.topics.includes(topic));
  return (
    <div className="space-y-4">
      <Card className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center">
        <Select value={exam} onChange={(e) => setExam(e.target.value)} className="lg:max-w-[14rem]" aria-label="Exam">
          {Object.entries(dir.exams).sort(([a], [b]) => Number(b === dir.my_exam) - Number(a === dir.my_exam)).map(([k, v]) => <option key={k} value={k}>{v}{k === dir.my_exam ? " (yours)" : ""}</option>)}
        </Select>
        <div className="flex flex-wrap gap-1.5">
          {[["", "Any help"], ...Object.entries(dir.topics).filter(([k]) => tests || k !== "mocks")].map(([k, v]) => (
            <button key={k} onClick={() => setTopic(k)} className={cn("rounded-full border px-3 py-1.5 text-[12.5px] transition pointer-coarse:py-2.5",
              topic === k ? "border-accent/60 bg-accent-soft text-fg" : "border-line bg-bg-soft text-fg-soft hover:border-line-strong")}>{v}</button>
          ))}
        </div>
      </Card>
      {shown.length ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {shown.map((m) => <MentorTile key={m.id} m={m} topics={dir.topics} languages={dir.languages} onAsk={() => setAsking(m)} dir={dir} />)}
        </div>
      ) : (
        <EmptyState icon={<Compass className="h-6 w-6" />} title={dir.mentors.length ? "No mentor for that yet" : `No mentors yet for ${dir.exams[exam] ?? "this exam"}`}
          body={dir.mentors.length ? "Try \"Any help\": most mentors help with more than they list." : `Focs is verifying ${dir.who ?? "mentors"}. Cleared this exam yourself? Become the first mentor.`}
          action={dir.mentors.length || !seniors ? undefined : <Link to="/app/campus"><Button variant="secondary">Ask a senior in the meantime</Button></Link>} />
      )}
      <RequestDialog mentor={asking} onClose={() => setAsking(null)} />
    </div>
  );
}

/* ---------------------------------------------------------------- mentorships */
function Row({ m }: { m: MentorshipRow }) {
  const s = STATUS[m.status];
  return (
    <Link to={`/app/mentors/${m.id}`} className="group block">
      <Card className="flex items-center gap-4 p-4 transition group-hover:border-line-strong">
        <Initials name={m.with} photo={m.photo} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 font-semibold">{m.with}<Badge tone={s.tone}>{s.label}</Badge>
            {m.checkin_due && <Badge tone="accent"><CalendarCheck className="h-3 w-3" />Check-in due</Badge>}
            {m.unread > 0 && <Badge tone="bad">{m.unread} new</Badge>}
          </div>
          <div className="truncate text-[13px] text-muted">{m.preview ?? m.credential}</div>
        </div>
        <span className="hidden text-xs text-muted sm:block">{timeAgo(m.last_message_at ?? m.created_at)}</span>
        <ArrowRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5" />
      </Card>
    </Link>
  );
}

function Mine({ list, onFind, none }: { list: MentorshipList; onFind: () => void; none: boolean }) {
  const seniors = useAuth((s) => asksSeniors(s.user?.exam_target));
  if (!list.as_student.length) {
    // no mentor has joined this exam yet: a button to an empty list would be a dead end, so point at what works today
    return none
      ? <EmptyState icon={<HeartHandshake className="h-6 w-6" />} title="Mentors are joining soon"
          body={`Focs checks every mentor before listing them, and none for your exam are listed yet.${seniors ? " Until then, seniors who cleared it answer your questions." : ""}`}
          action={seniors ? <Link to="/app/campus"><Button variant="primary">Ask a senior</Button></Link> : undefined} />
      : <EmptyState icon={<HeartHandshake className="h-6 w-6" />} title="No mentor yet"
          body="Pick someone who cleared your exam. You'll talk every week: they see how your week went and tell you what to change."
          action={<Button variant="primary" onClick={onFind}>Find a mentor</Button>} />;
  }
  return <div className="space-y-2.5">{list.as_student.map((m) => <Row key={m.id} m={m} />)}</div>;
}

/* ---------------------------------------------------------------- becoming a mentor */
/** Mentoring happens from a mentor account of its own, so a student is sent to make one rather than apply from here. */
function BecomeMentorDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  return (
    <Dialog open={open} onClose={onClose} title="Become a mentor" subtitle="Cleared an exam? Guide students preparing for it, at your own price.">
      <div className="space-y-4 text-sm">
        <p className="text-fg-soft">Mentors use a separate mentor account, with a dashboard of its own for their seekers, calls, master sessions and earnings.</p>
        <ol className="list-decimal space-y-1.5 pl-5 text-fg-soft">
          <li>Create a mentor account with a different email.</li>
          <li>Send your qualifications and proof of what you cleared.</li>
          <li>Focs checks them by hand, usually within two days, and you're listed.</li>
        </ol>
        <p className="text-xs text-muted">This student account stays as it is: sign back in to it any time.</p>
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>Not now</Button>
          <Button variant="primary" onClick={() => navigate("/switch/mentor", { replace: true })}>Sign out and create a mentor account</Button>
        </div>
      </div>
    </Dialog>
  );
}

/* ---------------------------------------------------------------- page */
export default function Mentors() {
  const [params, setParams] = useSearchParams();
  const [exam, setExam] = useState("");
  const [applying, setApplying] = useState(false);
  const { data: dir, isLoading } = useQuery({ queryKey: ["mentors", exam], queryFn: () => api.mentors(exam || undefined), placeholderData: (p) => p });
  const { data: list } = useQuery({ queryKey: ["mentorships"], queryFn: api.mentorships, refetchInterval: 30_000 });
  const asked = params.get("tab");
  const tab = asked === "group" ? "sessions" : asked === "find" || asked === "sessions" || asked === "mine" ? asked
    : list?.as_student.some((m) => m.status !== "declined") ? "mine" : "find";
  const go = (t: string) => setParams({ tab: t }, { replace: true });

  if (isLoading || !dir) return <div className="mx-auto max-w-5xl space-y-4"><Skeleton className="h-24" /><Skeleton className="h-72" /></div>;
  const due = list?.as_student.find((m) => m.checkin_due);
  const tabs = [{ value: "find", label: "Find a mentor" }, { value: "sessions", label: "Master sessions" }, { value: "mine", label: `My mentors${list?.as_student.length ? ` · ${list.as_student.length}` : ""}` }];

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow={<span className="flex items-center gap-1.5"><Compass className="h-3.5 w-3.5" />Mentors</span>}
        title="Guidance from people who cleared it"
        subtitle={`${dir.who ? dir.who[0].toUpperCase() + dir.who.slice(1) : "People who cleared your exam"}, checked by Focs before they're listed. A mentor stays with you: chat and a weekly check-in, private calls at the price they set, and master sessions you register for.${dir.group_per_week > 0 ? ` ${dir.pro ? "Your Pro includes" : "Pro includes"} ${dir.group_per_week} paid master session${dir.group_per_week === 1 ? "" : "s"} a week.` : ""}`}
        actions={<Button onClick={() => setApplying(true)} icon={<Plus className="h-4 w-4" />}>Become a mentor</Button>} />

      {due && (
        <Link to={`/app/mentors/${due.id}`} className="group mb-4 flex items-center gap-3 rounded-2xl border border-accent/40 bg-accent-soft p-4">
          <CalendarCheck className="h-5 w-5 shrink-0 text-accent" />
          <span className="min-w-0 flex-1 text-sm"><b>Time for your weekly check-in with {due.with.split(" ")[0]}.</b> <span className="text-fg-soft">Two lines on your week; Focs adds your study time, tests and weak chapters.</span></span>
          <ArrowRight className="h-4 w-4 text-muted transition group-hover:translate-x-0.5" />
        </Link>
      )}
      <div className="mb-4 max-w-full overflow-x-auto"><Segmented value={tab} onChange={go} options={tabs} /></div>

      {tab === "find" && <Find dir={dir} exam={dir.exam ?? ""} setExam={setExam} />}
      {tab === "sessions" && <StudentSessions />}
      {tab === "mine" && list && <Mine list={list} onFind={() => go("find")} none={!dir.mentors.length} />}
      <p className="mt-6 flex gap-2 px-1 text-xs leading-relaxed text-muted"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
        Mentors are students and graduates, checked by Focs, not teachers. Conversations stay on Focs: phone numbers and emails are hidden, and anything that feels wrong can be reported from the conversation.</p>
      <BecomeMentorDialog open={applying} onClose={() => setApplying(false)} />
    </div>
  );
}
