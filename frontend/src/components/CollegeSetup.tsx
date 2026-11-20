import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, RotateCcw, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { CollegeSetup as Setup } from "@/lib/types";
import { cn, subjectColor } from "@/lib/utils";
import { useAuth } from "@/stores/auth";

/** Everything that shows a college student's subjects, to refresh once they change. */
const AFFECTED = ["prep-college", "prep-syllabus", "prep-plan", "prep-goal", "mock-meta", "last-day", "weak"];

/** Where a B.Tech student studies, their semester and the subjects they take in it. A college's own semester plan
    is offered where Focs has it; either way the student can drop a course or add any other one. */
export function CollegeSetup({ submitLabel = "Save", onSaved, className }: {
  submitLabel?: string; onSaved?: (saved: Setup) => void; className?: string;
}) {
  const qc = useQueryClient();
  const setUser = useAuth((s) => s.setUser);
  // null: as saved. Choosing another college or semester shows that plan's subjects until the student edits them.
  const [college, setCollege] = useState<string | null>(null);
  const [semester, setSemester] = useState<number | null>(null);
  const [edited, setEdited] = useState<string[] | null>(null);
  const [q, setQ] = useState("");
  const { data, isFetching } = useQuery({
    queryKey: ["prep-college", college, semester], queryFn: () => api.prepCollege(college, semester), placeholderData: keepPreviousData,
  });
  const subjects = useMemo(() => edited ?? data?.subjects ?? [], [edited, data?.subjects]);
  const sem = semester ?? data?.semester ?? null;
  const byName = useMemo(() => new Map((data?.catalogue ?? []).map((c) => [c.name, c])), [data]);
  const planned = data && sem ? data.semesters[sem - 1]?.subjects ?? [] : [];
  const matches = useMemo(() => {
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!data || !words.length) return [];
    return data.catalogue
      .filter((c) => !subjects.includes(c.name) && words.every((w) => `${c.name} ${c.about} ${c.area}`.toLowerCase().includes(w)))
      .sort((a, b) => Number(!a.semester) - Number(!b.semester) || a.semester - b.semester)
      .slice(0, 8);
  }, [q, data, subjects]);

  const save = useMutation({
    // untouched: keep following the plan, or keep the list they picked before
    mutationFn: () => api.setPrepCollege({ college: data!.college, semester: sem!, subjects: edited ?? (data!.picked ? data!.subjects : null) }),
    onSuccess: async (saved) => {
      setCollege(null); setSemester(null); setEdited(null);
      qc.setQueryData(["prep-college", null, null], saved);
      AFFECTED.forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
      try { setUser(await api.me()); } catch { /* the next page load picks it up */ }
      onSaved?.(saved);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't save that. Try again."),
  });

  if (!data) return <div className={cn("space-y-3", className)}><Skeleton className="h-12" /><Skeleton className="h-12" /><Skeleton className="h-40" /></div>;
  const chosen = data.colleges.find((c) => c.id === data.college);
  const full = subjects.length >= data.max_subjects;
  const hours = subjects.reduce((n, s) => n + (byName.get(s)?.hours ?? 0), 0);
  const pick = (next: { college?: string; semester?: number }) => {
    if (next.college !== undefined) setCollege(next.college);
    if (next.semester !== undefined) setSemester(next.semester);
    setEdited(null);  // another plan: start from its subjects
  };

  return (
    <div className={cn("space-y-6", className)}>
      <div>
        <Label>Your college</Label>
        <div className="flex flex-wrap gap-2">
          {data.colleges.map((c) => (
            <button key={c.id} type="button" onClick={() => pick({ college: c.id })} aria-pressed={c.id === data.college} title={c.full}
              className={cn("rounded-xl border px-3.5 py-2 text-sm font-medium transition",
                c.id === data.college ? "border-accent/60 bg-accent-soft text-fg" : "border-line bg-elev/50 text-fg-soft hover:border-line-strong")}>
              {c.name}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs leading-relaxed text-muted">
          {!data.own_plan && data.college !== "other" && <>Focs doesn't have {chosen?.name}'s {data.branch.short} scheme yet, so this is a typical plan. </>}
          {data.source}
        </p>
      </div>

      <div>
        <Label>Your semester</Label>
        <div className="grid grid-cols-8 gap-1.5 sm:max-w-md">
          {data.semesters.map((s) => (
            <button key={s.n} type="button" onClick={() => pick({ semester: s.n })} aria-pressed={s.n === sem} aria-label={`Semester ${s.n}`}
              className={cn("h-10 rounded-xl border text-sm font-semibold tabular-nums transition",
                s.n === sem ? "border-accent/60 bg-accent-soft text-fg" : "border-line bg-elev/50 text-fg-soft hover:border-line-strong")}>
              {s.n}
            </button>
          ))}
        </div>
      </div>

      <div className={cn(isFetching && "opacity-70")}>
        <Label hint={sem ? `${subjects.length} subject${subjects.length === 1 ? "" : "s"} · about ${hours} h of self-study` : undefined}>
          Your subjects this semester
        </Label>
        {!sem ? (
          <p className="rounded-xl border border-dashed border-line-strong p-4 text-sm text-muted">Pick your semester and its subjects appear here.</p>
        ) : (
          <>
            {!planned.length && !edited && !data.picked && (
              <p className="mb-2 text-xs leading-relaxed text-muted">
                This plan has no taught courses in semester {sem} (it is the project or internship), so your last semester's subjects are kept. Change them to whatever you're studying now.
              </p>
            )}
            <div className="overflow-hidden rounded-2xl border border-line">
              {subjects.map((name) => {
                const c = byName.get(name);
                const elsewhere = c && c.semester !== sem;
                return (
                  <div key={name} className="flex items-center gap-3 border-b border-line px-3.5 py-2.5 last:border-0">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: subjectColor(name) }} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{name}</div>
                      <div className="truncate text-xs text-muted">
                        {c ? `${c.chapters} chapters · ${c.topics} topics · ~${c.hours} h` : ""}
                        {elsewhere ? ` · ${c.semester ? `semester ${c.semester} in this plan` : "from outside this plan"}` : ""}
                      </div>
                    </div>
                    <button type="button" onClick={() => setEdited(subjects.filter((s) => s !== name))} disabled={subjects.length <= 1}
                      aria-label={`Remove ${name}`} className="rounded-lg p-1.5 text-muted transition hover:bg-elev-2 hover:text-bad disabled:opacity-30">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                );
              })}
            </div>
            <div className="relative mt-3">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} disabled={full} className="pl-9"
                placeholder={full ? `That's the most a semester holds (${data.max_subjects})` : "Add a subject: an elective, a backlog, a course your college teaches now…"} />
            </div>
            {q.trim() && !full && (
              <div className="mt-2 overflow-hidden rounded-xl border border-line bg-bg-soft">
                {matches.map((c) => (
                  <button key={c.name} type="button" onClick={() => { setEdited([...subjects, c.name]); setQ(""); }}
                    className="flex w-full items-center gap-3 border-b border-line px-3.5 py-2 text-left transition last:border-0 hover:bg-elev-2/60">
                    <Plus className="h-4 w-4 shrink-0 text-accent" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{c.name}</span>
                      <span className="block truncate text-xs text-muted">{c.about}</span>
                    </span>
                    <span className="shrink-0 text-xs text-muted">{c.semester ? `Sem ${c.semester}` : c.area}</span>
                  </button>
                ))}
                {!matches.length && <p className="px-3.5 py-3 text-sm text-muted">No course by that name. Try a shorter word ("signals", "thermo", "networks").</p>}
              </div>
            )}
            {(edited || data.picked) && planned.length > 0 && subjects.join("|") !== planned.join("|") && (
              <button type="button" onClick={() => setEdited(planned)} className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:underline">
                <RotateCcw className="h-3 w-3" />Back to the plan's subjects for semester {sem}
              </button>
            )}
          </>
        )}
      </div>

      <Button variant="primary" size="lg" disabled={!sem || !subjects.length} loading={save.isPending} onClick={() => save.mutate()}
        icon={<Check className="h-4 w-4" />}>
        {submitLabel}
      </Button>
    </div>
  );
}

export function CollegeSetupDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} wide title="Your college, semester and subjects"
      subtitle="Your Prep Hub, plan, tests and revision follow these subjects. Change them whenever your semester does.">
      {open && <CollegeSetup onSaved={() => { toast.success("Subjects updated"); onClose(); }} />}
    </Dialog>
  );
}
