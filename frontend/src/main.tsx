// Geist for reading, Jost (a geometric face in the Futura tradition) for headlines, labels and buttons, Geist Mono for
// code. A browser downloads only the faces a page actually uses.
import "@fontsource-variable/geist";
import "@fontsource-variable/jost";
import "@fontsource-variable/jost/wght-italic.css";
import "@fontsource-variable/geist-mono";
// Hindi notes: Geist has no Devanagari letters
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-devanagari/600.css";
// Settings → Accessibility: a font made for legibility
import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "./index.css";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { toast } from "sonner";
import App from "./App";
import { ApiError } from "./lib/api";
import { initMonitoring } from "./lib/monitoring";
import { persistQueries, registerServiceWorker } from "./lib/offline";
import { useA11y } from "./stores/a11y";

const openPlans = () => {
  // tell react-router about the new URL without reloading the app
  window.history.pushState({}, "", "/app/settings#plan");
  window.dispatchEvent(new PopStateEvent("popstate"));
};

const onError = (err: unknown) => {
  if (err instanceof ApiError && err.status === 401) return; // handled by redirect to sign-in
  if (err instanceof ApiError && err.status === 0 && !navigator.onLine) return; // the offline banner says it once
  if (err instanceof ApiError && err.status === 402) {
    // AI allowance or mock-test quota used up: say when it resets and offer the plans
    queryClient.invalidateQueries({ queryKey: ["usage"] });
    toast.warning(err.message, { duration: 9000, action: { label: "See plans", onClick: openPlans } });
    return;
  }
  toast.error(err instanceof Error ? err.message : "Something went wrong");
};

const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({ onError }),
  mutationCache: new MutationCache({ onError, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["usage"] }) }),
  defaultOptions: {
    queries: {
      staleTime: 20_000,
      // a dropped or slow connection (status 0) is worth more tries than a server error
      retry: (count, err) => !(err instanceof ApiError && err.status < 500 && err.status !== 0)
        && count < (err instanceof ApiError && err.status === 0 ? 4 : 2),
      retryDelay: (n) => Math.min(1000 * 2 ** n, 15_000) + Math.random() * 500,  // spread out, not a burst
      refetchOnWindowFocus: false,
      gcTime: 24 * 3600_000,  // kept around so the saved copy can be shown offline
    },
  },
});

persistQueries(queryClient);  // last-seen data shows at once, and offline
registerServiceWorker();      // the app's own files open without a connection
initMonitoring();  // error reports, when VITE_SENTRY_DSN is set
useA11y.persist.rehydrate();  // text size, spacing, font, contrast and motion apply before the first paint

// A soft light follows the pointer across any card that can be opened (.lift reads --mx and --my in index.css).
document.addEventListener("pointermove", (e) => {
  const card = (e.target as Element | null)?.closest?.(".lift") as HTMLElement | null;
  if (!card) return;
  const r = card.getBoundingClientRect();
  card.style.setProperty("--mx", `${e.clientX - r.left}px`);
  card.style.setProperty("--my", `${e.clientY - r.top}px`);
}, { passive: true });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);

// Focs doesn't ask to be installed: this keeps the browser's own banner away too
window.addEventListener("beforeinstallprompt", (e) => e.preventDefault());
