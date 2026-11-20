// The people in the video, on top of backend/scripts/seed_demo.py: names for the demo students, a study goal, a few
// ticked topics, three approved mentors (JEE ×2, UPSC) with hours and master sessions, a mentorship with a week of
// messages and a check-in, and one application (NEET) waiting in the admin queue. All through the real API.
//
//   node shoot/seed.mjs            (filming server on FOCS_URL, default http://127.0.0.1:8017)
//
// Everyone here is a sample person: the proof images say so, and the video carries a "sample accounts" label.
import fs from "node:fs";
import path from "node:path";
import { api, login, ROOT, PASSWORD } from "./lib.mjs";

const ASSETS = path.join(ROOT, "shoot", "assets");
const ADMIN = { username: process.env.ADMIN_ID || "admin@focs", password: process.env.ADMIN_PASSWORD || "focs-demo-admin-2026" };
export const STUDENTS = {
  student: { full_name: "Riya Sharma", language: "en" },
  hindi: { full_name: "Aman Yadav", language: "hi" },
  teacher: { full_name: "Neha Kapoor" },
  senior: { full_name: "Arjun Mehta" },
  classmate: { full_name: "Kabir Singh" },
};
export const MENTORS = {
  aditya: { name: "Aditya Verma", exam: "jee", credential: "JEE Advanced 2023 · AIR 1,147", institution: "IIT Delhi, 3rd year",
    qualification: "B.Tech Electrical Engineering, IIT Delhi (2027)", price: 49, capacity: 10,
    experience: "Ran Sunday physics doubt sessions for 40+ juniors from my coaching batch.",
    headline: "Physics was my weakest subject. Now I teach it.", topics: "plan,mocks,subjects,mindset", languages: "en,hi",
    about: "I went from 38 to 82 in JEE Main physics in eight months by fixing how I practised, not how much. I'll help you build a weekly plan, read your mocks honestly and fix the chapters that leak marks." },
  sneha: { name: "Sneha Iyer", exam: "jee", credential: "JEE Advanced 2022 · AIR 612", institution: "IIT Bombay, final year",
    qualification: "B.Tech Computer Science, IIT Bombay (2026)", price: 99, capacity: 8,
    experience: "Mock-analysis mentor at a Mumbai coaching centre for two seasons.",
    headline: "Mock analysis that moves your rank, not your mood.", topics: "mocks,revision,choices", languages: "en",
    about: "Most marks are lost in the last 40 minutes of a mock. I'll show you where yours go, and how to choose a branch and college once the rank is in." },
  ananya: { name: "Ananya Rao", exam: "upsc", credential: "UPSC CSE 2024 · Interview stage", institution: "New Delhi · preparing for CSE 2026",
    qualification: "B.A. (Hons) Political Science, University of Delhi", price: 199, capacity: 6,
    experience: "Evaluated 500+ mains answers for a study group.",
    headline: "Answer writing, one page at a time.", topics: "writing,plan,interview", languages: "en,hi",
    about: "Mains is won on structure. Send me one answer a day and I'll mark it like an examiner." },
};
const PENDING = { meera: { name: "Meera Nair", exam: "neet", credential: "NEET UG 2024 · AIR 3,402", institution: "MAMC New Delhi, 2nd year",
  qualification: "MBBS, Maulana Azad Medical College (2029)", price: 49, capacity: 5, experience: "", headline: "Biology in stories, not lists.",
  topics: "plan,subjects,mindset", languages: "en,hi", about: "NCERT line by line, and a plan that leaves time for sleep." } };

const email = (k) => `demo.focs.${k}@example.com`;
const mentorEmail = (k) => `pitch.mentor.${k}@example.com`;
const bearer = (a) => a.access_token;

/** A day `days` from today at hh:mm India time, as UTC ISO. */
export function istAt(days, hh, mm = 0) {
  const now = new Date(Date.now() + 5.5 * 3600e3);
  const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + days, hh, mm) - 5.5 * 3600e3);
  return d.toISOString();
}

