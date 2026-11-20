import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, GitBranch } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { hasSyllabus } from "@/lib/utils";
import { useAuth } from "@/stores/auth";

/* "Your real gap": the root-cause loop surfaced where students already look. An open root first, then what silent
   tracing noticed from weak chapters, then a suggestion; nothing at all when there is nothing to say. */
export function RealGap({ compact, suspectsOnly }: { compact?: boolean; suspectsOnly?: boolean }) {
  const tr = useT();
  const navigate = useNavigate();
  const syllabus = useAuth((s) => hasSyllabus(s.user?.exam_target));
  const { data } = useQuery({ queryKey: ["gaps"], queryFn: api.gaps, enabled: syllabus });
  const start = useMutation({
    mutationFn: (chapterId: string) => api.gapStart(chapterId),
    onSuccess: (t) => navigate(`/app/roots?trace=${t.id}`),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start the check"),
  });
  if (!syllabus || !data) return null;

  const open = suspectsOnly ? undefined : data.traces.find((t) => t.status === "found" && t.root !== null && t.chain[t.root]);
  const suspect = data.suspects?.[0];
  const sug = data.suggestions[0];
  let text: string; let action: React.ReactNode;
  if (open) {
    const root = open.chain[open.root as number];
    text = `Fix your root gap: ${root.idea}${root.cls ? ` (Class ${root.cls})` : ""}, behind ${open.title}`;
    action = <Link to={`/app/roots?trace=${open.id}`}><Button variant="primary" size={compact ? "sm" : "md"} icon={<ArrowRight className="h-4 w-4" />}>{tr("Fix it")}</Button></Link>;
  } else if (suspect) {
    const [a, b] = suspect.because;
    text = `Focs noticed: ${b ? `${a}, ${b} both rest` : `${a} rests`} on ${suspect.name}${suspect.cls ? ` (Class ${suspect.cls})` : ""}. Check it in 2 minutes`;
    action = (
      <Button variant="primary" size={compact ? "sm" : "md"} loading={start.isPending} icon={<ArrowRight className="h-4 w-4" />}
        onClick={() => start.mutate(suspect.trace_chapter_id)}>{tr("Check it")}</Button>
    );
  } else if (sug && !suspectsOnly) {
    text = `Find the real gap behind ${sug.chapter || sug.name}`;
    action = <Link to="/app/roots"><Button variant="primary" size={compact ? "sm" : "md"} icon={<ArrowRight className="h-4 w-4" />}>{tr("Find it")}</Button></Link>;
  } else return null;

  return (
    <Card className={compact ? "flex flex-wrap items-center gap-3 p-4" : "flex flex-wrap items-center gap-4 p-5"}>
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-fg text-bg"><GitBranch className="h-5 w-5" /></span>
      <div className="min-w-[200px] flex-1">
        <div className="text-[12px] text-muted">{tr("Your real gap")}</div>
        <p className="text-[14px] font-medium leading-snug">{text}</p>
      </div>
      {action}
    </Card>
  );
}
