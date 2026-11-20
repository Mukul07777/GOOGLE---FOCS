import { useEffect, useRef, useState, type ReactNode } from "react";
import { Dialog } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/** Content that may be wider than its place (a table in a chat bubble, a row of tabs): it slides left and right
    instead of spilling out, and fades at whichever edge has more to show. */
export function ScrollX({ children, className, quiet, hint }: {
  children: ReactNode; className?: string;
  /** no scrollbar (tabs, chips): the fade is the only cue */
  quiet?: boolean;
  /** say "slide to see more" under it while part is out of view, with a button that opens it full width (tables) */
  hint?: boolean;
}) {
  const [wide, setWide] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const [more, setMore] = useState({ left: false, right: false });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const left = el.scrollLeft > 2, right = el.scrollLeft + el.clientWidth < el.scrollWidth - 2;
      setMore((m) => (m.left === left && m.right === right ? m : { left, right }));
    };
    measure();
    el.addEventListener("scroll", measure, { passive: true });
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    if (el.firstElementChild) ro.observe(el.firstElementChild);
    return () => { el.removeEventListener("scroll", measure); ro.disconnect(); };
  }, []);
  const edge = more.left && more.right ? "scroll-fade-both" : more.right ? "scroll-fade-right" : more.left ? "scroll-fade-left" : "";
  return (
    <>
      <div ref={ref} className={cn("max-w-full overflow-x-auto overscroll-x-contain", quiet && "no-scrollbar", edge, className)}
        tabIndex={more.left || more.right ? 0 : undefined}>
        {children}
      </div>
      {hint && (more.left || more.right) && (
        <div className="no-print mt-1 flex flex-wrap items-center gap-x-3 text-[12px] text-muted">
          Slide sideways to see the whole table, or
          <button type="button" onClick={() => setWide(true)} className="inline-flex min-h-8 items-center font-medium text-accent hover:underline">
            open it full width
          </button>
        </div>
      )}
      {hint && (
        <Dialog open={wide} onClose={() => setWide(false)} wide title="Table" className="sm:max-w-[min(96vw,1400px)]">
          <div className="prose-notes overflow-auto">{children}</div>
        </Dialog>
      )}
    </>
  );
}
