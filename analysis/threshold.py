#!/usr/bin/env python3
"""Locate the mobility threshold above which not adapting beats adapting.

Two crossovers are reported, because they answer different questions:
  oracle     -- vs the per-speed best fixed rate chosen in hindsight. Conservative:
                above it, adaptation loses even to a static choice with foresight.
  deployable -- vs ONE fixed MCS chosen for the whole deployment (no knowledge of speed).
                This is what an operator could actually configure, so it is the
                operationally meaningful threshold, and it sits at a higher speed.
"""
import sys
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt

import _paths
src = sys.argv[1] if len(sys.argv) > 1 else _paths.RESULTS / "threshold/sweep.parquet"
d = pd.read_parquet(src)
fixed = d[d.arm.str.startswith("Fixed(")].copy()
fixed["mcs"] = fixed.arm.str.extract(r"MCS(\d+)").astype(int)

# per-speed oracle static rate
oracle = (fixed.groupby(["speed", "seed", "mcs"]).thr.sum().reset_index()
          .sort_values("thr").groupby(["speed", "seed"]).tail(1)
          .rename(columns={"thr": "oracle_fixed"})[["speed", "seed", "oracle_fixed"]])

# ONE deployment-wide MCS: the one maximising mean throughput across ALL speeds
per_mcs = fixed.groupby(["mcs", "speed"]).thr.mean().groupby("mcs").mean()
best_global = int(per_mcs.idxmax())
deploy = (fixed[fixed.mcs == best_global].groupby(["speed", "seed"]).thr.sum()
          .rename("deploy_fixed").reset_index())
print(f"Single deployment-wide MCS (best mean across all speeds): MCS{best_global}\n")

def crossing(x, y):
    """First x where y drops below 1.0, by linear interpolation."""
    for i in range(len(x) - 1):
        if y[i] >= 1.0 > y[i + 1]:
            t = (1.0 - y[i]) / (y[i + 1] - y[i])
            return x[i] + t * (x[i + 1] - x[i])
    return np.nan if y[0] < 1.0 else np.inf

rows = []
for arm in ["Mono(w=0.25)", "Thompson(d=2.0)"]:
    a = d[d.arm == arm].groupby(["speed", "seed"]).thr.sum().rename("adaptive").reset_index()
    j = a.merge(oracle, on=["speed", "seed"]).merge(deploy, on=["speed", "seed"])
    g = j.groupby("speed").mean(numeric_only=True)
    sp = g.index.values
    r_or = (g.adaptive / g.oracle_fixed).values
    r_dp = (g.adaptive / g.deploy_fixed).values
    # bootstrap the crossings over seeds
    boots = {"oracle": [], "deploy": []}
    seeds = sorted(j.seed.unique()); rng = np.random.default_rng(0)
    for _ in range(2000):
        pick = rng.choice(seeds, len(seeds), replace=True)
        sub = pd.concat([j[j.seed == s] for s in pick])
        gg = sub.groupby("speed").mean(numeric_only=True)
        boots["oracle"].append(crossing(gg.index.values, (gg.adaptive/gg.oracle_fixed).values))
        boots["deploy"].append(crossing(gg.index.values, (gg.adaptive/gg.deploy_fixed).values))
    def ci(v):
        v = np.array([x for x in v if np.isfinite(x)])
        return (np.nan, np.nan) if len(v) < 50 else (np.percentile(v, 2.5), np.percentile(v, 97.5))
    co, cd = crossing(sp, r_or), crossing(sp, r_dp)
    lo_o, hi_o = ci(boots["oracle"]); lo_d, hi_d = ci(boots["deploy"])
    rows.append((arm, sp, r_or, r_dp))
    print(f"{arm}")
    print(f"   ratio vs per-speed ORACLE fixed rate : " +
          "  ".join(f"{s:g}m/s={v:.2f}" for s, v in zip(sp, r_or)))
    print(f"   ratio vs DEPLOYMENT-WIDE MCS{best_global:<2d}        : " +
          "  ".join(f"{s:g}m/s={v:.2f}" for s, v in zip(sp, r_dp)))
    print(f"   -> oracle crossover     {co:.1f} m/s   [95% CI {lo_o:.1f}, {hi_o:.1f}]")
    print(f"   -> deployable crossover {cd:.1f} m/s   [95% CI {lo_d:.1f}, {hi_d:.1f}]\n")

fig, ax = plt.subplots(figsize=(7.6, 4.6))
sty = {"Mono(w=0.25)": ("tab:blue", "ours"), "Thompson(d=2.0)": ("tab:orange", "Thompson")}
for arm, sp, r_or, r_dp in rows:
    c, lab = sty[arm]
    ax.plot(sp, r_or, 'o-', color=c, lw=2, label=f"{lab} vs per-speed oracle fixed rate")
    ax.plot(sp, r_dp, 's--', color=c, lw=1.6, alpha=.65,
            label=f"{lab} vs one deployment-wide MCS{best_global}")
ax.axhline(1.0, color='k', lw=1.6)
ax.fill_between([0, 20], 0, 1, color='tab:red', alpha=.07)
ax.text(0.4, 0.55, "adapting is WORSE\nthan a static rate", fontsize=9, color='tab:red')
ax.set_xlabel("STA speed (m/s)"); ax.set_ylabel("adaptive throughput / static reference")
ax.set_title("Where does rate adaptation stop paying?\n802.11be 80 MHz 2SS, 4 STAs, Jakes fading, 10 seeds", fontsize=10)
ax.grid(alpha=.3); ax.legend(fontsize=7.5); ax.set_ylim(0, 1.5)
fig.tight_layout(); fig.savefig(_paths.OUT / "threshold.png", dpi=150)
print(f"figure -> {_paths.OUT / 'threshold.png'}")
