import { useState } from "react";
import type { MockQuestion } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The language a paper is read in: SSC prints every question in English and Hindi. Kept per device. */
export type PaperLanguage = "en" | "hi";
const KEY = "focs-paper-language";

export function usePaperLanguage(): [PaperLanguage, (l: PaperLanguage) => void] {
  const [lang, setLang] = useState<PaperLanguage>(() => {
    try { return localStorage.getItem(KEY) === "hi" ? "hi" : "en"; } catch { return "en"; }
  });
  const set = (l: PaperLanguage) => {
    setLang(l);
    try { localStorage.setItem(KEY, l); } catch { /* private window: the choice lasts this visit */ }
  };
  return [lang, set];
}

/** The question and its options in the chosen language (English where the paper has no Hindi for a part). */
export function shownIn(q: MockQuestion, lang: PaperLanguage): { question: string; options: string[] | null } {
  const hi = lang === "hi" ? q.hindi : undefined;
  return {
    question: hi?.question || q.question,
    options: q.options ? q.options.map((o, i) => hi?.options?.[i] || o) : null,
  };
}

/** English / हिंदी switch, for a paper with questions in both. */
export function LanguageToggle({ value, onChange, className }: { value: PaperLanguage; onChange: (l: PaperLanguage) => void; className?: string }) {
  return (
    <div role="group" aria-label="Question language" className={cn("inline-flex rounded-lg border border-line bg-bg-soft p-0.5 text-xs", className)}>
      {(["en", "hi"] as const).map((l) => (
        <button key={l} type="button" aria-pressed={value === l} onClick={() => onChange(l)} lang={l}
          className={cn("min-h-8 rounded-md px-2.5 font-medium transition", value === l ? "bg-elev-2 text-fg ring-1 ring-line-strong" : "text-muted hover:text-fg")}>
          {l === "en" ? "English" : "हिंदी"}
        </button>
      ))}
    </div>
  );
}

/** The figures a question needs (mirror images, paper folding, series of pictures). */
export function QuestionFigures({ q, className }: { q: MockQuestion; className?: string }) {
  const figures = q.media?.figures ?? [];
  if (!figures.length) return null;
  return (
    <div className={cn("flex flex-wrap gap-3", className)}>
      {figures.map((src, i) => (
        <img key={src} src={src} alt={`Figure ${i + 1} of the question`} loading="lazy"
          className="max-h-72 max-w-full rounded-lg border border-line bg-white object-contain p-1" />
      ))}
    </div>
  );
}

/** An option given as a picture, or null when the option is text. */
export function optionFigure(q: MockQuestion, i: number): string | null {
  return q.media?.options?.[i] ?? null;
}

export function OptionFigure({ src, n }: { src: string; n: number }) {
  return <img src={src} alt={`Option ${n}`} loading="lazy" className="max-h-28 max-w-full rounded-md border border-line bg-white object-contain p-0.5" />;
}
