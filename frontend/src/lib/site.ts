/** Public business details shown on legal pages. Set them in frontend/.env (VITE_*) before launch. */
export const SITE = {
  name: "Focs",
  legalName: (import.meta.env.VITE_LEGAL_NAME as string | undefined) || "Focs",
  supportEmail: (import.meta.env.VITE_SUPPORT_EMAIL as string | undefined) || "support@focs.in",  // students' help and privacy requests
  grievanceOfficer: (import.meta.env.VITE_GRIEVANCE_OFFICER as string | undefined) || "Mukul",  // DPDP Act, 2023
  jurisdiction: (import.meta.env.VITE_JURISDICTION as string | undefined) || "India",
  updated: "24 October 2026",
};

export const contactLine = SITE.supportEmail
  ? `write to ${SITE.supportEmail}`
  : "use Settings → Your data in the app, or the contact details on our website";

/* ---------------------------------------------------------------- the bridge (Devlympics "Bridge the Gap" build) */
/** The event build (VITE_EDITION=bridge) tells one story and shows only the screens that tell it; everything else
    still works by URL. The normal build is unchanged. */
export const BRIDGE = import.meta.env.VITE_EDITION === "bridge";

/* ---------------------------------------------------------------- the roots build (Google hackathon) */
/** VITE_EDITION=roots: one story, the root-cause loop (scribble -> wrong step -> the earlier gap -> five-minute fix ->
    proof), with only its screens in the menu. Everything else still opens by URL. */
export const ROOTS = import.meta.env.VITE_EDITION === "roots";
export const ROOTS_LINE = "Other apps mark the answer. Focs finds the step, and the year, where understanding broke.";
export const ROOTS_LEDE = "Write your working on the rough pad. Gemini reads every step, finds the first one that went wrong, and traces it back to the earlier class it comes from. A five-minute fix in your language, then proof that the stuck topic moved. Teachers see where their whole batch's gaps really start.";

/** The one answer to "which two sides, and what's between them", used word for word on the landing page, the
    README, slide 1 and the demo's first sentence. */
export const BRIDGE_LINE = "Focs carries the lecture to the student, and the confusion back to the teacher.";

export interface Lane { key: string; title: string; body: string; toTeacher?: boolean; ready: boolean }
/** The four lanes between the two sides. `ready` says whether the lane is built yet: the page never claims more. */
export const LANES: Lane[] = [
  { key: "speed", title: "Speed", body: "The board, read by Focs's own OCR, and the teacher's voice become live notes and captions.", ready: true },
  { key: "language", title: "Language and ability", body: "Notes, quizzes and captions in Hindi or Hinglish, with every formula left as it is.", ready: true },
  { key: "understanding", title: "Understanding", body: "Every answer locked in as Sure or Guessing: the blind spots, sure and wrong, come first.", ready: true },
  { key: "return", title: "Return", body: "\u201cI'm lost\u201d taps, pinned to the exact board, reach the teacher live.", toTeacher: true, ready: true },
];
