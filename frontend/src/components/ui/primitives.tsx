import { motion } from "motion/react";
import { forwardRef, useEffect, useId, useRef, useState, type CSSProperties, type HTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- Card */
export function Card({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("panel", className)} {...p} />;
}

export function CardHeader({ title, subtitle, action, icon, className }: {
  title: ReactNode; subtitle?: ReactNode; action?: ReactNode; icon?: ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3 px-5 pt-5", className)}>
      <div className="flex min-w-0 items-start gap-3">
        {icon && <div className="grid h-9 w-9 shrink-0 place-items-center rounded-sm border border-line-strong text-fg">{icon}</div>}
        <div className="min-w-0">
          <h3 className="font-display text-[13px] font-semibold uppercase tracking-[0.14em]">{title}</h3>
          {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

/* ---------------------------------------------------------------- Badge */
type Tone = "neutral" | "accent" | "ok" | "warn" | "bad" | "cyan";
const tones: Record<Tone, string> = {
  neutral: "bg-elev-2 text-fg-soft border-line",
  accent: "bg-accent-soft text-accent border-accent/20",
  ok: "bg-ok/10 text-ok border-ok/20",
  warn: "bg-warn/10 text-warn border-warn/25",
  bad: "bg-bad/10 text-bad border-bad/20",
  cyan: "bg-accent-2/10 text-accent-2 border-accent-2/20",
};

export function Badge({ tone = "neutral", className, children, dot, ...p }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone; dot?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-display text-[10.5px] font-medium uppercase tracking-[0.1em]", tones[tone], className)} {...p}>
      {dot && <span className="h-1.5 w-1.5 rounded-full" style={{ background: dot }} />}
      {children}
    </span>
  );
}

/* ---------------------------------------------------------------- Inputs */
const field = "field";  // index.css: the board's soft well, the notebook's ink-outlined box with a highlighter focus

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...p }, ref) {
  return <input ref={ref} className={cn(field, "h-11", className)} {...p} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...p }, ref) {
  return <textarea ref={ref} className={cn(field, "min-h-24 py-3 leading-relaxed", className)} {...p} />;
});

export function Select({ className, children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(field, "h-11 cursor-pointer appearance-none bg-[length:16px] bg-[right_12px_center] bg-no-repeat pr-9", className)}
      style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%237d7d92' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")" }}
      {...p}>
      {children}
    </select>
  );
}

export function Label({ children, hint, className, htmlFor }: { children: ReactNode; hint?: ReactNode; className?: string; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className={cn("mb-1.5 flex items-center justify-between text-[13px] font-medium text-fg-soft", className)}>
      {children}
      {hint && <span className="font-normal text-muted">{hint}</span>}
    </label>
  );
}

/* ---------------------------------------------------------------- Feedback */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-xl", className)} />;
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded-md border border-line-strong bg-elev px-1.5 font-mono text-[10.5px] text-fg-soft shadow-[inset_0_-1px_0_var(--line-strong)]">
      {children}
    </kbd>
  );
}

