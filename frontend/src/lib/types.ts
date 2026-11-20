/** A B.Tech branch: college students prepare for "college_<branch>". */
export type CollegeBranch = "college_cse" | "college_it" | "college_ece" | "college_ee" | "college_me" | "college_ce" | "college_ai" | "college_che" | "college_bt";
export type CollegeId = "iitd" | "iiitd" | "dtu" | "nsut" | "ggsipu" | "aktu" | "other";
export type GatePaper = "gate_cs" | "gate_da" | "gate_ec" | "gate_ee" | "gate_me" | "gate_ce";
export type SchoolClass = "cbse_1" | "cbse_2" | "cbse_3" | "cbse_4" | "cbse_5" | "cbse_6" | "cbse_7" | "cbse_8" | "cbse_9" | "cbse_10" | "cbse_11" | "cbse_12";
export type Language = "en" | "hinglish" | "hi";
export type ExamTarget = "jee" | "neet" | "ssc_cgl" | "upsc" | "gate" | "ca" | "cbse" | "coding" | "college" | CollegeBranch | GatePaper | SchoolClass | "other";

export interface User {
  id: number;
  email: string;
  full_name: string;
  plan: "free" | "pro" | "team" | null;
  exam_target: ExamTarget | null;
  class_level: string | null;
  daily_goal_min: number | null;
  show_on_leaderboard?: boolean | null;
  created_at: string | null;
  /** college students: whose semester plan they follow, their semester, and the subjects they picked (null: the plan's) */
  college?: CollegeId | null;
  semester?: number | null;
  subjects?: string[] | null;
  /** the language explanations are written in (null: English) */
  language?: Language | null;
  /** a paid Pro month ends here */
  pro_until?: string | null;
  /** a student studies; a mentor (approved by Focs) guides students from their own dashboard */
  role?: "student" | "mentor" | null;
}

/** The right password, and a code sent to the account's email: the second step of signing in. */
export interface LoginCode {
  code_required: true;
  challenge: string;
  sent_to: string;
  resend_after: number;
}

export interface TokenResponse {
  access_token: string;
  user: User;
  created?: boolean;  // Continue with Google made a new account
}

export interface StudySession {
  id: number;
  title: string | null;
  subject: string | null;
  source: "screen" | "upload" | "camera" | "link" | null;
  video_url: string | null;
  course_id: number | null;
  is_active: boolean | null;
  started_at: string | null;
  ended_at: string | null;
  frames_processed: number | null;
  note_count: number;
  duration_min: number;
  summary: string | null;
}

export interface Note {
  id: number;
  session_id: number;
  topic: string | null;
  subject: string | null;
  ai_notes: string | null;
  /** the notes' language when not English */
  language?: Language | null;
  /** what the teacher said while this board was up (the voice lane) */
  spoken_md?: string | null;
  ocr_raw: string | null;
  ocr_confidence: number | null;
  engine: string | null;
  has_image: boolean;
  is_pinned: boolean | null;
  captured_at: string | null;
  updated_at: string | null;
}

export interface SessionDetail extends StudySession {
  notes: Note[];
}

export interface OcrLine {
  text: string;
  confidence: number;
  box: number[][];
  engine: "focs" | "rapid" | string;
  candidates?: Record<string, { text: string; confidence: number }>;
}

export interface OcrResult {
  text: string;
  confidence: number;
  lines: OcrLine[];
  engine: string;
  detector: string;
  elapsed_ms: number;
  width: number;
  height: number;
  board: string;
}

export interface Checkpoint {
  question: string;
  options: string[];
  answer_index: number;
  explanation: string;
  topic: string;
  source: string;
}

export type FrameStatus = "busy" | "unchanged" | "no_text" | "duplicate" | "not_lecture" | "created" | "updated" | "growing";

/** About half a minute of what the teacher said, as text (the audio itself is never kept). */
export interface LectureSegment { id: number; start_s: number; end_s: number; text: string; language: string | null; note_id: number | null }
/** A summary of everything the teacher said, kept with the lecture. ``stale``: it covers fewer pieces than there are now,
    because a new one couldn't be written (``reason``). */
export interface TalkSummary { summary_md: string | null; pieces: number; source?: "ai" | "kept"; stale?: boolean; reason?: "allowance" | "busy" }
export interface AudioResult { segment?: LectureSegment; spoken_note?: Note | null; skipped?: "silence" | "unavailable" | "allowance" | "captions" | "busy" }

export interface FrameResponse {
  status: FrameStatus;
  ocr?: OcrResult;
  note?: Note;
  checkpoint?: Checkpoint | null;
  ai_source?: string;
  session_id?: number;
  basic_mode?: boolean;
  /** "growing": send a settle request once the board has been still this long */
  settle_after?: number;
  /** a board the lecture moved on from, written up now (a minute after it left the screen) */
  also_updated?: Note;
  also_status?: "created" | "updated";
  /** the student reads Hindi/Hinglish but this board's notes are in English (the AI couldn't translate them now) */
  language_note?: string | null;
}

/** lecture by link: "rewatch" (already written up), "nothing" (no teaching in it), "busy" (try again later) */
export interface ClipResult {
  status: "created" | "nothing" | "rewatch" | "allowance" | "busy";
  note?: Note;
  checkpoint?: Checkpoint | null;
}

export interface SessionEnd {
  session: StudySession;
  summary_md: string;
  key_formulas: string[];
  flashcards_created: number;
  source: string;
  /** the lecture's quizzes, sure vs right */
  calibration?: Calibration | null;
}

export interface MCQ {
  q: string;
  options: string[];
  answer_index: number;
  explanation: string;
}
export interface TrueFalse {
  statement: string;
  answer: boolean;
  explanation: string;
}
export interface Subjective {
  q: string;
  key_points: string[];
  model_answer: string;
}
export interface Quiz {
  topic: string;
  subject: string;
  mcq: MCQ[];
  true_false: TrueFalse[];
  subjective: Subjective[];
  source: string;
  /** why a set came back shorter than asked, or built offline */
  notice?: string | null;
  session_id: number | null;
  /** set when the set was built for a syllabus topic */
  topic_id?: string;
}

