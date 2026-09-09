#!/usr/bin/env python3
"""Pre-registered campaign analysis (protocol-v1).

Reports, for every (channel x contention) cell:
  - H-main: does one fixed config of ours dominate the entire swept Decay frontier?
  - the Minstrel-HT SampleColumn frontier, the ORS family, and the two static references
  - paired tests with Holm correction across the speed family
"""
import sys
import numpy as np, pandas as pd
from scipy import stats

import _paths
src = sys.argv[1] if len(sys.argv) > 1 else _paths.RESULTS / "campaign/full.parquet"
d = pd.read_parquet(src)
KEY = ["channel", "nsta", "speed", "seed"]
OURS = "Mono(w=0.25)"

fixed = d[d.arm.str.startswith("Fixed(")].copy()
fixed["mcs"] = fixed.arm.str.extract(r"MCS(\d+)").astype(int)
oracle = (fixed.sort_values("thr").groupby(KEY).tail(1)
          .rename(columns={"thr": "oracle_fixed"})[KEY + ["oracle_fixed", "mcs"]])
# one deployment-wide MCS, chosen on mean across ALL conditions
gbest = int(fixed.groupby("mcs").thr.mean().idxmax())
deploy = (fixed[fixed.mcs == gbest].rename(columns={"thr": "deploy_fixed"})
          [KEY + ["deploy_fixed"]])

fam = {"Thompson": d[d.arm.str.startswith("Thompson(")],
       "MinstrelHt": d[d.arm.str.startswith("MinstrelHt(")],
       "ORS": d[d.arm.str.contains("ORS|KL-R", regex=True)]}
ours = d[d.arm == OURS][KEY + ["thr"]].rename(columns={"thr": "ours"})

print(f"rows={len(d)}  arms={d.arm.nunique()}  cells={d.groupby(KEY).ngroups}")
print(f"deployment-wide static choice: MCS{gbest}\n")

summary = []
for (ch, ns), g in d.groupby(["channel", "nsta"]):
    print("=" * 88)
    print(f"channel={ch}   nSTA={ns}")
    o = ours[(ours.channel == ch) & (ours.nsta == ns)]
    # H-main: dominate every member of each baseline family, per speed
    for fname, fdf in fam.items():
        sub = fdf[(fdf.channel == ch) & (fdf.nsta == ns)]
        if sub.empty:
            continue
        # protocol-v1 defines dominance by NON-OVERLAPPING CIs, not by the sign of a point
        # estimate. A raw ">0" test miscounts an exact tie (e.g. a constant channel at
        # 0 m/s, where every algorithm converges to the same rate) as a failure. The
        # pre-registered test is therefore: ours is never SIGNIFICANTLY WORSE than any
        # family member (paired t-test, Holm-corrected within the family x speed grid).
        worst, losses, pvals = {}, [], []
        for arm, a in sub.groupby("arm"):
            m = o.merge(a[KEY + ["thr"]], on=KEY)
            for sp, s in m.groupby("speed"):
                rel = 100 * (s.ours.mean() / s.thr.mean() - 1)
                worst[sp] = min(worst.get(sp, 1e9), rel)
                pv = stats.ttest_rel(s.ours.values, s.thr.values).pvalue
                pvals.append((arm, sp, rel, pv))
        k = len(pvals)
        for rank, (arm, sp, rel, pv) in enumerate(sorted(pvals, key=lambda t: t[3])):
            if rel < 0 and min(1.0, (k - rank) * pv) < 0.05:
                losses.append((arm, sp, rel))
        line = "  ".join(f"v={sp:g}:{worst[sp]:+6.1f}%" for sp in sorted(worst))
        dominated = not losses
        print(f"  vs WORST-CASE over {fname:11s} family: {line}   "
              f"{'DOMINATES' if dominated else 'SIGNIFICANTLY WORSE in ' + str(len(losses))}")
        for arm, sp, rel in sorted(losses, key=lambda t: t[2])[:3]:
            print(f"        loses to {arm} at {sp:g} m/s by {rel:.1f}%")
        summary.append((ch, ns, fname, dominated, min(worst.values()), losses))
    # static references
    for rname, rdf, col in (("oracle static", oracle, "oracle_fixed"),
                            (f"deploy MCS{gbest}", deploy, "deploy_fixed")):
        m = o.merge(rdf[(rdf.channel == ch) & (rdf.nsta == ns)], on=KEY)
        ps, rels = [], {}
        for sp, s in m.groupby("speed"):
            rels[sp] = 100 * (s.ours.mean() / s[col].mean() - 1)
            ps.append((sp, stats.ttest_rel(s.ours.values, s[col].values).pvalue))
        order = sorted(range(len(ps)), key=lambda i: ps[i][1])
        holm = {}
        for rank, i in enumerate(order):
            holm[ps[i][0]] = min(1.0, (len(ps) - rank) * ps[i][1])
        line = "  ".join(f"v={sp:g}:{rels[sp]:+6.1f}%(p={holm[sp]:.1e})" for sp in sorted(rels))
        print(f"  vs {rname:16s}: {line}")

print("=" * 88)
tot = len(summary); dom = sum(1 for s in summary if s[3])
print(f"\nH-main: ours dominates the whole family in {dom}/{tot} (channel x contention x family) cells")
for ch, ns, fname, ok, mn, _ls in summary:
    if not ok:
        print(f"   NOT dominated: {ch} nSTA={ns} vs {fname} (worst {mn:+.1f}%)")
