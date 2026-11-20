// Phone and tablet check: every page at four screen sizes, signed out and signed in (a Class 10, a Class 7 and an SSC
// student). Fails on a page wider than the screen, a script error, or an API call that fails; lists tap targets
// under 32 px and slow loads. Screenshots go to RESPONSIVE_SHOTS when it is set.
//   node scripts/responsive.mjs [base-url]      (a running Focs; default http://127.0.0.1:8000)
// Its accounts are deleted at the end (they are real rows in whatever database the server uses).
import fs from "node:fs";
import { chromium } from "playwright";

const BASE = (process.argv[2] || "http://127.0.0.1:8000").replace(/\/$/, "");
const SHOTS = process.env.RESPONSIVE_SHOTS;
const SCREENS = [
  { name: "phone-se", width: 375, height: 667, mobile: true },
  { name: "phone", width: 412, height: 915, mobile: true },
  { name: "tablet", width: 768, height: 1024, mobile: true },
  { name: "tablet-wide", width: 1024, height: 768, mobile: true },
];
const PUBLIC = ["/", "/login", "/signup", "/mentor/signup", "/pricing", "/privacy", "/terms", "/forgot-password"];
const STUDENT = ["/app", "/app/studio", "/app/prep", "/app/plan", "/app/mock", "/app/practice", "/app/revise", "/app/flashcards",
  "/app/weak", "/app/rooms", "/app/campus", "/app/mentors", "/app/settings", "/app/library", "/app/leaderboard", "/app/formulas", "/app/snap", "/app/classes"];
const ACCOUNTS = [
  { exam_target: "neet", class_level: "12" },
  { exam_target: "jee", class_level: "12" },
  { exam_target: "cbse_10", class_level: "Class 10" },
  { exam_target: "cbse_7", class_level: "Class 7" },
  { exam_target: "ssc_cgl" },
];
const PASSWORD = "Resp-check-123";

async function account(extra) {
  const email = `resp.${extra.exam_target}.${Date.now()}@example.com`;
  const r = await fetch(`${BASE}/api/auth/register`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, full_name: "Resp Check", password: PASSWORD, accepted_terms: true, ...extra }),
  });
  if (!r.ok) throw new Error(`sign-up failed: ${r.status} ${await r.text()}`);
  return { email, ...(await r.json()) };
}

const problems = [];
const notes = [];
const browser = await chromium.launch(process.env.RESP_CHANNEL ? { channel: process.env.RESP_CHANNEL } : {});

async function visit(context, screen, path, who) {
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(`script: ${e.message.slice(0, 160)}`));
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|sentry|Failed to load resource/i.test(m.text())) errors.push(`console: ${m.text().slice(0, 160)}`); });
  page.on("response", (r) => {
    const u = r.url();
    if (u.startsWith(BASE + "/api/") && r.status() >= 400 && !(r.status() === 403 && u.includes("/mock")) && !(r.status() === 404 && /\/(last-day|goal)$/.test(u)))
      errors.push(`api ${r.status()}: ${u.replace(BASE, "")}`);
  });
  const t0 = Date.now();
  const res = await page.goto(BASE + path, { waitUntil: "networkidle", timeout: 45000 }).catch((e) => ({ status: () => 0, e }));
  const ms = Date.now() - t0;
  await page.waitForTimeout(700);
  const where = `${screen.name} ${who} ${path}`;
  const layout = await page.evaluate(() => {
    const w = document.documentElement.clientWidth;
    const wide = [];
    for (const el of document.querySelectorAll("body *")) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const style = getComputedStyle(el);
      if (style.position === "fixed" && r.right <= w + 1) continue;
      if (r.right > w + 2 && !el.closest("[data-scroll-x], .overflow-x-auto, .overflow-auto, .overflow-x-scroll, pre, table")) {
        wide.push(`${el.tagName.toLowerCase()}${el.className && typeof el.className === "string" ? "." + el.className.split(" ").slice(0, 3).join(".") : ""} right=${Math.round(r.right)}`);
      }
    }
    const small = [];
    for (const el of document.querySelectorAll("a[href], button, [role=button], input, select")) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0 || getComputedStyle(el).visibility === "hidden") continue;
      if (r.height < 32 && r.width < 32) small.push(`${el.tagName.toLowerCase()} "${(el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
    return { scroll: document.documentElement.scrollWidth, width: w, wide: wide.slice(0, 5), small: small.slice(0, 6) };
  });
  if (layout.scroll > layout.width + 1) problems.push(`${where}: page is ${layout.scroll}px wide on a ${layout.width}px screen  ${layout.wide.join(" | ")}`);
  if (!res || res.status() >= 500 || res.status() === 0) problems.push(`${where}: page load failed (${res?.status?.()})`);
  for (const e of [...new Set(errors)]) problems.push(`${where}: ${e}`);
  if (layout.small.length) notes.push(`${where}: small tap targets: ${layout.small.join(", ")}`);
  if (ms > 4000) notes.push(`${where}: loaded in ${ms} ms`);
  if (SHOTS) {
    fs.mkdirSync(SHOTS, { recursive: true });
    await page.screenshot({ path: `${SHOTS}/${screen.name}${who === "out" ? "" : "-" + who}${path.replace(/\//g, "_") || "_home"}.png` });
  }
  console.log(`${layout.scroll > layout.width + 1 || errors.length ? "FAIL" : "ok  "}  ${where}  ${ms} ms`);
  await page.close();
}

const made = [];
try {
  for (const screen of SCREENS) {
    const opts = { viewport: { width: screen.width, height: screen.height }, isMobile: screen.mobile, hasTouch: true, deviceScaleFactor: 2 };
    const out = await browser.newContext(opts);
    for (const p of PUBLIC) await visit(out, screen, p, "out");
    await out.close();
    for (const a of ACCOUNTS) {
      const acc = await account(a);
      made.push(acc);
      const ctx = await browser.newContext(opts);
      await ctx.addInitScript(([token, u]) => localStorage.setItem("focs-auth", JSON.stringify({ state: { token, user: u }, version: 0 })), [acc.access_token, acc.user]);
      for (const p of STUDENT) await visit(ctx, screen, p, a.exam_target);
      await ctx.close();
    }
  }
} finally {
  await browser.close();
  for (const a of made) {  // leave no test accounts behind
    await fetch(`${BASE}/api/auth/delete-account`, {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${a.access_token}` },
      body: JSON.stringify({ password: PASSWORD, confirm: "DELETE" }),
    }).catch(() => {});
  }
}

if (notes.length) console.log(`\nNotes (${notes.length}):\n  ${[...new Set(notes)].join("\n  ")}`);
if (problems.length) {
  console.log(`\n${problems.length} problems:\n  ${problems.join("\n  ")}`);
  process.exit(1);
}
console.log("\nEvery page fits every screen, with no script or API errors.");
