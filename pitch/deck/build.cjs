// The Shark Tank deck: open (problem → vision → how it works), the demo film, close (tech, execution, business, ask).
//   node deck/build.cjs            -> out/Focs-Pitch.pptx (embeds out/Focs-Demo.mp4 when it exists)
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const IMG = (f) => path.join(__dirname, "img", f);
const OUT = process.env.PITCH_OUT || path.join(ROOT, "out", "Focs-Pitch.pptx");
const VIDEO = process.env.PITCH_VIDEO || path.join(ROOT, "out", "Focs-Demo-v2.mp4");
const THEME_JS = process.env.PPTX_APPLY_THEME;  // the pptx skill's scripts/apply_theme.js, when available

const THEME = {
  name: "Focs Ink", headFontFace: "Segoe UI Semibold", bodyFontFace: "Segoe UI",
  colors: { dk1: "0A0A0B", lt1: "F3F1EC", dk2: "141416", lt2: "8D8B86", accent1: "C8FF2E", accent2: "F3F1EC", accent3: "8D8B86",
            accent4: "3A3A3E", accent5: "FF4D3D", accent6: "5B5B60", hlink: "C8FF2E", folHlink: "8D8B86" },
};
const COL = { bg: "0A0A0B", fg: "F3F1EC", muted: "8D8B86", accent: "C8FF2E", panel: "141416", line: "2B2B2F", ink: "0A0A0B" };
const MONO = "Consolas", SERIF = "Georgia";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";  // 13.333 × 7.5 in
pres.title = "Focs — Shark Tank pitch";
pres.author = "Team Focs";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const W = 13.333, H = 7.5, M = 0.6;

pres.defineSlideMaster({
  title: "FOCS_DARK", background: { color: COL.bg },
  objects: [
    { image: { path: IMG("logo-light.png"), x: M, y: 6.93, w: 0.26, h: 0.26 } },
    { text: { text: "FOCS", options: { x: M + 0.32, y: 6.9, w: 1.2, h: 0.32, fontFace: THEME.headFontFace, fontSize: 11, color: COL.fg, charSpacing: 6, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: 6.9, w: 0.6, h: 0.32, fontFace: MONO, fontSize: 10, color: COL.muted, align: "right" },
  placeholders: [],
});
pres.defineSlideMaster({
  title: "FOCS_CONTENT", background: { color: COL.bg },
  objects: [
    { image: { path: IMG("logo-light.png"), x: M, y: 6.93, w: 0.26, h: 0.26 } },
    { text: { text: "FOCS", options: { x: M + 0.32, y: 6.9, w: 1.2, h: 0.32, fontFace: THEME.headFontFace, fontSize: 11, color: COL.fg, charSpacing: 6, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: 6.9, w: 0.6, h: 0.32, fontFace: MONO, fontSize: 10, color: COL.muted, align: "right" },
  placeholders: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.95, w: W - 2 * M, h: 1.0, fontFace: THEME.headFontFace, fontSize: 36, color: COL.fg, valign: "top", margin: 0 },
      text: "Title" } },
  ],
});

/* ---------------------------------------------------------------- pieces */
const eyebrow = (s, text, y = 0.55, color = COL.accent) =>
  s.addText(`— ${text.toUpperCase()}`, { x: M, y, w: 9, h: 0.3, fontFace: MONO, fontSize: 12, color, charSpacing: 3, margin: 0, isTextBox: true });

/** Title with an italic serif accent part: [plain, accent] */
const TITLE = { x: M, y: 0.95, w: W - 2 * M, h: 1.0, fontFace: THEME.headFontFace, fontSize: 36, color: COL.fg, valign: "top", margin: 0, isTextBox: true };
const title = (s, plain, accent) => s.addText([
  { text: plain, options: {} },
  ...(accent ? [{ text: accent, options: { fontFace: SERIF, italic: true, color: COL.accent } }] : []),
], { ...TITLE });

/** The bridge motif: teacher on the left, student on the right. */
function bridge(s, y, { x = M, w = W - 2 * M, back = false, labels = true } = {}) {
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: COL.fg, width: 1.25, transparency: 40 } });
  s.addShape(pres.shapes.RECTANGLE, { x: x - 0.06, y: y - 0.06, w: 0.12, h: 0.12, fill: { color: COL.fg }, line: { color: COL.fg } });
  s.addShape(pres.shapes.RECTANGLE, { x: x + w - 0.06, y: y - 0.06, w: 0.12, h: 0.12, fill: { color: COL.fg }, line: { color: COL.fg } });
  [0.22, 0.47, 0.71].forEach((k, i) => s.addShape(pres.shapes.OVAL, { x: x + w * k - 0.05, y: y - 0.05, w: 0.1, h: 0.1,
    fill: { color: back && i === 1 ? COL.accent : i === 2 ? COL.accent : COL.fg }, line: { type: "none" } }));
  if (labels) {
    s.addText("TEACHER", { x, y: y + 0.12, w: 2, h: 0.25, fontFace: MONO, fontSize: 9, color: COL.muted, charSpacing: 4, margin: 0, isTextBox: true });
    s.addText("STUDENT", { x: x + w - 2, y: y + 0.12, w: 2, h: 0.25, fontFace: MONO, fontSize: 9, color: COL.muted, charSpacing: 4, margin: 0, align: "right", isTextBox: true });
  }
}

