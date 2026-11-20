import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Compass, ExternalLink, Flag, IndianRupee, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Input, Segmented } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { CallMoney } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { Initials } from "@/pages/Mentors";

const failed = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "That didn't work.");

/** One mentor's earnings with a way to record money sent to them (UPI or bank, outside Focs). */
function PayoutRow({ m }: { m: CallMoney["by_mentor"][number] }) {
  const qc = useQueryClient();
  const [amount, setAmount] = useState("");
  const pay = useMutation({
    mutationFn: () => api.adminPayout(m.id, Number(amount), `Recorded ${new Date().toLocaleDateString("en-IN")}`),
    onSuccess: () => { setAmount(""); qc.invalidateQueries({ queryKey: ["admin-call-money"] }); toast.success("Payout recorded"); },
    onError: failed,
  });
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-line py-2 text-[13px]">
      <span className="min-w-0 flex-1 basis-48"><b>{m.mentor}</b> <span className="text-muted">· {m.calls} calls ₹{m.calls_inr} · {m.sessions} group ₹{m.sessions_inr} · paid ₹{m.paid_out_inr}</span></span>
      <span className={m.owed_inr > 0 ? "font-semibold text-warn" : "text-muted"}>owed ₹{m.owed_inr}</span>
      <Input value={amount} onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))} placeholder="₹" className="h-8 w-20 text-xs" />
      <Button size="sm" variant="secondary" disabled={!Number(amount)} loading={pay.isPending} onClick={() => pay.mutate()}>Paid</Button>
    </div>
  );
}

