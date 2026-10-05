"""Draw the model as a directed acyclic graph: figures/dag.svg.

    python scripts/make_dag.py
"""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "figures" / "dag.svg"
W, H = 1500, 1010
BLUE, BLUEF, GREY, DARK, PRIOR, PLATE = "#1f4e79", "#dce8f5", "#7f7f7f", "#1f4e79", "#b36b00", "#9aa5b1"

o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
     '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
     '<path d="M0,0L10,5L0,10z" fill="#44505c"/></marker>'
     '<marker id="g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
     '<path d="M0,0L10,5L0,10z" fill="#a0a8b0"/></marker></defs>',
     f'<rect width="{W}" height="{H}" fill="white"/>',
     '<style>text{font-family:"DejaVu Serif","Times New Roman",serif}'
     '.m{font-style:italic;font-size:25px}.s{font-size:16px}'
     '.p{font-family:Arial,"DejaVu Sans",sans-serif;font-size:17px;fill:#b36b00}'
     '.pl{font-family:Arial,"DejaVu Sans",sans-serif;font-size:18px;fill:#5a6570;font-style:italic}'
     '.lg{font-family:Arial,"DejaVu Sans",sans-serif;font-size:18px;fill:#222}'
     '.el{font-family:Arial,"DejaVu Sans",sans-serif;font-size:15px;fill:#44505c}</style>']
N = {}


