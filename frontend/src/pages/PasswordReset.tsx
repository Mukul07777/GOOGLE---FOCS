import { ArrowLeft, MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Backdrop } from "@/components/Backdrop";
import { Logo } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/primitives";
import { api } from "@/lib/api";

/** "Forgot password" (ask for a link) and "Reset password" (choose a new one from the link). */
export default function PasswordReset({ mode }: { mode: "forgot" | "reset" }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = params.get("token") ?? "";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "forgot") {
        await api.forgotPassword(email);
        setSent(true);
      } else {
        await api.resetPassword(token, password);
        toast.success("Password changed — sign in with your new password.");
        navigate("/login", { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-dvh flex-col px-6 pb-[calc(2rem+env(safe-area-inset-bottom))] pt-[calc(2rem+env(safe-area-inset-top))] sm:px-12">
      <Backdrop scene="auth" />
      <Link to="/" className="inline-flex min-h-10 items-center"><Logo /></Link>
      <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
        {sent ? (
          <div className="text-center">
            <MailCheck className="mx-auto h-10 w-10 text-ok" />
            <h1 className="mt-4 text-[30px]">Check your email</h1>
            <p className="mt-2 text-sm text-muted">If an account exists for <b className="text-fg">{email}</b>, a reset link is on its way. It works for 30 minutes.</p>
            <Link to="/login" className="mt-6 inline-flex min-h-10 items-center gap-1.5 text-sm text-accent hover:underline"><ArrowLeft className="h-4 w-4" />Back to sign in</Link>
          </div>
        ) : (
          <>
            <h1 className="text-[36px]">{mode === "forgot" ? "Forgot your password?" : "Choose a new password"}</h1>
            <p className="mt-2 text-sm text-muted">
              {mode === "forgot" ? "Enter your email and we'll send you a link to set a new one." : "Use at least 8 characters."}
            </p>
            {mode === "reset" && !token ? (
              <p className="mt-6 rounded-xl border border-bad/25 bg-bad/10 px-3.5 py-2.5 text-sm text-bad">
                This link is incomplete. <Link to="/forgot-password" className="underline">Ask for a new one</Link>.
              </p>
            ) : (
              <form onSubmit={submit} className="mt-8 space-y-4">
                {mode === "forgot" ? (
                  <div><Label>Email</Label><Input type="email" autoComplete="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" /></div>
                ) : (
                  <div><Label hint="8+ characters">New password</Label><Input type="password" autoComplete="new-password" required minLength={8} autoFocus value={password} onChange={(e) => setPassword(e.target.value)} /></div>
                )}
                {error && (
                  <div className="rounded-xl border border-bad/25 bg-bad/10 px-3.5 py-2.5 text-sm text-bad">
                    {error}{mode === "reset" && <> <Link to="/forgot-password" className="underline">Send a new link</Link></>}
                  </div>
                )}
                <Button type="submit" variant="primary" size="lg" loading={busy} className="w-full">
                  {mode === "forgot" ? "Send reset link" : "Save new password"}
                </Button>
              </form>
            )}
            <Link to="/login" className="mt-6 inline-flex min-h-10 items-center justify-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft className="h-4 w-4" />Back to sign in</Link>
          </>
        )}
      </div>
    </div>
  );
}
