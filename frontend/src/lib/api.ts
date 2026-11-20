import { useAdmin } from "@/stores/admin";
import { useAuth } from "@/stores/auth";
import type {
  Language, GapOverview, GapTrace, ClassRecap, MistakeFingerprint, TutorTurn, WorkingCheck,
  MockOffer,
  CardStats, Checkpoint, Doubt, Evaluation, Flashcard, FrameResponse, Grade, Health, HealthDetails, ModelInfo, Note, OcrResult,
  Feeling, MockDetail, MockMeta, Warmup, MockResponse, MockSummary, Overview, PlansInfo, PriceSector, ProPass, Quiz, RedoItem, Room, SessionDetail, SessionEnd,
  AdminOverview, AdminUser, ConfusionReport, WaitTask, AskVerification, NotificationItem, FormulaSubject, Leaderboard, StudySession, TokenResponse, LoginCode, Usage, User,
  AskBoard, AskPost, AudioResult, ClipResult, Calibration, TalkSummary, CallMoney, LectureSegment, Checkout, EarningsRow, GroupSessionInfo, GroupSessions, Hosting, MentorEarnings, CollegeSetup, CampusItem, MentorCall, MentorshipCalls, MyCalls, MentorApplication, MentorCard, MentorDirectory, MentorWorkspace, MentorMessage, MentorReport, MentorshipDetail, MentorshipList, MentorshipRow, CampusQuestions, CampusShelf, ClassDashboard, ClassList, ClassRow, ParentLink, ParentSummary, DetailedNotes, LastDayPlan, MarkedAnswer, SolvedDoubt, PrepOptions, StudyGoal, WeakCheckResult, WeakDraft, WeakOverview, StudyPlan, SyllabusChapter, SyllabusTree, TodayPlan, TopicDetail,
} from "./types";

const FIELD_LABELS: Record<string, string> = { full_name: "Name", email: "Email", password: "Password", exam_target: "Exam", college: "College", title: "Title", name: "Name" };

/** A server validation error in words a student can act on ("Name can't be empty", not "full_name: String should have at least 1 character"). */
function validationMessage(field: string, d: { type?: string; msg?: string; ctx?: { min_length?: number; max_length?: number } }): string {
  const label = FIELD_LABELS[field] ?? (field ? field.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) : "This");
  if (d.type === "string_too_short") return d.ctx?.min_length && d.ctx.min_length > 1 ? `${label} needs at least ${d.ctx.min_length} characters.` : `${label} can't be empty.`;
  if (d.type === "string_too_long") return `${label} is too long${d.ctx?.max_length ? ` (at most ${d.ctx.max_length} characters)` : ""}.`;
  if (d.type === "missing") return `${label} is required.`;
  return `${field ? `${label}: ` : ""}${String(d.msg ?? "Check this field").replace(/^Value error, /, "")}`;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Body = Record<string, unknown> | FormData | undefined;

const GET_TIMEOUT_MS = 25_000;

async function request<T>(method: string, path: string, body?: Body, opts: { raw?: boolean; admin?: boolean } = {}): Promise<T> {
  // the admin panel has its own session; student calls never carry it and vice versa
  const token = opts.admin ? useAdmin.getState().token : useAuth.getState().token;
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  // A read that hangs on a weak connection gives up after a while, so the page can show its saved copy and retry.
  // Writes (AI answers, uploads) can take far longer on purpose and are left to finish.
  const stop = method === "GET" ? new AbortController() : null;
  const timer = stop ? setTimeout(() => stop.abort(), GET_TIMEOUT_MS) : undefined;
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method, headers, body: payload, signal: stop?.signal });
  } catch {
    throw new ApiError(0, typeof navigator !== "undefined" && !navigator.onLine
      ? "You're offline. Showing what's saved on this device; it updates when you're back online."
      : stop?.signal.aborted ? "The connection is too slow right now. Trying again shortly."
      : "Can't reach the Focs server. Check your connection and try again.");
  } finally {
    clearTimeout(timer);
  }

  if (res.status === 401 && token && opts.admin) {
    useAdmin.getState().signOut();
    throw new ApiError(401, "Your admin session ended. Please sign in again.");
  }
  if (res.status === 401 && token && !opts.admin) {
    // a call sent with a token that has since been replaced (a password change hands out a new one) is
    // just stale: send it again with the new token instead of signing the student out
    const now = useAuth.getState().token;
    if (now && now !== token) return request<T>(method, path, body, opts);
    useAuth.getState().logout();
    throw new ApiError(401, "Your session expired. Please sign in again.");
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]?.msg) {
        const d = data.detail[0];
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : "";
        message = validationMessage(String(field), d);
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  if (opts.raw) return res as unknown as T;
  return res.json() as Promise<T>;
}

