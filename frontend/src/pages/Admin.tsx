import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, IndianRupee, LogOut, Moon, Search, ShieldCheck, Sun, Target, TrendingUp, Users } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Logo, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Input, ProgressBar, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { cn, examLabel, timeAgo } from "@/lib/utils";
import { adminSignedIn, useAdmin } from "@/stores/admin";
import { useTheme } from "@/stores/theme";
import { MentorAdmin } from "@/components/MentorAdmin";

/** ₹1,234 / −₹12 — never "₹-0" for an amount that rounds to zero */
const inr = (n: number, digits = 0) => {
  const rounded = Number(n.toFixed(digits));
  const text = Math.abs(rounded).toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
  return `${rounded < 0 ? "−" : ""}₹${text}`;
};
const calls = (n: number) => `${n.toLocaleString("en-IN")} call${n === 1 ? "" : "s"}`;
const FEATURE_LABEL: Record<string, string> = {
  board_notes: "Board notes", quiz_question: "Pop / room quizzes", checkpoint: "Checkpoints", doubt: "Doubts & Ask AI",
  practice_set: "Practice sets", grade_answer: "Answer grading", revision_sheet: "Revision sheets", flashcards: "Flashcards",
  question_bank: "Writing bank questions", question_verify: "Verifying bank questions", other: "Other",
};

function Kpi({ icon, label, value, sub, tone }: { icon: ReactNode; label: string; value: ReactNode; sub?: ReactNode; tone?: string }) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 text-[13px] text-muted"><span className={cn("grid h-7 w-7 place-items-center rounded-lg bg-elev-2", tone)}>{icon}</span>{label}</div>
      <div className="mt-3 text-[26px] font-semibold leading-none tracking-tight tabular-nums">{value}</div>
      {sub && <div className="mt-1.5 text-xs text-muted">{sub}</div>}
    </Card>
  );
}

const tooltipStyle = { background: "var(--panel)", border: "1px solid var(--line-strong)", borderRadius: 12 };

/** The admin panel: its own sign-in and its own frame, nothing shared with the student app. */
export default function Admin() {
  const token = useAdmin((s) => s.token);
  const username = useAdmin((s) => s.username);
  const signOut = useAdmin((s) => s.signOut);
  const { theme, toggle } = useTheme();
  const qc = useQueryClient();
  if (!token || !adminSignedIn()) return <Navigate to="/admin/login" replace />;

  const leave = () => {
    signOut();
    qc.removeQueries({ queryKey: ["admin-overview"] });
    qc.removeQueries({ queryKey: ["admin-users"] });
  };
  return (
    <div className="min-h-dvh bg-bg">
      <header className="sticky top-0 z-20 border-b border-line bg-bg/80 px-4 pt-[env(safe-area-inset-top)] backdrop-blur sm:px-6">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3">
          <Logo />
          <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent">
            <ShieldCheck className="h-3 w-3" />Admin
          </span>
          <span className="ml-auto hidden truncate text-[13px] text-muted sm:block">{username}</span>
          <button type="button" onClick={toggle} className="ml-auto grid h-10 w-10 shrink-0 place-items-center rounded-lg text-muted sm:ml-0 hover:bg-elev-2 hover:text-fg"
            aria-label="Toggle light / dark theme">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <Button size="sm" variant="ghost" className="shrink-0" onClick={leave} aria-label="Sign out" icon={<LogOut className="h-3.5 w-3.5" />}><span className="hidden min-[400px]:inline">Sign out</span></Button>
        </div>
      </header>
      <main className="space-y-5 px-4 py-6 sm:px-6"><Dashboard /><div className="mx-auto max-w-6xl"><MentorAdmin /></div></main>
    </div>
  );
}

