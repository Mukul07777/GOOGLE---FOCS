import { Square, Volume2 } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { canSpeak, speak, speakingId, stopSpeaking } from "@/lib/readAloud";
import { useA11y } from "@/stores/a11y";
import { useAuth } from "@/stores/auth";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

/** "Read aloud" for a note, an answer or a solution, in the student's language where the device has the voice. */
export function ReadAloud({ text, label = "Read aloud", className }: { text: string; label?: string; className?: string }) {
  const id = useId();
  const [on, setOn] = useState(false);
  const rate = useA11y((s) => s.speechRate);
  const language = useAuth((s) => s.user?.language) ?? "en";
  const t = useT();
  useEffect(() => () => { if (speakingId() === id) stopSpeaking(); }, [id]);  // leaving the page stops it
  if (!canSpeak() || !text.trim()) return null;
  const toggle = () => {
    if (on) return stopSpeaking();
    setOn(true);
    speak(text, id, () => setOn(false), { lang: language, rate });
  };
  return (
    <button type="button" onClick={toggle} aria-pressed={on} title={t(on ? "Stop reading" : label)}
      className={cn("inline-flex items-center gap-1.5 rounded-lg px-2 py-1 pointer-coarse:py-2.5 text-xs font-medium text-muted transition hover:bg-elev-2 hover:text-fg", on && "text-accent", className)}>
      {on ? <Square className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
      {t(on ? "Stop" : label)}
    </button>
  );
}
