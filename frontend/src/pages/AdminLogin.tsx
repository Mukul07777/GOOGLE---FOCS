import { ArrowRight, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { adminSignedIn, useAdmin } from "@/stores/admin";

/** The admin panel's own sign-in: an admin ID and password, separate from every student account. */
export default function AdminLogin() {
  const navigate = useNavigate();
  const sentFrom = (useLocation().state as { username?: string } | null)?.username; // typed into the student sign-in
  const signIn = useAdmin((s) => s.signIn);
  const [form, setForm] = useState({ username: sentFrom ?? "", password: "" });
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (adminSignedIn()) return <Navigate to="/admin" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.adminLogin(form.username, form.password);
      signIn(res.token, res.username, res.expires_in);
      navigate("/admin", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setForm((f) => ({ ...f, password: "" }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-dvh flex-col bg-bg px-6 pb-[calc(2rem+env(safe-area-inset-bottom))] pt-[calc(2rem+env(safe-area-inset-top))] sm:px-12">
      <Logo />
      <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <div className="mb-5 grid h-11 w-11 place-items-center rounded-xl bg-accent-soft text-accent"><ShieldCheck className="h-5 w-5" /></div>
          <h1 className="text-[36px]">Admin panel</h1>
          <p className="mt-2 text-sm text-muted">
            {sentFrom ? "That's the admin ID — admins sign in here. Enter the admin password." : "For the Focs team. Student accounts can't sign in here."}
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <div>
              <Label htmlFor="admin-id">Admin ID</Label>
              <Input id="admin-id" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="admin@focs"
                autoComplete="username" autoCapitalize="none" spellCheck={false} required autoFocus={!sentFrom} />
            </div>
            <div>
              <Label htmlFor="admin-password">Password</Label>
              <div className="relative">
                <Input id="admin-password" type={showPw ? "text" : "password"} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                  aria-label="Password" className="pr-11" autoComplete="current-password" required autoFocus={!!sentFrom} />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-0.5 top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center text-muted hover:text-fg"
                  aria-label={showPw ? "Hide password" : "Show password"}>
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            {error && <div role="alert" className="rounded-xl border border-bad/25 bg-bad/10 px-3.5 py-2.5 text-sm text-bad">{error}</div>}
            <Button type="submit" variant="primary" size="lg" loading={loading} className="w-full">
              Sign in {!loading && <ArrowRight className="h-4 w-4" />}
            </Button>
          </form>
          <p className="mt-6 text-center text-xs leading-relaxed text-muted">
            Forgot it? Run <code className="rounded bg-elev-2 px-1 py-0.5">set_admin.bat</code> on the server to set a new one.
          </p>
        </motion.div>
      </div>
    </div>
  );
}