function card(s, x, y, w, h, { head, body, num, hot = false, size = 14 }) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: COL.panel }, line: { color: hot ? COL.accent : COL.line, width: 1 } });
  let ty = y + 0.22;
  if (num) { s.addText(num, { x: x + 0.25, y: ty, w: w - 0.5, h: 0.3, fontFace: MONO, fontSize: 11, color: hot ? COL.accent : COL.muted, margin: 0, isTextBox: true }); ty += 0.38; }
  if (head) { s.addText(head, { x: x + 0.25, y: ty, w: w - 0.5, h: 0.45, fontFace: THEME.headFontFace, fontSize: 19, color: COL.fg, margin: 0, isTextBox: true }); ty += 0.5; }
  if (body) s.addText(body, { x: x + 0.25, y: ty, w: w - 0.5, h: y + h - ty - 0.15, fontSize: size, color: COL.muted, valign: "top", margin: 0, isTextBox: true,
    paraSpaceAfter: 4 });
}

function stat(s, x, y, w, num, label, hot = false) {
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: hot ? COL.accent : COL.fg, width: 1.5 } });
  s.addText(num, { x, y: y + 0.12, w, h: 0.85, fontFace: THEME.headFontFace, fontSize: 44, color: hot ? COL.accent : COL.fg, margin: 0, isTextBox: true });
  s.addText(label, { x, y: y + 0.98, w, h: 0.6, fontSize: 12, color: COL.muted, valign: "top", margin: 0, isTextBox: true });
}

function shot(s, img, x, y, w) {
  const h = w * (1350 / 2160);
  s.addShape(pres.shapes.RECTANGLE, { x: x - 0.02, y: y - 0.26, w: w + 0.04, h: h + 0.28, fill: { color: "18181B" }, line: { color: COL.line, width: 0.75 } });
  ["FF5F57", "FEBC2E", "28C840"].forEach((c, i) => s.addShape(pres.shapes.OVAL, { x: x + 0.12 + i * 0.16, y: y - 0.18, w: 0.1, h: 0.1, fill: { color: c }, line: { type: "none" } }));
  s.addImage({ path: IMG(img), x, y, w, h });
}

const bullets = (items, opts = {}) => items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: i < items.length - 1, ...opts } }));

/* ---------------------------------------------------------------- PART 1 · the opening */
pres.addSection({ title: "Opening" });

