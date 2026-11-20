// Error reports to Sentry (project focs-frontend): every crash screen, and once Sentry has loaded, any uncaught error
// or rejected promise. Off without VITE_SENTRY_DSN (read from backend/.env at build time).
//
// Sentry's code (~30 KB gzipped) loads after the first page has drawn, so it never slows the first visit; a crash
// before then is held and sent once it arrives. No personal data: no account, email, IP, cookies or request bodies.
type Sentry = typeof import("./sentry");

const DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;
let sentry: Sentry | null = null;
const waiting: [unknown, Record<string, unknown> | undefined][] = [];

export function initMonitoring() {
  if (!DSN) return;
  const start = () => import("./sentry").then((S) => {
    S.init({
      dsn: DSN,
      environment: import.meta.env.MODE,
      tracesSampleRate: 0,  // errors only
      // a lazy page from the build before a redeploy: the error boundary reloads it, nothing to report
      ignoreErrors: [/Failed to fetch dynamically imported module/, /Importing a module script failed/, /error loading dynamically imported module/],
      beforeSend(event) {
        delete event.user;
        if (event.request) { delete event.request.cookies; delete event.request.data; }
        return event;
      },
    });
    sentry = S;
    for (const [err, extra] of waiting.splice(0)) S.captureException(err, { extra });
  }).catch(() => { /* blocked by an ad blocker or offline: the app carries on */ });
  if ("requestIdleCallback" in window) window.requestIdleCallback(start, { timeout: 4000 });
  else setTimeout(start, 2000);
}

/** A crash the app caught itself (the error boundary). */
export function reportError(err: unknown, extra?: Record<string, unknown>) {
  if (!DSN) return;
  if (sentry) sentry.captureException(err, { extra });
  else if (waiting.length < 20) waiting.push([err, extra]);
}
