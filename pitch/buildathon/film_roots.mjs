// Films the root-cause story (the Google Startup Buildathon edition, VITE_EDITION=roots) into public/clips/r-*.mp4.
//
//   node buildathon/film_roots.mjs [scene ...]      (no names: every scene)
//
// Needs the filming server on FOCS_URL (default :8017) serving the roots build, seeded with backend/scripts/seed_demo.py.
// Staged: only the practice question (one fixed torque MCQ, so the photographed working matches it). Everything else,
// the working check by Gemini included, is the real server.
import path from "node:path";
import { api, context, DESKTOP, glide, hover, launch, login, record, ROOT, scroll, scrollTo, settle, sleep, tap, type, BASE } from "../shoot/lib.mjs";

const email = (k) => `demo.focs.${k}@example.com`;
const PAPER = path.join(ROOT, "public", "bt", "paper.jpg");

const QUIZ = {
  topic: "Rotational Motion", subject: "Physics", source: "text", notice: null, session_id: null,
  mcq: [{
    q: "A force of 10 N acts on the end of a 2 m spanner, at 30° to the spanner. What is the torque about the bolt?",
    options: ["10 N·m", "17.3 N·m", "20 N·m", "5 N·m"], answer_index: 0,
    explanation: "τ = r F sin θ = 2 × 10 × sin 30° = **10 N·m**. θ is the angle between the spanner and the force, so it's sin θ, not cos θ.",
  }],
  true_false: [], subjective: [],
};

let browser;
const auths = {};
const as = async (who) => (auths[who] ??= await login(email(who)));

// the guided tour is for a first visit, not the film
const NO_TOUR = `for (let i = 0; i <= 40; i++) localStorage.setItem("focs.tour.done." + i, "1"); localStorage.setItem("focs.tour.done.anon", "1");`;

async function open(who, url, init = []) {
  const ctx = await context(browser, { auth: who ? await as(who) : null, theme: "light", device: DESKTOP, init: [NO_TOUR, ...init] });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => console.log("    page error:", e.message.slice(0, 160)));
  p.on("dialog", (d) => d.accept());
  if (url) { await p.goto(BASE + url, { waitUntil: "domcontentloaded" }); await settle(p, 900); }
  return p;
}

