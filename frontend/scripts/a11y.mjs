// Accessibility check: axe-core (WCAG 2.1 A and AA rules) on the pages a judge or a student sees first, signed out
// and signed in. Fails on any serious or critical violation.
//   node scripts/a11y.mjs [base-url]        (a running Focs; default http://127.0.0.1:8000)
//   A11Y_CHANNEL=msedge node scripts/a11y.mjs   (use an installed browser instead of Playwright's Chromium)
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";

const BASE = (process.argv[2] || "http://127.0.0.1:8000").replace(/\/$/, "");
const PUBLIC = ["/", "/login", "/signup", "/mentor/signup", "/privacy", "/terms"];
const SIGNED_IN = ["/app", "/app/studio", "/app/weak", "/app/rooms", "/app/campus", "/app/prep", "/app/revise", "/app/practice", "/app/flashcards", "/app/mentors", "/app/settings"];
const MENTOR = ["/mentor", "/mentor/profile"];  // a new mentor account: the application form, and the account settings

async function account(role = "student") {
  const email = `a11y.${role}.${Date.now()}@example.com`;
  const r = await fetch(`${BASE}/api/auth/register`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, full_name: "Axe Check", password: "a11y-check-123", exam_target: "jee", class_level: "Class 12", accepted_terms: true, role }),
  });
  if (!r.ok) throw new Error(`sign-up failed: ${r.status} ${await r.text()}`);
  return r.json();
}

const browser = await chromium.launch(process.env.A11Y_CHANNEL ? { channel: process.env.A11Y_CHANNEL } : {});
const failures = [];
async function check(page, path) {
  await page.goto(BASE + path, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);  // entrance animations settle
  const { violations } = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  for (const v of bad) failures.push({ path, id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) });
  console.log(`${bad.length ? "FAIL" : "ok  "}  ${path}${bad.length ? `  (${bad.map((v) => v.id).join(", ")})` : ""}`);
}

for (const theme of ["dark", "light"]) {
  const context = await browser.newContext();
  await context.addInitScript((t) => localStorage.setItem("focs-look-4", t), theme);
  const page = await context.newPage();
  console.log(`-- ${theme} theme, signed out`);
  for (const path of PUBLIC) await check(page, path);
  const { access_token, user } = await account();
  await context.addInitScript(([token, u]) => localStorage.setItem("focs-auth", JSON.stringify({ state: { token, user: u }, version: 0 })), [access_token, user]);
  console.log(`-- ${theme} theme, signed in`);
  for (const path of SIGNED_IN) await check(page, path);
  await context.close();
  const mentorContext = await browser.newContext();
  const m = await account("mentor");
  await mentorContext.addInitScript(([t, token, u]) => {
    localStorage.setItem("focs-look-4", t);
    localStorage.setItem("focs-auth", JSON.stringify({ state: { token, user: u }, version: 0 }));
  }, [theme, m.access_token, m.user]);
  const mentorPage = await mentorContext.newPage();
  console.log(`-- ${theme} theme, a mentor account`);
  for (const path of MENTOR) await check(mentorPage, path);
  await mentorContext.close();
}
await browser.close();

if (failures.length) {
  console.log(`\n${failures.length} serious or critical accessibility problems:`);
  for (const f of failures) console.log(`  ${f.path}  [${f.impact}] ${f.id}: ${f.help}\n    ${f.nodes.join("\n    ")}`);
  process.exit(1);
}
console.log("\nNo serious or critical accessibility problems.");
