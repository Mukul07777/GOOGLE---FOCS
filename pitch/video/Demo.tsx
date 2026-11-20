// FOCS — the demo film. Black stage, chalk-white type, one lime accent; the real app inside a browser frame.
import React from "react";
import {
  AbsoluteFill, Easing, Img, interpolate, OffthreadVideo, Sequence, Series, spring, staticFile,
  useCurrentFrame,
} from "remotion";
import { FPS, SHOTS, segFrames, TOTAL, type Callout, type Segment, type Shot } from "./timeline";

const C = { bg: "#0a0a0b", fg: "#f3f1ec", muted: "#8d8b86", line: "rgba(243,241,236,0.12)", accent: "#c8ff2e", panel: "#141416" };
const F = { display: "Jost, sans-serif", sans: "Geist, sans-serif", mono: "'Geist Mono', monospace", serif: "'Instrument Serif', serif" };
const ease = Easing.bezier(0.16, 1, 0.3, 1);
const sec = (s: number) => Math.round(s * FPS);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Fonts = () => (
  <style>{`
    @font-face { font-family: Jost; src: url(${staticFile("fonts/jost-latin-wght-normal.woff2")}) format("woff2"); font-weight: 100 900; }
    @font-face { font-family: Geist; src: url(${staticFile("fonts/geist-latin-wght-normal.woff2")}) format("woff2"); font-weight: 100 900; }
    @font-face { font-family: 'Geist Mono'; src: url(${staticFile("fonts/geist-mono-latin-wght-normal.woff2")}) format("woff2"); font-weight: 100 900; }
    @font-face { font-family: 'Instrument Serif'; src: url(${staticFile("fonts/instrument-serif-latin-400-italic.woff2")}) format("woff2"); font-style: italic; }
  `}</style>
);

/* ---------------------------------------------------------------- small pieces */
/** "Plain words *serif italic words*" → the starred part in Instrument Serif italic, lime. */
function Rich({ text }: { text: string }) {
  return <>{text.split(/(\*[^*]+\*)/).map((p, i) => p.startsWith("*")
    ? <span key={i} style={{ fontFamily: F.serif, fontStyle: "italic", fontWeight: 400, color: C.accent, letterSpacing: 0 }}>{p.slice(1, -1)}</span>
    : <span key={i}>{p}</span>)}</>;
}

/** Words that rise into place one after another. */
function Rise({ text, delay = 0, step = 3, style }: { text: string; delay?: number; step?: number; style?: React.CSSProperties }) {
  const frame = useCurrentFrame();
  const parts = text.split(/(\*[^*]+\*)/).flatMap((p) => (p.startsWith("*") ? [p] : p.split(/(\s+)/))).filter(Boolean);
  let k = 0;
  return (
    <span style={style}>
      {parts.map((w, i) => {
        if (/^\s+$/.test(w)) return <span key={i}>{w}</span>;
        const d = delay + (k++) * step;
        const t = interpolate(frame - d, [0, 18], [0, 1], { ...clamp, easing: ease });
        return (
          <span key={i} style={{ display: "inline-block", overflow: "hidden", verticalAlign: "bottom", paddingBottom: "0.08em" }}>
            <span style={{ display: "inline-block", transform: `translateY(${(1 - t) * 105}%)`, opacity: t }}><Rich text={w} /></span>
          </span>
        );
      })}
    </span>
  );
}

function Grid({ opacity = 1 }: { opacity?: number }) {
  return <AbsoluteFill style={{ opacity, backgroundImage: `linear-gradient(${C.line} 1px, transparent 1px), linear-gradient(90deg, ${C.line} 1px, transparent 1px)`,
    backgroundSize: "96px 96px", maskImage: "radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0.55), transparent 75%)" }} />;
}

function Grain() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "overlay", opacity: 0.18 }}>
      <svg width="1920" height="1080"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={frame % 8} /></filter>
        <rect width="100%" height="100%" filter="url(#n)" /></svg>
    </AbsoluteFill>
  );
}

export function Logo({ size = 120, draw = 1 }: { size?: number; draw?: number }) {
  const len = 2 * Math.PI * 15;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64">
      <circle cx="32" cy="32" r="15" fill="none" stroke={C.fg} strokeWidth="5" strokeDasharray={`${70.6 * draw} ${len}`} transform="rotate(-40 32 32)" />
      <rect x="28" y="28" width="8" height="8" fill={C.accent} transform={`translate(32 32) scale(${Math.min(1, draw * 1.4)}) translate(-32 -32)`} />
    </svg>
  );
}

