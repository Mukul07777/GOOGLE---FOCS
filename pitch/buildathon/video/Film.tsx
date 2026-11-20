// FOCS · Startup Buildathon film. Light, like the app: warm paper, ink type, one gold accent; the real app in a browser.
import React from "react";
import {
  AbsoluteFill, Audio, Easing, Img, interpolate, OffthreadVideo, Sequence, Series, spring, staticFile, useCurrentFrame,
} from "remotion";
import { CHECK, FPS, scene, SCENES, segStarts, SUBS, TEACHER, TOTAL, TOUR, TRACE, voLen, when, type Seg } from "./timeline";

export const C = {
  bg: "#efede9", paper: "#f8f7f4", card: "#ffffff", ink: "#0d0d0d", soft: "#2b2a28", muted: "#6b6862",
  line: "rgba(13,13,13,0.10)", lineStrong: "rgba(13,13,13,0.22)", gold: "#C9975B", goldDeep: "#9a6a2f",
  red: "#c0283a", redSoft: "rgba(192,40,58,0.10)", green: "#1f7a4a", greenSoft: "rgba(31,122,74,0.12)",
};
const F = { display: "Jost, sans-serif", sans: "Geist, sans-serif", mono: "'Geist Mono', monospace", serif: "'Instrument Serif', serif",
  indic: "'Nirmala UI', 'Noto Sans', sans-serif" };
const ease = Easing.bezier(0.16, 1, 0.3, 1);
const sec = (s: number) => Math.round(s * FPS);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const fade = (f: number, a: number, b: number) => interpolate(f, [sec(a), sec(b)], [0, 1], { ...clamp, easing: ease });

const Fonts = () => (
  <style>{`
    @font-face { font-family: Jost; src: url(${staticFile("fonts/jost-latin-wght-normal.woff2")}) format("woff2"); font-weight: 100 900; }
    @font-face { font-family: Geist; src: url(${staticFile("fonts/geist-latin-wght-normal.woff2")}) format("woff2"); font-weight: 100 900; }
    @font-face { font-family: 'Geist Mono'; src: url(${staticFile("fonts/geist-mono-latin-wght-normal.woff2")}) format("woff2"); font-weight: 100 900; }
    @font-face { font-family: 'Instrument Serif'; src: url(${staticFile("fonts/instrument-serif-latin-400-italic.woff2")}) format("woff2"); font-style: italic; }
  `}</style>
);

/* ------------------------------------------------------------------ shared pieces */
/** "Plain words *serif italic words*": the starred part in Instrument Serif italic, gold. */
function Rich({ text, color = C.goldDeep }: { text: string; color?: string }) {
  return <>{text.split(/(\*[^*]+\*)/).map((p, i) => p.startsWith("*")
    ? <span key={i} style={{ fontFamily: F.serif, fontStyle: "italic", fontWeight: 400, color, letterSpacing: 0 }}>{p.slice(1, -1)}</span>
    : <span key={i}>{p}</span>)}</>;
}

/** Words that rise into place one after another, starting at `delay` frames. */
function Rise({ text, delay = 0, step = 2.5, style, color }: { text: string; delay?: number; step?: number; style?: React.CSSProperties; color?: string }) {
  const frame = useCurrentFrame();
  const parts = text.split(/(\*[^*]+\*)/).flatMap((p) => (p.startsWith("*") ? [p] : p.split(/(\s+)/))).filter(Boolean);
  let k = 0;
  return (
    <span style={style}>
      {parts.map((w, i) => {
        if (/^\s+$/.test(w)) return <span key={i}>{w}</span>;
        const d = delay + (k++) * step;
        const t = interpolate(frame - d, [0, 16], [0, 1], { ...clamp, easing: ease });
        return (
          <span key={i} style={{ display: "inline-block", overflow: "hidden", verticalAlign: "bottom", paddingBottom: "0.1em", marginBottom: "-0.1em" }}>
            <span style={{ display: "inline-block", transform: `translateY(${(1 - t) * 105}%)`, opacity: t }}><Rich text={w} color={color} /></span>
          </span>
        );
      })}
    </span>
  );
}

function Backdrop() {
  const frame = useCurrentFrame();
  const x = 50 + 18 * Math.sin(frame / 260), y = 40 + 12 * Math.cos(frame / 310);
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <AbsoluteFill style={{ background: `radial-gradient(1100px 700px at ${x}% ${y}%, rgba(201,151,91,0.16), transparent 70%)` }} />
      <AbsoluteFill style={{ backgroundImage: `radial-gradient(${C.lineStrong} 1.2px, transparent 1.3px)`, backgroundSize: "34px 34px",
        opacity: 0.35, maskImage: "radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0.9), transparent 80%)" }} />
    </AbsoluteFill>
  );
}

/** The Focs mark (from the app's favicon): ink viewfinder corners, gold inner corners and a gold dot. */
export function Mark({ size = 120, draw = 1, ink = C.ink }: { size?: number; draw?: number; ink?: string }) {
  const outer = Math.min(1, draw * 1.25), inner = interpolate(draw, [0.35, 0.9], [0, 1], clamp), dot = interpolate(draw, [0.75, 1], [0, 1], clamp);
  return (
    <svg width={size} height={size} viewBox="0 0 64 64">
      <path d="M5 20V5h15M44 5h15v15M59 44v15H44M20 59H5V44" fill="none" stroke={ink} strokeWidth="6.5" strokeLinecap="round" strokeLinejoin="round"
        pathLength={1} strokeDasharray={`${outer} 1`} />
      <path d="M21 28v-7h7M36 21h7v7M43 36v7h-7M28 43h-7v-7" fill="none" stroke={C.gold} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"
        pathLength={1} strokeDasharray={`${inner} 1`} />
      <circle cx="32" cy="32" r={5 * dot} fill={C.gold} />
    </svg>
  );
}

function Eyebrow({ children, color = C.goldDeep, style }: { children: React.ReactNode; color?: string; style?: React.CSSProperties }) {
  return <div style={{ fontFamily: F.mono, fontSize: 17, letterSpacing: "0.22em", textTransform: "uppercase", color, ...style }}>{children}</div>;
}

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 18, boxShadow: "0 30px 80px rgba(40,30,20,0.12), 0 2px 6px rgba(40,30,20,0.06)", ...style }}>{children}</div>;
}

