import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowRight, Check, CircleHelp, GitBranch, GraduationCap, PenLine, Search, Sparkles, Target, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/common";
import { Markdown } from "@/components/Markdown";
import { RoughPad } from "@/components/RoughPad";
import { MistakeFingerprintCard, TutorChat, useCheckWorking, WorkingCheckCard } from "@/components/WorkingCheck";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, EmptyState, Input, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { GapCheck, GapLink, GapRetestPart, GapTrace, WorkingCheck } from "@/lib/types";
import { cn, timeAgo } from "@/lib/utils";

/* Root cause: a topic that won't make sense, traced back through the earlier chapters it rests on. The student
   answers one quick question per link; the deepest one they miss is the real gap, fixed with a five-minute lesson. */

const failed = (fallback: string) => (e: unknown) => toast.error(e instanceof ApiError ? e.message : fallback);
const where = (l: GapLink) => (l.cls ? `Class ${l.cls}` : "Your course") + ` · ${l.subject}`;
const STATUS: Record<GapTrace["status"], { label: string; tone: "neutral" | "warn" | "ok" | "accent" }> = {
  checking: { label: "Checking", tone: "neutral" }, found: { label: "Root found", tone: "warn" },
  clear: { label: "Foundations hold", tone: "ok" }, fixed: { label: "Fixed", tone: "ok" },
};

function Options({ check, value, onPick, locked }: { check: GapCheck; value: number | null | undefined; onPick?: (i: number) => void; locked?: boolean }) {
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {check.options.map((o, i) => {
        const right = locked && check.answer === i;
        const wrongPick = locked && value === i && check.answer !== i;
        return (
          <button key={i} type="button" disabled={locked} onClick={() => onPick?.(i)} aria-pressed={value === i}
            className={cn("rounded-xl border px-3 py-2.5 text-left text-[13.5px] transition",
              !locked && (value === i ? "border-fg bg-fg text-bg" : "border-line-strong bg-panel hover:border-fg"),
              right && "border-ok bg-ok/10", wrongPick && "border-bad bg-bad/10", locked && !right && !wrongPick && "border-line opacity-70")}>
            <span className="mr-2 font-semibold">{"ABCD"[i]}.</span><Markdown className="inline [&_p]:inline">{o}</Markdown>
          </button>
        );
      })}
    </div>
  );
}

/** The stuck topic's own questions (before the trace, or again after the fix), answered together. */
function RetestQuestions({ part, picks, onPicks, locked }: {
  part: GapRetestPart; picks: (number | null)[]; onPicks: (p: (number | null)[]) => void; locked: boolean;
}) {
  return (
    <div className="mt-4 space-y-5">
      {part.items.map((item, i) => (
        <div key={i}>
          <div className="flex gap-2 text-[14px]"><span className="font-semibold text-muted">{i + 1}.</span><Markdown>{item.q}</Markdown></div>
          <Options check={item} value={locked ? part.choices?.[i] : picks[i]} locked={locked}
            onPick={(c) => onPicks(picks.map((v, j) => (j === i ? c : v)))} />
          {locked && item.explain && <Markdown className="mt-2 line-clamp-3 text-[12.5px] text-muted">{item.explain}</Markdown>}
        </div>
      ))}
    </div>
  );
}