/** The bridge: teacher on one side, student on the other, packets running between. */
function Bridge({ width = 1500, progress = 1, back = false, y = 0, packets = true }: { width?: number; progress?: number; back?: boolean; y?: number; packets?: boolean }) {
  const frame = useCurrentFrame();
  const node = (label: string, side: "l" | "r") => (
    <div style={{ position: "absolute", [side === "l" ? "left" : "right"]: -8, top: -8, display: "flex", flexDirection: "column", alignItems: side === "l" ? "flex-start" : "flex-end" }}>
      <div style={{ width: 16, height: 16, background: C.fg, transform: `scale(${progress})` }} />
      <div style={{ marginTop: 16, fontFamily: F.mono, fontSize: 16, letterSpacing: "0.25em", color: C.muted, opacity: progress }}>{label}</div>
    </div>
  );
  return (
    <div style={{ position: "relative", width, height: 2, transform: `translateY(${y}px)` }}>
      <div style={{ position: "absolute", left: 0, top: 0, height: 2, width: width * progress, background: C.fg, opacity: 0.6 }} />
      {node("TEACHER", "l")}{node("STUDENT", "r")}
      {packets && progress > 0.98 && [0, 1, 2, 3].map((i) => {
        const dir = back ? (i % 2 ? -1 : 1) : i === 3 ? -1 : 1;
        const t = ((frame + i * 23) % 70) / 70;
        const x = dir > 0 ? t * width : (1 - t) * width;
        return <div key={i} style={{ position: "absolute", top: -4, left: x - 5, width: 10, height: 10, borderRadius: 5,
          background: dir < 0 ? C.accent : C.fg, boxShadow: `0 0 18px ${dir < 0 ? C.accent : "#fff"}` }} />;
      })}
    </div>
  );
}

/* ---------------------------------------------------------------- the app inside a browser */
function Clip({ clip, from, rate }: { clip: string; from: number; rate: number }) {
  return <OffthreadVideo muted src={staticFile(`clips/${clip}.mp4`)} trimBefore={sec(from)} playbackRate={rate}
    style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />;
}

function Segments({ segments }: { segments: Segment[] }) {
  return (
    <Series>
      {segments.map((s, i) => (
        <Series.Sequence key={i} durationInFrames={segFrames(s)}>
          <Clip clip={s.clip} from={s.from} rate={s.rate} />
        </Series.Sequence>
      ))}
    </Series>
  );
}

function Browser({ url, width, children }: { url: string; width: number; children: React.ReactNode }) {
  const h = (width / 1440) * 900;
  return (
    <div style={{ width, borderRadius: 14, overflow: "hidden", background: C.panel, border: `1px solid ${C.line}`,
      boxShadow: `0 60px 140px rgba(0,0,0,0.65), 0 0 0 1px rgba(255,255,255,0.04), 0 0 120px rgba(200,255,46,0.06)` }}>
      <div style={{ height: 38, display: "flex", alignItems: "center", gap: 8, padding: "0 16px", background: "#18181b", borderBottom: `1px solid ${C.line}` }}>
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => <div key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c, opacity: 0.85 }} />)}
        <div style={{ marginLeft: 18, flex: 1, maxWidth: 520, height: 24, borderRadius: 6, background: "#0f0f11", display: "flex", alignItems: "center", padding: "0 12px",
          fontFamily: F.mono, fontSize: 13, color: C.muted }}>🔒 {url}</div>
      </div>
      <div style={{ width, height: h, position: "relative", overflow: "hidden" }}>{children}</div>
    </div>
  );
}

function zoomAt(keys: number[][] | undefined, t: number) {
  if (!keys?.length) return { s: 1, x: 0.5, y: 0.5 };
  let a = keys[0], b = keys[keys.length - 1];
  for (let i = 0; i < keys.length - 1; i++) if (t >= keys[i][0] && t <= keys[i + 1][0]) { a = keys[i]; b = keys[i + 1]; break; }
  if (t >= keys[keys.length - 1][0]) a = b = keys[keys.length - 1];
  const k = a === b ? 0 : Easing.inOut(Easing.cubic)((t - a[0]) / (b[0] - a[0]));
  return { s: a[1] + (b[1] - a[1]) * k, x: a[2] + (b[2] - a[2]) * k, y: a[3] + (b[3] - a[3]) * k };
}