function Stamp({ at, kind = "x", size = 120, style }: { at: number; kind?: "x" | "check"; size?: number; style?: React.CSSProperties }) {
  const frame = useCurrentFrame();
  const k = spring({ frame: frame - sec(at), fps: FPS, config: { damping: 11, mass: 0.6 } });
  if (frame < sec(at)) return null;
  const color = kind === "x" ? C.red : C.green;
  return (
    <div style={{ width: size, height: size, borderRadius: size / 2, background: color, display: "grid", placeItems: "center",
      transform: `scale(${0.3 + 0.7 * k}) rotate(${(1 - k) * -25}deg)`, opacity: Math.min(1, k * 1.4), boxShadow: `0 16px 40px ${color}55`, ...style }}>
      <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
        {kind === "x" ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M5 12.5l4.5 4.5L19 7.5" />}
      </svg>
    </div>
  );
}

/* ------------------------------------------------------------------ the app inside a browser */
function Clip({ clip, from, rate }: { clip: string; from: number; rate: number }) {
  return <OffthreadVideo muted src={staticFile(`clips/${clip}.mp4`)} trimBefore={sec(from)} playbackRate={rate}
    style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />;
}

function Segments({ segs }: { segs: Seg[] }) {
  return (
    <Series>
      {segs.map((s, i) => (
        <Series.Sequence key={i} durationInFrames={Math.round(((s.to - s.from) / s.rate) * FPS)}>
          <Clip clip={s.clip} from={s.from} rate={s.rate} />
        </Series.Sequence>
      ))}
    </Series>
  );
}

function Browser({ url, width, children }: { url: string; width: number; children: React.ReactNode }) {
  const h = (width / 1440) * 900;
  return (
    <div style={{ width, borderRadius: 16, overflow: "hidden", background: C.card, border: `1px solid ${C.lineStrong}`,
      boxShadow: "0 50px 120px rgba(40,30,20,0.22), 0 6px 18px rgba(40,30,20,0.08)" }}>
      <div style={{ height: 40, display: "flex", alignItems: "center", gap: 8, padding: "0 16px", background: "#f4f2ee", borderBottom: `1px solid ${C.line}` }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => <div key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c }} />)}
        <div style={{ marginLeft: 18, flex: 1, maxWidth: 520, height: 26, borderRadius: 7, background: "#fff", border: `1px solid ${C.line}`,
          display: "flex", alignItems: "center", padding: "0 12px", fontFamily: F.mono, fontSize: 14, color: C.muted }}>🔒 {url}</div>
        <div style={{ marginLeft: "auto", fontFamily: F.mono, fontSize: 12, letterSpacing: "0.14em", color: C.muted }}>REAL APP · SAMPLE ACCOUNTS</div>
      </div>
      <div style={{ width, height: h, position: "relative", overflow: "hidden", background: C.bg }}>{children}</div>
    </div>
  );
}

type Zoom = [number, number, number, number]; // [second, scale, x, y]
function zoomAt(keys: Zoom[] | undefined, t: number) {
  if (!keys?.length) return { s: 1, x: 0.5, y: 0.5 };
  let a = keys[0], b = keys[keys.length - 1];
  for (let i = 0; i < keys.length - 1; i++) if (t >= keys[i][0] && t <= keys[i + 1][0]) { a = keys[i]; b = keys[i + 1]; break; }
  if (t >= keys[keys.length - 1][0]) a = b = keys[keys.length - 1];
  if (t <= keys[0][0]) a = b = keys[0];
  const k = a === b ? 0 : Easing.inOut(Easing.cubic)((t - a[0]) / (b[0] - a[0]));
  return { s: a[1] + (b[1] - a[1]) * k, x: a[2] + (b[2] - a[2]) * k, y: a[3] + (b[3] - a[3]) * k };
}

interface Callout { at: number; dur: number; x: number; y: number; text: string; tone?: "red" | "green" | "gold"; big?: boolean }
function Chip({ c, frame, boxW, boxH }: { c: Callout; frame: number; boxW: number; boxH: number }) {
  const t0 = sec(c.at), t1 = sec(c.at + c.dur);
  if (frame < t0 - 1 || frame > t1 + 12) return null;
  const inT = interpolate(frame, [t0, t0 + 14], [0, 1], { ...clamp, easing: ease });
  const outT = interpolate(frame, [t1, t1 + 12], [1, 0], clamp);
  const chars = Math.floor(interpolate(frame, [t0 + 3, t0 + 3 + c.text.length * 0.7], [0, c.text.length], clamp));
  const color = c.tone === "red" ? C.red : c.tone === "green" ? C.green : c.tone === "gold" ? C.goldDeep : C.ink;
  const chipW = 60 + c.text.length * (c.big ? 13.6 : 11.2) + 40;
  const left = Math.max(10, Math.min(c.x * boxW, boxW - chipW - 10));
  return (
    <div style={{ position: "absolute", left, top: c.y * boxH, transform: `translateY(-50%) scale(${0.92 + 0.08 * inT})`, opacity: outT * inT, zIndex: 5 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, background: C.ink, color: "#fff", borderRadius: 999,
        padding: c.big ? "14px 24px" : "11px 20px", fontFamily: F.mono, fontSize: c.big ? 23 : 19, whiteSpace: "nowrap",
        boxShadow: "0 14px 40px rgba(0,0,0,0.28)", border: `2px solid ${color === C.ink ? "rgba(255,255,255,0.0)" : color}` }}>
        <span style={{ width: 11, height: 11, borderRadius: 6, background: color === C.ink ? C.gold : color, boxShadow: `0 0 0 ${4 + 6 * (1 - inT)}px ${(color === C.ink ? C.gold : color)}44` }} />
        <span>{c.text.slice(0, chars)}<span style={{ opacity: chars < c.text.length ? 1 : 0 }}>▍</span></span>
      </div>
    </div>
  );
}

function Caption({ eyebrow, head, sub, frame0 = 0 }: { eyebrow: string; head: string; sub?: string; frame0?: number }) {
  const frame = useCurrentFrame() - frame0;
  const subT = interpolate(frame, [20, 38], [0, 1], { ...clamp, easing: ease });
  return (
    <div style={{ width: 470 }}>
      <Eyebrow style={{ marginBottom: 22, opacity: interpolate(frame, [0, 12], [0, 1], clamp) }}>— {eyebrow}</Eyebrow>
      <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 54, lineHeight: 1.05, letterSpacing: "-0.015em", color: C.ink }}>
        <Rise text={head} delay={frame0 + 3} step={2} />
      </div>
      {sub && <div style={{ marginTop: 22, fontFamily: F.sans, fontSize: 21, lineHeight: 1.5, color: C.muted, opacity: subT, transform: `translateY(${(1 - subT) * 12}px)` }}>{sub}</div>}
    </div>
  );
}

/** A caption that changes with the shot: [from second, eyebrow, head, sub]. */
function Captions({ items }: { items: [number, string, string, string?][] }) {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  let idx = 0;
  items.forEach((it, i) => { if (t >= it[0]) idx = i; });
  const [from, eyebrow, head, sub] = items[idx];
  const next = items[idx + 1]?.[0];
  const out = next ? interpolate(frame, [sec(next) - 8, sec(next)], [1, 0], clamp) : 1;
  return <div style={{ opacity: out }}><Caption key={idx} eyebrow={eyebrow} head={head} sub={sub} frame0={sec(from)} /></div>;
}

function AppShot({ segs, url, captions, callouts = [], zoom, frames, children }: {
  segs: Seg[]; url: string; captions: [number, string, string, string?][]; callouts?: Callout[]; zoom?: Zoom[]; frames: number; children?: React.ReactNode;
}) {
  const frame = useCurrentFrame();
  const W = 1240, H = (W / 1440) * 900;
  const enter = spring({ frame, fps: FPS, config: { damping: 200, mass: 0.9 } });
  const exit = interpolate(frame, [frames - 10, frames], [1, 0], clamp);
  const z = zoomAt(zoom, frame / FPS);
  const tilt = interpolate(frame, [0, frames], [-5, 2]);
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 80, top: 250, opacity: exit }}><Captions items={captions} /></div>
      <div style={{ position: "absolute", left: 600, top: (1080 - H - 40) / 2 - 30, perspective: 2600, opacity: exit }}>
        <div style={{ transform: `translateX(${(1 - enter) * 240}px) rotateY(${tilt + (1 - enter) * -14}deg) scale(${0.95 + enter * 0.05})`, transformOrigin: "left center" }}>
          <Browser url={url} width={W}>
            <div style={{ position: "absolute", inset: 0, transform: `scale(${z.s})`, transformOrigin: `${z.x * 100}% ${z.y * 100}%` }}>
              <Segments segs={segs} />
            </div>
          </Browser>
        </div>
        <div style={{ position: "absolute", left: 0, top: 40, width: W, height: H }}>
          {callouts.map((c, i) => <Chip key={i} c={c} frame={frame} boxW={W} boxH={H} />)}
        </div>
        {children}
      </div>
    </AbsoluteFill>
  );
}