export interface Evaluation {
  score: number;
  grade: string;
  points_covered: string[];
  points_missed: string[];
  feedback: string;
  source: string;
  /** a photographed answer: what Focs read in it */
  read_answer?: string;
}

export interface RedoItem {
  id: number;
  topic: string | null;
  question: string | null;
  q_type: string | null;
  subject: string | null;
  attempted_at: string | null;
}

export type Grade = "again" | "hard" | "good" | "easy";

export interface Flashcard {
  id: number;
  front: string;
  back: string;
  topic: string | null;
  subject: string | null;
  session_id: number | null;
  note_id: number | null;
  ease: number;
  interval_days: number;
  repetitions: number;
  lapses: number;
  due_at: string;
  last_reviewed_at: string | null;
  created_at: string;
  intervals: Record<Grade, string>;
}

export interface CardStats {
  total: number;
  due: number;
  new: number;       // never reviewed
  learning: number;  // reviewed, not yet remembered twice in a row
  mature: number;
}

export interface Overview {
  streak: number;
  best_streak: number;
  streak_at_risk: boolean;
  active_today: boolean;
  freezes_left: number;
  frozen_days: number;
  study_days_year: number;
  today_minutes: number;
  today_by_activity: Record<string, number>;
  daily_goal_min: number;
  week_minutes: number;
  totals: { sessions: number; notes: number; questions: number; doubts: number; flashcards: number };
  accuracy: number | null;
  due_cards: number;
  redo_count: number;
  week: { date: string; label: string; minutes: number; questions: number; correct: number; accuracy: number | null }[];
  heatmap: { date: string; minutes: number; actions: number; active: boolean }[];
  subjects: { subject: string; notes: number; questions: number; correct: number; accuracy: number | null }[];
  weak_topics: { topic: string; attempts: number; accuracy: number }[];
  recent_sessions: StudySession[];
}

/** A board of a room's lecture, as the confusion map names it. */
/** One small thing to do while the AI works (GET /wait/task). */
export type WaitTask =
  | { kind: "card"; id: number; front: string; back: string; topic: string | null }
  | { kind: "redo"; id: number; question: string; topic: string | null }
  | { kind: "formula"; id: number; formula: string; topic: string | null; subject: string }
  | { kind: "none"; id?: undefined; topic?: undefined };

export interface RoomBoard { note_id: number; number: number; topic: string; excerpt: string }
export interface ConfusionMeter { last_minute: number; total: number; board: (RoomBoard & { count: number }) | null }
export interface ConfusionReport {
  code: string; name: string; topic: string | null; is_active: boolean; live: ConfusionMeter | null;
  totals: { lost: number; wrong: number; doubts: number; quizzes: number; boards: number };
  boards: (RoomBoard & { lost: number; wrong: number; doubts: number; sure_wrong: number; score: number })[];
  timeline: { minute: number; lost: number; wrong: number; doubts: number }[];
  quizzes: { question: string; options: string[]; counts: number[]; answer_index: number | null; answered: number; correct: number; board: number | null }[];
  doubts: { text: string; votes: number; resolved: boolean; board: number | null }[];
}

export interface Room {
  id: number;
  code: string;
  name: string;
  video_url: string;
  topic: string | null;
  is_host: boolean;
  max_members: number;
  online: number;
  is_active: boolean;
  created_at: string | null;
}

export interface Doubt {
  id: number;
  session_id: number | null;
  question: string;
  answer: string;
  created_at: string;
}

export interface ModelCard {
  name: string;
  version: string;
  exported: string;
  architecture: string;
  params: number;
  charset_size: number;
  best_step: number;
  validation: { cer: number; wer: number; line_acc: number; n: number };
  examples: { gt: string; pred: string }[];
  training: { steps?: number; samples_seen?: number; train_minutes?: number; device?: string; batch?: number };
  loss_curve: { step: number; loss: number }[];
  eval_curve: { step: number; cer: number; wer: number; line_acc: number }[];
  data: { type: string; styles: string[]; degradations: string[] };
}

export interface Benchmark {
  generated: string;
  images: number;
  lines: number;
  engines: Record<string, { cer: number; wer: number; line_acc: number; ms_per_image: number }>;
  by_style?: Record<string, Record<string, number>>;
  set?: string;
  licences?: Record<string, number>;  // a real set: how many frames under each licence
  sources?: number;
}

export interface ModelInfo {
  default: string;
  engines: string[];
  detector: string | null;
  errors: Record<string, string>;
  model_card: ModelCard | null;
  benchmark: Benchmark | null;
  benchmark_real?: Benchmark | null;
}

export interface Plan {
  id: "free" | "pro" | "team";
  name: string;
  price_inr: number | null;
  period: string;
  tagline: string;
  features: string[];
  highlight?: boolean;
  /** the regular price, struck through while the launch offer runs */
  regular_inr?: number | null;
}

/** A way to buy Pro: a month, six months or a year. save_pct is against paying month by month; regular_inr is struck
 *  through while the launch offer runs; fair_use_hours is about how many lecture hours its 30-day ceiling holds. */
export interface ProPass {
  id: "month" | "semester" | "year"; label: string; price_inr: number; days: number; per_month_inr: number; save_pct: number;
  regular_inr: number | null; fair_use_hours: number | null;
}
/** Who pays which Pro price: JEE / NEET (and every exam without its own yet), college, school */
export type PriceSector = "exam" | "college" | "school" | "ssc";
export interface PlansInfo {
  plans: Plan[]; dev_upgrade: boolean; payments: "razorpay" | "dev" | null; pro_days: number; call_price_inr: number;
  passes: ProPass[]; pro_sessions_per_week: number; captions_min_week: { free: number; pro: number };
  sector: PriceSector; sectors: { id: PriceSector; label: string; hint: string }[];
  /** the launch offer while it runs: Pro at the offer price for the first `places` students who pay */
  offer: { places: number; left: number } | null;
}

/** The public health check: only what a signed-out page needs. */
export interface Health {
  status: string;
  llm: { available: boolean };
  email?: boolean;
  google_client_id?: string | null;  // Sign in with Google is set up on this server
}