function CalloutChip({ c, frame, boxW, boxH }: { c: Callout; frame: number; boxW: number; boxH: number }) {
  const t0 = sec(c.at), t1 = sec(c.at + c.dur);
  if (frame < t0 - 1 || frame > t1 + 12) return null;
  const inT = interpolate(frame, [t0, t0 + 14], [0, 1], { ...clamp, easing: ease });
  const outT = interpolate(frame, [t1, t1 + 12], [1, 0], clamp);
  const chars = Math.floor(interpolate(frame, [t0 + 4, t0 + 4 + c.text.length * 0.9], [0, c.text.length], clamp));
  const color = c.accent ? C.accent : C.fg;
  // keep the whole chip on screen: the box starts 600 px in, so the frame's right edge is at 1320 - 36 px margin
  const chipW = 70 + 34 + c.text.length * (c.big ? 13.3 : 10.9) + 20;
  const left = Math.min(c.x * boxW, 1320 - 36 - chipW);
  return (
    <div style={{ position: "absolute", left, top: c.y * boxH, transform: `translate(-6px, -50%)`, opacity: outT, zIndex: 5 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 12, height: 12, borderRadius: 6, background: color, boxShadow: `0 0 0 ${6 + 10 * (1 - inT)}px ${c.accent ? "rgba(200,255,46,0.25)" : "rgba(255,255,255,0.18)"}` }} />
        <div style={{ height: 2, width: 40 * inT, background: color }} />
        <div style={{ clipPath: `inset(0 ${100 - inT * 100}% 0 0)`, background: "rgba(10,10,11,0.88)", border: `1px solid ${c.accent ? C.accent : "rgba(243,241,236,0.35)"}`,
          padding: c.big ? "14px 20px" : "10px 16px", fontFamily: F.mono, fontSize: c.big ? 22 : 18, color, whiteSpace: "nowrap", letterSpacing: "0.01em",
          backdropFilter: "blur(8px)", boxShadow: "0 10px 40px rgba(0,0,0,0.5)" }}>
          {c.text.slice(0, chars)}<span style={{ opacity: chars < c.text.length ? 1 : 0 }}>▍</span>
        </div>
      </div>
    </div>
  );
}

function Caption({ eyebrow, head, sub, width = 520 }: { eyebrow?: string; head?: string; sub?: string; width?: number }) {
  const frame = useCurrentFrame();
  const subT = interpolate(frame, [22, 40], [0, 1], { ...clamp, easing: ease });
  return (
    <div style={{ width }}>
      {eyebrow && <div style={{ fontFamily: F.mono, fontSize: 17, letterSpacing: "0.22em", textTransform: "uppercase", color: C.accent, marginBottom: 26,
        opacity: interpolate(frame, [0, 12], [0, 1], clamp) }}>— {eyebrow}</div>}
      {head && <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 56, lineHeight: 1.04, letterSpacing: "-0.015em", color: C.fg }}>
        <Rise text={head} delay={3} step={2} /></div>}
      {sub && <div style={{ marginTop: 26, fontFamily: F.sans, fontSize: 21, lineHeight: 1.5, color: C.muted, opacity: subT, transform: `translateY(${(1 - subT) * 12}px)` }}>{sub}</div>}
    </div>
  );
}

function AppShot({ shot }: { shot: Shot & { frames: number } }) {
  const frame = useCurrentFrame();
  const W = 1260, H = (W / 1440) * 900;
  const enter = spring({ frame, fps: FPS, config: { damping: 200, mass: 0.9 } });
  const exit = interpolate(frame, [shot.frames - 10, shot.frames], [1, 0], clamp);
  const z = zoomAt(shot.zoom, frame / FPS);
  const tilt = interpolate(frame, [0, shot.frames], [-7, 3]);
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 84, top: 300, opacity: exit }}>
        <Caption eyebrow={shot.eyebrow} head={shot.head} sub={shot.sub} />
      </div>
      <div style={{ position: "absolute", left: 600, top: (1080 - H - 38) / 2, perspective: 2400, opacity: exit }}>
        <div style={{ transform: `translateX(${(1 - enter) * 260}px) rotateY(${tilt + (1 - enter) * -16}deg) scale(${0.94 + enter * 0.06})`, transformOrigin: "left center" }}>
          <Browser url={shot.url} width={W}>
            <div style={{ position: "absolute", inset: 0, transform: `scale(${z.s})`, transformOrigin: `${z.x * 100}% ${z.y * 100}%` }}>
              <Segments segments={shot.segments!} />
            </div>
            {shot.proofAt !== undefined && <ProofCard at={shot.proofAt} />}
          </Browser>
        </div>
        <div style={{ position: "absolute", left: 0, top: 38, width: W, height: H }}>
          {(shot.callouts ?? []).map((c: Callout, i: number) => <CalloutChip key={i} c={c} frame={frame} boxW={W} boxH={H} />)}
        </div>
      </div>
    </AbsoluteFill>
  );
}

function ProofCard({ at }: { at: number }) {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [sec(at), sec(at) + 12, sec(at + 2.2), sec(at + 2.6)], [0, 1, 1, 0], clamp);
  if (t <= 0) return null;
  return (
    <div style={{ position: "absolute", right: 40, top: 60, width: 520, opacity: t, transform: `translateY(${(1 - t) * 30}px) rotate(${(1 - t) * 3}deg)`,
      boxShadow: "0 30px 80px rgba(0,0,0,0.55)", border: `2px solid ${C.accent}`, background: "#fff" }}>
      <Img src={staticFile("proof-rohan.png")} style={{ width: "100%", display: "block" }} />
      <div style={{ background: C.accent, color: "#0a0a0b", fontFamily: F.mono, fontSize: 15, padding: "6px 10px" }}>PROOF · SEEN BY FOCS STAFF ONLY · DELETED AFTER REVIEW</div>
    </div>
  );
}