// 1 · title
{
  const s = pres.addSlide({ masterName: "FOCS_DARK", sectionTitle: "Opening" });
  s.addImage({ path: IMG("logo-light.png"), x: M, y: 1.35, w: 1.1, h: 1.1 });
  s.addText("FOCS", { x: M + 1.35, y: 1.25, w: 7, h: 1.3, fontFace: THEME.headFontFace, fontSize: 88, color: COL.fg, charSpacing: 20, margin: 0, isTextBox: true });
  s.addText([{ text: "Every lecture, " }, { text: "understood.", options: { fontFace: SERIF, italic: true, color: COL.accent } }],
    { x: M, y: 2.85, w: 11, h: 0.9, fontFace: THEME.headFontFace, fontSize: 40, color: COL.fg, margin: 0, isTextBox: true });
  s.addText("Focs carries the lecture to the student, and the confusion back to the teacher.",
    { x: M, y: 3.75, w: 11, h: 0.5, fontSize: 18, color: COL.muted, margin: 0, isTextBox: true });
  bridge(s, 5.2);
  s.addText("github.com/Mukul07777/Break_The_Gap_Focs", { x: M, y: 5.75, w: 9, h: 0.3, fontFace: MONO, fontSize: 13, color: COL.accent, margin: 0, isTextBox: true });
  s.addText("GDG NSUT DEVLYMPICS 2026  ·  BRIDGE THE GAP  ·  TEAM FOCS", { x: M, y: 6.2, w: 9, h: 0.3, fontFace: MONO, fontSize: 11, color: COL.muted, charSpacing: 3, margin: 0, isTextBox: true });
  s.addNotes("Hello Sharks. We're Team Focs. [Say names.] In one line: Focs carries the lecture to the student, and the confusion back to the teacher. Give us 60 seconds on the problem, then we'll show you the product running live.");
}

// 2 · the problem
{
  const s = pres.addSlide({ masterName: "FOCS_CONTENT", sectionTitle: "Opening" });
  eyebrow(s, "The problem");
  title(s, "1 teacher. 1 board. 200 students. ", "0 questions asked.");
  card(s, M, 2.35, 3.85, 2.45, { num: "SPEED", head: "The board moves on", body: "The lecture runs at the teacher's speed. Copy the board or listen: you can't do both." });
  card(s, M + 4.07, 2.35, 3.85, 2.45, { num: "LANGUAGE", head: "Taught in one language", body: "Lakhs of aspirants think in Hindi or Hinglish, but notes and doubt solvers answer in English." });
  card(s, M + 8.14, 2.35, 3.86, 2.45, { num: "RETURN", head: "Silence travels back", body: "The student who is lost doesn't raise a hand. The teacher never learns which board lost the room.", hot: true });
  stat(s, M, 5.15, 3.6, "14 lakh+", "JEE Main candidates a year");
  stat(s, M + 4.07, 5.15, 3.6, "23 lakh+", "NEET UG candidates a year");
  stat(s, M + 8.14, 5.15, 3.6, "13 lakh", "UPSC CSE applicants a year", true);
  s.addNotes("Every coaching hall and online batch looks like this: one teacher, one board, hundreds of students, and nobody asks. Three gaps: speed, language and the return. The student who's lost stays quiet, and the teacher never finds out. And this is at scale: about 14 lakh JEE Main candidates, 23 lakh NEET, 13 lakh UPSC applicants every year (NTA and UPSC 2024 figures, rounded). Most of them learn from lectures.");
}

// 3 · the gap → the bridge
{
  const s = pres.addSlide({ masterName: "FOCS_CONTENT", sectionTitle: "Opening" });
  eyebrow(s, "The gap");
  title(s, "Two sides that ", "never meet.");
  const col = (x, head, rows, hot) => {
    s.addText(head, { x, y: 2.3, w: 4.6, h: 0.4, fontFace: MONO, fontSize: 13, color: hot ? COL.accent : COL.fg, charSpacing: 4, margin: 0, isTextBox: true });
    s.addText(bullets(rows), { x, y: 2.8, w: 4.6, h: 1.9, fontSize: 17, color: COL.fg, valign: "top", margin: 0, paraSpaceAfter: 10, isTextBox: true });
  };
  col(M, "THE TEACHER", ["Board and voice, at their speed", "In their language", "Can't see who is lost, or where"]);
  col(W - M - 4.6, "THE STUDENT", ["Needs their own pace", "Needs their own language", "Won't say they're lost"], true);
  s.addText("FOCS", { x: W / 2 - 1, y: 3.2, w: 2, h: 0.5, fontFace: THEME.headFontFace, fontSize: 22, color: COL.accent, charSpacing: 10, align: "center", margin: 0, isTextBox: true });
  bridge(s, 5.45, { back: true });
  s.addText("Four lanes across the gap:  01 Speed  ·  02 Language  ·  03 Understanding  ·  04 Return",
    { x: M, y: 6.0, w: W - 2 * M, h: 0.35, fontFace: MONO, fontSize: 12, color: COL.muted, margin: 0, isTextBox: true });
  s.addNotes("On one side the teacher: their speed, their language, and no way to see who's lost. On the other the student, who needs their own pace and language and won't say they're lost. Focs sits in between, with four lanes: three carry the lecture to the student and one carries the confusion back.");
}