function Dashboard() {
  const [q, setQ] = useState("");
  const { data: o, isLoading, error } = useQuery({ queryKey: ["admin-overview"], queryFn: api.adminOverview, refetchInterval: 60_000 });
  const { data: people } = useQuery({ queryKey: ["admin-users", q], queryFn: () => api.adminUsers(q) });
  if (error && !o) return <div className="mx-auto max-w-6xl rounded-xl border border-bad/25 bg-bad/10 px-4 py-3 text-sm text-bad">{error.message}</div>;
  if (isLoading || !o) return <div className="mx-auto max-w-6xl space-y-4"><Skeleton className="h-24" /><Skeleton className="h-72" /></div>;

  const goalPct = Math.min(100, (100 * o.goal.paying) / Math.max(1, o.goal.target));
  const signupPct = Math.min(100, (100 * o.goal.signups) / Math.max(1, o.goal.target));
  const maxFeature = Math.max(0.0001, ...o.ai_cost.by_feature.map((f) => f.inr));

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHeader title="Business dashboard"
        subtitle={`Updated ${timeAgo(o.generated_at)} · refreshes every minute · costs at list prices (₹${o.ai_cost.usd_inr}/$)`} />

      <Card className="p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold"><Target className="h-4 w-4 text-accent" />Goal: {o.goal.target} customers</div>
            <p className="mt-1 text-xs text-muted">Paying = Pro or Institute plan. Sign-ups include free students.</p>
          </div>
          <Badge tone={o.goal.paying >= o.goal.target ? "ok" : "accent"}>{o.goal.target - o.goal.paying > 0 ? `${o.goal.target - o.goal.paying} to go` : "Goal reached"}</Badge>
        </div>
        <div className="mt-4 space-y-3">
          <div><div className="mb-1 flex justify-between text-xs"><span>Paying customers</span><span className="tabular-nums">{o.goal.paying} / {o.goal.target}</span></div><ProgressBar value={goalPct} /></div>
          <div><div className="mb-1 flex justify-between text-xs"><span>Sign-ups</span><span className="tabular-nums">{o.goal.signups} / {o.goal.target}</span></div><ProgressBar value={signupPct} tone="ok" /></div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi icon={<Users className="h-4 w-4 text-accent" />} label="Students" value={o.users.total.toLocaleString("en-IN")}
          sub={`+${o.users.new_today} today · +${o.users.new_7d} this week · +${o.users.new_30d} in 30 days`} />
        <Kpi icon={<Activity className="h-4 w-4 text-ok" />} label="Active" value={o.users.active.week}
          sub={`${o.users.active.day} today · ${o.users.active.month} in 30 days`} />
        <Kpi icon={<IndianRupee className="h-4 w-4 text-warn" />} label="Monthly revenue (expected)" value={inr(o.revenue.mrr_inr)}
          sub={o.revenue.payments_connected ? `${inr(o.revenue.collected_inr)} collected` : `${o.revenue.pro_users} Pro × ${inr(o.revenue.price_inr)} · payments not connected yet${o.revenue.offer ? ` · launch offer: ${o.revenue.offer.left} of ${o.revenue.offer.places} places left` : ""}`} />
        <Kpi icon={<Bot className="h-4 w-4 text-accent-2" />} label="AI cost (last 30 days)" value={inr(o.ai_cost.last_30d.inr, 2)}
          sub={`${inr(o.ai_cost.total.inr, 2)} all time · ${inr(o.ai_cost.today.inr, 2)} today`
            + (o.ai_cost.budget?.daily_inr ? ` · daily budget ${inr(o.ai_cost.budget.spent_inr)} of ${inr(o.ai_cost.budget.daily_inr)}`
              + (o.ai_cost.budget.reached ? ": reached, free accounts get offline answers until 05:30" : "") : "")} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Kpi icon={<TrendingUp className="h-4 w-4 text-ok" />} label="Margin (30 days)" value={inr(o.margin_30d_inr)} tone={o.margin_30d_inr < 0 ? "text-bad" : undefined}
          sub="expected revenue − AI cost" />
        <Kpi icon={<Bot className="h-4 w-4 text-accent" />} label="AI cost per active student" value={inr(o.ai_cost.per_active_user_30d.inr, 2)} sub="last 30 days" />
        <Kpi icon={<Activity className="h-4 w-4 text-accent-2" />} label="AI calls" value={o.ai_cost.calls.toLocaleString("en-IN")} sub={o.ai_cost.note} />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Sign-ups per day" subtitle="Last 30 days" />
          <div className="h-56 px-2 pb-3">
            <ResponsiveContainer>
              <BarChart data={o.series} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="day" tickFormatter={(d: string) => d.slice(5)} tickLine={false} axisLine={false} interval={4} tick={{ fill: "var(--muted)", fontSize: 11 }} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--elev-2)" }} />
                <Bar dataKey="signups" name="Sign-ups" fill="var(--accent)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <CardHeader title="AI cost per day (₹)" subtitle="Last 30 days, list prices" />
          <div className="h-56 px-2 pb-3">
            <ResponsiveContainer>
              <BarChart data={o.series} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="day" tickFormatter={(d: string) => d.slice(5)} tickLine={false} axisLine={false} interval={4} tick={{ fill: "var(--muted)", fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--elev-2)" }} formatter={(v) => [inr(Number(v), 2), "AI cost"]} />
                <Bar dataKey="cost_inr" name="AI cost" fill="var(--accent-2)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.1fr_1fr]">
        <Card>
          <CardHeader title="Where the AI money goes" subtitle="By feature, all time" />
          <div className="space-y-3 p-5">
            {!o.ai_cost.by_feature.length && <p className="text-sm text-muted">No AI calls recorded yet.</p>}
            {o.ai_cost.by_feature.map((f) => (
              <div key={f.feature}>
                <div className="mb-1 flex justify-between gap-2 text-[13px]">
                  <span>{FEATURE_LABEL[f.feature] ?? f.feature}</span>
                  <span className="tabular-nums text-muted">{calls(f.calls)} · <b className="text-fg">{inr(f.inr, 2)}</b></span>
                </div>
                <ProgressBar value={(100 * f.inr) / maxFeature} />
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="By model" subtitle="Tokens and cost, all time" />
          <div className="divide-y divide-line">
            {o.ai_cost.by_model.map((m) => (
              <div key={m.model} className="flex items-center gap-3 px-5 py-3 text-[13px]">
                <span className="min-w-0 flex-1 truncate font-mono text-xs">{m.model}</span>
                <span className="text-xs tabular-nums text-muted">{calls(m.calls)} · {((m.prompt_tokens + m.completion_tokens) / 1000).toFixed(0)}k tokens</span>
                <span className="w-20 text-right font-semibold tabular-nums">{inr(m.inr, 2)}</span>
              </div>
            ))}
            {!o.ai_cost.by_model.length && <p className="px-5 py-4 text-sm text-muted">No AI calls recorded yet.</p>}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_1.4fr]">
        <Card>
          <CardHeader title="Plans, exams and usage" />
          <div className="space-y-4 p-5 text-[13px]">
            <div className="flex flex-wrap gap-2">
              {Object.entries(o.users.by_plan).map(([p, n]) => <Badge key={p} tone={p === "free" ? "neutral" : "accent"}>{p === "free" ? "Starter" : p}: {n}</Badge>)}
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(o.users.by_exam).sort((a, b) => b[1] - a[1]).map(([e, n]) => <Badge key={e}>{examLabel(e)}: {n}</Badge>)}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {[["Lectures", o.usage.lectures], ["Lectures (30 d)", o.usage.lectures_30d], ["Boards read", o.usage.boards], ["Questions answered", o.usage.questions_answered],
                ["Doubts", o.usage.doubts], ["Mocks taken", o.usage.mocks_taken], ["Rooms live now", o.usage.rooms_live], ["In rooms now", o.usage.people_in_rooms]]
                .map(([k, v]) => (
                  <div key={String(k)} className="rounded-xl border border-line bg-bg-soft px-3 py-2">
                    <div className="text-base font-semibold tabular-nums">{Number(v).toLocaleString("en-IN")}</div>
                    <div className="text-[11.5px] text-muted">{String(k)}</div>
                  </div>
                ))}
            </div>
          </div>
        </Card>
        <Card>
          <CardHeader title="Biggest AI spenders" subtitle="All time — check for abuse or heavy users worth a call" />
          <div className="divide-y divide-line">
            {o.ai_cost.top_users.map((u) => (
              <div key={u.user_id} className="flex items-center gap-3 px-5 py-2.5 text-[13px]">
                <div className="min-w-0 flex-1"><div className="truncate font-medium">{u.name}</div><div className="truncate text-xs text-muted">{u.email}</div></div>
                <Badge>{u.plan ?? "—"}</Badge>
                <span className="text-xs tabular-nums text-muted">{calls(u.calls)}</span>
                <span className="w-16 text-right font-semibold tabular-nums">{inr(u.inr, 2)}</span>
              </div>
            ))}
            {!o.ai_cost.top_users.length && <p className="px-5 py-4 text-sm text-muted">No AI calls recorded yet.</p>}
          </div>
        </Card>
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
          <div className="font-semibold">Students</div>
          <div className="relative w-full max-w-xs">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name or email…" className="h-9 pl-9" />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full whitespace-nowrap text-[13px]">
            <thead className="text-left text-xs text-muted">
              <tr>{["Name", "Email", "Plan", "Exam", "Joined", "Last seen", "Lectures", "AI cost"].map((h) => <th key={h} className="px-5 py-2 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {(people ?? []).map((u) => (
                <tr key={u.id} className="border-t border-line">
                  <td className="px-5 py-2 font-medium">{u.name}</td>
                  <td className="px-5 py-2 text-muted">{u.email}</td>
                  <td className="px-5 py-2"><Badge tone={u.plan === "free" ? "neutral" : "accent"}>{u.plan === "free" ? "Starter" : u.plan}</Badge></td>
                  <td className="px-5 py-2">{examLabel(u.exam)}</td>
                  <td className="px-5 py-2 text-muted">{timeAgo(u.joined)}</td>
                  <td className="px-5 py-2 text-muted">{u.last_seen ? timeAgo(u.last_seen) : "—"}</td>
                  <td className="px-5 py-2 tabular-nums">{u.lectures}</td>
                  <td className="px-5 py-2 tabular-nums">{inr(u.inr, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
