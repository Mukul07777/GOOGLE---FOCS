"""Text-line generator for synthetic training data.

Lines mix six sources so the recogniser learns characters, not a language model:
formulas, chemistry, exam phrasing, science vocabulary, common English (+ Hinglish),
and random character soup. Lines from existing Focs notes are folded in when available.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import numpy as np

from .charset import in_charset, normalize_text

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "corpus"

SCIENCE_TERMS = """
Newton's Laws of Motion|Kinematics|Projectile Motion|Relative Velocity|Work Energy Theorem|
Conservation of Momentum|Centre of Mass|Rotational Motion|Moment of Inertia|Torque|Angular Momentum|
Gravitation|Escape Velocity|Kepler's Laws|Elasticity|Young's Modulus|Bulk Modulus|Stress and Strain|
Thermal Expansion|Calorimetry|Heat Transfer|Thermodynamics|Carnot Engine|Entropy|Kinetic Theory|
Simple Harmonic Motion|Damped Oscillations|Wave Motion|Doppler Effect|Standing Waves|Beats|
Electrostatics|Coulomb's Law|Electric Field|Gauss's Law|Electric Potential|Capacitance|Dielectric|
Current Electricity|Ohm's Law|Kirchhoff's Laws|Wheatstone Bridge|Potentiometer|Magnetic Field|
Biot-Savart Law|Ampere's Law|Lorentz Force|Electromagnetic Induction|Faraday's Law|Lenz's Law|
Self Inductance|Alternating Current|LCR Circuit|Resonance|Ray Optics|Refraction|Total Internal Reflection|
Lens Formula|Wave Optics|Interference|Diffraction|Polarisation|Photoelectric Effect|de Broglie Wavelength|
Bohr Model|Nuclear Physics|Radioactivity|Half Life|Semiconductors|p-n Junction|Logic Gates|
Mole Concept|Stoichiometry|Atomic Structure|Quantum Numbers|Periodic Table|Chemical Bonding|
Hybridisation|VSEPR Theory|Molecular Orbital Theory|States of Matter|Ideal Gas Equation|
Chemical Equilibrium|Le Chatelier's Principle|Ionic Equilibrium|Buffer Solution|Solubility Product|
Redox Reactions|Oxidation Number|Electrochemistry|Nernst Equation|Chemical Kinetics|Rate Constant|
Activation Energy|Arrhenius Equation|Surface Chemistry|Adsorption|Solutions|Raoult's Law|
Colligative Properties|Osmotic Pressure|Thermochemistry|Hess's Law|Enthalpy|Gibbs Free Energy|
s-Block Elements|p-Block Elements|d and f Block|Coordination Compounds|Crystal Field Theory|
Organic Chemistry|IUPAC Nomenclature|Isomerism|Inductive Effect|Resonance Effect|Hyperconjugation|
Carbocation|SN1 Reaction|SN2 Reaction|Elimination Reaction|Aldehydes and Ketones|Carboxylic Acids|
Amines|Biomolecules|Polymers|Haloalkanes|Alcohols Phenols Ethers|Hydrocarbons|Benzene|
Sets Relations Functions|Trigonometric Functions|Inverse Trigonometry|Complex Numbers|Quadratic Equations|
Sequences and Series|Permutations and Combinations|Binomial Theorem|Straight Lines|Circles|
Conic Sections|Parabola|Ellipse|Hyperbola|Limits and Continuity|Differentiability|
Application of Derivatives|Maxima and Minima|Indefinite Integration|Definite Integration|
Area Under Curves|Differential Equations|Vectors|Three Dimensional Geometry|Matrices|Determinants|
Probability|Bayes' Theorem|Statistics|Mean Median Mode|Variance|Standard Deviation|
Cell Structure|Cell Division|Mitosis|Meiosis|Photosynthesis|Respiration|Plant Hormones|
Human Physiology|Digestion|Breathing|Body Fluids|Excretion|Locomotion|Neural Control|
Chemical Coordination|Reproduction|Genetics|Mendel's Laws|Molecular Basis of Inheritance|DNA Replication|
Transcription|Translation|Evolution|Human Health and Disease|Biotechnology|Ecosystem|Biodiversity|
Data Structures|Linked List|Binary Search|Dynamic Programming|Graph Theory|Time Complexity|
Operating Systems|Deadlock|Paging|Computer Networks|TCP/IP|DBMS|Normalization|SQL Joins|
Indian Polity|Fundamental Rights|Directive Principles|Parliament|Monetary Policy|GDP Growth|
Accounting Standards|Balance Sheet|Depreciation|Cost Accounting|Taxation|Company Law
"""

EXAM_PHRASES = [
    "Find the {q}", "Calculate the {q}", "Determine the {q} of the system", "Given:", "To find:",
    "Sol:", "Solution:", "Ans:", "Answer: {n}", "Note:", "Important!", "Remember:", "Hint:", "Proof:",
    "Q.{i}", "Q{i}.", "Ex. {i}.{j}", "Example {i}", "Illustration {i}", "(i)", "(ii)", "(iii)", "(iv)",
    "(a)", "(b)", "(c)", "(d)", "Case I:", "Case II:", "Step {i}:", "JEE Main {y}", "JEE Adv. {y}",
    "NEET {y}", "PYQ {y}", "Level {i}", "DPP {i}", "HW: Q{i} to Q{j}", "Page {n}", "Lecture {i}",
    "{q} is a {kind} quantity", "SI unit of {q} is {u}", "Dimension of {q}: {dim}", "Let {v} = {n} {u}",
    "Therefore {v} = {n} {u}", "=> {v} = {n}", "Hence proved", "Correct option is ({opt})",
    "Which of the following is correct?", "Assertion (A):", "Reason (R):", "Match the following",
    "Both A and R are true", "Consider a block of mass {m} kg", "A body is projected at {deg}° with {n} m/s",
    "The ratio of {q} is {i}:{j}", "Draw the free body diagram", "Take g = 10 m/s²", "Neglect air resistance",
]

HINGLISH = (
    "dekho yaha ab hum karenge matlab samjho sawal jawab isko dhyan se likho yaad rakhna "
    "bahut important hai toh phir chalo agla question kya hoga kaise niklega formula lagao "
    "simple hai ek baar aur revise karo concept clear hai bacchon dekhiye yeh wala"
).split()

QUANTITIES = [
    "velocity", "acceleration", "displacement", "force", "momentum", "impulse", "work", "power",
    "energy", "pressure", "density", "stress", "strain", "torque", "frequency", "wavelength",
    "current", "resistance", "potential", "capacitance", "flux", "magnetic field", "charge",
    "tension", "friction", "normal reaction", "angular velocity", "time period", "efficiency",
    "molarity", "molality", "normality", "enthalpy", "entropy", "rate constant", "half life",
]
UNITS = [
    "m", "cm", "mm", "km", "s", "ms", "kg", "g", "N", "J", "W", "Pa", "m/s", "m/s²", "km/h",
    "N/m²", "Nm", "kg m/s", "Hz", "A", "V", "Ω", "C", "F", "T", "Wb", "K", "°C", "mol", "M",
    "L", "mL", "atm", "eV", "kJ/mol", "J/K", "rad/s", "nm", "μm", "μF", "kΩ", "mA",
]
VARS = list("abcdefghkmnpqrstuvwxyzABCFGHIKLMNPQRSTVWXYZ") + list("αβγθλμπρσωΔΦ")
DIMS = ["[MLT⁻²]", "[ML²T⁻²]", "[MLT⁻¹]", "[ML⁻¹T⁻²]", "[LT⁻¹]", "[LT⁻²]", "[M⁰L⁰T⁰]", "[ML²T⁻³]"]

FORMULAS = [
    "F = ma", "v = u + at", "s = ut + ½at²", "v² = u² + 2as", "p = mv", "W = F·s cosθ", "P = W/t",
    "KE = ½mv²", "PE = mgh", "τ = r × F", "L = Iω", "I = Σmr²", "F = Gm₁m₂/r²", "g = GM/R²",
    "vₑ = √(2gR)", "T = 2π√(l/g)", "T = 2π√(m/k)", "x = A sin(ωt + φ)", "ω = 2πf", "v = fλ",
    "Y = stress/strain", "ΔL = LαΔT", "Q = mcΔT", "PV = nRT", "ΔU = Q - W", "η = 1 - T₂/T₁",
    "F = kq₁q₂/r²", "E = F/q", "V = kq/r", "C = Q/V", "C = ε₀A/d", "U = ½CV²", "V = IR",
    "R = ρL/A", "P = I²R", "F = qvB sinθ", "B = μ₀I/2πr", "ε = -dΦ/dt", "XL = ωL", "XC = 1/ωC",
    "Z = √(R² + (XL - XC)²)", "1/f = 1/v - 1/u", "n = c/v", "sin C = 1/n", "λ = h/p", "E = hν",
    "KEmax = hν - φ", "E = mc²", "N = N₀e^(-λt)", "t½ = 0.693/λ", "n₁ sin θ₁ = n₂ sin θ₂",
    "sin²θ + cos²θ = 1", "sin 2θ = 2 sinθ cosθ", "cos 2θ = cos²θ - sin²θ", "tan(A+B) = (tanA + tanB)/(1 - tanA tanB)",
    "(a + b)² = a² + 2ab + b²", "a² - b² = (a - b)(a + b)", "x = (-b ± √(b² - 4ac))/2a",
    "∫ xⁿ dx = xⁿ⁺¹/(n+1) + C", "∫ sin x dx = -cos x + C", "d/dx (sin x) = cos x", "d/dx (e^x) = e^x",
    "lim x→0 (sin x)/x = 1", "∑ n = n(n+1)/2", "nCr = n!/(r!(n-r)!)", "P(A∪B) = P(A) + P(B) - P(A∩B)",
    "|a × b| = |a||b| sinθ", "a · b = |a||b| cosθ", "y - y₁ = m(x - x₁)", "x² + y² = r²",
    "x²/a² + y²/b² = 1", "y² = 4ax", "e = c/a", "A⁻¹ = adj(A)/|A|", "ΔG = ΔH - TΔS",
    "ΔG° = -RT ln K", "E = E° - (0.0591/n) log Q", "k = Ae^(-Ea/RT)", "pH = -log[H⁺]",
    "pH + pOH = 14", "Kw = 10⁻¹⁴", "M = n/V", "π = CRT", "ΔTb = Kb·m", "PA = xA·PA°",
    "2H₂ + O₂ → 2H₂O", "CH₄ + 2O₂ → CO₂ + 2H₂O", "N₂ + 3H₂ ⇔ 2NH₃", "CaCO₃ → CaO + CO₂",
    "Zn + CuSO₄ → ZnSO₄ + Cu", "CH₃COOH", "C₆H₁₂O₆", "H₂SO₄", "KMnO₄", "K₂Cr₂O₇", "NaOH + HCl → NaCl + H₂O",
    "6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂", "ATP → ADP + Pi", "NA = 6.022 × 10²³", "h = 6.63 × 10⁻³⁴ J s",
    "e = 1.6 × 10⁻¹⁹ C", "c = 3 × 10⁸ m/s", "R = 8.314 J/mol K", "g = 9.8 m/s²", "ε₀ = 8.85 × 10⁻¹²",
    "v = √(T/μ)", "f' = f(v ± v₀)/(v ∓ vs)", "a ∝ 1/m", "F ∝ 1/r²", "∇·E = ρ/ε₀", "∂f/∂x",
    "O(n log n)", "T(n) = 2T(n/2) + n", "dp[i] = max(dp[i-1], dp[i-2] + a[i])", "if (x >= 0) { return x; }",
]


def _load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [w.strip() for w in path.read_text(encoding="utf-8", errors="ignore").splitlines() if w.strip()]


def _notes_from_db(db_path: Path) -> list[str]:
    """Pull clean text lines out of previously generated Focs notes, if the DB exists."""
    if not db_path.exists():
        return []
    try:
        con = sqlite3.connect(str(db_path))
        rows = con.execute("SELECT ai_notes FROM notes WHERE length(ai_notes) > 40").fetchall()
        con.close()
    except sqlite3.Error:
        return []
    lines: list[str] = []
    for (md,) in rows:
        for raw in (md or "").splitlines():
            line = re.sub(r"[#*`_>]+", " ", raw)
            line = normalize_text(line)
            # skip browser junk that leaked into old notes
            if 4 <= len(line) <= 60 and not re.search(r"https?:|www\.|127\.0|localhost|\.com", line):
                lines.append(line)
    return lines


class Corpus:
    def __init__(self, db_path: Path | None = None):
        self.words = [w for w in _load_lines(DATA_DIR / "english_words.txt") if w.isalpha()] or [
            "the", "of", "and", "force", "energy", "mass", "time", "value", "system", "equation"]
        self.terms = [t.strip() for t in SCIENCE_TERMS.replace("\n", "").split("|") if t.strip()]
        self.note_lines = _notes_from_db(db_path) if db_path else []
        self.formulas = [normalize_text(f) for f in FORMULAS]

    # --- individual generators -------------------------------------------------
    def _number(self, rng: np.random.Generator) -> str:
        r = rng.random()
        if r < 0.4:
            return str(int(rng.integers(0, 1000)))
        if r < 0.75:
            return f"{rng.uniform(0, 100):.{int(rng.integers(1, 3))}f}"
        if r < 0.9:
            sup = "⁰¹²³⁴⁵⁶⁷⁸⁹"
            exp = int(rng.integers(1, 35))
            sign = "⁻" if rng.random() < 0.6 else ""
            return f"{rng.uniform(1, 9.9):.2f} × 10{sign}{''.join(sup[int(d)] for d in str(exp))}"
        return f"{int(rng.integers(1, 20))}/{int(rng.integers(2, 20))}"

    def _phrase(self, rng: np.random.Generator) -> str:
        tpl = EXAM_PHRASES[int(rng.integers(len(EXAM_PHRASES)))]
        return tpl.format(
            q=QUANTITIES[int(rng.integers(len(QUANTITIES)))],
            n=self._number(rng), i=int(rng.integers(1, 30)), j=int(rng.integers(1, 30)),
            y=int(rng.integers(2005, 2027)), u=UNITS[int(rng.integers(len(UNITS)))],
            v=VARS[int(rng.integers(len(VARS)))], kind=("vector" if rng.random() < 0.5 else "scalar"),
            dim=DIMS[int(rng.integers(len(DIMS)))], opt="abcd"[int(rng.integers(4))],
            m=int(rng.integers(1, 50)), deg=int(rng.choice([15, 30, 37, 45, 53, 60, 90])),
        )

    def _equation(self, rng: np.random.Generator) -> str:
        """Random but plausible algebra: 'v = 3.5t² - 2x + 7'."""
        lhs = VARS[int(rng.integers(len(VARS)))]
        terms = []
        for _ in range(int(rng.integers(1, 4))):
            coef = "" if rng.random() < 0.3 else str(int(rng.integers(1, 20)))
            var = VARS[int(rng.integers(len(VARS)))]
            power = rng.choice(["", "", "²", "³", "⁻¹", "^2", "^n"])
            terms.append(f"{coef}{var}{power}")
        op = lambda: rng.choice([" + ", " - ", " × ", "/"])
        rhs = terms[0] + "".join(op() + t for t in terms[1:])
        if rng.random() < 0.3:
            rhs += f" {rng.choice(['+', '-'])} {self._number(rng)}"
        rel = rng.choice(["=", "=", "=", "≈", "∝", "≤", "≥", "≠", "→"])
        return f"{lhs} {rel} {rhs}"

    def _words(self, rng: np.random.Generator, hinglish: bool = False) -> str:
        pool = HINGLISH if hinglish else self.words
        n = int(rng.integers(1, 8))
        ws = [pool[int(rng.integers(len(pool)))] for _ in range(n)]
        style = rng.random()
        if style < 0.35:
            ws[0] = ws[0].capitalize()
        elif style < 0.45:
            ws = [w.upper() for w in ws]
        elif style < 0.55:
            ws = [w.capitalize() for w in ws]
        line = " ".join(ws)
        if rng.random() < 0.25:
            line += rng.choice([".", ",", ":", "?", "!", " -", ";"])
        return line

    def _soup(self, rng: np.random.Generator) -> str:
        from .charset import CHARS
        n = int(rng.integers(1, 18))
        visible = CHARS[1:]  # skip space
        return "".join(visible[int(rng.integers(len(visible)))] for _ in range(n))

    def _bullet(self, rng: np.random.Generator) -> str:
        head = rng.choice(["- ", "• ", "* ", "→ ", "1. ", "2) ", "a) ", ""])
        body = self.terms[int(rng.integers(len(self.terms)))] if rng.random() < 0.5 else self._words(rng)
        return f"{head}{body}"

    # --- public API -------------------------------------------------------------
    def _segment(self, rng: np.random.Generator) -> str:
        r = rng.random()
        if r < 0.16:
            return self.formulas[int(rng.integers(len(self.formulas)))]
        if r < 0.30:
            return self._equation(rng)
        if r < 0.44:
            return self._phrase(rng)
        if r < 0.54:
            term = self.terms[int(rng.integers(len(self.terms)))]
            return term.upper() if rng.random() < 0.3 else term
        if r < 0.72:
            return self._words(rng)
        if r < 0.76:
            return self._words(rng, hinglish=True)
        if r < 0.82:
            return self._bullet(rng)
        if r < 0.90:
            return self._soup(rng)
        if r < 0.95 and self.note_lines:
            return self.note_lines[int(rng.integers(len(self.note_lines)))]
        return self._number(rng) + (" " + UNITS[int(rng.integers(len(UNITS)))] if rng.random() < 0.6 else "")

    def sample(self, rng: np.random.Generator, max_len: int = 48, min_len: int = 1) -> str:
        """One text line whose length falls in [min_len, max_len]; segments are glued to reach min_len."""
        for _ in range(30):
            text = self._segment(rng)
            for _ in range(8):
                if len(text) >= min_len:
                    break
                sep = [" ", "  ", ", ", "; ", " - "][int(rng.integers(5))]
                text = f"{text}{sep}{self._segment(rng)}"
            text = normalize_text(text)
            if len(text) > max_len:
                head = text[:max_len]
                text = (head.rsplit(" ", 1)[0] if " " in head[min_len:] else head).strip()
            if min_len <= len(text) <= max_len and in_charset(text):
                return text
        return "F = ma"