/* ------------------------------------------------------------------ 1. the hook */
function Hook() {
  const frame = useCurrentFrame();
  const w = (p: string, end = false) => when("hook", "hook", p, end);
  const tWrong = w("Galat!"), tTeacher = w("Teacher"), tFifty = w("Wo pachaas"), tAgain = w("Phir bhi"), tWhy = w("Kyun?"), tNever = w("Because");
  const qIn = spring({ frame: frame - sec(w("Torque")), fps: FPS, config: { damping: 18 } });
  const left = frame < sec(tNever) ? 1 : interpolate(frame, [sec(tNever), sec(tNever) + 10], [1, 0], clamp);
  const tiles = 50;
  const filled = Math.floor(interpolate(frame, [sec(tFifty), sec(tAgain - 0.1)], [0, tiles], clamp));
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 110, top: 150, opacity: left }}>
        <Eyebrow style={{ marginBottom: 26 }}>Kota · 11:40 PM · JEE prep</Eyebrow>
        <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 92, lineHeight: 1.02, letterSpacing: "-0.03em", color: C.ink }}>
          <div><Rise text="Ek JEE student." delay={sec(0.5)} /></div>
          <div style={{ opacity: fade(frame, w("Torque") - 0.2, w("Torque")) }}><Rise text="Torque ka ek sawaal." delay={sec(w("Torque"))} /></div>
          {frame >= sec(tWrong) && <div style={{ color: C.red }}><Rise text="Galat." delay={sec(tWrong)} color={C.red} /></div>}
        </div>
        {frame >= sec(tTeacher) && (
          <div style={{ marginTop: 34, display: "inline-flex", alignItems: "center", gap: 14, padding: "14px 22px", borderRadius: 16, background: C.card,
            border: `1px solid ${C.line}`, fontFamily: F.sans, fontSize: 28, color: C.soft, opacity: fade(frame, tTeacher, tTeacher + 0.3),
            transform: `translateY(${(1 - fade(frame, tTeacher, tTeacher + 0.4)) * 20}px)` }}>
            <span style={{ fontFamily: F.mono, fontSize: 16, letterSpacing: "0.16em", color: C.goldDeep }}>TEACHER</span> “Practice more.”
          </div>
        )}
      </div>
      {/* the question card, then fifty more tries */}
      <div style={{ position: "absolute", right: 120, top: 150, width: 640, opacity: left, transform: `translateY(${(1 - qIn) * 60}px)` }}>
        <Card style={{ padding: 34, opacity: qIn }}>
          <Eyebrow color={C.muted} style={{ fontSize: 14 }}>Rotational motion · MCQ</Eyebrow>
          <div style={{ marginTop: 14, fontFamily: F.sans, fontSize: 25, lineHeight: 1.45, color: C.ink }}>10 N acts on a 2 m spanner at 30°. Torque about the bolt?</div>
          <div style={{ marginTop: 20, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {["10 N·m", "17.3 N·m", "20 N·m", "5 N·m"].map((o, i) => {
              const chosen = i === 1 && frame >= sec(tWrong - 0.5);
              const wrong = chosen && frame >= sec(tWrong);
              return <div key={o} style={{ padding: "13px 16px", borderRadius: 12, fontFamily: F.mono, fontSize: 21,
                border: `1.5px solid ${wrong ? C.red : chosen ? C.ink : C.line}`, background: wrong ? C.redSoft : "#faf9f7", color: C.ink }}>
                {"ABCD"[i]}. {o}</div>;
            })}
          </div>
          <Stamp at={tWrong} style={{ position: "absolute", right: -30, top: -30 }} size={96} />
        </Card>
        {frame >= sec(tFifty - 0.2) && (
          <div style={{ marginTop: 26, opacity: fade(frame, tFifty - 0.2, tFifty) }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontFamily: F.mono, fontSize: 18, color: C.muted, marginBottom: 10 }}>
              <span>+ {filled} more questions</span><span style={{ color: C.red }}>{filled ? `${Math.max(0, filled - Math.floor(filled / 7))} wrong` : ""}</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(10, 1fr)", gap: 7 }}>
              {Array.from({ length: tiles }).map((_, i) => {
                const on = i < filled, bad = on && i % 7 !== 3;
                return <div key={i} style={{ height: 30, borderRadius: 7, background: !on ? "rgba(13,13,13,0.05)" : bad ? C.red : C.green,
                  opacity: on ? 0.9 : 1, transform: `scale(${on ? 1 : 0.85})` }} />;
              })}
            </div>
            {frame >= sec(tAgain) && <div style={{ marginTop: 18, fontFamily: F.display, fontSize: 44, fontWeight: 600, color: C.red }}><Rise text="Phir bhi galat." delay={sec(tAgain)} color={C.red} /></div>}
          </div>
        )}
      </div>
      {frame >= sec(tWhy) && frame < sec(tNever) && (
        <div style={{ position: "absolute", left: 110, bottom: 190, fontFamily: F.serif, fontStyle: "italic", fontSize: 120, color: C.goldDeep,
          transform: `scale(${spring({ frame: frame - sec(tWhy), fps: FPS, config: { damping: 10 } })})` }}>Kyun?</div>
      )}
      {frame >= sec(tNever) && (
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 104, letterSpacing: "-0.03em", color: C.ink, textAlign: "center", lineHeight: 1.05 }}>
            <Rise text="The problem was never" delay={sec(tNever)} step={2} /><br />
            <span style={{ position: "relative", display: "inline-block" }}>
              <Rise text="*torque.*" delay={sec(tNever) + 12} />
              <span style={{ position: "absolute", left: -10, right: -10, top: "55%", height: 9, background: C.red, borderRadius: 4,
                transform: `scaleX(${interpolate(frame, [sec(tNever) + 30, sec(tNever) + 42], [0, 1], { ...clamp, easing: ease })})`, transformOrigin: "left" }} />
            </span>
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
}

