import { create } from "zustand";
import { persist } from "zustand/middleware";

/** Accessibility settings (Settings → Accessibility), kept on this device and applied to the whole page:
    text size, wider spacing, a font made for legibility, stronger contrast, less motion and the read-aloud speed. */
export interface A11y {
  textScale: number;       // 1, 1.15, 1.3, 1.5
  spacing: boolean;        // wider line and letter spacing
  legible: boolean;        // Atkinson Hyperlegible instead of Inter
  contrast: boolean;       // stronger secondary text and borders
  reduceMotion: boolean;   // on top of the device's own setting
  speechRate: number;      // read-aloud speed, 0.8–1.4
}

const DEFAULTS: A11y = { textScale: 1, spacing: false, legible: false, contrast: false, reduceMotion: false, speechRate: 1 };

export function applyA11y(s: A11y): void {
  const el = document.documentElement;
  el.style.setProperty("--a11y-zoom", String(s.textScale));
  el.dataset.zoom = s.textScale !== 1 ? "on" : "off";
  el.dataset.spacing = s.spacing ? "wide" : "normal";
  el.dataset.font = s.legible ? "legible" : "default";
  el.dataset.contrast = s.contrast ? "high" : "normal";
  el.dataset.motion = s.reduceMotion ? "reduce" : "system";
}

export const useA11y = create<A11y & { set: (patch: Partial<A11y>) => void; reset: () => void }>()(
  persist(
    (set, get) => ({
      ...DEFAULTS,
      set: (patch) => { set(patch); applyA11y({ ...get(), ...patch }); },
      reset: () => { set(DEFAULTS); applyA11y(DEFAULTS); },
    }),
    { name: "focs-a11y", onRehydrateStorage: () => (state) => applyA11y(state ?? DEFAULTS) },
  ),
);
