import { ArrowRight, RotateCw, Wifi } from "lucide-react";
import { useEffect, useState } from "react";
import { LogoMark } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/primitives";
import { openServer, reach, savedServer, saveServer, tidyAddress } from "@/lib/server";

/** The Android app's own screen. It knows one thing, where your Focs server is, and hands the app over to it:
    at once when it already knows, after asking when it doesn't, and with a way back when the server can't be reached. */
export default function Connect() {
  const saved = savedServer();
  const unreachable = window.location.pathname.includes("unreachable");  // the app came back here: the server didn't answer
  const asked = new URLSearchParams(window.location.search).has("connect");  // "Change" in Settings
  const handing = !!saved && !unreachable && !asked;
  const [address, setAddress] = useState(saved);
  const [checking, setChecking] = useState(false);
  const [unsure, setUnsure] = useState("");  // an address nothing could be confirmed at

  useEffect(() => {
    if (handing) openServer(saved);
  }, [handing, saved]);

  const go = (to: string) => { saveServer(to); openServer(to); };
  const connect = async () => {
    const tidy = tidyAddress(address);
    if (!tidy) return;
    setChecking(true);
    setUnsure("");
    const found = await reach(tidy);
    setChecking(false);
    if (found) go(tidy);
    else setUnsure(tidy);
  };

  if (handing) {
    return (
      <div className="grid h-dvh place-items-center">
        <div className="relative grid place-items-center">
          <span className="absolute h-28 w-28 rounded-full bg-accent/25 blur-2xl [animation:breathe_2.4s_ease-in-out_infinite]" />
          <LogoMark className="relative h-14 w-14 [animation:mark-in_0.7s_cubic-bezier(0.16,1,0.3,1)_backwards]" />
        </div>
      </div>
    );
  }

  return (
    <div className="grid min-h-dvh place-items-center px-6 py-10">
      <div className="w-full max-w-sm [animation:rise_0.8s_cubic-bezier(0.16,1,0.3,1)_backwards]">
        <LogoMark className="h-14 w-14" />
        <div className="eyebrow mt-8">{unreachable ? "No answer" : "Connect"}</div>
        <h1 className="mt-3 text-[40px]">{unreachable ? "Can't reach your Focs" : "Where is your Focs?"}</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-muted">
          {unreachable ? <>Nothing answered at <span className="font-mono text-[13px] text-fg-soft">{saved}</span>. Check that Focs is running there and that this phone is online, then try again.</>
            : "The app shows your own Focs: the same account, plan, notes and tests as on the web. Enter the address you open it at."}
        </p>
        {unreachable && saved && (
          <Button variant="primary" size="lg" className="mt-6 w-full" onClick={() => openServer(saved)} icon={<RotateCw className="h-4 w-4" />}>Try again</Button>
        )}
        <form className="mt-8" onSubmit={(e) => { e.preventDefault(); void connect(); }}>
          <Label htmlFor="server">{unreachable ? "Or use another address" : "Server address"}</Label>
          <Input id="server" value={address} onChange={(e) => { setAddress(e.target.value); setUnsure(""); }} inputMode="url" autoCapitalize="none" autoCorrect="off"
            spellCheck={false} placeholder="focs.example.com or 192.168.1.5:8000" />
          {unsure && (
            <p className="mt-2 text-[13px] leading-relaxed text-warn">
              Couldn't confirm a Focs server at {unsure}. If the address is right (some phones don't let an app look at a computer on the same Wi-Fi first), open it anyway.
            </p>
          )}
          <Button type="submit" variant={unreachable ? "secondary" : "primary"} size="lg" className="mt-5 w-full" loading={checking} disabled={!address.trim()}>
            Connect <ArrowRight className="h-4 w-4" />
          </Button>
          {unsure && <Button type="button" variant="ghost" className="mt-2 w-full" onClick={() => go(unsure)}>Open it anyway</Button>}
        </form>
        <p className="mt-6 flex gap-2.5 text-[13px] leading-relaxed text-muted">
          <Wifi className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <span>Running Focs on your own computer? Start it with <span className="font-mono text-fg-soft">mobile\serve_for_phone.bat</span> and
            type the phone address it prints. Phone and computer must be on the same Wi-Fi.</span>
        </p>
      </div>
    </div>
  );
}
