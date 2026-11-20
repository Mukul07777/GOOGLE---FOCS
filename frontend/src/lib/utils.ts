import { IN_APP } from "@/lib/server";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.round(diff / 86400)}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function formatDate(iso: string | null | undefined, withTime = false): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric", month: "short", year: "numeric", ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export function formatClock(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function formatMinutes(min: number): string {
  if (min < 1) return "0m";
  if (min < 60) return `${Math.round(min)}m`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}

export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

export function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Burning the midnight oil";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export const EXAMS: { id: string; label: string; hint: string }[] = [
  { id: "jee", label: "JEE", hint: "Main & Advanced" },
  { id: "neet", label: "NEET", hint: "UG medical" },
  { id: "ssc_cgl", label: "SSC CGL", hint: "Tier-I & Tier-II, past papers" },
  { id: "upsc", label: "UPSC", hint: "Lecture notes & doubts (no tests yet)" },
  { id: "gate", label: "GATE", hint: "Engineering PG" },
  { id: "ca", label: "CA", hint: "Lecture notes & doubts (no tests yet)" },
  { id: "cbse", label: "School", hint: "Class 1 to 12 (CBSE)" },
  { id: "coding", label: "Placements", hint: "DSA, core subjects & interviews" },
  { id: "college", label: "College", hint: "B.Tech, by semester" },
  { id: "other", label: "Other", hint: "Lecture notes & doubts" },
];

/** The exams a new student can pick from (UPSC, GATE and CA stay readable for accounts made before). */
export const SIGNUP_EXAMS = EXAMS.filter((e) => !["upsc", "gate", "ca"].includes(e.id));

/** B.Tech branches: a college student prepares for one of these ("college" alone is read as CSE). */
export const BRANCHES: { id: string; short: string; name: string }[] = [
  { id: "college_cse", short: "CSE", name: "Computer Science" },
  { id: "college_it", short: "IT", name: "Information Technology" },
  { id: "college_ece", short: "ECE", name: "Electronics & Communication" },
  { id: "college_ee", short: "EE", name: "Electrical" },
  { id: "college_me", short: "ME", name: "Mechanical" },
  { id: "college_ce", short: "CE", name: "Civil" },
  { id: "college_ai", short: "AI & DS", name: "AI & Data Science / AI-ML" },
  { id: "college_che", short: "ChE", name: "Chemical" },
  { id: "college_bt", short: "BT", name: "Biotechnology" },
];
export const COLLEGES: { id: string; name: string }[] = [
  { id: "iitd", name: "IIT Delhi" }, { id: "iiitd", name: "IIIT Delhi" }, { id: "dtu", name: "DTU" }, { id: "nsut", name: "NSUT" },
  { id: "ggsipu", name: "GGSIPU (IP University)" }, { id: "aktu", name: "AKTU" },
  { id: "other", name: "Another college" },
];

/** GATE papers ("gate" alone is read as CS) and the school classes ("cbse" alone is read as Class 12). */
export const PAPERS: { id: string; short: string; name: string }[] = [
  { id: "gate_cs", short: "CS", name: "Computer Science & IT" },
  { id: "gate_da", short: "DA", name: "Data Science & AI" },
  { id: "gate_ec", short: "EC", name: "Electronics & Communication" },
  { id: "gate_ee", short: "EE", name: "Electrical" },
  { id: "gate_me", short: "ME", name: "Mechanical" },
  { id: "gate_ce", short: "CE", name: "Civil" },
];
export const CLASSES: { id: string; short: string; name: string }[] = [
  ...[1, 2, 3, 4, 5].map((n) => ({ id: `cbse_${n}`, short: `Class ${n}`, name: n <= 2 ? "English, Maths, Hindi" : "English, Maths, Hindi, EVS" })),
  ...[6, 7, 8].map((n) => ({ id: `cbse_${n}`, short: `Class ${n}`, name: "Maths, Science, Social Science, languages" })),
  { id: "cbse_9", short: "Class 9", name: "The new NCERT books" },
  { id: "cbse_10", short: "Class 10", name: "The board year" },
  { id: "cbse_11", short: "Class 11", name: "Science, commerce or humanities" },
  { id: "cbse_12", short: "Class 12", name: "The board year" },
];
/** Exams that come in kinds the student picks from: a tile of EXAMS, then one of these. */
export const SUB_EXAMS: Record<string, { label: string; options: { id: string; short: string; name: string }[]; first: string }> = {
  college: { label: "Your branch", options: BRANCHES, first: "college_cse" },
  gate: { label: "Your paper", options: PAPERS, first: "gate_cs" },
  cbse: { label: "Your class", options: CLASSES, first: "cbse_12" },
};

