import { useEffect, useRef, useState } from "react";
import { useTheme } from "@/stores/theme";

// Google's own "Sign in with Google" button (Google Identity Services). Its script loads only on the pages that show
// the button, and the button only appears when the server has a Google client ID. The ID token it hands back is
// checked by the server (/api/auth/google), never trusted here.

interface GsiId {
  initialize(o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: "popup"; context?: string;
    itp_support?: boolean; use_fedcm_for_prompt?: boolean }): void;
  renderButton(el: HTMLElement, o: Record<string, unknown>): void;
}
declare global { interface Window { google?: { accounts: { id: GsiId } } } }

const SRC = "https://accounts.google.com/gsi/client";
let loading: Promise<void> | null = null;

function loadGsi(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  loading ??= new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = SRC; s.async = true; s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => { loading = null; reject(new Error("Google sign-in couldn't load")); };
    document.head.appendChild(s);
  });
  return loading;
}

export function GoogleButton({ clientId, signup, onCredential }: {
  clientId: string; signup: boolean; onCredential: (credential: string) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  callback.current = onCredential;  // the latest form state, without re-drawing Google's button on every keystroke
  const dark = useTheme((s) => s.theme) === "dark";
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    loadGsi().then(() => {
      if (!live || !box.current || !window.google) return;
      window.google.accounts.id.initialize({
        client_id: clientId, ux_mode: "popup", context: signup ? "signup" : "signin", itp_support: true,
        callback: (r) => callback.current(r.credential),
      });
      box.current.innerHTML = "";
      window.google.accounts.id.renderButton(box.current, {
        type: "standard", theme: dark ? "filled_black" : "outline", size: "large", shape: "pill",
        text: signup ? "signup_with" : "continue_with", logo_alignment: "center",
        width: Math.min(400, Math.max(240, box.current.offsetWidth || 320)),
      });
    }).catch(() => live && setFailed(true));
    return () => { live = false; };
  }, [clientId, signup, dark]);

  if (failed) return <p className="text-center text-xs text-muted">Google sign-in couldn't load. Use your email instead, or try again later.</p>;
  return <div ref={box} className="flex min-h-[44px] w-full justify-center" />;
}
