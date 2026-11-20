import { Loader2, Mic, MicOff, Square } from "lucide-react";
import { useCallback, useRef } from "react";
import { SPEECH_LANGS, useDictation } from "@/lib/speech";
import { cn, formatDuration } from "@/lib/utils";

/** An answer the student can type, speak, or both: spoken words land in the same text, where they can be fixed. */
export function AnswerInput({ value, onChange, placeholder, hint, className, minHeight = "min-h-40", disabled }: {
  value: string; onChange: (v: string) => void; placeholder?: string; className?: string; minHeight?: string; disabled?: boolean;
  /** what is being answered: helps speech recognition with the topic's vocabulary */
  hint?: string;
}) {
  const latest = useRef(value);
  latest.current = value;
  const append = useCallback((text: string) => {
    const before = latest.current.trimEnd();
    onChange(before ? `${before} ${text}` : text.charAt(0).toUpperCase() + text.slice(1));
  }, [onChange]);
  const d = useDictation(append, hint);
  const words = value.trim() ? value.trim().split(/\s+/).length : 0;

  return (
    <div className={cn("rounded-xl border border-line bg-bg-soft transition focus-within:border-accent/60 focus-within:bg-panel focus-within:ring-4 focus-within:ring-accent/10",
      d.listening && "border-bad/50 ring-4 ring-bad/10", className)}>
      <textarea value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled} placeholder={placeholder}
        aria-label={placeholder ?? "Your answer"}
        className={cn("block w-full resize-y bg-transparent px-3.5 pt-3 text-sm leading-relaxed text-fg outline-none placeholder:text-muted/80", minHeight)} />
      {d.interim && <p className="px-3.5 pb-2 text-sm italic leading-relaxed text-muted" aria-live="polite">{d.interim}…</p>}

      <div className="flex flex-wrap items-center gap-2 border-t border-line px-2 py-2">
        {d.available ? (
          d.listening ? (
            <button type="button" onClick={d.stop}
              className="inline-flex h-8 items-center gap-2 rounded-lg bg-bad/10 px-3 text-[13px] font-medium text-bad transition hover:bg-bad/20">
              <Square className="h-3 w-3 fill-current" />Stop
              <span className="flex items-center gap-1.5 font-mono text-xs tabular-nums"><span className="live-dot scale-75" />{formatDuration(d.seconds)}</span>
            </button>
          ) : d.transcribing ? (
            <span className="inline-flex h-8 items-center gap-2 px-2 text-[13px] text-muted"><Loader2 className="h-3.5 w-3.5 animate-spin" />Writing down what you said…</span>
          ) : (
            <button type="button" onClick={d.start} disabled={disabled}
              className="inline-flex h-8 items-center gap-2 rounded-lg border border-line bg-elev-2 px-3 text-[13px] font-medium text-fg transition hover:border-accent/50 disabled:opacity-50">
              <Mic className="h-3.5 w-3.5 text-accent" />{value.trim() ? "Speak more" : "Speak your answer"}
            </button>
          )
        ) : (
          <span className="inline-flex h-8 items-center gap-2 px-2 text-xs text-muted" title="Speaking an answer works in Chrome, Edge and Safari">
            <MicOff className="h-3.5 w-3.5" />Voice isn't available in this browser
          </span>
        )}
        {d.available && !d.listening && !d.transcribing && (
          <div className="inline-flex rounded-lg border border-line p-0.5" role="group" aria-label="Language you'll speak in">
            {SPEECH_LANGS.map((l) => (
              <button key={l.value} type="button" title={l.title} aria-pressed={d.lang === l.value} onClick={() => d.setLang(l.value)}
                className={cn("h-6 rounded-md px-2 text-[11.5px] font-medium transition", d.lang === l.value ? "bg-elev-2 text-fg" : "text-muted hover:text-fg")}>
                {l.label}
              </button>
            ))}
          </div>
        )}
        <span className="ml-auto pr-1.5 text-xs tabular-nums text-muted">
          {d.listening ? (d.engine === "server" ? "Recording. Press Stop when you're done" : "Listening. You can keep typing too") : words ? `${words} word${words === 1 ? "" : "s"}` : "Type or speak"}
        </span>
      </div>
      {d.error && <p className="border-t border-line px-3.5 py-2 text-xs leading-relaxed text-warn" role="alert">{d.error}</p>}
    </div>
  );
}
