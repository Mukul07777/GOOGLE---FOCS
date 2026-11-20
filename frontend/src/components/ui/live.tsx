import { useEffect, useRef, useState } from "react";

/* The live bits of Focs's AI layer: numbers that count up and things that lean toward the pointer. Both stand still
   for anyone who asks for less motion (the device setting or Settings → Accessibility). */

const still = () =>
  typeof window === "undefined" ||
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ||
  document.documentElement.dataset.motion === "reduce";

/** A number that counts up the first time it scrolls into view, and glides to a new value when it changes. */
export function CountUp({ value, decimals = 0, duration = 1200 }: { value: number; decimals?: number; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const shown = useRef(still() ? value : 0);
  const seen = useRef(false);
  const [n, setN] = useState(shown.current);

  useEffect(() => {
    if (still()) {
      shown.current = value;
      setN(value);
      return;
    }
    let frame = 0;
    const animate = () => {
      const from = shown.current;
      const start = performance.now();
      const tick = (t: number) => {
        const p = Math.min(1, (t - start) / duration);
        const x = from + (value - from) * (1 - Math.pow(1 - p, 3));
        shown.current = x;
        setN(x);
        if (p < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    };
    if (seen.current) {
      animate();
      return () => cancelAnimationFrame(frame);
    }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      seen.current = true;
      animate();
    }, { threshold: 0.35 });
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [value, duration]);

  return <span ref={ref} className="tabular-nums">{n.toFixed(decimals)}</span>;
}

/** Leans an element toward the pointer in 3-D (the .tilt class reads --rx and --ry). Mouse and pen only. */
export function useTilt<T extends HTMLElement>(max = 4) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || still() || !window.matchMedia?.("(hover: hover)").matches) return;
    let frame = 0;
    const move = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        el.style.setProperty("--ry", `${(x * max * 2).toFixed(2)}deg`);
        el.style.setProperty("--rx", `${(-y * max * 2).toFixed(2)}deg`);
        el.dataset.tilting = "";
      });
    };
    const leave = () => {
      cancelAnimationFrame(frame);
      el.style.setProperty("--rx", "0deg");
      el.style.setProperty("--ry", "0deg");
      delete el.dataset.tilting;
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", leave);
    return () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", leave);
      cancelAnimationFrame(frame);
    };
  }, [max]);
  return ref;
}
