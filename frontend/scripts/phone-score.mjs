// Phone and tablet score: every page at 360 and 768 px, signed out and as six kinds of student. Lists text cut off with
// "…", tap targets under 40 px and pages wider than the screen. The yearly activity chart is left out on purpose.
//   node scripts/phone-score.mjs [base-url]   (a local copy with LOGIN_EMAIL_CODE=false; its accounts are real rows there)
import { chromium } from "playwright";
const BASE = process.argv[2] || "http://127.0.0.1:8000";
const PUBLIC = ["/", "/login", "/signup", "/mentor/signup", "/privacy", "/terms", "/forgot-password"];
const APP = ["/app", "/app/studio", "/app/prep", "/app/plan", "/app/mock", "/app/practice", "/app/revise", "/app/flashcards", "/app/weak", "/app/rooms", "/app/campus", "/app/mentors", "/app/settings", "/app/library", "/app/leaderboard", "/app/formulas", "/app/snap", "/onboarding"];
const ACCOUNTS = ["neet", "jee", "ssc_cgl", "cbse_7", "cbse_12", "college_cse"];
const SIZES = [[360, 740], [768, 1024]];
const reg = async (exam) => (await (await fetch(`${BASE}/api/auth/register`, { method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: `sc.${exam}.${Date.now()}@example.com`, full_name: "Score Check", password: "Resp-check-123", accepted_terms: true, exam_target: exam }) })).json());
const check = () => {
  const out = { cut: [], small: [], wide: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 };
  for (const el of document.querySelectorAll("body *")) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const s = getComputedStyle(el);
    if (s.visibility === "hidden" || s.opacity === "0") continue;
    if (s.textOverflow === "ellipsis" && el.scrollWidth > el.clientWidth + 1) out.cut.push(`${el.textContent.trim().slice(0, 40)} [${Math.round(r.width)}px]`);
    if (!el.querySelector("button") && !el.closest("[aria-label^=\"Year\"]") && el.matches("a[href], button, [role=button], [role=tab], select, input:not([type=checkbox]):not([type=radio])") && !el.closest("p, label, nav[data-skip]")) {
      const hit = getComputedStyle(el, "::before").content !== "none" && getComputedStyle(el, "::before").position === "absolute" ? 20 : 0;
      if (!/^20[0-9][0-9]-/.test(el.getAttribute("aria-label") || el.textContent || "") && r.height + hit < 40 && (r.width + hit < 40 || r.height + hit < 36)) out.small.push(`${el.tagName.toLowerCase()} "${(el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 26)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
  }
  return out;
};
const b = await chromium.launch(process.env.RESP_CHANNEL ? { channel: process.env.RESP_CHANNEL } : {});
const seen = new Map(); let pages = 0;
const note = (kind, where, items) => { for (const i of items) { const k = `${kind} ${i}`; if (!seen.has(k)) seen.set(k, where); } };
for (const [w, h] of SIZES) {
  const out = await b.newContext({ viewport: { width: w, height: h }, isMobile: true, hasTouch: true });
  const p0 = await out.newPage();
  for (const path of PUBLIC) { await p0.goto(BASE + path); await p0.waitForTimeout(1000); const r = await p0.evaluate(check); pages++; note("CUT", `${w} out ${path}`, r.cut); note("SMALL", `${w} out ${path}`, r.small); if (r.wide) note("WIDE", `${w} out`, [path]); }
  await out.close();
  for (const exam of ACCOUNTS) {
    const a = await reg(exam);
    const c = await b.newContext({ viewport: { width: w, height: h }, isMobile: true, hasTouch: true });
    await c.addInitScript(([t, u]) => localStorage.setItem("focs-auth", JSON.stringify({ state: { token: t, user: u }, version: 0 })), [a.access_token, a.user]);
    const p = await c.newPage();
    for (const path of APP) { await p.goto(BASE + path); await p.waitForTimeout(1100); const r = await p.evaluate(check); pages++; note("CUT", `${w} ${exam} ${path}`, r.cut); note("SMALL", `${w} ${exam} ${path}`, r.small); if (r.wide) note("WIDE", `${w} ${exam}`, [path]); }
    await c.close();
  }
}
await b.close();
console.log(`${pages} page views, ${seen.size} distinct issues`);
for (const [k, where] of [...seen].sort()) console.log(`${k}  @ ${where}`);
