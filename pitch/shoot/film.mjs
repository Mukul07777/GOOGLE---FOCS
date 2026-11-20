// Films the real app, one scene at a time, into public/clips/<scene>.mp4 (+ .json with timing marks).
//
//   node shoot/film.mjs live quiz lecture ...     (no names: every scene, in order)
//
// Needs the filming server (see pitch/README.md) seeded with backend/scripts/seed_demo.py and shoot/seed.mjs.
import fs from "node:fs";
import path from "node:path";
import { api, BASE, context, DESKTOP, glide, hover, launch, login, PHONE, record, ROOT, scroll, scrollTo, settle, sleep, tap, type } from "./lib.mjs";

const email = (k) => `demo.focs.${k}@example.com`;
const LECTURE_JS = fs.readFileSync(path.join(ROOT, "shoot", "lecture-stream.js"), "utf8");
const TEACHER = JSON.parse(fs.readFileSync(path.join(ROOT, "public", "audio", "teacher.json"), "utf8"));

// the boards the teacher writes, in step with her voice (shoot/make_voice.py)
const LECTURE = {
  audio: "/__pitch/teacher.mp3", teacher: "Neha Kapoor · Physics", title: "Rotational Motion · L14", subtitle: "Class 12 · JEE Main & Advanced",
  speech: TEACHER.speech,
  boards: [
    { start: 1.0, end: 46.0, at: [0, 4.2, 8.8, 13.2], lines: ["Rotational Motion", "τ = r × F", "τ = I α", "Ring:  I = M R²"] },
    { start: 48.2, at: [0.4, 5.0, 9.6, 15.5], lines: ["Rolling without slipping", "v = ω R", "KE = ½ M v² + ½ I ω²", "Static friction:  W = 0"] },
  ],
};

let browser;
const auths = {};
async function as(who) {
  auths[who] ??= await login(who.includes("@") ? who : email(who));
  return auths[who];
}

async function page({ who = "student", theme = "light", device = DESKTOP, init = [], url }) {
  const ctx = await context(browser, { auth: who ? await as(who) : null, theme, device, init });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => console.log("    page error:", e.message.slice(0, 160)));
  p.on("dialog", (d) => d.accept());  // the dev server's test payment asks "Continue?"
  if (url) { await p.goto(BASE + url, { waitUntil: "domcontentloaded" }); await settle(p, 900); }
  return p;
}

