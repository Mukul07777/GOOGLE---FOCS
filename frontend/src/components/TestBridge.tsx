import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, BookOpen, Check, CircleDashed, Eye, Loader2, Map as MapIcon, RotateCcw, Sparkles, Target, Users } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, ProgressBar } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { Feeling, GapMap, GapRow, GapStep, MockDetail, WarmupCard } from "@/lib/types";
import { cn, subjectColor } from "@/lib/utils";

/* ================================================================== while the paper is written */

/** What Focs is doing right now, in plain words: the wait is the AI writing and checking, not a frozen page. */
function Stages({ progress }: { progress: number }) {
  const assembling = progress >= 95;  // (writing and checking run side by side, question by question)
  const stages: [string, "done" | "now" | "next"][] = [
    ["Writing fresh questions on your chapters", assembling ? "done" : "now"],
    ["A second AI re-solves every one; any it disagrees with is thrown out", assembling ? "done" : "now"],
    ["Putting your paper together", assembling ? "now" : "next"],
  ];
  return (
    <ol className="mt-5 space-y-2 text-left text-[13px]">
      {stages.map(([label, state]) => (
        <li key={label} className={cn("flex items-start gap-2.5", state === "next" && "text-muted")}>
          {state === "done" ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
            : state === "now" ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-accent" />
              : <CircleDashed className="mt-0.5 h-4 w-4 shrink-0" />}
          <span>{label}</span>
        </li>
      ))}
    </ol>
  );
}

function ChapterCard({ card, testId, onRated }: { card: WarmupCard; testId: number; onRated: () => void }) {
  const qc = useQueryClient();
  const [shown, setShown] = useState<Record<number, boolean>>({});
  const rate = useMutation({
    mutationFn: (felt: Feeling) => api.mockFeeling(testId, { subject: card.subject, chapter: card.chapter, felt }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["warmup", testId] }); onRated(); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't save that."),
  });
  return (
    <motion.div key={card.chapter} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="text-left">
      <Badge dot={subjectColor(card.subject)}>{card.subject}</Badge>
      <h2 className="mt-2 text-xl font-semibold tracking-tight">{card.chapter}</h2>
      {!!card.topics.length && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {card.topics.map((t) => <span key={t} className="rounded-full border border-line bg-bg-soft px-2.5 py-1 text-[12px] text-fg-soft">{t}</span>)}
        </div>
      )}
      {!!card.points.length && (
        <div className="mt-4">
          <div className="text-[11.5px] font-semibold uppercase tracking-[0.12em] text-muted">Key points</div>
          <ul className="mt-1.5 space-y-1.5">
            {card.points.map((p) => (
              <li key={p} className="flex gap-2 text-[13.5px]"><Sparkles className="mt-1 h-3.5 w-3.5 shrink-0 text-accent" /><Markdown className="min-w-0 [&_p]:my-0">{p}</Markdown></li>
            ))}
          </ul>
        </div>
      )}
      {!!card.check.length && (
        <div className="mt-4 space-y-2">
          <div className="text-[11.5px] font-semibold uppercase tracking-[0.12em] text-muted">Quick check</div>
          {card.check.map((c, i) => (
            <div key={c.q} className="rounded-xl border border-line bg-bg-soft px-3.5 py-2.5 text-[13.5px]">
              <Markdown className="[&_p]:my-0">{c.q}</Markdown>
              {shown[i] ? <Markdown className="mt-1.5 font-medium text-ok [&_p]:my-0">{c.a}</Markdown>
                : <button onClick={() => setShown({ ...shown, [i]: true })} className="mt-1 inline-flex items-center gap-1 text-[12.5px] font-medium text-accent hover:underline"><Eye className="h-3.5 w-3.5" />Think, then show the answer</button>}
            </div>
          ))}
        </div>
      )}
      {!card.points.length && !card.check.length && card.topics.length > 0 && (
        <p className="mt-3 text-[13px] text-muted">Pick one topic above and say its main idea or formula to yourself before the paper opens.</p>
      )}
      <div className="mt-5 rounded-xl border border-line bg-elev/60 p-3.5">
        <div className="text-[13px] font-medium">How ready do you feel for this chapter?</div>
        <div className="mt-2 flex flex-wrap gap-2">
          {([["sure", "I've got this"], ["shaky", "Not sure yet"]] as const).map(([v, label]) => (
            <Button key={v} size="sm" variant={card.felt === v ? (v === "sure" ? "success" : "danger") : "secondary"}
              loading={rate.isPending && rate.variables === v} onClick={() => rate.mutate(v)}>{label}</Button>
          ))}
        </div>
        <p className="mt-2 text-[11.5px] text-muted">After the test, your gap map puts this next to what the test finds.</p>
      </div>
    </motion.div>
  );
}