/** Admin: mentor applications to check against their proof, reported mentor conversations, and the money. */
export function MentorAdmin() {
  const qc = useQueryClient();
  const [status, setStatus] = useState<"pending" | "approved" | "rejected" | "photo">("pending");
  const [notes, setNotes] = useState<Record<number, string>>({});
  const { data: apps } = useQuery({ queryKey: ["admin-mentors", status], queryFn: () => api.adminMentors(status) });
  const { data: reports } = useQuery({ queryKey: ["admin-mentor-reports"], queryFn: api.adminMentorReports });
  const { data: money } = useQuery({ queryKey: ["admin-call-money"], queryFn: api.adminCallMoney });
  const refunded = useMutation({ mutationFn: api.adminRefunded, onSuccess: () => { qc.invalidateQueries({ queryKey: ["admin-call-money"] }); toast.success("Marked refunded"); }, onError: failed });
  const review = useMutation({
    mutationFn: (v: { id: number; approve: boolean }) => api.adminMentorReview(v.id, v.approve, notes[v.id] ?? ""),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["admin-mentors"] }); toast.success(r.status === "approved" ? "Approved: listed for students" : "Rejected"); },
    onError: failed,
  });
  const photo = useMutation({
    mutationFn: (v: { id: number; approve: boolean }) => api.adminMentorPhoto(v.id, v.approve, notes[v.id] ?? ""),
    onSuccess: (_, v) => { qc.invalidateQueries({ queryKey: ["admin-mentors"] }); toast.success(v.approve ? "Photo approved: it's on their card now" : "Photo rejected: the mentor is told why"); },
    onError: failed,
  });
  const proof = useMutation({
    mutationFn: async (id: number) => {
      const tab = window.open("", "_blank");
      try { const url = await api.adminMentorProof(id); if (tab) tab.location.href = url; } catch (e) { tab?.close(); throw e; }
    },
    onError: failed,
  });
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="Mentor applications" icon={<Compass className="h-4 w-4" />} subtitle="Check the proof matches the claim. The proof file is deleted once you decide." />
        <div className="px-5 pb-3 pt-3">
          <Segmented size="sm" value={status} onChange={setStatus} options={[{ value: "pending", label: "Waiting" }, { value: "approved", label: "Approved" }, { value: "rejected", label: "Rejected" }, { value: "photo", label: "New photos" }]} />
        </div>
        <div className="divide-y divide-line">
          {!apps?.length && <p className="px-5 py-6 text-sm text-muted">Nothing here.</p>}
          {apps?.map((a) => (
            <div key={a.id} className="flex flex-col gap-3 px-5 py-4 lg:flex-row lg:items-center">
              <div className="flex flex-col items-center gap-1">
                <Initials name={a.name} photo={a.photo_pending ?? a.photo} className="h-16 w-16 text-lg" />
                {a.photo_pending && <span className="text-[10px] font-medium text-warn">New photo</span>}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 font-semibold">{a.name}<Badge>{a.exam_label}</Badge><span className="text-xs font-normal text-muted">{a.email}{a.phone && ` · ${a.phone}`} · sent {timeAgo(a.submitted_at ?? a.created_at)}</span></div>
                <div className="text-[13px]"><b>{a.credential}</b> · {a.institution}</div>
                {a.qualification && <div className="text-[13px]">Qualification: {a.qualification}</div>}
                {a.experience && <div className="text-xs text-muted">Experience: {a.experience}</div>}
                <div className="text-xs text-muted">Calls at {a.call_price_inr ? `₹${a.call_price_inr}` : "no charge"} · up to {a.capacity} student{a.capacity === 1 ? "" : "s"}</div>
                {a.headline && <div className="text-xs text-muted">{a.headline}</div>}
                {a.review_note && <div className="text-xs text-muted">Note: {a.review_note}</div>}
              </div>
              {status === "pending" && (
                <div className="flex flex-wrap items-center gap-2">
                  <Button size="sm" variant="secondary" disabled={!a.has_proof} loading={proof.isPending && proof.variables === a.id} onClick={() => proof.mutate(a.id)} icon={<ExternalLink className="h-3.5 w-3.5" />}>Proof</Button>
                  <Input value={notes[a.id] ?? ""} onChange={(e) => setNotes({ ...notes, [a.id]: e.target.value })} placeholder="Note (shown if rejected)" className="h-9 w-full text-xs sm:w-48" />
                  <Button size="sm" variant="success" onClick={() => review.mutate({ id: a.id, approve: true })} icon={<Check className="h-3.5 w-3.5" />}
                    title={a.photo_pending ? "Approves the photo too" : undefined}>Approve</Button>
                  <Button size="sm" variant="danger" onClick={() => review.mutate({ id: a.id, approve: false })} icon={<X className="h-3.5 w-3.5" />}>Reject</Button>
                  {a.photo_pending && <Button size="sm" variant="secondary" onClick={() => photo.mutate({ id: a.id, approve: false })} icon={<X className="h-3.5 w-3.5" />}>Reject photo only</Button>}
                </div>
              )}
              {status !== "pending" && a.photo_pending && (
                <div className="flex flex-wrap items-center gap-2">
                  <Input value={notes[a.id] ?? ""} onChange={(e) => setNotes({ ...notes, [a.id]: e.target.value })} placeholder="Reason (shown if rejected)" className="h-9 w-full text-xs sm:w-48" />
                  <Button size="sm" variant="success" onClick={() => photo.mutate({ id: a.id, approve: true })} icon={<Check className="h-3.5 w-3.5" />}>Photo OK</Button>
                  <Button size="sm" variant="danger" onClick={() => photo.mutate({ id: a.id, approve: false })} icon={<X className="h-3.5 w-3.5" />}>Reject photo</Button>
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
      {money && (
        <Card>
          <CardHeader title="Mentor calls, master sessions and Pro" icon={<IndianRupee className="h-4 w-4" />}
            subtitle={`Collected: calls ₹${money.calls_revenue_inr.toLocaleString("en-IN")}, master sessions ₹${money.sessions_revenue_inr.toLocaleString("en-IN")}, Pro ₹${money.pro_revenue_inr.toLocaleString("en-IN")}, mock tests ₹${(money.mocks_revenue_inr ?? 0).toLocaleString("en-IN")}. Focs's ${money.commission_pct}% of calls and seats: ₹${money.focs_share_inr.toLocaleString("en-IN")}. Owed to mentors: ₹${money.owed_to_mentors_inr.toLocaleString("en-IN")}. Send refunds and payouts outside Focs, then record them here.`} />
          <div className="grid gap-5 p-5 md:grid-cols-2">
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Refunds owed</div>
              {money.refunds_due.length ? money.refunds_due.map((r) => (
                <div key={r.id} className="flex items-center gap-2 border-b border-line py-2 text-[13px]">
                  <span className="min-w-0 flex-1">{r.student} · ₹{r.amount_inr} · <span className="font-mono text-xs text-muted">{r.provider_payment_id ?? "test payment"}</span></span>
                  <Button size="sm" variant="secondary" onClick={() => refunded.mutate(r.id)}>Refunded</Button>
                </div>
              )) : <p className="text-sm text-muted">None.</p>}
            </div>
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Mentors: earned and owed</div>
              {money.by_mentor.length ? money.by_mentor.map((m) => <PayoutRow key={m.id} m={m} />) : <p className="text-sm text-muted">Nothing earned yet.</p>}
            </div>
          </div>
        </Card>
      )}
      {!!reports?.length && (
        <Card>
          <CardHeader title="Reported mentor conversations" icon={<Flag className="h-4 w-4" />} subtitle="A mentor reported by a student takes no new students until you deal with it." />
          <div className="divide-y divide-line">
            {reports.map((r) => (
              <details key={r.id} className="px-5 py-4">
                <summary className="cursor-pointer text-sm"><b>{r.mentor}</b> mentoring <b>{r.student}</b> · {r.status} · {r.reports.length} report{r.reports.length === 1 ? "" : "s"}: “{r.reports[r.reports.length - 1].reason}”</summary>
                <div className="mt-3 space-y-1.5 text-[13px]">
                  {r.reports.map((x, i) => <p key={i} className="text-bad">Report from the {x.by} ({timeAgo(x.at)}): {x.reason}</p>)}
                  <p className="text-muted">Goal: {r.goal}</p>
                  {r.messages.map((m, i) => <p key={i}><b>{m.from}{m.kind === "checkin" ? " (check-in)" : ""}:</b> {m.body || "—"} <span className="text-xs text-muted">{timeAgo(m.at)}</span></p>)}
                </div>
              </details>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
