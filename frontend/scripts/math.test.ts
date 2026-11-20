// Render-time LaTeX repair (src/lib/math.ts) — run with: npm run test:math
import { displayStyle, normalizeMath, repairTables } from "../src/lib/math";
import { plainTex } from "../src/lib/mathGuard";
import { mathToSpeech, toSpeech } from "../src/lib/readAloud";
import { TRANSLATED, translate } from "../src/lib/i18n";

let fails = 0;
const eq = (got: string, want: string) => {
  if (got !== want) { fails++; console.log("FAIL\n got:  " + JSON.stringify(got) + "\n want: " + JSON.stringify(want)); }
};

eq(normalizeMath(String.raw`speed $omega_0$ and $alpha$`), String.raw`speed $\omega_0$ and $\alpha$`);
eq(normalizeMath(String.raw`$displaystyle \tau = frac{tfrac12 mR^2}{t}$`), String.raw`$\displaystyle \tau = \frac{\tfrac12 mR^2}{t}$`);
eq(normalizeMath(String.raw`$mathbf{F} = m mathbf{a}$`), String.raw`$\mathbf{F} = m \mathbf{a}$`);
eq(normalizeMath("the alpha particle costs $5"), "the alpha particle costs $5");
eq(normalizeMath(String.raw`$text{sum of torques} = 0$`), String.raw`$\text{sum of torques} = 0$`);
// a script inside \text{} makes KaTeX paint the whole formula red (JEE paper Q5 and Q9, 28 October)
eq(normalizeMath(String.raw`$-33.0\ \text{kJ mol^{-1}}$`), String.raw`$-33.0\ \text{kJ mol}^{-1}$`);
eq(normalizeMath(String.raw`$a = 2\,\text{m/s^2}$`), String.raw`$a = 2\,\text{m/s}^{2}$`);
eq(normalizeMath(String.raw`$E_{int} + E_{max}$`), String.raw`$E_{int} + E_{max}$`);
eq(normalizeMath(String.raw`$\beta + \eta$`), String.raw`$\beta + \eta$`);
eq(normalizeMath(String.raw`inline \(x^2\) and \[E = mc^2\]`), String.raw`inline $x^2$ and $$E = mc^2$$`);

const md = [
  "### Key ideas",
  String.raw`- Torque \tau causes rotation of the body about an axis`,
  "### Formulas",
  String.raw`- \tau = \mathbf{r}\times\mathbf{F}`,
  String.raw`- **Torque:** \tau = I\alpha`,
  "- F = ma",
  String.raw`- Already fine: $L = I\omega$`,
  "- If there is no external torque acting then angular momentum stays constant",
  String.raw`- \text{If }\tau=0\text{, then }\mathbf{L}=\text{constant}`,
  "### Exam tip",
  "- v = u + at is for constant acceleration only, never for variable forces",
].join("\n");
const out = normalizeMath(md).split("\n");
eq(out[1], String.raw`- Torque $\tau$ causes rotation of the body about an axis`); // prose: only the command is wrapped
eq(out[3], String.raw`- $\displaystyle \tau = \mathbf{r}\times\mathbf{F}$`); // formula sheets: full-size fractions
eq(out[4], String.raw`- **Torque:** $\displaystyle \tau = I\alpha$`);
eq(out[5], String.raw`- $\displaystyle F = ma$`);
eq(out[6], String.raw`- Already fine: $\displaystyle L = I\omega$`);
eq(out[7], "- If there is no external torque acting then angular momentum stays constant");
eq(out[8], String.raw`- $\displaystyle \text{If }\tau=0\text{, then }\mathbf{L}=\text{constant}$`);
eq(out[10], "- v = u + at is for constant acceleration only, never for variable forces");
eq(normalizeMath(String.raw`Remember the direction of \tau and L`), String.raw`Remember the direction of $\tau$ and L`);
eq(normalizeMath(String.raw`Use \mathbf{L} here, and $\tau = I\alpha$ there`), String.raw`Use $\mathbf{L}$ here, and $\tau = I\alpha$ there`);
eq(normalizeMath("Escape with `\\alpha` in code"), "Escape with `\\alpha` in code");
eq(normalizeMath(String.raw`a newline \n stays`), String.raw`a newline \n stays`);
eq(normalizeMath(String.raw`travels 150\,m in 12.0\,s at $4\,\mathrm{m\,s^{-2}}$`), "travels 150 m in 12.0 s at $4\\,\\mathrm{m\\,s^{-2}}$");
// ---- the user's screenshots (notes saved while JSON mode was deleting backslashes)
eq(normalizeMath(String.raw`- Quadratic formula: $x = \frac{-bpmsqrt{b^2-4ac}}{2a}$`), String.raw`- Quadratic formula: $x = \frac{-b\pm\sqrt{b^2-4ac}}{2a}$`);
eq(normalizeMath(String.raw`| $f(x)=prod_{i=1}^{n}(x-a_i)$ | When solving $f(x)ge0$ or $f(x)le0$ |`), String.raw`| $f(x)=\prod_{i=1}^{n}(x-a_i)$ | When solving $f(x)\ge0$ or $f(x)\le0$ |`);
eq(normalizeMath(String.raw`$f(x)=aprod_{i=1}^{n}(x-a_i)$`), String.raw`$f(x)=a\prod_{i=1}^{n}(x-a_i)$`);
eq(normalizeMath(String.raw`1. Rewrite as (1-\frac{6}{x+3}).`), String.raw`1. Rewrite as ($1-\frac{6}{x+3}$).`);
eq(normalizeMath(String.raw`2. Integrate: (int \frac{6}{x+3},dx = 6\ln|x+3|).`), String.raw`2. Integrate: ($\int \frac{6}{x+3}\,dx = 6\ln|x+3|$).`);
eq(normalizeMath(String.raw`3. Combine: (x-6\ln|x+3|+C).`), String.raw`3. Combine: ($x-6\ln|x+3|+C$).`);
eq(normalizeMath(String.raw`Then \frac{6}{x+3} integrates`), String.raw`Then $\frac{6}{x+3}$ integrates`);
// ---- 18 Nov screenshots: neighbouring bare commands became "$a$$b$", and "$$" turned the formula red
eq(normalizeMath(String.raw`if \log_{10}\sin x+\log_{10}\cos x = -1?`), String.raw`if $\log_{10}\sin x+\log_{10}\cos x = -1$?`);
eq(normalizeMath(String.raw`if \log_{10}$$\sin x+\log_{10}$$\cos x = -1?`), String.raw`if $\log_{10}\sin x+\log_{10}\cos x = -1$?`);
eq(normalizeMath(String.raw`terms of sec x: \tan^8 x = \tan^4 x \cdot 2 = \sec^4 x .$$`), String.raw`terms of sec x: $\tan^8 x = \tan^4 x \cdot 2 = \sec^4 x$ .`);
eq(normalizeMath(String.raw`Remember \tau is torque`), String.raw`Remember $\tau$ is torque`); // an ordinary word after a command is not absorbed
eq(normalizeMath("costs $5 and $10"), "costs $5 and $10");
// a formula KaTeX can't draw is shown as readable text, never as red source (src/lib/mathGuard.ts)
eq(plainTex(String.raw`\frac{a}{b} \leq \sqrt{2}$$`), "(a)/(b) ≤ √(2)");
// ---- glued commands
eq(normalizeMath(String.raw`$costheta + sin^2 theta$`), String.raw`$\cos\theta + \sin^2 \theta$`);
eq(normalizeMath(String.raw`$A = pir^2$`), String.raw`$A = \pi r^2$`);
eq(normalizeMath(String.raw`$lim_{x to 0} frac{sin x}{x} = 1$`), String.raw`$\lim_{x \to 0} \frac{\sin x}{x} = 1$`);
// ---- must stay untouched: variables, chemistry, subscript words, English inside \text
for (const keep of [String.raw`$mgh$`, String.raw`$KE = \frac{1}{2}mv^2$`, String.raw`$H_2SO_4 + CH_3COOH$`, String.raw`$KMnO_4$`,
  String.raw`$F_{net} = ma$`, String.raw`$v_{max}$`, String.raw`$\text{using the net force}$`, String.raw`$s = ut + \frac12 at^2$`,
  String.raw`$NaCl$`, String.raw`$\alpha + \beta$`]) eq(normalizeMath(keep), keep);