/** The full health check, for signed-in users (Settings). */
export interface HealthDetails extends Omit<Health, "llm"> {
  version: string;
  database: "supabase" | "local";
  storage: "supabase" | "local";
  llm: { available: boolean; model: string | null };
  ocr: { engines: string[]; default: string; detector: string | null };
}

/* ---------------------------------------------------------------- AI allowance */
export interface UsageMeter {
  used: number;
  limit: number | null;
  unlimited: boolean;
  pct: number;
  resets_at: string | null;
}

export interface MockOffer { id: "one" | "pack"; count: number; price_inr: number }

export interface MockQuota {
  used: number;
  limit: number | null;
  unlimited: boolean;
  /** this week's free ones left plus bought ones */
  left: number | null;
  /** this week's free ones left (bought ones are used after them) */
  free_left?: number | null;
  /** bought mocks not yet taken; they don't run out with time */
  credits?: number;
  /** full mocks on sale one at a time (empty: off sale, or the plan is unlimited) */
  offers?: MockOffer[];
  resets_at: string | null;
}

export interface Usage {
  plan: "free" | "pro" | "team";
  window_hours: number;
  window: UsageMeter;
  week: UsageMeter;
  /** lecture time today that got AI board notes, in minutes (each plan's daily lecture hours: lecture_limits) */
  lecture: UsageMeter;
  lecture_limits: Record<string, number>;
  /** lecture captions this week, in minutes */
  captions: UsageMeter;
  /** share of the plan's 30-day fair-use AI used (null: no limit) */
  fair_use_pct: number | null;
  costs: { action: string; label: string; cost: number }[];
  limits: Record<string, { window: number; week: number }>;
  mocks: MockQuota;
}

/* ---------------------------------------------------------------- mock tests */
export interface MockSection {
  key: string;
  qtype: "mcq" | "numerical";
  count: number;
  attempt: number;
  correct: number;
  wrong: number;
  label: string;
}

export interface MockPattern {
  id: string;
  name: string;
  short: string;
  description: string;
  duration_min: number;
  subjects: string[];
  per_subject: number;
  total_questions: number;
  max_score: number;
  notes: string[];
  sections: MockSection[];
  chapters: string[];
  /** subject → its number of questions, when subjects get different numbers (GATE, a last-day test) */
  subject_counts?: Record<string, number> | null;
}

export interface MockMeta {
  /** college: no full mock, only tests on one subject (all of it or some chapters) */
  exam: "jee" | "neet" | "ssc_cgl" | "college" | "gate" | "cbse";
  patterns: MockPattern[];
  default: string | null;
  quota: MockQuota;
  bank: Record<string, Record<string, number>>;
  syllabus: Record<string, string[]>;
  chapter_stock: Record<string, Record<string, number>>;
  chapter_sizes: number[];
  /** Class 10 and 12: a timed board-style paper on a whole subject */
  board_mock?: boolean;
}

export type MockStatus = "preparing" | "ready" | "in_progress" | "submitted" | "failed";

export interface MockSummary {
  id: number;
  title: string;
  pattern: string;
  pattern_name: string;
  kind: "full" | "chapter";
  config: { subject: string; chapters: string[]; count: number } | null;
  status: MockStatus;
  progress: number;
  error: string | null;
  duration_min: number;
  created_at: string | null;
  started_at: string | null;
  submitted_at: string | null;
  remaining_sec: number | null;
  score: number | null;
  max_score: number | null;
  accuracy: number | null;
  correct: number | null;
  incorrect: number | null;
  time_sec: number | null;
  subjects: { subject: string; score: number; max: number }[];
}

export interface MockQuestion {
  id: number;
  no: number;
  subject: string;
  section: string;
  qtype: "mcq" | "numerical";
  question: string;
  options: string[] | null;
  /** a past exam question: "JEE Main 2019 (Jan)", "NEET 2021"… */
  paper?: string | null;
  answer?: string;
  solution?: string;
  chapter?: string;
  difficulty?: string;
  /** pictures the question needs (SSC reasoning figures); an option given as a picture has "" as its text */
  media?: { figures: string[]; options: (string | null)[] | null };
  /** the question as the paper printed it in Hindi */
  hindi?: { question: string | null; options: string[] | null };
}

/** a = answer (option index or number, as text), m = marked for review, v = visited, t = seconds spent */
export interface MockResponse { a: string | null; m?: boolean; v?: boolean; t?: number; /** how sure */ c?: "sure" | "unsure" }

/** Confidence vs reality (services/calibration.py): answers locked in as sure or guessing, against right or wrong. */
export interface CalibrationItem { id: number; topic: string | null; subject: string | null; question: string; q_type: string | null; at: string | null }
export interface Calibration {
  answers: number; grid: { sure_right: number; sure_wrong: number; guess_right: number; guess_wrong: number };
  sure_accuracy: number | null; guess_accuracy: number | null; blind_spots: CalibrationItem[]; hidden_strengths: CalibrationItem[];
  topics: { topic: string; subject: string; sure_right: number; sure_wrong: number; guess_right: number; guess_wrong: number }[];
  headline: string | null;
}

export interface MockBreakdown {
  score: number;
  max: number;
  correct: number;
  incorrect: number;
  unattempted: number;
  attempted: number;
  accuracy: number;
  negative: number;
  time_sec: number;
}

export interface MockResult {
  total: MockBreakdown;
  subjects: (MockBreakdown & { subject: string; sections: (MockBreakdown & { key: string; label: string })[] })[];
  chapters: (MockBreakdown & { subject: string; chapter: string })[];
  questions: { id: number; subject: string; section: string; chapter: string; outcome: "correct" | "incorrect" | "unattempted"; marks: number; time_sec: number; answer: string | null; marked: boolean; confidence?: "sure" | "unsure" | null }[];
  insights: string[];
}

export interface MockDetail extends MockSummary {
  pattern_info: MockPattern | null;
  questions?: MockQuestion[];
  responses?: Record<string, MockResponse>;
  current_index?: number;
  tab_switches?: number;
  result?: MockResult;
  gap_map?: GapMap | null;
}

