import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CalendarPlus, Check, Clock, ListTodo, Lock, Star, Video, X } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, CardHeader, Input, Label, Segmented, Skeleton, Textarea } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { pay, PaymentCancelled } from "@/lib/checkout";
import type { CallSlot, MentorCall, MentorshipCalls } from "@/lib/types";
import { cn } from "@/lib/utils";

const failed = (e: unknown) => { if (!(e instanceof PaymentCancelled)) toast.error(e instanceof ApiError || e instanceof Error ? e.message : "That didn't work. Try again."); };
export const dayLabel = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
export const timeLabel = (iso: string) => new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
export const whenLabel = (iso: string) => `${dayLabel(iso)}, ${timeLabel(iso)}`;

export function Stars({ value, onChange, size = "h-5 w-5" }: { value: number; onChange?: (n: number) => void; size?: string }) {
  return (
    <span className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" disabled={!onChange} onClick={() => onChange?.(n)} aria-label={`${n} star${n === 1 ? "" : "s"}`}
          className={cn(!onChange && "cursor-default")}>
          <Star className={cn(size, n <= value ? "fill-warn text-warn" : "text-line-strong")} />
        </button>
      ))}
    </span>
  );
}

/* ---------------------------------------------------------------- booking */
function BookDialog({ open, onClose, mentorshipId, info, mentor }: { open: boolean; onClose: () => void; mentorshipId: number; info: MentorshipCalls; mentor: string }) {
  const qc = useQueryClient();
  const [pick, setPick] = useState<CallSlot | null>(null);
  const [agenda, setAgenda] = useState("");
  const days = useMemo(() => {
    const m = new Map<string, CallSlot[]>();
    info.slots.forEach((s) => m.set(dayLabel(s.starts_at), [...(m.get(dayLabel(s.starts_at)) ?? []), s]));
    return [...m.entries()];
  }, [info.slots]);
  const book = useMutation({
    mutationFn: async () => {
      const r = await api.bookCall(mentorshipId, { starts_at: pick!.starts_at, agenda: agenda.trim() });
      if (r.checkout) await pay(r.checkout);
      return r;
    },
    onSuccess: (r) => {
      toast.success(`Call booked for ${whenLabel(r.call.starts_at)}${r.call.paid_via === "free" ? " · free" : ""}`);
      setPick(null); setAgenda(""); onClose();
    },
    onError: failed,
    onSettled: () => { qc.invalidateQueries({ queryKey: ["calls", mentorshipId] }); qc.invalidateQueries({ queryKey: ["my-calls"] }); },
  });
  const first = mentor.split(" ")[0];
  return (
    <Dialog open={open} onClose={onClose} wide title={`Book a call with ${first}`} subtitle={`${info.minutes} minutes on video. Times are in your time zone.`}>
      <div className="space-y-4">
        {!info.slots.length ? <p className="text-sm text-muted">{info.has_hours ? `${first}'s hours for the next two weeks are all booked.` : `${first} hasn't set call hours yet. Ask in the chat.`}</p> : (
          <div className="max-h-72 space-y-3 overflow-y-auto pr-1">
            {days.map(([day, slots]) => (
              <div key={day}>
                <div className="mb-1.5 text-[12px] font-semibold text-muted">{day}</div>
                <div className="flex flex-wrap gap-1.5">
                  {slots.map((s) => (
                    <button key={s.starts_at} type="button" onClick={() => setPick(s)}
                      className={cn("inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px] tabular-nums transition",
                        pick?.starts_at === s.starts_at ? "border-accent bg-accent-soft font-semibold" : "border-line bg-bg-soft hover:border-line-strong")}>
                      {timeLabel(s.starts_at)}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
        <div>
          <Label>What do you want to cover?</Label>
          <Textarea rows={3} value={agenda} onChange={(e) => setAgenda(e.target.value)} maxLength={1000}
            placeholder="e.g. My mock scores are stuck at 120. I want a plan for the next 4 weeks and help with time in the paper." />
          <p className="mt-1 text-[11.5px] text-muted">Your mentor also sees your week on Focs with it, if you share your progress.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-bg-soft p-3 text-sm">
          <span>{info.price_inr ? <><b>₹{info.price_inr}</b> for a private {info.minutes}-minute call</> : <><b>Free</b> {info.minutes}-minute call: your mentor doesn't charge</>}</span>
          <span className="flex-1" />
          <Button variant="primary" disabled={!pick} loading={book.isPending} onClick={() => book.mutate()}>
            {!pick ? "Pick a time" : info.price_inr ? `Pay ₹${info.price_inr} and book` : "Book the call"}
          </Button>
        </div>
        {info.payments === null && info.price_inr > 0 && <p className="text-xs text-bad">Payments aren't set up on this server yet, so paid calls can't be booked.</p>}
        <p className="text-[11.5px] text-muted">Cancel up to 12 hours before for a full refund. If your mentor cancels, you're always refunded.</p>
      </div>
    </Dialog>
  );
}

/* ---------------------------------------------------------------- one call */
function NotesForm({ call }: { call: MentorCall }) {
  const qc = useQueryClient();
  const [notes, setNotes] = useState("");
  const [actions, setActions] = useState(["", "", ""]);
  const save = useMutation({
    mutationFn: () => api.callNotes(call.id, { notes: notes.trim(), actions: actions.map((a) => a.trim()).filter(Boolean) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["calls", call.mentorship_id] }); qc.invalidateQueries({ queryKey: ["my-calls"] }); toast.success("Notes sent. The action items are on their dashboard now."); },
    onError: failed,
  });
  return (
    <div className="mt-3 space-y-2 rounded-xl border border-accent/30 bg-accent-soft/30 p-3">
      <div className="text-[13px] font-semibold">How did it go? Leave notes and what to do next</div>
      <Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={3000} placeholder="What you talked about and what you noticed." />
      {actions.map((a, i) => (
        <Input key={i} value={a} onChange={(e) => setActions(actions.map((x, j) => (j === i ? e.target.value : x)))} maxLength={200} placeholder={`Action item ${i + 1}, e.g. two timed calculus sets a day`} />
      ))}
      <Button size="sm" variant="primary" disabled={notes.trim().length < 10} loading={save.isPending} onClick={() => save.mutate()}>Send notes</Button>
    </div>
  );
}

function RateForm({ call }: { call: MentorCall }) {
  const qc = useQueryClient();
  const [stars, setStars] = useState(0);
  const [review, setReview] = useState("");
  const rate = useMutation({
    mutationFn: () => api.rateCall(call.id, { rating: stars, review: review.trim() }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["calls", call.mentorship_id] }); qc.invalidateQueries({ queryKey: ["my-calls"] }); toast.success("Thanks for rating."); },
    onError: failed,
  });
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-bg-soft p-3">
      <span className="text-[13px] font-medium">Rate this call</span><Stars value={stars} onChange={setStars} />
      <Input value={review} onChange={(e) => setReview(e.target.value)} maxLength={600} placeholder="A line for other students (optional)" className="h-8 min-w-0 flex-1 text-[13px]" />
      <Button size="sm" variant="primary" disabled={!stars} loading={rate.isPending} onClick={() => rate.mutate()}>Rate</Button>
    </div>
  );
}

export function ActionList({ call }: { call: MentorCall }) {
  const qc = useQueryClient();
  const tick = useMutation({
    mutationFn: (v: { i: number; done: boolean }) => api.tickAction(call.id, v.i, v.done),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["calls", call.mentorship_id] }); qc.invalidateQueries({ queryKey: ["my-calls"] }); },
    onError: failed,
  });
  if (!call.actions.length) return null;
  return (
    <ul className="mt-2 space-y-1.5">
      {call.actions.map((a, i) => (
        <li key={i}>
          <button type="button" disabled={call.role !== "student"} onClick={() => tick.mutate({ i, done: !a.done })} className="flex items-start gap-2 text-left text-[13.5px]">
            <span className={cn("mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded border", a.done ? "border-ok bg-ok text-white" : "border-line-strong")}>{a.done && <Check className="h-3 w-3" />}</span>
            <span className={cn(a.done && "text-muted line-through")}>{a.text}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function CallRow({ c }: { c: MentorCall }) {
  const qc = useQueryClient();
  const cancel = useMutation({
    mutationFn: () => api.cancelCall(c.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["calls", c.mentorship_id] }); qc.invalidateQueries({ queryKey: ["my-calls"] }); toast.success("Cancelled"); },
    onError: failed,
  });
  const ask = () => {
    const money = c.paid_via === "paid" && c.status === "booked" ? (c.refundable ? ` The ₹${c.price_inr} will be refunded.` : " It's less than 12 hours away, so there's no refund.") : "";
    if (window.confirm(`Cancel the call on ${whenLabel(c.starts_at)}?${money}`)) cancel.mutate();
  };
  const upcoming = (c.status === "booked" || c.status === "held") && !c.over;
  return (
    <div className="rounded-xl border border-line bg-bg-soft p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <Video className={cn("h-4 w-4", c.can_join ? "text-ok" : "text-accent")} />
        <span className="text-[14px] font-semibold">{whenLabel(c.starts_at)}</span>
        <span className="text-xs text-muted">{c.minutes} min</span>
        {c.paid_via === "pro" ? <Badge tone="accent">Pro</Badge> : <Badge>₹{c.price_inr}</Badge>}
        {c.status === "held" && <Badge tone="warn">Awaiting payment</Badge>}
        {c.status === "cancelled" && <Badge>Cancelled{c.cancelled_by === "system" ? " (refund due)" : ""}</Badge>}
        {c.status === "done" && <Badge tone="ok">Done</Badge>}
        {c.rating && <Stars value={c.rating} size="h-3.5 w-3.5" />}
        <span className="flex-1" />
        {c.can_join && c.join_url && <a href={c.join_url} target="_blank" rel="noreferrer"><Button size="sm" variant="primary" icon={<Video className="h-3.5 w-3.5" />}>Join call</Button></a>}
        {upcoming && !c.can_join && c.status === "booked" && <span className="text-xs text-muted">Opens at {timeLabel(c.opens_at)}</span>}
        {upcoming && <Button size="sm" variant="ghost" loading={cancel.isPending} onClick={ask} icon={<X className="h-3.5 w-3.5" />}>Cancel</Button>}
      </div>
      {c.agenda && <p className="mt-1.5 text-[13px] text-fg-soft"><span className="text-muted">Agenda:</span> {c.agenda}</p>}
      {c.can_join && c.join_url && <RoomTip host={c.role === "mentor"} className="mt-1.5" />}
      {c.role === "mentor" && c.snapshot && upcoming && (
        <p className="mt-1 text-xs text-muted">Their week when they booked: {Math.round(c.snapshot.week_minutes / 60)} h studied · streak {c.snapshot.streak}
          {c.snapshot.last_test ? ` · last test ${c.snapshot.last_test.percent}%` : ""}{c.snapshot.weak.length ? ` · weak: ${c.snapshot.weak.slice(0, 3).map((w) => w.chapter).join(", ")}` : ""}</p>
      )}
      {c.notes && (
        <div className="mt-2.5 border-t border-line pt-2.5">
          <div className="flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-[0.12em] text-muted"><ListTodo className="h-3 w-3" />Mentor's notes</div>
          <p className="mt-1 whitespace-pre-wrap text-[13.5px] leading-relaxed">{c.notes}</p>
          <ActionList call={c} />
        </div>
      )}
      {c.review && <p className="mt-1.5 text-xs italic text-muted">“{c.review}”</p>}
      {c.needs_notes && <NotesForm call={c} />}
      {c.can_rate && <RateForm call={c} />}
    </div>
  );
}

/** The private calls of one mentorship: book and pay, join when the room opens, notes and ratings after. */
/** Under a live Join button: meet.jit.si only starts a room once a signed-in host arrives, and on phones it pushes its
 * app first. Without this, a student sat on "waiting for a moderator" and a mentor didn't know they had to sign in. */
export function RoomTip({ host, className }: { host: boolean; className?: string }) {
  return (
    <p className={cn("text-[12px] leading-relaxed text-muted", className)}>
      {host
        ? "The room is on meet.jit.si and starts once you sign in there as the host (Google works; once per device). Your students wait until you do."
        : "Opens on meet.jit.si. If it says it's waiting for a moderator, your mentor hasn't opened the room yet: keep the tab open. On a phone, pick “Join in browser” or use the Jitsi Meet app."}
    </p>
  );
}

export function CallsPanel({ mentorshipId, role, other, active }: { mentorshipId: number; role: "student" | "mentor"; other: string; active: boolean }) {
  const [booking, setBooking] = useState(false);
  const { data } = useQuery({ queryKey: ["calls", mentorshipId], queryFn: () => api.mentorshipCalls(mentorshipId), refetchInterval: 60_000 });
  if (!data) return <Skeleton className="h-28" />;
  return (
    <Card>
      <CardHeader title="Calls" icon={<CalendarClock className="h-4 w-4" />}
        subtitle={role === "student" ? `Private ${data.minutes}-minute video call · ${data.price_inr ? `₹${data.price_inr} each` : "free"}`
          : `Calls your student booked: you earn ₹${data.mentor_share_inr} of each ₹${data.price_inr}. The room opens 10 minutes before.`}
        action={role === "student" && active ? <Button size="sm" variant="primary" onClick={() => setBooking(true)} icon={<CalendarPlus className="h-3.5 w-3.5" />}>Book a call</Button> : undefined} />
      <div className="space-y-2.5 p-5">
        {data.calls.length ? data.calls.map((c) => <CallRow key={c.id} c={c} />)
          : <p className="text-sm text-muted">{role === "student" ? "No calls yet. Book one when you want to talk it through." : "No calls booked yet."}</p>}
      </div>
      {role === "student" && <BookDialog open={booking} onClose={() => setBooking(false)} mentorshipId={mentorshipId} info={data} mentor={other} />}
    </Card>
  );
}

/* ---------------------------------------------------------------- the mentor's weekly hours */
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const TIMES = Array.from({ length: 36 }, (_, i) => `${String(6 + Math.floor(i / 2)).padStart(2, "0")}:${i % 2 ? "30" : "00"}`);
const ampm = (t: string) => { const [h, m] = t.split(":").map(Number); return `${((h + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`; };

export function HoursEditor({ initial }: { initial: { day: number; time: string }[] }) {
  const qc = useQueryClient();
  const [slots, setSlots] = useState(() => new Set(initial.map((s) => `${s.day}|${s.time}`)));
  const [day, setDay] = useState("0");
  const save = useMutation({
    mutationFn: () => api.mentorSlots([...slots].map((k) => ({ day: Number(k.split("|")[0]), time: k.split("|")[1] }))),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mentor-me"] }); toast.success("Hours saved. Your students can book them now."); },
    onError: failed,
  });
  const toggle = (k: string) => setSlots((cur) => { const n = new Set(cur); if (n.has(k)) n.delete(k); else if (n.size < 40) n.add(k); return n; });
  return (
    <Card>
      <CardHeader title="Your call hours" icon={<Clock className="h-4 w-4" />} subtitle="Every week, India time. Each slot is a 30-minute call your students can book up to two weeks ahead." />
      <div className="space-y-3 p-5">
        <Segmented size="sm" value={day} onChange={setDay}
          options={DAYS.map((d, i) => ({ value: String(i), label: `${d}${[...slots].some((k) => k.startsWith(`${i}|`)) ? " •" : ""}` }))} />
        <div className="grid grid-cols-3 gap-1.5 min-[400px]:grid-cols-4 sm:flex sm:flex-wrap">
          {TIMES.map((t) => {
            const k = `${day}|${t}`;
            return (
              <button key={k} type="button" onClick={() => toggle(k)}
                className={cn("rounded-lg border px-2 py-2.5 text-[12.5px] sm:w-[5.5rem] sm:py-1.5 tabular-nums transition", slots.has(k) ? "border-accent bg-accent-soft font-semibold" : "border-line bg-bg-soft text-fg-soft hover:border-line-strong")}>
                {ampm(t)}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-muted">{slots.size ? `${slots.size} slot${slots.size === 1 ? "" : "s"} a week` : <><Lock className="mr-1 inline h-3 w-3" />No hours yet: students can chat but can't book calls</>}</span>
          <span className="flex-1" />
          <Button size="sm" variant="primary" loading={save.isPending} onClick={() => save.mutate()}>Save hours</Button>
        </div>
      </div>
    </Card>
  );
}
