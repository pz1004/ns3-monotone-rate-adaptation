#!/usr/bin/env python3
r"""Regenerate every figure in the paper from the stored result files.

The figures were originally produced ad hoc, which left them free to drift from the
tables: f1 was still the 5-seed bias run after the table moved to ten seeds, and f2
still showed the data-rate correlation computed with the old, non-comparable metric.
Every quantity a figure draws is therefore recomputed here from the same file
make_numbers.py reads, and cross-checked against numbers.tex before the PNG is
written -- a figure that disagrees with the prose is a failure, not a redraw.
"""
import re, pathlib, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import _paths
R = _paths.RESULTS
FIG = _paths.OUT
mac = dict(re.findall(r"^\\newcommand\{\\(Num[A-Za-z]+)\}\{(.*)\}$",
                      (_paths.OUT / "numbers.tex").read_text(), re.M))
BAD = []
def agree(name, got, want):
    # the figure must round to the same value the prose prints, no looser
    dec = len(want.split(".")[1]) if "." in want else 0
    ok = abs(got - float(want)) < 0.5 * 10 ** -dec + 1e-9
    print(f"  {'ok  ' if ok else 'DRIFT'} {name:26s} figure={got:+.2f}  numbers.tex={want}")
    if not ok:
        BAD.append(name)

plt.rcParams.update({"font.size": 8.5, "axes.titlesize": 9, "axes.grid": True,
                     "grid.alpha": .3, "figure.dpi": 200, "savefig.bbox": "tight"})
BLUE, RED, GREY, PURPLE = "#1f77b4", "#d62728", "#7f7f7f", "#7e57c2"


# ---------------------------------------------------------------- f1: the bias
b = pd.read_parquet(R / "diag/bias10.parquet")
idl = b[b.arm == "Ideal"][["speed", "seed", "mean_mcs", "tx_per_MB"]].rename(
    columns={"mean_mcs": "i_mcs", "tx_per_MB": "i_tx"})
m = b[b.arm.str.startswith("Thompson")][["speed", "seed", "mean_mcs", "tx_per_MB"]].merge(
    idl, on=["speed", "seed"])
m["bias"] = m.mean_mcs - m.i_mcs
m["txoh"] = 100 * (m.tx_per_MB / m.i_tx - 1)
g = m.groupby("speed").agg(bias=("bias", "mean"), txoh=("txoh", "mean"),
                           n=("bias", "size"),
                           bs=("bias", lambda x: x.std(ddof=1)),
                           ts=("txoh", lambda x: x.std(ddof=1)))
g["bci"] = 1.96 * g.bs / np.sqrt(g.n)
g["tci"] = 1.96 * g.ts / np.sqrt(g.n)
nseed = int(m.groupby("speed").seed.nunique().max())
agree("bias @ 0 m/s", g.bias[0.0], mac["NumBiasVzero"])
agree("bias @ 20 m/s", g.bias[20.0], mac["NumBiasVtwozero"])
agree("extra tx @ 20 m/s", g.txoh[20.0], mac["NumTxOhVtwozero"])

f, ax = plt.subplots(1, 2, figsize=(7.0, 2.15), layout="constrained")
x = g.index.values
ax[0].axhline(0, color="k", lw=1)
ax[0].fill_between(x, 0, g.bias, where=(g.bias < 0), color=BLUE, alpha=.18)
ax[0].fill_between(x, 0, g.bias, where=(g.bias > 0), color=RED, alpha=.18)
ax[0].errorbar(x, g.bias, yerr=g.bci, marker="o", ms=4, color=PURPLE, capsize=3)
ax[0].annotate("too CONSERVATIVE", (0.4, -1.9), color=BLUE, fontsize=8, weight="bold")
ax[0].annotate("too AGGRESSIVE", (7.0, 1.05), color=RED, fontsize=8, weight="bold")
ax[0].set_xlabel("STA speed (m/s)")
ax[0].set_ylabel("mean MCS chosen $-$ genie MCS")
ax[0].set_title("The selection bias flips sign with mobility")
ax[1].errorbar(x, g.txoh, yerr=g.tci, marker="s", ms=4, color=RED, capsize=3)
ax[1].set_xlabel("STA speed (m/s)")
ax[1].set_ylabel("extra PHY transmissions\nper delivered MB (%)")
ax[1].set_title("Cost of over-aggression: retries")
f.savefig(FIG / "f1_bias.png"); plt.close(f)