const SCENES = {
  /** Live lecture: share the lecture tab, crop to the board, notes and captions arrive, a pop quiz locked in as Sure. */
  async live() {
    const token = (await as("student")).access_token;
    for (const s of await api("/sessions?limit=50", { token })) {  // earlier takes of this scene
      if (s.title?.startsWith("Rotational Motion")) await api(`/sessions/${s.id}`, { method: "DELETE", token });
    }
    const p = await page({ url: "/app/studio", init: [`window.__LECTURE = ${JSON.stringify(LECTURE)};`, LECTURE_JS] });
    await p.route("**/__pitch/teacher.mp3", (r) => r.fulfill({ path: path.join(ROOT, "public", "audio", "teacher.mp3"), contentType: "audio/mpeg" }));
    let quizAnswer = null;
    p.on("response", async (r) => { if (r.url().includes("/pop-quiz")) quizAnswer = await r.json().catch(() => null); });
    return record(p, "live", async (mark) => {
      await sleep(600);
      await type(p, p.getByPlaceholder("e.g. Rotational Motion — Lecture 4"), "Rotational Motion · Lecture 14");
      await p.getByLabel("Subject").selectOption("Physics");
      await sleep(300);
      mark("share");
      await tap(p, p.getByRole("button", { name: /Share a lecture tab/ }));
      const video = p.locator("video").first();
      await video.waitFor({ state: "visible" });
      await sleep(2200);
      mark("crop");
      const b = await video.boundingBox();
      const fx = (x) => b.x + (x / 1920) * b.width, fy = (y) => b.y + (y / 1080) * b.height;
      await glide(p, fx(1392), fy(48), 700);
      await p.mouse.down();
      await glide(p, fx(48), fy(894), 1100);
      await p.mouse.up();
      mark("cropped");
      await p.getByText(/^Notes · 1/).waitFor({ timeout: 90000 });
      mark("note1");
      await sleep(2500);
      await hover(p, p.getByText(/^Notes · 1/), 500);
      while ((await p.evaluate(() => (performance.now() - (window.__lectureT0 || 0)) / 1000)) < 27) await sleep(500);
      mark("quiz");
      await tap(p, p.getByRole("button", { name: "Quiz me now" }));
      const dlg = p.getByRole("dialog");
      await dlg.locator("button[aria-pressed]").first().waitFor({ timeout: 60000 });
      await sleep(1800);
      const opts = dlg.locator("button[aria-pressed]");
      const right = quizAnswer?.answer_index ?? quizAnswer?.answer ?? 0;
      const wrong = (typeof right === "number" ? right + 1 : 1) % (await opts.count());
      await tap(p, opts.nth(wrong));
      await sleep(500);
      mark("lock");
      await tap(p, dlg.getByRole("button", { name: /^Sure/ }));
      await sleep(3500);
      mark("verdict");
      await tap(p, dlg.getByRole("button", { name: /Continue lecture/ }));
      await p.getByText(/Rolling without slipping/i).first().waitFor({ timeout: 120000 });
      mark("note2");
      await sleep(4000);
      const panel = p.locator("div.overflow-y-auto").last();
      await panel.evaluate((el) => el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }));
      await sleep(3000);
      mark("end");
    }).finally(async () => {
      const live = (await api("/sessions?limit=5", { token })).find((s) => s.title?.startsWith("Rotational Motion"));
      if (live && !live.ended_at) await api(`/sessions/${live.id}/end`, { method: "POST", token }).catch((e) => console.log("    end:", e.message));
    });
  },
};

