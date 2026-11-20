import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarCheck, ListTodo, MessageCircle, Star, Video } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { timeLabel, whenLabel } from "@/components/MentorCalls";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/primitives";
import { api } from "@/lib/api";

const DAY = 24 * 60 * 60 * 1000;

function Line({ to, icon, children, action }: { to: string; icon: ReactNode; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-accent/30 bg-accent-soft/60 p-4">
      {icon}
      <Link to={to} className="min-w-0 flex-1 truncate text-sm hover:underline">{children}</Link>
      {action ?? <Link to={to}><ArrowRight className="h-4 w-4 shrink-0 text-muted" /></Link>}
    </div>
  );
}

/** Dashboard: what mentorship needs from you now (a call or master session to join, a rating to give, the week's
    check-in, a reply), and the action items your mentor left you. Nothing at all when there's nothing. */
export function MentorNudge() {
  const { data: list } = useQuery({ queryKey: ["mentorships"], queryFn: api.mentorships, staleTime: 60_000 });
  const busy = !!list && list.as_student.length > 0;
  const { data: calls } = useQuery({ queryKey: ["my-calls"], queryFn: api.myCalls, enabled: busy, refetchInterval: 60_000 });
  const { data: group } = useQuery({ queryKey: ["group-sessions"], queryFn: api.groupSessions, staleTime: 60_000, refetchInterval: 60_000 });
  const qc = useQueryClient();
  const tick = useMutation({
    mutationFn: (a: { call_id: number; index: number }) => api.tickAction(a.call_id, a.index, true),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-calls"] }); toast.success("Done. One less thing before your next call."); },
  });
  if (!list) return null;
  const live = calls?.upcoming.find((c) => c.can_join);
  const seat = group?.sessions.find((s) => s.seated && s.status === "scheduled" && !s.over);
  const soon = calls?.upcoming.find((c) => c.status === "booked" && new Date(c.starts_at).getTime() - Date.now() < DAY);
  const due = list.as_student.find((m) => m.checkin_due);
  const unread = list.as_student.find((m) => m.unread > 0);
  const chat = (id: number) => `/app/mentors/${id}`;

  let line: ReactNode = null;
  if (live) line = <Line to={chat(live.mentorship_id)} icon={<Video className="h-5 w-5 text-ok" />}
    action={<a href={live.join_url!} target="_blank" rel="noreferrer"><Button size="sm" variant="primary">Join call</Button></a>}><b>Your call with {live.with.split(" ")[0]} is open now.</b></Line>;
  else if (seat?.can_join) line = <Line to="/app/mentors?tab=sessions" icon={<Video className="h-5 w-5 text-ok" />}
    action={<a href={seat.join_url!} target="_blank" rel="noreferrer"><Button size="sm" variant="primary">Join session</Button></a>}><b>{seat.mentor.split(" ")[0]}'s master session is live.</b> Your doubt is in the queue.</Line>;
  else if (seat && new Date(seat.starts_at).getTime() - Date.now() < DAY) line = <Line to="/app/mentors?tab=sessions" icon={<Video className="h-5 w-5 text-accent" />}><b>Master session with {seat.mentor.split(" ")[0]} at {timeLabel(seat.starts_at)}</b> · {seat.topic || "open doubts"}</Line>;
  else if (soon) line = <Line to={chat(soon.mentorship_id)} icon={<Video className="h-5 w-5 text-accent" />}><b>Call with {soon.with.split(" ")[0]} at {timeLabel(soon.starts_at)}</b> · {whenLabel(soon.starts_at)}. The room opens 10 minutes before.</Line>;
  else if (calls?.to_rate[0]) line = <Line to={chat(calls.to_rate[0].mentorship_id)} icon={<Star className="h-5 w-5 text-warn" />}><b>How was your call with {calls.to_rate[0].with.split(" ")[0]}?</b> Rate it in a tap.</Line>;
  else if (due) line = <Line to={chat(due.id)} icon={<CalendarCheck className="h-5 w-5 text-accent" />}><b>Weekly check-in with {due.with.split(" ")[0]}.</b> Two lines on your week; Focs adds your progress.</Line>;
  else if (unread) line = <Line to={chat(unread.id)} icon={<MessageCircle className="h-5 w-5 text-accent" />}><b>{unread.with.split(" ")[0]} wrote to you.</b> {unread.preview}</Line>;

  const first = calls?.actions[0];
  return (
    <>
      {line}
      {first && (
        <Card>
          <CardHeader title={`From ${first.with.split(" ")[0]}: before your next call`} icon={<ListTodo className="h-4 w-4" />}
            subtitle={`${calls!.actions.length} action item${calls!.actions.length === 1 ? "" : "s"} open · tick them off as you go`} />
          <ul className="space-y-1.5 px-5 pb-4">
            {calls!.actions.slice(0, 6).map((a) => (
              <li key={`${a.call_id}-${a.index}`}>
                <button type="button" onClick={() => tick.mutate(a)} className="flex items-start gap-2 text-left text-[13.5px]">
                  <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded border border-line-strong" />{a.text}
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
