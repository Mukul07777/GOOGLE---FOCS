import { useEffect, useRef } from "react";
import { api } from "@/lib/api";

/**
 * setInterval that keeps its pace in a background tab. Browsers slow main-thread timers in hidden tabs to
 * once a minute — exactly where Focs sits while the student watches the lecture in another tab — but a
 * dedicated worker's timer keeps ticking and its messages still wake the page.
 */
export function steadyInterval(fn: () => void, ms: number): () => void {
  try {
    const src = `let t=null;onmessage=(e)=>{clearInterval(t);if(e.data>0)t=setInterval(()=>postMessage(0),e.data)}`;
    const url = URL.createObjectURL(new Blob([src], { type: "text/javascript" }));
    const worker = new Worker(url);
    URL.revokeObjectURL(url);
    worker.onmessage = () => fn();
    worker.postMessage(ms);
    return () => { worker.postMessage(0); worker.terminate(); };
  } catch {
    const t = setInterval(fn, ms); // no workers (very old browser / locked-down page): plain timer
    return () => clearInterval(t);
  }
}

export type FocusActivity = "lecture" | "mock" | "practice" | "flashcards" | "room" | "revision";

const IDLE_AFTER_MS = 3 * 60_000;
let lastInteraction = Date.now();
let listening = false;
function trackInteraction() {
  if (listening) return;
  listening = true;
  const mark = () => { lastInteraction = Date.now(); };
  for (const e of ["pointerdown", "keydown", "wheel", "touchstart", "scroll"]) window.addEventListener(e, mark, { passive: true, capture: true });
}

/**
 * Focus time: one heartbeat a minute while the student is studying. `active` says whether this screen is in
 * a studying state (capturing a lecture, a mock running…). With `needsAttention`, the tab must also be visible
 * and touched in the last 3 minutes, so a practice page left open doesn't count.
 */
export function useFocus(activity: FocusActivity, active: boolean, needsAttention = false) {
  const latest = useRef({ activity, active, needsAttention });
  latest.current = { activity, active, needsAttention };
  useEffect(() => {
    trackInteraction();
    const tzOffset = -new Date().getTimezoneOffset();
    return steadyInterval(() => {
      const { activity: a, active: on, needsAttention: attention } = latest.current;
      if (!on) return;
      if (attention && (document.hidden || Date.now() - lastInteraction > IDLE_AFTER_MS)) return;
      api.focusHeartbeat(a, tzOffset).catch(() => undefined); // focus time is best-effort, never an error toast
    }, 60_000);
  }, []);
}
