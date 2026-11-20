import { WifiOff } from "lucide-react";
import { useOnline } from "@/lib/offline";

/** Said once, at the top, while there is no connection: what still works and what will wait. */
export function OfflineBanner() {
  const online = useOnline();
  if (online) return null;
  return (
    <div role="status" className="no-print fixed inset-x-0 top-0 z-[80] flex items-center justify-center gap-2 bg-warn px-4 pb-2 pt-[calc(0.5rem+env(safe-area-inset-top))] text-center text-[13px] font-medium text-bg">
      <WifiOff className="h-4 w-4 shrink-0" aria-hidden />
      You're offline. Notes, lectures and flashcards you've opened before still work; anything you send goes when you're back.
    </div>
  );
}
