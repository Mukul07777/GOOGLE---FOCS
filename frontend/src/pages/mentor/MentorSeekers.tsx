import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarCheck, HeartHandshake, Inbox, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { ApprovedOnly, useWorkspace } from "@/components/MentorShell";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, EmptyState, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { MentorshipRow } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { Initials } from "@/pages/Mentors";

const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work. Try again.");

/** One seeker: their name, how the conversation stands, and the way in. */
export function SeekerRow({ m }: { m: MentorshipRow }) {
  return (
    <Link to={`/mentor/seekers/${m.id}`} className="group block">
      <Card className="flex items-center gap-4 p-4 transition group-hover:border-fg">
        <Initials name={m.with} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 font-semibold">{m.with}
            {m.status !== "active" && <Badge>{m.status === "ended" ? "Ended" : m.status === "declined" ? "Declined" : "Waiting"}</Badge>}
            {m.unread > 0 && <Badge tone="bad">{m.unread} new</Badge>}
            {m.status === "active" && m.last_checkin_at && <Badge><CalendarCheck className="h-3 w-3" />checked in {timeAgo(m.last_checkin_at)}</Badge>}
          </div>
          <div className="truncate text-[13px] text-muted">{m.preview ?? m.goal}</div>
        </div>
        <span className="hidden text-xs text-muted sm:block">{timeAgo(m.last_message_at ?? m.accepted_at ?? m.created_at)}</span>
        <ArrowRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5" />
      </Card>
    </Link>
  );
}

function Seekers() {
  const qc = useQueryClient();
  const { data: ws } = useWorkspace();
  const { data: list, isLoading } = useQuery({ queryKey: ["mentorships"], queryFn: api.mentorships, refetchInterval: 30_000 });
  const decide = useMutation({
    mutationFn: (v: { id: number; to: "accept" | "decline" }) => api.mentorDecide(v.id, v.to),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["mentorships"] }); qc.invalidateQueries({ queryKey: ["mentor-me"] }); toast.success(r.status === "active" ? `${r.with} is your seeker now. Say hello.` : "Declined"); },
    onError: failed,
  });
  if (isLoading || !list || !ws?.profile) return <Skeleton className="h-72" />;
  const p = ws.profile;
  const requests = list.as_mentor.filter((m) => m.status === "requested");
  const active = list.as_mentor.filter((m) => m.status === "active");
  const past = list.as_mentor.filter((m) => m.status === "ended" || m.status === "declined");
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader eyebrow="Seekers" title="The students you guide"
        subtitle={`${active.length} of ${p.capacity} places taken. Each seeker sends a check-in every week with their Focs progress; reply with what to change. ${p.accepting ? "" : "You're not taking new students right now (Profile)."}`} />
      {requests.length > 0 && (
        <Card className="mb-6">
          <CardHeader title={`Asking for you · ${requests.length}`} icon={<Inbox className="h-4 w-4" />} subtitle="Read what they need. Accept only if you can reply every week." />
          <div className="mt-3 divide-y divide-line border-t border-line">
            {requests.map((r) => (
              <div key={r.id} className="space-y-2 px-5 py-4">
                <div className="flex items-center gap-2 font-semibold"><Initials name={r.with} className="h-8 w-8 text-xs" />{r.with}<span className="text-xs font-normal text-muted">{timeAgo(r.created_at)}</span>
                  {!r.share_progress && <Badge>keeps progress private</Badge>}</div>
                <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-fg-soft">{r.goal}</p>
                <div className="flex gap-2">
                  <Button size="sm" variant="primary" disabled={active.length >= p.capacity}
                    loading={decide.isPending && decide.variables?.id === r.id && decide.variables.to === "accept"} onClick={() => decide.mutate({ id: r.id, to: "accept" })}>Accept</Button>
                  <Button size="sm" variant="ghost" onClick={() => decide.mutate({ id: r.id, to: "decline" })}>Decline</Button>
                  {active.length >= p.capacity && <span className="self-center text-xs text-muted">You're full. Raise your limit in Profile.</span>}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold"><Users className="h-4 w-4" />Your seekers</div>
      {active.length ? <div className="space-y-2.5">{active.map((m) => <SeekerRow key={m.id} m={m} />)}</div>
        : <EmptyState icon={<HeartHandshake className="h-6 w-6" />} title="No seekers yet"
            body={`Students preparing for ${p.exam_label} can find you now. A clear headline and a master session help them choose you.`}
            action={<Link to="/mentor/profile"><Button>Polish my profile</Button></Link>} />}
      {past.length > 0 && (
        <>
          <div className="mb-3 mt-8 caps text-[10.5px] font-semibold text-muted">Past</div>
          <div className="space-y-2.5">{past.map((m) => <SeekerRow key={m.id} m={m} />)}</div>
        </>
      )}
    </div>
  );
}

export default function MentorSeekers() {
  return <ApprovedOnly><Seekers /></ApprovedOnly>;
}