/** The preparing screen: progress, what the AI is doing, and the chapters to look over meanwhile. */
export function Warmup({ test }: { test: MockDetail }) {
  const { data } = useQuery({ queryKey: ["warmup", test.id], queryFn: () => api.mockWarmup(test.id), staleTime: Infinity });
  const [i, setI] = useState(0);
  const cards = data?.cards ?? [];
  const card = cards[Math.min(i, cards.length - 1)];
  const rated = cards.filter((c) => c.felt).length;
  useEffect(() => { if (i >= cards.length && cards.length) setI(cards.length - 1); }, [cards.length, i]);

  return (
    <div className="mx-auto grid max-w-5xl gap-5 lg:grid-cols-[0.85fr_1.15fr]">
      <Card className="h-fit p-6 text-center lg:sticky lg:top-6">
        <Loader2 className="mx-auto h-7 w-7 animate-spin text-accent" />
        <h1 className="mt-3 text-[24px]">Preparing your paper</h1>
        <ProgressBar value={test.progress} className="mx-auto mt-4 max-w-xs" />
        <div className="mt-1.5 text-xs tabular-nums text-muted">{test.progress}%</div>
        <Stages progress={test.progress} />
        <p className="mt-5 border-t border-line pt-4 text-left text-[12.5px] leading-relaxed text-muted">
          Why the wait: each question is written by one AI and re-solved by another, about 10–15 a minute. It opens on its own when ready,
          and you can leave: it stays in your list of tests.
        </p>
      </Card>

      {cards.length > 0 ? (
        <Card className="p-6">
          <div className="mb-4 flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">While you wait · look over what's coming</div>
              <div className="mt-0.5 text-xs text-muted">Chapter {Math.min(i, cards.length - 1) + 1} of {cards.length} · {rated} rated</div>
            </div>
            <Button size="icon-sm" variant="ghost" aria-label="Previous chapter" disabled={i === 0} onClick={() => setI(i - 1)}><ArrowLeft className="h-4 w-4" /></Button>
            <Button size="icon-sm" variant="ghost" aria-label="Next chapter" disabled={i >= cards.length - 1} onClick={() => setI(i + 1)}><ArrowRight className="h-4 w-4" /></Button>
          </div>
          <div className="mb-4 flex gap-1">
            {cards.map((c, n) => (
              <button key={c.subject + c.chapter} aria-label={c.chapter} onClick={() => setI(n)}
                className={cn("h-1.5 flex-1 rounded-full transition", n === i ? "bg-accent" : c.felt ? "bg-ok/60" : "bg-elev-2")} />
            ))}
          </div>
          {card && <ChapterCard key={card.subject + card.chapter} card={card} testId={test.id} onRated={() => setI((n) => Math.min(n + 1, cards.length - 1))} />}
        </Card>
      ) : (
        <Card className="grid place-items-center p-8 text-center text-sm text-muted">{data ? "Your paper will open here when it's ready." : <Loader2 className="h-5 w-5 animate-spin" />}</Card>
      )}
    </div>
  );
}

/* ================================================================== after the test */
const LEVEL = {
  strong: { label: "Strong", bar: "bg-ok", text: "text-ok" },
  shaky: { label: "Shaky", bar: "bg-warn", text: "text-warn" },
  gap: { label: "Gap", bar: "bg-bad", text: "text-bad" },
  untried: { label: "Too few", bar: "bg-elev-2", text: "text-muted" },
} as const;

