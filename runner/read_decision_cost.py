#!/usr/bin/env python3
"""Read the manager's own cost report: direct timing of PropagateMonotone.

Each manager instance writes calls, accumulated nanoseconds, the summed rate-table size
over those calls, and the cost of an empty steady_clock read-pair measured in the same
binary on the same clock (scaled by 1e6 for integer transport). Every timed call carries
one such pair as constant bias, so it is subtracted here rather than assumed negligible.
"""
import subprocess, sys, tempfile, shutil
from pathlib import Path

import _ns3

BIN = _ns3.binary(_ns3.SCENARIO)
CONFIGS = [(20, 1, 12), (40, 1, 24), (80, 1, 36), (80, 2, 72)]

_ns3.require(BIN)
print(f"{'config':>9s} {'rates':>6s} {'calls':>8s} {'raw ns/call':>12s} "
      f"{'clock pair':>11s} {'net ns/call':>12s} {'ns/rate':>9s}")
rows = []
for width, nss, nrates in CONFIGS:
    tot_calls = tot_ns = tot_rates = 0; pair = None
    for seed in range(1, 6):
        tmp = Path(tempfile.mkdtemp(prefix="cd_"))
        try:
            subprocess.run(
                [str(BIN), f"--out={tmp/'o.csv'}", "--raa=Cqr", "--cqrMode=Thompson",
                 "--cqrStructure=Monotone", "--cqrStructWeight=0.25",
                 "--cqrOrder=RequiredSnr", "--nSta=4", "--channel=logdistance+jakes",
                 "--simTime=10", "--interval=0.5", f"--channelWidth={width}",
                 f"--nss={nss}", "--speed=5", "--mobility=linear", f"--seed={seed}",
                 f"--cqrCostLog={tmp/'c'}"],
                cwd=tmp, capture_output=True, text=True, timeout=600, check=True)
            for f in tmp.glob("c.*"):
                ln = f.read_text().splitlines()
                if len(ln) < 2:
                    continue
                c, ns, r, p = (int(x) for x in ln[1].split(","))
                tot_calls += c; tot_ns += ns; tot_rates += r
                pair = p / 1e6 if pair is None else min(pair, p / 1e6)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    raw = tot_ns / tot_calls
    net = raw - pair
    per_rate = net / (tot_rates / tot_calls)
    rows.append((nrates, net, per_rate))
    print(f"{width:>6d}/{nss:<2d} {nrates:>6d} {tot_calls:>8d} {raw:>11.1f}ns "
          f"{pair:>10.1f}ns {net:>11.1f}ns {per_rate:>8.2f}ns")

import numpy as np
from scipy import stats
x = np.array([r[0] for r in rows], float); y = np.array([r[1] for r in rows], float)
sl, ic, rr, pv, se = stats.linregress(x, y)
print(f"\nnet cost vs rate-table size: {sl:.2f} ns/rate + {ic:.1f} ns fixed "
      f"(r={rr:+.4f}, p={pv:.4f})")