// 4 · vision + the product
{
  const s = pres.addSlide({ masterName: "FOCS_CONTENT", sectionTitle: "Opening" });
  eyebrow(s, "Vision");
  title(s, "Any lecture in India, ", "understood in your own language.");
  const lanes = [
    ["01 →", "Speed", "The board, read by our own OCR model, and the teacher's voice become live notes and captions."],
    ["02 →", "Language", "Notes, quizzes and doubts in English, Hinglish or हिंदी. Every formula checked unchanged."],
    ["03 →", "Understanding", "Every answer locked in as Sure or Guessing. Blind spots (sure and wrong) come first."],
    ["04 ←", "Return", "Anonymous \"I'm lost\" taps reach the teacher live, pinned to the exact board."],
  ];
  lanes.forEach(([n, h, b], i) => card(s, M + i * 3.07, 2.45, 2.88, 3.1, { num: n, head: h, body: b, hot: i === 3, size: 13 }));
  s.addText([{ text: "Works on top of any lecture ", options: { color: COL.fg } }, { text: "(YouTube, Physics Wallah, Unacademy, Zoom, or a real classroom through a phone on the desk). We don't replace teachers; we make every one of them reach the last bench.", options: { color: COL.muted } }],
    { x: M, y: 5.85, w: W - 2 * M, h: 0.7, fontSize: 15, margin: 0, isTextBox: true });
  s.addNotes("Our vision: any lecture in India, understood in the student's own language. Focs isn't another content app. It runs on top of the lecture the student already watches. Four lanes. Speed: the board and voice become notes and captions. Language: Hindi and Hinglish, formulas intact. Understanding: every answer is locked in as Sure or Guessing, so we find blind spots. And Return: the confusion goes back to the teacher, live.");
}

// 5 · how it works (technical depth up front)
{
  const s = pres.addSlide({ masterName: "FOCS_CONTENT", sectionTitle: "Opening" });
  eyebrow(s, "How it works");
  title(s, "Not a ChatGPT wrapper. ", "Our own model in the loop.");
  const steps = [
    ["1 · CAPTURE", "Shares one browser tab, crops to the board. A 48×27 change detector on the device sends a frame only when the writing changes."],
    ["2 · READ", "DBNet finds the lines; FocsOCR (our CNN + BiLSTM + CTC, 3.1 M params) and PP-OCRv4 both read them; the better reading wins."],
    ["3 · WRITE", "An AI router (Groq gpt-oss → Gemini) writes notes, quizzes and captions (Whisper), with a cost ledger and an offline fallback."],
    ["4 · RETURN", "Live rooms on WebSockets carry \"I'm lost\", wrong answers and doubts to the teacher, pinned to the board on screen."],
  ];
  steps.forEach(([h, b], i) => {
    const x = M + i * 3.07;
    s.addText(h, { x, y: 2.4, w: 2.88, h: 0.32, fontFace: MONO, fontSize: 12, color: i === 1 ? COL.accent : COL.fg, charSpacing: 2, margin: 0, isTextBox: true });
    s.addShape(pres.shapes.LINE, { x, y: 2.8, w: 2.75, h: 0, line: { color: i === 1 ? COL.accent : COL.fg, width: 1.5, endArrowType: i < 3 ? "triangle" : undefined } });
    s.addText(b, { x, y: 2.95, w: 2.8, h: 1.9, fontSize: 13.5, color: COL.muted, valign: "top", margin: 0, isTextBox: true });
  });
  stat(s, M, 5.0, 2.8, "0.48%", "FocsOCR character error on held-out frames, vs 7.27% for PP-OCRv4 (synthetic set)", true);
  stat(s, M + 3.07, 5.0, 2.8, "1.76 M", "synthetic board lines it trained on: 61 fonts, Greek, sub/superscripts");
  stat(s, M + 6.14, 5.0, 2.8, "₹0", "for an idle board: nothing is sent while the teacher only talks");
  stat(s, M + 9.21, 5.0, 2.8, "23 → 0", "AI calls for a 4-board lecture: 8 for the first student, 0 for the next");
  s.addNotes("Technical depth, before the demo. Four steps. Capture: one tab, cropped to the board, and an on-device change detector so idle boards cost nothing. Read: our own OCR model, FocsOCR, trained on 1.76 million synthetic board lines on a laptop GPU, in an ensemble with PP-OCRv4. On held-out frames it gets 0.48% character error against 7.27% (those frames are synthetic; a real-board benchmark is being collected). Write: an AI router with a cost ledger and an offline fallback. And Return: live rooms on WebSockets. Notes are shared, so a popular lecture costs 8 AI calls for the first student and zero for the next.");
}

