import { useQuery } from "@tanstack/react-query";
import {
  BookOpen, Camera, CircleHelp, ChevronRight, Command, Compass, Crosshair, Dna, GitBranch, GraduationCap, Hourglass, Layers, LayoutDashboard, LogOut, Menu, Moon, Plus, Presentation, Radio, Route, ScanText, School, Search,
  Settings, Sigma, Sun, Target, Timer, Trophy, Users,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useDeferredValue, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useNavigationType } from "react-router-dom";
import { Backdrop } from "@/components/Backdrop";
import { Logo, LogoMark } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/primitives";
import { SidebarUsage } from "@/components/UsageMeter";
import { api } from "@/lib/api";
import { useBackClose } from "@/lib/overlay";
import { asksSeniors, cn, examLabel, hasSyllabus, hasTests, isGate, isSsc, mockExamName, subjectTestsOnly, usesCourses } from "@/lib/utils";
import { NotificationBell } from "@/components/NotificationBell";
import { buildTourSteps, GuidedTour, markTourSeen, tourSeen } from "@/components/GuidedTour";
import { useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";
import { BRIDGE, ROOTS } from "@/lib/site";
import { useT } from "@/lib/i18n";

const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/plan", label: "My plan", icon: Route },
  { to: "/app/prep", label: "Prep Hub", icon: GraduationCap },
  { to: "/app/studio", label: "Live lecture", icon: Radio },
  { to: "/app/library", label: "Library", icon: BookOpen },
  { to: "/app/practice", label: "Practice", icon: Target },
  { to: "/app/snap", label: "Ask with a photo", icon: Camera },
  { to: "/app/mock", label: "Mock tests", icon: Timer },
  { to: "/app/weak", label: "Weak spots", icon: Crosshair },
  { to: "/app/roots", label: "Root cause", icon: GitBranch },
  { to: "/app/genome", label: "Gap Genome", icon: Dna },
  { to: "/app/campus", label: "Campus", icon: School },
  { to: "/app/mentors", label: "Mentors", icon: Compass },
  { to: "/app/revise", label: "Last-day revision", icon: Hourglass },
  { to: "/app/flashcards", label: "Flashcards", icon: Layers },
  { to: "/app/rooms", label: "Study rooms", icon: Users },
  { to: "/app/classes", label: "Classes", icon: Presentation },
  { to: "/app/leaderboard", label: "Leaderboard", icon: Trophy },
];

/** Phone bottom bar: the four most phone-friendly sections; everything else is under "More". */
const MOBILE_TABS: Record<string, string> = ROOTS
  ? { "/app": "Home", "/app/roots": "Roots", "/app/practice": "Practice", "/app/mock": "Mocks" }
  : { "/app": "Home", "/app/plan": "Plan", "/app/studio": "Live", "/app/mock": "Mocks" };

/** The menu as this student sees it: a B.Tech student has subject tests, not mock tests; Campus is for course students. */
/** The event build shows only the screens on the teacher \u2194 student bridge (the rest still open by URL). */
const BRIDGE_NAV: Record<string, string> = {
  "/app": "Home", "/app/studio": "Live lecture", "/app/rooms": "Live class", "/app/mock": "Tests & gap map", "/app/campus": "Ask a senior",
};

/** The roots build (Google hackathon): only the screens on the root-cause loop. */
const ROOTS_NAV: Record<string, string> = {
  "/app": "Home", "/app/roots": "Root cause", "/app/genome": "Gap Genome", "/app/practice": "Practice", "/app/mock": "Mock tests",
  "/app/weak": "Weak spots", "/app/classes": "Classes",
};

/** Pages built on a syllabus: a student whose exam has none here (UPSC, CA, other) never gets another exam's. */
const SYLLABUS_ONLY = new Set(["/app/plan", "/app/prep", "/app/mock", "/app/weak", "/app/revise"]);

function useNav() {
  const college = useAuth((s) => subjectTestsOnly(s.user?.exam_target));
  const courses = useAuth((s) => usesCourses(s.user?.exam_target));
  const seniors = useAuth((s) => asksSeniors(s.user?.exam_target));  // JEE/NEET: Campus is just "Ask a senior"
  const syllabus = useAuth((s) => hasSyllabus(s.user?.exam_target));
  const tests = useAuth((s) => hasTests(s.user?.exam_target));  // school: only Class 10 and 12 take tests
  return useMemo(() => {
    const items = NAV.filter((n) => (seniors || n.to !== "/app/campus") && (syllabus || !SYLLABUS_ONLY.has(n.to)) && (tests || n.to !== "/app/mock"))
      .map((n) => (college && n.to === "/app/mock" ? { ...n, label: "Tests" } : !courses && n.to === "/app/campus" ? { ...n, label: "Ask a senior" } : n));
    const only = BRIDGE ? BRIDGE_NAV : ROOTS ? ROOTS_NAV : null;
    return only ? items.filter((n) => n.to in only).map((n) => ({ ...n, label: only[n.to] })) : items;
  }, [college, courses, seniors, syllabus, tests]);
}

