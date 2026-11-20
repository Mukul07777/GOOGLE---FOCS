// Filming the real app: Chrome driven by Playwright, recorded through the DevTools screencast (sharper than
// Playwright's own video), with a visible cursor and click ripples drawn into the page.
import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const BASE = process.env.FOCS_URL || "http://127.0.0.1:8017";
export const CLIPS = path.join(ROOT, "public", "clips");
export const FFMPEG = path.join(ROOT, "node_modules", "@remotion", "compositor-win32-x64-msvc", "ffmpeg.exe");
export const PASSWORD = process.env.DEMO_PASSWORD || "focs-demo-2026";
export const THEME_KEY = "focs-look-4";
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** The desktop frame every clip is filmed at: a 1440 × 900 laptop screen, drawn at 1.5× so zooms stay sharp. */
export const DESKTOP = { width: 1440, height: 900, scale: 1.5 };
export const PHONE = { width: 390, height: 844, scale: 2 };

export async function api(pathname, { token, method = "GET", body, form } = {}) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["content-type"] = "application/json"; payload = JSON.stringify(body); }
  const r = await fetch(BASE + "/api" + pathname, { method, headers, body: payload });
  const text = await r.text();
  if (!r.ok) throw new Error(`${method} ${pathname} → ${r.status} ${text.slice(0, 300)}`);
  return text ? JSON.parse(text) : null;
}

export async function login(email, password = PASSWORD) {
  return api("/auth/login", { method: "POST", body: { email, password } });
}

export async function launch({ headless = true } = {}) {
  return chromium.launch({
    channel: "chrome", headless,
    args: ["--autoplay-policy=no-user-gesture-required", "--hide-scrollbars", "--force-color-profile=srgb",
           "--disable-features=Translate,MediaRouter", "--lang=en-IN"],
  });
}