/** While a paper is written: what it covers, from the notes library, and how ready the student feels. */
export type Feeling = "sure" | "shaky";
export interface WarmupCard {
  subject: string; chapter: string; chapter_id: string | null; topics: string[]; points: string[];
  check: { q: string; a: string }[]; felt: Feeling | null;
}
export interface Warmup { cards: WarmupCard[]; status: MockStatus; progress: number }

/** After it: how each chapter held up against how ready the student felt, and what to do next. */
export interface GapRow {
  subject: string; chapter: string; chapter_id: string | null; asked: number; attempted: number; correct: number; wrong: number; share: number;
  level: "strong" | "shaky" | "gap" | "untried"; felt: Feeling | null; flag: "blind_spot" | "hidden_strength" | null;
}
export interface GapStep {
  kind: "revise" | "retest" | "senior" | "redo" | "stretch"; title: string; detail: string;
  chapter_id?: string; subject?: string; chapters?: string[]; count?: number; chapter?: string;
}
export interface GapMap { chapters: GapRow[]; steps: GapStep[]; summary: string }

/* ---------------------------------------------------------------- leaderboard */
export interface LeaderRow { user_id: number; name: string; exam: string | null; correct: number; answered: number; accuracy: number; xp: number; rank: number }
export interface Leaderboard { period: "week" | "all"; scope: "exam" | "everyone"; exam: string | null; total: number; top: LeaderRow[]; me: LeaderRow | null; hidden: boolean; xp_rule: string }

/* ---------------------------------------------------------------- formula book */
export interface FormulaSubject {
  subject: string;
  count: number;
  topics: { topic: string; formulas: { text: string; note_id: number; session_id: number }[] }[];
}

/* ---------------------------------------------------------------- admin */
export interface Money { usd: number; inr: number }
export interface AdminOverview {
  generated_at: string;
  goal: { target: number; paying: number; signups: number };
  users: { total: number; new_today: number; new_7d: number; new_30d: number; paying: number;
    active: { day: number; week: number; month: number }; by_plan: Record<string, number>; by_exam: Record<string, number> };
  revenue: { price_inr: number; offer: { places: number; left: number } | null; pro_users: number; team_users: number; mrr_inr: number; collected_inr: number; payments_connected: boolean };
  ai_cost: { total: Money; today: Money; week: Money; this_month: Money; last_30d: Money; per_active_user_30d: Money; calls: number;
    by_feature: (Money & { feature: string; calls: number })[];
    by_model: (Money & { model: string; calls: number; prompt_tokens: number; completion_tokens: number })[];
    top_users: (Money & { user_id: number; name: string; email: string | null; plan: string | null; calls: number })[];
    usd_inr: number; note: string; budget: { daily_inr: number; spent_inr: number; reached: boolean } };
  margin_30d_inr: number;
  series: { day: string; signups: number; cost_inr: number }[];
  usage: { lectures: number; boards: number; questions_answered: number; doubts: number; mocks_taken: number;
    lectures_30d: number; rooms_live: number; people_in_rooms: number };
  roots: RootProof;
}
/** Root-cause tracing for real students, from the app's own records (percentages are null until there is data). */
export interface RootProof {
  students: number; traces: number; with_root: number; root_rate: number | null; root_classes: { cls: number; traces: number }[];
  lessons: number; fixed: number; recheck_pass: number | null; median_minutes_to_fix: number | null;
  chains_built: number; reused: number | null; ai_usd: number; ai_usd_per_student: number | null;
  /** the stuck topic itself, before the trace and after the fix, over the students who did both (percent right) */
  retest_pairs: number; retest_before: number | null; retest_after: number | null;
}
export interface AdminUser extends Money {
  id: number; name: string; email: string; plan: string; exam: string | null; joined: string | null; last_seen: string | null; lectures: number;
}

/* ---------------------------------------------------------------- prep hub & mentor plan */
export type EntranceTrack = "jee_main" | "jee_advanced" | "neet";
export type Track = EntranceTrack | "college" | "gate" | "cbse" | "placement" | "ssc_cgl";
export type ClassLevel = "11" | "12" | "dropper";
export type Standing = "none" | "partial" | "done";
/** entrance: JEE/NEET · college: a B.Tech semester · gate: a GATE paper · school: Class 11/12 */
export type SyllabusKind = "entrance" | "college" | "gate" | "school";

export interface TargetBand { id: string; label: string; hint: string; hours: number }

export interface PrepOptions {
  tracks: { id: EntranceTrack; exam: "jee" | "neet"; label: string }[];
  targets: Record<"jee" | "neet" | "college" | "gate" | "cbse" | "placement" | "ssc_cgl", TargetBand[]>;
  subjects: Record<"jee" | "neet", string[]>;
  default_dates: Record<EntranceTrack, Record<ClassLevel, string>>;
  date_choices: Record<EntranceTrack, string[]>;
  /** the next exam rounds of a college year (approximate) and the one a plan aims at by default */
  college: { dates: { date: string; label: string }[]; default_date: string };
  /** GATE, placements and school: the coming rounds (approximate), by "gate", "placement", "cbse_1" … "cbse_12" */
  rounds: Record<string, { date: string; label: string }[]>;
}

/** A college student's set-up: their branch's semester plan at a college, and the courses to pick from. */
export interface CollegeSetup {
  branch: { id: CollegeBranch; short: string; name: string };
  branches: { id: CollegeBranch; short: string; name: string }[];
  college: CollegeId;
  semester: number | null;
  /** the student has saved a semester (false: still on the defaults) */
  saved: boolean;
  colleges: { id: CollegeId; name: string; full: string; has_plan: boolean }[];
  /** the plan shown is this college's own (false: the typical plan) */
  own_plan: boolean;
  source: string;
  semesters: { n: number; subjects: string[] }[];
  subjects: string[];
  /** the student chose these themselves, instead of following the plan */
  picked: boolean;
  catalogue: { name: string; about: string; area: string; semester: number; chapters: number; topics: number; hours: number }[];
  max_subjects: number;
}