/* ---------------------------------------------------------------- other shot types */
function Open() {
  const frame = useCurrentFrame();
  const beats: [number, number, React.ReactNode][] = [
    [0, 1.8, <><b style={{ color: C.fg }}>1</b> teacher.</>],
    [1.8, 3.5, <><b>1</b> board.</>],
    [3.5, 5.2, <><b>200</b> students.</>],
    [5.2, 7.0, <><b style={{ color: C.accent }}>0</b> questions asked.</>],
  ];
  const last = interpolate(frame, [sec(7.0), sec(7.4)], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "absolute", left: 84, top: 70, fontFamily: F.mono, fontSize: 16, letterSpacing: "0.2em", color: C.muted }}>
        {"KOTA · 08:00 IST · PHYSICS LECTURE 14".slice(0, Math.floor(frame / 1.6))}
      </div>
      {beats.map(([a, b, node], i) => {
        const f0 = sec(a), f1 = sec(b);
        if (frame < f0 || frame >= f1) return null;
        const k = spring({ frame: frame - f0, fps: FPS, config: { damping: 14, mass: 0.6 } });
        return <div key={i} style={{ fontFamily: F.display, fontWeight: 600, fontSize: 168, letterSpacing: "-0.03em", color: C.fg,
          transform: `scale(${1.25 - 0.25 * k})`, filter: `blur(${(1 - k) * 12}px)`, opacity: k }}>{node}</div>;
      })}
      {frame >= sec(7.0) && (
        <div style={{ textAlign: "center", opacity: last }}>
          <div style={{ fontFamily: F.display, fontWeight: 500, fontSize: 62, color: C.fg, letterSpacing: "-0.02em" }}>
            <Rise text="The lecture moves at the *teacher's* speed." delay={sec(7.0)} step={2} />
          </div>
          <div style={{ marginTop: 18, fontFamily: F.display, fontWeight: 500, fontSize: 62, color: C.muted, letterSpacing: "-0.02em" }}>
            <Rise text="The confusion never travels back." delay={sec(8.1)} step={2} />
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
}

function Title() {
  const frame = useCurrentFrame();
  const draw = interpolate(frame, [0, 34], [0, 1], { ...clamp, easing: ease });
  const bridge = interpolate(frame, [26, 70], [0, 1], { ...clamp, easing: ease });
  const tag = interpolate(frame, [70, 96], [0, 1], { ...clamp, easing: ease });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <Grid opacity={bridge} />
      <div style={{ display: "flex", alignItems: "center", gap: 40, marginTop: -120 }}>
        <Logo size={150} draw={draw} />
        <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 190, color: C.fg, letterSpacing: "0.2em", display: "flex" }}>
          {"FOCS".split("").map((ch, i) => {
            const k = interpolate(frame, [8 + i * 4, 28 + i * 4], [0, 1], { ...clamp, easing: ease });
            return <span key={i} style={{ opacity: k, transform: `translateY(${(1 - k) * 60}px)`, display: "inline-block" }}>{ch}</span>;
          })}
        </div>
      </div>
      <div style={{ position: "absolute", top: 640 }}><Bridge width={1400} progress={bridge} /></div>
      <div style={{ position: "absolute", top: 740, fontFamily: F.display, fontSize: 40, color: C.fg, opacity: tag, transform: `translateY(${(1 - tag) * 16}px)` }}>
        Focs carries the lecture to the student, <span style={{ fontFamily: F.serif, fontStyle: "italic", color: C.accent }}>and the confusion back to the teacher.</span>
      </div>
      <div style={{ position: "absolute", bottom: 70, fontFamily: F.mono, fontSize: 16, letterSpacing: "0.3em", color: C.muted, opacity: tag }}>
        GDG NSUT DEVLYMPICS 2026 · BRIDGE THE GAP
      </div>
    </AbsoluteFill>
  );
}

