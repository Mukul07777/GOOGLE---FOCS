import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BadgeCheck, CalendarClock, Clock, Hourglass, IndianRupee, Inbox, MessageSquare, NotebookPen, Presentation, ShieldAlert, Star, Users, Video } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/common";
import { MentorApplyForm } from "@/components/MentorApplyForm";
import { useWorkspace } from "@/components/MentorShell";
import { whenLabel } from "@/components/MentorCalls";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { MentorCard, MentorWorkspace } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { useAuth } from "@/stores/auth";

const STEPS = [
  ["Apply", "Your qualifications, a line about you, your price and proof of what you cleared."],
  ["Review", "Focs checks the proof by hand, usually within two days, and tells you here."],
  ["Guide", "Students find you, ask you to mentor them, book calls and register for your master sessions."],
];

/** Before approval: the application, and where it stands. */
function Application({ ws, profile }: { ws: MentorWorkspace; profile: MentorCard | null }) {
  const first = useAuth((s) => s.user?.full_name?.split(" ")[0]) ?? "there";
  const [editing, setEditing] = useState(!profile || profile.status === "rejected");
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="Mentor dashboard" title={profile ? "Your application" : `Welcome, ${first}`}
        subtitle={profile ? undefined : "Mentors on Focs are checked by hand before students can find them. Tell Focs what you cleared and how you'd help."} />
      <div className="mb-6 grid gap-px border border-line bg-line sm:grid-cols-3">
        {STEPS.map(([t, b], i) => {
          const done = profile ? (i === 0 || (i === 1 && profile.status !== "pending")) : false;
          const now = profile ? (profile.status === "pending" ? i === 1 : i === 0) : i === 0;
          return (
            <div key={t} className={now ? "band p-5" : "bg-bg p-5"}>
              <div className={now ? "caps text-[10px] font-medium text-band-muted" : "caps text-[10px] font-medium text-muted"}>Step {i + 1}{done ? " · done" : now ? " · now" : ""}</div>
              <div className="mt-2 text-[14px] font-semibold uppercase tracking-[0.1em]">{t}</div>
              <p className={now ? "mt-1.5 text-[13px] text-band-muted" : "mt-1.5 text-[13px] text-muted"}>{b}</p>
            </div>
          );
        })}
      </div>
      {profile?.status === "pending" && (
        <Card className="mb-5 flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
          <Hourglass className="h-7 w-7 shrink-0" strokeWidth={1.3} />
          <div className="min-w-0 flex-1">
            <div className="font-semibold">Under review since {timeAgo(profile.submitted_at ?? profile.created_at)}</div>
            <p className="text-[13px] text-muted">{profile.credential} · {profile.qualification} · {profile.institution}. You'll get a notification as soon as Focs decides.</p>
          </div>
          {!editing && <Button variant="secondary" onClick={() => setEditing(true)}>Edit and resend</Button>}
        </Card>
      )}
      {profile?.status === "rejected" && (
        <Card className="mb-5 flex gap-4 border-bad/40 p-5">
          <ShieldAlert className="h-7 w-7 shrink-0 text-bad" strokeWidth={1.3} />
          <div>
            <div className="font-semibold">Your application wasn't approved</div>
            <p className="text-[13px] text-muted">{profile.review_note ?? "The proof didn't show what you cleared."} Fix what's needed and send it again with clear proof.</p>
          </div>
        </Card>
      )}
      {editing && <MentorApplyForm ws={ws} profile={profile} onDone={() => setEditing(false)} />}
    </div>
  );
}

function Stat({ label, value, hint, icon, to }: { label: string; value: ReactNode; hint?: string; icon: ReactNode; to?: string }) {
  const body = (
    <div className="h-full bg-bg p-5 transition-colors hover:bg-panel">
      <div className="flex items-center gap-2 text-muted">{icon}<span className="caps text-[10px] font-medium">{label}</span></div>
      <div className="figure mt-3 text-[34px]">{value}</div>
      {hint && <div className="mt-1 text-[12px] text-muted">{hint}</div>}
    </div>
  );
  return to ? <Link to={to} className="block">{body}</Link> : body;
}