export const isCollege = (id: string | null | undefined) => !!id && id.startsWith("college");
export const isGate = (id: string | null | undefined) => !!id && id.startsWith("gate");
export const isBoards = (id: string | null | undefined) => !!id && id.startsWith("cbse");
/** Preparing for placements (the "coding" target): DSA, the core subjects, aptitude and interviews. */
export const isPlacement = (id: string | null | undefined) => id === "coding";
/** The branch a college exam target means. */
export const branchOf = (id: string | null | undefined) => BRANCHES.find((b) => b.id === id) ?? BRANCHES[0];
/** Which tile of EXAMS a target belongs under (every branch is under "college", every paper under "gate"). */
export const examGroup = (id: string | null | undefined) => (isCollege(id) ? "college" : isGate(id) ? "gate" : isBoards(id) ? "cbse" : id ?? "");
/** The target a tile stands for: the kind already chosen under it, else its first one. */
export const targetFor = (tile: string, current: string | null | undefined) =>
  !SUB_EXAMS[tile] ? tile : examGroup(current) === tile && current !== tile ? current! : SUB_EXAMS[tile].first;
/** The kind of a tile that is chosen (a bare "gate" or "college" from before there were kinds shows its first). */
export const subExamOf = (id: string | null | undefined) => {
  const sub = SUB_EXAMS[examGroup(id)];
  return sub ? sub.options.find((o) => o.id === id)?.id ?? sub.first : null;
};
/** Exams with a syllabus on Focs: the Prep Hub, a plan, topic notes and tests. */
export const isSsc = (id: string | null | undefined) => id === "ssc_cgl";
export const hasSyllabus = (id: string | null | undefined) => id === "jee" || id === "neet" || isSsc(id) || isCollege(id) || isGate(id) || isBoards(id) || isPlacement(id);
/** School has timed tests only in the board years: chapter tests and a mock board exam in Class 10 and 12 ("cbse"
 *  alone is Class 12). Every other exam has them. */
export const hasTests = (id: string | null | undefined) => !isBoards(id) || id === "cbse" || id === "cbse_10" || id === "cbse_12";
/** Tested one subject at a time (a semester, the boards, placement rounds): there is no single full mock. */
export const subjectTestsOnly = (id: string | null | undefined) => isCollege(id) || isBoards(id) || isPlacement(id);
/** Subjects are courses of the B.Tech library (a semester's, a GATE paper's, what placements test). */
export const usesCourses = (id: string | null | undefined) => isCollege(id) || isGate(id) || isPlacement(id);
/** who has an "Ask a senior" shelf: course students, and JEE/NEET aspirants (answered by B.Tech students) */
export const asksSeniors = (id: string | null | undefined) => usesCourses(id) || id === "jee" || id === "neet";

/** Class 11 and 12 streams: the subjects each one takes (CBSE's usual combinations; one more can be added). */
export const STREAMS: { id: string; name: string; subjects: string[] }[] = [
  { id: "pcm", name: "Science (PCM)", subjects: ["Physics", "Chemistry", "Mathematics", "English Core"] },
  { id: "pcb", name: "Science (PCB)", subjects: ["Physics", "Chemistry", "Biology", "English Core"] },
  { id: "pcmb", name: "Science (PCMB)", subjects: ["Physics", "Chemistry", "Mathematics", "Biology", "English Core"] },
  { id: "commerce_maths", name: "Commerce with Maths", subjects: ["Accountancy", "Business Studies", "Economics", "Mathematics", "English Core"] },
  { id: "commerce", name: "Commerce without Maths", subjects: ["Accountancy", "Business Studies", "Economics", "Informatics Practices", "English Core"] },
  { id: "arts", name: "Arts (Humanities)", subjects: ["History", "Political Science", "Geography", "Economics", "English Core"] },
];
/** Class 6 to 8: the third language, one of these (NEP 2020's three-language formula). */
export const THIRD_LANGUAGES = ["Sanskrit", "French", "German", "Spanish"];

export const examLabel = (id: string | null | undefined) =>
  isCollege(id) ? `B.Tech ${branchOf(id).short}`
    : isGate(id) ? `GATE ${PAPERS.find((p) => p.id === subExamOf(id))?.short ?? ""}`.trim()
      : isBoards(id) ? CLASSES.find((c) => c.id === subExamOf(id))?.short ?? "Boards"
        : EXAMS.find((e) => e.id === id)?.label ?? "Exam";