function Lanes() {
  const frame = useCurrentFrame();
  const lanes = [["01", "Speed", "Board and voice → live notes and captions", false], ["02", "Language", "English, Hinglish or हिंदी, formulas intact", false],
    ["03", "Understanding", "Sure or Guessing → blind spots first", false], ["04", "Return", "\"I'm lost\" → the teacher, live", true]] as const;
  return (
    <AbsoluteFill style={{ padding: "150px 84px" }}>
      <div style={{ fontFamily: F.mono, fontSize: 17, letterSpacing: "0.22em", color: C.accent }}>— FOUR LANES ACROSS THE GAP</div>
      <div style={{ marginTop: 90, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 36 }}>
        {lanes.map(([n, t, b, back], i) => {
          const k = interpolate(frame, [6 + i * 6, 26 + i * 6], [0, 1], { ...clamp, easing: ease });
          return (
            <div key={n} style={{ borderTop: `2px solid ${back ? C.accent : C.fg}`, paddingTop: 30, opacity: k, transform: `translateY(${(1 - k) * 40}px)` }}>
              <div style={{ fontFamily: F.mono, fontSize: 20, color: back ? C.accent : C.muted }}>{n} {back ? "← student → teacher" : "→ teacher → student"}</div>
              <div style={{ marginTop: 26, fontFamily: F.display, fontWeight: 600, fontSize: 60, color: C.fg }}>{t}</div>
              <div style={{ marginTop: 18, fontFamily: F.sans, fontSize: 22, color: C.muted, lineHeight: 1.45 }}>{b}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 84, bottom: 140 }}><Bridge width={1752} progress={interpolate(frame, [20, 60], [0, 1], { ...clamp, easing: ease })} /></div>
    </AbsoluteFill>
  );
}

function Chapter({ shot }: { shot: Shot & { frames: number } }) {
  const frame = useCurrentFrame();
  const k = interpolate(frame, [0, 16], [0, 1], { ...clamp, easing: ease });
  const wipe = interpolate(frame, [shot.frames - 12, shot.frames], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", background: shot.back ? C.accent : C.bg }}>
      <div style={{ position: "absolute", fontFamily: F.display, fontWeight: 800, fontSize: 620, lineHeight: 1, color: "transparent",
        WebkitTextStroke: `2px ${shot.back ? "rgba(10,10,11,0.25)" : "rgba(243,241,236,0.16)"}`, transform: `scale(${1.1 - 0.1 * k})` }}>{shot.num}</div>
      <div style={{ textAlign: "center", transform: `translateY(${(1 - k) * 30 - wipe * 40}px)`, opacity: k * (1 - wipe) }}>
        <div style={{ fontFamily: F.mono, fontSize: 22, letterSpacing: "0.3em", color: shot.back ? "#0a0a0b" : C.accent }}>LANE {shot.num} · {String(shot.dir).toUpperCase()}</div>
        <div style={{ marginTop: 20, fontFamily: F.display, fontWeight: 600, fontSize: 150, letterSpacing: "-0.02em", color: shot.back ? "#0a0a0b" : C.fg }}>{shot.title}</div>
      </div>
    </AbsoluteFill>
  );
}

function Split({ shot }: { shot: Shot & { frames: number } }) {
  const frame = useCurrentFrame();
  const W = 860;
  const side = (s: any, i: number) => {
    const k = spring({ frame: frame - i * 6, fps: FPS, config: { damping: 200 } });
    return (
      <div style={{ transform: `translateY(${(1 - k) * 80}px)`, opacity: k }}>
        <Browser url={i ? "focs.app · हिंदी" : "focs.app · English"} width={W}><Clip clip={s.clip} from={s.from} rate={s.rate} /></Browser>
        <div style={{ marginTop: 18, fontFamily: F.mono, fontSize: 20, color: i ? C.accent : C.fg, letterSpacing: "0.1em" }}>{s.label}</div>
      </div>
    );
  };
  return (
    <AbsoluteFill style={{ padding: "70px 84px" }}>
      <Caption eyebrow={shot.eyebrow} head={shot.head} width={1500} />
      <div style={{ marginTop: 44, display: "flex", gap: 60 }}>{side(shot.left, 0)}{side(shot.right, 1)}</div>
      <div style={{ position: "absolute", left: 84, bottom: 46, fontFamily: F.sans, fontSize: 20, color: C.muted, opacity: interpolate(frame, [30, 50], [0, 1], clamp) }}>{shot.note}</div>
    </AbsoluteFill>
  );
}

function Montage({ shot }: { shot: Shot & { frames: number } }) {
  const each = Math.floor(shot.frames / shot.items.length);
  return (
    <Series>
      {shot.items.map((it: any, i: number) => (
        <Series.Sequence key={i} durationInFrames={i === shot.items.length - 1 ? shot.frames - each * i : each}>
          <MontageItem it={it} />
        </Series.Sequence>
      ))}
    </Series>
  );
}

function MontageItem({ it }: { it: any }) {
  const frame = useCurrentFrame();
  const k = interpolate(frame, [0, 10], [0, 1], { ...clamp, easing: ease });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ transform: `scale(${1.08 - 0.08 * k})`, opacity: k }}>
        <Browser url="focs.app" width={1500}><Clip clip={it.clip} from={it.from} rate={it.rate} /></Browser>
      </div>
      <div style={{ position: "absolute", left: 210, bottom: 70, background: C.accent, color: "#0a0a0b", fontFamily: F.display, fontWeight: 600, fontSize: 40,
        padding: "12px 26px", clipPath: `inset(0 ${100 - k * 100}% 0 0)` }}>{it.label}</div>
    </AbsoluteFill>
  );
}

