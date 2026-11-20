import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Check, IndianRupee, MessageCircleQuestion, Presentation, Users, Video, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { RoomTip, timeLabel, whenLabel } from "@/components/MentorCalls";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Badge, Card, CardHeader, EmptyState, Input, Label, Select, Skeleton, Textarea } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { pay, PaymentCancelled } from "@/lib/checkout";
import type { GroupSessionRow, HostedSession } from "@/lib/types";
import { cn } from "@/lib/utils";

const failed = (e: unknown) => { if (!(e instanceof PaymentCancelled)) toast.error(e instanceof ApiError || e instanceof Error ? e.message : "That didn't work. Try again."); };
const priceLabel = (inr: number) => (inr ? `₹${inr}` : "Free");

function JoinButton({ s, host = false }: { s: { can_join: boolean; join_url: string | null; opens_at: string; over: boolean; status: string }; host?: boolean }) {
  if (s.can_join && s.join_url) return <>
    <a href={s.join_url} target="_blank" rel="noreferrer"><Button size="sm" variant="primary" icon={<Video className="h-3.5 w-3.5" />}>Join session</Button></a>
    <RoomTip host={host} className="basis-full" />
  </>;
  if (s.status === "scheduled" && !s.over) return <span className="text-xs text-muted">Room opens {timeLabel(s.opens_at)}</span>;
  return null;
}

/* ---------------------------------------------------------------- the student's side */
/** What registering costs this student: free, covered by their Pro this week, or the mentor's price. */
const cost = (s: GroupSessionRow) => (!s.price_inr ? "free" : s.pro_free ? "pro" : "paid");