Object.assign(SCENES, {
  /** The lecture afterwards: what the teacher said (summary, exact words a tap away), the notes, the revision sheet. */
  async lecture() {
    const p = await page({ url: "/app/library" });
    return record(p, "lecture", async (mark) => {
      await sleep(900);
      await tap(p, p.getByText(/Rotational Motion · Lecture 14/).first());
      await settle(p, 1200);
      mark("open");
      await scroll(p, 520, 2200); await sleep(1400);
      await scroll(p, 620, 2200); await sleep(1400);
      mark("sheet");
      await tap(p, p.getByRole("button", { name: /Revision sheet/ }).first()).catch(() => {});
      await sleep(1600);
      await scroll(p, 600, 2400); await sleep(1500);
      mark("end");
    });
  },

  /** The same lecture for a Hindi-medium student: notes and the whole interface in Hindi, formulas untouched. */
  async hindi() {
    const p = await page({ who: "hindi", url: "/app/library" });
    return record(p, "hindi", async (mark) => {
      await sleep(800);
      await tap(p, p.locator("a[href^='/app/library/']").first());
      await settle(p, 1200);
      mark("open");
      await scroll(p, 700, 2600); await sleep(1600);
      await scroll(p, 600, 2400); await sleep(1400);
    });
  },

  /** Flashcards from the lecture, spaced repetition. */
  async flashcards() {
    const p = await page({ url: "/app/flashcards" });
    return record(p, "flashcards", async () => {
      await sleep(1200);
      for (const grade of ["Good", "Easy", "Good"]) {
        await p.keyboard.press("Space"); await sleep(1500);
        await tap(p, p.getByRole("button", { name: new RegExp(`^${grade}`) }).first(), { after: 900 }).catch(() => {});
      }
    });
  },

  /** A chapter test the bank can't fill yet: the warm-up from the student's own notes while the AI writes the paper. */
  async warmup() {
    const token = (await as("student")).access_token;
    for (const t of await api("/mock", { token })) if (t.status === "preparing" || t.status === "ready") await api(`/mock/${t.id}`, { method: "DELETE", token }).catch(() => {});
    const p = await page({ url: "/app/mock" });
    return record(p, "warmup", async (mark) => {
      await sleep(700);
      await scrollTo(p, p.getByRole("button", { name: /^Rotational Motion/ }), { offset: 380 });
      await tap(p, p.getByRole("button", { name: /^Rotational Motion/ }));
      await tap(p, p.getByText("10 Q", { exact: true }));
      mark("start");
      await tap(p, p.getByRole("button", { name: "Start chapter test" }));
      await p.waitForURL(/\/app\/mock\/\d+/);
      await settle(p, 1500);
      mark("warmup");
      await scroll(p, 380, 1800); await sleep(2500);
      await tap(p, p.getByRole("button", { name: /Think, then show the answer|Show the answer/ }).first()).catch(() => {});
      await sleep(2500);
      await scroll(p, 420, 1800); await sleep(3000);
      mark("end");
    });
  },

  /** The NTA-style test screen, a paper answered (a few confidently wrong), submitted, and the gap map that comes back. */
  async exam() {
    const token = (await as("student")).access_token;
    for (const t of await api("/mock", { token })) {  // earlier takes
      if (t.status === "in_progress") await api(`/mock/${t.id}/submit`, { method: "POST", token, body: {} }).catch(() => {});
      else if (t.status === "preparing" || t.status === "ready") await api(`/mock/${t.id}`, { method: "DELETE", token }).catch(() => {});
    }
    const made = await api("/mock", { method: "POST", token, body: { pattern: "chapter", subject: "Physics", chapters: ["Laws of Motion", "Work, Energy & Power"], count: 10 } });
    for (let i = 0; i < 90; i++) { if ((await api(`/mock/${made.id}`, { token })).status !== "preparing") break; await sleep(2000); }
    const { execFileSync } = await import("node:child_process");
    const answers = JSON.parse(execFileSync(process.env.FOCS_PY || "python", [path.join(ROOT, "shoot", "answers.py"), process.env.FOCS_DB, String(made.id)]).toString());
    const p = await page({ url: `/app/mock/${made.id}` });
    return record(p, "exam", async (mark) => {
      await sleep(900);
      await tap(p, p.getByText("I have read and understood the instructions."));
      await tap(p, p.getByRole("button", { name: /I am ready to begin/ }));
      await p.waitForURL(/\/exam\/\d+/);
      await settle(p, 1200);
      mark("paper");
      const plan = ["right", "right", "sure-wrong", "right", "guess-wrong", "right", "sure-wrong", "right", "right", "guess-right"];
      for (let i = 0; i < answers.length; i++) {
        const opts = p.locator("button:has(> span.h-6.w-6.rounded-full)");
        const n = await opts.count();
        const fast = i >= 3;  // the first three at a person's pace, then quicker (the edit speeds this up)
        if (n) {
          const right = Number(answers[i]) || 0;
          const how = plan[i] || "right";
          const pick = how.includes("wrong") ? (right + 1) % n : right;
          await tap(p, opts.nth(pick), { ms: fast ? 260 : 600, after: fast ? 120 : 350 });
          const conf = how.startsWith("sure") || how === "right" ? "Sure" : "Guessing";
          await tap(p, p.getByRole("button", { name: conf, exact: true }), { ms: fast ? 220 : 450, after: fast ? 80 : 250 });
        } else if (await p.getByPlaceholder("Type your answer").count()) {  // a numerical question
          const how = plan[i] || "right";
          const value = how.includes("wrong") ? String(Math.round(Number(answers[i]) * 2) || 7) : String(answers[i]);
          await type(p, p.getByPlaceholder("Type your answer"), value, { delay: 90 });
          const conf = how.startsWith("sure") || how === "right" ? "Sure" : "Guessing";
          await tap(p, p.getByRole("button", { name: conf, exact: true }), { ms: 260, after: 120 });
        }
        await tap(p, p.getByRole("button", { name: "Save & Next" }), { ms: fast ? 240 : 550, after: fast ? 250 : 600 });
      }
      mark("submit");
      await tap(p, p.getByRole("button", { name: /^Submit$/ }).first());
      await sleep(700);
      await tap(p, p.getByRole("dialog").getByRole("button", { name: /^Submit/ }).last());
      await p.waitForURL(/\/app\/mock\/\d+/, { timeout: 30000 });
      await settle(p, 2500);
      mark("result");
      await sleep(1500);
      for (let k = 0; k < 4; k++) { await scroll(p, 560, 2000); await sleep(1500); }
      mark("explain");
      const hindi = p.getByRole("button", { name: "हिंदी" }).first();
      if (await hindi.count()) { await scrollTo(p, hindi, { offset: 300 }); await tap(p, hindi); await sleep(6000); }
      mark("end");
    });
  },

  /** The plan, built from the goal and rebuilt from progress every day. */
  async plan() {
    const p = await page({ url: "/app/plan" });
    return record(p, "plan", async () => {
      await sleep(1500);
      await scroll(p, 600, 2400); await sleep(1300);
      await scroll(p, 700, 2400); await sleep(1300);
    });
  },

  /** Last-day revision: the whole syllabus by marks, most-asked topics first, a test at the end. */
  async revise() {
    const p = await page({ url: "/app/revise" });
    return record(p, "revise", async () => {
      await sleep(1500);
      await scroll(p, 520, 2200); await sleep(1500);
      await scroll(p, 620, 2400); await sleep(1500);
    });
  },

  /** Ask a senior: Focs drafts an answer at once, labelled as AI; a verified senior checks it. */
  async senior() {
    const p = await page({ url: "/app/campus?tab=ask" });
    return record(p, "senior", async (mark) => {
      await sleep(1000);
      await type(p, p.getByPlaceholder(/What should I focus on/), "How do I stop panicking in the last 30 minutes of a JEE mock?", { delay: 30 });
      await tap(p, p.getByRole("button", { name: /^Ask$/ }));
      mark("asked");
      await sleep(9000);
      mark("answered");
      await scroll(p, 650, 2600); await sleep(2000);
    });
  },

  /** Dashboard in both looks, for the montage. */
  async dashboard() {
    const p = await page({ url: "/app" });
    return record(p, "dashboard", async () => {
      await sleep(1500);
      await scroll(p, 500, 2200); await sleep(1500);
    });
  },
});

