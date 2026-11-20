import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { asksSeniors, cn, timeAgo, usesCourses } from "@/lib/utils";
import { useAuth } from "@/stores/auth";

/** The bell: a junior asked about a course you did, a senior answered or checked your question. Checked once a minute. */
export function NotificationBell() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const { data } = useQuery({ queryKey: ["notifications"], queryFn: api.notifications, refetchInterval: 60_000, staleTime: 30_000 });
  const read = useMutation({ mutationFn: api.notificationsRead, onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }) });
  const unread = data?.unread ?? 0;

  const courses = useAuth((s) => usesCourses(s.user?.exam_target));
  const seniors = useAuth((s) => asksSeniors(s.user?.exam_target));
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    window.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); window.removeEventListener("keydown", esc); };
  }, [open]);

  const empty = courses ? "Nothing yet. When a junior asks about a course you've done, or a senior answers you, it shows here."
    : seniors ? "Nothing yet. When a senior answers your question, it shows here." : "Nothing new yet.";
  const toggle = () => {
    setOpen(!open);
    if (!open && unread) read.mutate();  // opening the list counts as seeing them
  };
  return (
    <div className="relative" ref={box}>
      <Button variant="ghost" size="icon-sm" onClick={toggle} aria-expanded={open} aria-haspopup="true"
        aria-label={unread ? `Notifications, ${unread} new` : "Notifications"}>
        <Bell className="h-4 w-4" />
        {unread > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-accent px-1 text-[10px] font-bold text-accent-fg">{unread > 9 ? "9+" : unread}</span>}
      </Button>
      {open && (
        <div className="panel fixed inset-x-3 top-[calc(3.75rem+env(safe-area-inset-top))] z-50 overflow-hidden shadow-2xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-11 sm:w-80" role="region" aria-label="Notifications">
          <div className="border-b border-line px-4 py-2.5 text-sm font-semibold">Notifications</div>
          <div className="max-h-96 overflow-y-auto">
            {!data?.items.length && <p className="px-4 py-6 text-center text-sm text-muted">{empty}</p>}
            {data?.items.map((n) => (
              <button key={n.id} type="button" onClick={() => { setOpen(false); if (n.link) navigate(n.link); }}
                className={cn("block w-full border-b border-line px-4 py-3 text-left text-sm transition last:border-0 hover:bg-elev-2", !n.read && "bg-accent-soft/40")}>
                <div className="text-fg">{n.text}</div>
                {n.created_at && <div className="mt-0.5 text-xs text-muted">{timeAgo(n.created_at)}</div>}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