function RegisterDialog({ s, onClose }: { s: GroupSessionRow | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [doubt, setDoubt] = useState("");
  const register = useMutation({
    mutationFn: async () => {
      const r = await api.takeSeat(s!.id, doubt.trim());
      if (r.checkout) await pay(r.checkout);
      return r;
    },
    onSuccess: () => { toast.success("You're registered. Your doubt is in the mentor's queue."); setDoubt(""); onClose(); },
    onError: failed,
    onSettled: () => qc.invalidateQueries({ queryKey: ["group-sessions"] }),
  });
  if (!s) return null;
  const how = cost(s);
  return (
    <Dialog open={!!s} onClose={onClose} title={s.topic || `Master session with ${s.mentor.split(" ")[0]}`} subtitle={`${s.mentor} · ${whenLabel(s.starts_at)} · ${s.minutes} min`}>
      <div className="space-y-3">
        {s.description && <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-fg-soft">{s.description}</p>}
        <div>
          <Label>The doubt you want answered</Label>
          <Textarea rows={4} value={doubt} onChange={(e) => setDoubt(e.target.value)} maxLength={600}
            placeholder="e.g. Why is torque r × F and not F × r? I get the direction wrong in every problem." />
          <p className="mt-1 text-[11.5px] text-muted">The mentor sees every registered student's doubt before the session and answers them in turn. Others hear the answers, not your name.</p>
        </div>
        <div className="flex items-center gap-3 border border-line bg-bg-soft p-3 text-sm">
          <span className="min-w-0 flex-1">{how === "free" ? <b>Free session</b> : how === "pro" ? <><b>Included in your Pro</b> this week <span className="text-muted">(₹{s.price_inr} otherwise)</span></> : <><b>₹{s.price_inr}</b> a seat</>}</span>
          <Button variant="primary" loading={register.isPending} onClick={() => register.mutate()}>{how === "paid" ? `Pay ₹${s.price_inr} and register` : "Register"}</Button>
        </div>
        {how === "paid" && <p className="text-[11.5px] text-muted">Leave up to 12 hours before for a full refund. If the mentor cancels, you're always refunded.</p>}
      </div>
    </Dialog>
  );
}

function StudentSession({ s, onRegister }: { s: GroupSessionRow; onRegister: () => void }) {
  const qc = useQueryClient();
  const leave = useMutation({ mutationFn: () => api.leaveSeat(s.id), onSuccess: () => { qc.invalidateQueries({ queryKey: ["group-sessions"] }); toast.success("You've left the session"); }, onError: failed });
  const full = s.taken >= s.seats;
  const how = cost(s);
  return (
    <Card className={cn("p-4", s.seated && "border-fg")}>
      <div className="flex flex-wrap items-start gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center border border-line-strong"><Presentation className="h-5 w-5" /></div>
        <div className="min-w-0 flex-1 basis-48">
          <div className="font-semibold">{s.topic || "Open doubt session"}</div>
          <div className="text-[13px] text-muted">{s.mentor} · {s.credential}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="font-medium text-fg-soft">{whenLabel(s.starts_at)}</span><span>{s.minutes} min</span><span>{s.taken}/{s.seats} seats</span>
            <Badge>{how === "pro" && !s.seated ? "Included in Pro" : priceLabel(s.price_inr)}</Badge>
            {s.status === "cancelled" && <Badge tone="bad">Cancelled by the mentor</Badge>}
            {s.status === "done" && <Badge tone="ok">Held</Badge>}
            {s.seated && s.status === "scheduled" && <Badge tone="accent">Registered</Badge>}
            {s.seat_status === "held" && <Badge tone="warn">Payment not finished</Badge>}
          </div>
          {s.description && <p className="mt-2 line-clamp-2 text-[13px] text-fg-soft">{s.description}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {s.seated ? <>
            <JoinButton s={s} />
            {s.status === "scheduled" && !s.can_join && <Button size="sm" variant="ghost" loading={leave.isPending} onClick={() => leave.mutate()} icon={<X className="h-3.5 w-3.5" />}>Leave</Button>}
          </> : s.status === "scheduled" && !s.over && (
            <Button size="sm" variant="primary" disabled={full && s.seat_status !== "held"} onClick={onRegister}>
              {s.seat_status === "held" ? "Finish payment" : full ? "Full" : how === "paid" ? `Register · ₹${s.price_inr}` : "Register"}
            </Button>
          )}
        </div>
      </div>
      {s.seated && s.my_doubt && <p className="mt-2 flex gap-1.5 text-[13px] text-fg-soft"><MessageCircleQuestion className="mt-0.5 h-4 w-4 shrink-0" />{s.my_doubt}{s.answered && <Badge tone="ok" className="ml-1">answered</Badge>}</p>}
      {s.notes && <p className="mt-2 whitespace-pre-wrap border border-line bg-bg-soft p-3 text-[13px]"><b>Mentor's notes:</b> {s.notes}</p>}
    </Card>
  );
}

/** Master sessions with mentors for the student's exam: free ones, paid ones at the mentor's price, and (when the server
    sets per_week) paid sessions included with Pro. */
export function StudentSessions() {
  const { data } = useQuery({ queryKey: ["group-sessions"], queryFn: api.groupSessions, refetchInterval: 60_000 });
  const [registering, setRegistering] = useState<GroupSessionRow | null>(null);
  if (!data) return <Skeleton className="h-48" />;
  const mine = data.sessions.filter((s) => s.seated);
  const open = data.sessions.filter((s) => !s.seated && s.status === "scheduled" && !s.over);
  return (
    <div className="space-y-4">
      <Card className="flex flex-col gap-2 p-4 text-[13px] sm:flex-row sm:items-center">
        <Presentation className="h-5 w-5 shrink-0" />
        <span className="min-w-0 flex-1 text-fg-soft">Live sessions with mentors who cleared {data.exam_label ?? "your exam"}: bring your doubt, they answer it on video. Each mentor sets the price; some are free.
          {data.per_week > 0 && ` ${data.pro ? "Your Pro covers" : "Pro covers"} ${data.per_week} paid session${data.per_week === 1 ? "" : "s"} a week.`}</span>
      </Card>
      {mine.length > 0 && (
        <div className="space-y-2.5">
          <div className="text-sm font-semibold">Registered</div>
          {mine.map((s) => <StudentSession key={s.id} s={s} onRegister={() => setRegistering(s)} />)}
        </div>
      )}
      <div className="space-y-2.5">
        <div className="text-sm font-semibold">{mine.length ? "More coming up" : "Coming up"}</div>
        {open.length ? open.map((s) => <StudentSession key={s.id} s={s} onRegister={() => setRegistering(s)} />)
          : mine.length ? <p className="text-sm text-muted">You're in every session posted so far. Mentors post more a week or two ahead.</p>
            : <EmptyState icon={<Users className="h-6 w-6" />} title="No master sessions posted yet" body="Mentors for your exam post them a week or two ahead. Check back soon." />}
      </div>
      <RegisterDialog s={registering} onClose={() => setRegistering(null)} />
    </div>
  );
}

/* ---------------------------------------------------------------- the mentor's side */
function HostedRow({ s }: { s: HostedSession }) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["hosting"] });
  const [notes, setNotes] = useState("");
  const answered = useMutation({ mutationFn: (v: { seat: number; answered: boolean }) => api.markAnswered(s.id, v.seat, v.answered), onSuccess: refresh, onError: failed });
  const held = useMutation({ mutationFn: () => api.markHeld(s.id, notes.trim()), onSuccess: () => { refresh(); qc.invalidateQueries({ queryKey: ["earnings"] }); toast.success("Marked held. Thank you!"); }, onError: failed });
  const cancel = useMutation({ mutationFn: () => api.cancelSession(s.id), onSuccess: () => { refresh(); toast.success("Cancelled. Registered students are told, and paid seats refunded."); }, onError: failed });
  return (
    <div className="border border-line bg-bg-soft p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{s.topic || "Master session"}</span>
        <Badge>{priceLabel(s.price_inr)}</Badge>
        {s.status === "done" && <Badge tone="ok">Held</Badge>}
        <span className="flex-1" />
        <JoinButton s={s} host />
        {s.status === "scheduled" && !s.can_join && !s.over && !s.needs_marking && (
          <Button size="sm" variant="ghost" loading={cancel.isPending} onClick={() => { if (confirm("Cancel this session? Registered students are told and paid seats are refunded.")) cancel.mutate(); }}>Cancel</Button>
        )}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        <span className="font-medium text-fg-soft">{whenLabel(s.starts_at)}</span><span>{s.minutes} min</span>
        <span>{s.registered} registered of {s.seats}</span>{s.earning_inr > 0 && <span>you earn ₹{s.earning_inr}</span>}
      </div>
      {s.description && <p className="mt-2 line-clamp-2 text-[13px] text-fg-soft">{s.description}</p>}
      {s.queue.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {s.queue.map((q) => (
            <li key={q.id}>
              <button type="button" onClick={() => answered.mutate({ seat: q.id, answered: !q.answered })} className="flex items-start gap-2 text-left text-[13.5px]">
                <span className={cn("mt-0.5 grid h-4 w-4 shrink-0 place-items-center border", q.answered ? "border-ok bg-ok text-white" : "border-line-strong")}>{q.answered && <Check className="h-3 w-3" />}</span>
                <span className={cn(q.answered && "text-muted line-through")}><b className="font-medium">{q.student}:</b> {q.doubt || <i className="text-muted">no doubt written</i>}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {s.needs_marking && (
        <div className="mt-3 space-y-2 border border-fg p-3">
          <div className="text-[13px] font-semibold">Did it happen? Mark it held, with notes for the students who came</div>
          <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={3000} placeholder="What you covered and one thing everyone should practise." />
          <Button size="sm" variant="primary" loading={held.isPending} onClick={() => held.mutate()}>Mark held</Button>
        </div>
      )}
      {s.notes && <p className="mt-2 text-[13px] text-fg-soft"><b>Your notes:</b> {s.notes}</p>}
    </div>
  );
}

/** For an approved mentor: post master sessions at their own price and work through each one's doubt queue. */
export function HostSessions() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["hosting"], queryFn: api.hosting, refetchInterval: 60_000 });
  const [f, setF] = useState({ when: "", topic: "", description: "", minutes: "60", seats: "25", price: "0", repeat: "1" });
  const price = Number(f.price), seats = Number(f.seats);
  const post = useMutation({
    mutationFn: () => api.scheduleSessions({ starts_at: new Date(f.when).toISOString(), topic: f.topic.trim(), description: f.description.trim(),
      minutes: Number(f.minutes), seats, price_inr: price, repeat_weeks: Number(f.repeat) }),
    onSuccess: (made) => { qc.invalidateQueries({ queryKey: ["hosting"] }); setF({ ...f, when: "", topic: "", description: "", repeat: "1" }); toast.success(`${made.length} session${made.length === 1 ? "" : "s"} posted. Students can register now.`); },
    onError: failed,
  });
  if (!data) return <Skeleton className="h-40" />;
  const ok = f.when && f.topic.trim().length >= 3 && seats >= 1 && seats <= data.max_seats && price >= 0 && price <= data.max_price_inr;
  const upcoming = data.sessions.filter((s) => s.status === "scheduled");
  const past = data.sessions.filter((s) => s.status === "done").slice(-5).reverse();
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="Post a master session" icon={<CalendarPlus className="h-4 w-4" />}
          subtitle={`A live class for many students, like Google Meet. You set the price per seat (₹0 for free); you keep ${100 - data.commission_pct}% of every paid seat, and Focs pays your share for seats Pro students use.`} />
        <div className="grid gap-3 p-5 sm:grid-cols-2">
          <div className="sm:col-span-2"><Label htmlFor="ms-title">Title</Label><Input id="ms-title" value={f.topic} onChange={set("topic")} maxLength={120} placeholder="e.g. Rotational motion: the 10 problems every JEE paper repeats" /></div>
          <div className="sm:col-span-2"><Label htmlFor="ms-desc" hint="optional">What it covers and who it's for</Label>
            <Textarea id="ms-desc" rows={2} value={f.description} onChange={set("description")} maxLength={2000} placeholder="e.g. For Class 12 students who know the basics. Bring your toughest torque doubt." /></div>
          <div><Label htmlFor="ms-when">When</Label><Input id="ms-when" type="datetime-local" value={f.when} onChange={set("when")} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label htmlFor="ms-min">Length</Label>
              <Select id="ms-min" value={f.minutes} onChange={set("minutes")}>{[30, 45, 60, 90, 120, 180].map((n) => <option key={n} value={n}>{n} min</option>)}</Select></div>
            <div><Label htmlFor="ms-rep">Repeat</Label>
              <Select id="ms-rep" value={f.repeat} onChange={set("repeat")}>{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n === 1 ? "Once" : `${n} weeks`}</option>)}</Select></div>
          </div>
          <div><Label htmlFor="ms-seats" hint={`max ${data.max_seats}`}>Seats</Label><Input id="ms-seats" inputMode="numeric" value={f.seats} onChange={(e) => setF({ ...f, seats: e.target.value.replace(/\D/g, "") })} /></div>
          <div><Label htmlFor="ms-price" hint={`₹0 to ₹${data.max_price_inr}`}>Price per seat (₹)</Label><Input id="ms-price" inputMode="numeric" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value.replace(/\D/g, "") })} /></div>
          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <span className="min-w-0 flex-1 basis-48 text-[13px] text-muted">{price ? `Full house: ₹${seats * (price - Math.round((price * data.commission_pct) / 100))} for you.` : "Free sessions are a good way to be found."}</span>
            <Button variant="primary" disabled={!ok} loading={post.isPending} onClick={() => post.mutate()} icon={<CalendarPlus className="h-4 w-4" />}>Post session</Button>
          </div>
        </div>
      </Card>
      <div className="space-y-2.5">
        <div className="text-sm font-semibold">Coming up · {upcoming.length}</div>
        {upcoming.length ? upcoming.map((s) => <HostedRow key={s.id} s={s} />) : <p className="text-sm text-muted">Nothing posted. One a week at a fixed time works best: students plan around it.</p>}
      </div>
      {past.length > 0 && <div className="space-y-2.5"><div className="caps text-[10.5px] font-semibold text-muted">Recently held</div>{past.map((s) => <HostedRow key={s.id} s={s} />)}</div>}
    </div>
  );
}