function Phone({ children, scale = 1 }: { children: React.ReactNode; scale?: number }) {
  return (
    <div style={{ width: 390 * scale + 28, height: 844 * scale + 28, borderRadius: 58, background: "#1b1b1e", padding: 14,
      boxShadow: "0 50px 120px rgba(0,0,0,0.7), inset 0 0 0 2px rgba(255,255,255,0.08)" }}>
      <div style={{ width: 390 * scale, height: 844 * scale, borderRadius: 46, overflow: "hidden", position: "relative" }}>{children}</div>
    </div>
  );
}

function Return({ shot }: { shot: Shot & { frames: number } }) {
  const frame = useCurrentFrame();
  const W = 1080;
  const tapF = sec(shot.tap);
  const fly = interpolate(frame, [tapF, tapF + 22], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const p0 = [330, 850], p1 = [900, 700], pc = [620, 380];
  const bx = (1 - fly) ** 2 * p0[0] + 2 * (1 - fly) * fly * pc[0] + fly ** 2 * p1[0];
  const by = (1 - fly) ** 2 * p0[1] + 2 * (1 - fly) * fly * pc[1] + fly ** 2 * p1[1];
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 84, top: 70 }}><Caption eyebrow={shot.eyebrow} head={shot.head} width={1700} /></div>
      <div style={{ position: "absolute", left: 120, top: 250, transform: "rotate(-4deg)" }}>
        <Phone scale={0.88}><Clip clip={shot.phone.clip} from={shot.phone.from} rate={shot.phone.rate} /></Phone>
        <div style={{ marginTop: 20, fontFamily: F.mono, fontSize: 18, color: C.muted, letterSpacing: "0.12em" }}>STUDENT · PHONE</div>
      </div>
      <div style={{ position: "absolute", left: 720, top: 300 }}>
        <Browser url="focs.app/app/rooms/SGR7TY" width={W}><Clip clip={shot.desk.clip} from={shot.desk.from} rate={shot.desk.rate} /></Browser>
        <div style={{ marginTop: 20, fontFamily: F.mono, fontSize: 18, color: C.muted, letterSpacing: "0.12em" }}>TEACHER · LAPTOP · LIVE OVER WEBSOCKETS</div>
      </div>
      {fly > 0 && fly < 1 && <div style={{ position: "absolute", left: bx - 14, top: by - 14, width: 28, height: 28, borderRadius: 14, background: C.accent,
        boxShadow: `0 0 40px ${C.accent}, 0 0 90px ${C.accent}` }} />}
      {frame > tapF + 20 && <div style={{ position: "absolute", left: 1290, top: 250, background: C.accent, color: "#0a0a0b", fontFamily: F.mono, fontSize: 20, padding: "10px 16px",
        opacity: interpolate(frame, [tapF + 20, tapF + 30], [0, 1], clamp) }}>anonymous · count + board, never a name</div>}
    </AbsoluteFill>
  );
}

const PRO_FEATURES = [
  "A live mentor session every week, included (60-min master session)",
  "10× the AI allowance of Starter",
  "Up to 2 full mock tests a day with full analysis",
  "AI practice sets & subjective answer grading",
  "Doubt solver with Socratic mode",
  "Study rooms up to 50",
];