const SCENES = {
  /** The landing page, signed out: scrolled top to bottom. */
  async "r-landing"() {
    const p = await open(null, "/");
    return record(p, "r-landing", async (mark) => {
      await sleep(1400);
      mark("hero");
      for (let i = 0; i < 6; i++) { await scroll(p, 620, 1500); await sleep(700); }
      mark("end");
    });
  },

  /** Dashboard: "Your real gap" where the student already looks. */
  async "r-home"() {
    const p = await open("student", "/app");
    return record(p, "r-home", async (mark) => {
      await sleep(900);
      const card = p.getByText(/Your real gap|Aapki asli gap/).first();
      await hover(p, card, 900);
      mark("card");
      await sleep(1600);
      await scroll(p, 260, 1600);
      await sleep(1200);
    });
  },

  /** Practice: torque answered Sure and wrong, then a photo of the paper working, checked by Gemini. */
  async "r-check"() {
    const p = await open("student", "/app/practice");
    await p.route("**/api/quiz/generate", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(QUIZ) }));
    await p.getByText(/^(Paste material|Material paste karo)$/).click();
    await p.getByPlaceholder(/Paste notes/).fill("Torque: τ = r F sin θ, where θ is the angle between r and F. Rotational motion of a rigid body.");
    await p.getByRole("button", { name: /^(Generate|Banao)$/ }).click();
    await p.getByText(/Question 1 of 1/).waitFor({ timeout: 20000 });
    await sleep(700);
    return record(p, "r-check", async (mark) => {
      await sleep(700);
      await hover(p, p.getByText(/A force of 10 N/), 900);
      await sleep(900);
      mark("pick");
      await tap(p, p.getByRole("button", { name: /17\.3 N·m/ }));
      await sleep(500);
      mark("sure");
      await tap(p, p.getByRole("button", { name: /^(Sure|Pakka)/ }));
      await sleep(2200);
      mark("photo");
      const chooser = p.waitForEvent("filechooser");
      await tap(p, p.getByRole("button", { name: /Check my paper working/ }), { after: 100 });
      await (await chooser).setFiles(PAPER);
      mark("reading");
      await p.getByText("Your working, checked").waitFor({ timeout: 120000 });
      mark("checked");
      await sleep(900);
      await scrollTo(p, p.getByText("Your working, checked"), { offset: 90, ms: 1500 });
      await sleep(1200);
      const wrong = p.locator("li").filter({ hasText: /first slip/ }).first();
      if (await wrong.count()) await hover(p, wrong, 900);
      await sleep(2200);
      const rootBox = p.getByText("The root behind this step");
      if (await rootBox.count()) {
        await scrollTo(p, rootBox, { offset: 260, ms: 1500 });
        mark("root");
        await hover(p, rootBox, 800);
        await sleep(2400);
        const go = p.getByRole("button", { name: /Open your trace|Revisit your fix|Fix the root in 5 minutes/ }).first();
        await hover(p, go, 700);
        await sleep(700);
        mark("go");
        await tap(p, go, { after: 200 });
        await p.waitForURL(/\/app\/roots\?trace=/, { timeout: 60000 }).catch(() => {});
        await settle(p, 1200);
        await sleep(1800);
      } else {
        await scroll(p, 300, 1500);
        await sleep(2500);
      }
    });
  },

  /** Root cause: Focs noticed, how you lose marks, then the fixed trace: the root gap, the Hinglish fix, 1/3 -> 3/3. */
  async "r-trace"() {
    const tok = (await as("student")).access_token;
    const ov = await api("/gaps", { token: tok });
    const t = ov.traces.find((x) => x.status === "fixed") ?? ov.traces[0];
    const p = await open("student", "/app/roots");
    return record(p, "r-trace", async (mark) => {
      await sleep(900);
      const noticed = p.getByText("Focs noticed").first();
      if (await noticed.count()) { await hover(p, noticed, 900); mark("noticed"); await sleep(2600); }
      const fp = p.getByText("How you lose marks");
      if (await fp.count()) { await scrollTo(p, fp, { offset: 140, ms: 1500 }); mark("fingerprint"); await sleep(2600); }
      const row = p.getByRole("button").filter({ hasText: t.title }).first();
      await scrollTo(p, row, { offset: 300, ms: 1200 });
      await sleep(500);
      mark("open");
      await tap(p, row);
      await settle(p, 900);
      await sleep(1200);
      mark("chain");
      await scroll(p, 520, 2600); await sleep(900);
      const gap = p.getByText("Root gap").first();
      if (await gap.count()) { await scrollTo(p, gap, { offset: 200, ms: 1800 }); mark("root"); await hover(p, gap, 700); await sleep(2000); }
      const real = p.getByText(/^The real gap:/).first();
      if (await real.count()) { await scrollTo(p, real, { offset: 110, ms: 1800 }); mark("lesson"); await sleep(1500); await scroll(p, 420, 3800); await sleep(1200); }
      const ba = p.getByText(/before and after/i).first();
      if (await ba.count()) { await scrollTo(p, ba, { offset: 240, ms: 1800 }); mark("proof"); await hover(p, ba, 700); await sleep(3200); }
    });
  },

  /** Gap Genome: the map of what JEE and NEET chapters really rest on. */
  async "r-genome"() {
    const p = await open("student", "/app/genome");
    return record(p, "r-genome", async (mark) => {
      await sleep(1500);
      const svg = p.locator("svg circle").first();
      await svg.waitFor({ timeout: 15000 }).catch(() => {});
      const nodes = p.locator("svg g circle");
      const n = await nodes.count();
      mark("map");
      for (const k of [0, Math.floor(n / 3), Math.floor(n / 2)]) {
        if (k >= n) continue;
        const b = await nodes.nth(k).boundingBox().catch(() => null);
        if (b) { await glide(p, b.x + b.width / 2, b.y + b.height / 2, 800); await sleep(900); }
      }
      if (n) { await tap(p, nodes.first()); mark("picked"); await sleep(2200); }
      const lb = p.getByText("Most load-bearing school chapters");
      if (await lb.count()) { await scrollTo(p, lb, { offset: 160, ms: 1800 }); mark("load"); await sleep(2600); }
    });
  },

  /** The teacher: where the batch's gaps really start, and what to teach first. */
  async "r-class"() {
    const tok = (await as("teacher")).access_token;
    const list = await api("/classes", { token: tok });
    const rows = list.classes ?? list.teaching ?? list.items ?? list;
    const cls = (Array.isArray(rows) ? rows : Object.values(rows).flat()).find((c) => c && c.id);
    const p = await open("teacher", `/app/classes/${cls.id}`);
    return record(p, "r-class", async (mark) => {
      await sleep(1200);
      const where = p.getByText("Where the gaps really start");
      await scrollTo(p, where, { offset: 110, ms: 1800 });
      mark("map");
      await sleep(1200);
      const first = p.getByText(/Teach first:/).first();
      if (await first.count()) { await hover(p, first, 900); mark("first"); await sleep(3000); }
      await scroll(p, 300, 1800);
      await sleep(1600);
    });
  },
};

browser = await launch({ headless: true });
try {
  const names = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(SCENES);
  for (const n of names) {
    console.log(`scene ${n}`);
    try { await SCENES[n](); } catch (e) { console.log(`  ${n} failed: ${e.message.slice(0, 400)}`); }
  }
} finally {
  await browser.close();
}
