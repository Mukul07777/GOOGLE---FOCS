import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarClock, IndianRupee, NotebookPen, Video } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { HoursEditor, RoomTip, whenLabel } from "@/components/MentorCalls";
import { ApprovedOnly, useWorkspace } from "@/components/MentorShell";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Input, Label, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { MentorCard, MentorWorkspace } from "@/lib/types";

const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work. Try again.");

/** The mentor's own price for a private call, and what they keep of it. */
export function PriceCard({ ws, profile }: { ws: MentorWorkspace; profile: MentorCard }) {
  const qc = useQueryClient();
  const [price, setPrice] = useState(String(profile.call_price_inr));
  const n = Number(price);
  const ok = price !== "" && n >= 0 && n <= ws.max_call_price_inr;
  const save = useMutation({
    mutationFn: () => api.mentorEdit({ call_price_inr: n }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mentor-me"] }); qc.invalidateQueries({ queryKey: ["earnings"] }); toast.success(n ? `Calls are ₹${n} from now on` : "Your calls are free from now on"); },
    onError: failed,
  });
  return (
    <Card>
      <CardHeader title="Your price" icon={<IndianRupee className="h-4 w-4" />}
        subtitle={`For a ${ws.call_minutes}-minute private call. Calls already booked keep the price they were booked at.`} />
      <div className="flex flex-wrap items-end gap-3 p-5">
        <div className="w-40"><Label htmlFor="call-price" hint={`max ₹${ws.max_call_price_inr}`}>Price (₹)</Label>
          <Input id="call-price" inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))} /></div>
        <p className="min-w-0 flex-1 basis-48 pb-2 text-[13px] text-muted">
          {!ok ? "Enter a whole number in range." : n ? <>You earn <b className="text-fg">₹{n - Math.round((n * ws.commission_pct) / 100)}</b> of each call; Focs keeps {ws.commission_pct}% for payments and the platform.</> : "Free: students book without paying."}
        </p>
        <Button variant="primary" disabled={!ok || n === profile.call_price_inr} loading={save.isPending} onClick={() => save.mutate()}>Save price</Button>
      </div>
    </Card>
  );
}

function Calls() {
  const { data: ws } = useWorkspace();
  const { data: calls, isLoading } = useQuery({ queryKey: ["my-calls"], queryFn: api.myCalls, refetchInterval: 60_000 });
  if (isLoading || !calls || !ws?.profile) return <Skeleton className="h-72" />;
  const upcoming = calls.upcoming.filter((c) => c.status === "booked");
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <PageHeader eyebrow="Calls" title="Private calls" subtitle="Your seekers book your weekly hours up to two weeks ahead. The video room opens ten minutes before; afterwards you write notes and action items." />
      <Card>
        <CardHeader title={`Booked · ${upcoming.length}`} icon={<CalendarClock className="h-4 w-4" />} />
        <div className="mt-3 border-t border-line">
          {upcoming.map((c) => (
            <div key={c.id} className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3.5 last:border-b-0">
              <span className="w-44 shrink-0 text-sm font-semibold">{whenLabel(c.starts_at)}</span>
              <span className="min-w-0 flex-1 basis-48 text-sm"><b>{c.with}</b>{c.agenda && <span className="text-muted"> · {c.agenda}</span>}</span>
              <Badge>{c.paid_via === "free" ? "Free" : `₹${c.price_inr}`}</Badge>
              {c.can_join && c.join_url ? <a href={c.join_url} target="_blank" rel="noreferrer"><Button size="sm" variant="primary" icon={<Video className="h-3.5 w-3.5" />}>Join</Button></a>
                : <Link to={`/mentor/seekers/${c.mentorship_id}`} className="link-line">Open <ArrowRight className="h-3.5 w-3.5" /></Link>}
              {c.can_join && c.join_url && <RoomTip host className="basis-full" />}
            </div>
          ))}
          {!upcoming.length && <p className="px-5 py-6 text-sm text-muted">{ws.profile.has_hours ? "No calls booked yet." : "Set your weekly hours below so your seekers can book calls."}</p>}
        </div>
      </Card>
      {calls.to_note.length > 0 && (
        <Card>
          <CardHeader title="Notes to write" icon={<NotebookPen className="h-4 w-4" />} subtitle="A few lines and up to five action items after each call: your seeker ticks them off before the next one." />
          <div className="mt-3 border-t border-line">
            {calls.to_note.map((c) => (
              <Link key={c.id} to={`/mentor/seekers/${c.mentorship_id}`} className="flex items-center gap-3 border-b border-line px-5 py-3.5 last:border-b-0 hover:bg-hover">
                <span className="min-w-0 flex-1 text-sm">Call with <b>{c.with}</b> · {whenLabel(c.starts_at)}</span><ArrowRight className="h-4 w-4 text-muted" />
              </Link>
            ))}
          </div>
        </Card>
      )}
      <PriceCard ws={ws} profile={ws.profile} />
      <HoursEditor initial={ws.profile.slots ?? []} />
    </div>
  );
}

export default function MentorCallsPage() {
  return <ApprovedOnly><Calls /></ApprovedOnly>;
}
