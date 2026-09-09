#!/usr/bin/env python3
"""Analyse the Decay x speed x channel frontier.

Load-bearing question: is there a single fixed Decay that wins across the speed range?
If yes, the adaptive-forgetting contribution collapses.
"""
import sys
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt

import _paths
src = sys.argv[1] if len(sys.argv) > 1 else _paths.RESULTS / "gate1/decay_frontier.parquet"
d = pd.read_parquet(src)

ad = d[d.raa != "ConstantRate"].copy()
tot = (ad.groupby(["channel", "speed", "raa", "decay", "seed"])
         .throughput_mbps.sum().rename("tp").reset_index())
ideal = (tot[tot.raa == "Ideal"][["channel", "speed", "seed", "tp"]]
         .rename(columns={"tp": "ideal"}))
ts = tot[tot.raa == "ThompsonSampling"].merge(ideal, on=["channel", "speed", "seed"])
ts["pct"] = 100 * ts.tp / ts.ideal

g = (ts.groupby(["channel", "speed", "decay"])
       .agg(m=("pct", "mean"), sd=("pct", "std"), n=("pct", "count")).reset_index())
g["ci"] = 1.96 * g.sd / np.sqrt(g.n)

for ch in sorted(g.channel.unique()):
    sub = g[g.channel == ch]
    piv = sub.pivot_table(index="decay", columns="speed", values="m")
    print(f"\n=== {ch}: ThompsonSampling % of genie, rows = Decay (Hz), cols = speed (m/s) ===")
    print(piv.round(1).to_string())
    best = piv.idxmax()
    print("\n  best Decay per speed :", dict(best))
    print("  best value per speed :", dict(piv.max().round(1)))
    # the load-bearing test: how much does the best SINGLE fixed decay lose?
    mean_over_speeds = piv.mean(axis=1)
    d_star = mean_over_speeds.idxmax()
    loss = (piv.max() - piv.loc[d_star])
    print(f"\n  best single fixed Decay overall = {d_star} Hz "
          f"(mean {mean_over_speeds.max():.1f}%)")
    print("  its shortfall vs per-speed-oracle Decay, per speed (pp):")
    print("   ", {k: round(v, 1) for k, v in loss.items()})
    print(f"  --> MAX shortfall = {loss.max():.1f} pp at speed {loss.idxmax()} m/s")

fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
for ax, ch in zip(axes, sorted(g.channel.unique())):
    sub = g[g.channel == ch]
    for sp in sorted(sub.speed.unique()):
        s = sub[sub.speed == sp].sort_values("decay")
        ax.errorbar(s.decay.replace(0, 0.25), s.m, yerr=s.ci, marker="o", capsize=3,
                    lw=1.6, label=f"{sp:.0f} m/s")
    ax.set_xscale("log"); ax.axhline(100, color="k", ls="--", lw=1)
    ax.axvline(1.0, color="grey", ls=":", lw=1.4)
    ax.text(1.05, 12, "ns-3 default", rotation=90, fontsize=7, color="grey")
    ax.set_xlabel("ThompsonSampling  Decay  (Hz, log; 0 plotted at 0.25)")
    ax.set_title(ch); ax.grid(alpha=.3)
axes[0].set_ylabel("% of Ideal genie")
axes[0].legend(fontsize=7, title="STA speed", ncol=2)
fig.suptitle("No single forgetting rate is right everywhere: the optimal Decay shifts with mobility\n"
             "(802.11be 80 MHz 2SS, 4 STAs, 5 seeds, 95% CI)", fontsize=10)
fig.tight_layout()
fig.savefig(_paths.OUT / "decay_frontier.png", dpi=150)
print(f"\nfigure -> {_paths.OUT / 'decay_frontier.png'}")
