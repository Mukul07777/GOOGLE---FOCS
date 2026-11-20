import { Eraser, Maximize2, Minimize2, PenLine, ScanSearch, Trash2, Undo2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Rough work under a question, like the rough sheet in a real exam hall: a page per question, drawn with a stylus,
 * a finger or a mouse. Points are stored as fractions of the pad's width, so a page survives the tablet turning.
 * Once a stylus touches the pad, fingers scroll it instead of drawing (a resting palm leaves no marks).
 * Pages live in sessionStorage per test: a refresh keeps them. Nothing is sent to the server unless the student taps
 * "Check my working" (``onCheck``): then the page goes, as a clean black-on-white picture, to be read step by step.
 */
type Stroke = { e?: 1; w: number; p: number[] };  // e: eraser; w: width (fraction of pad width); p: x0,y0,x1,y1...
type Pages = Record<string, Stroke[]>;

const NONE: Stroke[] = [];
const TALL = 2.4;  // the page is this many pad-widths tall: room to scroll down for a long solution

function load(key: string): Pages {
  try { return JSON.parse(sessionStorage.getItem(key) || "{}") as Pages; } catch { return {}; }
}

/** The strokes of one saved page (a mock's rough work, read again on the review screen). */
export function savedPage(storageKey: string, page: string): Stroke[] {
  return load(storageKey)[page] ?? [];
}

/** One page as a picture the reader can see clearly: black ink on white, cropped to the writing, whatever the theme. */
export function roughImage(strokes: Stroke[]): Promise<Blob | null> {
  const ink = strokes.filter((s) => !s.e);
  if (!ink.length) return Promise.resolve(null);
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const s of ink) for (let i = 0; i < s.p.length; i += 2) {
    x0 = Math.min(x0, s.p[i]); x1 = Math.max(x1, s.p[i]); y0 = Math.min(y0, s.p[i + 1]); y1 = Math.max(y1, s.p[i + 1]);
  }
  const PX = 1100, padding = 0.04;  // pixels per pad width: big enough for small handwriting
  x0 -= padding; y0 -= padding; x1 += padding; y1 += padding;
  const w = Math.max(240, Math.round((x1 - x0) * PX)), h = Math.min(4000, Math.max(160, Math.round((y1 - y0) * PX)));
  const layer = document.createElement("canvas");
  layer.width = w; layer.height = h;
  const g = layer.getContext("2d");
  if (!g) return Promise.resolve(null);
  g.lineCap = "round"; g.lineJoin = "round";
  for (const s of strokes) {  // the eraser cuts the ink on its own layer, so the white page underneath stays white
    g.globalCompositeOperation = s.e ? "destination-out" : "source-over";
    g.strokeStyle = "#111";
    g.lineWidth = Math.max(2, s.w * PX);
    g.beginPath();
    for (let i = 0; i < s.p.length; i += 2) {
      const x = (s.p[i] - x0) * PX, y = (s.p[i + 1] - y0) * PX;
      if (i === 0) { g.moveTo(x, y); g.lineTo(x + 0.01, y); } else g.lineTo(x, y);
    }
    g.stroke();
  }
  const page = document.createElement("canvas");
  page.width = w; page.height = h;
  const p = page.getContext("2d");
  if (!p) return Promise.resolve(null);
  p.fillStyle = "#fff";
  p.fillRect(0, 0, w, h);
  p.drawImage(layer, 0, 0);
  return new Promise((done) => page.toBlob((b) => done(b), "image/png"));
}