/** What a mentor has earned (calls and master-session seats, less Focs's share) and what Focs still owes them. */
export function EarningsCard() {
  const { data: e } = useQuery({ queryKey: ["earnings"], queryFn: api.myEarnings });
  if (!e) return <Skeleton className="h-32" />;
  const m = e.month;
  return (
    <Card>
      <CardHeader title="Your earnings" icon={<IndianRupee className="h-4 w-4" />}
        subtitle={`Your calls are ${e.call_price_inr ? `₹${e.call_price_inr}: you keep ₹${e.call_share_inr}` : "free"}. Of every paid master-session seat you keep ${100 - e.commission_pct}%. Focs pays you out by UPI or bank.`} />
      <div className="grid grid-cols-2 gap-px border-t border-line bg-line sm:grid-cols-4">
        {[["This month", `₹${m.earned_inr}`], ["Private calls", `${m.calls} · ₹${m.calls_inr}`], ["Master sessions", `${m.sessions} · ₹${m.sessions_inr}`], ["Owed to you", `₹${e.total.owed_inr}`]].map(([k, v]) => (
          <div key={k} className="bg-panel px-5 py-4">
            <div className="figure text-[26px] tabular-nums">{v}</div><div className="caps mt-1.5 text-[10px] text-muted">{k}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}