/* ------------------------------------------------------------------ 2. the real gap: a tower with a cracked block */
function Pain1() {
  const frame = useCurrentFrame();
  const tTrig = when("pain1", "pain1", "trigonometry"), tSin = when("pain1", "pain1", "Sin aur cos");
  const blocks = [
    { label: "Class 10", name: "Introduction to Trigonometry", w: 760 },
    { label: "Class 11", name: "Trigonometry · sin & cos", w: 680, crack: true },
    { label: "Class 11", name: "Vectors · components", w: 600 },
    { label: "JEE", name: "Rotational Motion · torque", w: 520, top: true },
  ];
  const crack = interpolate(frame, [sec(tTrig), sec(tTrig) + 10], [0, 1], { ...clamp, easing: ease });
  const wobble = crack > 0 ? Math.sin(frame / 2.2) * 2.2 * Math.max(0, 1 - (frame - sec(tTrig)) / 45) : 0;
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 110, top: 220, width: 640 }}>
        <Eyebrow style={{ marginBottom: 24 }}>The real problem</Eyebrow>
        <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 74, lineHeight: 1.04, letterSpacing: "-0.025em", color: C.ink }}>
          <Rise text="Asli problem: Class 11 *trigonometry.*" delay={sec(0.3)} />
        </div>
        <div style={{ marginTop: 30, fontFamily: F.sans, fontSize: 28, color: C.muted, lineHeight: 1.45, opacity: fade(frame, tSin, tSin + 0.4) }}>
          <b style={{ color: C.ink, fontFamily: F.mono }}>sin θ</b> vs <b style={{ color: C.ink, fontFamily: F.mono }}>cos θ</b> — never really learned.
          Every chapter built on top of it wobbles.
        </div>
      </div>
      <div style={{ position: "absolute", right: 120, bottom: 150, width: 800, display: "flex", flexDirection: "column-reverse", alignItems: "center", gap: 10 }}>
        {blocks.map((b, i) => {
          const k = spring({ frame: frame - sec(0.25 + i * 0.32), fps: FPS, config: { damping: 14, mass: 0.7 } });
          const above = i >= 2;
          return (
            <div key={i} style={{ width: b.w, height: 100, borderRadius: 16, position: "relative", overflow: "hidden",
              background: b.crack && crack > 0 ? "#fbe9ea" : b.top ? C.ink : C.card, color: b.top ? "#fff" : C.ink,
              border: `2px solid ${b.crack && crack > 0 ? C.red : C.line}`, boxShadow: "0 18px 40px rgba(40,30,20,0.10)",
              transform: `translateY(${(1 - k) * -260}px) rotate(${above ? wobble * (i - 1) : 0}deg)`, opacity: k,
              display: "flex", alignItems: "center", gap: 18, padding: "0 28px" }}>
              <span style={{ fontFamily: F.mono, fontSize: 16, letterSpacing: "0.14em", textTransform: "uppercase", color: b.top ? C.gold : C.muted }}>{b.label}</span>
              <span style={{ fontFamily: F.display, fontSize: 30, fontWeight: 600 }}>{b.name}</span>
              {b.crack && crack > 0 && (
                <svg width={b.w} height={100} style={{ position: "absolute", left: 0, top: 0 }}>
                  <path d={`M ${b.w * 0.62} 0 L ${b.w * 0.58} 30 L ${b.w * 0.66} 46 L ${b.w * 0.6} 70 L ${b.w * 0.64} 100`} fill="none" stroke={C.red}
                    strokeWidth={4} pathLength={1} strokeDasharray={`${crack} 1`} />
                </svg>
              )}
              {b.crack && crack > 0 && <span style={{ marginLeft: "auto", fontFamily: F.mono, fontSize: 16, color: C.red, fontWeight: 700, opacity: crack }}>ROOT GAP</span>}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}

/* ------------------------------------------------------------------ 3. every test app: right or wrong, nothing else */
function Pain2() {
  const frame = useCurrentFrame();
  const w = (p: string) => when("pain2", "pain2", p);
  const tRW = w("Right ya wrong"), tNobody = w("Koi nahi"), tClass = w("aur gap kis class"), tLoop = w("So students");
  const rows = [true, false, false, true, false, false];
  const spin = frame >= sec(tLoop) ? (frame - sec(tLoop)) * 4 : 0;
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 110, top: 120, width: 1700 }}>
        <Eyebrow style={{ marginBottom: 20 }}>Every test app today</Eyebrow>
        <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 68, lineHeight: 1.05, letterSpacing: "-0.02em", color: C.ink }}>
          <Rise text="Marks the *final answer.* Nothing else." delay={sec(0.3)} />
        </div>
      </div>
      <div style={{ position: "absolute", left: 110, top: 360, display: "flex", gap: 40, alignItems: "flex-start" }}>
        <Card style={{ width: 520, padding: 30, opacity: fade(frame, 0.4, 0.9) }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontFamily: F.mono, fontSize: 18, color: C.muted }}><span>MOCK TEST 7</span><span>Score</span></div>
          <div style={{ fontFamily: F.display, fontSize: 64, fontWeight: 600, marginTop: 6 }}>42<span style={{ color: C.muted, fontSize: 34 }}> / 100</span></div>
          <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 10 }}>
            {rows.map((ok, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 14, fontFamily: F.sans, fontSize: 21, color: C.soft,
                opacity: fade(frame, 0.6 + i * 0.25, 0.9 + i * 0.25) }}>
                <span style={{ width: 30, height: 30, borderRadius: 8, display: "grid", placeItems: "center", color: "#fff", background: ok ? C.green : C.red, fontWeight: 700 }}>{ok ? "✓" : "✗"}</span>
                Q{i + 3}. {["Kinematics", "Torque", "Rolling", "Work-energy", "Moment of inertia", "Angular momentum"][i]}
              </div>
            ))}
          </div>
          {frame >= sec(tRW) && <div style={{ marginTop: 18, fontFamily: F.display, fontSize: 30, fontWeight: 600, color: C.ink, opacity: fade(frame, tRW, tRW + 0.3) }}>Right ya wrong. <span style={{ color: C.muted }}>Bas.</span></div>}
        </Card>
        <div style={{ display: "flex", flexDirection: "column", gap: 22, paddingTop: 10 }}>
          {[["Kaunsa step galat tha?", tNobody], ["Gap kis class se shuru hua?", tClass]].map(([q, t], i) => (
            frame >= sec(t as number) ? (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 18, opacity: fade(frame, t as number, (t as number) + 0.3),
                transform: `translateX(${(1 - fade(frame, t as number, (t as number) + 0.5)) * 40}px)` }}>
                <span style={{ width: 64, height: 64, borderRadius: 32, background: C.gold, color: "#fff", display: "grid", placeItems: "center", fontFamily: F.display, fontSize: 40, fontWeight: 700 }}>?</span>
                <span style={{ fontFamily: F.display, fontSize: 40, fontWeight: 600, color: C.ink }}>{q as string}</span>
              </div>
            ) : null
          ))}
          {frame >= sec(tNobody + 0.6) && <div style={{ fontFamily: F.mono, fontSize: 20, color: C.red, marginLeft: 82, opacity: fade(frame, tNobody + 0.6, tNobody + 1) }}>no app tells them.</div>}
        </div>
      </div>
      {frame >= sec(tLoop - 0.2) && (
        <div style={{ position: "absolute", right: 120, top: 330, width: 560, opacity: fade(frame, tLoop - 0.2, tLoop + 0.2) }}>
          <Card style={{ padding: 30 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
              <svg width="130" height="130" viewBox="0 0 100 100" style={{ transform: `rotate(${spin}deg)` }}>
                <circle cx="50" cy="50" r="36" fill="none" stroke={C.line} strokeWidth="8" />
                <path d="M50 14 A36 36 0 1 1 18 34" fill="none" stroke={C.red} strokeWidth="8" strokeLinecap="round" />
                <path d="M10 26 L18 36 L28 28" fill="none" stroke={C.red} strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <div style={{ fontFamily: F.display, fontSize: 30, fontWeight: 600, lineHeight: 1.25 }}>Practice the<br />wrong thing.<br /><span style={{ color: C.muted }}>Repeat.</span></div>
            </div>
            <svg width="500" height="150" viewBox="0 0 500 150" style={{ marginTop: 18 }}>
              <line x1="0" y1="140" x2="500" y2="140" stroke={C.line} strokeWidth="2" />
              <polyline points="0,82 70,78 140,84 210,76 280,83 350,79 420,82 500,80" fill="none" stroke={C.red} strokeWidth="5" strokeLinejoin="round"
                pathLength={1} strokeDasharray={`${fade(frame, tLoop, tLoop + 2)} 1`} />
              <text x="0" y="40" fontFamily="Geist Mono" fontSize="18" fill={C.muted}>marks, month after month</text>
              <text x="380" y="60" fontFamily="Geist Mono" fontSize="18" fill={C.red}>atak gaye</text>
            </svg>
          </Card>
        </div>
      )}
    </AbsoluteFill>
  );
}