export interface StudyGoal {
  /** "jee" | "neet" | a college branch */
  exam: string;
  kind?: SyllabusKind;
  /** what the goal is kept under: jee | neet | college | gate | cbse */
  group?: "jee" | "neet" | "college" | "gate" | "cbse" | "placement";
  track: Track;
  /** "11" | "12" | "dropper"; college: the semester, "1"-"8" */
  class_level: string;
  exam_date: string;
  target: string;
  dream: string | null;
  weekday_hours: number;
  weekend_hours: number;
  coaching: "self" | "online" | "offline";
  /** per subject: by class ("11"/"12"), or for a college course as a whole ("all") */
  standing: Record<string, Partial<Record<"11" | "12" | "all", Standing>>>;
}

export interface PlanTask {
  key: string;
  /** custom: a task the student added themselves (key "custom:<id>"); fix: today's weak spot from a test */
  kind: "learn" | "practice" | "revise" | "test" | "mock" | "custom" | "fix";
  /** fix: how many more weak spots are waiting behind this one */
  more?: number;
  title: string;
  minutes: number;
  subject?: string;
  chapter_id?: string;
  chapter?: string;
  topics?: { id: string; name: string }[];
  questions?: number;
  done: boolean;
}

export interface TodayPlan {
  date: string;
  minutes: number;
  tasks: PlanTask[];
  done?: number;
  note: string | null;
  /** planned tasks the student took off today's list */
  hidden?: { key: string; title: string }[];
}

export interface PlanWeek {
  start: string;
  end: string;
  phase: "learning" | "revision";
  hours: number;
  learn: { chapter_id: string; chapter: string; subject: string; hours: number; topics: string[]; finishes: boolean }[];
  finished: string[];
  revise: { id: string; name: string }[];
  chapter_tests: { id: string; name: string }[];
  mocks: number;
  completion: number;
  questions: number;
}

export interface PlanMonth {
  month: string;
  phase: "learning" | "revision" | "mixed";
  hours: number;
  mocks: number;
  questions: number;
  completion: number;
  finish: { id: string; name: string; subject: string }[];
  start: { id: string; name: string; subject: string }[];
  milestones: string[];
}

export interface MentorNote { tone: "good" | "warn" | "info"; title: string; text: string }

export interface StudyPlan {
  kind?: SyllabusKind;
  /** tested one subject at a time (a semester, the boards, placements): no full mock */
  subject_tests?: boolean;
  status: "done" | "comfortable" | "on_track" | "tight" | "behind" | "past";
  exam_date: string;
  days_left: number;
  revision_from: string;
  revision_weeks: number;
  syllabus_done_on: string | null;
  completion: number;
  by_subject: Record<string, number>;
  expected_now: number | null;
  /** by_day: Monday…Sunday; custom_days: the student set them day by day */
  hours: { weekday: number; weekend: number; weekly: number; needed_daily: number; by_day: number[]; custom_days: boolean };
  target: TargetBand;
  unfinished: string[];
  priority_mode: boolean;
  covered_weight: number;
  /** chapters the student left out of the plan, and how much of the paper they are worth (percent) */
  skipped: { id: string; name: string; subject: string; weightage: "high" | "medium" | "low" }[];
  skipped_weight: number;
  /** chapters the student asked to study next, first one first */
  pinned: string[];
  weeks: PlanWeek[];
  months: PlanMonth[];
  mentor: MentorNote[];
  today: TodayPlan | null;
  goal: StudyGoal;
}

export interface SyllabusTopic { id: string; name: string; done: boolean; video: string | null; has_notes: boolean }

export interface SyllabusChapter {
  id: string;
  name: string;
  subject: string;
  unit: string;
  /** 11 | 12; for a college course the semester it is planned in (0: not in the plan) */
  class: number;
  hours: number;
  weight: number;
  weightage: "high" | "medium" | "low";
  foundation: boolean;
  done: number;
  total: number;
  finished_on: string | null;
  revisions: number;
  questions: number;
  topics: SyllabusTopic[];
}

export interface SyllabusTree {
  exam: string;
  kind: SyllabusKind;
  /** college: the student's semester, the semester being looked at (null: their own subjects), and their subjects */
  college: { semester: number | null; viewing: number | null; college: CollegeId; branch: { id: string; short: string; name: string };
    set_up: boolean; my_subjects: string[] } | null;
  /** Class 11/12: every subject there is to take (the student's own are `subjects`) */
  choices?: string[] | null;
  name: string;
  about: string;
  subjects: { name: string; about?: string | null; semester?: number | null; mine?: boolean;
    units: { name: string; chapters: SyllabusChapter[] }[] }[];
  stats: { subjects: number; chapters: number; topics: number; hours: number; done_topics: number; questions: number };
}

export interface TopicDetail {
  id: string;
  name: string;
  video: string | null;
  /** the detailed notes are already in the library (they open instantly) */
  notes_ready: boolean;
  done: boolean;
  kind?: SyllabusKind;
  chapter: { id: string; name: string; subject: string; class: number; topics: { id: string; name: string }[] };
  your_notes: { id: number; topic: string | null; session_id: number; captured_at: string | null }[];
  questions: number;
}

/** Detailed notes: a topic's pre-made note from the library, or the detailed write-up of one board. */
export interface DetailedNotes {
  source: "library" | "board";
  title: string;
  notes_md: string;
  language?: Language;
  language_note?: string;
  written_now: boolean;
  /** a second model went through the note and found nothing left to correct */
  checked?: boolean;
  topic_id?: string;
  chapter?: string;
  subject?: string;
  /** how the exam asks it: real past questions from the bank first */
  questions?: ExamQuestion[];
}

/** A question shown with a note. ``real``: a genuine past exam question, from the paper named in ``paper``. */
export interface ExamQuestion {
  id: number;
  real: boolean;
  paper: string | null;
  year: number | null;
  /** on this very topic, or only from the same chapter */
  match: "topic" | "chapter";
  qtype: "mcq" | "numerical";
  difficulty: string | null;
  question: string;
  options: string[] | null;
  /** the option index (mcq) or the value (numerical), as text */
  answer: string;
  solution: string;
}

