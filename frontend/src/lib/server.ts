/** The Android app and the Focs server it shows.
 *
 *  The app carries one small screen of its own (the "shell": this same code, built by mobile/build_apk.bat). All the
 *  shell does is learn where your Focs server is and hand the app over to it; from then on the app shows the
 *  server's own pages, exactly as a browser would. So the app is never a version behind the web, and it needs no
 *  special access to the server. */
const KEY = "focs-server";
const SHELL = "http://localhost";  // where the app serves its own screen from (mobile/capacitor.config.json)

/** This build is the app's shell. */
export const IS_SHELL = import.meta.env.VITE_FOCS_APP === "1";
/** Running inside the Android app, as its shell or as a server's pages shown in it (the app adds "FocsApp" to the
 *  browser's name). There is one window there, nowhere to save a file to and no printer. */
export const IN_APP = IS_SHELL || /\bFocsApp\b/.test(navigator.userAgent);
const BUILT_IN = String(import.meta.env.VITE_FOCS_SERVER ?? "").trim();

/** "192.168.1.5:8000" → "http://192.168.1.5:8000"; "focs.example.com/" → "https://focs.example.com". */
export function tidyAddress(address: string): string {
  const a = address.trim().replace(/\s+/g, "").replace(/\/+$/, "");
  if (!a || /^https?:\/\//i.test(a)) return a;
  const local = /^(localhost|\d{1,3}(\.\d{1,3}){3}|[^./]+)(:\d+)?$/i.test(a);  // an IP, a bare machine name: a computer nearby
  return `${local ? "http" : "https"}://${a}`;
}

/** The server the shell last handed over to (or the one the app was built for). */
export function savedServer(): string {
  try {
    return localStorage.getItem(KEY) || tidyAddress(BUILT_IN);
  } catch {
    return tidyAddress(BUILT_IN);
  }
}

export function saveServer(address: string): void {
  try {
    localStorage.setItem(KEY, tidyAddress(address));
  } catch {
    /* storage is off: the address is asked for again next time */
  }
}

/** Is there a Focs server at this address? Its name when there is; null when nothing answered, or when the phone
 *  would not let the shell look (some do not, for a computer on the same Wi-Fi). */
export async function reach(address: string, timeoutMs = 6000): Promise<string | null> {
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), timeoutMs);
  try {
    const res = await fetch(`${tidyAddress(address)}/api/health`, { signal: stop.signal });
    const data = res.ok ? await res.json() : null;
    return data?.status === "ok" && typeof data.app === "string" ? data.app : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/** Hand the app over to a server: its pages take it from here. */
export const openServer = (address: string) => window.location.replace(`${tidyAddress(address)}/app`);
/** From a server's page shown in the app: back to the shell, to point the app at another server. */
export const chooseServer = () => { window.location.href = `${SHELL}/?connect=1`; };
