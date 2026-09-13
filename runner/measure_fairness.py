#!/usr/bin/env python3
"""Per-STA Jain fairness (protocol-v1 §6).

§6 pre-commits per-STA Jain fairness as a secondary metric. It went unreported because the
scenario logged only per-interval *aggregate* throughput, so the per-station breakdown the
index needs did not exist in the released data. The scenario now accepts --perStaOut, which
records each sink's per-interval delta. That is pure observation: Sample() already calls
GetTotalRx() on every sink to build the aggregate, so recording the per-sink deltas adds no
simulator interaction and cannot change a run.

Jain's index over per-STA delivered bytes x_i:  J = (sum x_i)^2 / (n * sum x_i^2).
J = 1 is perfectly equal, J = 1/n is one station taking everything.
"""
import argparse, itertools, shutil, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
import pandas as pd

import _ns3

BIN = _ns3.binary(_ns3.SCENARIO)

# All arms on the 84-arm EHT table (protocol-v1 A9.1). ns3::ThompsonSamplingWifiManager
# cannot enumerate EHT, so the Thompson arm runs as Cqr with propagation disabled -- the
# path verify_equivalence.py proves byte-identical to the shipped sampler.
MOD_FAMILY = "Latest"
ARMS = {
    "proposed":    ["--raa=Cqr", "--cqrMode=Thompson", "--cqrStructure=Monotone",
                    "--cqrStructWeight=0.25", "--cqrOrder=RequiredSnr"],
    "Thompson":    ["--raa=Cqr", "--cqrMode=Thompson", "--cqrStructure=Monotone",
                    "--cqrStructWeight=0"],
    "Minstrel-HT": ["--raa=MinstrelHt"],
}


def one(cfg):
    arm, nsta, chan, speed, seed, decay, simt = cfg
    tmp = Path(tempfile.mkdtemp(prefix="jf_"))
    try:
        cmd = [str(BIN), f"--out={tmp/'o.csv'}", f"--perStaOut={tmp/'p.csv'}",
               *ARMS[arm], f"--nSta={nsta}", f"--channel={chan}", f"--simTime={simt}",
               "--interval=0.5", "--channelWidth=80", "--nss=2", f"--tsDecay={decay}",
               f"--modFamily={MOD_FAMILY}",
               f"--speed={speed}", "--mobility=" + ("linear" if speed > 0 else "static"),
               f"--seed={seed}"]
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            return None
        per = pd.read_csv(tmp / "p.csv")
        x = per.groupby("sta").rx_bytes.sum().values.astype(float)
        if x.sum() <= 0:
            return None
        jain = float(x.sum() ** 2 / (len(x) * (x ** 2).sum()))
        return dict(arm=arm, nsta=nsta, channel=chan, speed=speed, seed=seed,
                    jain=jain, thr=float(x.sum()), min_share=float(x.min() / x.sum()))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nsta", nargs="+", type=int, default=[4, 8])
    ap.add_argument("--speeds", nargs="+", type=float, default=[1.0, 5.0, 20.0],
                    help="default is the held-out split (protocol-v1 S2)")
    ap.add_argument("--channels", nargs="+",
                    default=["logdistance", "logdistance+jakes"])
    ap.add_argument("--seeds", nargs="+", type=int, default=list(range(1, 11)))
    ap.add_argument("--decay", type=float, default=2.0)
    ap.add_argument("--sim-time", type=float, default=10.0)
    ap.add_argument("--workers", type=int, default=_ns3.workers_default())
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    grid = [(arm, n, c, s, sd, a.decay, a.sim_time)
            for arm in ARMS for n in a.nsta for c in a.channels
            for s in a.speeds for sd in a.seeds]
    _ns3.require(BIN)
    print(f"[fairness] {len(grid)} runs on {a.workers} workers", flush=True)

    rows, fails = [], 0
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, r in enumerate(ex.map(one, grid), 1):
            rows.append(r) if r else None
            fails += r is None
            if i % 60 == 0:
                print(f"  {i}/{len(grid)} fails={fails}", flush=True)
    d = pd.DataFrame(rows)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        d.to_parquet(a.out, index=False)
        print(f"[fairness] {len(d)} rows -> {a.out} ({fails} failures)")

    print(f"\n{'arm':>12s} {'STAs':>5s} {'Jain (mean +/- 95% CI)':>26s} {'worst run':>10s} "
          f"{'min share':>10s}")
    for (arm, n), g in d.groupby(["arm", "nsta"]):
        m, sem = g.jain.mean(), g.jain.sem()
        print(f"{arm:>12s} {n:>5d} {m:>17.4f} +/- {1.96*sem:<6.4f} {g.jain.min():>10.4f} "
              f"{g.min_share.min():>10.4f}")
    print("\nJain = 1 is perfectly equal; 1/n is one station taking everything "
          "(0.25 at 4 STAs, 0.125 at 8).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