/* ---------------------------------------------------------------- ask with a photo */
export interface SolvedDoubt {
  id: number; question: string; subject: string; topic: string; idea: string; steps: string[]; answer: string; watch_out: string | null;
}
export interface MarkedAnswer {
  question: string; marks: number; max_marks: number; percent: number; got_right: string[];
  lost: { where: string; why: string; marks: number }[]; model_answer: string; next_time: string | null;
}

/* ---------------------------------------------------------------- campus: papers and notes students share */
export interface CampusItem {
  id: number; kind: "paper" | "notes"; subject: string; title: string; year: number | null;
  exam_kind: "mid" | "end" | "quiz" | "other" | null; college: string; pages: number; size: number;
  votes: number; voted: boolean; mine: boolean; by: string; has_questions: boolean; opens: number; created_at: string | null;
}
export interface CampusShelf { college: string; college_name: string; subjects: string[]; catalogue: string[]; items: CampusItem[] }
/** Ask a senior: a junior's question (with its answers), a senior's tip, or an answer. */
export interface AskPost {
  id: number; kind: "question" | "tip" | "answer"; subject: string; chapter: string | null; body: string;
  /** why the author can speak for the course ("Did it in Sem 3"); null: not a senior */ senior: string | null;
  college: string; by: string; mine: boolean; votes: number; voted: boolean; created_at: string | null; answers?: AskPost[];
  /** Focs's AI draft, and what a senior made of it */ ai: boolean; checked: string | null;
  /** the asker marked it as the answer that settled it */ accepted: boolean; /** answers of this author that settled a question */ helped: number;
}
export interface AskVerification { verified: boolean; email: string | null; needed: boolean; domains: string[]; pending: boolean }
export interface NotificationItem { id: number; kind: string; text: string; link: string | null; read: boolean; created_at: string | null }
export interface AskBoard {
  subject: string; chapters: string[]; college: string; college_name: string; subjects: string[]; /** courses this student has done */ done: string[]; catalogue: string[];
  senior: string | null; tips: AskPost[]; questions: AskPost[]; waiting: AskPost[];
  /** "courses": a college's shelf; "school": a JEE/NEET aspirant's, answered by B.Tech students */ shelf: "courses" | "school";
  verification: AskVerification;
}
export interface CampusQuestions { id: number; title: string; subject: string; questions: { no: string; text: string; marks: number | null }[] }

/* ---------------------------------------------------------------- classes and the parent link */
/** How a student's preparation is going: what a teacher sees for each student, and a parent for a child. */
export interface ProgressSummary {
  exam: string; week_minutes: number; /** the last 7 days, today last */ days: number[]; today_minutes: number; goal_minutes: number; streak: number;
  syllabus: { done: number; total: number; percent: number | null };
  weak: { id: string; chapter: string; subject: string }[]; weak_count: number;
  last_test: { title: string; score: number; max: number; percent: number; on: string | null } | null;
  tests_week: number; questions_week: number; accuracy_week: number | null; last_active: string | null;
}
/* ---------------------------------------------------------------- mentors */
export interface MentorCard {
  id: number; name: string; exam: string; exam_label: string; credential: string; institution: string; headline: string; about: string;
  topics: string[]; languages: string[]; capacity: number; active: number; open_spots: number; accepting: boolean; verified: boolean;
  has_hours: boolean; calls_done: number; rating: number | null; ratings: number;
  qualification: string; experience: string; /** their price for a private call (0: free) */ call_price_inr: number;
  /** a photo Focs has checked, or null (initials are shown) */ photo: string | null;
  /** your own profile: weekly call hours, India time */ slots?: { day: number; time: string }[];
  /** this student's open mentorship with them, if any */ with_me?: "requested" | "active" | null;
  /** only on your own profile */ status?: "pending" | "approved" | "rejected"; review_note?: string | null; created_at?: string | null;
  phone?: string; submitted_at?: string | null; reviewed_at?: string | null; has_proof?: boolean; price_set?: boolean;
  /** your own profile (and the admin's view): a new photo waiting for Focs to check it */ photo_pending?: string | null;
}
export interface MentorDirectory {
  exam: string | null; my_exam: string | null; exams: Record<string, string>; who: string | null; topics: Record<string, string>;
  languages: Record<string, string>; mentors: MentorCard[]; call_minutes: number; group_per_week: number; pro: boolean;
}
/** A mentor account's starting point: their application or profile (null before applying) and the form limits. */
export interface MentorWorkspace {
  profile: MentorCard | null; exams: Record<string, string>; topics: Record<string, string>; languages: Record<string, string>;
  max_capacity: number; default_call_price_inr: number; max_call_price_inr: number; max_session_price_inr: number;
  commission_pct: number; call_minutes: number; pro_sessions_per_week: number;
}
export type MentorshipStatus = "requested" | "active" | "declined" | "ended";
export interface MentorshipRow {
  id: number; role: "student" | "mentor"; status: MentorshipStatus; with: string; mentor_id: number; exam_label: string; credential: string;
  institution: string; goal: string; share_progress: boolean; created_at: string | null; accepted_at: string | null; last_message_at: string | null;
  last_checkin_at: string | null; checkin_due: boolean; unread: number; preview: string | null;
  /** the mentor's photo, when you are the student */ photo?: string | null;
}
export interface MentorshipList { as_student: MentorshipRow[]; as_mentor: MentorshipRow[]; checkins_due: number; requests: number; unread: number }
export interface MentorMessage {
  id: number; kind: "text" | "checkin"; body: string; mine: boolean; created_at: string | null;
  /** a check-in's week, as Focs saw it (shared: false when the student keeps it private) */ snapshot: (ProgressSummary | { shared: false }) | null;
}
export interface MentorshipDetail extends MentorshipRow { messages: MentorMessage[]; mentor: MentorCard; progress: ProgressSummary | null }
/** A 30-minute video call inside a mentorship: included in Pro (one a week) or paid for. */
export interface MentorCall {
  id: number; mentorship_id: number; role: "student" | "mentor"; with: string; starts_at: string; ends_at: string; minutes: number;
  status: "held" | "booked" | "done" | "cancelled"; paid_via: "pro" | "paid" | "free"; price_inr: number; agenda: string;
  snapshot: ProgressSummary | null; notes: string | null; actions: { text: string; done: boolean }[]; rating: number | null; review: string | null;
  cancelled_by: string | null; join_url: string | null; can_join: boolean; opens_at: string; over: boolean; payment_id: number | null;
  needs_notes: boolean; can_rate: boolean; refundable: boolean;
}
export interface CallSlot { starts_at: string }
export interface MentorshipCalls {
  calls: MentorCall[]; slots: CallSlot[]; has_hours: boolean; price_inr: number; minutes: number; pro: boolean;
  payments: "razorpay" | "dev" | null; mentor_share_inr: number;
}
export interface MyCalls {
  upcoming: MentorCall[]; to_rate: MentorCall[]; to_note: MentorCall[];
  actions: { call_id: number; index: number; text: string; with: string }[];
}
/** What the browser needs to open a payment: Razorpay's checkout, or a dev server's test button. */
export interface Checkout {
  payment_id: number; provider: "razorpay" | "dev"; key_id: string | null; order_id: string | null; amount_paise: number; amount_inr: number;
  currency: string; description: string; prefill: { name: string; email: string };
}
/** A mentor's master session: a live class for many students, at the mentor's price per seat (0: free). */
export interface GroupSessionInfo {
  id: number; starts_at: string; minutes: number; topic: string; description: string; price_inr: number; seats: number; taken: number;
  status: "scheduled" | "done" | "cancelled"; notes: string | null; over: boolean; can_join: boolean; join_url: string | null; opens_at: string;
}
export interface GroupSessionRow extends GroupSessionInfo {
  mentor: string; mentor_id: number; credential: string; institution: string; seated: boolean; seat_status: "held" | "booked" | null;
  paid_via: "free" | "paid" | "pro" | null; my_doubt: string | null; answered: boolean | null;
  /** a Pro student's included seat this week covers this paid session */ pro_free: boolean; week_free: boolean;
}
export interface GroupSessions { sessions: GroupSessionRow[]; pro: boolean; per_week: number; exam_label: string | null }
export interface HostedSession extends GroupSessionInfo {
  needs_marking: boolean; registered: number; earning_inr: number;
  queue: { id: number; student: string; doubt: string; answered: boolean; paid_via: "free" | "paid" | "pro" }[];
}
export interface Hosting { sessions: HostedSession[]; pay_inr: number; minutes: number; seats: number; max_seats: number; max_price_inr: number; commission_pct: number }
export interface EarningsRow { calls: number; calls_inr: number; focs_inr: number; sessions: number; sessions_inr: number; earned_inr: number; paid_out_inr: number; owed_inr: number }
export interface MentorEarnings {
  month: EarningsRow; total: EarningsRow; call_price_inr: number; commission_pct: number; call_share_inr: number; session_pay_inr: number;
  payouts: { amount_inr: number; note: string; created_at: string | null }[];
}
export interface CallMoney {
  calls_revenue_inr: number; sessions_revenue_inr: number; pro_revenue_inr: number; mocks_revenue_inr?: number; focs_share_inr: number; commission_pct: number; owed_to_mentors_inr: number;
  refunds_due: { id: number; student: string | null; amount_inr: number; purpose: string; provider_payment_id: string | null; paid_at: string | null }[];
  by_mentor: (EarningsRow & { id: number; mentor: string | null })[];
}
export interface MentorApplication extends MentorCard { email: string; has_proof: boolean }
export interface MentorReport {
  id: number; mentor: string | null; mentor_profile: number; student: string | null; status: MentorshipStatus; goal: string;
  reports: { by: string; reason: string; at: string | null }[]; messages: { from: string; body: string; kind: string; at: string | null }[];
}

