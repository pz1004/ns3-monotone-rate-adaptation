#!/usr/bin/env python3
"""Emit the per-cell results table straight from the campaign parquet."""
import numpy as np, pandas as pd
from scipy import stats

import _paths
d = pd.read_parquet(_paths.RESULTS / 'campaign/full.parquet')
KEY = ["channel", "nsta", "speed", "seed"]
ours = d[d.arm == "Mono(w=0.25)"][KEY + ["thr"]].rename(columns={"thr": "ours"})

fixed = d[d.arm.str.startswith("Fixed(")].copy()
fixed["mcs"] = fixed.arm.str.extract(r"MCS(\d+)").astype(int)
oracle = (fixed.sort_values("thr").groupby(KEY).tail(1)
          .rename(columns={"thr": "ref"})[KEY + ["ref"]])
gbest = int(fixed.groupby("mcs").thr.mean().idxmax())
deploy = fixed[fixed.mcs == gbest].rename(columns={"thr": "ref"})[KEY + ["ref"]]

fam = {"Thompson": d[d.arm.str.startswith("Thompson(")],
       "Minstrel": d[d.arm.str.startswith("MinstrelHt(")],
       "ORS": d[d.arm.str.contains("ORS|KL-R", regex=True)]}

def worst_vs_family(o, sub):
    """Worst-case % margin over every (arm, speed), and whether any loss is significant."""
    worst, sig_loss = 1e9, False
    pv = []
    for arm, a in sub.groupby("arm"):
        m = o.merge(a[KEY + ["thr"]], on=KEY)
        for sp, s in m.groupby("speed"):
            rel = 100 * (s.ours.mean() / s.thr.mean() - 1)
            worst = min(worst, rel)
            pv.append((rel, stats.ttest_rel(s.ours.values, s.thr.values).pvalue))
    k = len(pv)
    for rank, (rel, p) in enumerate(sorted(pv, key=lambda t: t[1])):
        if rel < 0 and min(1.0, (k - rank) * p) < 0.05:
            sig_loss = True
    return worst, sig_loss

def worst_vs_ref(o, rdf):
    m = o.merge(rdf, on=KEY)
    return min(100 * (s.ours.mean() / s.ref.mean() - 1) for _, s in m.groupby("speed"))

rows = []
for (ch, ns), _ in d.groupby(["channel", "nsta"]):
    o = ours[(ours.channel == ch) & (ours.nsta == ns)]
    cells = {}
    for fname, fdf in fam.items():
        sub = fdf[(fdf.channel == ch) & (fdf.nsta == ns)]
        cells[fname] = worst_vs_family(o, sub)
    orc = worst_vs_ref(o, oracle[(oracle.channel == ch) & (oracle.nsta == ns)])
    dep = worst_vs_ref(o, deploy[(deploy.channel == ch) & (deploy.nsta == ns)])
    rows.append((ch, ns, cells, orc, dep))

short = {"logdistance": "path loss", "logdistance+jakes": "+ fading"}
out = []
out.append(r"\begin{table}[t]")
out.append(r"\caption{Per-cell audit. Each entry is the \emph{worst-case} margin of one")
out.append(r"fixed configuration over every member of that baseline family at every speed;")
out.append(r"$\dagger$ marks a cell containing a statistically significant loss. Static")
out.append(r"columns give the worst margin over speeds; the ORS column spans SW-ORS and")
out.append(r"KL-R-UCB. \NumSeedsWordCap{} seeds, Holm-corrected.}")
out.append(r"\label{tab:percell}")
out.append(r"\centering\small\setlength{\tabcolsep}{3.5pt}")
out.append(r"\begin{tabular}{@{}llrrrrr@{}}")
out.append(r"\toprule")
out.append(r"channel & STAs & Thomp. & Minst. & ORS & orac. & depl. \\")
out.append(r"\midrule")
for ch, ns, cells, orc, dep in rows:
    f = []
    for k in ["Thompson", "Minstrel", "ORS"]:
        w, sig = cells[k]
        f.append(f"${w:+.1f}$" + (r"$^\dagger$" if sig else ""))
    out.append(f"{short[ch]} & {ns} & " + " & ".join(f) +
               f" & ${orc:+.1f}$ & ${dep:+.1f}$ \\\\")
out.append(r"\bottomrule")
out.append(r"\end{tabular}")
out.append(r"\end{table}")
open(_paths.OUT / "percell.tex", "w").write("\n".join(out) + "\n")
print("\n".join(out))
