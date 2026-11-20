import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Sigma, Target, Timer, Trophy } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Card } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { hasSyllabus, hasTests, isGate, isSsc, mockExamName, subjectTestsOnly, timeAgo } from "@/lib/utils";

function Tile({ to, icon, title, value, sub }: { to: string; icon: ReactNode; title: string; value: ReactNode; sub: ReactNode }) {
  return (
    <Link to={to} className="group">
      <Card className="flex h-full items-center gap-4 p-5 transition group-hover:border-line-strong">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-elev-2">{icon}</div>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] text-muted">{title}</div>
          <div className="mt-0.5 text-lg font-semibold tracking-tight">{value}</div>
          <div className="text-xs text-muted">{sub}</div>
        </div>
        <ArrowRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-fg" />
      </Card>
    </Link>
  );
}

/** Dashboard row that keeps the exam-practice features one click away. */
export function NextSteps() {
  const { data: mocks } = useQuery({ queryKey: ["mocks"], queryFn: api.mocks, staleTime: 60_000 });
  const { data: board } = useQuery({ queryKey: ["leaderboard", "week", "exam"], queryFn: () => api.leaderboard("week", "exam"), staleTime: 60_000 });
  const { data: formulas } = useQuery({ queryKey: ["formula-book"], queryFn: api.formulaBook, staleTime: 5 * 60_000 });

  const user = useAuth((st) => st.user);
  const college = subjectTestsOnly(user?.exam_target);  // a semester, the boards: tests are on one subject, there is no full mock
  const lastFull = mocks?.find((m) => (college || m.kind === "full") && m.status === "submitted");
  const running = mocks?.find((m) => m.status === "in_progress");
  const formulaCount = (formulas ?? []).reduce((n, s) => n + s.count, 0);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {(!hasSyllabus(user?.exam_target) || !hasTests(user?.exam_target)) && !running ? (  // UPSC, CA, other, and school outside the board years: practice instead
        <Tile to="/app/practice" icon={<Target className="h-5 w-5 text-bad" />} title="Practice"
          value="Questions from your notes" sub="Quizzes on what your lectures covered" />
      ) : (
      <Tile to={running ? `/exam/${running.id}` : "/app/mock"} icon={<Timer className="h-5 w-5 text-bad" />}
        title={college ? "Subject tests" : `Full ${mockExamName(user?.exam_target)} mock`}
        value={running ? "Resume your test" : lastFull ? `${lastFull.score} / ${lastFull.max_score}` : college ? "Take your first test" : "Take your first mock"}
        sub={running ? "The clock is still running" : lastFull ? `Last ${college ? "test" : "mock"} · ${timeAgo(lastFull.submitted_at)}`
          : college ? "MCQs on any of your subjects · timed · full analysis"
            : isGate(user?.exam_target) ? "3 hours · 65 questions · full analysis"
              : isSsc(user?.exam_target) ? "Tier-I · 100 questions in 60 min · full analysis"
              : `${user?.exam_target === "neet" ? "3 h 20 min" : "3 hours"} · NTA-style · full analysis`} />
      )}
      <Tile to="/app/leaderboard" icon={<Trophy className="h-5 w-5 text-warn" />} title="This week's leaderboard"
        value={board?.me ? `#${board.me.rank} · ${board.me.xp.toLocaleString()} XP` : "Not ranked yet"}
        sub={board?.me ? `of ${board.total} students` : "Answer any question to get on the board"} />
      <Tile to="/app/formulas" icon={<Sigma className="h-5 w-5 text-accent-2" />} title="Formula book"
        value={formulaCount ? `${formulaCount} formulas` : "Builds itself"} sub={formulaCount ? "Every formula from your lectures" : "Capture a lecture to start it"} />
    </div>
  );
}