# ------------------------------------------------------- f2: frontier + ordering
fr = pd.read_parquet(R / "mono/frontier_test.parquet")
fr = fr[fr.arm != "Ideal"].copy()
fr["lam"] = fr.arm.str.extract(r"d=([\d.]+)").astype(float)
ours = fr[fr.arm.str.startswith("Mono")].groupby("speed").thr.mean()
ts = fr[fr.arm.str.startswith("Thompson")].groupby(["speed", "lam"]).thr.mean()

om = pd.read_parquet(R / "mono/order_matched.parquet")

def scaling(arm, mcs_per_ss=12):
    """Identical to make_numbers.order_scaling, on the matched grid."""
    rows = []
    for (wd, ns), k in om.groupby(["width", "nss"]):
        tt = k[k.arm == "Thompson(d=2.0)"]; qq = k[k.arm == arm]
        rows.append((mcs_per_ss * ns * (int(np.log2(wd / 20)) + 1),
                     100 * (qq.thr.mean() / tt.thr.mean() - 1)))
    rows.sort(); a = np.array(rows)
    return np.corrcoef(a[:, 0], a[:, 1])[0, 1], a

c_rate, a_rate = scaling("Mono/DataRate(w=0.25)")
c_snr,  a_snr  = scaling("Mono(w=0.25)")
agree("corr, data-rate order", c_rate, mac["NumCorrDataRate"])
agree("corr, required-SNR order", c_snr, mac["NumCorrReqSnr"])
agree("smallest table", a_snr[0, 0], mac["NumScaleSmallN"])
agree("largest table", a_snr[-1, 0], mac["NumScaleBigN"])

# The caption claims the dashed line clears every point of the frontier. Nothing
# checked that; a figure is not allowed to make a claim the data has not been asked.
for sp in sorted(ours.index):
    best = ts.loc[sp].max()
    if ours[sp] <= best:
        BAD.append(f"frontier @ {sp:g} m/s (ours {ours[sp]:.0f} <= best Thompson {best:.0f})")
    print(f"  {'ok  ' if ours[sp] > best else 'DRIFT'} frontier @ {sp:g} m/s"
          f"{'':14s} ours/best = {ours[sp]/best:.3f}")

f, ax = plt.subplots(1, 2, figsize=(7.2, 2.6), layout="constrained")
for sp, col in zip(sorted(ours.index), ["#2ca02c", "#ff7f0e", RED]):
    y = ts.loc[sp]; base = y.max()
    ax[0].plot(y.index, y.values / base, marker="o", ms=3.5, color=col,
               label=f"Thompson, {sp:g} m/s")
    ax[0].axhline(ours[sp] / base, ls="--", color=col, lw=1.4)
ax[0].set_xscale("log")
ax[0].set_xlabel(r"ThompsonSampling  $\mathtt{Decay}$  (Hz)")
ax[0].set_ylabel("throughput, normalised\nto best Thompson")
ax[0].set_title("Dashed = ours (one fixed config);\nit beats every point of the frontier")
ax[0].legend(fontsize=7, loc="lower left")
for a, c, col, mk, lab in ((a_rate, c_rate, GREY, "s", "DATA RATE"),
                           (a_snr, c_snr, BLUE, "o", "REQUIRED SNR")):
    ax[1].plot(a[:, 0], a[:, 1], marker=mk, ms=5, color=col,
               label=f"ordered by {lab} ($r={c:+.2f}$)")
    p = np.poly1d(np.polyfit(a[:, 0], a[:, 1], 1))
    ax[1].plot(a[:, 0], p(a[:, 0]), ls=":", color=col, lw=1.2)