// 6 · the film
{
  const s = pres.addSlide({ masterName: "FOCS_DARK", sectionTitle: "Opening" });
  if (fs.existsSync(VIDEO)) {
    s.addMedia({ type: "video", path: VIDEO, x: 0, y: 0, w: W, h: H, cover: "data:image/png;base64," + fs.readFileSync(IMG("poster.png")).toString("base64") });
  } else {
    s.addImage({ path: IMG("poster.png"), x: 0, y: 0, w: W, h: H });
    s.addText("▶  DEMO FILM · 3:48 · THE REAL APP, END TO END", { x: M, y: 0.45, w: 8, h: 0.35, fontFace: MONO, fontSize: 13, color: COL.accent, charSpacing: 3, margin: 0, isTextBox: true });
  }
  s.addNotes("DEMO FILM (3:48, silent: talk over it). Click the video to play. 0:00 the problem; 0:18 title; 0:25 lane 1, live lecture: share a tab, crop, notes in seconds, captions, a pop quiz locked as Sure; 1:12 Hindi; 1:22 tests: warm-up while the paper is written, NTA screen, gap map; 1:53 lane 4: I'm lost from a phone reaches the teacher, confusion map, re-explain; 2:25 mentors, chat with weekly check-in, a ₹49 call, Pro; 2:56 a mentor applies with proof, the admin approves, the mentor dashboard; 3:24 under the hood.");
}

/* ---------------------------------------------------------------- PART 2 · the close */
pres.addSection({ title: "Close" });

// 7 · under the hood
{
  const s = pres.addSlide({ masterName: "FOCS_CONTENT", sectionTitle: "Close" });
  eyebrow(s, "Execution");
  title(s, "Built and running, ", "not a mock-up.");
  stat(s, M, 2.3, 2.8, "37k", "lines of code: 17.5k Python, 19.4k TypeScript", true);
  stat(s, M + 3.07, 2.3, 2.8, "221", "automated tests · CI on every push · Docker build");
  stat(s, M + 6.14, 2.3, 2.8, "193", "API endpoints behind 45 screens");
  stat(s, M + 9.21, 2.3, 2.8, "2", "apps: the web app and an Android app (Capacitor)");
  const rows = [
    ["Stack", "React 19 + Vite · FastAPI (Python 3.12) · Postgres on Supabase · WebSockets · Docker, Cloud Run ready"],
    ["AI", "FocsOCR (ours, ONNX on CPU) · Groq gpt-oss-120b/20b → Gemini fallback · Whisper · every call metered per student"],
    ["Quality", "AI questions kept only when a 2nd model solves them the same way · formulas checked after translation"],
    ["Trust", "WCAG 2.1 AA checked in CI · DPDP: export or delete everything · masked contacts, verified mentors"],
  ];
  rows.forEach(([k, v], i) => {
    const y = 4.35 + i * 0.55;
    s.addShape(pres.shapes.LINE, { x: M, y, w: W - 2 * M, h: 0, line: { color: COL.line, width: 0.75 } });
    s.addText(k.toUpperCase(), { x: M, y: y + 0.1, w: 1.6, h: 0.35, fontFace: MONO, fontSize: 11, color: COL.accent, charSpacing: 2, margin: 0, isTextBox: true });
    s.addText(v, { x: M + 1.7, y: y + 0.08, w: W - 2 * M - 1.7, h: 0.4, fontSize: 14, color: COL.fg, margin: 0, isTextBox: true });
  });
  s.addNotes("What you just saw is the real app on a live server, not a prototype. 37 thousand lines of code, 221 automated tests running in CI, 193 endpoints, 45 screens and an Android app. Every AI call is metered per student, and every AI-written question is checked by a second model before a student sees it.");
}

