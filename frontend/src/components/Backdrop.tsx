import { type CSSProperties, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/* The page behind every page: a faint grid under the aurora (the body's own background), and on wide screens Focs's
   AI layer at work in the margins: formulas off a lecture board that FocsOCR has picked out, each locked in focus
   brackets with its confidence, and line diagrams drawn in light. On a landing page a reading line passes down once as
   it opens and each formula locks as the line reaches it. Decoration only: hidden from screen readers, and the
   formulas' text is drawn by CSS, so nothing reads it out. Styles: index.css (backdrop). */

type Spot = { left?: string; right?: string; top?: string; bottom?: string };
type Det = Spot & { text: string; conf: string; size?: number };
type Holo = Spot & { draw: keyof typeof DRAWINGS; width: number; turn?: number };

/** Diagrams from a physics, chemistry and maths board: a wave, a right triangle with θ, benzene, a parabola, a circuit,
    a free-body box and an atom. */
const DRAWINGS = {
  wave: { box: "0 0 120 40", body: <path d="M2 20H118M4 20C13 3 22 3 31 20S49 37 58 20 76 3 85 20 103 37 112 20" /> },
  triangle: {
    box: "0 0 100 80",
    body: <path d="M8 72H92V10ZM82 72V62H92M30 72A22 22 0 0 0 25.7 58.9" />,
  },
  benzene: { box: "0 0 80 80", body: <path d="M40 6L69 23V57L40 74 11 57V23ZM24 40a16 16 0 1 0 32 0a16 16 0 1 0 -32 0" /> },
  parabola: { box: "0 0 100 90", body: <path d="M8 78H96M92 74L96 78 92 82M50 86V4M46 8L50 4 54 8M16 10Q50 142 84 10" /> },
  circuit: { box: "0 0 140 36", body: <path d="M2 18H34L39 6 47 30 55 6 63 30 71 6 79 30 84 18H104M104 8V28M110 4V32M110 18H138" /> },
  forces: {
    box: "0 0 84 100",
    body: <path d="M24 38H56V62H24ZM40 38V8M34 15L40 7 46 15M40 62V92M34 85L40 93 46 85M56 50H78M71 44L79 50 71 56" />,
  },
  atom: {
    box: "0 0 90 90",
    body: (
      <>
        <ellipse cx="45" cy="45" rx="40" ry="14" />
        <ellipse cx="45" cy="45" rx="40" ry="14" transform="rotate(60 45 45)" />
        <ellipse cx="45" cy="45" rx="40" ry="14" transform="rotate(-60 45 45)" />
        <circle cx="45" cy="45" r="4" />
      </>
    ),
  },
} satisfies Record<string, { box: string; body: ReactNode }>;

interface Scene {
  /** a page that scrolls carries its backdrop with it; the app's stays put while its panel scrolls */
  scroll?: boolean;
  quiet?: boolean;
  /** FocsOCR reads the page once as it opens */
  scan?: boolean;
  /** beside the first screen, from 1536 px: the margins of a 1152 px page */
  dets?: Det[];
  holos?: Holo[];
  /** further down a long page, at the very edges */
  far?: { dets: Det[]; holos: Holo[] };
  /** where the notes may appear, as a Tailwind display class */
  from?: string;
}

const LANDING: Scene = {
  scroll: true,
  scan: true,
  dets: [
    { text: "τ = r × F", conf: "ocr 0.98", left: "3%", top: "230px" },
    { text: "PV = nRT", conf: "ocr 0.99", left: "4.5%", top: "470px" },
    { text: "Σ F = ma", conf: "ocr 0.98", left: "2.5%", top: "700px" },
    { text: "∫ x² dx = x³/3 + C", conf: "ocr 0.96", right: "2.5%", top: "250px", size: 20 },
    { text: "E = mc²", conf: "ocr 0.99", right: "4%", top: "520px" },
    { text: "λ = h / p", conf: "ocr 0.97", right: "3%", top: "730px" },
  ],
  holos: [
    { draw: "wave", left: "3%", top: "350px", width: 120 },
    { draw: "triangle", right: "4.5%", top: "370px", width: 84 },
    { draw: "atom", left: "4%", top: "560px", width: 72 },
    { draw: "benzene", right: "6%", top: "610px", width: 60, turn: 8 },
  ],
  far: {
    dets: [
      { text: "sin²θ + cos²θ = 1", conf: "ocr 0.95", left: "1.6%", top: "28%", size: 19 },
      { text: "Δ = b² − 4ac", conf: "ocr 0.97", right: "1.8%", top: "40%", size: 20 },
      { text: "F = −kx", conf: "ocr 0.99", left: "2.4%", top: "57%" },
      { text: "H₂O", conf: "ocr 0.99", right: "3%", top: "72%" },
    ],
    holos: [
      { draw: "circuit", right: "1.6%", top: "50%", width: 118 },
      { draw: "parabola", left: "2.4%", top: "82%", width: 84 },
      { draw: "forces", right: "2.6%", top: "86%", width: 60 },
    ],
  },
};

const SCENES: Record<"landing" | "bridge" | "auth" | "app" | "plain", Scene> = {
  landing: LANDING,
  bridge: LANDING,
  auth: {
    from: "xl:block",
    dets: [
      { text: "τ = r × F", conf: "ocr 0.98", right: "7%", top: "8%" },
      { text: "E = mc²", conf: "ocr 0.99", right: "9%", bottom: "9%" },
    ],
    holos: [{ draw: "wave", right: "4%", top: "46%", width: 104 }],
  },
  app: { quiet: true },
  plain: { quiet: true },
};

const spot = ({ left, right, top, bottom }: Spot, turn = 0): CSSProperties =>
  ({ left, right, top, bottom, transform: turn ? `rotate(${turn}deg)` : undefined });

/** When the reading line (moving at a steady speed from 80 px above the page to 780 px down) reaches `top`. */
const readAt = (top?: string) => (top?.endsWith("px") ? `${(0.6 + (3 * (parseFloat(top) + 95)) / 860).toFixed(2)}s` : undefined);

function Detection({ text, conf, size, scan, ...at }: Det & { scan?: boolean }) {
  const read = scan ? readAt(at.top) : undefined;
  return (
    <span className={cn("det", read && "det-read")} data-conf={conf}
      style={{ ...spot(at), fontSize: size, "--read-at": read } as CSSProperties}>
      <span className="det-text" data-text={text} />
    </span>
  );
}

function Diagram({ draw, width, turn, ...at }: Holo) {
  const { box, body } = DRAWINGS[draw];
  return (
    <span className="absolute" style={spot(at, turn)}>
      <svg viewBox={box} width={width} className="holo" focusable="false">{body}</svg>
    </span>
  );
}

export function Backdrop({ scene, className }: { scene: keyof typeof SCENES; className?: string }) {
  const s = SCENES[scene];
  return (
    <div aria-hidden className={cn("backdrop print:hidden", s.scroll ? "absolute" : "fixed", s.quiet && "backdrop-quiet", className)}>
      <div className="bd-grid" />
      {(s.dets || s.holos) && (
        <div className={cn("absolute inset-0 hidden", s.from ?? "2xl:block")}>
          {s.dets?.map((d) => <Detection key={d.text} {...d} scan={s.scan} />)}
          {s.holos?.map((h, i) => <Diagram key={i} {...h} />)}
        </div>
      )}
      {s.far && (
        <div className="absolute inset-0 hidden 2xl:block">
          {s.far.dets.map((d) => <Detection key={d.text} {...d} />)}
          {s.far.holos.map((h, i) => <Diagram key={i} {...h} />)}
        </div>
      )}
      {s.scan && <div className="backdrop-scan" />}
    </div>
  );
}