function Row({ r }: { r: GapRow }) {
  const l = LEVEL[r.level];
  return (
    <div className="px-5 py-3">
      <div className="flex items-center gap-2 text-[13.5px]">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: subjectColor(r.subject) }} />
        {r.chapter_id ? <Link to={`/app/prep?chapter=${encodeURIComponent(r.chapter_id)}`} className="min-w-0 flex-1 truncate font-medium hover:text-accent">{r.chapter}</Link>
          : <span className="min-w-0 flex-1 truncate font-medium">{r.chapter}</span>}
        {r.flag === "blind_spot" && <Badge tone="bad">Blind spot</Badge>}
        {r.flag === "hidden_strength" && <Badge tone="ok">Better than you thought</Badge>}
        <span className={cn("w-14 shrink-0 text-right text-xs font-semibold", l.text)}>{l.label}</span>
      </div>
      <div className="mt-1.5 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-elev-2"><div className={cn("h-full rounded-full", l.bar)} style={{ width: `${Math.max(4, r.share)}%` }} /></div>
        <span className="w-44 shrink-0 text-right text-[11.5px] tabular-nums text-muted">
          {r.correct}/{r.attempted} right{r.attempted < r.asked ? ` · ${r.asked - r.attempted} left blank` : ""}{r.felt ? ` · felt ${r.felt === "sure" ? "sure" : "shaky"}` : ""}
        </span>
      </div>
    </div>
  );
}

const STEP_ICON = { revise: BookOpen, retest: Target, senior: Users, redo: RotateCcw, stretch: Sparkles } as const;

function Step({ s, n }: { s: GapStep; n: number }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const retest = useMutation({
    mutationFn: () => api.createChapterTest(s.subject!, s.chapters!, s.count ?? 10),
    onSuccess: (t) => { qc.invalidateQueries({ queryKey: ["mocks"] }); navigate(`/app/mock/${t.id}`); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start that test."),
  });
  const Icon = STEP_ICON[s.kind];
  const action = {
    revise: <Link to={`/app/prep?chapter=${encodeURIComponent(s.chapter_id ?? "")}`}><Button size="sm" variant="primary">Open notes</Button></Link>,
    retest: <Button size="sm" variant="primary" loading={retest.isPending} onClick={() => retest.mutate()}>Start it</Button>,
    senior: <Link to={`/app/campus?tab=ask&subject=${encodeURIComponent(s.subject ?? "")}&chapter=${encodeURIComponent(s.chapter ?? "")}`}><Button size="sm" variant="primary">Ask a senior</Button></Link>,
    redo: <Link to="/app/practice"><Button size="sm" variant="primary">Open redo queue</Button></Link>,
    stretch: <Link to="/app/mock"><Button size="sm" variant="primary">Pick a test</Button></Link>,
  }[s.kind];
  return (
    <li className="flex gap-3 rounded-xl border border-line bg-bg-soft p-4">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-sm font-semibold text-accent">{n}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-[14px] font-semibold"><Icon className="h-4 w-4 shrink-0 text-accent" />{s.title}</div>
        <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{s.detail}</p>
        <div className="mt-2.5">{action}</div>
      </div>
    </li>
  );
}

/** The result turned into a plan: each chapter's standing (and how sure the student felt), then three next steps. */
export function GapMapCard({ map }: { map: GapMap }) {
  return (
    <Card>
      <CardHeader title="Your gap map" icon={<MapIcon className="h-4 w-4" />} subtitle={map.summary} />
      <div className="grid grid-cols-1 gap-0 md:grid-cols-[1.1fr_1fr]">
        <div className="max-h-[22rem] divide-y divide-line overflow-y-auto border-line md:border-r">
          {map.chapters.map((r) => <Row key={r.subject + r.chapter} r={r} />)}
        </div>
        <div className="p-5">
          <div className="mb-3 text-[11.5px] font-semibold uppercase tracking-[0.12em] text-muted">Your next {map.steps.length === 1 ? "step" : `${map.steps.length} steps`}</div>
          <ol className="space-y-2.5">{map.steps.map((s, n) => <Step key={s.kind} s={s} n={n + 1} />)}</ol>
        </div>
      </div>
    </Card>
  );
}