function Pro({ shot }: { shot: Shot & { frames: number } }) {
  const frame = useCurrentFrame();
  const k = spring({ frame: frame - 8, fps: FPS, config: { damping: 200 } });
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 84, top: 140, opacity: 0.55, transform: "scale(0.82)", transformOrigin: "left top", filter: "saturate(0.6)" }}>
        <Browser url="focs.app/app/settings#plan" width={1260}><Clip clip={shot.clip} from={shot.from} rate={shot.rate} /></Browser>
      </div>
      <div style={{ position: "absolute", right: 84, top: 110, width: 760, background: C.fg, color: "#0a0a0b", padding: "46px 50px",
        transform: `translateX(${(1 - k) * 900}px)`, boxShadow: "0 50px 140px rgba(0,0,0,0.7)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div style={{ fontFamily: F.mono, fontSize: 18, letterSpacing: "0.3em" }}>FOCS PRO</div>
          <div style={{ fontFamily: F.mono, fontSize: 16, letterSpacing: "0.1em", background: "#0a0a0b", color: C.accent, padding: "6px 10px" }}>UPI · RAZORPAY</div>
        </div>
        <div style={{ marginTop: 20, fontFamily: F.display, fontWeight: 600, fontSize: 104, letterSpacing: "-0.03em", lineHeight: 1 }}>
          ₹149<span style={{ fontSize: 34, fontWeight: 400 }}> / month</span></div>
        <div style={{ marginTop: 30 }}>
          {PRO_FEATURES.map((f, i) => {
            const t = interpolate(frame, [18 + i * 7, 32 + i * 7], [0, 1], { ...clamp, easing: ease });
            return (
              <div key={f} style={{ display: "flex", gap: 16, alignItems: "flex-start", padding: "12px 0", borderTop: "1px solid rgba(10,10,11,0.14)", opacity: t,
                transform: `translateX(${(1 - t) * 30}px)`, fontFamily: F.sans, fontSize: i === 0 ? 27 : 23, fontWeight: i === 0 ? 650 : 450 }}>
                <span style={{ width: 26, height: 26, flex: "none", marginTop: 2, display: "grid", placeItems: "center", background: i === 0 ? C.accent : "#0a0a0b",
                  color: i === 0 ? "#0a0a0b" : C.fg, fontSize: 16 }}>✓</span>
                <span style={i === 0 ? { background: `linear-gradient(transparent 60%, ${C.accent} 60%)` } : undefined}>{f}</span>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 22, fontFamily: F.sans, fontSize: 19, color: "#55534f" }}>Starter stays free. 1:1 mentor calls ₹49 for everyone; Focs keeps 20%.</div>
      </div>
    </AbsoluteFill>
  );
}

function Tech() {
  const frame = useCurrentFrame();
  const at = (s: number) => interpolate(frame, [sec(s), sec(s) + 14], [0, 1], { ...clamp, easing: ease });
  const box = (x: number, y: number, w: number, title: string, lines: string[], s: number, hot = false) => {
    const k = at(s);
    return (
      <div style={{ position: "absolute", left: x, top: y, width: w, border: `1px solid ${hot ? C.accent : "rgba(243,241,236,0.3)"}`, background: "rgba(20,20,22,0.92)",
        padding: "18px 20px", opacity: k, transform: `translateY(${(1 - k) * 24}px)` }}>
        <div style={{ fontFamily: F.mono, fontSize: 15, letterSpacing: "0.18em", color: hot ? C.accent : C.muted }}>{title}</div>
        {lines.map((l) => <div key={l} style={{ marginTop: 8, fontFamily: F.sans, fontSize: 19, color: C.fg }}>{l}</div>)}
      </div>
    );
  };
  const wire = (x1: number, y1: number, x2: number, y2: number, s: number) => {
    const k = at(s);
    const len = Math.hypot(x2 - x1, y2 - y1);
    const dot = ((frame % 40) / 40) * len;
    return (
      <g key={`${x1}${y1}${x2}`}>
        <line x1={x1} y1={y1} x2={x1 + (x2 - x1) * k} y2={y1 + (y2 - y1) * k} stroke="rgba(243,241,236,0.45)" strokeWidth={2} />
        {k >= 1 && <circle cx={x1 + ((x2 - x1) * dot) / len} cy={y1 + ((y2 - y1) * dot) / len} r={5} fill={C.accent} />}
      </g>
    );
  };
  const stats: [string, string][] = [["0.48%", "FocsOCR character error vs 7.27% PP-OCRv4*"], ["221", "automated tests · CI on every push"], ["193", "API endpoints"], ["37k", "lines of code · web + Android app"]];
  return (
    <AbsoluteFill>
      <Grid />
      <div style={{ position: "absolute", left: 84, top: 64 }}>
        <div style={{ fontFamily: F.mono, fontSize: 17, letterSpacing: "0.22em", color: C.accent }}>— UNDER THE HOOD</div>
        <div style={{ marginTop: 16, fontFamily: F.display, fontWeight: 600, fontSize: 60, color: C.fg }}><Rise text="Not a wrapper. *Our own model, our own stack.*" step={2} /></div>
      </div>
      <svg width="1920" height="1080" style={{ position: "absolute", inset: 0 }}>
        {wire(430, 420, 560, 420, 1.2)}{wire(900, 420, 1020, 330, 2.0)}{wire(900, 450, 1020, 520, 2.6)}{wire(1440, 330, 1540, 420, 3.2)}{wire(1440, 520, 1540, 450, 3.4)}
        {wire(730, 520, 730, 640, 3.8)}
      </svg>
      {box(84, 300, 346, "BROWSER · REACT 19", ["Tab capture + crop", "48×27 change detector", "Mic → 25 s audio pieces"], 0.4)}
      {box(560, 300, 340, "FASTAPI · PYTHON 3.12", ["193 endpoints", "WebSockets for live rooms", "Rate limits · allowance"], 1.0)}
      {box(1020, 230, 420, "OCR ENSEMBLE", ["DBNet detector → FocsOCR × PP-OCRv4", "FocsOCR: CNN+BiLSTM+CTC, 3.1 M", "1.76 M synthetic lines · 1 h on RTX 4050"], 1.8, true)}
      {box(1020, 470, 420, "AI ROUTER", ["Groq gpt-oss-120b / 20b → Gemini", "Formula check on every translation", "Cost ledger · offline fallback"], 2.4)}
      {box(1540, 330, 300, "OUT", ["Notes · quizzes · gap map", "Whisper captions", "Hindi / Hinglish"], 3.0)}
      {box(560, 640, 340, "DATA & SHIP", ["Postgres (Supabase)", "Docker · Cloud Run ready", "Android app (Capacitor)"], 3.6)}
      {box(1020, 700, 420, "MONEY & SAFETY", ["Razorpay: Pro, calls, seats", "Verified mentors · masked contacts", "DPDP: export or delete in one tap"], 4.2)}
      <div style={{ position: "absolute", left: 84, right: 84, bottom: 70, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 30 }}>
        {stats.map(([n, l], i) => {
          const k = at(7 + i * 0.7);
          return (
            <div key={l} style={{ borderTop: `2px solid ${i === 0 ? C.accent : C.fg}`, paddingTop: 16, opacity: k }}>
              <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 70, color: i === 0 ? C.accent : C.fg }}>{n}</div>
              <div style={{ fontFamily: F.sans, fontSize: 18, color: C.muted }}>{l}</div>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", right: 84, bottom: 30, fontFamily: F.mono, fontSize: 13, color: C.muted, opacity: at(9) }}>
        * 240 held-out synthetic lecture frames; a real-board benchmark is being collected
      </div>
    </AbsoluteFill>
  );
}

function Finale() {
  const frame = useCurrentFrame();
  const k = interpolate(frame, [0, 40], [0, 1], { ...clamp, easing: ease });
  const t = interpolate(frame, [36, 70], [0, 1], { ...clamp, easing: ease });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <Grid opacity={k} />
      <div style={{ position: "absolute", top: 300 }}><Bridge width={1500} progress={k} back /></div>
      <div style={{ marginTop: 60, textAlign: "center" }}>
        <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 112, color: C.fg, letterSpacing: "-0.02em" }}>
          <Rise text="Every lecture, *understood.*" delay={10} step={4} />
        </div>
        <div style={{ marginTop: 50, display: "flex", alignItems: "center", gap: 26, justifyContent: "center", opacity: t }}>
          <Logo size={64} draw={t} />
          <div style={{ fontFamily: F.display, fontWeight: 600, fontSize: 56, letterSpacing: "0.3em", color: C.fg }}>FOCS</div>
        </div>
        <div style={{ marginTop: 26, fontFamily: F.mono, fontSize: 17, letterSpacing: "0.26em", color: C.muted, opacity: t }}>
          BUILT AND RUNNING · JEE · NEET · UPSC · GATE · CA · B.TECH
        </div>
        <div style={{ marginTop: 18, fontFamily: F.mono, fontSize: 22, color: C.accent, opacity: t }}>github.com/Mukul07777/Break_The_Gap_Focs</div>
      </div>
    </AbsoluteFill>
  );
}

/* ---------------------------------------------------------------- the film */
function ShotView({ shot }: { shot: (typeof SHOTS)[number] }) {
  switch (shot.type) {
    case "open": return <Open />;
    case "title": return <Title />;
    case "lanes": return <Lanes />;
    case "chapter": return <Chapter shot={shot} />;
    case "app": return <AppShot shot={shot} />;
    case "split": return <Split shot={shot} />;
    case "montage": return <Montage shot={shot} />;
    case "return": return <Return shot={shot} />;
    case "pro": return <Pro shot={shot} />;
    case "tech": return <Tech />;
    case "finale": return <Finale />;
    default: return null;
  }
}

const FOOTAGE = new Set(["app", "split", "montage", "return", "pro"]);

function Overlay() {
  const frame = useCurrentFrame();
  const shot = SHOTS.find((s) => frame >= s.start && frame < s.start + s.frames);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", left: 0, bottom: 0, height: 4, width: `${(frame / TOTAL) * 100}%`, background: C.accent, opacity: 0.8 }} />
      {shot && FOOTAGE.has(shot.type) && (
        <div style={{ position: "absolute", right: 30, top: 24, fontFamily: F.mono, fontSize: 13, letterSpacing: "0.18em", color: C.muted, display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: "#ff4d3d", opacity: frame % 30 < 18 ? 1 : 0.3 }} />
          REAL APP · LIVE SERVER · SAMPLE ACCOUNTS
        </div>
      )}
    </AbsoluteFill>
  );
}

export const Demo = () => {
  return (
    <AbsoluteFill style={{ background: C.bg, color: C.fg, fontFamily: F.sans }}>
      <Fonts />
      {SHOTS.map((s) => (
        <Sequence key={s.id} from={s.start} durationInFrames={s.frames}>
          <ShotView shot={s} />
        </Sequence>
      ))}
      <Overlay />
      <Grain />
    </AbsoluteFill>
  );
};
