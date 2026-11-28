"""Draw candidate figures for the paper as SVG, then render each to PDF and PNG.

Run from the repository root:
    python3 final_paper/figures/options/make_options.py

Each figure is written as <name>.pdf, ready for \\includegraphics. Rendering
uses headless Google Chrome, so no plotting library is needed. Set the
PREVIEW environment variable to a folder to also get PNG previews there.

Where the numbers come from:
  * Group A, base vs V2: Fir eval job 4702161 (compare.md).
  * Group B v4, base vs V2: Fir eval job 6126071 (compare.md).
  * V1 and V4: Fir jobs 6466682, 6466683 and the RQ4 table in the paper.
  * Training-aligned prompt: Fir jobs 6262009 and 6466681.
  * Training data stats: data/generated/grade_first_v2.jsonl (local copy).
  * Training time and memory: Fir logs train-lora-1040737 and 4236978.
"""

import json
import os
import statistics
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PREVIEW = os.environ.get("PREVIEW")

FONT = "'Times New Roman', Times, serif"
INK, MUTE, GRID = "#1a1a1a", "#5f6368", "#e3e3e3"
BASE, OURS, V1C, V4C = "#8a9099", "#1f5fbf", "#d9822b", "#2a9d8f"
BAD, GOOD, NA = "#c8453a", "#2f8a4c", "#b9bcc2"


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=10, anchor="start", weight="normal", fill=INK, italic=False, rotate=None):
        st = "font-style:italic;" if italic else ""
        tr = f' transform="rotate({rotate} {x} {y})"' if rotate else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
                 f'font-weight="{weight}" fill="{fill}" style="{st}"{tr}>{s}</text>')

    def line(self, x1, y1, x2, y2, stroke=INK, w=1, dash=None, cap="butt", op=1):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
                 f'stroke-width="{w}" stroke-linecap="{cap}" opacity="{op}"{d}/>')

    def rect(self, x, y, w, h, fill, stroke="none", sw=1, rx=0, op=1):
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w,0):.1f}" height="{max(h,0):.1f}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}" rx="{rx}" opacity="{op}"/>')

    def circle(self, cx, cy, r, fill, stroke="none", sw=1):
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def path(self, d, fill="none", stroke="none", sw=1, op=1):
        self.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}"/>')

    def svg(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" style="font-family:{FONT}">' + "".join(self.parts) + "</svg>")


def save(name, svg, html_body=None, w=None, h=None):
    """Write the HTML source and render it to PDF and PNG."""
    w = w or svg.w
    h = h or svg.h
    body = html_body if html_body is not None else svg.svg()
    html = (f"<!doctype html><meta charset='utf-8'><title>{name}</title>"
            f"<style>@page{{size:{w}px {h}px;margin:0}}html,body{{margin:0;background:#fff}}"
            f"body{{width:{w}px;height:{h}px;overflow:hidden;font-family:{FONT};color:{INK}}}svg{{display:block}}</style>"
            + body)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"{name}.html"
        src.write_text(html)
        url = src.as_uri()
        common = [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", "--no-pdf-header-footer"]
        subprocess.run(common + [f"--print-to-pdf={HERE / (name + '.pdf')}", url], capture_output=True)
        if PREVIEW:
            subprocess.run(common + ["--force-device-scale-factor=2", f"--window-size={w},{h}",
                                     f"--screenshot={Path(PREVIEW) / (name + '.png')}", url], capture_output=True)
    print("wrote", name + ".pdf")


def legend(s, x, y, items, size=9):
    """items: list of (label, color, kind) with kind in dot, bar, line, dash."""
    for label, col, kind in items:
        if kind == "dot":
            s.circle(x + 5, y - 3, 4, col)
        elif kind == "line":
            s.line(x, y - 3, x + 14, y - 3, col, 2)
        elif kind == "dash":
            s.line(x, y - 3, x + 14, y - 3, col, 2, dash="4 2")
        else:
            s.rect(x, y - 8, 12, 9, col)
        s.text(x + 18, y, label, size, fill=INK)
        x += 18 + len(label) * size * 0.48 + 16


# ---------------------------------------------------------------- results data
LEVELS = ["Partial", "Minimal", "None", "Full"]
LEVEL_A = {"Partial": (14, 5, 13), "Minimal": (18, 9, 18), "None": (38, 33, 33), "Full": (59, 58, 59)}
LEVEL_B = {"Partial": (73, 52, 60), "Minimal": (34, 22, 29), "None": (40, 38, 39), "Full": (177, 173, 168)}
TOPIC_A = [("Regular expressions", 15, 9, 13), ("DFAs and NFAs", 15, 11, 14), ("Complete induction", 20, 16, 20),
           ("Program correctness", 15, 12, 15), ("Asymptotic analysis", 15, 13, 15),
           ("Structural induction", 19, 16, 18), ("Recurrences", 15, 14, 15), ("Simple induction", 15, 14, 13)]
RQ3 = [("Sensitivity", "catches a removed step or added error", 13, 9, 13),
       ("Fairness", "same grade despite typos", 10, 9, 8),
       ("Paraphrase", "same grade for reworded answers", 7, 4, 3),
       ("Robustness", "ignores embedded instructions", 12, 12, 12)]
TESTTYPE_B = [("Fairness", 31, 29, 31), ("Sensitivity", 42, 35, 37), ("Paraphrase", 56, 43, 45),
              ("Original", 155, 141, 145), ("Robustness", 40, 37, 38)]
ABL = [("Base model", 81.4, 88.0, BASE), ("V1  stage 1 only", 75.2, 77.5, V1C),
       ("V4  stage 2 only", 95.3, 90.4, V4C), ("V2  both stages (GradeAI)", 95.3, 91.4, OURS)]


def fig_forest():
    """Paired bootstrap differences (GradeAI minus base) with 95% intervals."""
    rows = [("Group A", "Exact agreement (points)", 14.0, 5.6, 22.7, False),
            ("Group A", "QWK (x100)", 10.0, 3.7, 18.9, False),
            ("Group A", "Mean abs. error (x100, lower is better)", -22.7, -36.2, -10.1, True),
            ("Group A", "Signed error (x100)", -11.8, -25.8, 1.6, None),
            ("Group A", "Format compliance (points)", 5.0, 0.0, 12.5, False),
            ("Group B v4", "Exact agreement (points)", 3.4, -0.3, 7.1, False),
            ("Group B v4", "Signed error (x100)", -9.0, -15.0, -4.0, None),
            ("Group B v4", "Sensitivity cases caught (points)", 31.0, 7.0, 56.0, False)]
    s = Svg(624, 318)
    s.text(0, 14, "Change from the base model to GradeAI, with paired 95% bootstrap intervals", 12, weight="bold")
    s.text(0, 29, "Intervals that touch or cross zero (grey) are not significant. For both error rows, negative is better.", 9.5, fill=MUTE)
    x0, x1, lo, hi = 300, 600, -40, 60
    X = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    top, rh = 56, 27
    for v in range(-40, 61, 20):
        s.line(X(v), top - 8, X(v), top + rh * len(rows) + 2, GRID if v else "#9a9a9a", 1 if v else 1.2)
        s.text(X(v), top + rh * len(rows) + 8, f"{v:+d}" if v else "0", 9, "middle", fill=MUTE)
    grp = None
    for i, (g, m, est, a, b, lower_better) in enumerate(rows):
        y = top + i * rh + (16 if g == "Group B v4" else 0)
        if g != grp:
            s.text(0, y - 10, g, 10, weight="bold")
            grp = g
        s.text(10, y + 4, m, 9.5)
        sig = a > 0 or b < 0
        col = OURS if sig else NA
        s.line(X(a), y, X(b), y, col, 2.2, cap="round")
        s.line(X(a), y - 4, X(a), y + 4, col, 1.5)
        s.line(X(b), y - 4, X(b), y + 4, col, 1.5)
        s.rect(X(est) - 4, y - 4, 8, 8, col)
        s.text(X(b) + 7, y + 4, f"{est:+.1f}", 9, fill=INK if sig else MUTE)
    s.text((x0 + x1) / 2, top + rh * len(rows) + 24, "Difference, GradeAI minus base", 9.5, "middle")
    save("01_forest_gains", s)


def fig_verdict():
    cols = ["Group A\naccuracy", "Group B\naccuracy", "Paraphrase\nconsistent", "Fairness\nidentical",
            "Sensitivity\ndetected", "Robustness\npassed"]
    data = {
        "Base model": [(81.4, 80), (88.0, 80), (4 / 7 * 100, 90, "4/7"), (90, None, "9/10"), (9 / 13 * 100, None, "9/13"), (100, None, "12/12")],
        "V1  stage 1 only": [(75.2, 80), (77.5, 80), None, None, None, (42, None, "42%")],
        "V4  stage 2 only": [(95.3, 80), (90.4, 80), None, None, None, None],
        "GradeAI (V2)": [(95.3, 80), (91.4, 80), (3 / 7 * 100, 90, "3/7"), (80, None, "8/10"), (100, None, "13/13"), (100, None, "12/12")],
    }
    s = Svg(624, 250)
    s.text(0, 14, "Every model against every target", 12, weight="bold")
    s.text(0, 29, "Green meets the target (80% accuracy, 90% paraphrase consistency). Red misses it. Blue shades show"
           " tests without a target, darker is better.", 9, fill=MUTE)
    x0, cw, ch, y0 = 150, 77, 36, 74
    for j, c in enumerate(cols):
        for k, part in enumerate(c.split("\n")):
            s.text(x0 + j * cw + cw / 2, y0 - 22 + k * 11, part, 9, "middle", "bold")
    for i, (name, cells) in enumerate(data.items()):
        y = y0 + i * (ch + 5)
        s.text(0, y + ch / 2 + 4, name, 10, weight="bold" if "GradeAI" in name else "normal")
        for j, cell in enumerate(cells):
            x = x0 + j * cw
            if cell is None:
                s.rect(x + 2, y, cw - 4, ch, "#f4f4f4", "#dddddd", 1, 3)
                s.text(x + cw / 2, y + ch / 2 + 3, "not shown", 8, "middle", fill="#9a9a9a", italic=True)
                continue
            val, target = cell[0], cell[1]
            label = cell[2] if len(cell) > 2 else f"{val:.1f}%"
            if target is not None:
                ok = val >= target
                fill, stroke, tc = ("#dcefe2", GOOD, GOOD) if ok else ("#f7dcd8", BAD, BAD)
                word = "PASS" if ok else "FAIL"
            else:
                t = val / 100
                fill = f"rgba(31,95,191,{0.12 + 0.6 * t:.2f})"
                stroke, tc, word = "#9fb4d8", "#ffffff" if t > 0.75 else INK, ""
            s.rect(x + 2, y, cw - 4, ch, fill, stroke, 1.2, 3)
            if word:
                s.text(x + cw / 2, y + 15, word, 9.5, "middle", "bold", tc)
                s.text(x + cw / 2, y + 28, label, 9, "middle", fill=INK)
            else:
                s.text(x + cw / 2, y + ch / 2 + 4, label, 10, "middle", "bold", tc)
    s.text(0, 246, "Group B v4 for all invariance columns. Other V1 and V4 invariance results are not in the paper yet.",
           8.5, fill=MUTE, italic=True)
    save("02_verdict_matrix", s)


def fig_ablation_bars():
    s = Svg(624, 250)
    s.text(0, 14, "Ablation: what each training stage contributes", 12, weight="bold")
    s.text(0, 29, "Exact criterion agreement. Dashed line is the 80% target.", 9.5, fill=MUTE)
    lo, hi, y0, y1 = 60, 100, 200, 46
    Y = lambda v: y0 - (v - lo) / (hi - lo) * (y0 - y1)
    for v in range(60, 101, 10):
        s.line(48, Y(v), 610, Y(v), GRID)
        s.text(42, Y(v) + 3, f"{v}%", 9, "end", fill=MUTE)
    s.line(48, Y(80), 610, Y(80), BAD, 1.2, dash="5 3")
    groups = [("Group A (training questions)", 1), ("Group B v4 (new questions)", 2)]
    bw = 44
    for gi, (gname, idx) in enumerate(groups):
        gx = 90 + gi * 275
        for k, row in enumerate(ABL):
            v, col = row[idx], row[3]
            x = gx + k * (bw + 12)
            s.rect(x, Y(v), bw, y0 - Y(v), col, rx=2)
            s.text(x + bw / 2, Y(v) - 5, f"{v:.1f}", 9.5, "middle", "bold")
        s.text(gx + 2 * (bw + 12) - 6, y0 + 16, gname, 10, "middle", "bold")
    legend(s, 40, 240, [(r[0], r[3], "bar") for r in ABL], 9)
    save("03_ablation_bars", s)


def fig_dumbbell():
    s = Svg(624, 236)
    s.text(0, 14, "Accuracy by the correct grade level", 12, weight="bold")
    s.text(0, 29, "Grey: base model. Blue: GradeAI. Almost all of the gain is on partial and minimal criteria.", 9.5, fill=MUTE)
    for gi, (title, D) in enumerate([("Group A (training questions)", LEVEL_A), ("Group B v4 (new questions)", LEVEL_B)]):
        ox = gi * 318
        X0, W, lo = ox + 66, 220, 30
        X = lambda v: X0 + (v - lo) / (100 - lo) * W
        T, R = 72, 36
        s.text(ox, 52, title, 10.5, weight="bold")
        for v in range(30, 101, 10):
            s.line(X(v), T - 12, X(v), T + 3 * R + 12, GRID)
            s.text(X(v), T + 3 * R + 24, f"{v}", 8.5, "middle", fill=MUTE)
        for i, lv in enumerate(LEVELS):
            n, b, o = D[lv]
            y, pb, po = T + i * R, b / n * 100, o / n * 100
            s.text(ox, y + 3, lv, 10)
            s.text(ox, y + 14, f"n = {n}", 8, fill=MUTE)
            col = OURS if po >= pb else BAD
            if abs(po - pb) > 1:
                s.line(X(pb), y, X(po), y, col, 2.5, op=0.45)
            s.circle(X(pb), y, 4.5, BASE, "#fff", 1.2)
            s.circle(X(po), y, 4.5, OURS, "#fff", 1.2)
            d = int(po - pb + 0.5) if po >= pb else -int(pb - po + 0.5)
            s.text(X(max(pb, po)) + 9, y + 3.5, (f"{d:+d}" if d else "0"), 9, weight="bold",
                   fill=OURS if d > 0 else BAD if d < 0 else MUTE)
        s.text(X0 + W / 2, T + 3 * R + 36, "Criteria graded correctly (%)", 9, "middle")
    save("04_level_dumbbell", s)


def fig_tiles():
    s = Svg(624, 262)
    s.text(0, 14, "Every Group A criterion, one square each", 12, weight="bold")
    s.text(0, 29, "Filled: same level as the reference label. Outlined with a cross: a different level.", 9.5, fill=MUTE)
    X0, S, G, y = 92, 7, 1.4, 50
    for lv in ["Full", "None", "Minimal", "Partial"]:
        n, b, o = LEVEL_A[lv]
        s.text(0, y + 11, lv, 10.5, weight="bold")
        s.text(0, y + 23, f"{n} criteria", 8.5, fill=MUTE)
        for k, (nm, r, col) in enumerate([("Base", b, BASE), ("GradeAI", o, OURS)]):
            yy = y + k * (S + 4)
            s.text(X0 - 6, yy + S - 0.5, nm, 8, "end", fill=MUTE)
            for i in range(n):
                x = X0 + i * (S + G)
                if i < r:
                    s.rect(x, yy, S, S, col, rx=1)
                else:
                    s.rect(x + .5, yy + .5, S - 1, S - 1, "#fff", BAD, 1, 1)
                    s.line(x + 1.8, yy + 1.8, x + S - 1.8, yy + S - 1.8, BAD, 1)
                    s.line(x + S - 1.8, yy + 1.8, x + 1.8, yy + S - 1.8, BAD, 1)
            s.text(X0 + n * (S + G) + 5, yy + S - 0.5, f"{r}/{n}", 8.5, weight="bold" if k else "normal",
                   fill=OURS if k else MUTE)
        y += 48
    s.text(0, y + 8, "Base model: 24 of 129 criteria wrong. GradeAI: 6 wrong.", 9.5)
    save("05_criterion_tiles", s)


def fig_pips():
    s = Svg(624, 228)
    s.text(0, 14, "Invariance tests (RQ3), one circle per test case", 12, weight="bold")
    s.text(0, 29, "Filled: passed. Hollow: failed. Group B v4.", 9.5, fill=MUTE)
    y, X0, P = 56, 260, 15
    for i, (nm, d, n, b, o) in enumerate(RQ3):
        if i == 0:
            s.rect(-2, y - 13, 626, 40, "#eef2fa", rx=3)
        s.text(4, y + 1, nm, 10.5, weight="bold")
        s.text(4, y + 13, d, 8.5, fill=MUTE, italic=True)
        for k, (m, p, col) in enumerate([("Base", b, BASE), ("GradeAI", o, OURS)]):
            yy = y - 3 + k * 15
            s.text(X0 - 8, yy + 3, m, 8.5, "end", fill=MUTE)
            for j in range(n):
                s.circle(X0 + j * P, yy, 5, col if j < p else "#fff", col, 1.2)
            s.text(X0 + n * P + 4, yy + 3.5, f"{p}/{n}", 9, weight="bold" if k else "normal", fill=OURS if k else MUTE)
        y += 40
    s.text(0, 222, "Only the sensitivity change is significant (paired interval +7 to +56 points).", 9, fill=MUTE, italic=True)
    save("06_invariance_pips", s)


def fig_topics():
    s = Svg(624, 268)
    s.text(0, 14, "Group A accuracy by topic", 12, weight="bold")
    s.text(0, 29, "Arrow from the base model to GradeAI, sorted by gain.", 9.5, fill=MUTE)
    X0, W, lo, T, R = 140, 370, 50, 54, 25
    X = lambda v: X0 + (v - lo) / (100 - lo) * W
    for v in range(50, 101, 10):
        s.line(X(v), T - 12, X(v), T + R * 7 + 10, GRID)
        s.text(X(v), T + R * 7 + 22, f"{v}%", 8.5, "middle", fill=MUTE)
    for i, (t, n, b, o) in enumerate(TOPIC_A):
        y, pb, po = T + i * R, b / n * 100, o / n * 100
        up = po > pb
        col = OURS if up else BAD
        s.text(0, y + 3.5, t, 10)
        tip = X(po)
        back = tip - 8 if up else tip + 8
        s.line(X(pb), y, back, y, col, 4, cap="round", op=.9)
        s.path(f"M{back} {y-5} L{tip} {y} L{back} {y+5}Z", fill=col)
        s.text(max(X(pb), X(po)) + 10, y + 3.5, f"{b} to {o} of {n}", 8.5, fill=MUTE)
    save("07_topic_arrows", s)


def fig_training_time():
    s = Svg(624, 170)
    s.text(0, 14, "Training cost of the final adapter on one H100", 12, weight="bold")
    s.text(0, 29, "Stage 1 takes about three quarters of the time. The ablation shows it adds at most 1 point.", 9.5, fill=MUTE)
    total = 344 + 101
    X = lambda m: 10 + m / total * 600
    y = 50
    s.add('<defs><pattern id="h" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
          '<rect width="6" height="6" fill="#eef0f3"/><line x1="0" y1="0" x2="0" y2="6" stroke="#b5bac2" stroke-width="2"/></pattern></defs>')
    s.rect(X(0), y, X(344) - X(0) - 2, 30, "url(#h)", "#9aa0a8", 1)
    s.rect(X(344), y, X(total) - X(344), 30, OURS)
    s.text((X(0) + X(344)) / 2, y + 13, "Stage 1: course notes", 10, "middle", "bold")
    s.text((X(0) + X(344)) / 2, y + 25, "8,862 steps, 5 h 44 min", 9, "middle")
    s.text((X(344) + X(total)) / 2, y + 13, "Stage 2: grading", 9.5, "middle", "bold", "#fff")
    s.text((X(344) + X(total)) / 2, y + 25, "2,048 steps, 1 h 41 min", 8.5, "middle", fill="#fff")
    for hr in range(0, 8):
        s.line(X(hr * 60), y + 32, X(hr * 60), y + 36, MUTE)
        s.text(X(hr * 60), y + 46, f"{hr} h", 8.5, "middle", fill=MUTE)
    y2 = 122
    s.text(10, y2, "Peak GPU memory", 10, weight="bold")
    gx, gw = 130, 440
    s.rect(gx, y2 - 10, gw, 13, "#f1f1f1", "#c9c9c9", 1)
    s.rect(gx, y2 - 10, gw * 55.5 / 80, 13, "#5d6d7e")
    s.text(gx + gw * 55.5 / 80 - 4, y2, "55 to 56 GiB", 8.5, "end", fill="#fff", weight="bold")
    s.text(gx + gw + 4, y2, "80 GiB", 8.5, fill=MUTE)
    s.text(10, y2 + 26, "LoRA rank 16 on attention and MLP projections: 116.7M trainable parameters (0.42% of the model).",
           9, fill=MUTE, italic=True)
    save("08_training_cost", s)


# ------------------------------------------------------------- training data
def load_training():
    path = ROOT / "data/generated/grade_first_v2.jsonl"
    rows = [json.loads(l) for l in open(path)]

    def answer(r):
        q = r["question"]
        i = q.rfind("Student Answer:")
        return q[i + 15:].strip() if i >= 0 else ""
    return rows, answer


TOPIC_NAMES = {"induction_simple": "Simple induction", "induction_complete": "Complete induction",
               "structural_induction": "Structural induction", "recurrences": "Recurrences",
               "asymptotic_analysis": "Asymptotic analysis", "program_correctness": "Program correctness",
               "regex": "Regular expressions", "dfa_nfa": "DFAs and NFAs"}
LVCOL = {"full": "#1f5fbf", "partial": "#7aa3e0", "minimal": "#f0b07a", "none": "#c8453a"}


def stacked_row(s, x, y, w, h, counts, order, label_min=0.06):
    tot = sum(counts.get(k, 0) for k in order)
    cx = x
    for k in order:
        f = counts.get(k, 0) / tot
        s.rect(cx, y, w * f - 1.2, h, LVCOL[k])
        if f >= label_min:
            s.text(cx + w * f / 2, y + h / 2 + 3.5, f"{f*100:.0f}%", 8.5, "middle",
                   fill="#fff" if k in ("full", "none") else INK)
        cx += w * f
    return tot


def fig_training_levels():
    rows, _ = load_training()
    by = {}
    for r in rows:
        for v in json.loads(r["target_json"]).values():
            by.setdefault(r["topic"], {}).setdefault(v, 0)
            by[r["topic"]][v] += 1
    order = ["full", "partial", "minimal", "none"]
    s = Svg(624, 290)
    s.text(0, 14, "Target levels in the grade-first training data, by topic", 12, weight="bold")
    s.text(0, 29, f"Every criterion of every training answer ({len(rows):,} answers). Levels are chosen by code before"
           " the answer is written.", 9.5, fill=MUTE)
    topics = sorted(by, key=lambda t: by[t].get("full", 0) / sum(by[t].values()))
    y = 48
    for t in topics:
        s.text(0, y + 12, TOPIC_NAMES[t], 10)
        n = stacked_row(s, 140, y, 430, 17, by[t], order)
        s.text(578, y + 12, f"{n}", 8.5, fill=MUTE)
        y += 25
    s.text(578, 44, "criteria", 8, fill=MUTE)
    legend(s, 140, y + 16, [("Full", LVCOL["full"], "bar"), ("Partial", LVCOL["partial"], "bar"),
                            ("Minimal", LVCOL["minimal"], "bar"), ("None", LVCOL["none"], "bar")])
    save("09_training_levels_by_topic", s)


def fig_level_mix():
    rows, _ = load_training()
    tr = {}
    for r in rows:
        for v in json.loads(r["target_json"]).values():
            tr[v] = tr.get(v, 0) + 1
    sets = [("Training data", tr), ("Group A test set", {k.lower(): v[0] for k, v in LEVEL_A.items()}),
            ("Group B v4 test set", {k.lower(): v[0] for k, v in LEVEL_B.items()})]
    order = ["full", "partial", "minimal", "none"]
    s = Svg(624, 150)
    s.text(0, 14, "Mix of correct levels: training data vs the two test sets", 12, weight="bold")
    s.text(0, 29, "Full credit is about half of every set. Group A has more none criteria, Group B more partial ones.",
           9.5, fill=MUTE)
    y = 46
    for nm, c in sets:
        s.text(0, y + 13, nm, 10)
        n = stacked_row(s, 130, y, 440, 19, c, order)
        s.text(578, y + 13, f"{n:,}", 8.5, fill=MUTE)
        y += 28
    legend(s, 130, y + 14, [("Full", LVCOL["full"], "bar"), ("Partial", LVCOL["partial"], "bar"),
                            ("Minimal", LVCOL["minimal"], "bar"), ("None", LVCOL["none"], "bar")])
    save("10_level_mix", s)


def fig_length():
    rows, answer = load_training()
    g = {}
    for r in rows:
        t = json.loads(r["target_json"])
        k = min(sum(v != "full" for v in t.values()), 3)
        g.setdefault(k, []).append(len(answer(r).split()))
    s = Svg(624, 250)
    s.text(0, 14, "A possible shortcut: flawed training answers are shorter", 12, weight="bold")
    s.text(0, 29, "Words per training answer by how many criteria are below full. Box: middle half. Line: median."
           " Whiskers: 5th to 95th percentile.", 9, fill=MUTE)
    lo, hi, y0, y1 = 0, 650, 210, 46
    Y = lambda v: y0 - (v - lo) / (hi - lo) * (y0 - y1)
    for v in range(0, 651, 100):
        s.line(50, Y(v), 610, Y(v), GRID)
        s.text(44, Y(v) + 3, f"{v}", 8.5, "end", fill=MUTE)
    s.text(14, (y0 + y1) / 2, "Words", 9.5, "middle", rotate=-90)
    labels = ["0 (all full)", "1", "2", "3 or more"]
    for k in range(4):
        v = sorted(g[k])
        q1, med, q3 = statistics.quantiles(v, n=4)
        p5, p95 = v[int(.05 * len(v))], v[int(.95 * len(v))]
        cx = 130 + k * 125
        col = OURS
        s.line(cx, Y(p5), cx, Y(q1), col, 1.2)
        s.line(cx, Y(q3), cx, Y(p95), col, 1.2)
        s.line(cx - 10, Y(p5), cx + 10, Y(p5), col, 1.2)
        s.line(cx - 10, Y(p95), cx + 10, Y(p95), col, 1.2)
        s.rect(cx - 28, Y(q3), 56, Y(q1) - Y(q3), "#dbe6f7", col, 1.2)
        s.line(cx - 28, Y(med), cx + 28, Y(med), col, 2.4)
        s.text(cx + 33, Y(med) + 3.5, f"{med:.0f}", 9, weight="bold")
        s.text(cx, y0 + 15, labels[k], 9.5, "middle")
        s.text(cx, y0 + 27, f"n = {len(v)}", 8, "middle", fill=MUTE)
    s.text(330, y0 + 40, "Criteria below full in the answer", 9.5, "middle")
    save("11_answer_length", s)


def fig_prompt_tradeoff():
    pts = [("A", "eval-prompt-v3", 95.3, 100), ("A", "train-v1", 97.7, 85),
           ("B", "eval-prompt-v3", 91.4, 100), ("B", "train-v1", 85.2, 59)]
    s = Svg(624, 260)
    s.text(0, 14, "Prompt layout: accuracy vs well-formed replies", 12, weight="bold")
    s.text(0, 29, "GradeAI with the evaluation prompt (circle) and a prompt laid out like the training data (square).",
           9.5, fill=MUTE)
    x0, x1, y0, y1 = 70, 575, 220, 46
    X = lambda v: x0 + (v - 50) / 50 * (x1 - x0)
    Y = lambda v: y0 - (v - 80) / 20 * (y0 - y1)
    for v in range(50, 101, 10):
        s.line(X(v), y1, X(v), y0, GRID)
        s.text(X(v), y0 + 13, f"{v}%", 8.5, "middle", fill=MUTE)
    for v in range(80, 101, 5):
        s.line(x0, Y(v), x1, Y(v), GRID)
        s.text(x0 - 6, Y(v) + 3, f"{v}%", 8.5, "end", fill=MUTE)
    s.text((x0 + x1) / 2, y0 + 30, "Replies in the expected format", 9.5, "middle")
    s.text(18, (y0 + y1) / 2, "Exact criterion agreement", 9.5, "middle", rotate=-90)
    for g, col in [("A", OURS), ("B", V1C)]:
        a, b = [p for p in pts if p[0] == g]
        s.line(X(a[3]), Y(a[2]), X(b[3]), Y(b[2]), col, 1.4, dash="4 3")
        s.circle(X(a[3]), Y(a[2]), 6, col, "#fff", 1.2)
        s.rect(X(b[3]) - 5.5, Y(b[2]) - 5.5, 11, 11, col)
        s.text(X(a[3]), Y(a[2]) + 18, f"Group {g}, {a[2]}%", 9, "middle", weight="bold")
        s.text(X(b[3]), Y(b[2]) - 11, f"Group {g}, {b[2]}%", 9, "middle", weight="bold")
    s.text(X(59), Y(85.2) + 20, "21 criteria graded twice", 8.5, "middle", fill=MUTE, italic=True)
    save("12_prompt_tradeoff", s)


def fig_audit():
    s = Svg(624, 170)
    s.text(0, 14, "How often a grade-first label is wrong: audit of 129 Group A criteria", 12, weight="bold")
    s.text(0, 29, "AI-assisted audit with a team member deciding flagged cases; not verified end to end by a person.",
           9.5, fill=MUTE, italic=True)
    cols, S, G, x0, y0 = 43, 11, 2.5, 10, 46
    special = {0: ("down", BAD), 1: ("down", BAD), 2: ("up", V1C)}
    reason = set(range(3, 9))
    for i in range(129):
        r, c = divmod(i, cols)
        x, y = x0 + c * (S + G), y0 + r * (S + G)
        if i in special:
            s.rect(x, y, S, S, special[i][1], rx=2)
        elif i in reason:
            s.rect(x, y, S, S, "#9fb7e6", rx=2)
        else:
            s.rect(x, y, S, S, OURS, rx=2, op=.85)
    ly = y0 + 3 * (S + G) + 20
    legend(s, 10, ly, [("Level confirmed (120)", OURS, "bar"), ("Level confirmed, reason corrected (6)", "#9fb7e6", "bar"),
                       ("Level lowered (2)", BAD, "bar"), ("Level raised (1)", V1C, "bar")], 9)
    s.text(10, ly + 22, "126 of 129 levels unchanged (97.7%, QWK 0.986). All three changes are where the teacher,"
           " not code, decides the level.", 9.5)
    save("13_label_audit", s)


def fig_testtype_b():
    s = Svg(624, 200)
    s.text(0, 14, "Group B v4 criterion accuracy by test type", 12, weight="bold")
    s.text(0, 29, "Grey: base model. Blue: GradeAI. Criterion level, so these differ from the case-level counts.", 9.5,
           fill=MUTE)
    X0, W, lo, T, R = 120, 420, 70, 56, 26
    X = lambda v: X0 + (v - lo) / (100 - lo) * W
    for v in range(70, 101, 5):
        s.line(X(v), T - 12, X(v), T + R * 4 + 10, GRID)
        s.text(X(v), T + R * 4 + 22, f"{v}%", 8.5, "middle", fill=MUTE)
    for i, (nm, n, b, o) in enumerate(TESTTYPE_B):
        y, pb, po = T + i * R, b / n * 100, o / n * 100
        s.text(0, y + 3.5, nm, 10)
        s.text(0, y + 13, f"{n} criteria", 7.5, fill=MUTE)
        s.line(X(pb), y, X(po), y, OURS, 2.4, op=.45)
        s.circle(X(pb), y, 4.5, BASE, "#fff", 1.2)
        s.circle(X(po), y, 4.5, OURS, "#fff", 1.2)
        s.text(X(po) + 9, y + 3.5, f"{b} to {o}", 8.5, fill=MUTE)
    save("14_testtype_b", s)


def fig_funnel():
    s = Svg(624, 190)
    s.text(0, 14, "Building Group A from a separate grade-first run", 12, weight="bold")
    s.text(0, 29, "Bar length is the number of answers. Exclusions can overlap, so they add up to more than 35.",
           9.5, fill=MUTE)
    stages = [("Candidate answers", 454, "for the 48 seed questions"), ("Eligible pool", 419, "after exclusions"),
              ("Group A", 40, "5 per topic, all four levels")]
    X0, W, y = 130, 330, 52
    for i, (nm, n, sub) in enumerate(stages):
        s.text(0, y + 12, nm, 10, weight="bold")
        s.rect(X0, y, W * n / 454, 18, OURS if i == 2 else "#9fb7e6", rx=2)
        s.text(X0 + W * n / 454 + 6, y + 13, f"{n}", 11, weight="bold")
        s.text(X0 + W * n / 454 + 34, y + 13, sub, 9, fill=MUTE)
        y += 32
    ex = [(12, "duplicate a training answer"), (24, "level never confirmed"), (18, "near-duplicates"),
          (5, "minimal pairs with training answers")]
    s.text(0, y + 12, "Excluded", 10, weight="bold")
    cx = X0
    for n, t in ex:
        s.rect(cx, y + 2, W * n / 454, 12, BAD, rx=1)
        cx += W * n / 454 + 3
    s.text(cx + 6, y + 12, "; ".join(f"{n} {t}" for n, t in ex), 8.5, fill=MUTE)
    save("15_groupA_funnel", s)


# ------------------------------------------------------------- HTML figures
def fig_redpen():
    body = """
<style>
.wrap{padding:6px 4px;font-family:'Times New Roman',Times,serif}
h1{font-size:15px;margin:0 0 2px}.sub{font-size:11.5px;color:#5f6368;margin-bottom:10px}
.row{display:flex;gap:10px;align-items:stretch}
.pg{flex:1;border:1px solid #c9c9c9;padding:8px 10px 8px 10px;position:relative}
.hd{font-size:11px;font-weight:bold;border-bottom:1px solid #ddd;padding-bottom:4px;margin-bottom:6px;display:flex;justify-content:space-between}
.code{font:10.5px/15px Menlo,Consolas,monospace}
.dim{color:#9a9a9a}.del{color:#c8453a;text-decoration:line-through}.ins{background:#fde6d8}
.crit{display:flex;justify-content:space-between;align-items:flex-start;border-left:3px solid #1f5fbf;padding-left:8px;margin:4px 0}
.crit.bad{border-left-color:#c8453a}
.g{font:bold 11px 'Times New Roman',serif;white-space:nowrap;margin-left:8px}
.g.ok{color:#1f5fbf}.g.no{color:#c8453a}
.mid{width:86px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-size:10.5px;color:#333}
.tg{background:#1f5fbf;color:#fff;font-weight:bold;padding:4px 6px;border-radius:2px;margin-bottom:6px}
.ar{font-size:22px;color:#1f5fbf;line-height:1}
</style>
<div class="wrap">
<h1>Grade first, then write: one real pair from the training data</h1>
<div class="sub">induction_simple_01, answers a02 (reference) and a22. Code chooses the target level for each criterion; the teacher
then rewrites only the lines that criterion depends on. Unchanged lines are shortened here.</div>
<div class="row">
<div class="pg"><div class="hd"><span>Reference answer</span><span>10 / 10</span></div>
<div class="crit"><div class="code">We define the predicate P(n) as:<br>&nbsp;&nbsp;3 divides 4^n - 1.<br>Base case: We verify P(0).<br>4^0 - 1 = 1 - 1 = 0.<br>Since 0 = 3 * 0, P(0) is true.</div><span class="g ok">C1 full 3/3</span></div>
<div class="crit"><div class="code dim">Induction Hypothesis:<br>Let k be an arbitrary integer in N.<br>We assume that P(k) is true. ...</div><span class="g ok">C2 full 3/3</span></div>
<div class="crit"><div class="code dim">Inductive Step:<br>4^(k+1) - 1 = 4(4^k - 1) + 3<br>= 4(3m) + 3 = 3(4m + 1). ...</div><span class="g ok">C3 full 4/4</span></div>
</div>
<div class="mid"><div class="tg">C1: minimal</div><div class="ar">&#10142;</div><div>target set by code before any text is written</div></div>
<div class="pg"><div class="hd"><span>Rewritten answer</span><span>8 / 10</span></div>
<div class="crit bad"><div class="code"><span class="del">We define the predicate P(n) as:</span><br><span class="del">&nbsp;&nbsp;3 divides 4^n - 1.</span><br><span class="del">Base case: We verify P(0).</span><br><span class="ins">Base case:</span><br><span class="ins">We check n = 1.</span><br><span class="ins">4^1 - 1 = 3.</span></div><span class="g no">C1 minimal 1/3</span></div>
<div class="crit"><div class="code dim">Induction Hypothesis:<br>Let k be an arbitrary integer in N.<br>We assume that P(k) is true. ...</div><span class="g ok">C2 full 3/3</span></div>
<div class="crit"><div class="code dim">Inductive Step:<br>4^(k+1) - 1 = 4(4^k - 1) + 3<br>= 4(3m) + 3 = 3(4m + 1). ...</div><span class="g ok">C3 full 4/4</span></div>
</div></div>
<div class="sub" style="margin-top:8px">Teacher's reason for C1: "The student checks n = 1 instead of the required base case n = 0."</div>
</div>"""
    save("16_grade_first_example", None, body, 760, 330)


def fig_subway():
    s = Svg(680, 300)
    s.text(8, 16, "The GradeAI pipeline as a line map", 12, weight="bold")
    s.text(8, 31, "Real counts at each stop. The knowledge line joins the grading line because stage 2 starts from the"
           " stage 1 adapter.", 9.5, fill=MUTE)
    K, G, T = "#d9a12b", OURS, "#2f8a4c"
    W = 7
    def ln(d, c):
        s.add(f'<path d="{d}" stroke="{c}" stroke-width="{W}" fill="none" stroke-linejoin="round" stroke-linecap="round"/>')
    ln("M60 80 H280 Q300 80 310 95 L330 125", K)
    ln("M60 170 H250 Q270 170 290 150 L330 125 H560 Q585 125 595 150 L620 240", G)
    ln("M170 178 V240 H330", T)
    ln("M450 240 H620", T)
    def st(x, y, top, big="", bot="", inter=False):
        s.circle(x, y, 9 if inter else 6, "#fff", INK, 3 if inter else 2.5)
        if top: s.text(x, y - 14, top, 9.5, "middle", "bold")
        if big: s.text(x, y + 21, big, 11, "middle", "bold")
        if bot: s.text(x, y + (33 if big else 21), bot, 8.5, "middle", fill=MUTE)
    st(60, 80, "CSC236 notes", "", "5 knowledge entries")
    st(170, 80, "Knowledge Q&A", "76", "seed pairs")
    st(280, 80, "Stage 1", "", "8,862 steps")
    st(60, 170, "Seed questions", "48", "with rubrics")
    st(170, 170, "Grade first", "", "", True)
    s.text(180, 196, "levels set by code", 8.5, fill=MUTE)
    st(330, 125, "", "", "", True)
    st(440, 125, "Graded answers", "1,948", "after cleaning")
    st(560, 125, "Stage 2", "", "2,048 steps")
    st(330, 240, "Group A", "40", "held-out answers")
    st(450, 240, "Group B v4", "101", "new questions, separate labels")
    st(620, 240, "", "GradeAI", "95.3% / 91.4%", True)
    for i, (c, t) in enumerate([(K, "Knowledge line"), (G, "Grading line"), (T, "Test line")]):
        s.rect(20 + i * 130, 282, 22, 6, c, rx=3)
        s.text(48 + i * 130, 289, t, 9.5)
    save("17_pipeline_line_map", s)


# ------------------------------------------------------------- non-bar forms
LEVEL_ORDER = ["full", "partial", "minimal", "none"]


def training_tables():
    rows, answer = load_training()
    lv = {}      # topic -> level -> criteria
    flaws = {}   # topic -> number of criteria below full (capped at 3) -> answers
    pts = []     # (words, share of criteria at full, criteria below full)
    for r in rows:
        t = json.loads(r["target_json"])
        for v in t.values():
            lv.setdefault(r["topic"], {}).setdefault(v, 0)
            lv[r["topic"]][v] += 1
        nf = sum(v != "full" for v in t.values())
        flaws.setdefault(r["topic"], {}).setdefault(min(nf, 3), 0)
        flaws[r["topic"]][min(nf, 3)] += 1
        pts.append((len(answer(r).split()), 1 - nf / len(t), min(nf, 3)))
    return rows, lv, flaws, pts


def fig_heatmap():
    _, lv, _, _ = training_tables()
    topics = sorted(lv, key=lambda t: -lv[t].get("full", 0) / sum(lv[t].values()))
    s = Svg(624, 290)
    s.text(0, 14, "Training criteria by topic and target level", 12, weight="bold")
    s.text(0, 29, "Cell shade is the share of that topic's criteria at each level; the number is the count.", 9.5, fill=MUTE)
    x0, y0, cw, ch = 150, 62, 92, 26
    for j, l in enumerate(LEVEL_ORDER):
        s.text(x0 + j * cw + cw / 2, y0 - 8, l.capitalize(), 10, "middle", "bold")
    for i, t in enumerate(topics):
        tot = sum(lv[t].values())
        s.text(x0 - 8, y0 + i * ch + ch / 2 + 4, TOPIC_NAMES[t], 10, "end")
        for j, l in enumerate(LEVEL_ORDER):
            n = lv[t].get(l, 0)
            f = n / tot
            a = min(1, f / 0.6)
            s.rect(x0 + j * cw + 1, y0 + i * ch + 1, cw - 2, ch - 2, f"rgba(31,95,191,{0.06 + 0.9 * a:.2f})")
            s.text(x0 + j * cw + cw / 2, y0 + i * ch + ch / 2 + 4, f"{n}", 9.5, "middle",
                   fill="#fff" if a > 0.55 else INK, weight="bold" if a > 0.55 else "normal")
        s.text(x0 + 4 * cw + 10, y0 + i * ch + ch / 2 + 4, f"{tot}", 9, fill=MUTE)
    s.text(x0 + 4 * cw + 10, y0 - 8, "total", 9, fill=MUTE)
    # colour key
    kx, ky = x0 + 4 * cw + 60, y0 + 10
    for k in range(6):
        s.rect(kx, ky + k * 22, 14, 20, f"rgba(31,95,191,{0.06 + 0.9 * min(1, (k*0.12)/0.6):.2f})")
        s.text(kx + 20, ky + k * 22 + 14, f"{k*12}%", 8.5, fill=MUTE)
    s.text(kx, ky - 6, "share", 8.5, fill=MUTE)
    save("18_training_heatmap", s)


def arc(cx, cy, r0, r1, a0, a1):
    import math
    p = lambda r, a: (cx + r * math.sin(a), cy - r * math.cos(a))
    large = 1 if a1 - a0 > math.pi else 0
    (x1, y1), (x2, y2) = p(r1, a0), p(r1, a1)
    (x3, y3), (x4, y4) = p(r0, a1), p(r0, a0)
    return (f"M{x1:.2f} {y1:.2f} A{r1} {r1} 0 {large} 1 {x2:.2f} {y2:.2f} L{x3:.2f} {y3:.2f} "
            f"A{r0} {r0} 0 {large} 0 {x4:.2f} {y4:.2f}Z")


def fig_sunburst():
    import math
    _, lv, _, _ = training_tables()
    topics = sorted(lv, key=lambda t: -sum(lv[t].values()))
    total = sum(sum(v.values()) for v in lv.values())
    s = Svg(624, 330)
    s.text(0, 14, "The grading data at a glance", 12, weight="bold")
    s.text(0, 29, f"Inner ring: topics. Outer ring: target levels within each topic. {total:,} criteria in all.",
           9.5, fill=MUTE)
    cx, cy = 200, 180
    greys = ["#4b5563", "#6b7280", "#525b68", "#737b87", "#4f5865", "#6e7682", "#59616d", "#7a828d"]
    a = 0.0
    for i, t in enumerate(topics):
        n = sum(lv[t].values())
        da = n / total * 2 * math.pi
        s.path(arc(cx, cy, 52, 100, a + .004, a + da - .004), fill=greys[i % len(greys)])
        mid = a + da / 2
        lx, ly = cx + 76 * math.sin(mid), cy - 76 * math.cos(mid)
        short = TOPIC_NAMES[t].replace("induction", "ind.").replace("Regular expressions", "Regex") \
            .replace("Program correctness", "Program corr.").replace("Asymptotic analysis", "Asymptotics")
        s.text(lx, ly + 3, short, 7.5, "middle", fill="#fff", weight="bold")
        b = a
        for l in LEVEL_ORDER:
            d2 = lv[t].get(l, 0) / total * 2 * math.pi
            s.path(arc(cx, cy, 103, 140, b + .003, b + d2 - .003), fill=LVCOL[l])
            b += d2
        a += da
    s.text(cx, cy - 2, f"{total:,}", 14, "middle", "bold")
    s.text(cx, cy + 12, "criteria", 9, "middle", fill=MUTE)
    lx = 400
    s.text(lx, 90, "Outer ring", 10, weight="bold")
    allv = {l: sum(lv[t].get(l, 0) for t in lv) for l in LEVEL_ORDER}
    for k, l in enumerate(LEVEL_ORDER):
        s.rect(lx, 102 + k * 22, 14, 14, LVCOL[l])
        s.text(lx + 22, 113 + k * 22, f"{l.capitalize()}  {allv[l]:,} ({allv[l]/total*100:.0f}%)", 10)
    s.text(lx, 210, "Every topic gets every level, so the", 9.5, fill=MUTE)
    s.text(lx, 224, "model sees flawed answers for all", 9.5, fill=MUTE)
    s.text(lx, 238, "eight topics.", 9.5, fill=MUTE)
    save("19_training_sunburst", s)


def kde(vals, xs, bw):
    import math
    n = len(vals)
    return [sum(math.exp(-0.5 * ((x - v) / bw) ** 2) for v in vals) / (n * bw * math.sqrt(2 * math.pi)) for x in xs]


def fig_ridgeline():
    _, _, _, pts = training_tables()
    groups = {k: [w for w, _, f in pts if f == k] for k in range(4)}
    xs = list(range(0, 701, 7))
    s = Svg(624, 280)
    s.text(0, 14, "Answer length by how many criteria are below full", 12, weight="bold")
    s.text(0, 29, "Smoothed distribution of words per training answer. Flawed answers are shorter, which a model could"
           " learn as a shortcut.", 9.5, fill=MUTE)
    x0, x1 = 130, 600
    X = lambda v: x0 + v / 700 * (x1 - x0)
    names = ["0 (all full)", "1 below full", "2 below full", "3 or more"]
    cols = ["#1f5fbf", "#5b86cf", "#d98a4a", "#c8453a"]
    base0, gap, H = 92, 42, 95
    dens = {k: kde(groups[k], xs, 22) for k in groups}
    mx = max(max(d) for d in dens.values())
    for v in range(0, 701, 100):
        s.line(X(v), 50, X(v), base0 + 3 * gap + 4, GRID)
        s.text(X(v), base0 + 3 * gap + 18, f"{v}", 8.5, "middle", fill=MUTE)
    for k in range(4):
        yb = base0 + k * gap
        d = dens[k]
        path = f"M{X(0)} {yb} " + " ".join(f"L{X(x):.1f} {yb - y / mx * H:.1f}" for x, y in zip(xs, d)) + f" L{X(700)} {yb}Z"
        s.path(path, fill=cols[k], op=0.55)
        s.path(path, stroke=cols[k], sw=1.4)
        med = statistics.median(groups[k])
        s.line(X(med), yb, X(med), yb - 10, INK, 1.5)
        s.text(0, yb - 2, names[k], 10)
        s.text(0, yb + 10, f"n = {len(groups[k])}, median {med:.0f}", 8, fill=MUTE)
    s.text((x0 + x1) / 2, base0 + 3 * gap + 32, "Words in the answer", 9.5, "middle")
    save("20_length_ridgeline", s)


def fig_scatter():
    import random
    _, _, _, pts = training_tables()
    random.seed(0)
    s = Svg(624, 306)
    s.text(0, 14, f"Every training answer: length against share of criteria at full ({len(pts):,} answers)", 12,
           weight="bold")
    s.text(0, 29, "Each dot is one answer, jittered vertically. Diamonds mark the median length in each row.",
           9.5, fill=MUTE)
    x0, x1, y0, y1 = 60, 600, 254, 62
    X = lambda v: x0 + min(v, 800) / 800 * (x1 - x0)
    Y = lambda v: y0 - v * (y0 - y1)
    for v in range(0, 801, 100):
        s.line(X(v), y1 - 6, X(v), y0 + 6, GRID)
        s.text(X(v), y0 + 18, f"{v}", 8.5, "middle", fill=MUTE)
    for v in [0, .25, .5, .75, 1]:
        s.text(x0 - 8, Y(v) + 3, f"{v*100:.0f}%", 8.5, "end", fill=MUTE)
    cols = ["#1f5fbf", "#5b86cf", "#d98a4a", "#c8453a"]
    for w, f, k in pts:
        s.circle(X(w), Y(f) + random.uniform(-7, 7), 1.6, cols[k])
    rows = {}
    for w, f, k in pts:
        rows.setdefault(round(f, 2), []).append(w)
    for f, ws in rows.items():
        if len(ws) >= 25:
            m = statistics.median(ws)
            yy = Y(f)
            s.path(f"M{X(m)} {yy-6} L{X(m)+5} {yy} L{X(m)} {yy+6} L{X(m)-5} {yy}Z", fill="#fff", stroke=INK, sw=1.4)
    s.text((x0 + x1) / 2, y0 + 34, "Words in the answer (capped at 800)", 9.5, "middle")
    legend(s, 300, 44, [("all full", cols[0], "dot"), ("1 below", cols[1], "dot"), ("2 below", cols[2], "dot"),
                        ("3+ below", cols[3], "dot")], 8.5)
    s.text(16, (y0 + y1) / 2, "Criteria at full", 9.5, "middle", rotate=-90)
    save("21_length_scatter", s)


def fig_radar():
    import math
    s = Svg(624, 330)
    s.text(0, 14, "Group A accuracy by topic, base model vs GradeAI", 12, weight="bold")
    s.text(0, 29, "Each spoke is a topic; the centre is 50%, the outer ring 100%.", 9.5, fill=MUTE)
    cx, cy, R = 250, 185, 120
    n = len(TOPIC_A)
    ang = lambda i: 2 * math.pi * i / n
    rr = lambda v: (v - 50) / 50 * R
    for v in [60, 70, 80, 90, 100]:
        pts = " ".join(f"{cx + rr(v)*math.sin(ang(i)):.1f},{cy - rr(v)*math.cos(ang(i)):.1f}" for i in range(n))
        s.add(f'<polygon points="{pts}" fill="none" stroke="{GRID}" stroke-width="1"/>')
        s.text(cx + 3, cy - rr(v) + 10, f"{v}%", 7.5, fill=MUTE)
    for i, (t, *_rest) in enumerate(TOPIC_A):
        s.line(cx, cy, cx + R * math.sin(ang(i)), cy - R * math.cos(ang(i)), GRID)
        lx, ly = cx + (R + 16) * math.sin(ang(i)), cy - (R + 16) * math.cos(ang(i))
        anchor = "middle" if abs(math.sin(ang(i))) < .3 else ("start" if math.sin(ang(i)) > 0 else "end")
        s.text(lx, ly + 4, t, 9, anchor)
    for idx, col, op in [(2, BASE, .25), (3, OURS, .22)]:
        pts = [(cx + rr(r[idx] / r[1] * 100) * math.sin(ang(i)), cy - rr(r[idx] / r[1] * 100) * math.cos(ang(i)))
               for i, r in enumerate(TOPIC_A)]
        ps = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        s.add(f'<polygon points="{ps}" fill="{col}" fill-opacity="{op}" stroke="{col}" stroke-width="2"/>')
        for x, y in pts:
            s.circle(x, y, 3, col)
    legend(s, 470, 260, [("Base model, 81.4%", BASE, "line")])
    legend(s, 470, 280, [("GradeAI, 95.3%", OURS, "line")])
    s.text(470, 304, "The base model is weakest", 9.5, fill=MUTE)
    s.text(470, 318, "on regex and DFAs.", 9.5, fill=MUTE)
    save("22_topic_radar", s)


def fig_sankey():
    _, _, flaws, _ = training_tables()
    topics = sorted(flaws, key=lambda t: -sum(flaws[t].values()))
    total = sum(sum(v.values()) for v in flaws.values())
    s = Svg(624, 340)
    s.text(0, 14, "Where the training answers go: topic to number of flawed criteria", 12, weight="bold")
    s.text(0, 29, f"Band width is the number of answers ({total:,} in all).", 9.5, fill=MUTE)
    H, top, gapL, gapR = 260, 48, 4, 10
    scale = (H - gapL * (len(topics) - 1)) / total
    lx, rx, nw = 150, 460, 12
    right = {k: sum(flaws[t].get(k, 0) for t in topics) for k in range(4)}
    rscale = (H - gapR * 3) / total
    ry, y = {}, top
    for k in range(4):
        ry[k] = y
        y += right[k] * rscale + gapR
    cols = ["#1f5fbf", "#5b86cf", "#d98a4a", "#c8453a"]
    names = ["all full", "1 below full", "2 below full", "3 or more below"]
    roff = dict(ry)
    y = top
    for t in topics:
        n = sum(flaws[t].values())
        s.rect(lx - nw, y, nw, n * scale, "#4b5563")
        s.text(lx - nw - 6, y + n * scale / 2 + 3.5, TOPIC_NAMES[t], 9.5, "end")
        yy = y
        for k in range(4):
            c = flaws[t].get(k, 0)
            if not c:
                continue
            h1, h2 = c * scale, c * rscale
            y2 = roff[k]
            mx = (lx + rx) / 2
            d = (f"M{lx} {yy:.1f} C{mx} {yy:.1f} {mx} {y2:.1f} {rx} {y2:.1f} L{rx} {y2+h2:.1f} "
                 f"C{mx} {y2+h2:.1f} {mx} {yy+h1:.1f} {lx} {yy+h1:.1f}Z")
            s.path(d, fill=cols[k], op=0.35)
            roff[k] += h2
            yy += h1
        y += n * scale + gapL
    for k in range(4):
        h = right[k] * rscale
        s.rect(rx, ry[k], nw, h, cols[k])
        s.text(rx + nw + 6, ry[k] + h / 2 + 0, names[k], 10, weight="bold")
        s.text(rx + nw + 6, ry[k] + h / 2 + 13, f"{right[k]} answers ({right[k]/total*100:.0f}%)", 8.5, fill=MUTE)
    save("23_training_flow", s)


ALL = [fig_forest, fig_verdict, fig_ablation_bars, fig_dumbbell, fig_tiles, fig_pips, fig_topics,
       fig_training_time, fig_training_levels, fig_level_mix, fig_length, fig_prompt_tradeoff, fig_audit,
       fig_testtype_b, fig_funnel, fig_redpen, fig_subway, fig_heatmap, fig_sunburst, fig_ridgeline,
       fig_scatter, fig_radar, fig_sankey]

if __name__ == "__main__":
    import sys
    os.chdir(ROOT)
    only = set(sys.argv[1:])
    for f in ALL:
        if not only or f.__name__ in only:
            f()