ax[1].axhline(0, color="k", lw=1)
ax[1].set_xlabel(r"rate-table size  (# MCS $\times$ Nss $\times$ widths)")
ax[1].set_ylabel("throughput gain over\nThompson (%)")
ax[1].set_title("Matched ablation: the ordering\nalone flips the scaling")
ax[1].legend(fontsize=7, loc="center right")
f.savefig(FIG / "f2_ordering.png"); plt.close(f)


# ------------------------------------- f3: when does adapting stop paying at all?
th = pd.read_parquet(R / "threshold/sweep.parquet")
fx = th[th.arm.str.startswith("Fixed(")].copy()
oracle = fx.sort_values("thr").groupby(["speed", "seed"]).tail(1)[["speed", "seed", "thr"]] \
           .rename(columns={"thr": "oracle"})
depl = fx[fx.arm == f"Fixed(MCS{mac['NumDeployMcs']})"][["speed", "seed", "thr"]] \
         .rename(columns={"thr": "depl"})
ref = oracle.merge(depl, on=["speed", "seed"])

def curve(arm, col):
    a = th[th.arm == arm].groupby(["speed", "seed"]).thr.sum().rename("ad").reset_index()
    j = a.merge(ref, on=["speed", "seed"]).groupby("speed").mean(numeric_only=True)
    return j.index.values, (j.ad / j[col]).values

def crossing(x, y):
    for i in range(len(x) - 1):
        if y[i] >= 1.0 > y[i + 1]:
            return x[i] + (1.0 - y[i]) / (y[i + 1] - y[i]) * (x[i + 1] - x[i])
    return float("nan")

xo, yo = curve("Mono(w=0.25)", "oracle")
xt, yt = curve("Thompson(d=2.0)", "oracle")
agree("crossover, ours", crossing(xo, yo), mac["NumCrossOurs"])
agree("crossover, Thompson", crossing(xt, yt), mac["NumCrossThompson"])

f, ax = plt.subplots(figsize=(3.6, 1.55), layout="constrained")
ax.axhspan(0, 1, color=RED, alpha=.06)
ax.axhline(1, color="k", lw=1)
for arm, col, sty, c, lab in (
        ("Mono(w=0.25)", "oracle", "-", BLUE, "ours vs oracle rate"),
        ("Mono(w=0.25)", "depl", "--", BLUE, f"ours vs one MCS{mac['NumDeployMcs']}"),
        ("Thompson(d=2.0)", "oracle", "-", "#ff7f0e", "Thomp. vs oracle rate"),
        ("Thompson(d=2.0)", "depl", "--", "#ff7f0e", f"Thomp. vs one MCS{mac['NumDeployMcs']}")):
    x, y = curve(arm, col)
    ax.plot(x, y, sty, marker="o" if col == "oracle" else "s", ms=3, color=c,
            lw=1.4, alpha=1.0 if col == "oracle" else .55, label=lab)
for xc, c in ((float(mac["NumCrossOurs"]), BLUE), (float(mac["NumCrossThompson"]), "#ff7f0e")):
    ax.plot([xc], [1.0], marker="v", ms=6, color=c, clip_on=False, zorder=5)
ax.annotate("adapting is WORSE than a static rate", (0.5, .15), color=RED, fontsize=6)
ax.set_xlabel("STA speed (m/s)")
ax.set_ylabel("adaptive / static", fontsize=7.5)
ax.set_ylim(0, 2.35)
ax.legend(fontsize=5.6, loc="upper left", ncol=2, framealpha=.9,
          handlelength=1.6, columnspacing=.9, borderpad=.3)
ax.set_title(f"Crossover moves {mac['NumCrossThompson']} $\\to$ "
             f"{mac['NumCrossOurs']} m/s", fontsize=8)
f.savefig(FIG / "f3_refs.png"); plt.close(f)

print(f"\nwrote {len(list(FIG.glob('*.png')))} figures to {FIG}/")
if BAD:
    print("FIGURES DISAGREE WITH numbers.tex:", BAD); sys.exit(1)
print("every figure agrees with numbers.tex")
