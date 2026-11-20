// Render-time LaTeX repair. Provider JSON modes used to delete every backslash that isn't a valid JSON escape
// ("\pm\sqrt{b^2-4ac}" arrived as "pmsqrt{b^2-4ac}", "\prod" as "prod", "\ge" as "ge"). The backend no longer
// uses JSON mode for content, but notes saved before that still carry the damage, so every Markdown string is
// repaired here before KaTeX sees it. Mirrors the simpler repair in backend/app/services/llm.py.

/* ---------------------------------------------------------------- command vocabulary */
const GREEK = "alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|lambda|mu|nu|xi|pi|varpi|rho|"
  + "varrho|sigma|varsigma|tau|upsilon|phi|varphi|chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega";
/** Commands that never take an argument. Inside math a bare one is never meant literally. */
const BARE = `${GREEK}|displaystyle|textstyle|cdot|times|div|pm|mp|leq|geq|le|ge|neq|ne|approx|equiv|sim|simeq|propto|`
  + "infty|partial|nabla|hbar|ell|sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan|sinh|cosh|tanh|log|ln|exp|lim|sum|prod|"
  + "int|iint|oint|det|max|min|quad|qquad|cdots|ldots|dots|to|rightarrow|leftarrow|Rightarrow|Leftarrow|leftrightarrow|"
  + "Leftrightarrow|implies|iff|forall|exists|angle|circ|perp|parallel|cup|cap|subset|subseteq|supset|emptyset|"
  + "varnothing|neg|land|lor|therefore|because|prime|degree|left|right|langle|rangle|lfloor|rfloor|lceil|rceil";
/** Commands that take a {group} (or a digit, as in \frac12). */
const BRACED = "frac|dfrac|tfrac|sqrt|mathbf|mathrm|mathit|mathcal|mathbb|boldsymbol|vec|hat|bar|tilde|dot|ddot|overline|"
  + "underline|overrightarrow|binom|operatorname|text|textbf|textit|textrm";
const BARE_SET = new Set(BARE.split("|"));
const BRACED_SET = new Set(BRACED.split("|"));
/** Commands trusted when a glued run is split apart ("bpmsqrtb" -> b \pm \sqrt b). Short words that hide inside
 *  ordinary words (in, to, ne, le, ge, int, sin, max…) are deliberately left out or marked weak. */
const SPLIT_STRONG = new Set([...GREEK.split("|").filter((g) => g.length >= 3), "pm", "mp", "sqrt", "frac", "dfrac",
  "tfrac", "prod", "sum", "times", "cdot", "infty", "partial", "nabla", "approx", "propto", "theta", "leq", "geq",
  "neq", "equiv", "displaystyle", "mathbf", "mathrm", "boldsymbol", "overline", "rightarrow", "Rightarrow"]);
const SPLIT_WEAK = new Set(["pi", "mu", "nu", "xi", "sin", "cos", "tan", "log", "lim", "det"]);

/* ---------------------------------------------------------------- inside math */
// Groups whose contents are text or labels, never commands: \text{...}, \mathrm{...}, sub/superscripts
const PROTECTED = /(\\?(?:text|textbf|textit|textrm|mathrm|operatorname|mbox)\{[^{}]*\}|[_^]\{[^{}]*\}|[_^][A-Za-z]+)/;

/** Split a glued run like "bpmsqrtb" into single letters and known commands, or null when it isn't one. */
function splitRun(run: string): string[] | null {
  type Best = { parts: string[]; singles: number; weak: boolean } | null;
  const memo = new Map<number, Best>();
  const solve = (i: number): Best => {
    if (i === run.length) return { parts: [], singles: 0, weak: false };
    if (memo.has(i)) return memo.get(i)!;
    let best: Best = null;
    const consider = (piece: string, cmd: boolean, weak: boolean) => {
      const rest = solve(i + piece.length);
      if (!rest) return;
      const cand = { parts: [cmd ? `\\${piece}` : piece, ...rest.parts], singles: rest.singles + (cmd ? 0 : 1), weak: rest.weak || weak };
      if (!best || cand.singles < best.singles) best = cand;
    };
    for (let len = Math.min(13, run.length - i); len >= 2; len--) {
      const piece = run.slice(i, i + len);
      if (SPLIT_STRONG.has(piece)) consider(piece, true, false);
      else if (SPLIT_WEAK.has(piece)) consider(piece, true, true);
    }
    consider(run[i], false, false);
    memo.set(i, best);
    return best;
  };
  const best = solve(0) as Best;
  if (!best || best.parts.every((p) => !p.startsWith("\\"))) return null;
  return best.singles <= (best.weak ? 1 : 2) ? best.parts : null;
}

