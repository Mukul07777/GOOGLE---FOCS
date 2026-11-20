import { useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { MotionConfig } from "motion/react";
import { Toaster } from "sonner";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { LogoMark } from "@/components/common";
import { OfflineBanner } from "@/components/OfflineBanner";
import { IN_APP, IS_SHELL } from "@/lib/server";
import Connect from "@/pages/Connect";
import { useAuth } from "@/stores/auth";
import { useA11y } from "@/stores/a11y";
import { useTheme } from "@/stores/theme";

// the signed-in shell (sidebar, search, tour) loads with the first app page, not on the landing page
const AppShell = lazy(() => import("@/components/AppShell"));
const Landing = lazy(() => import("@/pages/Landing"));
const Auth = lazy(() => import("@/pages/Auth"));
const PasswordReset = lazy(() => import("@/pages/PasswordReset"));
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Studio = lazy(() => import("@/pages/Studio"));
const Library = lazy(() => import("@/pages/Library"));
const SessionView = lazy(() => import("@/pages/SessionView"));
const Practice = lazy(() => import("@/pages/Practice"));
const MockTests = lazy(() => import("@/pages/MockTests"));
const MockView = lazy(() => import("@/pages/MockView"));
const MockExam = lazy(() => import("@/pages/MockExam"));
const Leaderboard = lazy(() => import("@/pages/Leaderboard"));
const FormulaBook = lazy(() => import("@/pages/FormulaBook"));
const PrepHub = lazy(() => import("@/pages/PrepHub"));
const MyPlan = lazy(() => import("@/pages/MyPlan"));
const LastDay = lazy(() => import("@/pages/LastDay"));
const WeakSpots = lazy(() => import("@/pages/WeakSpots"));
const RootCause = lazy(() => import("@/pages/RootCause"));
const Genome = lazy(() => import("@/pages/Genome"));
const Snap = lazy(() => import("@/pages/Snap"));
const Campus = lazy(() => import("@/pages/Campus"));
const Mentors = lazy(() => import("@/pages/Mentors"));
const MentorChat = lazy(() => import("@/pages/MentorChat"));
// the mentor's side: an account of its own with its own dashboard
const MentorShell = lazy(() => import("@/components/MentorShell"));
const MentorHome = lazy(() => import("@/pages/mentor/MentorHome"));
const MentorSeekers = lazy(() => import("@/pages/mentor/MentorSeekers"));
const MentorCallsPage = lazy(() => import("@/pages/mentor/MentorCallsPage"));
const MentorSessionsPage = lazy(() => import("@/pages/mentor/MentorSessionsPage"));
const MentorEarningsPage = lazy(() => import("@/pages/mentor/MentorEarningsPage"));
const MentorProfilePage = lazy(() => import("@/pages/mentor/MentorProfilePage"));
const Classes = lazy(() => import("@/pages/Classes"));
const ClassView = lazy(() => import("@/pages/ClassView"));
const ParentView = lazy(() => import("@/pages/ParentView"));
const Onboarding = lazy(() => import("@/pages/Onboarding"));
const Admin = lazy(() => import("@/pages/Admin"));
const AdminLogin = lazy(() => import("@/pages/AdminLogin"));
const Flashcards = lazy(() => import("@/pages/Flashcards"));
const Rooms = lazy(() => import("@/pages/Rooms"));
const RoomView = lazy(() => import("@/pages/RoomView"));
const RoomReport = lazy(() => import("@/pages/RoomReport"));
const OcrLab = lazy(() => import("@/pages/OcrLab"));
const Settings = lazy(() => import("@/pages/Settings"));
const NotFound = lazy(() => import("@/pages/NotFound"));
const Privacy = lazy(() => import("@/pages/Privacy"));
const Terms = lazy(() => import("@/pages/Terms"));

function Splash() {
  return (
    <div className="grid h-dvh place-items-center">
      <div className="relative grid place-items-center">
        <span className="absolute h-28 w-28 rounded-full bg-hl/40 blur-2xl [animation:breathe_2.4s_ease-in-out_infinite]" />
        <LogoMark className="relative h-14 w-14 [animation:mark-in_0.7s_cubic-bezier(0.16,1,0.3,1)_backwards]" />
      </div>
    </div>
  );
}

/** Signed in, and with the right kind of account: students use /app, mentors /mentor. The other kind is sent home. */
function RequireAuth({ children, role = "student" }: { children: ReactNode; role?: "student" | "mentor" }) {
  const token = useAuth((s) => s.token);
  const mine = useAuth((s) => s.user?.role ?? "student");
  const location = useLocation();
  if (!token) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  if (mine !== role) return <Navigate to={mine === "mentor" ? "/mentor" : "/app"} replace />;
  return <>{children}</>;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const token = useAuth((s) => s.token);
  const role = useAuth((s) => s.user?.role);
  const redirect = useAuth((s) => s.redirect); // e.g. a new student goes to set their goal, not the dashboard
  return token ? <Navigate to={role === "mentor" ? "/mentor" : redirect ?? "/app"} replace /> : <>{children}</>;
}

/** Signs out, forgets what the last account loaded, then goes on: how a student switches to making a mentor account.
    A route of its own, so no signed-in page's guard sends them to the sign-in screen first. */
function SignOutTo({ to }: { to: string }) {
  const token = useAuth((s) => s.token);
  const logout = useAuth((s) => s.logout);
  const qc = useQueryClient();
  useEffect(() => { if (token) { qc.clear(); logout(); } }, [token, logout, qc]);
  return token ? null : <Navigate to={to} replace />;
}

export default function App() {
  const theme = useTheme((s) => s.theme);
  const reduceMotion = useA11y((s) => s.reduceMotion);
  if (IS_SHELL) return <Connect />;  // the app's own screen: it finds the server and hands over to it
  return (
    <MotionConfig reducedMotion={reduceMotion ? "always" : "user"}>
    <BrowserRouter>
      <ErrorBoundary>
        <Suspense fallback={<Splash />}>
          <Routes>
            <Route path="/" element={IN_APP ? <Navigate to="/app" replace /> : <Landing />} />
            <Route path="/pricing" element={<Navigate to="/#pricing" replace />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/terms" element={<Terms />} />
            {/* a parent's read-only view of their child's week, from a link the student made */}
            <Route path="/p/:token" element={<ParentView />} />
            <Route path="/login" element={<GuestOnly><Auth mode="login" /></GuestOnly>} />
            <Route path="/signup" element={<GuestOnly><Auth mode="signup" /></GuestOnly>} />
            <Route path="/mentor/signup" element={<GuestOnly><Auth mode="mentor-signup" /></GuestOnly>} />
            <Route path="/switch/mentor" element={<SignOutTo to="/mentor/signup" />} />
            <Route path="/forgot-password" element={<GuestOnly><PasswordReset mode="forgot" /></GuestOnly>} />
            <Route path="/reset-password" element={<PasswordReset mode="reset" />} />
            <Route path="/app" element={<RequireAuth><AppShell /></RequireAuth>}>
              <Route index element={<Dashboard />} />
              <Route path="plan" element={<MyPlan />} />
              <Route path="revise" element={<LastDay />} />
              <Route path="weak" element={<WeakSpots />} />
              <Route path="roots" element={<RootCause />} />
              <Route path="genome" element={<Genome />} />
              <Route path="snap" element={<Snap />} />
              <Route path="campus" element={<Campus />} />
              <Route path="mentors" element={<Mentors />} />
              <Route path="mentors/:id" element={<MentorChat />} />
              <Route path="classes" element={<Classes />} />
              <Route path="classes/:id" element={<ClassView />} />
              <Route path="prep" element={<PrepHub />} />
              <Route path="studio" element={<Studio />} />
              <Route path="library" element={<Library />} />
              <Route path="library/:id" element={<SessionView />} />
              <Route path="practice" element={<Practice />} />
              <Route path="mock" element={<MockTests />} />
              <Route path="mock/:id" element={<MockView />} />
              <Route path="flashcards" element={<Flashcards />} />
              <Route path="rooms" element={<Rooms />} />
              <Route path="rooms/:code" element={<RoomView />} />
              <Route path="rooms/:code/report" element={<RoomReport />} />
              <Route path="leaderboard" element={<Leaderboard />} />
            <Route path="formulas" element={<FormulaBook />} />
            <Route path="admin" element={<Navigate to="/admin" replace />} />
              <Route path="ocr" element={<OcrLab />} />
              <Route path="settings" element={<Settings />} />
            </Route>
            {/* a mentor account's dashboard: seekers, calls, master sessions, earnings and profile */}
            <Route path="/mentor" element={<RequireAuth role="mentor"><MentorShell /></RequireAuth>}>
              <Route index element={<MentorHome />} />
              <Route path="seekers" element={<MentorSeekers />} />
              <Route path="seekers/:id" element={<MentorChat />} />
              <Route path="calls" element={<MentorCallsPage />} />
              <Route path="sessions" element={<MentorSessionsPage />} />
              <Route path="earnings" element={<MentorEarningsPage />} />
              <Route path="profile" element={<MentorProfilePage />} />
            </Route>
            {/* the admin panel: its own sign-in, nothing shared with student accounts */}
            <Route path="/admin" element={<Admin />} />
            <Route path="/admin/login" element={<AdminLogin />} />
            {/* the exam takes the whole screen, like the NTA computer-based test */}
            <Route path="/exam/:id" element={<RequireAuth><MockExam /></RequireAuth>} />
            {/* goal set-up after signup (and "Edit goal"): full screen, like a welcome */}
            <Route path="/onboarding" element={<RequireAuth><Onboarding /></RequireAuth>} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
      <OfflineBanner />
      <Toaster theme={theme} position="top-center" richColors closeButton
        toastOptions={{ style: { borderRadius: 16, border: "var(--toast-border)", boxShadow: "var(--shadow)" } }} />
    </BrowserRouter>
    </MotionConfig>
  );
}