eq(displayStyle(String.raw`$x = 1$`), String.raw`$\displaystyle x = 1$`);

// ---- read aloud: formulas are said as words (src/lib/readAloud.ts)
eq(mathToSpeech(String.raw`\frac{a}{b}`), "a over b");
eq(mathToSpeech(String.raw`R = \frac{u^2 \sin 2\theta}{g}`), "R equals u squared sin 2 theta over g");
eq(mathToSpeech(String.raw`x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}`), "x equals minus b plus or minus square root of b squared minus 4ac over 2a");
eq(mathToSpeech(String.raw`v_{max} \leq c`), "v sub max less than or equal to c");
eq(mathToSpeech("E = mc^2"), "E equals mc squared");
eq(mathToSpeech("x^25"), "x to the power 2 5");
eq(mathToSpeech(String.raw`\vec{F} = m\vec{a}`), "F equals m a");
eq(mathToSpeech(String.raw`H_2O`), "H 2 O");
eq(toSpeech("## Range\n\n- The range is $R = \\frac{u^2}{g}$ at 45°\n- **Max** height"), "Range. The range is R equals u squared over g at 45° Max height");
eq(toSpeech("| a | b |\n| --- | --- |\n| 1 | 2 |"), "a, b. 1, 2.");
// a table the model wrote without its |---| line
eq(repairTables("| A | B |\n| 1 | 2 |"), "| A | B |\n| --- | --- |\n| 1 | 2 |");
eq(repairTables("| A | B |\n|---|---|\n| 1 | 2 |"), "| A | B |\n|---|---|\n| 1 | 2 |");
eq(repairTables("text | not a table\n- x"), "text | not a table\n- x");

// ---- the interface in the student's language (src/lib/i18n.ts)
eq(translate("Live lecture", "en"), "Live lecture");
eq(translate("Live lecture", undefined), "Live lecture");
eq(translate("Something not translated yet", "hi"), "Something not translated yet");  // falls back to English, never blank
eq(translate("I'm lost", "hinglish"), "Samajh nahi aaya");
for (const key of TRANSLATED) {
  const hi = translate(key, "hi"), hinglish = translate(key, "hinglish");
  if (!/[ऀ-ॿ]/.test(hi)) { fails++; console.log("FAIL Hindi has no Devanagari: " + key); }
  if (!hinglish.trim() || /[ऀ-ॿ]/.test(hinglish)) { fails++; console.log("FAIL Hinglish should be Latin script: " + key); }
}
console.log(fails ? `${fails} FAILED` : "ALL MATH TESTS PASS");
if (fails) process.exit(1);
