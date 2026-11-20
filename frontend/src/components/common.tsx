import { ImageOff } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useBackClose } from "@/lib/overlay";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- Logo */
/** The mark: a square of ink with the focus ring cut into it, in the page's own colours (black on Stone, ivory on
    Ink). public/favicon.svg draws it too. */
const LOGO_GOLD = "#C9975B";  // the logo's gold, the same in both themes (public/favicon.svg and the icons match)

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn("h-8 w-8", className)} aria-hidden>
      {/* a viewfinder framing the board, and in it the one point that matters: in focus */}
      <path d="M5 20V5h15M44 5h15v15M59 44v15H44M20 59H5V44" fill="none" stroke="var(--fg)" strokeWidth="6"
        strokeLinecap="round" strokeLinejoin="round" />
      <path d="M21 28v-7h7M36 21h7v7M43 36v7h-7M28 43h-7v-7" fill="none" stroke={LOGO_GOLD} strokeWidth="3.5"
        strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="32" cy="32" r="4.5" fill={LOGO_GOLD} />
    </svg>
  );
}

/** The mark and the name, in wide Jost capitals like a label's wordmark. */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark className="h-7 w-7" />
      <span className="font-brand text-[22px] font-medium uppercase leading-none tracking-[0.14em]">Focs</span>
    </span>
  );
}

/* ---------------------------------------------------------------- Auth-protected board snapshot */
const imageCache = new Map<string, string>();

/** `version` (e.g. the note's updated_at) busts the cache when a growing board replaces its snapshot. */
export function BoardImage({ noteId, version, className, onClick }: {
  noteId: number; version?: string | null; className?: string; onClick?: (src: string) => void;
}) {
  const key = `${noteId}:${version ?? ""}`;
  const [src, setSrc] = useState<string | null>(imageCache.get(key) ?? null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const cached = imageCache.get(key);
    if (cached) return setSrc(cached);
    let cancelled = false;
    api.noteImage(noteId)
      .then((r) => r.blob())
      .then((b) => {
        const url = URL.createObjectURL(b);
        imageCache.set(key, url);
        if (!cancelled) setSrc(url);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [noteId, key]);

  if (failed)
    return (
      <div className={cn("grid place-items-center bg-elev-2 text-muted", className)}>
        <ImageOff className="h-5 w-5" />
      </div>
    );
  if (!src) return <div className={cn("skeleton", className)} />;
  return (
    <img src={src} alt="Board snapshot" onClick={() => onClick?.(src)} loading="lazy"
      className={cn("object-cover", onClick && "cursor-zoom-in", className)} />
  );
}

/* ---------------------------------------------------------------- Activity heatmap */
export function PageHeader({ title, subtitle, actions, eyebrow }: {
  title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; eyebrow?: React.ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <div className="eyebrow mb-3">{eyebrow}</div>}
        <h1 className="display-caps text-[34px] sm:text-[46px]">{title}</h1>
        {subtitle && <p className="mt-2.5 max-w-2xl text-[15px] leading-relaxed text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ---------------------------------------------------------------- Image lightbox */
export function Lightbox({ src, onClose }: { src: string | null; onClose: () => void }) {
  useBackClose(!!src, onClose);
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  if (!src) return null;
  return (
    <div className="fixed inset-0 z-[60] grid cursor-zoom-out place-items-center bg-black/85 p-6 backdrop-blur" onClick={onClose}>
      <img src={src} alt="Board" className="max-h-full max-w-full" />
    </div>
  );
}
