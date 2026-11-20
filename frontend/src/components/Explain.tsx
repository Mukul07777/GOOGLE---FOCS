import { useQuery } from "@tanstack/react-query";
import { Languages } from "lucide-react";
import { useState } from "react";
import { Markdown } from "@/components/Markdown";
import { ReadAloud } from "@/components/ReadAloud";
import { Segmented } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { Language, MockQuestion } from "@/lib/types";
import { useAuth } from "@/stores/auth";
import { WaitBridge } from "@/components/WaitBridge";

export const LANGUAGES: { value: Language; label: string }[] = [
  { value: "en", label: "English" }, { value: "hinglish", label: "Hinglish" }, { value: "hi", label: "हिंदी" },
];

/** A test question's solution, in English or said again in the student's language (written once, then kept). */
export function Solution({ q }: { q: MockQuestion }) {
  const preferred = useAuth((s) => s.user?.language) ?? "en";
  const [language, setLanguage] = useState<Language>(preferred);
  const other = language !== "en";
  const { data, isLoading, error } = useQuery({
    queryKey: ["explain", q.id, language], enabled: other, retry: false, staleTime: Infinity,
    queryFn: () => api.explainQuestion(q.id, language as Exclude<Language, "en">),
  });
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <Languages className="h-3.5 w-3.5 text-muted" />
        <Segmented size="sm" value={language} onChange={setLanguage} options={LANGUAGES} />
      </div>
      {!other && <Markdown className="text-[13.5px]">{q.solution ?? ""}</Markdown>}
      {other && isLoading && <WaitBridge kind="translation" topic={q.chapter} compact />}
      {other && error && <p className="text-[13px] text-bad">{error instanceof ApiError ? error.message : "Couldn't explain it in that language."}</p>}
      {other && data && <Markdown className="text-[13.5px]">{data.solution}</Markdown>}
      <ReadAloud text={other ? data?.solution ?? "" : q.solution ?? ""} className="-ml-2 mt-1" />
    </div>
  );
}
