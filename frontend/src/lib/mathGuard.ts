// Last line of defence for maths: a formula that KaTeX can't draw must never reach a student as red source code.
// Runs as a rehype plugin BEFORE rehype-katex, on exactly the formulas the parser found:
//   1. stray "$" inside a formula (the parser paired "$a$$b$" into one) are removed;
//   2. if KaTeX still throws, the formula is shown as plain readable text ("(sec^2 x - 1)^4 - 2"), not red LaTeX.
// Mirrors plain() in backend/app/services/math_text.py.
import katex from "katex";
import { visit } from "unist-util-visit";

const SYMBOLS: Record<string, string> = {
  le: "≤", leq: "≤", ge: "≥", geq: "≥", ne: "≠", neq: "≠", pm: "±", mp: "∓", cdot: "·", times: "×", div: "÷", infty: "∞",
  pi: "π", theta: "θ", alpha: "α", beta: "β", gamma: "γ", delta: "δ", lambda: "λ", mu: "μ", sigma: "σ", omega: "ω", phi: "φ",
  to: "→", rightarrow: "→", Rightarrow: "⇒", implies: "⇒", cup: "∪", cap: "∩", circ: "°", approx: "≈", degree: "°",
};

/** A formula as readable text, for when it can't be drawn. */
export function plainTex(src: string): string {
  let s = src.replace(/(?<!\\)\$/g, "");
  for (let i = 0; i < 3; i++) s = s.replace(/\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, (_m, a: string, b: string) => `(${a})/(${b})`);
  s = s.replace(/\\(?:displaystyle|textstyle|left|right|mathrm|mathbf|text|textbf|operatorname)(?![A-Za-z])/g, "")
    .replace(/\\sqrt\s*\{([^{}]*)\}/g, "√($1)")
    .replace(/\\([A-Za-z]+)/g, (_m, name: string) => SYMBOLS[name] ?? name)
    .replace(/\\[,;:! ]/g, " ")
    .replace(/\^\{([^{}]*)\}/g, "^$1").replace(/_\{([^{}]*)\}/g, "_$1")
    .replace(/[{}]/g, "");
  return s.replace(/\s+/g, " ").trim();
}

type Node = { type: string; tagName?: string; value?: string; properties?: { className?: unknown }; children?: Node[] };

function textOf(n: Node): string {
  return n.type === "text" ? (n.value ?? "") : (n.children ?? []).map(textOf).join("");
}

function drawable(src: string, display: boolean): boolean {
  try { katex.renderToString(src, { throwOnError: true, strict: "ignore", displayMode: display }); return true; } catch { return false; }
}

export function rehypeMathGuard() {
  return (tree: Node) => {
    visit(tree as never, "element", ((node: Node, index: number | undefined, parent: Node | undefined) => {
      const cls = node.properties?.className;
      const classes = Array.isArray(cls) ? (cls as string[]) : [];
      if (node.tagName !== "code" || !classes.includes("language-math")) return;
      const display = classes.includes("math-display");
      const raw = textOf(node);
      const clean = raw.replace(/(?<!\\)\$+/g, " ").trim();
      if (drawable(clean, display)) { node.children = [{ type: "text", value: clean }]; return; }
      // can't be drawn: plain text in the page's own colour
      const fallback: Node = { type: "element", tagName: "span", properties: { className: ["math-fallback"] },
        children: [{ type: "text", value: plainTex(raw) }] };
      if (parent && index !== undefined) parent.children![index] = fallback;
    }) as never);
  };
}
