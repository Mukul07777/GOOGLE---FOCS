/**
 * Focs on a weak or missing connection.
 *
 * - What the student has already loaded (notes, lectures, flashcards, plans) is saved on this device per account,
 *   so the next visit draws at once from it while fresh data loads, and still works with no connection at all.
 * - Signing out deletes the saved copy.
 * - A small service worker (public/sw.js) keeps the app's own files, so the app opens offline too.
 */
import { dehydrate, hydrate, onlineManager, type Query, type QueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { useAuth } from "@/stores/auth";

const PREFIX = "focs-cache-v1:";
const MAX_AGE_MS = 7 * 24 * 3600_000;  // older than a week: not worth showing
const MAX_BYTES = 2_500_000;           // leaves room in localStorage for everything else
// Answers that are only right at the moment they were fetched, or are private beyond the account's own data.
const VOLATILE = new Set(["usage", "health", "health-details", "wait-task", "notifications", "active-session", "plans",
  "token-refresh", "speech-status", "room", "mock"]);

const keyFor = (userId: number) => `${PREFIX}${userId}`;

function keep(q: Query): boolean {
  if (q.state.status !== "success") return false;
  const head = String(q.queryKey[0] ?? "");
  return !VOLATILE.has(head) && !head.startsWith("admin");  // the admin panel has its own sign-in: never kept
}

function removeAllSaved() {
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (k?.startsWith(PREFIX)) localStorage.removeItem(k);
    }
  } catch { /* storage blocked */ }
}

/** Load the saved copy for whoever is signed in, then keep saving as data arrives. Returns a cleanup function. */
export function persistQueries(qc: QueryClient): () => void {
  let userId = useAuth.getState().user?.id ?? null;

  const restore = (id: number) => {
    try {
      const raw = localStorage.getItem(keyFor(id));
      if (!raw) return;
      const saved = JSON.parse(raw) as { at: number; state: unknown };
      if (Date.now() - saved.at > MAX_AGE_MS) return localStorage.removeItem(keyFor(id));
      hydrate(qc, saved.state as Parameters<typeof hydrate>[1]);
    } catch { /* a damaged copy is simply ignored */ }
  };
  if (userId) restore(userId);

  let timer: number | undefined;
  const save = () => {
    timer = undefined;
    if (!userId) return;
    try {
      const json = JSON.stringify({ at: Date.now(), state: dehydrate(qc, { shouldDehydrateQuery: keep }) });
      if (json.length <= MAX_BYTES) localStorage.setItem(keyFor(userId), json);
    } catch { /* full or blocked: the app still works, just without the saved copy */ }
  };
  const soon = () => { if (timer === undefined) timer = window.setTimeout(save, 2000); };
  const stopCache = qc.getQueryCache().subscribe((e) => { if (e.type === "updated" && e.action.type === "success") soon(); });
  const flush = () => { if (document.visibilityState === "hidden" && timer !== undefined) { clearTimeout(timer); save(); } };
  document.addEventListener("visibilitychange", flush);

  const stopAuth = useAuth.subscribe((s) => {
    const next = s.user?.id ?? null;
    if (next === userId) return;
    if (!s.token) {  // signed out: nothing of theirs stays on this device
      removeAllSaved();
      qc.clear();
    } else if (next) {
      restore(next);
    }
    userId = next;
  });

  return () => { stopCache(); stopAuth(); document.removeEventListener("visibilitychange", flush); if (timer) clearTimeout(timer); };
}

/** True while the browser has a connection. */
export function useOnline(): boolean {
  return useSyncExternalStore((cb) => onlineManager.subscribe(cb), () => onlineManager.isOnline(), () => true);
}

/** A slow or data-saving connection: features can do less (fewer frames, no decorative motion). */
export function slowConnection(): boolean {
  const c = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
  return !!c && (c.saveData === true || c.effectiveType === "slow-2g" || c.effectiveType === "2g");
}

/** Register the service worker in production builds (it would serve stale files to the dev server). */
export function registerServiceWorker() {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}
