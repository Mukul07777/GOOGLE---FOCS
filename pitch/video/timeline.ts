// The edit as data (shots.json), with each shot's length in frames worked out. The music script reads the same file.
import data from "./shots.json";

export const FPS = data.fps;

export interface Segment { clip: string; from: number; to: number; rate: number; voice?: boolean }
export interface Callout { at: number; dur: number; x: number; y: number; text: string; big?: boolean; accent?: boolean }
export type Shot = Record<string, any> & { id: string; type: string; dur: number; segments?: Segment[]; callouts?: Callout[] };

export const segFrames = (s: Segment) => Math.round(((s.to - s.from) / s.rate) * FPS);
const frames = (s: Shot) => (s.segments?.length ? s.segments.reduce((n, g) => n + segFrames(g), 0) : Math.round(s.dur * FPS));

let at = 0;
export const SHOTS = (data.shots as Shot[]).map((s) => {
  const out = { ...s, start: at, frames: frames(s) };
  at += out.frames;
  return out;
});
export const TOTAL = at;
