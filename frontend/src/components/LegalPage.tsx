import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "@/components/common";
import { SITE } from "@/lib/site";

export function LegalPage({ title, intro, children }: { title: string; intro: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-bg text-fg pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]">
      <header className="mx-auto flex max-w-3xl items-center justify-between px-5 py-6">
        <Link to="/" className="inline-flex min-h-10 items-center"><Logo /></Link>
        <Link to="/" className="inline-flex min-h-10 items-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft className="h-4 w-4" />Home</Link>
      </header>
      <main className="mx-auto max-w-3xl px-5 pb-20">
        <h1 className="text-[36px]">{title}</h1>
        <p className="mt-2 text-sm text-muted">Last updated {SITE.updated}</p>
        <div className="mt-6 text-[15px] leading-relaxed text-fg-soft">{intro}</div>
        <div className="legal mt-8 space-y-8 text-[14.5px] leading-relaxed text-fg-soft [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-fg [&_li]:ml-5 [&_li]:list-disc [&_li]:pl-1 [&_ul]:mt-2 [&_ul]:space-y-1.5 [&_b]:text-fg">
          {children}
        </div>
        <p className="mt-12 border-t border-line pt-6 text-xs text-muted">
          See also: <Link to="/privacy" className="text-accent underline underline-offset-2">Privacy Policy</Link> ·{" "}
          <Link to="/terms" className="text-accent underline underline-offset-2">Terms of Service</Link>
        </p>
      </main>
    </div>
  );
}
