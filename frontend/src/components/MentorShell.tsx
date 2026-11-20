import { useQuery } from "@tanstack/react-query";
import { IndianRupee, LayoutDashboard, Lock, LogOut, Menu, Moon, Presentation, Sun, UserRound, Users, Video } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Logo, LogoMark } from "@/components/common";
import { NotificationBell } from "@/components/NotificationBell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";

/* The mentor's side of Focs: an account of its own with its own menu. Until Focs approves the application, only the
   overview (where the application lives) and the profile are open. */

const NAV = [
  { to: "/mentor", label: "Overview", icon: LayoutDashboard, end: true, open: true },
  { to: "/mentor/seekers", label: "Seekers", icon: Users },
  { to: "/mentor/calls", label: "Calls", icon: Video },
  { to: "/mentor/sessions", label: "Master sessions", icon: Presentation },
  { to: "/mentor/earnings", label: "Earnings", icon: IndianRupee },
  { to: "/mentor/profile", label: "Profile", icon: UserRound, open: true },
];

/** The mentor's application and profile: every mentor page reads it (cached, refreshed with the bell). */
export function useWorkspace() {
  return useQuery({ queryKey: ["mentor-me"], queryFn: api.mentorWorkspace, refetchInterval: 60_000 });
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const { data: ws } = useWorkspace();
  const approved = ws?.profile?.status === "approved";
  const { data: list } = useQuery({ queryKey: ["mentorships"], queryFn: api.mentorships, refetchInterval: 30_000, enabled: approved });
  const badge = (to: string) => (to === "/mentor/seekers" ? (list?.requests ?? 0) + (list?.unread ?? 0) : 0);
  const status = ws?.profile?.status;
  return (
    <aside className="glass flex h-full w-[248px] flex-col border-r border-line px-3 pb-4 pt-[calc(1rem+env(safe-area-inset-top))]">
      <Link to="/mentor" className="mb-2 px-2" onClick={onNavigate}><Logo /></Link>
      <div className="caps mb-6 px-2 text-[10px] font-medium text-muted">Mentor dashboard</div>
      <nav className="-mr-1 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto pr-1">
        {NAV.map(({ to, label, icon: Icon, end, open }) => {
          const locked = !approved && !open;
          if (locked) {
            return (
              <span key={to} title="Opens once Focs approves your application" aria-disabled
                className="nav-item flex h-10 shrink-0 cursor-not-allowed items-center gap-3 rounded-sm px-3 text-[11.5px] font-medium opacity-45">
                <Icon className="h-[18px] w-[18px]" /><span className="flex-1">{label}</span><Lock className="h-3.5 w-3.5" />
              </span>
            );
          }
          return (
            <NavLink key={to} to={to} end={end} onClick={onNavigate}
              className={({ isActive }) => cn("nav-item group relative flex h-10 shrink-0 items-center gap-3 rounded-sm px-3 text-[11.5px] font-medium transition", isActive && "nav-item-on")}>
              {({ isActive }) => (
                <>
                  {isActive && <motion.span layoutId="mentor-nav-pill" className="nav-pill" transition={{ type: "spring", stiffness: 420, damping: 36 }} />}
                  <Icon className="nav-icon relative h-[18px] w-[18px]" />
                  <span className="relative flex-1">{label}</span>
                  {badge(to) > 0 && <span className="relative bg-fg px-1.5 text-[11px] font-semibold text-bg">{badge(to)}</span>}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>
      <div className="flex items-center gap-2 rounded-sm border border-line bg-elev/70 p-2">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-brand text-xs font-semibold text-brand-fg">
          {(user?.full_name ?? "").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase() || "?"}
        </div>
        <NavLink to="/mentor/profile" onClick={onNavigate} className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-medium">{user?.full_name}</div>
          <div className="truncate text-[11.5px] text-muted">
            {status === "approved" ? `${ws?.profile?.exam_label} mentor · verified` : status === "pending" ? "Application under review" : status === "rejected" ? "Application not approved" : "Not applied yet"}
          </div>
        </NavLink>
        <button onClick={logout} className="rounded-sm p-2 text-muted hover:bg-elev-2 hover:text-bad" aria-label="Sign out" title="Sign out">
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}

/** A mentor page that needs an approved profile: until then it explains why it's closed. */
export function ApprovedOnly({ children }: { children: ReactNode }) {
  const { data: ws, isLoading } = useWorkspace();
  if (isLoading || !ws) return null;
  if (ws.profile?.status === "approved") return <>{children}</>;
  return (
    <div className="mx-auto max-w-xl py-16 text-center">
      <Lock className="mx-auto h-8 w-8" strokeWidth={1.3} />
      <h1 className="display-caps mt-5 text-[28px]">Opens once you're approved</h1>
      <p className="mt-3 text-sm text-muted">Focs checks every mentor's qualifications by hand before students can find them. Your application and its status are on the overview.</p>
      <Link to="/mentor" className="mt-6 inline-block"><Button variant="primary">Go to my application</Button></Link>
    </div>
  );
}

export default function MentorShell() {
  const [drawer, setDrawer] = useState(false);
  const { theme, toggle } = useTheme();
  const location = useLocation();
  const setUser = useAuth((s) => s.setUser);
  useQuery({ queryKey: ["me"], queryFn: async () => { const u = await api.me(); setUser(u); return u; }, staleTime: 5 * 60_000 });
  useEffect(() => setDrawer(false), [location.pathname]);
  const current = [...NAV].reverse().find((n) => (n.end ? location.pathname === n.to : location.pathname.startsWith(n.to))) ?? NAV[0];

  return (
    <div className="flex h-dvh overflow-hidden">
      <div className="hidden lg:block"><Sidebar /></div>
      <AnimatePresence>
        {drawer && (
          <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-black/60" onClick={() => setDrawer(false)} />
            <motion.div className="relative h-full w-fit bg-bg" initial={{ x: -260 }} animate={{ x: 0 }} exit={{ x: -260 }} transition={{ type: "spring", damping: 30, stiffness: 300 }}>
              <Sidebar onNavigate={() => setDrawer(false)} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass-bar sticky top-0 z-30 flex h-[calc(3.5rem+env(safe-area-inset-top))] shrink-0 items-center gap-3 border-b border-line px-4 pt-[env(safe-area-inset-top)] sm:px-6">
          <button className="-ml-2.5 grid h-10 w-10 shrink-0 place-items-center lg:hidden" onClick={() => setDrawer(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
          <LogoMark className="h-6 w-6 lg:hidden" />
          <div className="caps text-[11.5px] font-medium text-fg">{current.label}</div>
          <Badge className="hidden sm:inline-flex">Mentor</Badge>
          <div className="flex-1" />
          <NotificationBell />
          <Button variant="ghost" size="icon-sm" onClick={toggle} aria-label="Toggle theme">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </header>
        <main className="flex-1 overflow-y-auto">
          <motion.div key={location.pathname} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
            className="page-enter mx-auto w-full max-w-[1200px] px-4 py-7 pb-16 sm:px-6 lg:px-8">
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
}