export function EmptyState({ icon, title, body, action, className }: {
  icon: ReactNode; title: string; body?: ReactNode; action?: ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-14 text-center", className)}>
      {/* a square tile, corner marks round it */}
      <div className="relative mb-5 grid h-14 w-14 place-items-center rounded-sm border border-line-strong bg-elev text-fg">
        <span aria-hidden className="brackets -inset-2 [--arm:9px]" />
        {icon}
      </div>
      <h3 className="font-display text-[13px] font-semibold uppercase tracking-[0.16em]">{title}</h3>
      {body && <p className="mt-1.5 max-w-sm text-sm text-muted">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ProgressBar({ value, className, tone = "accent" }: { value: number; className?: string; tone?: "accent" | "ok" | "warn" | "bad" }) {
  // a rule of ink filling a hairline track
  const bg = { accent: "bg-accent", ok: "bg-ok", warn: "bg-warn", bad: "bg-bad" }[tone];
  return (
    <div className={cn("h-1.5 w-full overflow-hidden bg-elev-2", className)}>
      <div className={cn("grow-x h-full transition-[width] duration-700", bg)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function ProgressRing({ value, size = 64, stroke = 6, children, color }: {
  value: number; size?: number; stroke?: number; children?: ReactNode; color?: string;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  const id = `ring-${useId().replace(/:/g, "")}`;
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--accent)" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--elev-2)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color ?? `url(#${id})`} strokeWidth={stroke}
          strokeLinecap="butt" strokeDasharray={c} strokeDashoffset={c - (pct / 100) * c} className="draw-ring"
          style={{ transition: "stroke-dashoffset .8s cubic-bezier(.2,.8,.2,1)", "--ring-length": c } as CSSProperties} />
      </svg>
      <div className="absolute inset-0 grid place-items-center">{children}</div>
    </div>
  );
}

/* ---------------------------------------------------------------- Segmented control / tabs */
export function Segmented<T extends string>({ value, onChange, options, className, size = "md" }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; icon?: ReactNode }[]; className?: string; size?: "sm" | "md";
}) {
  const pill = useId();  // the selected option's backing slides from the old choice to the new one
  // a row wider than the screen slides sideways; fade the edge that has more to show so that is visible
  const ref = useRef<HTMLDivElement>(null);
  const [edge, setEdge] = useState("");
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const l = el.scrollLeft > 2, r = el.scrollLeft + el.clientWidth < el.scrollWidth - 2;
      setEdge(l && r ? "scroll-fade-both" : r ? "scroll-fade-right" : l ? "scroll-fade-left" : "");
    };
    measure();
    el.addEventListener("scroll", measure, { passive: true });
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => { el.removeEventListener("scroll", measure); ro.disconnect(); };
  }, []);
  useEffect(() => {  // keep the chosen tab in view when it sits past the edge
    const el = ref.current, on = el?.querySelector<HTMLElement>("[aria-selected=true]");
    if (!el || !on || el.scrollWidth <= el.clientWidth) return;
    const left = on.offsetLeft - el.offsetLeft;
    if (left < el.scrollLeft || left + on.offsetWidth > el.scrollLeft + el.clientWidth) el.scrollTo({ left: left - 24, behavior: "smooth" });
  }, [value]);
  return (
    <div ref={ref} className={cn("seg no-scrollbar inline-flex max-w-full overflow-x-auto overscroll-x-contain rounded-sm p-1", edge, className)} role="tablist">
      {options.map((o) => (
        <button key={o.value} type="button" role="tab" aria-selected={value === o.value} onClick={() => onChange(o.value)}
          className={cn(
            "relative inline-flex shrink-0 items-center whitespace-nowrap rounded-sm font-display font-medium uppercase tracking-[0.1em] transition-colors duration-200",
            size === "sm" ? "h-7 px-2.5 text-[10.5px] pointer-coarse:h-10" : "h-8 px-3 text-[11.5px] pointer-coarse:h-10",
            value === o.value ? "seg-on" : "text-muted hover:text-fg",
          )}>
          {/* a block of ink behind the chosen option */}
          {value === o.value && (
            <motion.span layoutId={pill} className="seg-pill absolute inset-0 rounded-sm"
              transition={{ type: "spring", stiffness: 440, damping: 36 }} />
          )}
          <span className="relative inline-flex items-center gap-1.5">{o.icon}{o.label}</span>
        </button>
      ))}
    </div>
  );
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
      className={cn("relative h-6 w-10 shrink-0 rounded-full before:absolute before:-inset-2.5 before:content-[''] border transition", checked ? "border-transparent bg-accent" : "border-line-strong bg-elev-2")}>
      <span className={cn("absolute top-0.5 h-4.5 w-4.5 rounded-full transition-all", checked ? "left-[18px] bg-accent-fg" : "left-0.5 bg-fg/70")} />
    </button>
  );
}
