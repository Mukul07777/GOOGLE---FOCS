// The Buildathon film as data: scenes, the voice lines placed in them, and the app footage each one uses.
// Scene lengths follow the voiceover (public/bt/vo.json, written by buildathon/make_vo.py), so a re-voiced line re-times the cut.
import voMeta from "../../public/bt/vo.json";
import voScript from "../vo.json";

export const FPS = 30;
const meta = voMeta as Record<string, number | string>;
export const VO_TEXT: Record<string, string> = Object.fromEntries((voScript as { lines: { id: string; text: string }[] }).lines.map((l) => [l.id, l.text]));
export const voLen = (id: string) => Number(meta[id] ?? 0);

export interface Seg { clip: string; from: number; to: number; rate: number }
export interface Line { id: string; at: number }
export interface Scene { id: string; dur: number; lines: Line[]; segs?: Seg[]; start: number; frames: number }

const segLen = (s: Seg) => (s.to - s.from) / s.rate;
const sum = (segs: Seg[]) => segs.reduce((n, s) => n + segLen(s), 0);

export const CHECK: Seg[] = [
  { clip: "r-check", from: 2.3, to: 8.9, rate: 1.0 },    // the question, B picked, locked in as Sure: a blind spot
  { clip: "r-check", from: 8.9, to: 14.1, rate: 2.6 },   // the photo goes up (a phone is shown over it)
  { clip: "r-check", from: 14.1, to: 23.0, rate: 1.2 },  // Gemini's reading: step 1 is where it went wrong
  { clip: "r-check", from: 23.0, to: 28.4, rate: 1.15 }, // the root behind the step
];
export const TRACE: Seg[] = [
  { clip: "r-check", from: 28.4, to: 33.5, rate: 1.3 },  // Fix the root: the chain, class by class
  { clip: "r-trace", from: 11.0, to: 24.5, rate: 2.0 },  // the student's finished trace: the root gap
  { clip: "r-trace", from: 25.3, to: 33.8, rate: 2.4 },  // the five-minute fix, in Hinglish
  { clip: "r-trace", from: 34.0, to: 38.6, rate: 0.9 },  // before and after: 1/3 -> 3/3
];
export const TEACHER: Seg[] = [
  { clip: "r-class", from: 2.6, to: 12.6, rate: 1.55 },
  { clip: "r-genome", from: 1.2, to: 17.0, rate: 2.6 },
];

/** The platform tour: each scene's footage (source seconds) is sped to fit its voice line. */
const tourDur = (id: string) => 0.3 + voLen(id) + 1.2;
const fit = (raw: [string, number, number][], dur: number): Seg[] => {
  const src = raw.reduce((n, [, a, b]) => n + (b - a), 0);
  return raw.map(([clip, from, to]) => ({ clip, from, to, rate: src / dur }));
};
export const TOUR: Record<string, Seg[]> = {
  tour1: fit([["r-landing", 0.4, 15.6]], tourDur("tour1")),
  tour2: fit([["live", 3.0, 12.0], ["live", 13.5, 31.0]], tourDur("tour2")),
  tour3: fit([["live", 32.6, 46.5]], tourDur("tour3")),
  tour4: fit([["exam", 5.0, 30.0], ["exam", 44.5, 60.5]], tourDur("tour4")),
  tour5: fit([["room-teacher", 0.0, 27.5]], tourDur("tour5")),
};

export const segStarts =(segs: Seg[]) => { let t = 0; return segs.map((s) => { const a = t; t += segLen(s); return a; }); };

const checkResult = segLen(CHECK[0]) + segLen(CHECK[1]);
const plan: Omit<Scene, "start" | "frames">[] = [
  { id: "hook", dur: 0.5 + voLen("hook") + 0.7, lines: [{ id: "hook", at: 0.5 }] },
  { id: "pain1", dur: 0.2 + voLen("pain1") + 0.6, lines: [{ id: "pain1", at: 0.2 }] },
  { id: "pain2", dur: 0.2 + voLen("pain2") + 0.7, lines: [{ id: "pain2", at: 0.2 }] },
  { id: "focs", dur: 1.4 + voLen("focs") + 1.0, lines: [{ id: "focs", at: 1.4 }] },
  { id: "check", dur: Math.max(sum(CHECK), checkResult + voLen("check2") + 0.4), lines: [{ id: "check1", at: 0.5 }, { id: "check2", at: checkResult }], segs: CHECK },
  { id: "trace", dur: Math.max(sum(TRACE), 0.3 + voLen("trace") + 0.3 + voLen("fix") + 0.4), lines: [{ id: "trace", at: 0.3 }, { id: "fix", at: 0.3 + voLen("trace") + 0.3 }], segs: TRACE },
  { id: "teacher", dur: Math.max(sum(TEACHER), 0.3 + voLen("teacher") + 0.4), lines: [{ id: "teacher", at: 0.3 }], segs: TEACHER },
  ...["tour1", "tour2", "tour3", "tour4", "tour5"].map((id) => ({ id, dur: sum(TOUR[id]), lines: [{ id, at: 0.3 }], segs: TOUR[id] })),
  { id: "tour6", dur: 0.3 + voLen("tour6") + 1.4, lines: [{ id: "tour6", at: 0.3 }] },
  { id: "tech", dur: 0.4 + voLen("tech") + 0.9, lines: [{ id: "tech", at: 0.4 }] },
  { id: "close", dur: 0.3 + voLen("close") + 5.0, lines: [{ id: "close", at: 0.3 }] },
];

let at = 0;
export const SCENES: Scene[] = plan.map((s) => {
  const frames = Math.round(s.dur * FPS);
  const out = { ...s, start: at, frames };
  at += frames;
  return out;
});
export const TOTAL = at;
export const scene = (id: string) => SCENES.find((s) => s.id === id)!;

/** Seconds into its scene at which a phrase of a voice line is spoken (by its share of the line's characters). */
export function when(sceneId: string, lineId: string, phrase: string, end = false): number {
  const s = scene(sceneId);
  const line = s.lines.find((l) => l.id === lineId)!;
  const text = VO_TEXT[lineId] ?? "";
  const i = text.indexOf(phrase);
  const k = i < 0 ? 0 : (i + (end ? phrase.length : 0)) / text.length;
  return line.at + voLen(lineId) * k;
}

/** Subtitles: each line cut at its punctuation into short phrases, timed by their share of the characters. */
export interface Sub { start: number; end: number; text: string }
export const SUBS: Sub[] = (() => {
  const out: Sub[] = [];
  for (const s of SCENES) {
    for (const l of s.lines) {
      const text = VO_TEXT[l.id] ?? "";
      const parts = text.match(/[^.!?:,]+[.!?:,]?/g)?.map((p) => p.trim()).filter(Boolean) ?? [text];
      // join tiny pieces so a subtitle has 3+ words
      const chunks: string[] = [];
      for (const p of parts) {
        const last = chunks[chunks.length - 1];
        if (last && (last.split(" ").length < 3 || p.split(" ").length < 2) && (last + " " + p).split(" ").length <= 9) chunks[chunks.length - 1] = last + " " + p;
        else chunks.push(p);
      }
      let pos = 0;
      const total = text.length;
      for (const c of chunks) {
        const i = text.indexOf(c, pos);
        const a = s.start / FPS + l.at + voLen(l.id) * (i / total);
        const b = s.start / FPS + l.at + voLen(l.id) * ((i + c.length) / total);
        out.push({ start: a, end: b + 0.12, text: c.replace(/[,:]$/, "") });
        pos = i + c.length;
      }
    }
  }
  return out;
})();
