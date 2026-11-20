import { RefreshCw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { LogoMark } from "@/components/common";
import { reportError } from "@/lib/monitoring";

const RELOADED_KEY = "focs-chunk-reload";

/** After a new deploy, lazily loaded pages from the old build no longer exist on the server. */
function isStaleChunk(error: Error) {
  return /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module/i
    .test(error.message);
}

/**
 * Last line of defence: a crash in one screen shows a calm recovery card instead of a blank page.
 * A missing code chunk (the app was updated while the tab was open) reloads once, silently.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (isStaleChunk(error)) {
      try {
        if (!sessionStorage.getItem(RELOADED_KEY)) {
          sessionStorage.setItem(RELOADED_KEY, "1");
          window.location.reload();
          return;
        }
      } catch { /* storage blocked: fall through to the card */ }
    }
    console.error("Focs crashed:", error, info.componentStack);
    reportError(error, { componentStack: info.componentStack, page: window.location.pathname });
  }

  render() {
    if (!this.state.error) return this.props.children;
    const stale = isStaleChunk(this.state.error);
    return (
      <div className="grid min-h-dvh place-items-center bg-bg p-6 pb-[calc(1.5rem+env(safe-area-inset-bottom))] pt-[calc(1.5rem+env(safe-area-inset-top))] text-fg">
        <div className="panel max-w-md p-8 text-center">
          <LogoMark className="mx-auto h-11 w-11" />
          <h1 className="mt-4 text-[26px]">{stale ? "Focs was just updated" : "Something went wrong on this screen"}</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            {stale ? "Reload to get the latest version — your notes and progress are safe." :
              "Your notes and progress are saved on the server. Reloading usually fixes this; if it keeps happening, tell us what you were doing."}
          </p>
          <div className="mt-6 flex justify-center gap-2">
            <button onClick={() => window.location.reload()}
              className="inline-flex h-10 items-center gap-2 rounded-xl bg-gradient-brand px-4 text-sm font-medium text-brand-fg">
              <RefreshCw className="h-4 w-4" /> Reload
            </button>
            <a href="/app" className="inline-flex h-10 items-center rounded-xl border border-line px-4 text-sm font-medium hover:bg-elev-2">Go to dashboard</a>
          </div>
        </div>
      </div>
    );
  }
}