export interface ClassRow { id: number; name: string; code: string; students: number }
export interface ClassList { teaching: ClassRow[]; joined: { id: number; name: string; teacher: string; joined_at: string | null }[] }
export interface ClassStudent extends ProgressSummary { user_id: number; name: string }
/** One earlier chapter that several students' root-cause traces led to. Counts only: nobody is named. */
export interface BatchRoot {
  chapter_id: string; name: string; subject: string | null; cls: number | null; idea: string;
  students: number; fixed: number; share: number; stuck_on: string[];
}
export interface BatchRoots { traced: number; with_root: number; fixed: number; roots: BatchRoot[] }
/** A ten-minute recap for the class of a gap several students share: the lesson they get, with its check question. */
export interface ClassRecap {
  chapter_id: string; name: string; cls: number | null; idea: string; stuck_on: string; students: number; md: string; check: GapCheck;
}

export interface ClassDashboard {
  id: number; name: string; code: string; students: ClassStudent[];
  weakest: { id: string; chapter: string; subject: string; students: number }[];
  roots: BatchRoots;
  totals: { students: number; active_week: number; avg_week_minutes: number; avg_syllabus: number | null };
}
export interface ParentSummary extends ProgressSummary { name: string }
export interface ParentLink { token: string | null; created_at: string | null }

/* ---------------------------------------------------------------- last-day revision */
export interface ChapterRef { id: string; name: string; subject: string; weightage: "high" | "medium" | "low" }

export interface LastDayChapter extends ChapterRef {
  minutes: number;
  /** the student's accuracy on this chapter across their tests (null: too few questions to say) */
  accuracy: number | null;
  /** percent of its topics studied */
  studied: number;
  revised_today: boolean;
  /** why it is on the list, most important first ("High weightage", "42% in your tests"…) */
  reasons: string[];
  has_capsule: boolean;
  /** the topics to revise: the ones named as coming when ``topics_chosen``; for a chapter not studied yet
      (``quick``) its most-asked ones; else all of it, the most-asked first ("only what I've studied": the studied ones) */
  topics: { id: string; name: string; done: boolean; /** papers ask it most (AI's reading of past papers) */ asked: boolean }[];
  /** how many topics the chapter has: fewer listed means the day (and its test) covers part of it */
  topic_count: number;
  topics_chosen: boolean;
  /** not studied yet: on the list for the marks it carries, its most-asked topics only */
  quick: boolean;
  /** put on today's list by the student */
  added: boolean;
  /** an open weak spot from a test */
  weak: boolean;
}