function restoreRun(run: string, next: string): string {
  if (BARE_SET.has(run)) return `\\${run}`;
  if (BRACED_SET.has(run) && /^[{\d]/.test(next)) return `\\${run}`;
  const parts = splitRun(run);
  return parts ? parts.map((p, i) => (p.startsWith("\\") && i < parts.length - 1 && !parts[i + 1].startsWith("\\") ? `${p} ` : p)).join("") : run;
}

function restorePlain(part: string): string {
  // each run of letters that isn't already a command (no backslash in front)
  let out = part.replace(/(?<![\\A-Za-z])([A-Za-z]{2,})(?![A-Za-z])/g, (run, _g, offset: number) => restoreRun(run, part.slice(offset + run.length)));
  out = out.replace(/(?<=[\w})|])\s?,d([a-zA-Z])(?![A-Za-z])/g, "\\,d$1"); // "f(x),dx" -> "f(x)\,dx"
  return out;
}

// "\text{mol^{-1}}", "\text{m/s^2}": KaTeX can't take a script inside \text and shows the whole formula in red
const SCRIPT_IN_TEXT = /\\text\{([^{}^_]*)([\^_])(\{[^{}]*\}|[^{}\s])([^{}]*)\}/g;

function scriptsOutOfText(segment: string): string {
  let prev;
  let out = segment;
  do {
    prev = out;
    out = out.replace(SCRIPT_IN_TEXT, (_m, before: string, op: string, script: string, after: string) =>
      `${before ? `\\text{${before}}` : ""}${op}${script.startsWith("{") ? script : `{${script}}`}${after ? `\\text{${after}}` : ""}`);
  } while (out !== prev);
  return out;
}

