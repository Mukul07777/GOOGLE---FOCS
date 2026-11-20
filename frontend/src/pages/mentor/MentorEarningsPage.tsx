import { useQuery } from "@tanstack/react-query";
import { Banknote, Wallet } from "lucide-react";
import { PageHeader } from "@/components/common";
import { EarningsCard } from "@/components/GroupSessions";
import { ApprovedOnly } from "@/components/MentorShell";
import { Card, CardHeader, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

/** All time: what the mentor has earned, from what, and what Focs has paid them so far. */
function AllTime() {
  const { data: e } = useQuery({ queryKey: ["earnings"], queryFn: api.myEarnings });
  if (!e) return <Skeleton className="h-64" />;
  const t = e.total;
  return (
    <>
      <Card>
        <CardHeader title="All time" icon={<Wallet className="h-4 w-4" />}
          subtitle="Counted when a call is done or a session is marked held. Refunded seats and cancelled calls don't count." />
        <div className="grid grid-cols-2 gap-px border-t border-line bg-line sm:grid-cols-4">
          {[["Earned", `₹${t.earned_inr}`], ["Private calls", `${t.calls} · ₹${t.calls_inr}`], ["Master sessions", `${t.sessions} · ₹${t.sessions_inr}`], ["Paid to you", `₹${t.paid_out_inr}`]].map(([k, v]) => (
            <div key={k} className="bg-panel px-5 py-4">
              <div className="figure text-[26px] tabular-nums">{v}</div><div className="caps mt-1.5 text-[10px] text-muted">{k}</div>
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <CardHeader title="Payouts" icon={<Banknote className="h-4 w-4" />}
          subtitle={t.owed_inr ? `Focs owes you ₹${t.owed_inr}. Payouts go by UPI or bank transfer at the start of each month.` : "You're all paid up."} />
        <div className="mt-3 border-t border-line">
          {e.payouts.map((p, i) => (
            <div key={i} className="flex items-center gap-3 border-b border-line px-5 py-3.5 last:border-b-0">
              <span className="w-32 shrink-0 text-sm text-muted">{formatDate(p.created_at)}</span>
              <span className="min-w-0 flex-1 truncate text-sm">{p.note || "Payout"}</span>
              <span className="text-sm font-semibold tabular-nums">₹{p.amount_inr}</span>
            </div>
          ))}
          {!e.payouts.length && <p className="px-5 py-6 text-sm text-muted">No payouts yet. Your first one comes after your first paid call or session.</p>}
        </div>
      </Card>
    </>
  );
}

/** The mentor's money: this month, all time, and payouts. */
export default function MentorEarningsPage() {
  return (
    <ApprovedOnly>
      <div className="mx-auto max-w-4xl space-y-5">
        <PageHeader eyebrow="Earnings" title="What you've earned"
          subtitle="You set your own prices. Focs keeps a share of each payment for payments and the platform, and pays you the rest. When a Pro student uses their included session, Focs pays your share." />
        <EarningsCard />
        <AllTime />
      </div>
    </ApprovedOnly>
  );
}