export function RoughPad({ storageKey, page, onClose, className, onCheck, checking }: {
  storageKey: string; page: string; onClose: () => void; className?: string;
  /** given: a "Check my working" button that hands over this page as a picture */
  onCheck?: (image: Blob) => void; checking?: boolean;
}) {
  const [pages, setPages] = useState<Pages>(() => load(storageKey));
  const [tool, setTool] = useState<"pen" | "eraser">("pen");
  const [big, setBig] = useState(false);
  const [penSeen, setPenSeen] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const drawing = useRef<{ id: number; stroke: Stroke } | null>(null);
  const strokes = pages[page] ?? NONE;

  useEffect(() => {
    try { sessionStorage.setItem(storageKey, JSON.stringify(pages)); } catch { /* full or private: the pad still works */ }
  }, [pages, storageKey]);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const height = Math.round(width * TALL);
  const paint = useCallback((list: Stroke[]) => {
    const c = canvas.current;
    if (!c || !width) return;
    const dpr = window.devicePixelRatio || 1;
    if (c.width !== Math.round(width * dpr)) { c.width = Math.round(width * dpr); c.height = Math.round(height * dpr); }
    const g = c.getContext("2d");
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, width, height);
    const ink = getComputedStyle(c).color || "#111";
    g.lineCap = "round";
    g.lineJoin = "round";
    for (const s of list) {
      g.globalCompositeOperation = s.e ? "destination-out" : "source-over";
      g.strokeStyle = ink;
      g.lineWidth = s.w * width;
      g.beginPath();
      for (let i = 0; i < s.p.length; i += 2) {
        const x = s.p[i] * width, y = s.p[i + 1] * width;
        if (i === 0) { g.moveTo(x, y); g.lineTo(x + 0.01, y); } else g.lineTo(x, y);
      }
      g.stroke();
    }
    g.globalCompositeOperation = "source-over";
  }, [width, height]);

  useEffect(() => { paint(strokes); }, [paint, strokes]);
  useEffect(() => { // the theme changed: ink follows it
    const mo = new MutationObserver(() => paint(pages[page] ?? []));
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => mo.disconnect();
  }, [paint, pages, page]);

  const point = (e: React.PointerEvent) => {
    const r = canvas.current!.getBoundingClientRect();
    return [Math.round(((e.clientX - r.left) / width) * 10000) / 10000, Math.round(((e.clientY - r.top) / width) * 10000) / 10000];
  };
  const down = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (e.pointerType === "pen" && !penSeen) setPenSeen(true);
    if (e.pointerType === "touch" && penSeen) return;  // a palm, or a finger scrolling
    if (e.button > 0 && e.pointerType === "mouse") return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const eraser = tool === "eraser" || e.button === 5;  // a stylus's eraser end
    const w = eraser ? 22 / width : (e.pointerType === "pen" ? 1.6 + 1.6 * (e.pressure || 0.5) : 2.4) / width;
    drawing.current = { id: e.pointerId, stroke: { ...(eraser ? { e: 1 as const } : {}), w, p: point(e) } };
  };
  const move = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const d = drawing.current;
    if (!d || d.id !== e.pointerId) return;
    const events = (e.nativeEvent as PointerEvent).getCoalescedEvents?.() ?? [e.nativeEvent];
    for (const ev of events) d.stroke.p.push(...point(ev as unknown as React.PointerEvent));
    paint([...strokes, d.stroke]);
  };
  const up = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const d = drawing.current;
    if (!d || d.id !== e.pointerId) return;
    drawing.current = null;
    setPages((all) => ({ ...all, [page]: [...(all[page] ?? []), d.stroke] }));
  };
  const undo = () => setPages((all) => ({ ...all, [page]: (all[page] ?? []).slice(0, -1) }));
  const clear = () => setPages((all) => { const next = { ...all }; delete next[page]; return next; });
  const check = async () => {
    const image = await roughImage(strokes);
    if (image && onCheck) onCheck(image);
  };

  const tb = "grid h-10 w-10 place-items-center rounded-lg text-muted transition hover:bg-elev-2 hover:text-fg disabled:opacity-40";
  return (
    <section aria-label="Rough work" className={cn("flex min-h-0 flex-col border-t-2 border-line-strong bg-panel", big ? "h-[78%]" : "h-[46%]", className)}>
      <div className="flex items-center gap-1 border-b border-line px-2 py-1">
        <span className="px-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Rough</span>
        <button type="button" className={cn(tb, tool === "pen" && "bg-elev-2 text-fg")} aria-pressed={tool === "pen"} onClick={() => setTool("pen")} title="Pen" aria-label="Pen"><PenLine className="h-4 w-4" /></button>
        <button type="button" className={cn(tb, tool === "eraser" && "bg-elev-2 text-fg")} aria-pressed={tool === "eraser"} onClick={() => setTool("eraser")} title="Eraser" aria-label="Eraser"><Eraser className="h-4 w-4" /></button>
        <button type="button" className={tb} onClick={undo} disabled={!strokes.length} title="Undo" aria-label="Undo"><Undo2 className="h-4 w-4" /></button>
        <button type="button" className={tb} onClick={clear} disabled={!strokes.length} title="Clear this page" aria-label="Clear this page"><Trash2 className="h-4 w-4" /></button>
        <span className="min-w-0 flex-1 truncate px-1 text-[11px] text-muted">{penSeen ? "Stylus: fingers scroll" : "A page for each question"}</span>
        {onCheck && (
          <Button size="sm" variant="primary" className="shrink-0" onClick={check} disabled={!strokes.length} loading={checking}
            icon={<ScanSearch className="h-3.5 w-3.5" />} title="Focs reads your steps and finds the first one that went wrong">
            {checking ? "Reading…" : <><span className="hidden min-[420px]:inline">Check my working</span><span className="min-[420px]:hidden">Check</span></>}
          </Button>
        )}
        <button type="button" className={tb} onClick={() => setBig(!big)} title={big ? "Smaller" : "Bigger"} aria-label={big ? "Make the rough pad smaller" : "Make the rough pad bigger"}>
          {big ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
        <button type="button" className={tb} onClick={onClose} title="Close rough work" aria-label="Close rough work"><X className="h-4 w-4" /></button>
      </div>
      <div ref={box} className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
        style={{ backgroundImage: "radial-gradient(circle, color-mix(in srgb, currentColor 14%, transparent) 1px, transparent 1px)", backgroundSize: "22px 22px", backgroundAttachment: "local" }}>
        <canvas ref={canvas} className="block text-fg" style={{ width, height, touchAction: penSeen ? "pan-y" : "none", cursor: tool === "eraser" ? "cell" : "crosshair" }}
          onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} />
      </div>
    </section>
  );
}