function Chain({ trace }: { trace: GapTrace }) {
  const qc = useQueryClient();
  const [picks, setPicks] = useState<(number | null)[]>(() => trace.chain.map(() => null));
  const [beforePicks, setBeforePicks] = useState<(number | null)[]>(() => Array(trace.retest?.before.total ?? 0).fill(null));
  const [afterPicks, setAfterPicks] = useState<(number | null)[]>(() => Array(trace.retest?.after.total ?? 0).fill(null));
  const put = (t: GapTrace) => { qc.setQueryData(["gap", t.id], t); qc.invalidateQueries({ queryKey: ["gaps"] }); };
  const submit = useMutation({ mutationFn: () => api.gapAnswers(trace.id, picks, trace.retest ? beforePicks : undefined), onSuccess: put, onError: failed("Couldn't check your answers") });
  const again = useMutation({ mutationFn: () => api.gapAfter(trace.id, afterPicks), onSuccess: put, onError: failed("Couldn't check those") });
  const before = trace.retest?.before;
  const after = trace.retest?.after;
  const lesson = useMutation({ mutationFn: () => api.gapLesson(trace.id), onSuccess: put, onError: failed("Couldn't write the lesson right now") });
  const [pick, setPick] = useState<number | null>(null);
  const recheck = useMutation({ mutationFn: (c: number) => api.gapCheck(trace.id, c), onSuccess: put, onError: failed("Couldn't check that") });
  const checking = trace.status === "checking";
  const root = trace.root !== null ? trace.chain[trace.root] : null;
  // rough work under each check: written while answering, checked step by step once the answers are marked
  const [padFor, setPadFor] = useState<number | null>(null);
  const [works, setWorks] = useState<Record<number, WorkingCheck>>({});
  const padLink = padFor !== null ? trace.chain[padFor] : null;
  const checkWork = useCheckWorking(padLink ? {
    question: padLink.check.q, options: padLink.check.options, answer: padLink.check.answer ?? null,
    chosen: padLink.choice ?? null, chapterId: padLink.chapter_id, solution: padLink.check.explain ?? null,
  } : null);

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-fg text-bg"><Target className="h-5 w-5" /></span>
          <div className="min-w-0">
            <div className="text-[12px] text-muted">You're stuck on</div>
            <div className="truncate text-[17px] font-semibold">{trace.title}</div>
          </div>
          <Badge tone={STATUS[trace.status].tone} className="ml-auto">{STATUS[trace.status].label}</Badge>
        </div>
        {checking && <p className="mt-3 text-[13.5px] text-muted">It rests on these earlier ideas. Answer one quick question for each: the deepest one you miss is your real gap.</p>}
      </Card>

      {before && before.items.length > 0 && (
        <Card className="p-5">
          <div className="text-[15px] font-semibold">First, {trace.title} itself</div>
          <p className="mt-0.5 text-[13px] text-muted">
            {checking ? "Three quick questions, so you can see the difference once the gap is fixed."
              : before.right === null ? "Skipped this time." : `Before the fix: ${before.right} of ${before.total} right.`}
          </p>
          <RetestQuestions part={before} picks={beforePicks} onPicks={setBeforePicks} locked={!checking} />
        </Card>
      )}

      {trace.chain.map((l, i) => (
        <div key={l.chapter_id}>
          <div className="flex justify-center py-1 text-muted"><ArrowDown className="h-4 w-4" /></div>
          <Card className={cn("p-5", trace.root === i && "ring-2 ring-warn")}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge>{where(l)}</Badge>
              <span className="text-[13px] text-muted">{l.name}</span>
              {l.result === "right" && <Badge tone="ok"><Check className="h-3 w-3" /> You have this</Badge>}
              {l.result === "wrong" && <Badge tone={trace.root === i ? "warn" : "bad"}><X className="h-3 w-3" /> {trace.root === i ? "Root gap" : "Shaky"}</Badge>}
            </div>
            <div className="mt-2 text-[15px] font-semibold">{l.idea}</div>
            {l.why && <p className="mt-0.5 text-[13px] text-muted">{l.why}</p>}
            <div className="mt-4 flex gap-2 text-[14px]"><CircleHelp className="mt-0.5 h-4 w-4 shrink-0 text-muted" /><Markdown>{l.check.q}</Markdown></div>
            <Options check={l.check} value={checking ? picks[i] : l.choice} locked={!checking}
              onPick={(c) => setPicks((p) => p.map((v, j) => (j === i ? c : v)))} />
            {!checking && l.check.explain && <Markdown className="mt-2 text-[12.5px] text-muted">{l.check.explain}</Markdown>}
            {works[i] ? <WorkingCheckCard check={works[i]} onClose={() => setWorks(({ [i]: _, ...rest }) => rest)} className="mt-3" />
              : (checking || l.result === "wrong") && (
                <button type="button" onClick={() => setPadFor(padFor === i ? null : i)}
                  className="mt-3 inline-flex items-center gap-1.5 text-[13px] font-medium text-accent hover:underline">
                  <PenLine className="h-3.5 w-3.5" />
                  {checking ? "Rough work" : "Check my working: where did it go wrong?"}
                </button>
              )}
          </Card>
        </div>
      ))}

      {checking && (
        <div className="flex flex-wrap items-center justify-end gap-3">
          <span className="text-[13px] text-muted">{[...beforePicks, ...picks].filter((p) => p !== null).length} of {beforePicks.length + picks.length} answered (a skip counts as not known yet)</span>
          <Button variant="primary" onClick={() => submit.mutate()} loading={submit.isPending}>Find my root gap</Button>
        </div>
      )}

      {padFor !== null && <>
        <div aria-hidden className="h-[50dvh]" />
        <RoughPad storageKey={`focs-rough-trace-${trace.id}`} page={`link-${padFor}`} onClose={() => setPadFor(null)}
          className="fixed inset-x-0 bottom-0 z-40 shadow-2xl" checking={checkWork.isPending}
          onCheck={checking ? undefined : (image) => { const at = padFor; checkWork.mutate(image, { onSuccess: (w) => { setWorks((m) => ({ ...m, [at]: w })); setPadFor(null); } }); }} />
      </>}

      {trace.status === "clear" && (
        <Card className="p-5">
          <div className="text-[15px] font-semibold">Your foundations hold.</div>
          <p className="mt-1 text-[13.5px] text-muted">Every idea underneath is solid, so the gap is in {trace.title} itself. Read its notes and do a short practice set on it.</p>
        </Card>
      )}

      {root && (trace.status === "found" || trace.status === "fixed") && (
        <Card className="p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Sparkles className="h-4 w-4 text-red" />
            <span className="text-[15px] font-semibold">The real gap: {root.idea}</span>
            <Badge>{where(root)}</Badge>
          </div>
          <p className="mt-1 text-[13.5px] text-muted">Fix this first and {trace.title} gets much easier.</p>
          {!trace.lesson ? (
            <Button variant="primary" className="mt-4" onClick={() => lesson.mutate()} loading={lesson.isPending}>Fix it in 5 minutes</Button>
          ) : (
            <div className="mt-4 space-y-4">
              <div className="rounded-xl bg-bg-soft p-4 text-[14px] leading-relaxed"><Markdown>{trace.lesson.md}</Markdown></div>
              <div>
                <div className="flex gap-2 text-[14px] font-medium"><CircleHelp className="mt-0.5 h-4 w-4 shrink-0" /><Markdown>{trace.lesson.check.q}</Markdown></div>
                <Options check={trace.lesson.check} value={pick ?? trace.lesson.choice}
                  locked={trace.lesson.result === "right"} onPick={setPick} />
                {trace.status === "fixed" ? (
                  <p className="mt-3 flex items-center gap-2 text-[14px] font-medium text-ok"><Check className="h-4 w-4" /> Gap closed.{after ? "" : ` Go back to ${trace.title}: it should click now.`}</p>
                ) : (
                  <div className="mt-3 flex items-center gap-3">
                    <Button variant="primary" size="sm" disabled={pick === null} onClick={() => pick !== null && recheck.mutate(pick)} loading={recheck.isPending}>Check</Button>
                    {trace.lesson.result === "wrong" && <span className="text-[13px] text-bad">Not yet. Read the example once more and try again.</span>}
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>
      )}

      {trace.status === "fixed" && after && after.items.length > 0 && (
        <Card className="p-5">
          {after.right === null ? (
            <>
              <div className="text-[15px] font-semibold">Now {trace.title} again</div>
              <p className="mt-0.5 text-[13px] text-muted">Three new questions on it, to see what fixing the root changed.</p>
              <RetestQuestions part={after} picks={afterPicks} onPicks={setAfterPicks} locked={false} />
              <div className="mt-4 flex justify-end">
                <Button variant="primary" onClick={() => again.mutate()} loading={again.isPending}>See the difference</Button>
              </div>
            </>
          ) : (
            <>
              <div className="text-[12px] font-medium uppercase tracking-[0.1em] text-muted">{trace.title}, before and after</div>
              <div className="mt-2 flex items-baseline gap-3 font-display text-[28px] font-semibold tabular-nums">
                <span className="text-muted">{before?.right ?? "–"}/{before?.total ?? after.total}</span>
                <ArrowRight className="h-5 w-5 self-center text-muted" aria-label="to" />
                <span className={before?.right != null && after.right > before.right ? "text-ok" : undefined}>{after.right}/{after.total}</span>
              </div>
              <p className="mt-1 text-[13px] text-muted">
                {before?.right == null ? "Right after the fix."
                  : after.right > before.right ? `Fixing ${root?.idea ?? "the root"} moved ${trace.title} from ${before.right} to ${after.right} right.`
                    : after.right === before.right ? `The same as before: the gap may be in ${trace.title} itself too. Practise it next.`
                      : `Lower than before: practise ${trace.title} next.`}
              </p>
              <RetestQuestions part={after} picks={afterPicks} onPicks={setAfterPicks} locked />
            </>
          )}
        </Card>
      )}

      {!checking && (
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-fg text-bg"><GraduationCap className="h-4 w-4" /></span>
            <div>
              <div className="text-[15px] font-semibold">Your tutor for {trace.title}</div>
              <div className="text-[12.5px] text-muted">Knows your root gaps, your slips and what this chapter rests on</div>
            </div>
          </div>
          <TutorChat chapterId={trace.chapter_id} placeholder={`Ask anything about ${trace.title}…`}
            starters={root ? [`How does ${root.idea} show up in ${trace.title}?`, "Give me one exam question to try", "What do toppers get wrong here?"]
              : ["Explain the hardest idea in this chapter", "Give me one exam question to try"]} />
        </Card>
      )}
    </div>
  );
}

function Picker({ onStart, busy }: { onStart: (chapterId: string, topicId?: string | null) => void; busy: boolean }) {
  const { data } = useQuery({ queryKey: ["gaps"], queryFn: api.gaps });
  const [q, setQ] = useState("");
  const matches = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!data || term.length < 2) return [];
    return data.chapters.filter((c) => `${c.name} ${c.subject}`.toLowerCase().includes(term)).slice(0, 8);
  }, [data, q]);
  if (!data) return <Skeleton className="h-48" />;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="What doesn't make sense?" icon={<Search className="h-4 w-4" />}
          subtitle="Pick a chapter. Focs traces it back through the earlier classes to the idea you're missing." />
        <div className="space-y-3 px-5 pb-5 pt-4">
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Rotational motion, Electrostatics, Trigonometry" aria-label="Search chapters" />
          {matches.length > 0 && (
            <div className="divide-y divide-line rounded-xl border border-line">
              {matches.map((c) => (
                <button key={c.id} type="button" disabled={busy} onClick={() => onStart(c.id)}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-[14px] hover:bg-hover">
                  <span>{c.name}</span><span className="text-[12px] text-muted">{c.subject}{c.cls >= 1 && c.cls <= 12 ? ` · Class ${c.cls}` : ""}</span>
                </button>
              ))}
            </div>
          )}
          {(data.suspects ?? []).map((s) => (
            <div key={s.chapter_id} className="rounded-xl border border-warn/50 bg-warn/10 p-4">
              <div className="caps mb-1 flex items-center gap-1.5 text-[11px] font-medium text-warn"><Sparkles size={13} /> Focs noticed</div>
              <p className="text-[14.5px] leading-relaxed">
                Your mistakes in <b>{s.because.slice(0, 3).join(", ")}</b> all rest on{" "}
                <b>{s.cls ? `Class ${s.cls} ` : ""}{s.name}</b> ({s.idea}). That may be the real gap, not those {s.because.length} chapters.
              </p>
              <Button size="sm" className="mt-3" disabled={busy} onClick={() => onStart(s.trace_chapter_id, null)}>
                Check it in 2 minutes <ArrowRight size={14} />
              </Button>
            </div>
          ))}
          {data.suggestions.length > 0 && (
            <div>
              <div className="caps mb-2 text-[11px] font-medium text-muted">From your weak spots</div>
              <div className="flex flex-wrap gap-2">
                {data.suggestions.map((s) => (
                  <Button key={`${s.chapter_id}${s.topic_id}`} size="sm" variant="secondary" disabled={busy} onClick={() => onStart(s.chapter_id, s.topic_id)}>
                    {s.name} <span className="text-muted">· lost {s.misses}</span>
                  </Button>
                ))}
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

export default function RootCause() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const id = Number(params.get("trace")) || null;
  const { data: overview } = useQuery({ queryKey: ["gaps"], queryFn: api.gaps });
  const { data: trace } = useQuery({ queryKey: ["gap", id], queryFn: () => api.gap(id!), enabled: !!id });
  const start = useMutation({
    mutationFn: ({ chapterId, topicId }: { chapterId: string; topicId?: string | null }) => api.gapStart(chapterId, topicId),
    onSuccess: (t) => { qc.setQueryData(["gap", t.id], t); qc.invalidateQueries({ queryKey: ["gaps"] }); setParams({ trace: String(t.id) }); },
    onError: failed("Couldn't trace that chapter right now"),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader eyebrow="Root cause" title="Find the real gap"
        subtitle="Most topics don't make sense because of something from an earlier class. Find it, fix it in five minutes, then go back."
        actions={id ? <Button variant="secondary" size="sm" onClick={() => setParams({})}>Trace another topic</Button> : undefined} />

      {start.isPending && (
        <Card className="flex items-center gap-3 p-5 text-[14px]">
          <GitBranch className="h-5 w-5 animate-pulse" /> Tracing it back through the earlier classes…
        </Card>
      )}
      {id ? (trace ? <Chain key={trace.id} trace={trace} /> : <Skeleton className="h-72" />)
        : !start.isPending && <Picker busy={start.isPending} onStart={(chapterId, topicId) => start.mutate({ chapterId, topicId })} />}

      {!id && <MistakeFingerprintCard />}

      {!id && overview && (overview.traces.length ? (
        <Card>
          <CardHeader title="Your traces" icon={<GitBranch className="h-4 w-4" />}
            subtitle={overview.fixed ? `${overview.fixed} root gap${overview.fixed === 1 ? "" : "s"} fixed` : "Each one checked against the classes before it"} />
          <div className="divide-y divide-line px-2 pb-2 pt-3">
            {overview.traces.map((t) => (
              <button key={t.id} type="button" onClick={() => setParams({ trace: String(t.id) })}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left hover:bg-hover">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14px] font-medium">{t.title}</span>
                  <span className="block truncate text-[12.5px] text-muted">
                    {t.root !== null ? `Root: ${t.chain[t.root].idea} (${where(t.chain[t.root])})` : t.chain.map((l) => l.idea).join(" ← ")}
                  </span>
                </span>
                <Badge tone={STATUS[t.status].tone}>{STATUS[t.status].label}</Badge>
                <span className="hidden text-[12px] text-muted sm:block">{t.created_at ? timeAgo(t.created_at) : ""}</span>
              </button>
            ))}
          </div>
        </Card>
      ) : (
        <EmptyState icon={<GitBranch className="h-5 w-5" />} title="No traces yet"
          body="Rotational motion, electrostatics, trigonometry: pick whatever isn't clicking." />
      ))}
    </div>
  );
}