/** What every filmed page gets: the cursor, its click ripples, no scrollbars, no caret blink. */
const STAGE = () => {
  const css = `
    html, body, * { scrollbar-width: none !important; }
    *::-webkit-scrollbar { display: none !important; }
    #__cur { position: fixed; left: 0; top: 0; width: 26px; height: 26px; z-index: 2147483647; pointer-events: none;
             transform: translate(-100px, -100px); transition: opacity .3s; filter: drop-shadow(0 2px 3px rgba(0,0,0,.35)); }
    .__rip { position: fixed; z-index: 2147483646; pointer-events: none; width: 14px; height: 14px; margin: -7px 0 0 -7px;
             border-radius: 50%; border: 2px solid #c8ff2e; background: rgba(200,255,46,.25); animation: __rip .55s ease-out forwards; }
    @keyframes __rip { to { transform: scale(4.2); opacity: 0; } }`;
  const add = () => {
    if (document.getElementById("__cur")) return;
    const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
    const c = document.createElement("div"); c.id = "__cur";
    c.innerHTML = `<svg viewBox="0 0 26 26" width="26" height="26"><path d="M3 2 L3 21 L8.2 16.4 L11.6 24 L15 22.5 L11.7 15.1 L18.6 15.1 Z" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
    document.documentElement.appendChild(c);
    const xy = window.__curXY || [-100, -100];
    c.style.transform = `translate(${xy[0] - 3}px, ${xy[1] - 2}px)`;
  };
  window.addEventListener("mousemove", (e) => {
    window.__curXY = [e.clientX, e.clientY];
    const c = document.getElementById("__cur"); if (c) c.style.transform = `translate(${e.clientX - 3}px, ${e.clientY - 2}px)`;
  }, true);
  window.addEventListener("mousedown", (e) => {
    const r = document.createElement("div"); r.className = "__rip"; r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px";
    document.documentElement.appendChild(r); setTimeout(() => r.remove(), 700);
  }, true);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", add); else add();
  new MutationObserver(add).observe(document, { childList: true, subtree: false });
};

/** A browser context signed in as `auth` (from login()), in the given look. */
export async function context(browser, { auth = null, theme = "light", device = DESKTOP, init = [] } = {}) {
  const ctx = await browser.newContext({
    viewport: { width: device.width, height: device.height }, deviceScaleFactor: device.scale,
    isMobile: device === PHONE, hasTouch: device === PHONE, locale: "en-IN", timezoneId: "Asia/Kolkata",
    permissions: ["microphone", "camera"],
  });
  await ctx.addInitScript(([a, t, key]) => {
    if (a) localStorage.setItem("focs-auth", JSON.stringify({ state: { token: a.access_token, user: a.user }, version: 0 }));
    else localStorage.removeItem("focs-auth");
    localStorage.setItem(key, t);
  }, [auth, theme, THEME_KEY]);
  await ctx.addInitScript(STAGE);
  for (const s of init) await ctx.addInitScript(s);
  return ctx;
}

/** Records a page through the DevTools screencast into public/clips/<name>.mp4 (30 fps, constant rate). */
export async function record(page, name, fn, { device = DESKTOP } = {}) {
  const dir = path.join(ROOT, ".frames", name);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  const cdp = await page.context().newCDPSession(page);
  const frames = [];
  let stopped = false;
  cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
    if (stopped) return;
    const file = `f${String(frames.length).padStart(6, "0")}.jpg`;
    fs.writeFileSync(path.join(dir, file), Buffer.from(data, "base64"));
    frames.push({ file, t: metadata.timestamp });
    cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
  });
  const W = Math.round(device.width * device.scale), H = Math.round(device.height * device.scale);
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  const t0 = Date.now() / 1000;
  const marks = [];
  const mark = (label) => marks.push({ label, t: Date.now() / 1000 - t0 });
  try {
    await fn(mark);
  } finally {
    await sleep(400);
    stopped = true;
    await cdp.send("Page.stopScreencast").catch(() => {});
    await cdp.detach().catch(() => {});
  }
  const end = Date.now() / 1000;
  if (!frames.length) throw new Error(`${name}: no frames recorded`);
  // a frame lasts until the next one arrives (the screencast only sends a frame when the page repaints)
  const lines = ["ffconcat version 1.0"];
  frames.forEach((f, i) => {
    const next = i + 1 < frames.length ? frames[i + 1].t : end;
    lines.push(`file '${f.file}'`, `duration ${Math.max(0.001, next - f.t).toFixed(4)}`);
  });
  lines.push(`file '${frames[frames.length - 1].file}'`);
  fs.writeFileSync(path.join(dir, "list.txt"), lines.join("\n"));
  fs.mkdirSync(CLIPS, { recursive: true });
  const out = path.join(CLIPS, `${name}.mp4`);
  execFileSync(FFMPEG, ["-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
    "-fps_mode", "cfr", "-r", "30", "-vf", `scale=${W}:${H}:flags=lanczos,format=yuv420p`, "-c:v", "libx264", "-preset", "medium",
    "-crf", "16", "-movflags", "+faststart", out], { cwd: dir });
  // time 0 of the clip is the first frame, a moment after recording began; marks are moved to match
  const seconds = end - frames[0].t;
  const meta = { name, seconds: +seconds.toFixed(2), frames: frames.length, fps: +(frames.length / seconds).toFixed(1), width: W, height: H,
                 marks: marks.map((m) => ({ ...m, t: +(m.t - (frames[0].t - t0)).toFixed(2) })) };
  fs.writeFileSync(path.join(CLIPS, `${name}.json`), JSON.stringify(meta, null, 2));
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(`  ${name}.mp4: ${meta.seconds}s, ${meta.frames} frames (${meta.fps}/s)`);
  return meta;
}

/* ---------------------------------------------------------------- moving like a person */
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/** Glide the cursor to a point (eased, about 60 steps a second). */
export async function glide(page, x, y, ms = 650) {
  const from = (await page.evaluate(() => window.__curXY)) || [x - 200, y + 120];
  const steps = Math.max(8, Math.round(ms / 16));
  for (let i = 1; i <= steps; i++) {
    const k = ease(i / steps);
    await page.mouse.move(from[0] + (x - from[0]) * k, from[1] + (y - from[1]) * k);
    await sleep(ms / steps);
  }
}

async function centre(page, locator) {
  await locator.waitFor({ state: "visible", timeout: 20000 });
  await locator.scrollIntoViewIfNeeded();
  const b = await locator.boundingBox();
  return [b.x + b.width / 2, b.y + b.height / 2];
}

/** Glide to an element, rest a beat, click it. */
export async function tap(page, locator, { ms = 650, rest = 220, after = 350 } = {}) {
  const [x, y] = await centre(page, locator);
  await glide(page, x, y, ms);
  await sleep(rest);
  await page.mouse.down(); await sleep(70); await page.mouse.up();
  await sleep(after);
}

export async function hover(page, locator, ms = 600) {
  const [x, y] = await centre(page, locator);
  await glide(page, x, y, ms);
}

/** Type into a field like a person (with the cursor going there first). */
export async function type(page, locator, text, { delay = 38 } = {}) {
  await tap(page, locator, { after: 150 });
  await locator.pressSequentially(text, { delay });
}

/** Smooth, eased scroll of whatever scrolls on the page (the window or the app's main column). */
export async function scroll(page, by, ms = 1400) {
  await page.evaluate(async ([by, ms]) => {
    // the scrolling box under the middle of the content (not the sidebar), else the page itself
    let el = document.elementFromPoint(window.innerWidth * 0.55, window.innerHeight * 0.6);
    const scrolls = (e) => e.scrollHeight > e.clientHeight + 4 && /(auto|scroll)/.test(getComputedStyle(e).overflowY);
    while (el && el !== document.body && !scrolls(el)) el = el.parentElement;
    if (!el || el === document.body) el = document.scrollingElement;
    const start = el.scrollTop, t0 = performance.now();
    const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    await new Promise((done) => {
      const step = (now) => {
        const k = Math.min(1, (now - t0) / ms);
        el.scrollTop = start + by * ease(k);
        k < 1 ? requestAnimationFrame(step) : done();
      };
      requestAnimationFrame(step);
    });
  }, [by, ms]);
  await sleep(150);
}

export async function scrollTo(page, locator, { offset = 120, ms = 1200 } = {}) {
  const top = await locator.evaluate((el) => el.getBoundingClientRect().top);
  await scroll(page, top - offset, ms);
}

/** Wait until the page is quiet (no requests in flight). */
export async function settle(page, ms = 600) {
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
  await sleep(ms);
}