// 8 · business model
{
  const s = pres.addSlide({ masterName: "FOCS_CONTENT", sectionTitle: "Close" });
  eyebrow(s, "Business model");
  title(s, "Free to start. ", "Pro at ₹149 a month.");
  card(s, M, 2.3, 3.0, 3.95, { num: "STARTER · ₹0", head: "Try it on any lecture", size: 13,
    body: "Live board capture and AI notes · FocsOCR · 1 full mock a week · mentor chat free · 1:1 calls ₹49 · study rooms for 5" });
  // Pro, the hero card
  const px = M + 3.2, pw = 5.0;
  s.addShape(pres.shapes.RECTANGLE, { x: px, y: 2.3, w: pw, h: 3.95, fill: { color: COL.fg }, line: { color: COL.fg } });
  s.addText("PRO", { x: px + 0.3, y: 2.48, w: 2, h: 0.3, fontFace: MONO, fontSize: 12, color: COL.ink, charSpacing: 4, margin: 0, isTextBox: true });
  s.addText([{ text: "₹149", options: { fontSize: 40 } }, { text: " / month", options: { fontSize: 16 } }],
    { x: px + 0.3, y: 2.75, w: 4, h: 0.7, fontFace: THEME.headFontFace, color: COL.ink, margin: 0, isTextBox: true });
  s.addShape(pres.shapes.RECTANGLE, { x: px + 0.3, y: 3.55, w: pw - 0.6, h: 0.5, fill: { color: COL.accent }, line: { type: "none" } });
  s.addText("✓  A live mentor session every week, included", { x: px + 0.42, y: 3.55, w: pw - 0.8, h: 0.5, fontFace: THEME.headFontFace, fontSize: 15, color: COL.ink, margin: 0, valign: "middle", isTextBox: true });
  s.addText(bullets(["10× the AI allowance of Starter", "Up to 2 full mock tests a day, with analysis", "AI practice sets and subjective answer grading", "Doubt solver with Socratic mode · rooms up to 50"], { color: COL.ink }),
    { x: px + 0.3, y: 4.2, w: pw - 0.6, h: 1.9, fontSize: 13.5, valign: "top", margin: 0, paraSpaceAfter: 6, isTextBox: true });
  card(s, px + pw + 0.2, 2.3, W - M - (px + pw + 0.2), 1.9, { num: "MENTOR MARKETPLACE", head: "We keep 20%", size: 13,
    body: "1:1 calls at the mentor's price (₹49 to start) · paid master sessions per seat", hot: true });
  card(s, px + pw + 0.2, 4.35, W - M - (px + pw + 0.2), 1.9, { num: "INSTITUTE · CUSTOM", head: "Coaching and colleges", size: 13,
    body: "Teachers' confusion maps and batch analytics · custom exam patterns · SSO" });
  s.addText("Payments live in the product through Razorpay: UPI, cards, netbanking. Pro runs 30 days at a time, no auto-renewal.",
    { x: M, y: 6.4, w: W - 2 * M, h: 0.35, fontSize: 12, color: COL.muted, margin: 0, isTextBox: true });
  s.addNotes("Starter is free, so every student can try it on tonight's lecture. Pro is ₹149 a month, less than one coaching test series, and it includes a live session with a mentor every week, 10 times the AI allowance, two full mocks a day, answer grading and the Socratic doubt solver. The mentor marketplace earns 20% of every 1:1 call and paid master-session seat. Institutes pay for the teacher side: confusion maps and batch analytics. Razorpay is integrated: UPI, cards, netbanking.");
}