/* ------------------------------------------------------------------ 4. meet Focs */
function Reveal() {
  const frame = useCurrentFrame();
  const draw = interpolate(frame, [0, sec(1.3)], [0, 1], { ...clamp, easing: ease });
  const word = fade(frame, 0.8, 1.4);
  const tStep = when("focs", "focs", "Focs finds"), tGem = when("focs", "focs", "Built on Gemini");
  const up = interpolate(frame, [sec(1.6), sec(2.3)], [0, -150], { ...clamp, easing: ease });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", transform: `translateY(${up}px)` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 34 }}>
          <Mark size={170} draw={draw} />
          <div style={{ fontFamily: F.display, fontWeight: 500, fontSize: 170, letterSpacing: "0.12em", color: C.ink, opacity: word,
            transform: `translateX(${(1 - word) * -30}px)` }}>FOCS</div>
        </div>
      </div>
      <div style={{ position: "absolute", top: 600, width: 1500, textAlign: "center" }}>
        <div style={{ fontFamily: F.display, fontWeight: 500, fontSize: 52, color: C.muted, letterSpacing: "-0.01em" }}>
          {frame >= sec(1.6) && <Rise text="Other apps mark the answer." delay={sec(1.6)} step={2} />}
        </div>
        <div style={{ marginTop: 10, fontFamily: F.display, fontWeight: 600, fontSize: 64, color: C.ink, letterSpacing: "-0.02em" }}>
          {frame >= sec(tStep) && <Rise text="Focs finds the *step* — and the *class* — where it broke." delay={sec(tStep)} step={2} />}
        </div>
        {frame >= sec(tGem - 0.2) && (
          <div style={{ marginTop: 40, display: "inline-flex", alignItems: "center", gap: 14, padding: "14px 26px", borderRadius: 999, background: C.card,
            border: `1px solid ${C.line}`, boxShadow: "0 16px 40px rgba(40,30,20,0.1)", opacity: fade(frame, tGem - 0.2, tGem + 0.2),
            transform: `scale(${0.9 + 0.1 * fade(frame, tGem - 0.2, tGem + 0.3)})` }}>
            <svg width="30" height="30" viewBox="0 0 24 24"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#4f7cff" /><stop offset="1" stopColor="#b56cff" /></linearGradient></defs>
              <path d="M12 1.5c.6 5.6 4.9 9.9 10.5 10.5-5.6.6-9.9 4.9-10.5 10.5C11.4 16.9 7.1 12.6 1.5 12 7.1 11.4 11.4 7.1 12 1.5z" fill="url(#g)" /></svg>
            <span style={{ fontFamily: F.mono, fontSize: 24, letterSpacing: "0.06em", color: C.ink }}>Built on Gemini · ready for Google Cloud Run</span>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
}

/* ------------------------------------------------------------------ 5. the check (real app) with the phone photo */
function Phone({ at, dur }: { at: number; dur: number }) {
  const frame = useCurrentFrame();
  const a = sec(at), b = sec(at + dur);
  if (frame < a - 2 || frame > b + 14) return null;
  const inT = spring({ frame: frame - a, fps: FPS, config: { damping: 16, mass: 0.8 } });
  const outT = interpolate(frame, [b, b + 12], [0, 1], { ...clamp, easing: ease });
  const flash = interpolate(frame, [a + 14, a + 16, a + 26], [0, 1, 0], clamp);
  return (
    <div style={{ position: "absolute", left: 380, top: 30, width: 420, height: 820, zIndex: 8,
      transform: `translateY(${(1 - inT) * 600 + outT * 120}px) rotate(${-6 + inT * 4}deg) scale(${1 - outT * 0.55})`, opacity: 1 - outT }}>
      <div style={{ position: "absolute", inset: 0, borderRadius: 54, background: "#111", padding: 14, boxShadow: "0 50px 100px rgba(0,0,0,0.35)" }}>
        <div style={{ width: "100%", height: "100%", borderRadius: 42, overflow: "hidden", position: "relative", background: "#000" }}>
          <Img src={staticFile("bt/paper.jpg")} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          <div style={{ position: "absolute", inset: 0, background: "#fff", opacity: flash }} />
          <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: "18px 0 26px", background: "linear-gradient(transparent, rgba(0,0,0,0.65))",
            display: "flex", justifyContent: "center" }}>
            <div style={{ width: 70, height: 70, borderRadius: 35, border: "5px solid #fff", background: flash > 0 ? "#ddd" : "rgba(255,255,255,0.25)" }} />
          </div>
          <div style={{ position: "absolute", top: 18, left: 0, right: 0, textAlign: "center", fontFamily: F.mono, fontSize: 15, color: "#fff", letterSpacing: "0.1em" }}>CHECK MY PAPER WORKING</div>
        </div>
      </div>
    </div>
  );
}

function Check() {
  const s = scene("check");
  const st = segStarts(CHECK);
  return (
    <AppShot segs={CHECK} url="focs.in/app/practice" frames={s.frames}
      captions={[
        [0, "The prototype · practice", "Locked in as *Sure.* And wrong.", "Every answer is locked in as Sure or Guessing. Sure and wrong is a blind spot: it comes first."],
        [st[1], "Check my working", "A photo of the *rough paper.*", "No typing maths. The student snaps the working on paper, or writes on the rough pad."],
        [st[2], "Gemini reads every step", "The exact step *where it broke.*", "Steps read back, the first wrong one marked, a hint, then the corrected step on request."],
        [st[3], "The root behind the step", "Not a slip. *A gap,* from an earlier class.", "A slip (sign, arithmetic) means slow down. A gap means an idea is missing: Focs names it."],
      ]}
      callouts={[
        { at: 1.0, dur: 1.6, x: 0.08, y: 0.08, text: "question · Rotational Motion" },
        { at: 3.0, dur: 3.4, x: 0.34, y: 0.77, text: "sure + wrong = blind spot", tone: "red" },
        { at: st[2] + 0.4, dur: 3.2, x: 0.05, y: 0.12, text: "4 handwritten steps · read by Gemini", big: true },
        { at: st[2] + 3.8, dur: 3.6, x: 0.42, y: 0.34, text: "step 1 · cos θ where it needs sin θ", tone: "red", big: true },
        { at: st[3] + 0.4, dur: 4.0, x: 0.36, y: 0.86, text: "root: Class 11 · vectors into components", tone: "gold", big: true },
      ]}
      zoom={[[0, 1.0, 0.5, 0.3], [0.6, 1.22, 0.58, 0.32], [st[1] - 0.6, 1.22, 0.58, 0.55], [st[1], 1.0, 0.5, 0.5], [st[2], 1.0, 0.5, 0.5],
             [st[2] + 1.0, 1.25, 0.56, 0.4], [st[3] - 0.3, 1.25, 0.56, 0.55], [st[3] + 0.6, 1.22, 0.56, 0.62], [st[3] + 4.7, 1.22, 0.56, 0.62]]}>
      <Phone at={st[1] - 0.1} dur={2.0} />
    </AppShot>
  );
}

/* ------------------------------------------------------------------ 6. trace, fix, proof (real app) */
function ProofOverlay({ at }: { at: number }) {
  const frame = useCurrentFrame();
  if (frame < sec(at)) return null;
  const k = spring({ frame: frame - sec(at), fps: FPS, config: { damping: 13, mass: 0.7 } });
  const n = Math.min(3, 1 + Math.floor(interpolate(frame, [sec(at + 0.6), sec(at + 1.6)], [0, 2.99], clamp)));
  return (
    <div style={{ position: "absolute", right: 60, top: 70, zIndex: 9, transform: `scale(${0.6 + 0.4 * k})`, opacity: Math.min(1, k * 1.3), transformOrigin: "top right" }}>
      <Card style={{ padding: "26px 36px", border: `2px solid ${C.green}` }}>
        <Eyebrow color={C.green} style={{ fontSize: 15 }}>Rotational Motion · retest</Eyebrow>
        <div style={{ display: "flex", alignItems: "baseline", gap: 22, marginTop: 6, fontFamily: F.display, fontWeight: 700 }}>
          <span style={{ fontSize: 76, color: C.muted }}>1/3</span>
          <span style={{ fontSize: 50, color: C.muted }}>→</span>
          <span style={{ fontSize: 108, color: C.green }}>{n}/3</span>
        </div>
        <div style={{ fontFamily: F.sans, fontSize: 19, color: C.muted }}>before the fix → after the fix</div>
      </Card>
    </div>
  );
}