/** The full mock a student takes: NEET for NEET students, GATE for GATE aspirants, JEE Main for everyone else. */
export const mockExamName = (examTarget: string | null | undefined) => (examTarget === "neet" ? "NEET" : isSsc(examTarget) ? "SSC CGL" : isGate(examTarget) ? "GATE" : "JEE Main");

const BANKED = new Set(["Physics", "Chemistry", "Mathematics", "Biology"]);
/** Subjects with a question bank behind them, so a chapter test can be made: the four school subjects, and for a
 *  B.Tech student every course. */
export const canTest = (subject: string | null | undefined, examTarget: string | null | undefined) =>
  hasTests(examTarget) && (BANKED.has(subject ?? "") || ((usesCourses(examTarget) || isSsc(examTarget)) && !!subject));

/** The id a subject or chapter name gets in the syllabus ("Ray & Wave Optics" -> "ray-and-wave-optics"). */
export const slug = (text: string) => text.toLowerCase().replace(/&/g, " and ").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

const SUBJECT_COLORS: Record<string, string> = {
  Physics: "#8b6cff",
  Chemistry: "#22d3ee",
  Mathematics: "#f5b64a",
  Biology: "#34d399",
  "Computer Science": "#f472b6",
  Economics: "#fb923c",
  Commerce: "#fb923c",
  General: "#94a3b8",
};

// A course outside the fixed list (a B.Tech subject) keeps one colour of its own, picked from its name
const COURSE_COLORS = ["#8b6cff", "#22d3ee", "#f5b64a", "#34d399", "#f472b6", "#fb923c", "#60a5fa", "#a3e635", "#e879f9", "#2dd4bf", "#f87171", "#facc15"];

export function subjectColor(s: string | null | undefined): string {
  const name = s ?? "General";
  if (SUBJECT_COLORS[name]) return SUBJECT_COLORS[name];
  if (name.length < 4 || name === "Other") return "#94a3b8";
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return COURSE_COLORS[h % COURSE_COLORS.length];
}

export async function downloadResponse(res: Response, fallbackName: string) {
  // (the app's web view has nowhere to save a file to)
  if (IN_APP) throw new Error("Saving a file isn't in the app yet. Open Focs in a browser to download this.");
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? fallbackName;
  const file = new File([blob], name, { type: blob.type || "text/plain" });
  if (matchMedia("(pointer: coarse)").matches && navigator.canShare?.({ files: [file] })) {  // a phone: WhatsApp, Drive, Files
    await navigator.share({ files: [file], title: name }).catch(() => undefined);
    return;
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const LETTERS = ["A", "B", "C", "D", "E", "F"];

export function dueLabel(iso: string): string {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000;
  if (diff <= 0) return "due now";
  if (diff < 3600) return `due in ${Math.ceil(diff / 60)}m`;
  if (diff < 86400) return `due in ${Math.round(diff / 3600)}h`;
  return `due in ${Math.round(diff / 86400)}d`;
}

/** "2 h 14 min" until an ISO time (for allowance resets). */
export function timeUntil(iso: string | null | undefined): string {
  if (!iso) return "";
  const min = Math.max(1, Math.round((new Date(iso).getTime() - Date.now()) / 60000));
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60), m = min % 60;
  if (h >= 24) return `${Math.floor(h / 24)} d ${h % 24 ? `${h % 24} h` : ""}`.trim();
  return m ? `${h} h ${m} min` : `${h} h`;
}

/** Local clock time of an ISO timestamp, with the day when it isn't today ("6:40 pm", "Tue 9:05 am"). */
export function clockAt(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString([], { weekday: "short" })} ${time}`;
}

const SCRIPT_LANGUAGES = ["hi", "mr", "bn", "ta", "te", "gu"];

/** The `lang` attribute for text in a student's language, so screen readers switch voice (Hinglish is Hindi in Latin letters). */
export function langAttr(language: string | null | undefined): string | undefined {
  return language && SCRIPT_LANGUAGES.includes(language) ? language : language === "hinglish" ? "hi-Latn" : undefined;
}

/** A chapter name as a student reads it: school chapters that share a name across classes are stored as
 *  "Fractions (Class 6)" so they stay unique, and the tag is only for the server. */
export function shownName(name: string) {
  return name.replace(/\s*\(Class [\d/]+\)/g, "");
}

export function formatPaused(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return m % 60 ? `${h} h ${m % 60} min` : `${h} h`;
}