// 9 · mentors: the supply side and trust
{
  const s = pres.addSlide({ masterName: "FOCS_CONTENT", sectionTitle: "Close" });
  eyebrow(s, "The mentor flywheel");
  title(s, "IITians for JEE, rankers for UPSC, ", "verified by us.");
  const flow = [["APPLY", "Rank, qualification, price, and proof (rank card or college ID)"], ["VERIFY", "Admin checks the proof, approves, and the proof is deleted"],
    ["MENTOR", "Chat, weekly check-ins with real progress, 1:1 calls, master sessions"], ["EARN", "80% of every call and seat · payouts tracked in the admin panel"]];
  flow.forEach(([h, b], i) => {
    const x = M + i * 1.62, y = 2.4;
    s.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color: i === 1 ? COL.accent : COL.panel }, line: { color: i === 1 ? COL.accent : COL.fg, width: 1 } });
    s.addText(String(i + 1), { x, y, w: 0.42, h: 0.42, fontFace: MONO, fontSize: 12, color: i === 1 ? COL.ink : COL.fg, align: "center", valign: "middle", margin: 0, isTextBox: true });
  });
  flow.forEach(([h, b], i) => {
    const y = 3.05 + i * 0.78;
    s.addText(h, { x: M, y, w: 1.4, h: 0.3, fontFace: MONO, fontSize: 12, color: i === 1 ? COL.accent : COL.fg, charSpacing: 2, margin: 0, isTextBox: true });
    s.addText(b, { x: M + 1.45, y: y - 0.02, w: 4.6, h: 0.65, fontSize: 14, color: COL.muted, valign: "top", margin: 0, isTextBox: true });
  });
  s.addText("Safe for under-18s: phone numbers and emails masked in every message · conversations reportable · mentors never see a student's contact.",
    { x: M, y: 6.25, w: 6.2, h: 0.55, fontSize: 12, color: COL.muted, margin: 0, isTextBox: true });
  shot(s, "admin.png", 7.15, 2.55, 5.55);
  s.addText("The admin panel: growth, revenue, AI cost per student, and the mentor queue.", { x: 7.15, y: 6.12, w: 5.55, h: 0.4, fontSize: 11, color: COL.muted, margin: 0, isTextBox: true });
  s.addNotes("Mentors are our supply side and our moat. Anyone who cleared the exam applies with proof. We check it, approve, and delete the proof. Mentors chat, get a weekly check-in carrying the student's real Focs progress, take 1:1 calls and run master sessions, and keep 80%. Because many students are under 18, contacts are masked and conversations can be reported.");
}

// 10 · why we win
{
  const s = pres.addSlide({ masterName: "FOCS_CONTENT", sectionTitle: "Close" });
  eyebrow(s, "Why Focs");
  title(s, "Content apps sell lectures. ", "We make them work.");
  const rows = [
    ["", "Coaching apps", "Generic AI chat", "Focs"],
    ["Works on any lecture, live", "Own content only", "Copy-paste, after class", "Yes: tab, phone or photo"],
    ["Reads the board", "No", "Screenshot by screenshot", "Own OCR model, live"],
    ["Hindi / Hinglish, formulas safe", "Some batches", "Formulas get mangled", "Checked on every translation"],
    ["The teacher sees who's lost", "No", "No", "Live, pinned to the board"],
    ["People who cleared it", "Faculty", "No", "Verified mentors, ₹49 calls"],
  ];
  s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: c, options: {
    fontFace: i === 0 ? MONO : THEME.bodyFontFace, fontSize: i === 0 ? 11 : 14, color: j === 3 ? (i === 0 ? COL.ink : COL.accent) : i === 0 ? COL.muted : COL.fg,
    fill: { color: j === 3 && i === 0 ? COL.accent : i % 2 ? COL.panel : COL.bg }, bold: j === 3 && i > 0, valign: "middle",
    border: [{ type: "none" }, { type: "none" }, { pt: 0.75, color: COL.line }, { type: "none" }] } }))),
    { x: M, y: 2.3, w: W - 2 * M, colW: [3.6, 2.6, 2.8, 3.133], rowH: 0.62, margin: [0.04, 0.12, 0.04, 0.12] });
  s.addNotes("Coaching apps sell their own lectures. Generic AI chat helps after class, one screenshot at a time. Focs works live on any lecture, reads the board with our own model, keeps formulas safe in Hindi, is the only one that tells the teacher who's lost, and connects students to people who cleared the exam.");
}

