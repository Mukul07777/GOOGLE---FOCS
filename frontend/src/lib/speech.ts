import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";

/* Spoken answers. The browser's own speech recognition (Chrome, Edge, Safari) is used when it exists: it is free and
   shows the words as they are said. Elsewhere (Firefox, Brave), or when the browser's service fails, the answer is
   recorded and transcribed by the Focs server instead. */

interface RecognitionResult { isFinal: boolean; 0: { transcript: string } }
interface RecognitionEvent { resultIndex: number; results: ArrayLike<RecognitionResult> }
interface Recognition {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void; stop(): void; abort(): void;
}
type RecognitionCtor = new () => Recognition;

export type SpeechLang = "en-IN" | "hi-IN" | "mr-IN" | "bn-IN" | "ta-IN" | "te-IN" | "gu-IN";
export const SPEECH_LANGS: { value: SpeechLang; label: string; title: string }[] = [
  { value: "en-IN", label: "EN", title: "English (also fine for Hinglish)" },
  { value: "hi-IN", label: "हिं", title: "Hindi" },
  { value: "mr-IN", label: "मरा", title: "Marathi" },
  { value: "bn-IN", label: "বাং", title: "Bengali" },
  { value: "ta-IN", label: "தமி", title: "Tamil" },
  { value: "te-IN", label: "తెలు", title: "Telugu" },
  { value: "gu-IN", label: "ગુજ", title: "Gujarati" },
];
const LANG_KEY = "focs-speech-lang";
const BROWSER_FAILED_KEY = "focs-speech-browser-failed";
const MAX_RECORDING_S = 180;

const recognitionCtor = (): RecognitionCtor | null => {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
};
const canRecord = () => typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
const stored = (key: string) => { try { return localStorage.getItem(key); } catch { return null; } };
const store = (key: string, value: string) => { try { localStorage.setItem(key, value); } catch { /* private mode */ } };

const MIC_BLOCKED = "Microphone access is blocked. Allow it for this site in your browser's address bar, then try again.";

export interface Dictation {
  /** speaking is possible here at all */
  available: boolean;
  /** which engine a new recording would use */
  engine: "browser" | "server" | null;
  listening: boolean;
  /** the recording is being turned into text (server engine only) */
  transcribing: boolean;
  /** words heard but not final yet (browser engine only) */
  interim: string;
  seconds: number;
  error: string | null;
  lang: SpeechLang;
  setLang: (l: SpeechLang) => void;
  start: () => void;
  stop: () => void;
}