function Todo({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <Link to={to} className="group flex items-center gap-3 border-b border-line px-5 py-3.5 last:border-b-0 hover:bg-hover">
      <span className="grid h-8 w-8 shrink-0 place-items-center border border-line-strong">{icon}</span>
      <span className="min-w-0 flex-1 text-sm">{children}</span>
      <ArrowRight className="h-4 w-4 text-muted transition group-hover:translate-x-0.5" />
    </Link>
  );
}

/** After approval: the day at a glance. */
function Overview({ profile }: { profile: MentorCard }) {
  const { data: list } = useQuery({ queryKey: ["mentorships"], queryFn: api.mentorships, refetchInterval: 30_000 });
  const { data: calls } = useQuery({ queryKey: ["my-calls"], queryFn: api.myCalls, refetchInterval: 60_000 });
  const { data: hosting } = useQuery({ queryKey: ["hosting"], queryFn: api.hosting, refetchInterval: 60_000 });
  const { data: money } = useQuery({ queryKey: ["earnings"], queryFn: api.myEarnings });
  const requests = list?.as_mentor.filter((m) => m.status === "requested") ?? [];
  const active = list?.as_mentor.filter((m) => m.status === "active") ?? [];
  const unread = active.filter((m) => m.unread > 0);
  const upcomingSessions = hosting?.sessions.filter((s) => s.status === "scheduled" && !s.over) ?? [];
  const toMark = hosting?.sessions.filter((s) => s.needs_marking) ?? [];
  const upcomingCalls = calls?.upcoming.filter((c) => c.status === "booked") ?? [];
  const todo = requests.length + unread.length + (calls?.to_note.length ?? 0) + toMark.length;

  return (
    <div>
      <PageHeader eyebrow={<span className="flex items-center gap-1.5"><BadgeCheck className="h-3.5 w-3.5" />Verified {profile.exam_label} mentor</span>}
        title={`Hello, ${profile.name.split(" ")[0]}`}
        subtitle={profile.headline || `${profile.credential} · ${profile.institution}`}
        actions={<><Link to="/mentor/sessions"><Button variant="primary" icon={<Presentation className="h-4 w-4" />}>Post a master session</Button></Link>
          <Link to="/mentor/calls"><Button icon={<Clock className="h-4 w-4" />}>Call hours</Button></Link></>} />

      <div className="grid grid-cols-2 gap-px border border-line bg-line lg:grid-cols-4">
        <Stat label="Seekers" value={`${active.length}/${profile.capacity}`} hint={profile.accepting ? `${requests.length} waiting for you` : "Not taking new students"} icon={<Users className="h-3.5 w-3.5" />} to="/mentor/seekers" />
        <Stat label="Calls booked" value={upcomingCalls.length} hint={profile.call_price_inr ? `₹${profile.call_price_inr} each` : "Free calls"} icon={<Video className="h-3.5 w-3.5" />} to="/mentor/calls" />
        <Stat label="Master sessions" value={upcomingSessions.length} hint={((n) => `${n} student${n === 1 ? "" : "s"} registered`)(upcomingSessions.reduce((n, s) => n + s.registered, 0))} icon={<Presentation className="h-3.5 w-3.5" />} to="/mentor/sessions" />
        <Stat label="This month" value={money ? `₹${money.month.earned_inr}` : "…"} hint={money ? `₹${money.total.owed_inr} owed to you` : undefined} icon={<IndianRupee className="h-3.5 w-3.5" />} to="/mentor/earnings" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader title="To do" icon={<Inbox className="h-4 w-4" />} subtitle={todo ? `${todo} thing${todo === 1 ? "" : "s"} waiting for you` : "You're all caught up."} />
          <div className="mt-3 border-t border-line">
            {requests.map((r) => <Todo key={`r${r.id}`} to={`/mentor/seekers/${r.id}`} icon={<Inbox className="h-4 w-4" />}><b>{r.with}</b> asked you to mentor them · {timeAgo(r.created_at)}</Todo>)}
            {unread.map((m) => <Todo key={`u${m.id}`} to={`/mentor/seekers/${m.id}`} icon={<MessageSquare className="h-4 w-4" />}><b>{m.with}</b>: {m.unread} new message{m.unread === 1 ? "" : "s"}</Todo>)}
            {calls?.to_note.map((c) => <Todo key={`n${c.id}`} to={`/mentor/seekers/${c.mentorship_id}`} icon={<NotebookPen className="h-4 w-4" />}>Write notes for your call with <b>{c.with}</b></Todo>)}
            {toMark.map((s) => <Todo key={`s${s.id}`} to="/mentor/sessions" icon={<Presentation className="h-4 w-4" />}>Mark <b>{s.topic || "your session"}</b> held</Todo>)}
            {!todo && <p className="px-5 py-6 text-sm text-muted">Nothing waiting. A master session at a fixed time each week is the easiest way to reach more students.</p>}
          </div>
        </Card>
        <Card>
          <CardHeader title="Coming up" icon={<CalendarClock className="h-4 w-4" />} />
          <div className="mt-3 border-t border-line">
            {[...upcomingCalls.map((c) => ({ key: `c${c.id}`, at: c.starts_at, label: <>Call with <b>{c.with}</b></>, tag: "Call", to: `/mentor/seekers/${c.mentorship_id}` })),
              ...upcomingSessions.map((s) => ({ key: `s${s.id}`, at: s.starts_at, label: <><b>{s.topic || "Master session"}</b> · {s.registered} registered</>, tag: "Session", to: "/mentor/sessions" }))]
              .sort((a, b) => a.at.localeCompare(b.at)).slice(0, 6)
              .map((x) => (
                <Link key={x.key} to={x.to} className="flex items-center gap-3 border-b border-line px-5 py-3.5 last:border-b-0 hover:bg-hover">
                  <Badge>{x.tag}</Badge><span className="min-w-0 flex-1 truncate text-sm">{x.label}</span><span className="shrink-0 text-xs text-muted">{whenLabel(x.at)}</span>
                </Link>
              ))}
            {!upcomingCalls.length && !upcomingSessions.length && <p className="px-5 py-6 text-sm text-muted">No calls or sessions booked yet.</p>}
          </div>
        </Card>
      </div>

      {(!profile.has_hours || profile.rating !== null) && (
        <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
          {!profile.has_hours && (
            <Card className="flex items-center gap-4 p-5">
              <Clock className="h-6 w-6 shrink-0" strokeWidth={1.3} />
              <div className="min-w-0 flex-1"><div className="font-semibold">Set your call hours</div><p className="text-[13px] text-muted">Your seekers can chat with you now, but they can't book a call until you set weekly hours.</p></div>
              <Link to="/mentor/calls"><Button size="sm" variant="primary">Set hours</Button></Link>
            </Card>
          )}
          {profile.rating !== null && (
            <Card className="flex items-center gap-4 p-5">
              <Star className="h-6 w-6 shrink-0 fill-warn text-warn" />
              <div><div className="font-semibold">{profile.rating.toFixed(1)} from {profile.ratings} rating{profile.ratings === 1 ? "" : "s"}</div>
                <p className="text-[13px] text-muted">{profile.calls_done} call{profile.calls_done === 1 ? "" : "s"} done. Students see this on your card.</p></div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

export default function MentorHome() {
  const { data: ws, isLoading } = useWorkspace();
  if (isLoading || !ws) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-72" /></div>;
  return ws.profile?.status === "approved" ? <Overview profile={ws.profile} /> : <Application ws={ws} profile={ws.profile} />;
}
