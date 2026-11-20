import { create } from "zustand";

type Theme = "dark" | "light";

/** Where the choice is kept. A new key (it was "focs-look-3") so everyone opens the editorial redesign in Stone once;
    from then on their own choice sticks. index.html reads it before the first paint, scripts/a11y.mjs sets it. */
export const THEME_KEY = "focs-look-4";
const STONE = "#e9e7e3";
const INK = "#0e0e0d";

const initial = (): Theme => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");

export const useTheme = create<{ theme: Theme; toggle: () => void }>((set, get) => ({
  theme: initial(),
  toggle: () => {
    const next: Theme = get().theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", next === "dark" ? INK : STONE);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* private mode */
    }
    set({ theme: next });
  },
}));
