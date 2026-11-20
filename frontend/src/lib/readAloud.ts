/**
 * Read aloud: notes, answers, solutions and captions spoken by the browser's own voices (no server, no cost).
 * Markdown and LaTeX are turned into words first, so "$\frac{a}{b}$" is read "a over b", not "dollar backslash frac".
 */

const SYMBOLS: [RegExp, string][] = [
  [/\\(?:times|cdot)/g, " times "], [/\\div/g, " divided by "], [/\\pm/g, " plus or minus "], [/\\mp/g, " minus or plus "],
  [/\\(?:leq|le)\b/g, " less than or equal to "], [/\\(?:geq|ge)\b/g, " greater than or equal to "],
  [/\\(?:neq|ne)\b/g, " not equal to "], [/\\approx/g, " approximately "], [/\\propto/g, " proportional to "],
  [/\\(?:to|rightarrow|Rightarrow|longrightarrow)/g, " gives "], [/\\infty/g, " infinity "], [/\\partial/g, " partial "],
  [/\\nabla/g, " del "], [/\\int/g, " integral of "], [/\\sum/g, " sum of "], [/\\lim/g, " limit "],
  [/\\(?:degree|circ)/g, " degrees "], [/\\angle/g, " angle "], [/\\Delta/g, " delta "],
];
const GREEK = "alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|lambda|mu|nu|xi|pi|rho|sigma|tau|phi|varphi|chi|psi|omega|Omega|Sigma|Phi|Psi|Gamma|Lambda|Theta";

/** One LaTeX expression in words. Not a full reader: the common school and college notation, said plainly. */
export function mathToSpeech(tex: string): string {
  let s = tex;
  for (let i = 0; i < 4; i++) {  // nested fractions and roots, innermost first
    s = s.replace(/\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}/g, " $1 over $2 ")
      .replace(/\\sqrt\[([^\]]*)\]\{([^{}]*)\}/g, " $1-th root of $2 ")
      .replace(/\\sqrt\{([^{}]*)\}/g, " square root of $1 ")
      .replace(/\\(?:text|mathrm|mathbf|vec|hat|bar|boldsymbol|operatorname)\{([^{}]*)\}/g, " $1 ");
  }
  for (const [re, words] of SYMBOLS) s = s.replace(re, words);
  s = s.replace(new RegExp(`\\\\(${GREEK})\\b`, "g"), " $1 ")
    .replace(/\\(sin|cos|tan|log|ln|exp)\b/g, " $1 ")
    .replace(/\^(?:\{2\}|2(?!\d))/g, " squared ").replace(/\^(?:\{3\}|3(?!\d))/g, " cubed ")
    .replace(/\^\{-1\}/g, " inverse ").replace(/\^\{([^{}]*)\}/g, " to the power $1 ").replace(/\^(\w)/g, " to the power $1 ")
    .replace(/_\{([^{}]*)\}/g, " sub $1 ").replace(/_(\w)/g, " $1 ")
    .replace(/=/g, " equals ").replace(/\+/g, " plus ").replace(/-/g, " minus ").replace(/</g, " less than ").replace(/>/g, " greater than ")
    .replace(/\\[a-zA-Z]+/g, " ").replace(/\\[,;:! ]/g, " ").replace(/[{}\\]/g, " ");
  return s.replace(/\s+/g, " ").trim();
}

/** A whole note or answer in words: math spoken, markdown symbols and table rules dropped. */
export function toSpeech(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/\$\$([\s\S]+?)\$\$/g, (_, t) => `. ${mathToSpeech(t)}. `)
    .replace(/\$([^$\n]+?)\$/g, (_, t) => ` ${mathToSpeech(t)} `)
    .replace(/^\s*\|?\s*:?-{2,}.*$/gm, " ")   // table separator rows
    .replace(/^\s*\|(.*)\|\s*$/gm, (_, row: string) => `${row.split("|").map((c) => c.trim()).filter(Boolean).join(", ")}.\n`)  // a table row: one sentence
    .replace(/\|/g, ", ")
    .replace(/^#{1,6}\s*(.+)$/gm, "$1. ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_`>#~]/g, "")
    .replace(/^\s*[-+]\s+/gm, "")
    .replace(/\n{2,}/g, ". ").replace(/\n/g, " ")
    .replace(/\s+([.,])/g, "$1").replace(/(\.\s*){2,}/g, ". ")
    .replace(/\s+/g, " ").trim();
}

export const canSpeak = (): boolean => typeof window !== "undefined" && "speechSynthesis" in window;

// the Unicode block of each Indian script, and the voice that reads it
const SCRIPTS: [number, number, string][] = [
  [0x0900, 0x097f, "hi-IN"], [0x0980, 0x09ff, "bn-IN"], [0x0a80, 0x0aff, "gu-IN"], [0x0b80, 0x0bff, "ta-IN"], [0x0c00, 0x0c7f, "te-IN"],
];
const NATIVE = ["hi", "mr", "bn", "ta", "te", "gu"];

function scriptOf(text: string): string | null {
  for (const ch of text) {
    const c = ch.codePointAt(0) ?? 0;
    const hit = SCRIPTS.find(([first, last]) => c >= first && c <= last);
    if (hit) return hit[2];
  }
  return null;
}

/** The voice for a text: the voice of the script it is written in (Marathi for a Marathi reader's Devanagari), else
 *  the student's language, else an Indian English one when the device has it. */
function voiceFor(text: string, lang?: string): { voice: SpeechSynthesisVoice | null; lang: string } {
  const script = scriptOf(text);
  const own = lang && NATIVE.includes(lang) ? `${lang}-IN` : null;
  const want = script === "hi-IN" && lang === "mr" ? "mr-IN" : script ?? own ?? "en-IN";
  const voices = window.speechSynthesis.getVoices();
  const voice = voices.find((v) => v.lang === want) ?? voices.find((v) => v.lang.startsWith(want.slice(0, 2))) ?? null;
  return { voice, lang: want };
}

let current: { id: string; done: () => void } | null = null;

/** Speak `md` (markdown with math); `id` says what is speaking, so its button can show "Stop". */
export function speak(md: string, id: string, onEnd: () => void, opts: { lang?: string; rate?: number } = {}): void {
  stopSpeaking();
  const text = toSpeech(md);
  if (!text || !canSpeak()) return onEnd();
  const { voice, lang } = voiceFor(text, opts.lang);
  // long texts are spoken sentence by sentence: some browsers stop a single long utterance after ~15 s
  const parts = text.match(/[^.!?।]+[.!?।]*/g) ?? [text];
  current = { id, done: onEnd };
  parts.forEach((part, i) => {
    const u = new SpeechSynthesisUtterance(part.trim());
    u.lang = lang;
    if (voice) u.voice = voice;
    u.rate = opts.rate ?? 1;
    if (i === parts.length - 1) u.onend = () => { if (current?.id === id) { current = null; onEnd(); } };
    window.speechSynthesis.speak(u);
  });
}

export const speakingId = (): string | null => current?.id ?? null;

export function stopSpeaking(): void {
  if (!canSpeak()) return;
  const was = current;
  current = null;
  window.speechSynthesis.cancel();
  was?.done();
}