function restoreMath(segment: string) {
  return scriptsOutOfText(segment).split(PROTECTED).map((part, i) => {
    if (!(i % 2)) return restorePlain(part);
    const text = /^(text|textbf|textit|textrm|mathrm|operatorname|mbox)\{/.exec(part);
    if (text) return `\\${part}`; // a \text{...} that lost its own backslash
    // sub/superscripts (x 	o 0 in a limit): only whole Greek letters, infinity and "to" — never words like "net"
    return part.replace(/(?<![\\A-Za-z])([A-Za-z]{2,})(?![A-Za-z])/g, (w) => (new RegExp(`^(?:${GREEK}|infty|to)$`).test(w) ? `\\${w}` : w));
  }).join("");
}

/* ---------------------------------------------------------------- formulas written without $...$ */
const COMMAND_NAME = new RegExp(`^(?:${BARE}|${BRACED})$`);
const TEXT_GROUP = /\\?text(?:bf|it|rm)?\{[^{}]*\}/g;
const MATH = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g;

function looksLikeFormula(s: string) {
  if (s.includes("$")) return false;
  const core = s.replace(TEXT_GROUP, " ");
  if (!/\\[A-Za-z]|[=^_]/.test(core)) return false;
  const prose = (core.match(/(?<![\\A-Za-z])[A-Za-z]{3,}(?![A-Za-z])/g) ?? []).filter((w) => !COMMAND_NAME.test(w));
  return prose.length < 3;
}

function wrapFormulaBullets(md: string) {
  let inFormulas = false;
  return md.split("\n").map((line) => {
    const heading = /^\s*#{1,6}\s+(.*)/.exec(line);
    if (heading) { inFormulas = /formula/i.test(heading[1]); return line; }
    const bullet = /^(\s*[-*]\s+)(.+)$/.exec(line);
    if (!inFormulas || !bullet) return line;
    if (bullet[2].includes("$")) return displayStyle(line); // a formula sheet reads better with full-size fractions
    const body = bullet[2].trim();
    const labelled = /^([^\\:$]{2,40}):(\*\*)?\s+(.+)$/.exec(body);
    if (labelled && looksLikeFormula(labelled[3])) return displayStyle(`${bullet[1]}${labelled[1]}:${labelled[2] ?? ""} $${labelled[3]}$`);
    return looksLikeFormula(body) ? displayStyle(`${bullet[1]}$${body}$`) : line;
  }).join("\n");
}

/* ---------------------------------------------------------------- outside math */
const GROUP = String.raw`\{(?:[^{}]|\{[^{}]*\})*\}`; // one level of nested braces
// "(1-\frac{6}{x+3})": a bracket in prose holding a command was math whose \( \) delimiters lost their backslash
const PAREN_MATH = /\(([^()$\n`]*\\[A-Za-z]+[^()$\n`]*)\)/g;
// a full stray command with its arguments and scripts: \frac{6}{x+3}, \sqrt{2}, \alpha_{1}, \ln
const STRAY = new RegExp(String.raw`\\(?:${BARE}|${BRACED})(?![A-Za-z])(?:${GROUP})*(?:[_^](?:${GROUP}|[A-Za-z0-9]))*`, "g");

// LaTeX spacing written outside math ("150\,m") would render as "150,m": turn it into real spaces
function plainSpacing(text: string) {
  return text.replace(/\\,/g, " ").replace(/\\[;:]/g, " ").replace(/\\!/g, "");
}

function outsideMath(md: string, fn: (prose: string) => string) {
  return md.split(MATH).map((part, i) =>
    i % 2 ? part : part.split(/(`[^`]*`)/).map((p, j) => (j % 2 ? p : fn(p))).join(""),
  ).join("");
}

export function normalizeMath(md: string) {
  // <br> is not rendered as HTML here: inside a table cell it becomes " · " (a newline would end the row), elsewhere a line break
  md = md.split("\n").map((l) => (/^\s*\|/.test(l) ? l.replace(/\s*<br\s*\/?>\s*/gi, " · ") : l.replace(/<br\s*\/?>/gi, "  \n"))).join("\n");
  // Models sometimes emit \( \) / \[ \] delimiters; remark-math wants $ / $$.
  let out = wrapFormulaBullets(md)
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `$$${m}$$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => `$${m}$`);
  out = outsideMath(out, (p) => p.replace(PAREN_MATH, (_, m: string) => `($${m.trim()}$)`));
  out = out.replace(MATH, (m) => restoreMath(m));
  return outsideMath(out, (p) => plainSpacing(p).replace(STRAY, (m) => `$${m}$`));
}

/** One formula on its own line (formula book): wrapped in display-style math when it's bare LaTeX. */
export function asFormula(text: string) {
  if (text.includes("$")) return displayStyle(text);
  const labelled = /^([^\\:$]{2,40}):(\*\*)?\s+(.+)$/.exec(text);
  if (labelled && looksLikeFormula(labelled[3])) return displayStyle(`${labelled[1]}:${labelled[2] ?? ""} $${labelled[3]}$`);
  return looksLikeFormula(text) ? displayStyle(`$${text}$`) : text;
}

/** Answer options are short; render their inline math in display style so fractions stay readable. */
export function displayStyle(text: string) {
  return text.replace(/(^|[^$])\$([^$\n]+?)\$/g, (whole, pre: string, m: string) =>
    m.includes("displaystyle") ? whole : `${pre}$\\displaystyle ${m}$`);
}

/** Models sometimes leave out a table's |---| line, and without it the whole table shows as raw text. */
export function repairTables(md: string): string {
  const row = (l: string) => /^\s*\|.*\|\s*$/.test(l);
  const divider = (l: string) => /^\s*\|?[\s:|-]+\|?\s*$/.test(l) && l.includes("-");
  const lines = md.split("\n");
  const out: string[] = [];
  lines.forEach((line, i) => {
    out.push(line);
    const starts = row(line) && !divider(line) && !(i > 0 && row(lines[i - 1]));
    if (starts && i + 1 < lines.length && row(lines[i + 1]) && !divider(lines[i + 1])) {
      const cells = line.trim().replace(/^\||\|$/g, "").split("|").length;
      out.push(`|${" --- |".repeat(cells)}`);
    }
  });
  return out.join("\n");
}