async function mentorAccount(key, m, admin) {
  let auth;
  try {
    auth = await api("/auth/register", { method: "POST", body: { email: mentorEmail(key), full_name: m.name, password: PASSWORD, role: "mentor", accepted_terms: true } });
  } catch {
    auth = await login(mentorEmail(key));
  }
  const token = bearer(auth);
  const ws = await api("/mentors/me", { token });
  if (!ws.profile || ws.profile.status !== "approved") {
    const form = new FormData();
    for (const [k, v] of Object.entries({ exam: m.exam, credential: m.credential, institution: m.institution, qualification: m.qualification,
      experience: m.experience, phone: "+91 90000 0" + String(10000 + Object.keys(MENTORS).indexOf(key)).slice(1), call_price_inr: m.price,
      headline: m.headline, about: m.about, topics: m.topics, languages: m.languages, capacity: m.capacity })) form.append(k, String(v));
    form.append("proof", new Blob([fs.readFileSync(path.join(ASSETS, `proof-${key}.png`))], { type: "image/png" }), `rank-card-${key}.png`);
    const p = await api("/mentors/apply", { method: "POST", token, form });
    if (admin) await api(`/admin/mentors/${p.id}/review`, { method: "POST", token: admin, body: { approve: true, note: "Rank card checked." } });
  }
  return { token, auth };
}