function Trace() {
  const s = scene("trace");
  const st = segStarts(TRACE);
  return (
    <AppShot segs={TRACE} url="focs.in/app/roots" frames={s.frames}
      captions={[
        [0, "Root cause", "Traced back, *class by class.*", "One quick question on each earlier idea the chapter rests on. The deepest miss is the real gap."],
        [st[1] + 1.5, "The real gap", "Class 11 trigonometry: *sin and cos.*", "The kinematics check was right. Standard angles were not: that is where Rotational Motion broke."],
        [st[2], "The five-minute fix", "A lesson in *their* language.", "Hinglish here. Also Hindi, Marathi, Bengali, Tamil, Telugu and Gujarati, with every formula kept exact."],
        [st[3], "The proof", "Same chapter. *3 out of 3.*", "Three questions before the fix, three new ones after: the student and the teacher see what changed."],
      ]}
      callouts={[
        { at: 0.6, dur: 3.0, x: 0.36, y: 0.2, text: "Fix the root → a trace starts" },
        { at: st[1] + 2.4, dur: 3.6, x: 0.4, y: 0.5, text: "deepest miss = ROOT GAP", tone: "red", big: true },
        { at: st[2] + 0.3, dur: 2.8, x: 0.32, y: 0.3, text: "5-minute lesson · Hinglish · re-checked", tone: "gold" },
      ]}
      zoom={[[0, 1, 0.5, 0.5], [st[3] - 0.2, 1, 0.5, 0.5], [st[3] + 0.6, 1.35, 0.35, 0.3], [st[3] + 6, 1.35, 0.35, 0.3]]}>
      <ProofOverlay at={st[3] + 0.6} />
    </AppShot>
  );
}

/* ------------------------------------------------------------------ 7. the teacher and the Gap Genome (real app) */
function Teacher() {
  const s = scene("teacher");
  const st = segStarts(TEACHER);
  return (
    <AppShot segs={TEACHER} url="focs.in/app/classes" frames={s.frames}
      captions={[
        [0, "For teachers", "Where the batch's gaps *really start.*", "Every student's traces added up. Counts only: nobody is named."],
        [st[1], "Gap Genome", "What JEE and NEET *rest on.*", "Every traced chapter in one map. The school chapters that hold up the most exam chapters, ranked."],
      ]}
      callouts={[
        { at: 1.2, dur: 4.4, x: 0.08, y: 0.18, text: "teach first: Trigonometry · unblocks 2 students", tone: "gold", big: true },
        { at: st[1] + 0.8, dur: 3.5, x: 0.5, y: 0.2, text: "Class 10 trigonometry → 3 exam chapters", tone: "gold" },
      ]}
      zoom={[[0, 1.18, 0.4, 0.25], [st[1] - 0.3, 1.18, 0.4, 0.3], [st[1], 1, 0.5, 0.5]]} />
  );
}

/* ------------------------------------------------------------------ 8. the platform tour (real app) */
function TourShot({ id, url, captions, callouts = [], zoom, children }: { id: string; url: string; captions: [number, string, string, string?][];
  callouts?: Callout[]; zoom?: Zoom[]; children?: React.ReactNode }) {
  const s = scene(id);
  return <AppShot segs={TOUR[id]} url={url} frames={s.frames} captions={captions} callouts={callouts} zoom={zoom}>{children}</AppShot>;
}

const Tour1 = () => (
  <TourShot id="tour1" url="focs.in" captions={[[0, "The platform", "One app for the *whole* prep.", "JEE, NEET, CBSE Class 1-12, SSC, B.Tech and placements. Free for students to start."]]}
    callouts={[{ at: 1.4, dur: 3.2, x: 0.5, y: 0.3, text: "focs.in · live today", tone: "gold" }]} />
);
const Tour2 = () => (
  <TourShot id="tour2" url="focs.in/app/studio" captions={[[0, "Live lecture", "Any lecture tab. *Notes write themselves.*", "YouTube, Physics Wallah, Unacademy, Zoom. Crop to the board; FocsOCR reads it, the notes follow in seconds."]]}
    callouts={[{ at: 1.0, dur: 2.6, x: 0.25, y: 0.14, text: "share one tab · crop to the board" },
               { at: 4.0, dur: 3.2, x: 0.16, y: 0.42, text: "FocsOCR · our own model · 0.48% CER, held-out frames", tone: "gold", big: true }]} />
);
const Tour3 = () => (
  <TourShot id="tour3" url="focs.in/app/studio" captions={[[0, "Pop quiz", "Mid-lecture. Locked in: *Sure or Guess.*", "Being sure and wrong is a blind spot. Blind spots lead the summary and the plan."]]}
    callouts={[{ at: 2.6, dur: 3.4, x: 0.55, y: 0.8, text: "sure + wrong = blind spot", tone: "red" }]} />
);
const Tour4 = () => (
  <TourShot id="tour4" url="focs.in/app/mock" captions={[[0, "Mock tests", "NTA-style screen. *A gap map,* not just a score.", "Full JEE mocks: +4 / -1, palette, server timer, autosave. Every AI question kept only if a second model agrees."]]}
    callouts={[{ at: 1.0, dur: 2.8, x: 0.4, y: 0.12, text: "+4 / −1 · timer · palette · autosave" },
               { at: 4.4, dur: 2.8, x: 0.3, y: 0.62, text: "gap map · shaky chapters · next steps", tone: "gold" }]} />
);
function PhoneClip({ clip, from, at, dur }: { clip: string; from: number; at: number; dur: number }) {
  const frame = useCurrentFrame();
  if (frame < sec(at) - 2 || frame > sec(at + dur) + 14) return null;
  const k = spring({ frame: frame - sec(at), fps: FPS, config: { damping: 16 } });
  const out = interpolate(frame, [sec(at + dur), sec(at + dur) + 12], [0, 1], clamp);
  return (
    <div style={{ position: "absolute", right: -40, top: 60, width: 300, height: 650, zIndex: 8, opacity: 1 - out,
      transform: `translateY(${(1 - k) * 500 + out * 80}px) rotate(${4 - 4 * k}deg)` }}>
      <div style={{ position: "absolute", inset: 0, borderRadius: 44, background: "#111", padding: 11, boxShadow: "0 40px 90px rgba(0,0,0,0.35)" }}>
        <div style={{ width: "100%", height: "100%", borderRadius: 34, overflow: "hidden", background: C.bg }}>
          <Sequence from={sec(at) - 2} layout="none"><Clip clip={clip} from={from} rate={1} /></Sequence>
        </div>
      </div>
    </div>
  );
}
const Tour5 = () => (
  <TourShot id="tour5" url="focs.in/app/rooms" captions={[[0, "Study rooms", "Study together. *I'm lost* reaches the teacher.", "Synced lecture, chat, doubts and a focus timer. “I'm lost” taps are pinned to the exact board: counts, never names."]]}
    callouts={[{ at: 3.6, dur: 3.0, x: 0.3, y: 0.56, text: "confusion map · which board lost the room", tone: "red" }]}>
    <PhoneClip clip="room-phone" from={0.6} at={0.8} dur={3.6} />
  </TourShot>
);