def node(key, x, y, label, kind, rx=58, ry=32):
    N[key] = (x, y, rx, ry)
    if kind == "est":
        o.append(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{BLUEF}" stroke="{BLUE}" stroke-width="2.5"/>')
    elif kind == "det":
        o.append(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="white" stroke="{GREY}" stroke-width="2.2" stroke-dasharray="7 5"/>')
    elif kind == "obs":
        o.append(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{DARK}" stroke="{DARK}" stroke-width="2.5"/>')
    elif kind == "con":
        o.append(f'<rect x="{x-rx}" y="{y-ry}" width="{2*rx}" height="{2*ry}" rx="6" fill="#eceff1" stroke="{GREY}" stroke-width="2"/>')
    col = "white" if kind == "obs" else "#16202a"
    o.append(f'<text x="{x}" y="{y+8}" text-anchor="middle" fill="{col}">{label}</text>')


def sub(a, b, sup=None):
    s = f'<tspan class="m">{a}</tspan><tspan class="s" dy="7">{b}</tspan>'
    if sup:
        s += f'<tspan class="s" dy="-19">{sup}</tspan>'
    return s


def edge(a, b, grey=False, label=None, dash=False, bend=0, lx=0, ly=0, ctrl=None):
    x1, y1, rx1, ry1 = N[a]
    x2, y2, rx2, ry2 = N[b]

    def border(x, y, rx, ry, tx, ty):
        dx, dy = tx - x, ty - y
        t = 1 / math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
        return x + dx * t, y + dy * t

    if ctrl:
        sx, sy = border(x1, y1, rx1, ry1, *ctrl)
        ex, ey = border(x2, y2, rx2, ry2, *ctrl)
        mx, my = ctrl
    else:
        sx, sy = border(x1, y1, rx1, ry1, x2, y2)
        ex, ey = border(x2, y2, rx2, ry2, x1, y1)
        mx, my = (sx + ex) / 2 - bend * (ey - sy) / 300, (sy + ey) / 2 + bend * (ex - sx) / 300
    col = "#a0a8b0" if grey else "#44505c"
    o.append(f'<path d="M{sx:.1f},{sy:.1f} Q{mx:.1f},{my:.1f} {ex:.1f},{ey:.1f}" fill="none" stroke="{col}" '
             f'stroke-width="{1.6 if grey else 2}" marker-end="url(#{"g" if grey else "a"})"'
             + (' stroke-dasharray="6 5"' if dash else "") + "/>")
    if label:
        o.append(f'<text x="{(sx+ex)/2+lx:.0f}" y="{(sy+ey)/2+ly:.0f}" class="el" text-anchor="middle">{label}</text>')


def plate(x, y, w, h, label):
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="none" stroke="{PLATE}" stroke-width="2"/>')
    o.append(f'<text x="{x+w-14}" y="{y+h-14}" text-anchor="end" class="pl">{label}</text>')


def prior(x, y, txt):
    o.append(f'<text x="{x}" y="{y}" text-anchor="middle" class="p">{txt}</text>')


plate(40, 330, 930, 580, "seasons  k = 1, …, K")
plate(75, 470, 640, 400, "teams  t = 1, …, T")
plate(1030, 330, 440, 580, "matches  i = 1, …, n")
G = 120
node("tatt", 110, G, sub("τ", "att"), "est"); prior(110, G - 48, "Gamma(0.01, 0.01)")
node("rho", 330, G, '<tspan class="m">ρ</tspan>', "est"); prior(330, G - 48, "Uniform(0, 1)")
node("tdef", 560, G, sub("τ", "def"), "est"); prior(560, G - 48, "Gamma(0.01, 0.01)")
node("entry", 745, G, '<tspan class="m">entry</tspan>', "est", rx=62); prior(745, G - 48, "N(0, 0.5²)")
node("tmu", 905, G, sub("τ", "μ"), "est"); prior(905, G - 48, "Gamma(0.01, 0.01)")
node("mu0", 1080, G, sub("μ", "0"), "est"); prior(1080, G - 48, "N(0, 100²)")
node("home", 1330, G, '<tspan class="m">home</tspan>', "est", rx=62); prior(1330, G - 48, "N(0, 100²)")
D = 250
node("satt", 110, D, sub("σ", "att"), "det")
node("shatt", 290, D, sub("sd", "shock,att"), "det", rx=78)
node("shdef", 490, D, sub("sd", "shock,def"), "det", rx=78)
node("sdef", 660, D, sub("σ", "def"), "det")
node("smu", 905, D, sub("σ", "μ"), "det")
node("muk", 880, 440, sub("μ", "k"), "est")
node("attp", 190, 560, sub("att", "t,k−1"), "est", rx=70)
node("attk", 540, 560, sub("att", "t,k"), "est", rx=62)
node("defp", 190, 790, sub("def", "t,k−1"), "est", rx=70)
node("defk", 540, 790, sub("def", "t,k"), "est", rx=62)
node("isent", 360, 675, '<tspan class="m" style="font-size:21px">is_entry</tspan><tspan class="s" dy="7">t,k</tspan>',
     "con", rx=78, ry=26)
node("idx", 1250, 420, '<tspan class="m" style="font-size:21px">h(i), a(i), s(i)</tspan>', "con", rx=92, ry=26)
node("lh", 1140, 590, sub("λ", "i", "home"), "det", rx=62)
node("la", 1360, 590, sub("λ", "i", "away"), "det", rx=62)
node("yh", 1140, 790, sub("y", "i", "home"), "obs", rx=62)
node("ya", 1360, 790, sub("y", "i", "away"), "obs", rx=62)

edge("tatt", "satt"); edge("satt", "shatt"); edge("rho", "shatt"); edge("rho", "shdef")
edge("tdef", "sdef"); edge("sdef", "shdef"); edge("tmu", "smu")
edge("smu", "muk"); edge("mu0", "muk")
edge("attp", "attk", label="× ρ", ly=-12); edge("defp", "defk", label="× ρ", ly=-12)
edge("shatt", "attk"); edge("shdef", "defk", ctrl=(690, 560))
edge("satt", "attp", dash=True, label="k = 1", lx=-30)
edge("sdef", "defp", dash=True, ctrl=(250, 700))
o.append('<text x="168" y="640" class="el">k = 1</text>')
edge("entry", "attk", bend=10); edge("entry", "defk", ctrl=(760, 600))
edge("isent", "attk"); edge("isent", "defk")
edge("muk", "lh"); edge("muk", "la", bend=-20)
edge("attk", "lh", bend=-8); edge("attk", "la", bend=-25)
edge("defk", "lh", bend=10); edge("defk", "la", bend=25)
edge("home", "lh", ctrl=(1080, 330))
edge("idx", "lh", grey=True); edge("idx", "la", grey=True)
edge("lh", "yh", label="Poisson", lx=-42); edge("la", "ya", label="Poisson", lx=42)

y, x = 965, 60
for kind, lab in [("est", "estimated parameter"), ("det", "computed from its parents"),
                  ("obs", "observed goals"), ("con", "known constant, from the data")]:
    if kind == "est":
        o.append(f'<ellipse cx="{x+22}" cy="{y}" rx="22" ry="14" fill="{BLUEF}" stroke="{BLUE}" stroke-width="2"/>')
    if kind == "det":
        o.append(f'<ellipse cx="{x+22}" cy="{y}" rx="22" ry="14" fill="white" stroke="{GREY}" stroke-width="2" stroke-dasharray="5 4"/>')
    if kind == "obs":
        o.append(f'<ellipse cx="{x+22}" cy="{y}" rx="22" ry="14" fill="{DARK}"/>')
    if kind == "con":
        o.append(f'<rect x="{x}" y="{y-13}" width="44" height="26" rx="4" fill="#eceff1" stroke="{GREY}" stroke-width="2"/>')
    o.append(f'<text x="{x+54}" y="{y+6}" class="lg">{lab}</text>')
    x += 70 + len(lab) * 9.2
o.append(f'<text x="{x}" y="{y+6}" class="p" style="font-size:18px">orange: prior</text>')
o.append("</svg>")
OUT.parent.mkdir(exist_ok=True)
OUT.write_text("\n".join(o), encoding="utf-8")
print("written", OUT)
