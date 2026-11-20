// Only what Focs uses from Sentry, so the build drops the rest (session replay, the feedback widget, tracing).
// Loaded lazily by monitoring.ts.
export { captureException, init } from "@sentry/react";