const get = <T,>(p: string) => request<T>("GET", p);
const post = <T,>(p: string, b?: Body) => request<T>("POST", p, b);
const patch = <T,>(p: string, b?: Body) => request<T>("PATCH", p, b);
const del = (p: string) => request<void>("DELETE", p);

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const s = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && s.set(k, String(v)));
  const str = s.toString();
  return str ? `?${str}` : "";
};

const tz = () => `tz_offset=${-new Date().getTimezoneOffset()}`;

/** Last-day revision: what tomorrow covers and how the student has shaped the day. */
export type LastDayBody = {
  hours: number; subject?: string; chapters: string[]; topics: string[]; include: string[]; exclude: string[];
  cover: "important" | "studied";
};

export const api = {
  health: () => get<Health>("/health"),
  healthDetails: () => get<HealthDetails>("/health/details"),

  // prep hub & mentor plan (days are the student's local days)
  prepOptions: () => get<PrepOptions>(`/prep/options?${tz()}`),
  prepGoal: () => get<StudyGoal | null>("/prep/goal"),
  setPrepGoal: (b: Omit<StudyGoal, "exam"> & { apply_standing?: boolean }) => request<StudyPlan>("PUT", `/prep/goal?${tz()}`, b),
  resetPrepGoal: () => del("/prep/goal"),
  prepPlan: () => get<StudyPlan | null>(`/prep/plan?${tz()}`),
  /** college: `semester` shows the courses the plan puts in that semester instead of the student's own subjects */
  prepSyllabus: (exam?: string, semester?: number | null) =>
    get<SyllabusTree>(`/prep/syllabus?${tz()}${exam ? `&exam=${exam}` : ""}${semester ? `&semester=${semester}` : ""}`),
  // college students: where they study, their semester and the subjects they take in it
  prepCollege: (college?: string | null, semester?: number | null) => get<CollegeSetup>(`/prep/college${qs({ college, semester })}`),
  /** Class 11/12: the subjects the student has */
  setPrepSubjects: (subjects: string[]) => request<{ subjects: string[]; all: string[] }>("PUT", "/prep/subjects", { subjects }),
  setPrepCollege: (b: { college: string; semester: number; subjects: string[] | null }) => request<CollegeSetup>("PUT", "/prep/college", b),
  setTopicDone: (topicId: string, done: boolean) => request<SyllabusChapter>("PUT", `/prep/topics/${encodeURIComponent(topicId)}?${tz()}`, { done }),
  setRevised: (chapterId: string, done: boolean) =>
    request<SyllabusChapter>("PUT", `/prep/chapters/${encodeURIComponent(chapterId)}/revision?${tz()}`, { done }),
  checkTask: (key: string, done: boolean) => request<TodayPlan>("PUT", `/prep/today/${encodeURIComponent(key)}?${tz()}`, { done }),
  // editing the plan: hours / exam date / goal in place, the order of chapters, and today's list
  editPlan: (b: { weekday_hours?: number; weekend_hours?: number; day_hours?: number[]; exam_date?: string; target?: string; dream?: string }) =>
    patch<StudyPlan>(`/prep/plan?${tz()}`, b),
  editPlanChapter: (chapterId: string, action: "next" | "unpin" | "skip" | "restore") =>
    request<StudyPlan>("PUT", `/prep/plan/chapters/${encodeURIComponent(chapterId)}?${tz()}`, { action }),
  addTask: (b: { title: string; minutes: number }) => post<TodayPlan>(`/prep/today/tasks?${tz()}`, b),
  removeTask: (id: number) => request<TodayPlan>("DELETE", `/prep/today/tasks/${id}?${tz()}`),
  hideTask: (key: string, hidden: boolean) => request<TodayPlan>("PUT", `/prep/today-hidden/${encodeURIComponent(key)}?${tz()}`, { done: hidden }),
  topicDetail: (topicId: string) => get<TopicDetail>(`/prep/topics/${encodeURIComponent(topicId)}`),
  topicNotes: (topicId: string) => post<DetailedNotes>(`/prep/topics/${encodeURIComponent(topicId)}/notes`),
  reportTopicNotes: (topicId: string) => post<void>(`/prep/topics/${encodeURIComponent(topicId)}/notes/report`),

  // last-day revision
  lastDay: (b: LastDayBody) => post<LastDayPlan>(`/prep/last-day?${tz()}`, b),
  /** the test that ends the day: only the chapters (and topics) on the list these choices lay out */
  lastDayTest: (b: LastDayBody & { count: number }) => post<{ id: number; status: string; title: string }>(`/prep/last-day/test?${tz()}`, b),
  chapterCapsule: (chapterId: string) => post<DetailedNotes>(`/prep/chapters/${encodeURIComponent(chapterId)}/capsule`),

  // root-cause gap tracing: the earlier gap behind a topic, found and fixed
  gaps: () => get<GapOverview>("/gaps"),
  genome: () => get<Genome>("/gaps/genome"),
  gapStart: (chapter_id: string, topic_id?: string | null) => post<GapTrace>("/gaps", { chapter_id, topic_id: topic_id ?? null }),
  gap: (id: number) => get<GapTrace>(`/gaps/${id}`),
  gapAnswers: (id: number, answers: (number | null)[], before?: (number | null)[]) => post<GapTrace>(`/gaps/${id}/answers`, { answers, before }),
  gapAfter: (id: number, answers: (number | null)[]) => post<GapTrace>(`/gaps/${id}/after`, { answers }),
  gapLesson: (id: number) => post<GapTrace>(`/gaps/${id}/lesson`),
  gapCheck: (id: number, choice: number) => post<GapTrace>(`/gaps/${id}/check`, { choice }),

  // Check my working: a page of rough work read step by step; the tutor that knows the student
  checkWorking: (image: Blob, q: { question: string; options?: string[] | null; answer?: number | null; chosen?: number | null;
    chapterId?: string | null; topic?: string | null; subject?: string | null; solution?: string | null }) => {
    const fd = new FormData();
    fd.append("image", image, "rough.png");
    fd.append("question", q.question.slice(0, 2000));
    fd.append("options", JSON.stringify(q.options ?? []));
    if (q.answer != null) fd.append("answer", String(q.answer));
    if (q.chosen != null) fd.append("chosen", String(q.chosen));
    if (q.chapterId) fd.append("chapter_id", q.chapterId);
    if (q.topic) fd.append("topic", q.topic.slice(0, 200));
    if (q.subject) fd.append("subject", q.subject.slice(0, 80));
    if (q.solution) fd.append("solution", q.solution.slice(0, 6000));
    return post<WorkingCheck>("/working/check", fd);
  },
  workingFingerprint: () => get<MistakeFingerprint>("/working/fingerprint"),
  tutor: (b: { question: string; history: TutorTurn[]; check_id?: number | null; chapter_id?: string | null }) => post<{ answer: string }>("/working/tutor", b),

  // weak spots: the result of a test taken anywhere, read and turned into a fix-it plan
  weak: () => get<WeakOverview>("/weak"),
  weakRead: (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    return post<WeakDraft>("/weak/read", fd);
  },
  weakAddTest: (b: { title: string; taken_on?: string; score?: number; max_score?: number; source: "upload" | "manual";
    subjects: { name: string; score: number | null; max: number | null }[];
    weak: { chapter_id: string; topic_id: string | null; misses: number; note?: string | null }[] }) => post<WeakOverview>("/weak/tests", b),
  weakRemoveTest: (id: number) => request<WeakOverview>("DELETE", `/weak/tests/${id}`),
  weakSetStatus: (id: number, status: "open" | "cleared") => patch<WeakOverview>(`/weak/${id}`, { status }),
  /** a practice set on a topic was finished: if the topic is a weak spot, this is its re-check */
  weakCheck: (topic_id: string, correct: number, total: number) => post<WeakCheckResult>("/weak/check", { topic_id, correct, total }),

  // auth
  register: (b: { email: string; full_name: string; password: string; exam_target?: string; class_level?: string; accepted_terms?: boolean; role?: "student" | "mentor";
    college?: string; semester?: number }) =>
    post<TokenResponse | LoginCode>("/auth/register", b),
  login: (b: { email: string; password: string }) => post<TokenResponse | LoginCode>("/auth/login", b),
  loginVerify: (b: { challenge: string; code: string }) => post<TokenResponse>("/auth/login/verify", b),
  loginResend: (challenge: string) => post<LoginCode>("/auth/login/resend", { challenge }),
  google: (b: { credential: string; accepted_terms?: boolean; exam_target?: string; college?: string }) =>
    post<TokenResponse>("/auth/google", b),
  forgotPassword: (email: string) => post<void>("/auth/forgot-password", { email }),
  resetPassword: (token: string, new_password: string) => post<void>("/auth/reset-password", { token, new_password }),
  me: () => get<User>("/auth/me"),
  updateMe: (b: Partial<Pick<User, "full_name" | "exam_target" | "class_level" | "daily_goal_min" | "show_on_leaderboard" | "college" | "semester" | "language">>) =>
    patch<User>("/auth/me", b),
  // the old token stops working the moment this returns: swap in the new one before anything else (the app-wide
  // "refresh usage after a write" runs before the caller's onSuccess and would otherwise sign the student out)
  changePassword: async (b: { current_password: string; new_password: string }) => {
    const r = await post<TokenResponse>("/auth/change-password", b);
    useAuth.getState().setAuth(r.access_token, r.user);
    return r;
  },
  exportData: () => request<Response>("GET", "/auth/export", undefined, { raw: true }),
  deleteAccount: (b: { password: string; confirm: string }) => post<void>("/auth/delete-account", b),

  // sessions
  startSession: (b: { title?: string; subject?: string; source?: string; video_url?: string }) => post<StudySession>("/sessions", b),
  sessions: (p: { limit?: number; offset?: number } = {}) => get<StudySession[]>(`/sessions${qs(p)}`),
  activeSession: () => get<StudySession | null>("/sessions/active"),
  session: (id: number) => get<SessionDetail>(`/sessions/${id}`),
  updateSession: (id: number, b: { title?: string; subject?: string }) => patch<StudySession>(`/sessions/${id}`, b),
  endSession: (id: number) => post<SessionEnd>(`/sessions/${id}/end`),
  sessionPopQuiz: (id: number) => post<Checkpoint>(`/sessions/${id}/pop-quiz`),
  deleteSession: (id: number) => del(`/sessions/${id}`),
  exportSession: (id: number) => request<Response>("GET", `/sessions/${id}/export`, undefined, { raw: true }),

  // capture
  sendFrame: (sessionId: number, frame: Blob, force = false, extra: { corners?: [number, number][]; camera?: boolean } = {}) => {
    const fd = new FormData();
    fd.append("frame", frame, "frame.jpg");
    fd.append("force", String(force));
    if (extra.camera) fd.append("camera", "true");
    if (extra.corners) fd.append("corners", JSON.stringify(extra.corners.map(([x, y]) => [+x.toFixed(4), +y.toFixed(4)])));
    return post<FrameResponse>(`/capture/${sessionId}/frame`, fd);
  },
  /** a piece of the lecture's sound (the voice lane): transcribed and dropped on the server */
  sendAudio: (sessionId: number, piece: Blob, startS: number, endS: number) => {
    const fd = new FormData();
    fd.append("audio", piece, "lecture.webm");
    fd.append("start_s", startS.toFixed(1));
    fd.append("end_s", endS.toFixed(1));
    return post<AudioResult>(`/capture/${sessionId}/audio`, fd);
  },
  transcript: (sessionId: number) => get<{ segments: LectureSegment[]; available: boolean }>(`/capture/${sessionId}/transcript`),
  /** written (and kept) the first time it's asked for, and again only after more speech came in */
  talkSummary: (sessionId: number) => post<TalkSummary>(`/capture/${sessionId}/transcript/summary`),
  /** lecture by link: the stretch of the YouTube lecture just watched, written up as one note */
  sendClip: (sessionId: number, startS: number, endS: number) =>
    post<ClipResult>(`/capture/${sessionId}/clip`, { start_s: +startS.toFixed(1), end_s: +endS.toFixed(1) }),
  /** the board stopped changing: write up the version the teacher finished */
  settleBoard: (sessionId: number) => post<FrameResponse>(`/capture/${sessionId}/settle`),
  sendPhoto: (photo: File | Blob, sessionId?: number) => {
    const fd = new FormData();
    fd.append("photo", photo, photo instanceof File ? photo.name : "photo.jpg");
    if (sessionId) fd.append("session_id", String(sessionId));
    return post<FrameResponse>("/capture/photo", fd);
  },

  // notes
  notes: (p: { q?: string; session_id?: number; subject?: string; pinned?: boolean; limit?: number; offset?: number } = {}) =>
    get<{ items: Note[]; total: number }>(`/notes${qs(p)}`),
  updateNote: (id: number, b: { ai_notes?: string; topic?: string; is_pinned?: boolean }) => patch<Note>(`/notes/${id}`, b),
  regenerateNote: (id: number) => post<Note>(`/notes/${id}/regenerate`),
  noteDetailed: (id: number) => post<DetailedNotes>(`/notes/${id}/detailed`),
  deleteNote: (id: number) => del(`/notes/${id}`),
  noteImage: (id: number) => request<Response>("GET", `/notes/${id}/image`, undefined, { raw: true }),

  // companion
  ask: (b: { question: string; session_id?: number; note_id?: number; mode: string; history: { role: string; content: string }[] }) =>
    post<{ id: number | null; answer: string; source: string }>("/companion/ask", b),
  doubts: (sessionId?: number) => get<Doubt[]>(`/companion/history${qs({ session_id: sessionId })}`),

  // confidence vs reality
  calibration: (p: { session_id?: number; days?: number } = {}) => get<Calibration>(`/analytics/calibration${qs(p)}`),
  // quiz
  generateQuiz: (b: { session_id?: number; text?: string; topic_id?: string; difficulty: string; n_mcq: number; n_tf: number; n_subjective: number }) =>
    post<Quiz>("/quiz/generate", b),
  attempt: (b: { question: string; q_type: string; correct: boolean; topic?: string; subject?: string; session_id?: number | null; score?: number;
    confidence?: "sure" | "unsure" | null }) =>
    post<{ id: number; needs_redo: boolean }>("/quiz/attempt", b),
  evaluate: (b: { question: string; student_answer: string; key_points: string[]; model_answer: string; topic?: string; subject?: string; session_id?: number | null }) =>
    post<Evaluation>("/quiz/evaluate", b),
  /** a written answer sent as a photo: read, then graded like a typed one */
  evaluatePhoto: (b: { question: string; key_points: string[]; model_answer: string; topic?: string; subject?: string; session_id?: number | null }, photo: File) => {
    const fd = new FormData();
    fd.append("question", b.question);
    fd.append("key_points", JSON.stringify(b.key_points));
    fd.append("model_answer", b.model_answer);
    if (b.topic) fd.append("topic", b.topic);
    if (b.subject) fd.append("subject", b.subject);
    if (b.session_id) fd.append("session_id", String(b.session_id));
    fd.append("files", photo, photo.name || "answer.jpg");
    return post<Evaluation>("/quiz/evaluate-photo", fd);
  },
  /** a topic explained back in the student's own words, checked against the lecture's boards or the library note */
  teachBack: (b: { topic: string; answer: string; topic_id?: string; session_id?: number; subject?: string }) => post<Evaluation>("/quiz/teach-back", b),
  redo: () => get<RedoItem[]>("/quiz/redo"),
  redoDone: (id: number) => post<void>(`/quiz/redo/${id}/done`),

  // spoken answers (only for browsers that can't dictate themselves)
  speechStatus: () => get<{ server: boolean }>("/speech/status"),
  transcribe: (audio: Blob, language: string, hint?: string) => {
    const fd = new FormData();
    fd.append("audio", audio, `answer.${audio.type.includes("mp4") ? "m4a" : "webm"}`);
    fd.append("language", language);
    if (hint) fd.append("hint", hint.slice(0, 400));
    return post<{ text: string }>("/speech/transcribe", fd);
  },

  // campus: past papers and notes shared by students of the same courses
  campus: (p: { subject?: string; kind?: string; scope?: string }) => get<CampusShelf>(`/campus${qs(p)}`),
  campusShare: (b: { file: File; kind: string; subject: string; title: string; year?: number; exam_kind?: string }) => {
    const fd = new FormData();
    fd.append("file", b.file, b.file.name);
    fd.append("kind", b.kind); fd.append("subject", b.subject); fd.append("title", b.title);
    if (b.year) fd.append("year", String(b.year));
    if (b.exam_kind) fd.append("exam_kind", b.exam_kind);
    return post<CampusItem>("/campus", fd);
  },
  /** the shared file, as a link this tab can open */
  campusFile: async (id: number) => URL.createObjectURL(await (await request<Response>("GET", `/campus/${id}/file`, undefined, { raw: true })).blob()),
  /** one page of it as a picture (the app shows these: it cannot display a PDF) */
  campusPage: async (id: number, page: number) => URL.createObjectURL(await (await request<Response>("GET", `/campus/${id}/page/${page}`, undefined, { raw: true })).blob()),
  campusVote: (id: number) => post<{ votes: number; voted: boolean }>(`/campus/${id}/vote`),
  campusReport: (id: number) => post<void>(`/campus/${id}/report`),
  campusRemove: (id: number) => del(`/campus/${id}`),
  campusQuestions: (id: number) => post<CampusQuestions>(`/campus/${id}/questions`),
  // mentors: people who cleared the exam, guiding students week after week
  mentors: (exam?: string) => get<MentorDirectory>(`/mentors${qs({ exam })}`),
  // a mentor account: its application (proof can be left out when resending a waiting one) and profile
  mentorWorkspace: () => get<MentorWorkspace>("/mentors/me"),
  mentorApply: (b: Record<string, string | number>, proof: File | null) => {
    const fd = new FormData();
    Object.entries(b).forEach(([k, v]) => fd.append(k, String(v)));
    if (proof) fd.append("proof", proof);
    return post<MentorCard>("/mentors/apply", fd);
  },
  mentorEdit: (b: Partial<Pick<MentorCard, "headline" | "about" | "topics" | "languages" | "capacity" | "accepting" | "call_price_inr">>) => request<MentorCard>("PATCH", "/mentors/me", b),
  mentorPhoto: (photo: File) => { const fd = new FormData(); fd.append("photo", photo); return post<MentorCard>("/mentors/me/photo", fd); },
  mentorPhotoRemove: () => request<MentorCard>("DELETE", "/mentors/me/photo"),
  mentorRequest: (id: number, b: { goal: string; share_progress: boolean }) => post<MentorshipRow>(`/mentors/${id}/request`, b),
  mentorships: () => get<MentorshipList>("/mentors/mentorships"),
  mentorship: (id: number) => get<MentorshipDetail>(`/mentors/mentorships/${id}`),
  mentorSend: (id: number, b: { body: string; checkin?: boolean }) => post<MentorMessage>(`/mentors/mentorships/${id}/messages`, b),
  mentorDecide: (id: number, to: "accept" | "decline" | "end") => post<MentorshipRow>(`/mentors/mentorships/${id}/${to}`),
  mentorShare: (id: number, share_progress: boolean) => request<MentorshipRow>("PATCH", `/mentors/mentorships/${id}`, { share_progress }),
  mentorReport: (id: number, reason: string) => post<void>(`/mentors/mentorships/${id}/report`, { reason }),
  // mentor calls
  mentorSlots: (slots: { day: number; time: string }[]) => request<{ slots: { day: number; time: string }[] }>("PUT", "/mentors/me/slots", { slots }),
  mentorshipCalls: (id: number) => get<MentorshipCalls>(`/mentors/mentorships/${id}/calls`),
  bookCall: (id: number, b: { starts_at: string; agenda: string }) => post<{ call: MentorCall; checkout: Checkout | null }>(`/mentors/mentorships/${id}/calls`, b),
  myCalls: () => get<MyCalls>("/mentors/calls"),
  // group doubt sessions (Pro)
  groupSessions: () => get<GroupSessions>("/mentors/sessions"),
  takeSeat: (id: number, doubt: string) => post<{ session_id: number; seated: boolean; seat_status: string; paid_via: string; my_doubt: string; checkout: Checkout | null }>(`/mentors/sessions/${id}/seat`, { doubt }),
  leaveSeat: (id: number) => del(`/mentors/sessions/${id}/seat`),
  hosting: () => get<Hosting>("/mentors/me/sessions"),
  scheduleSessions: (b: { starts_at: string; topic: string; description?: string; minutes?: number; seats?: number; price_inr?: number; repeat_weeks: number }) =>
    post<GroupSessionInfo[]>("/mentors/me/sessions", b),
  markAnswered: (id: number, seat: number, answered: boolean) => request<{ id: number; answered: boolean }>("PUT", `/mentors/sessions/${id}/queue/${seat}`, { answered }),
  markHeld: (id: number, notes: string) => post<GroupSessionInfo>(`/mentors/sessions/${id}/held`, { notes }),
  cancelSession: (id: number) => post<GroupSessionInfo>(`/mentors/sessions/${id}/cancel`),
  myEarnings: () => get<MentorEarnings>("/mentors/me/earnings"),
  cancelCall: (id: number) => post<MentorCall>(`/mentors/calls/${id}/cancel`),
  callNotes: (id: number, b: { notes: string; actions: string[] }) => post<MentorCall>(`/mentors/calls/${id}/notes`, b),
  tickAction: (id: number, index: number, done: boolean) => request<MentorCall>("PUT", `/mentors/calls/${id}/actions/${index}`, { done }),
  rateCall: (id: number, b: { rating: number; review: string }) => post<MentorCall>(`/mentors/calls/${id}/rate`, b),
  // ask a senior: questions, answers and tips about a course
  askBoard: (p: { subject?: string; scope?: string }) => get<AskBoard>(`/campus/ask${qs(p)}`),
  askPost: (b: { subject: string; kind: "question" | "tip"; body: string; chapter?: string | null }) => post<AskPost>("/campus/ask", b),
  askAnswer: (id: number, body: string) => post<AskPost>(`/campus/ask/${id}/answers`, { body }),
  askVote: (id: number) => post<{ votes: number; voted: boolean }>(`/campus/ask/${id}/vote`),
  askReport: (id: number) => post<void>(`/campus/ask/${id}/report`),
  askRemove: (id: number) => del(`/campus/ask/${id}`),
  askCheck: (id: number, verdict: "right" | "fix", correction?: string) => post<AskPost>(`/campus/ask/${id}/check`, { verdict, correction }),
  askAccept: (id: number) => post<{ accepted: boolean }>(`/campus/ask/${id}/accept`),
  askVerifyStart: (email: string) => post<{ sent: boolean; dev_code?: string }>("/campus/ask/verify/start", { email }),
  askVerifyConfirm: (code: string) => post<AskVerification>("/campus/ask/verify/confirm", { code }),
  // the bell
  notifications: () => get<{ unread: number; items: NotificationItem[] }>("/notifications"),
  notificationsRead: () => post<void>("/notifications/read"),

  // classes (a teacher sees a class's progress) and the parent link (a parent sees one child's)
  classes: () => get<ClassList>("/classes"),
  createClass: (name: string) => post<ClassRow>("/classes", { name }),
  joinClass: (code: string) => post<{ id: number; name: string; teacher: string }>("/classes/join", { code }),
  classRecap: (id: number, chapterId: string) => post<ClassRecap>(`/classes/${id}/recap`, { chapter_id: chapterId }),
  classDashboard: (id: number) => get<ClassDashboard>(`/classes/${id}`),
  removeClass: (id: number) => del(`/classes/${id}`),
  removeClassStudent: (id: number, userId: number) => del(`/classes/${id}/students/${userId}`),
  leaveClass: (id: number) => post<void>(`/classes/${id}/leave`),
  parentLink: () => get<ParentLink>("/parent/link"),
  makeParentLink: () => post<ParentLink>("/parent/link"),
  revokeParentLink: () => del("/parent/link"),
  parentView: (token: string) => get<ParentSummary>(`/parent/view/${encodeURIComponent(token)}`),

  // ask with a photo: a snapped question solved, a handwritten answer marked
  snapDoubt: (files: File[], note: string) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    fd.append("note", note);
    return post<SolvedDoubt>("/snap/doubt", fd);
  },
  explainDoubt: (id: number, language: Exclude<Language, "en">) =>
    post<{ language: string; solution: string }>(`/snap/doubt/${id}/explain`, { language }),
  snapAnswer: (files: File[], question: string, maxMarks: number) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    fd.append("question", question);
    fd.append("max_marks", String(maxMarks));
    return post<MarkedAnswer>("/snap/answer", fd);
  },

  // flashcards
  cards: (p: { due?: boolean; session_id?: number } = {}) => get<Flashcard[]>(`/flashcards${qs(p)}`),
  cardStats: () => get<CardStats>("/flashcards/stats"),
  createCard: (b: { front: string; back: string; topic?: string }) => post<Flashcard>("/flashcards", b),
  generateCards: (b: { note_id?: number; session_id?: number; count?: number }) => post<Flashcard[]>("/flashcards/generate", b),
  reviewCard: (id: number, grade: Grade) => post<Flashcard>(`/flashcards/${id}/review`, { grade }),
  deleteCard: (id: number) => del(`/flashcards/${id}`),

  // analytics
  focusHeartbeat: (activity: string, tz_offset: number) => post<void>("/analytics/heartbeat", { activity, tz_offset }),
  refreshToken: () => post<TokenResponse>("/auth/refresh"),
  overview: () => get<Overview>(`/analytics/overview${qs({ tz_offset: -new Date().getTimezoneOffset() })}`),

  // rooms
  createRoom: (b: { name: string; video_url?: string; topic?: string }) => post<Room>("/rooms", b),
  roomQuiz: (code: string, seconds = 30, noteId?: number) => post<{ id: string; source: string }>(`/rooms/${code}/quiz`, { seconds, note_id: noteId }),
  /** the host's confusion map: which boards lost the room (counts only, never names) */
  /** one small task from the student's own material, while the AI works */
  waitTask: (topic: string, skip = "") => get<WaitTask>(`/wait/task${qs({ topic, skip })}`),
  roomReport: (code: string) => get<ConfusionReport>(`/rooms/${code}/report`),
  roomRecap: (code: string, noteId: number) => post<{ ok: boolean }>(`/rooms/${code}/recap`, { note_id: noteId }),
  roomAsk: (code: string, question: string, doubtId?: string) => post<{ ok: boolean }>(`/rooms/${code}/ask`, { question, doubt_id: doubtId }),
  roomNotes: (code: string) => get<Note[]>(`/rooms/${code}/notes`),
  startRoomNotes: (code: string, takeOver = false) => post<{ session_id: number }>(`/rooms/${code}/notes/start`, { take_over: takeOver }),
  stopRoomNotes: (code: string) => post<void>(`/rooms/${code}/notes/stop`),
  saveRoomNotes: (code: string) => post<{ session_id: number; notes: number }>(`/rooms/${code}/notes/save`),
  myRooms: () => get<Room[]>("/rooms"),
  joinRoom: (code: string) => post<Room>("/rooms/join", { code }),
  closeRoom: (code: string) => post<void>(`/rooms/${code}/close`),

  // ocr lab
  ocrModel: () => get<ModelInfo>("/ocr/model"),
  runOcr: (image: Blob, engine: string) => {
    const fd = new FormData();
    fd.append("image", image, image instanceof File ? image.name : "image.png");
    fd.append("engine", engine);
    return post<OcrResult>("/ocr/run", fd);
  },

  // billing & allowance
  /** the plans for one kind of student; left out, the signed-in student's own (else JEE / NEET) */
  plans: (sector?: PriceSector) => get<PlansInfo>(`/billing/plans${qs({ sector })}`),
  buyPro: (plan: ProPass["id"] = "month") => post<Checkout>(`/billing/pro${qs({ plan })}`),
  /** full mock tests without Pro: one, or a pack */
  buyMocks: (pack: MockOffer["id"]) => post<Checkout>(`/billing/mocks${qs({ pack })}`),
  confirmPayment: (id: number, b: { razorpay_order_id?: string; razorpay_payment_id?: string; razorpay_signature?: string }) =>
    post<{ status: string; purpose: string; user: User }>(`/billing/payments/${id}/confirm`, b),
  devUpgrade: (plan: string) => post<User>("/billing/dev-upgrade", { plan }),
  usage: () => get<Usage>("/usage"),
  adminLogin: (username: string, password: string) =>
    request<{ token: string; username: string; expires_in: number }>("POST", "/admin/login", { username, password }, { admin: true }),
  adminOverview: () => request<AdminOverview>("GET", "/admin/overview", undefined, { admin: true }),
  adminMentors: (status = "pending") => request<MentorApplication[]>("GET", `/admin/mentors?status=${status}`, undefined, { admin: true }),
  adminMentorProof: async (id: number) => URL.createObjectURL(await (await request<Response>("GET", `/admin/mentors/${id}/proof`, undefined, { admin: true, raw: true })).blob()),
  adminMentorReview: (id: number, approve: boolean, note = "") => request<{ id: number; status: string }>("POST", `/admin/mentors/${id}/review`, { approve, note }, { admin: true }),
  adminMentorPhoto: (id: number, approve: boolean, note = "") => request<{ id: number; photo: string | null }>("POST", `/admin/mentors/${id}/photo`, { approve, note }, { admin: true }),
  adminCallMoney: () => request<CallMoney>("GET", "/admin/mentors/calls", undefined, { admin: true }),
  adminPayout: (id: number, amount_inr: number, note: string) => request<EarningsRow>("POST", `/admin/mentors/${id}/payouts`, { amount_inr, note }, { admin: true }),
  adminRefunded: (id: number) => request<void>("POST", `/admin/mentors/payments/${id}/refunded`, undefined, { admin: true }),
  adminMentorReports: () => request<MentorReport[]>("GET", "/admin/mentors/reports", undefined, { admin: true }),
  adminUsers: (q: string) => request<AdminUser[]>("GET", `/admin/users${qs({ q })}`, undefined, { admin: true }),
  formulaBook: () => get<FormulaSubject[]>("/notes/formulas"),
  leaderboard: (period: "week" | "all", scope: "exam" | "everyone") => get<Leaderboard>(`/leaderboard${qs({ period, scope })}`),

  // full mock tests
  mockMeta: () => get<MockMeta>("/mock/meta"),
  mocks: () => get<MockSummary[]>("/mock"),
  createMock: (pattern: string) => post<MockSummary>("/mock", { pattern }),
  /** a test on some chapters of a subject; for a college course, no chapters means all of it (a subject test) */
  createChapterTest: (subject: string, chapters: string[], count: number) =>
    post<MockSummary>("/mock", { pattern: "chapter", subject, chapters, count }),
  /** Class 10 and 12: a mock board exam on the whole subject */
  createBoardMock: (subject: string) => post<MockSummary>("/mock", { pattern: "chapter", subject, board: true }),
  mock: (id: number) => get<MockDetail>(`/mock/${id}`),
  startMock: (id: number) => post<MockDetail>(`/mock/${id}/start`),
  saveMock: (id: number, b: { responses: Record<string, MockResponse>; current_index?: number; tab_switches?: number }) =>
    request<{ status: string; remaining_sec: number | null }>("PUT", `/mock/${id}/responses`, b),
  submitMock: (id: number, b?: { responses: Record<string, MockResponse>; current_index?: number; tab_switches?: number }) =>
    post<MockDetail>(`/mock/${id}/submit`, b),
  discardMock: (id: number) => del(`/mock/${id}`),
  explainQuestion: (id: number, language: Exclude<Language, "en">) =>
    post<{ language: string; solution: string }>(`/mock/questions/${id}/explain`, { language }),
  mockWarmup: (id: number) => get<Warmup>(`/mock/${id}/warmup`),
  mockFeeling: (id: number, b: { subject: string; chapter: string; felt: Feeling | null }) =>
    request<{ felt: Record<string, Feeling> }>("PUT", `/mock/${id}/feeling`, b),
  reportQuestion: (qid: number, reason: string) => post<void>(`/mock/questions/${qid}/report`, { reason }),
};

export type { Checkpoint };

export interface GenomeNode {
  id: string; name: string; subject: string | null; cls: number | null; kind: "exam" | "school";
  underpins: number; roots: number; fixed: number;
}
export interface Genome {
  exam_chapters: number; foundations: number; links: number; students: number; traces: number; rooted: number;
  top: GenomeNode[]; nodes: GenomeNode[]; edges: { from: string; to: string; weight: number }[];
}