/** The test that ends the day, the latest made today. */
export interface LastDayTest {
  id: number; status: MockStatus; progress: number | null; score: number | null; max_score: number | null;
  accuracy: number | null; count: number | null;
}

export interface LastDayPlan {
  scope: "all" | "subject" | "chapters";
  subject: string | null;
  hours: number;
  hour_choices: number[];
  /** everything important in the syllabus, or only what has been studied */
  cover: "important" | "studied";
  exam_date: string | null;
  days_left: number | null;
  chapters: LastDayChapter[];
  /** next in line by marks (all of them: any can be added); ``quick``: not studied yet */
  if_time: (ChapterRef & { quick: boolean })[];
  /** chapters not studied yet: not for today ("only what I've studied") */
  leave: ChapterRef[];
  leave_count: number;
  /** chapters the student took off today's list */
  removed: ChapterRef[];
  minutes: { chapters: number; own: number; total: number };
  revised: number;
  paper_share: number;
  checklist: { id: string; text: string }[];
  own: { redo: number; cards_due: number; formulas: number; weak: number };
  subjects: string[];
  kind?: SyllabusKind;
  /** questions a final test can have, and how many minutes each size runs */
  test_sizes: number[];
  test_minutes: Record<string, number>;
  final_test: LastDayTest | null;
}

/* ---------------------------------------------------------------- weak spots (from tests taken anywhere) */
export interface WeakCheck { at: string; kind: "practice" | "chapter_test" | "self"; correct: number; total: number }

export interface WeakSpot {
  id: number;
  status: "open" | "cleared";
  /** questions lost on it, across tests */
  misses: number;
  note: string | null;
  chapter: { id: string; name: string; subject: string };
  /** null: the chapter as a whole */
  topic: { id: string; name: string } | null;
  test: { id: number; title: string } | null;
  last_check: WeakCheck | null;
  checks: number;
  notes_ready: boolean;
  cleared_at: string | null;
}

export interface OutsideTest {
  id: number;
  title: string;
  taken_on: string | null;
  score: number | null;
  max_score: number | null;
  subjects: { name: string; score: number | null; max: number | null }[];
  source: "upload" | "manual";
  created_at: string | null;
  weak: number;
}

export interface WeakOverview {
  /** how an uploaded result would be read right now */
  reader: "vision" | "ocr" | "none";
  open: WeakSpot[];
  cleared: WeakSpot[];
  tests: OutsideTest[];
  limits: { files: number; clear_percent: number; clear_min: number };
}

/** One weak topic in a draft or a new test: where it sits in the syllabus and how many questions it cost. */
export interface WeakDraftItem {
  chapter_id: string;
  chapter: string;
  subject: string;
  topic_id: string | null;
  topic: string | null;
  misses: number;
  note: string | null;
}

/** What Focs read from an uploaded result, for the student to check before it is saved. */
export interface WeakDraft {
  title: string | null;
  score: number | null;
  max_score: number | null;
  subjects: { name: string; score: number | null; max: number | null }[];
  weak: WeakDraftItem[];
  /** wrong questions that couldn't be placed in the syllabus */
  unplaced: string[];
  questions_read: number;
  wrong_read: number;
  read_by: "vision" | "ocr";
}

export interface WeakCheckResult { weak: boolean; cleared: boolean; percent: number; needed: number; enough_questions: boolean }

/* ---------------------------------------------------------------- Root-cause gap tracing */
export interface GapCheck { q: string; options: string[]; answer?: number; explain?: string }
export interface GapLink {
  chapter_id: string; name: string; subject: string; cls: number | null; idea: string; why: string;
  check: GapCheck; result: "right" | "wrong" | null; choice?: number | null;
}
/** Questions on the stuck topic itself (from the question bank): three before the trace, three others after the fix. */
export interface GapRetestPart { items: GapCheck[]; choices: (number | null)[] | null; right: number | null; total: number }
export interface GapTrace {
  id: number; title: string; chapter_id: string; topic_id: string | null; status: "checking" | "found" | "clear" | "fixed";
  root: number | null; chain: GapLink[]; lesson: { md: string; check: GapCheck; result: "right" | "wrong" | null; choice?: number | null } | null;
  retest: { before: GapRetestPart; after: GapRetestPart } | null;
  created_at: string | null;
}
export interface GapOverview {
  traces: GapTrace[]; fixed: number;
  suggestions: { chapter_id: string; topic_id: string | null; subject: string; name: string; chapter: string; misses: number }[];
  /** likely root gaps, from weak spots alone: two or more weak chapters resting on the same earlier one */
  suspects?: { chapter_id: string; name: string; subject: string | null; cls: number | null; idea: string;
    because: string[]; misses: number; trace_chapter_id: string }[];
  chapters: { id: string; subject: string; name: string; cls: number }[];
}

/* ---------------------------------------------------------------- Check my working, and the tutor */
export type WorkingError = "arithmetic" | "sign" | "units" | "misread" | "formula" | "setup" | "concept" | "algebra" | "incomplete";
/** How a student loses marks, from their checked rough work: careless slips, or gaps in ideas. */
export interface MistakeFingerprint {
  checked: number; right: number; mistakes: number; slips: number; gaps: number; careless_share: number | null;
  kinds: { type: WorkingError; label: string; count: number; careless: boolean }[];
}
/** One page of rough work, read and checked: the first wrong step, what kind of slip, and the root it comes from. */
export interface WorkingCheck {
  id: number; question: string; verdict: "right" | "wrong" | "incomplete";
  steps: { text: string; ok: boolean }[]; first_wrong: number | null;
  error_type: WorkingError | null; error_label: string | null; careless: boolean;
  what_went_wrong: string | null; hint: string | null; fix: string | null;
  root: { chapter_id: string; name: string; subject: string | null; cls: number | null; idea: string } | null;
  earlier_idea: string | null; chapter: { id: string; name: string; subject: string } | null; has_chain: boolean;
  again: { times: number; trace: { id: number; status: GapTrace["status"] } | null } | null;
  fingerprint: MistakeFingerprint; created_at: string | null;
}
export interface TutorTurn { role: "user" | "assistant"; content: string }