const ROHAN = { email: "pitch.mentor.rohan@example.com", name: "Rohan Gupta" };

Object.assign(SCENES, {
  /** The return lane, both ends at once: students tap "I'm lost" on their phones, the teacher's meter moves, then the
      confusion map and a re-explanation of the board that lost the room. */
  async room() {
    const teacherToken = (await as("teacher")).access_token;
    const rooms = await api("/rooms", { token: teacherToken });
    const code = (rooms.find?.((r) => /Work and energy/.test(r.name)) || rooms[0]).code;
    const teacher = await page({ who: "teacher", url: `/app/rooms/${code}` });
    const phone = await page({ who: "student", device: PHONE, url: `/app/rooms/${code}` });
    const others = [await page({ who: "hindi", url: `/app/rooms/${code}` }), await page({ who: "classmate", url: `/app/rooms/${code}` })];
    let tapped; const lostSent = new Promise((r) => (tapped = r));
    let over; const teacherDone = new Promise((r) => (over = r));
    await Promise.all([
      record(phone, "room-phone", async (mark) => {
        await sleep(1500);
        const lost = phone.locator("button[aria-describedby=lost-help]");
        await lost.scrollIntoViewIfNeeded();
        await scroll(phone, 0, 10);
        await sleep(900);
        mark("lost");
        await tap(phone, lost, { ms: 700 });
        tapped();
        await teacherDone;
      }, { device: PHONE }),
      record(teacher, "room-teacher", async (mark) => {
        await sleep(1500);
        await lostSent;
        mark("lost1");
        for (const o of others) { await sleep(1300); await o.locator("button[aria-describedby=lost-help]").click().catch(() => {}); }
        await sleep(3500);
        mark("map");
        await tap(teacher, teacher.getByRole("link", { name: "Open the confusion map" }).first());
        await settle(teacher, 1500);
        await scroll(teacher, 260, 1600);
        await sleep(1800);
        mark("reexplain");
        await tap(teacher, teacher.getByRole("button", { name: /Re-explain/ }).first());
        await sleep(4500);
        await scroll(teacher, 520, 2200);
        await sleep(2000);
        mark("end");
        over();
      }),
    ]);
  },

  /** A student finding a mentor: verified mentors for their exam (UPSC too), master sessions with the one Pro covers. */
  async mentors() {
    const p = await page({ url: "/app/mentors" });
    return record(p, "mentors", async (mark) => {
      await sleep(900);
      await tap(p, p.getByText("Find a mentor", { exact: true }).first());
      await settle(p, 900);
      await hover(p, p.getByText(MENTOR_NAMES.aditya).first());
      await sleep(1200);
      await scroll(p, 380, 1700); await sleep(1500);
      mark("upsc");
      await p.locator("select").first().selectOption("upsc");
      await settle(p, 1600);
      await hover(p, p.getByText(MENTOR_NAMES.ananya).first());
      await sleep(1500);
      await p.locator("select").first().selectOption("jee");
      await scroll(p, -400, 1200);
      mark("sessions");
      await tap(p, p.getByText("Master sessions", { exact: true }).first());
      await settle(p, 1200);
      await hover(p, p.getByText("Included in Pro").first());
      await sleep(1200);
      const card = p.locator("div.p-4", { hasText: "Rotational motion: the 10 questions" }).first();
      await tap(p, card.getByRole("button", { name: /^Register/ }));
      await sleep(700);
      await type(p, p.getByRole("dialog").locator("textarea"), "Why is friction static in rolling without slipping?", { delay: 28 });
      await tap(p, p.getByRole("dialog").getByRole("button", { name: /^Register$/ }));
      await sleep(2200);
      mark("end");
    });
  },

  /** The mentorship itself: a week of chat, the weekly check-in carrying Focs progress, and a ₹49 call booked. */
  async chat() {
    const token = (await as("student")).access_token;
    const m = (await api("/mentors/mentorships", { token })).as_student.find((r) => r.with === MENTOR_NAMES.aditya);
    const p = await page({ url: `/app/mentors/${m.id}` });
    return record(p, "chat", async (mark) => {
      await sleep(1200);
      await scroll(p, 500, 2200); await sleep(1600);
      mark("book");
      await tap(p, p.getByRole("button", { name: "Book a call" }));
      const dlg = p.getByRole("dialog");
      await sleep(900);
      await tap(p, dlg.locator("button.tabular-nums").first());
      await type(p, dlg.locator("textarea"), "Rolling without slipping, and a plan for the next four weeks.", { delay: 26 });
      mark("pay");
      await tap(p, dlg.getByRole("button", { name: /Pay ₹\d+ and book|Book the call/ }));
      await sleep(3000);
      mark("end");
    });
  },

  /** Pro, as the student sees it in Settings. */
  async pro() {
    const p = await page({ url: "/app/settings" });
    return record(p, "pro", async () => {
      await sleep(800);
      await scrollTo(p, p.locator("#plan"), { offset: 90, ms: 1800 });
      await sleep(900);
      await hover(p, p.getByText(/A live mentor session every week/).first(), 900);
      await sleep(2200);
    });
  },

  /** Someone who cleared JEE signs up as a mentor and applies with proof. */
  async apply() {
    try {  // an earlier take of this scene
      const old = await login(ROHAN.email);
      await api("/auth/delete-account", { method: "POST", token: old.access_token, body: { password: "focs-demo-2026", confirm: "DELETE" } });
    } catch { /* not there yet */ }
    const p = await page({ who: null, url: "/mentor/signup" });
    return record(p, "apply", async (mark) => {
      await sleep(900);
      await type(p, p.getByLabel("Full name"), ROHAN.name);
      await type(p, p.getByLabel("Email"), ROHAN.email, { delay: 22 });
      await type(p, p.getByLabel("Password"), "focs-demo-2026", { delay: 22 });
      await tap(p, p.locator("input[type=checkbox]").first());
      await tap(p, p.getByRole("button", { name: /Create mentor account/ }));
      await p.waitForURL(/\/mentor/, { timeout: 20000 });
      await settle(p, 1200);
      mark("form");
      await p.locator("#ma-exam").selectOption("jee");
      await type(p, p.locator("#ma-cred"), "JEE Advanced 2024 · AIR 2,310", { delay: 24 });
      await type(p, p.locator("#ma-qual"), "B.Tech Mechanical Engineering, IIT Kanpur (2028)", { delay: 16 });
      await type(p, p.locator("#ma-inst"), "IIT Kanpur, 2nd year", { delay: 20 });
      await type(p, p.locator("#ma-head"), "Cleared JEE from a Tier-3 town. Ask me anything.", { delay: 16 });
      await p.locator("#ma-about").fill("Self-study for two years with one online batch. I can help you plan, pick a batch, and stay sane.");
      for (const t of ["Study plan and timetable", "Stress and motivation"]) await tap(p, p.getByRole("button", { name: t }).first()).catch(() => {});
      await p.locator("#ma-phone").fill("+91 98100 22310");
      await p.locator("input[type=file]").setInputFiles(path.join(ROOT, "shoot", "assets", "proof-rohan.png"));
      await hover(p, p.getByText("proof-rohan.png").first());
      await sleep(900);
      await tap(p, p.locator("input[type=checkbox]").last());
      mark("send");
      await tap(p, p.getByRole("button", { name: /^Send for review/ }));
      await settle(p, 2500);
      mark("end");
    });
  },

  /** The Focs admin: the business at a glance, then the mentor queue: open the proof, approve. */
  async admin() {
    const p = await page({ who: null, url: "/admin/login" });
    return record(p, "admin", async (mark) => {
      await sleep(800);
      await type(p, p.getByLabel("Admin ID"), process.env.ADMIN_ID || "admin@focs", { delay: 30 });
      await type(p, p.getByLabel("Password"), process.env.ADMIN_PASSWORD || "focs-demo-admin-2026", { delay: 18 });
      await p.keyboard.press("Enter");
      await p.waitForURL(/\/admin$/, { timeout: 20000 });
      await settle(p, 2000);
      mark("dashboard");
      await scroll(p, 700, 2600); await sleep(1500);
      await scroll(p, 700, 2600); await sleep(1500);
      const row = p.locator("div", { hasText: ROHAN.name }).filter({ has: p.getByRole("button", { name: "Approve" }) }).last();
      await scrollTo(p, row, { offset: 260, ms: 1800 });
      await sleep(1200);
      mark("proof");
      await hover(p, row.getByRole("button", { name: "Proof" }), 700);
      await sleep(1600);
      mark("approve");
      await tap(p, row.getByRole("button", { name: "Approve" }));
      await sleep(2600);
      mark("end");
    });
  },

  /** A mentor's own dashboard: overview, seekers, calls, master sessions, earnings. */
  async mentorside() {
    const p = await page({ who: "pitch.mentor.aditya@example.com", url: "/mentor" });
    return record(p, "mentorside", async (mark) => {
      await sleep(1800);
      for (const [label, wait] of [["Seekers", 2400], ["Calls", 2400], ["Master sessions", 2400], ["Earnings", 2600]]) {
        mark(label.toLowerCase());
        await tap(p, p.getByRole("link", { name: label }).first());
        await settle(p, wait);
      }
      mark("end");
    });
  },
});

const MENTOR_NAMES = { aditya: "Aditya Verma", sneha: "Sneha Iyer", ananya: "Ananya Rao" };

async function main() {
  const names = process.argv.slice(2);
  browser = await launch();
  try {
    for (const name of names.length ? names : Object.keys(SCENES)) {
      console.log(`scene ${name}`);
      await SCENES[name]();
    }
  } finally {
    await browser.close();
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