// 11 · traction plan and the ask
{
  const s = pres.addSlide({ masterName: "FOCS_CONTENT", sectionTitle: "Close" });
  eyebrow(s, "The ask");
  s.addText([{ text: "We're asking for " }, { text: "₹ [amount]", options: { color: COL.accent } }, { text: " for " }, { text: "[x]%", options: { color: COL.accent } }, { text: " equity." }],
    { ...TITLE });
  const use = [["40%", "AI and hosting", "Paid Groq + Gemini keys, HTTPS hosting on Cloud Run with Postgres"],
    ["25%", "Mentor supply", "Recruit and verify the first 100 mentors across JEE, NEET and UPSC"],
    ["20%", "Proof", "Real-board OCR benchmark and a learning study with 12–20 students"],
    ["15%", "Pilots", "3 coaching centres or colleges on the teacher side (confusion maps)"]];
  use.forEach(([p, h, b], i) => card(s, M + i * 3.07, 2.3, 2.88, 2.45, { num: p, head: h, body: b, hot: i === 0, size: 13 }));
  s.addText("NEXT 90 DAYS", { x: M, y: 5.1, w: 3, h: 0.3, fontFace: MONO, fontSize: 12, color: COL.accent, charSpacing: 3, margin: 0, isTextBox: true });
  s.addText(bullets(["Host it on HTTPS with a paid AI key, and run the learning study", "Onboard 100 verified mentors and 1,000 students", "Publish the real-board OCR numbers next to the synthetic ones"]),
    { x: M, y: 5.45, w: W - 2 * M, h: 1.2, fontSize: 15, color: COL.fg, valign: "top", margin: 0, paraSpaceAfter: 4, isTextBox: true });
  s.addNotes("[Fill in the amount and equity before the pitch.] Here's how we'd use it: AI keys and hosting first, then mentor supply, then proof (a real-board OCR benchmark and a learning study), then pilots with coaching centres. In 90 days: hosted, 100 verified mentors, 1,000 students, and real numbers published honestly next to the synthetic ones.");
}

// 12 · close
{
  const s = pres.addSlide({ masterName: "FOCS_DARK", sectionTitle: "Close" });
  bridge(s, 2.2, { back: true });
  s.addText([{ text: "Every lecture, " }, { text: "understood.", options: { fontFace: SERIF, italic: true, color: COL.accent } }],
    { x: M, y: 2.9, w: W - 2 * M, h: 1.2, fontFace: THEME.headFontFace, fontSize: 54, color: COL.fg, align: "center", margin: 0, isTextBox: true });
  s.addImage({ path: IMG("logo-light.png"), x: W / 2 - 1.55, y: 4.45, w: 0.62, h: 0.62 });
  s.addText("FOCS", { x: W / 2 - 0.8, y: 4.43, w: 2.6, h: 0.66, fontFace: THEME.headFontFace, fontSize: 34, color: COL.fg, charSpacing: 14, margin: 0, isTextBox: true });
  s.addText("Focs carries the lecture to the student, and the confusion back to the teacher.", { x: M, y: 5.45, w: W - 2 * M, h: 0.4, fontSize: 16, color: COL.muted, align: "center", margin: 0, isTextBox: true });
  s.addText("github.com/Mukul07777/Break_The_Gap_Focs", { x: M, y: 6.45, w: W - 2 * M, h: 0.3, fontFace: MONO, fontSize: 13, color: COL.accent, align: "center", margin: 0, isTextBox: true });
  s.addText("THANK YOU, SHARKS  ·  QUESTIONS?", { x: M, y: 6.0, w: W - 2 * M, h: 0.35, fontFace: MONO, fontSize: 12, color: COL.muted, charSpacing: 4, align: "center", margin: 0, isTextBox: true });
  s.addNotes("Every lecture, understood. Focs carries the lecture to the student, and the confusion back to the teacher. Thank you, Sharks. We'd love your questions.");
}

(async () => {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  await pres.writeFile({ fileName: OUT });
  if (THEME_JS) { const { applyTheme } = require(THEME_JS); await applyTheme(OUT, THEME); }
  console.log("wrote", OUT, fs.existsSync(VIDEO) ? "(film embedded)" : "(no film yet: poster only)");
})();
