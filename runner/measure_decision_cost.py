#!/usr/bin/env python3
"""Measure the per-decision cost of monotone propagation.

protocol-v1 §6 pre-commits "the policy's own decision cost" as a secondary metric and
justifies expecting it to be negligible on the grounds that the policy "is a scalar
recursion". That was true of the withdrawn calibrated-quantile rule. It is not true of
monotone propagation, which walks the whole rate order on every outcome, so the cost is
linear in rate-table size -- the quantity the paper argues is growing.

Isolation. PropagateMonotone returns immediately when StructureWeight <= 0. Comparing
w = 0 against w = 1e-12 therefore switches the loop on and off while adding evidence too
small to change any decision, so the two arms follow the same trajectory and the
wall-clock difference is the loop and nothing else. The script checks that premise rather
than assuming it: if throughput differs between the arms, the isolation has failed and
the timing is meaningless.
"""
import argparse, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import pandas as pd

import _ns3

BIN = _ns3.binary(_ns3.SCENARIO)
# 802.11be: 12 MCS x nss x (number of usable widths). Matches the paper's 12..72 range.
CONFIGS = [(20, 1), (40, 1), (80, 1), (80, 2)]
N_RATES = {(20, 1): 12, (40, 1): 24, (80, 1): 36, (80, 2): 72}


def one(cfg):
    width, nss, w, seed, log = cfg
    tmp = Path(tempfile.mkdtemp(prefix="dc_"))
    try:
        cmd = [str(BIN), f"--out={tmp/'o.csv'}", "--raa=Cqr", "--cqrMode=Thompson",
               "--cqrStructure=Monotone", f"--cqrStructWeight={w}",
               "--cqrOrder=RequiredSnr", "--nSta=4", "--channel=logdistance+jakes",
               "--simTime=10", "--interval=0.5", f"--channelWidth={width}",
               f"--nss={nss}", "--speed=5", "--mobility=linear", f"--seed={seed}"]
        if log:
            cmd.append(f"--cqrLog={tmp/'d.log'}")
        t0 = time.perf_counter()
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=600)
        wall = time.perf_counter() - t0
        if p.returncode != 0:
            return None
        thr = pd.read_csv(tmp / "o.csv").throughput_mbps.sum()
        n_dec = None
        if log:
            n_dec = sum(sum(1 for _ in open(f)) for f in tmp.glob("d.log.*"))
        return dict(width=width, nss=nss, w=w, seed=seed, wall=wall, thr=thr, n_dec=n_dec)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--workers", type=int, default=3,
                    help="kept low deliberately: timing under full load is noise")
    ap.add_argument("--out", default="", help="optional parquet of the raw per-run timings")
    a = ap.parse_args()

    grid = [(wd, ns, w, s, False)
            for (wd, ns) in CONFIGS for w in (0.0, 1e-12)
            for s in range(1, a.seeds + 1)]
    grid += [(wd, ns, 1e-12, 1, True) for (wd, ns) in CONFIGS]   # decision counts
    _ns3.require(BIN)
    print(f"{len(grid)} runs on {a.workers} workers", flush=True)

    rows = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, r in enumerate(ex.map(one, grid), 1):
            if r:
                rows.append(r)
            if i % 10 == 0:
                print(f"  {i}/{len(grid)}", flush=True)
    d = pd.DataFrame(rows)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        d.to_parquet(a.out, index=False)
        print(f"raw timings -> {a.out}")

    timed = d[d.n_dec.isna()]
    counts = d[d.n_dec.notna()].set_index(["width", "nss"]).n_dec

    from scipy import stats
    import numpy as np

    print(f"\n{'config':>9s} {'rates':>6s} {'decisions':>10s} {'paired dwall':>14s} "
          f"{'95% CI':>20s} {'per-dec':>12s} {'thr diff':>9s}")
    pts = []
    for (wd, ns) in CONFIGS:
        s = timed[(timed.width == wd) & (timed.nss == ns)]
        off = s[s.w == 0.0].set_index("seed").wall
        on  = s[s.w > 0.0].set_index("seed").wall
        d_paired = (on - off).dropna()              # same seed = same trajectory = same work
        m = d_paired.mean()
        ci = stats.t.interval(0.95, len(d_paired)-1, loc=m,
                              scale=stats.sem(d_paired)) if len(d_paired) > 1 else (m, m)
        nd = counts.loc[(wd, ns)]
        tdiff = 100 * (on.mean() and (s[s.w > 0.0].thr.mean() / s[s.w == 0.0].thr.mean() - 1))
        pts.append((N_RATES[(wd, ns)], m / nd * 1e9, nd))
        print(f"{wd:>6d}/{ns:<2d} {N_RATES[(wd,ns)]:>6d} {int(nd):>10d} "
              f"{m*1000:>+12.1f}ms  [{ci[0]*1000:>+7.1f},{ci[1]*1000:>+7.1f}]ms "
              f"{m/nd*1e9:>+10.0f}ns {tdiff:>+8.3f}%")

    print("\nthr diff is the isolation check: 0.000% means both arms ran the identical")
    print("trajectory, so any wall-clock delta is the propagation loop alone.")

    # Does the cost scale with rate-table size, as the structure predicts?
    x = np.array([p[0] for p in pts], float)
    y = np.array([p[1] for p in pts], float)
    sl, ic, r, pv, se = stats.linregress(x, y)
    print(f"\nper-decision cost vs rate-table size: slope {sl:+.1f} ns/rate "
          f"(p={pv:.2f}, r={r:+.2f})")

    # Rigorous statement: what can this instrument actually resolve?
    allp = []
    for (wd, ns) in CONFIGS:
        s = timed[(timed.width == wd) & (timed.nss == ns)]
        off = s[s.w == 0.0].set_index("seed").wall
        on  = s[s.w > 0.0].set_index("seed").wall
        dd = (on - off).dropna()
        nd = counts.loc[(wd, ns)]
        allp.append(np.abs(stats.t.interval(0.95, len(dd)-1, loc=dd.mean(),
                    scale=stats.sem(dd))).max() / nd * 1e9)
    print(f"resolution of this instrument: +/-{max(allp):.0f} ns per decision "
          f"(widest 95% CI half-width across configs)")
    print("A measured value inside that band is indistinguishable from zero here.")


if __name__ == "__main__":
    sys.exit(main())
