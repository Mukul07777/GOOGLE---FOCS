import { useQuery } from "@tanstack/react-query";
import { Languages } from "lucide-react";
import { useState } from "react";
import { Markdown } from "@/components/Markdown";
import { ReadAloud } from "@/components/ReadAloud";
import { Select } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import type { Language, MockQuestion } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { WaitBridge } from "@/components/WaitBridge";

/** Every language Focs explains in, each named in its own script (and in English, for the menu). */
export const LANGUAGES: { value: Language; label: string; name: string }[] = [
  { value: "en", label: "English", name: "English" }, { value: "hinglish", label: "Hinglish", name: "Hinglish" },
  { value: "hi", label: "हिंदी", name: "Hindi" }, { value: "mr", label: "मराठी", name: "Marathi" },
  { value: "bn", label: "বাংলা", name: "Bengali" }, { value: "ta", label: "தமிழ்", name: "Tamil" },
  { value: "te", label: "తెలుగు", name: "Telugu" }, { value: "gu", label: "ગુજરાતી", name: "Gujarati" },
];

/** A compact language menu: eight languages are too many for a row of tabs on a phone. */
export function LanguagePicker({ value, onChange, className, label = "Language" }: {
  value: Language; onChange: (l: Language) => void; className?: string; label?: string;
}) {
  return (
    <Select aria-label={label} value={value} onChange={(e) => onChange(e.target.value as Language)} className={cn("h-8 w-auto pl-2.5 text-xs", className)}>
      {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label === l.name ? l.label : `${l.label} (${l.name})`}</option>)}
    </Select>
  );
}

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
        <LanguagePicker value={language} onChange={setLanguage} />
      </div>
      {!other && <Markdown className="text-[13.5px]">{q.solution ?? ""}</Markdown>}
      {other && isLoading && <WaitBridge kind="translation" topic={q.chapter} compact />}
      {other && error && <p className="text-[13px] text-bad">{error instanceof ApiError ? error.message : "Couldn't explain it in that language."}</p>}
      {other && data && <Markdown className="text-[13.5px]">{data.solution}</Markdown>}
      <ReadAloud text={other ? data?.solution ?? "" : q.solution ?? ""} className="-ml-2 mt-1" />
    </div>
  );
}
