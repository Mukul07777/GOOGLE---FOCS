import { useQuery } from "@tanstack/react-query";
import { Crown, EyeOff, Medal, Trophy } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/common";
import { Card, EmptyState, Segmented, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { LeaderRow } from "@/lib/types";
import { cn, examLabel } from "@/lib/utils";
import { useAuth } from "@/stores/auth";

const PODIUM = [
  { place: 2, height: "h-20", tone: "text-[#cbd5e1]" },
  { place: 1, height: "h-28", tone: "text-warn" },
  { place: 3, height: "h-14", tone: "text-[#d6a77a]" },
];

function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span className={cn("grid shrink-0 place-items-center rounded-full bg-gradient-brand font-semibold text-brand-fg", className)}>
      {name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
    </span>
  );
}

function Row({ r, me }: { r: LeaderRow; me: boolean }) {
  return (
    <div className={cn("flex items-center gap-3 px-5 py-3", me && "bg-accent-soft")}>
      <span className="w-8 text-center font-mono text-sm font-semibold tabular-nums text-muted">{r.rank}</span>
      <Avatar name={r.name} className="h-8 w-8 text-xs" />
      <span className="min-w-0 flex-1 truncate text-sm font-medium">{r.name}{me && <span className="text-muted"> (you)</span>}</span>
      <span className="hidden text-xs tabular-nums text-muted sm:block">{r.correct}/{r.answered} · {r.accuracy}%</span>
      <span className="w-20 text-right font-semibold tabular-nums">{r.xp.toLocaleString()} <span className="text-xs font-normal text-muted">XP</span></span>
    </div>
  );
}

export default function Leaderboard() {
  const user = useAuth((s) => s.user);
  const [period, setPeriod] = useState<"week" | "all">("week");
  const [scope, setScope] = useState<"exam" | "everyone">("exam");
  const { data, isLoading } = useQuery({ queryKey: ["leaderboard", period, scope], queryFn: () => api.leaderboard(period, scope) });
  const top3 = data?.top.slice(0, 3) ?? [];
  const meInTop = data?.me && data.top.some((r) => r.user_id === data.me!.user_id);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageHeader eyebrow="Compete" title="Leaderboard"
        subtitle="Every question you answer — practice, pop quizzes, rooms and mocks — earns XP. “This week” counts the last 7 days."
        actions={
          <>
            <Segmented size="sm" value={period} onChange={setPeriod} options={[{ value: "week", label: "This week" }, { value: "all", label: "All time" }]} />
            <Segmented size="sm" value={scope} onChange={setScope} options={[{ value: "exam", label: examLabel(user?.exam_target) }, { value: "everyone", label: "Everyone" }]} />
          </>
        } />

      {isLoading && <Skeleton className="h-64" />}
      {data && !data.top.length && (
        <Card><EmptyState className="py-14" icon={<Trophy className="h-6 w-6" />} title="No one on the board yet"
          body="Answer a pop quiz, a practice set or a mock to be the first." /></Card>
      )}

      {top3.length > 0 && (
        <Card className="noise relative overflow-hidden px-6 pb-0 pt-8">
          <div className="relative mx-auto grid max-w-md grid-cols-3 items-end gap-3">
            {PODIUM.map(({ place, height, tone }) => {
              const r = top3[place - 1];
              return (
                <div key={place} className="flex flex-col items-center text-center">
                  {r ? (
                    <>
                      {place === 1 && <Crown className="mb-1 h-5 w-5 text-warn" />}
                      <Avatar name={r.name} className={cn(place === 1 ? "h-14 w-14 text-base" : "h-11 w-11 text-sm", r.user_id === user?.id && "ring-2 ring-accent ring-offset-2 ring-offset-bg")} />
                      <div className="mt-2 w-full truncate text-sm font-semibold">{r.name}</div>
                      <div className="text-xs tabular-nums text-muted">{r.xp.toLocaleString()} XP</div>
                    </>
                  ) : <div className="h-11" />}
                  <div className={cn("mt-3 grid w-full place-items-center rounded-t-xl bg-elev-2", height)}>
                    <Medal className={cn("h-6 w-6", tone)} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {data && data.top.length > 0 && (
        <Card className="overflow-hidden">
          <div className="divide-y divide-line">
            {data.top.map((r) => <Row key={r.user_id} r={r} me={r.user_id === user?.id} />)}
          </div>
          {data.me && !meInTop && (
            <div className="border-t-2 border-dashed border-line"><Row r={data.me} me /></div>
          )}
        </Card>
      )}

      <p className="text-center text-xs text-muted">
        {data?.xp_rule}. Names show as first name + initial.{" "}
        {data?.hidden
          ? <>You're hidden from leaderboards — <Link to="/app/settings" className="text-accent hover:underline">show me</Link>.</>
          : <>Don't want to appear? <Link to="/app/settings" className="inline-flex items-center gap-1 text-accent hover:underline"><EyeOff className="h-3 w-3" />Hide me</Link></>}
      </p>
    </div>
  );
}