/** Pages reached from elsewhere (not the sidebar) still need a title in the top bar. */
const OTHER_PAGES = [
  { to: "/app/formulas", label: "Formula book" },
  { to: "/app/settings", label: "Settings" },
  { to: "/app/ocr", label: "OCR lab" },
];

function Avatar({ name, className }: { name: string; className?: string }) {
  const initials = name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-brand text-xs font-semibold text-brand-fg", className)}>
      {initials || "?"}
    </div>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const nav = useNav();
  const { user, logout } = useAuth();
  const { data: active } = useQuery({ queryKey: ["active-session"], queryFn: api.activeSession, refetchInterval: 30_000 });
  const { data: stats } = useQuery({ queryKey: ["card-stats"], queryFn: api.cardStats, staleTime: 60_000 });
  const navigate = useNavigate();
  const t = useT();

  return (
    <aside className="glass flex h-full w-[248px] flex-col border-r border-line px-3 pb-4 pt-[calc(1rem+env(safe-area-inset-top))]">
      <Link to="/app" className="mb-6 px-2" onClick={onNavigate}>
        <Logo />
      </Link>

      <Button data-tour="start" variant="primary" className="mb-5 w-full justify-start" icon={active ? <span className="live-dot mr-0.5" /> : <Plus className="h-4 w-4" />}
        onClick={() => { navigate("/app/studio"); onNavigate?.(); }}>
        {t(active ? "Return to live lecture" : "Start a lecture")}
      </Button>

      <nav className="-mr-1 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto pr-1">
        {nav.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} onClick={onNavigate} data-tour={`nav:${to}`}
            className={({ isActive }) => cn(
              "nav-item group relative flex h-10 shrink-0 items-center gap-3 rounded-sm px-3 text-[11.5px] font-medium transition",
              isActive && "nav-item-on",
            )}>
            {({ isActive }) => (
              <>
                {/* a rule of ink that slides to the page you open */}
                {isActive && <motion.span layoutId="nav-pill" className="nav-pill" transition={{ type: "spring", stiffness: 420, damping: 36 }} />}
                <Icon className="nav-icon relative h-[18px] w-[18px]" />
                <span className="relative flex-1">{t(label)}</span>
                {to === "/app/flashcards" && !!stats?.due && (
                  <span className="nav-count relative rounded-full bg-accent-soft px-1.5 text-[11px] font-semibold text-accent">{stats.due}</span>
                )}
                {to === "/app/studio" && active && <span className="live-dot" />}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div data-tour="usage"><SidebarUsage onNavigate={onNavigate} /></div>

      <div data-tour="profile" className="flex items-center gap-2 rounded-sm border border-line bg-elev/70 p-2">
        <Avatar name={user?.full_name ?? ""} />
        <NavLink to="/app/settings" onClick={onNavigate} className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-medium">{user?.full_name}</div>
          <div className="truncate text-[11.5px] text-muted">{examLabel(user?.exam_target)} · {user?.plan === "free" ? "Starter" : "Pro"}</div>
        </NavLink>
        <button onClick={logout} className="rounded-lg p-2.5 text-muted hover:bg-elev-2 hover:text-bad" aria-label="Sign out" title="Sign out">
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}

/* ---------------------------------------------------------------- Command palette */
interface Cmd { id: string; label: string; hint?: string; icon: ReactNode; run: () => void }

function CommandPalette({ open, onClose, onTour }: { open: boolean; onClose: () => void; onTour: () => void }) {
  useBackClose(open, onClose);
  const nav = useNav();
  const navigate = useNavigate();
  const examTarget = useAuth((s) => s.user?.exam_target);
  const toggleTheme = useTheme((s) => s.toggle);
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const t = useT();

  const commands: Cmd[] = useMemo(() => {
    const go = (to: string) => () => { navigate(to); onClose(); };
    return [
      { id: "studio", label: "Start a live lecture", hint: "Capture a lecture tab", icon: <Radio className="h-4 w-4" />, run: go("/app/studio") },
      { id: "plan", label: "Open my plan", hint: "Today, this week and month by month", icon: <Route className="h-4 w-4" />, run: go("/app/plan") },
      { id: "prep", label: "Open the Prep Hub", hint: "Syllabus, topics and progress", icon: <GraduationCap className="h-4 w-4" />, run: go("/app/prep") },
      { id: "photo", label: "Upload a board photo", hint: "Offline classes", icon: <ScanText className="h-4 w-4" />, run: go("/app/studio?mode=photo") },
      ...(hasTests(examTarget) && hasSyllabus(examTarget) ? [{ id: "mock", label: subjectTestsOnly(examTarget) ? "Take a subject test" : `Take a full ${mockExamName(examTarget)} mock`,
        hint: subjectTestsOnly(examTarget) ? "MCQs on one of your subjects" : isGate(examTarget) ? "3 hours · 65 questions" : isSsc(examTarget) ? "Tier-I · 100 questions · 60 min" : `${examTarget === "neet" ? "3 h 20 min" : "3 hours"} · NTA-style`,
        icon: <Timer className="h-4 w-4" />, run: go("/app/mock") }] : []),
      { id: "weak", label: "Add a test result", hint: "Find and fix your weak spots", icon: <Crosshair className="h-4 w-4" />, run: go("/app/weak?add=1") },
      { id: "revise", label: "Last-day revision", hint: "What to revise the day before", icon: <Hourglass className="h-4 w-4" />, run: go("/app/revise") },
      { id: "formulas", label: "Open my formula book", hint: "Every formula from your lectures", icon: <Sigma className="h-4 w-4" />, run: go("/app/formulas") },
      { id: "review", label: "Review due flashcards", icon: <Layers className="h-4 w-4" />, run: go("/app/flashcards") },
      { id: "quiz", label: "Generate a practice set", icon: <Target className="h-4 w-4" />, run: go("/app/practice") },
      { id: "search", label: "Search my notes", icon: <Search className="h-4 w-4" />, run: go("/app/library") },
      ...nav.map((n) => ({ id: n.to, label: `Go to ${t(n.label)}`, icon: <n.icon className="h-4 w-4" />, run: go(n.to) })),
      { id: "settings", label: "Settings", icon: <Settings className="h-4 w-4" />, run: go("/app/settings") },
      { id: "tour", label: "Take the tour", hint: "What every control does", icon: <CircleHelp className="h-4 w-4" />, run: () => { onClose(); onTour(); } },
      { id: "theme", label: "Toggle light / dark theme", icon: <Sun className="h-4 w-4" />, run: () => { toggleTheme(); onClose(); } },
    ];
  }, [navigate, onClose, onTour, toggleTheme, nav, t, examTarget]);

  // Notes are searched too, so "torque" finds the boards it is on, not only commands with that word.
  const typed = useDeferredValue(q.trim());
  const { data: found, isFetching: searching } = useQuery({
    queryKey: ["notes", "search", typed, "palette"],
    queryFn: () => api.notes({ q: typed, limit: 6 }),
    enabled: open && typed.length >= 2,
    staleTime: 30_000,
  });
  const noteCmds: Cmd[] = typed.length >= 2 ? (found?.items ?? []).map((n) => ({
    id: `note-${n.id}`, label: n.topic || "Board notes", hint: n.subject || "Note",
    icon: <ScanText className="h-4 w-4" />, run: () => { navigate(`/app/library/${n.session_id}`); onClose(); },
  })) : [];
  const filtered = [...commands.filter((c) => c.label.toLowerCase().includes(q.toLowerCase())), ...noteCmds];
  useEffect(() => {
    if (open) {
      setQ("");
      setIdx(0);
      setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [open]);
  useEffect(() => setIdx(0), [q]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[70] flex items-start justify-center px-4 pt-[14vh]" initial={{ opacity: 0 }} animate={{ opacity: 1, pointerEvents: "auto", visibility: "visible" }} exit={{ opacity: 0, pointerEvents: "none", transitionEnd: { visibility: "hidden" } }}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
          <motion.div className="panel relative w-full max-w-xl overflow-hidden" initial={{ y: -10, scale: 0.98 }} animate={{ y: 0, scale: 1 }} exit={{ y: -10, scale: 0.98 }}>
            <div className="flex items-center gap-3 border-b border-line px-4">
              <Command className="h-4 w-4 text-muted" />
              <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search notes or jump to a page…"
                className="h-14 flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted"
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(i + 1, filtered.length - 1)); }
                  if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
                  if (e.key === "Enter") filtered[idx]?.run();
                  if (e.key === "Escape") onClose();
                }} />
              <Kbd>Esc</Kbd>
            </div>
            <div className="max-h-[50vh] overflow-y-auto p-2">
              {filtered.length === 0 && <div className="px-3 py-8 text-center text-sm text-muted">
                {searching ? "Searching your notes…" : typed.length >= 2 ? "No commands or notes match" : "No matching commands"}
              </div>}
              {filtered.map((c, i) => (
                <button key={c.id} onMouseEnter={() => setIdx(i)} onClick={c.run}
                  className={cn("flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition", i === idx ? "bg-elev-2 text-fg" : "text-fg-soft")}>
                  <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line", i === idx && "border-accent/40 text-accent")}>{c.icon}</span>
                  {/* on a phone the hint goes under the label so the label keeps one line */}
                  <span className="flex min-w-0 flex-1 flex-col sm:flex-row sm:items-center sm:gap-3">
                    <span className="min-w-0 sm:flex-1">{c.label}</span>
                    {c.hint && <span className="text-xs text-muted">{c.hint}</span>}
                  </span>
                  {i === idx && <ChevronRight className="h-4 w-4 shrink-0 text-muted" />}
                </button>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ---------------------------------------------------------------- Shell */
/** Hours since a sign-in token was issued (its "iat"), or Infinity when it can't be read. */
function tokenAgeHours(token: string | null | undefined): number {
  try {
    const payload = JSON.parse(atob(token!.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    const age = (Date.now() / 1000 - Number(payload.iat)) / 3600;
    return Number.isFinite(age) ? age : Infinity;
  } catch {
    return Infinity;
  }
}

export default function AppShell() {
  const nav = useNav();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [drawer, setDrawer] = useState(false);
  useBackClose(drawer, () => setDrawer(false));
  const userId = useAuth((s) => s.user?.id);
  const joined = useAuth((s) => s.user?.created_at);
  const [tour, setTour] = useState(false);
  const tourSteps = useMemo(() => buildTourSteps(nav), [nav]);
  const { theme, toggle } = useTheme();
  const location = useLocation();
  // a new student gets the tour once, on the dashboard after it has drawn; the ? button replays it. "Seen" is kept
  // per device, so an older account signing in on a new phone isn't toured again, and never over a test's instructions
  const onDashboard = location.pathname === "/app" || location.pathname === "/app/";
  useEffect(() => {
    if (!userId || !onDashboard || tourSeen(userId)) return;
    if (joined && Date.now() - new Date(joined).getTime() > 3 * 86_400_000) { markTourSeen(userId); return; }
    const id = setTimeout(() => setTour(true), 900);
    return () => clearTimeout(id);
  }, [userId, joined, onDashboard]);
  const closeTour = () => { setTour(false); markTourSeen(userId); };
  const setUser = useAuth((s) => s.setUser);
  const language = useAuth((s) => s.user?.language);
  useEffect(() => { document.documentElement.lang = language === "hi" ? "hi" : "en"; }, [language]);  // screen readers pick the voice
  const setAuth = useAuth((s) => s.setAuth);
  const t = useT();

  useQuery({ queryKey: ["me"], queryFn: async () => { const u = await api.me(); setUser(u); return u; }, staleTime: 5 * 60_000 });
  // a fresh 7-day token on a visit once the current one is half a day old: anyone who opens Focs at least weekly
  // stays signed in, without a refresh on every page load
  const token = useAuth((s) => s.token);
  useQuery({
    queryKey: ["token-refresh"],
    queryFn: async () => { const r = await api.refreshToken(); setAuth(r.access_token, r.user); return true; },
    staleTime: Infinity, retry: false, refetchOnWindowFocus: false, enabled: tokenAgeHours(token) > 12,
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => setDrawer(false), [location.pathname]);
  const page = useRef<HTMLElement>(null);
  const howArrived = useNavigationType();
  useEffect(() => {  // a new page starts at its top; Back returns to where the student was
    if (howArrived !== "POP") page.current?.scrollTo(0, 0);
  }, [location.pathname, howArrived]);

  const current = [...nav, ...OTHER_PAGES].find((n) => ("end" in n && n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)))
    ?? { label: "Focs" };

  return (
    <div className="flex h-dvh overflow-hidden">
      <Backdrop scene="app" />
      <div className="hidden lg:block"><Sidebar /></div>

      <AnimatePresence>
        {drawer && (
          <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1, pointerEvents: "auto", visibility: "visible" }} exit={{ opacity: 0, pointerEvents: "none", transitionEnd: { visibility: "hidden" } }}>
            <div className="absolute inset-0 bg-black/60" onClick={() => setDrawer(false)} />
            <motion.div className="relative h-full w-fit bg-bg" initial={{ x: -260 }} animate={{ x: 0 }} exit={{ x: -260 }} transition={{ type: "spring", damping: 30, stiffness: 300 }}>
              <Sidebar onNavigate={() => setDrawer(false)} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass-bar sticky top-0 z-30 flex h-[calc(3.5rem+env(safe-area-inset-top))] shrink-0 items-center gap-1 border-b border-line px-4 pt-[env(safe-area-inset-top)] sm:gap-3 sm:px-6">
          <button className="-ml-1 shrink-0 p-1 lg:hidden" onClick={() => setDrawer(true)} aria-label="Open menu"><LogoMark className="h-8 w-8" /></button>
          <div className="caps line-clamp-2 min-w-0 pl-1 text-[11.5px] font-medium leading-tight text-fg sm:pl-0">{t(current.label)}</div>
          <div className="flex-1" />
          <button data-tour="search" onClick={() => setPaletteOpen(true)}
            className="hidden h-9 w-72 items-center gap-2 rounded-sm border border-line-strong bg-panel px-3 text-[13px] text-muted transition hover:border-fg hover:text-fg-soft md:flex">
            <Search className="h-4 w-4" /> <span className="flex-1 text-left">{t("Search or jump to…")}</span> <Kbd>Ctrl</Kbd><Kbd>K</Kbd>
          </button>
          <Button variant="ghost" size="icon-sm" onClick={() => setPaletteOpen(true)} className="md:hidden" aria-label="Search" data-tour="search"><Search className="h-4 w-4" /></Button>
          <span data-tour="bell" className="inline-flex"><NotificationBell /></span>
          <Button variant="ghost" size="icon-sm" onClick={() => { setDrawer(false); setTour(true); }} aria-label={t("Take the tour")} title={t("Take the tour")} data-tour="help">
            <CircleHelp className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={toggle} aria-label="Toggle theme" data-tour="theme">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </header>

        <main ref={page} className="flex-1 overflow-y-auto">
          <motion.div key={location.pathname} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
            className="page-enter mx-auto w-full max-w-[1400px] px-4 py-7 pb-[calc(6rem+env(safe-area-inset-bottom))] sm:px-6 lg:px-8 lg:pb-10">
            <Outlet />
          </motion.div>
        </main>

        <nav className="glass-bar fixed inset-x-0 bottom-0 z-30 flex h-[calc(4rem+env(safe-area-inset-bottom))] items-center justify-around border-t border-line px-1 pb-[env(safe-area-inset-bottom)] lg:hidden">
          {nav.filter((n) => n.to in MOBILE_TABS).map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} data-tour={`nav:${to}`}
              onClick={() => { if (location.pathname === to) page.current?.scrollTo({ top: 0, behavior: "smooth" }); }}
              className={({ isActive }) => cn("relative flex min-w-0 flex-1 flex-col items-center gap-1 rounded-sm px-0.5 py-1.5 font-display text-[10px] font-medium uppercase tracking-[0.12em] transition-colors", isActive ? "text-fg" : "text-muted")}>
              {({ isActive }) => (
                <>
                  {isActive && <motion.span layoutId="tab-pill" className="absolute -top-[9px] h-[2px] w-8 bg-fg"
                    transition={{ type: "spring", stiffness: 420, damping: 36 }} />}
                  <Icon className="h-5 w-5" />
                  {t(label === "Tests" ? label : MOBILE_TABS[to])}
                </>
              )}
            </NavLink>
          ))}
          <button data-tour="more" onClick={() => setDrawer(true)} className="flex min-w-0 flex-1 flex-col items-center gap-1 rounded-sm px-0.5 py-1.5 font-display text-[10px] font-medium uppercase tracking-[0.12em] text-muted">
            <Menu className="h-5 w-5" />{t("More")}
          </button>
        </nav>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onTour={() => setTour(true)} />
      <GuidedTour steps={tourSteps} open={tour} onClose={closeTour} />
    </div>
  );
}
