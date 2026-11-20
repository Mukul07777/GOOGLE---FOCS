import { useCallback, useEffect, useRef } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { SessionAlive } from "@/lib/types";
import { formatPaused } from "@/lib/utils";

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

export const welcomeBack = (secs: number) =>
  toast.success(`Welcome back. ${secs >= 60 ? `Your lecture was paused for ${formatPaused(secs)}; it's` : "It's"} still the same session and your notes are safe.`);

const LIVE_KEY = "focs-live-session";
export function rememberLive(id: number) { try { localStorage.setItem(LIVE_KEY, JSON.stringify({ id, at: Date.now() })); } catch { /* private mode */ } }
export function forgetLive() { try { localStorage.removeItem(LIVE_KEY); } catch { /* private mode */ } }
/** the lecture this browser had open in the last 12 hours (the tab may have been discarded during a long pause) */
export function recallLive(): number | null {
  try {
    const v = JSON.parse(localStorage.getItem(LIVE_KEY) ?? "null") as { id: number; at: number } | null;
    return v && Date.now() - v.at < 12 * 3_600_000 ? v.id : null;
  } catch { return null; }
}

/** Keeps the screen on while `on`. A hidden tab can't hold the lock, so it is asked for again when the tab is visible. */
export function useWakeLock(on: boolean) {
  useEffect(() => {
    if (!on || !("wakeLock" in navigator)) return;
    type Lock = { release: () => Promise<void> };
    let lock: Lock | null = null;
    let dead = false;
    const hold = () => {
      if (document.visibilityState !== "visible") return;
      void lock?.release().catch(() => undefined);
      (navigator as Navigator & { wakeLock: { request: (t: "screen") => Promise<Lock> } }).wakeLock.request("screen")
        .then((l) => { if (dead) void l.release().catch(() => undefined); else lock = l; }).catch(() => undefined);
    };
    hold();
    document.addEventListener("visibilitychange", hold);
    return () => { dead = true; document.removeEventListener("visibilitychange", hold); void lock?.release().catch(() => undefined); };
  }, [on]);
}

/**
 * Tells the server this lecture tab is still open, every minute and the moment the student comes back or goes online.
 * A session the server closed for idleness comes back; one the student ended makes `onGone` run. Errors stay silent.
 */
export function useSessionAlive(sessionId: number, getState: () => { paused: boolean; secs: number }, onGone: () => void) {
  const latest = useRef({ getState, onGone });
  latest.current = { getState, onGone };
  const ping = useCallback(async (over?: { paused: boolean; secs: number }): Promise<SessionAlive | null> => {
    const s = over ?? latest.current.getState();
    try {
      const r = await api.sessionAlive(sessionId, { paused: s.paused, paused_for_s: Math.round(s.secs) });
      if (r.active) rememberLive(sessionId);
      if (r.reopened) welcomeBack(Math.max(r.paused_for_s, s.secs));
      else if (!r.active) latest.current.onGone();
      return r;
    } catch { return null; }
  }, [sessionId]);
  useEffect(() => {
    const again = () => { void ping(); };
    const visible = () => { if (document.visibilityState === "visible") again(); };
    again();  // once now: remembers the lecture and reopens one the server closed while the tab was away
    const stop = steadyInterval(again, 60_000);
    document.addEventListener("visibilitychange", visible);
    window.addEventListener("online", again);
    return () => { stop(); document.removeEventListener("visibilitychange", visible); window.removeEventListener("online", again); };
  }, [ping]);
  return ping;
}