function Tour6() {
  const frame = useCurrentFrame();
  const w = (p: string) => when("tour6", "tour6", p);
  const items = [
    { clip: "flashcards", from: 1, rate: 1.6, label: "Spaced-repetition flashcards", t: w("Flashcards") },
    { clip: "plan", from: 1, rate: 1.8, label: "A daily plan to the exam date", t: w("daily plan") },
    { clip: "revise", from: 1, rate: 1.8, label: "Last-day revision, most marks first", t: w("last day") },
    { clip: "mentors", from: 2, rate: 1.8, label: "Mentors who cleared the exam", t: w("mentors") },
    { clip: "senior", from: 13, rate: 1.4, label: "Ask a senior · AI draft, senior-checked", t: w("Ask a senior") },
    { clip: "hindi", from: 1, rate: 1.2, label: "Notes and the whole app in Hindi", t: w("saat Indian") },
  ];
  const langs = ["English", "Hinglish", "हिन्दी", "मराठी", "বাংলা", "தமிழ்", "తెలుగు", "ગુજરાતી"];
  const tLang = w("saat Indian");
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 110, top: 64 }}>
        <Eyebrow>And everything around it</Eyebrow>
        <div style={{ marginTop: 12, fontFamily: F.display, fontWeight: 600, fontSize: 54, letterSpacing: "-0.02em" }}><Rise text="Sab kuch, *ek hi jagah.*" delay={sec(0.3)} /></div>
      </div>
      <div style={{ position: "absolute", left: 110, top: 205, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 22, width: 1700 }}>
        {items.map((it, i) => {
          const k = spring({ frame: frame - sec(it.t - 0.25), fps: FPS, config: { damping: 16 } });
          return (
            <div key={i} style={{ opacity: k, transform: `translateY(${(1 - k) * 40}px) scale(${0.96 + 0.04 * k})` }}>
              <div style={{ height: 300, borderRadius: 14, overflow: "hidden", border: `1px solid ${C.lineStrong}`, boxShadow: "0 20px 50px rgba(40,30,20,0.14)", background: C.bg }}>
                {frame >= sec(it.t - 0.3) && <Sequence from={sec(it.t - 0.3)} layout="none"><Clip clip={it.clip} from={it.from} rate={it.rate} /></Sequence>}
              </div>
              <div style={{ marginTop: 10, fontFamily: F.mono, fontSize: 19, color: C.ink }}>{it.label}</div>
            </div>
          );
        })}
      </div>
      {frame >= sec(tLang - 0.3) && (
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 118, display: "flex", justifyContent: "center", gap: 12 }}>
          {langs.map((l, i) => {
            const k = spring({ frame: frame - sec(tLang - 0.3) - i * 3, fps: FPS, config: { damping: 12 } });
            return <div key={l} style={{ padding: "10px 20px", borderRadius: 999, background: C.ink, color: "#fff", fontFamily: F.indic, fontSize: 24,
              transform: `scale(${k})`, boxShadow: "0 12px 30px rgba(0,0,0,0.2)" }}>{l}</div>;
          })}
        </div>
      )}
    </AbsoluteFill>
  );
}

/* ------------------------------------------------------------------ 9. under the hood */
function Tech() {
  const frame = useCurrentFrame();
  const w = (p: string) => when("tech", "tech", p);
  const nodes = [
    { x: 130, y: 330, t: 0.4, title: "Photo or rough pad", sub: "the student's working", icon: "📷" },
    { x: 560, y: 330, t: w("Gemini handwriting"), title: "Gemini reads it", sub: "every step · first wrong one · slip or gap", icon: "✦", gem: true },
    { x: 990, y: 330, t: w("har step check"), title: "Root-cause chain", sub: "earlier-class ideas · cached per chapter", icon: "⛓" },
    { x: 1420, y: 330, t: w("JEE aur NEET"), title: "Fix + retest", sub: "5-min lesson · bank questions", icon: "✓" },
  ];
  const fallbackT = w("Agar Gemini");
  const cloudT = w("Google Cloud Run");
  const stats = [
    { t: w("aath second"), big: "8 s", label: "no answer → a second model is asked" },
    { t: w("twenty two"), big: "22", label: "root-cause chains ship · top JEE + NEET chapters" },
    { t: w("JEE aur NEET") + 1.2, big: "2–6 s", label: "a check, in our first real Gemini runs" },
  ];
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 110, top: 80 }}>
        <Eyebrow>Under the hood</Eyebrow>
        <div style={{ marginTop: 14, fontFamily: F.display, fontWeight: 600, fontSize: 60, letterSpacing: "-0.02em" }}><Rise text="Built on *Gemini,* ready for *Cloud Run.*" delay={sec(0.3)} /></div>
      </div>
      <svg width="1920" height="1080" style={{ position: "absolute", inset: 0 }}>
        {nodes.slice(1).map((n, i) => {
          const a = nodes[i];
          const k = fade(frame, n.t - 0.3, n.t + 0.4);
          const x1 = a.x + 370, x2 = n.x, y = a.y + 85;
          return <g key={i}>
            <line x1={x1} y1={y} x2={x1 + (x2 - x1) * k} y2={y} stroke={C.ink} strokeWidth={3} />
            {k >= 1 && [0, 1].map((j) => { const p = ((frame + j * 20) % 40) / 40; return <circle key={j} cx={x1 + (x2 - x1) * p} cy={y} r={6} fill={C.gold} />; })}
          </g>;
        })}
      </svg>
      {nodes.map((n, i) => {
        const k = spring({ frame: frame - sec(n.t), fps: FPS, config: { damping: 15 } });
        return (
          <div key={i} style={{ position: "absolute", left: n.x, top: n.y, width: 370, opacity: k, transform: `translateY(${(1 - k) * 30}px)` }}>
            <Card style={{ padding: 26, height: 170, border: n.gem ? "2px solid #8a7dff" : `1px solid ${C.line}` }}>
              <div style={{ fontSize: 36, color: n.gem ? "#6a6aff" : C.ink }}>{n.icon}</div>
              <div style={{ marginTop: 8, fontFamily: F.display, fontSize: 31, fontWeight: 600 }}>{n.title}</div>
              <div style={{ marginTop: 4, fontFamily: F.sans, fontSize: 18, color: C.muted }}>{n.sub}</div>
            </Card>
          </div>
        );
      })}
      {frame >= sec(fallbackT) && (
        <div style={{ position: "absolute", left: 560, top: 540, width: 370, opacity: fade(frame, fallbackT, fallbackT + 0.4) }}>
          <div style={{ marginLeft: 180, width: 3, height: 40, background: `repeating-linear-gradient(${C.muted} 0 6px, transparent 6px 12px)` }} />
          <div style={{ padding: "14px 18px", borderRadius: 14, border: `2px dashed ${C.muted}`, fontFamily: F.mono, fontSize: 17, color: C.soft, background: C.paper }}>
            no reply in 8 s → a second model too: the student never waits
          </div>
        </div>
      )}
      {frame >= sec(cloudT - 0.3) && (
        <div style={{ position: "absolute", left: 110, right: 110, top: 290, height: 470, borderRadius: 26, border: `2px dashed ${C.gold}`,
          opacity: fade(frame, cloudT - 0.3, cloudT + 0.3) }}>
          <div style={{ position: "absolute", right: 24, bottom: -18, background: C.bg, padding: "0 12px", fontFamily: F.mono, fontSize: 19, color: C.goldDeep }}>
            Google Cloud Run · asia-south1 (Mumbai) · FastAPI + React · Postgres
          </div>
        </div>
      )}
      <div style={{ position: "absolute", left: 110, top: 800, display: "flex", gap: 30 }}>
        {stats.map((s, i) => frame >= sec(s.t) ? (
          <div key={i} style={{ width: 540, opacity: fade(frame, s.t, s.t + 0.4), display: "flex", alignItems: "center", gap: 18 }}>
            <div style={{ fontFamily: F.display, fontSize: 64, fontWeight: 700, color: C.ink, minWidth: 150 }}>{s.big}</div>
            <div style={{ fontFamily: F.sans, fontSize: 21, color: C.muted, lineHeight: 1.35 }}>{s.label}</div>
          </div>
        ) : null)}
      </div>
    </AbsoluteFill>
  );
}