async function main() {
  const admin = (await api("/admin/login", { method: "POST", body: ADMIN })).token;

  console.log("Students:");
  const s = {};
  for (const [k, spec] of Object.entries(STUDENTS)) {
    s[k] = bearer(await login(email(k)));
    await api("/auth/me", { method: "PATCH", token: s[k], body: spec });
    console.log(`  ${spec.full_name} <${email(k)}>`);
  }

  // Riya's goal: JEE Main, Class 12, AIR under 10,000 (the plan, today's list and the dashboard come from it)
  const goal = await api("/prep/goal", { token: s.student }).catch(() => null);
  if (!goal) {
    await api("/prep/goal?tz=-330", { method: "PUT", token: s.student, body: {
      track: "jee_main", class_level: "12", exam_date: "2027-04-04", target: "air_10k", dream: "IIT Delhi",
      weekday_hours: 6, weekend_hours: 9, coaching: "online", apply_standing: true,
      standing: { Physics: { "11": "partial", "12": "none" }, Chemistry: { "11": "partial", "12": "none" }, Mathematics: { "11": "done", "12": "partial" } } } });
    console.log("  Riya's plan: JEE Main 2027, AIR under 10,000");
  }
  for (const t of ["physics.laws-of-motion", "physics.work-energy-and-power"]) {
    const tree = await api(`/prep/syllabus?tz=-330`, { token: s.student });
    const ch = tree.subjects.flatMap((x) => x.units.flatMap((u) => u.chapters)).find((c) => c.id === t);
    for (const topic of (ch?.topics || []).slice(0, 3)) await api(`/prep/topics/${encodeURIComponent(topic.id)}?tz=-330`, { method: "PUT", token: s.student, body: { done: true } }).catch(() => {});
  }

  console.log("Mentors:");
  const m = {};
  for (const [k, spec] of Object.entries(MENTORS)) {
    m[k] = (await mentorAccount(k, spec, admin)).token;
    await api("/mentors/me/slots", { method: "PUT", token: m[k], body: { slots: [0, 1, 2, 3, 4, 5, 6].flatMap((day) => [{ day, time: "19:00" }, { day, time: "20:00" }, ...(day >= 5 ? [{ day, time: "11:00" }] : [])]) } });
    console.log(`  ${spec.name}: approved, hours set`);
  }
  for (const [k, spec] of Object.entries(PENDING)) {
    await mentorAccount(k, spec, null);
    console.log(`  ${spec.name}: application waiting for the admin`);
  }

  console.log("Master sessions:");
  const have = await api("/mentors/me/sessions", { token: m.aditya });
  if (!(have.sessions || []).length) {
    await api("/mentors/me/sessions", { method: "POST", token: m.aditya, body: { starts_at: istAt(2, 19), topic: "Rotational motion: the 10 questions that decide your rank",
      description: "Torque, rolling and angular momentum through ten past-paper questions. Bring the one that beat you.", minutes: 60, seats: 25, price_inr: 99 } });
    await api("/mentors/me/sessions", { method: "POST", token: m.sneha, body: { starts_at: istAt(3, 18), topic: "Mock analysis live: where the last 40 minutes go",
      description: "Bring your last full mock. We find the three habits costing you marks.", minutes: 60, seats: 40, price_inr: 149 } });
    await api("/mentors/me/sessions", { method: "POST", token: m.sneha, body: { starts_at: istAt(5, 11), topic: "Open doubts: JEE Physics and Maths",
      description: "Free for everyone. Post your doubt when you register.", minutes: 45, seats: 60, price_inr: 0 } });
    console.log("  3 sessions (₹99, ₹149, free)");
  }

  console.log("A mentorship (Riya and Aditya):");
  const dir = await api("/mentors?exam=jee", { token: s.student });
  const aditya = dir.mentors.find((x) => x.name === MENTORS.aditya.name);
  const mine = await api("/mentors/mentorships", { token: s.student });
  if (!mine.as_student.length) {
    const row = await api(`/mentors/${aditya.id}/request`, { method: "POST", token: s.student, body: {
      goal: "I score around 40/100 in Physics mocks and panic on rotational motion. I want 70+ before the January attempt.", share_progress: true } });
    await api(`/mentors/mentorships/${row.id}/accept`, { method: "POST", token: m.aditya });
    const say = (token, body, checkin = false) => api(`/mentors/mentorships/${row.id}/messages`, { method: "POST", token, body: { body, checkin } });
    await say(m.aditya, "Hi Riya! I looked at your progress: Laws of Motion is solid, rotational motion is where the marks leak. Let's fix that first.");
    await say(s.student, "Yes! Torque questions take me 6-7 minutes each and I still get them wrong.");
    await say(m.aditya, "Do 10 torque questions a day, 3 minutes each, timed. Send me your accuracy in Sunday's check-in.");
    await say(s.student, "Week 1: 60 torque questions done. Accuracy went from 55% to 68%. Rolling motion still confuses me.", true);
    await say(m.aditya, "That's a big jump. Book a call this week and we'll do rolling without slipping together.");
    console.log("  5 messages, one weekly check-in");
  }

  // Kabir has a mentorship and a paid call with Aditya, and a seat in his master session, so the mentor's side has students
  const kab = await api("/mentors/mentorships", { token: s.classmate });
  if (!kab.as_student.length) {
    const row = await api(`/mentors/${aditya.id}/request`, { method: "POST", token: s.classmate, body: {
      goal: "Dropper, scored 92 percentile last year. Need a plan that fits coaching plus self-study.", share_progress: true } });
    await api(`/mentors/mentorships/${row.id}/accept`, { method: "POST", token: m.aditya });
    const booked = await api(`/mentors/mentorships/${row.id}/calls`, { method: "POST", token: s.classmate, body: { starts_at: istAt(1, 20), agenda: "Weekly plan with coaching tests on Sundays" } });
    if (booked.checkout) await api(`/billing/payments/${booked.checkout.payment_id}/confirm`, { method: "POST", token: s.classmate, body: {} });
    const sessions = await api("/mentors/sessions", { token: s.classmate });
    const rot = sessions.sessions.find((x) => x.topic.startsWith("Rotational"));
    const seat = await api(`/mentors/sessions/${rot.id}/seat`, { method: "POST", token: s.classmate, body: { doubt: "Why is friction static in rolling without slipping?" } });
    if (seat.checkout) await api(`/billing/payments/${seat.checkout.payment_id}/confirm`, { method: "POST", token: s.classmate, body: {} });
    console.log("  Kabir: a paid call tomorrow and a seat in Aditya's session");
  }
  console.log("Done.");
}

main().catch((e) => { console.error(e); process.exit(1); });