/** `onText` gets each finished phrase; `hint` (e.g. the question) helps the server engine with technical terms. */
export function useDictation(onText: (text: string) => void, hint?: string): Dictation {
  const { data: status } = useQuery({ queryKey: ["speech-status"], queryFn: api.speechStatus, staleTime: Infinity, retry: false });
  const [lang, setLangState] = useState<SpeechLang>(() => SPEECH_LANGS.find((l) => l.value === stored(LANG_KEY))?.value ?? "en-IN");
  const [browserFailed, setBrowserFailed] = useState(() => { try { return sessionStorage.getItem(BROWSER_FAILED_KEY) === "1"; } catch { return false; } });
  const [listening, setListening] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [interim, setInterim] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const onTextRef = useRef(onText);
  onTextRef.current = onText;
  const hintRef = useRef(hint);
  hintRef.current = hint;
  const wanted = useRef(false);  // the student wants to keep speaking (the browser engine stops by itself after a pause)
  const pending = useRef("");    // words heard but not yet made final by the browser engine
  const heard = useRef(false);   // this browser-engine session caught at least one word
  const failed = useRef(false);  // …or ended with an error that already explained itself
  const startedAt = useRef(0);
  const recognition = useRef<Recognition | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);

  const serverOk = !!status?.server && canRecord();
  const engine: Dictation["engine"] = recognitionCtor() && !browserFailed ? "browser" : serverOk ? "server" : null;

  const setLang = useCallback((l: SpeechLang) => { setLangState(l); store(LANG_KEY, l); }, []);

  const release = useCallback(() => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    recorder.current = null;
  }, []);

  const startServer = useCallback(async () => {
    setError(null);
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      wanted.current = false;
      return setError(MIC_BLOCKED);
    }
    const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((m) => MediaRecorder.isTypeSupported(m));
    const rec = new MediaRecorder(stream.current, mime ? { mimeType: mime } : undefined);
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    rec.onstop = async () => {
      const type = rec.mimeType || mime || "audio/webm";
      release();
      setListening(false);
      const blob = new Blob(chunks, { type });
      if (blob.size < 800) return setError("Nothing was recorded. Check your microphone and try again.");
      setTranscribing(true);
      try {
        const { text } = await api.transcribe(blob, lang.slice(0, 2), hintRef.current);
        onTextRef.current(text);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Couldn't turn that into text. Try again, or type your answer.");
      } finally {
        setTranscribing(false);
      }
    };
    recorder.current = rec;
    rec.start();
    setListening(true);
  }, [lang, release]);

  const startBrowser = useCallback(() => {
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    setError(null);
    pending.current = "";
    heard.current = failed.current = false;
    startedAt.current = Date.now();
    const rec = new Ctor();
    rec.lang = lang;
    rec.interimResults = true;
    rec.continuous = !/Android/i.test(navigator.userAgent);  // Android Chrome repeats phrases in continuous mode
    rec.onresult = (e) => {
      let unfinished = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        const text = r[0].transcript.trim();
        if (!text) continue;
        heard.current = true;
        if (r.isFinal) onTextRef.current(text); else unfinished += ` ${text}`;
      }
      pending.current = unfinished.trim();
      setInterim(pending.current);
    };
    rec.onerror = (e) => {
      if (e.error === "no-speech" || e.error === "aborted") return;  // a pause: onend restarts while still wanted
      wanted.current = false;
      failed.current = true;
      if (e.error === "not-allowed" || e.error === "audio-capture") return setError(MIC_BLOCKED);
      // "network" / "service-not-allowed": this browser has the API but no service behind it (Brave, some Chromium builds)
      try { sessionStorage.setItem(BROWSER_FAILED_KEY, "1"); } catch { /* private mode */ }
      setBrowserFailed(true);
      setError(serverOk ? "Your browser's dictation isn't working, so Focs will record and transcribe instead. Press the mic again."
        : "Your browser's dictation isn't working here. Type your answer, or try Chrome or Edge.");
    };
    rec.onend = () => {
      // stopping mid-sentence can end the session before the last words are made final: keep them
      if (pending.current) onTextRef.current(pending.current);
      pending.current = "";
      setInterim("");
      if (wanted.current) {
        try { rec.start(); return; } catch { /* already restarting */ }
      }
      setListening(false);
      recognition.current = null;
      // listened for a while and caught nothing at all: the API is there but nothing is behind it (or the wrong mic)
      if (!heard.current && Date.now() - startedAt.current > 5000 && !failed.current) {
        if (serverOk) {
          try { sessionStorage.setItem(BROWSER_FAILED_KEY, "1"); } catch { /* private mode */ }
          setBrowserFailed(true);
          setError("Didn't catch anything. Press the mic again and Focs will record your answer instead.");
        } else setError("Didn't catch anything. Check that the right microphone is selected, or type your answer.");
      }
    };
    recognition.current = rec;
    try {
      rec.start();
      setListening(true);
    } catch {
      wanted.current = false;
      setError("Couldn't start listening. Try again.");
    }
  }, [lang, serverOk]);

  const stop = useCallback(() => {
    wanted.current = false;
    recognition.current?.stop();
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  const start = useCallback(() => {
    if (wanted.current || transcribing) return;
    wanted.current = true;
    setSeconds(0);
    if (engine === "browser") startBrowser();
    else if (engine === "server") void startServer();
    else wanted.current = false;
  }, [engine, startBrowser, startServer, transcribing]);

  useEffect(() => {
    if (!listening) return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [listening]);
  useEffect(() => { if (listening && seconds >= MAX_RECORDING_S) stop(); }, [listening, seconds, stop]);
  useEffect(() => () => {  // leaving the page mid-sentence: let go of the microphone
    wanted.current = false;
    recognition.current?.abort();
    if (recorder.current?.state === "recording") { recorder.current.onstop = null; recorder.current.stop(); }
    stream.current?.getTracks().forEach((t) => t.stop());
  }, []);

  return { available: engine !== null, engine, listening, transcribing, interim, seconds, error, lang, setLang, start, stop };
}
