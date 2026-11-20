import { X } from "lucide-react";
import { AnimatePresence, motion, useDragControls } from "motion/react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useBackClose } from "@/lib/overlay";
import { cn } from "@/lib/utils";

export function Dialog({ open, onClose, children, className, title, subtitle, dismissable = true, wide }: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  dismissable?: boolean;
  wide?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const drag = useDragControls();
  useBackClose(open && dismissable, onClose);
  useEffect(() => {
    if (!open) return;
    const before = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && dismissable) onClose();
      if (e.key !== "Tab" || !box.current) return;
      // keep keyboard focus inside the dialog while it's open
      const items = [...box.current.querySelectorAll<HTMLElement>('button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])')];
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // screen readers and keyboards start inside the dialog, and return where they were when it closes
    const t = setTimeout(() => box.current?.focus(), 30);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
      before?.focus?.();
    };
  }, [open, onClose, dismissable]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-6"
          initial={{ opacity: 0 }} animate={{ opacity: 1, pointerEvents: "auto" }} exit={{ opacity: 0, pointerEvents: "none" }}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => dismissable && onClose()} />
          <motion.div role="dialog" aria-modal="true" ref={box} tabIndex={-1} aria-labelledby={title ? titleId : undefined}
            className={cn("panel relative z-10 max-h-[92dvh] outline-none w-full overflow-y-auto rounded-b-none sm:rounded-2xl",
              wide ? "sm:max-w-3xl" : "sm:max-w-lg", className)}
            drag={dismissable ? "y" : false} dragListener={false} dragControls={drag} dragConstraints={{ top: 0, bottom: 0 }} dragElastic={{ top: 0, bottom: 0.7 }}
            onDragEnd={(_, info) => { if (info.offset.y > 90 || info.velocity.y > 600) onClose(); }}
            initial={{ y: 24, scale: 0.98, opacity: 0 }} animate={{ y: 0, scale: 1, opacity: 1 }}
            exit={{ y: 16, scale: 0.98, opacity: 0 }} transition={{ type: "spring", stiffness: 380, damping: 32 }}>
            {dismissable && (  // on a phone a sheet comes away by its handle, like any other
              <div onPointerDown={(e) => drag.start(e)} className="flex touch-none justify-center pt-2.5 pb-1 sm:hidden" aria-hidden>
                <span className="h-1 w-10 rounded-full bg-line-strong" />
              </div>
            )}
            {(title || dismissable) && (
              <div className="flex items-start justify-between gap-4 px-6 pt-6">
                <div>
                  {title && <h2 id={titleId} className="font-display text-[26px] leading-tight tracking-tight">{title}</h2>}
                  {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
                </div>
                {dismissable && (
                  <button type="button" onClick={onClose} aria-label="Close" className="-mr-2 -mt-1 rounded-lg p-2.5 text-muted hover:bg-elev-2 hover:text-fg">
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}
            <div className="px-6 pb-6 pt-4">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