/* ------------------------------------------------------------------ 10. close */
function Close() {
  const frame = useCurrentFrame();
  const w = (p: string) => when("close", "close", p);
  const tFocs = w("Focs. Find");
  const after = frame >= sec(tFocs);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      {!after && (
        <div style={{ textAlign: "center", fontFamily: F.display, fontWeight: 600, fontSize: 84, lineHeight: 1.12, letterSpacing: "-0.025em" }}>
          <Rise text="Students ko aur practice nahi chahiye." delay={sec(0.3)} step={2} /><br />
          {frame >= sec(w("Unhe")) && <Rise text="Unhe chahiye *sahi fix,* sahi root pe." delay={sec(w("Unhe"))} step={2} />}
        </div>
      )}
      {after && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
            <Mark size={130} draw={fade(frame, tFocs, tFocs + 1)} />
            <div style={{ fontFamily: F.display, fontWeight: 500, fontSize: 130, letterSpacing: "0.12em", opacity: fade(frame, tFocs + 0.2, tFocs + 0.7) }}>FOCS</div>
          </div>
          <div style={{ marginTop: 16, fontFamily: F.display, fontWeight: 600, fontSize: 64, letterSpacing: "-0.02em" }}>
            <Rise text="Find the step. *Fix the root.*" delay={sec(tFocs + 0.4)} step={3} />
          </div>
          <div style={{ marginTop: 60, display: "flex", gap: 22, opacity: fade(frame, tFocs + 1.6, tFocs + 2.2) }}>
            {[["Ashpreet Singh Saini", "Team leader"], ["Mukul", "Team member"]].map(([n, r]) => (
              <Card key={n} style={{ padding: "20px 30px", display: "flex", alignItems: "center", gap: 16 }}>
                <div style={{ width: 54, height: 54, borderRadius: 14, background: n.startsWith("A") ? "#e0457b" : "#8a6a55", color: "#fff", display: "grid", placeItems: "center", fontFamily: F.display, fontSize: 28, fontWeight: 600 }}>{n[0]}</div>
                <div><div style={{ fontFamily: F.display, fontSize: 28, fontWeight: 600 }}>{n}</div><div style={{ fontFamily: F.mono, fontSize: 15, color: C.muted, letterSpacing: "0.1em", textTransform: "uppercase" }}>{r}</div></div>
              </Card>
            ))}
          </div>
          <div style={{ marginTop: 34, fontFamily: F.mono, fontSize: 21, letterSpacing: "0.14em", color: C.muted, opacity: fade(frame, tFocs + 2.2, tFocs + 2.8) }}>
            FOCS.IN · STARTUP BUILDATHON · INDIA 2026
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
}

/* ------------------------------------------------------------------ subtitles, sound, the whole film */
function Subtitles() {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const sub = SUBS.find((s) => t >= s.start && t < s.end);
  if (!sub) return null;
  const k = interpolate(t, [sub.start, sub.start + 0.12], [0, 1], clamp);
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 44, display: "flex", justifyContent: "center", zIndex: 50 }}>
      <div style={{ maxWidth: 1500, padding: "12px 26px", borderRadius: 14, background: "rgba(13,13,13,0.86)", color: "#fff", fontFamily: F.sans,
        fontSize: 32, fontWeight: 500, letterSpacing: "0.005em", opacity: k, transform: `translateY(${(1 - k) * 8}px)`, textAlign: "center" }}>{sub.text}</div>
    </div>
  );
}

function Progress() {
  const frame = useCurrentFrame();
  return <div style={{ position: "absolute", left: 0, top: 0, height: 5, width: `${(100 * frame) / TOTAL}%`, background: C.gold, zIndex: 60 }} />;
}

const SFX: [string, string, number, number?][] = (() => {
  const S = (id: string) => scene(id).start / FPS;
  const out: [string, string, number, number?][] = [];
  for (const s of SCENES.slice(1)) out.push([`w-${s.id}`, "whoosh", s.start / FPS - 0.15, 0.5]);
  out.push(["x1", "buzz", S("hook") + when("hook", "hook", "Galat!"), 0.55]);
  out.push(["x2", "buzz", S("hook") + when("hook", "hook", "Phir bhi"), 0.4]);
  out.push(["strike", "pop", S("hook") + when("hook", "hook", "Because") + 1.4, 0.6]);
  out.push(["crack", "buzz", S("pain1") + when("pain1", "pain1", "trigonometry"), 0.4]);
  out.push(["rise", "rise", S("focs") - 1.3, 0.55]);
  out.push(["logo", "ding", S("focs") + 0.9, 0.45]);
  out.push(["blind", "buzz", S("check") + 2.9, 0.35]);
  out.push(["snap", "snap", S("check") + segStarts(CHECK)[1] + 0.4, 0.7]);
  out.push(["found", "pop", S("check") + segStarts(CHECK)[2] + 3.8, 0.6]);
  out.push(["proof", "ding", S("trace") + segStarts(TRACE)[3] + 1.6, 0.6]);
  out.push(["end", "ding", S("close") + when("close", "close", "Focs. Find"), 0.45]);
  return out;
})();

function Sound() {
  const vo = SCENES.flatMap((s) => s.lines.map((l) => ({ id: l.id, at: s.start / FPS + l.at, len: voLen(l.id) })));
  const speaking = (t: number) => vo.some((v) => t >= v.at - 0.15 && t <= v.at + v.len + 0.1);
  return (
    <>
      <Audio src={staticFile("bt/music.wav")} volume={(f) => {
        const t = f / FPS;
        const base = speaking(t) ? 0.13 : 0.32;
        return base * interpolate(f, [TOTAL - sec(2.5), TOTAL], [1, 0], clamp);
      }} />
      {vo.map((v) => (
        <Sequence key={v.id} from={sec(v.at)} durationInFrames={sec(v.len + 0.5)}><Audio src={staticFile(`bt/vo/${v.id}.wav`)} volume={1} /></Sequence>
      ))}
      {SFX.map(([key, name, at, vol]) => (
        <Sequence key={key} from={Math.max(0, sec(at))} durationInFrames={sec(1.6)}><Audio src={staticFile(`bt/sfx/${name}.wav`)} volume={vol ?? 0.5} /></Sequence>
      ))}
    </>
  );
}

const VIEW: Record<string, React.FC> = { hook: Hook, pain1: Pain1, pain2: Pain2, focs: Reveal, check: Check, trace: Trace, teacher: Teacher, tour1: Tour1, tour2: Tour2, tour3: Tour3, tour4: Tour4, tour5: Tour5, tour6: Tour6, tech: Tech, close: Close };

function SceneWrap({ id, frames }: { id: string; frames: number }) {
  const frame = useCurrentFrame();
  const V = VIEW[id];
  const inT = interpolate(frame, [0, 10], [0, 1], { ...clamp, easing: ease });
  const outT = interpolate(frame, [frames - 8, frames], [1, 0], clamp);
  return <AbsoluteFill style={{ opacity: Math.min(inT, outT), transform: `scale(${1.02 - 0.02 * inT})` }}><V /></AbsoluteFill>;
}

export function Film() {
  return (
    <AbsoluteFill style={{ background: C.bg, color: C.ink, fontFamily: F.sans }}>
      <Fonts />
      <Backdrop />
      {SCENES.map((s) => (
        <Sequence key={s.id} from={s.start} durationInFrames={s.frames}><SceneWrap id={s.id} frames={s.frames} /></Sequence>
      ))}
      <Subtitles />
      <Progress />
      <Sound />
    </AbsoluteFill>
  );
}
