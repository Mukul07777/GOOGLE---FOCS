import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import { cn, STREAMS, subjectColor, THIRD_LANGUAGES } from "@/lib/utils";

/** A school student's subjects (PCM, PCB, commerce, humanities, the languages): the Prep Hub, plan and tests follow the ones ticked. */
export function SchoolSubjects({ all, mine, submitLabel = "Save", onSaved, ask = false }: {
  all: string[]; mine: string[]; submitLabel?: string; onSaved?: (subjects: string[]) => void;
  /** first set-up: a Class 11 or 12 student picks their stream themselves (nothing is chosen for them) */
  ask?: boolean;
}) {
  const qc = useQueryClient();
  const [picked, setPicked] = useState<string[]>(mine);
  const save = useMutation({
    mutationFn: () => api.setPrepSubjects(all.filter((s) => picked.includes(s))),
    onSuccess: (r) => {
      ["prep-syllabus", "prep-plan", "prep-goal", "mock-meta", "last-day", "weak"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      onSaved?.(r.subjects);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't save that. Try again."),
  });
  // Class 11 and 12: the stream comes first (it decides the subjects); then one more subject can be added or removed
  const senior = all.includes("Accountancy");
  const streams = senior ? STREAMS.map((st) => ({ ...st, subjects: st.subjects.filter((x) => all.includes(x)) })) : [];
  const [stream, setStream] = useState<string | null>(() => ask ? null : streams.find((st) => st.subjects.every((x) => mine.includes(x))
    && !streams.some((o) => o.subjects.length > st.subjects.length && o.subjects.every((x) => mine.includes(x))))?.id ?? null);
  // Class 6 to 8: the third language is one of Sanskrit, French, German and Spanish
  const languages = THIRD_LANGUAGES.filter((l) => all.includes(l));
  const choosesLanguage = languages.length > 1 && all.includes("French");
  const language = languages.find((l) => picked.includes(l)) ?? null;
  const pickLanguage = (l: string) => setPicked([...picked.filter((x) => !languages.includes(x)), l]);
  const others = all.filter((x) => !(choosesLanguage && languages.includes(x)));
  return (
    <div className="space-y-5">
      {senior && (
        <div>
          <p className="mb-2 text-sm font-medium">Your stream</p>
          <div className="flex flex-wrap gap-2">
            {streams.map((st) => (
              <button key={st.id} type="button" aria-pressed={stream === st.id} onClick={() => { setStream(st.id); setPicked(st.subjects); }}
                className={cn("rounded-xl border px-3 py-2 text-sm font-medium transition",
                  stream === st.id ? "border-accent/60 bg-accent-soft" : "border-line bg-bg-soft hover:border-line-strong")}>
                {st.name}
              </button>
            ))}
          </div>
          {stream && <p className="mt-3 text-sm text-muted">Your subjects (add an elective such as Hindi Core, or remove one):</p>}
        </div>
      )}
      {choosesLanguage && (
        <div>
          <p className="mb-2 text-sm font-medium">Your third language</p>
          <div className="flex flex-wrap gap-2">
            {languages.map((l) => (
              <button key={l} type="button" aria-pressed={language === l} onClick={() => pickLanguage(l)}
                className={cn("rounded-xl border px-3 py-2 text-sm font-medium transition",
                  language === l ? "border-accent/60 bg-accent-soft" : "border-line bg-bg-soft hover:border-line-strong")}>
                {l}
              </button>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted">Your other subjects:</p>
        </div>
      )}
      {(!senior || stream) && <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {others.map((s) => {
          const on = picked.includes(s);
          return (
            <button key={s} type="button" aria-pressed={on} onClick={() => setPicked(on ? picked.filter((x) => x !== s) : [...picked, s])}
              className={cn("flex items-center gap-3 rounded-2xl border p-4 text-left transition",
                on ? "border-accent/60 bg-accent-soft" : "border-line bg-bg-soft hover:border-line-strong")}>
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: subjectColor(s) }} />
              <span className="flex-1 font-semibold">{s}</span>
              {on && <Check className="h-4 w-4 text-accent" />}
            </button>
          );
        })}
      </div>}
      <Button variant="primary" size="lg" disabled={!picked.length || (senior && !stream) || (choosesLanguage && !language)} loading={save.isPending} onClick={() => save.mutate()}>{submitLabel}</Button>
    </div>
  );
}

export function SchoolSubjectsDialog({ open, onClose, all, mine }: { open: boolean; onClose: () => void; all: string[]; mine: string[] }) {
  return (
    <Dialog open={open} onClose={onClose} title="Your subjects" subtitle="Tick the ones you have this year. Your Prep Hub, plan and tests follow them.">
      {open && <SchoolSubjects all={all} mine={mine} onSaved={() => { toast.success("Subjects updated"); onClose(); }} />}
    </Dialog>
  );
}
