#!/usr/bin/env python3
"""With evidence sharing off, CqrWifiManager must be byte-identical to the upstream
ThompsonSamplingWifiManager. The paper rests on this: it is what makes any measured
difference attributable to the propagation rule rather than to the reimplementation.

The paper says this is re-checked after every change to the manager, so it needs to be
a script and not a thing someone remembers to do. Run it after touching the module.
"""
import argparse, itertools, subprocess, sys, tempfile, shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import pandas as pd

import _ns3

BIN = _ns3.binary(_ns3.SCENARIO)
DECAYS, SPEEDS, SEEDS = (1.0, 2.0, 10.0), (0.0, 5.0, 20.0), (1, 2, 3)


def run(args):
    tmp = Path(tempfile.mkdtemp(prefix="eq_"))
    try:
        cmd = [str(BIN), f"--out={tmp/'o.csv'}", f"--rateLog={tmp/'o.rate.csv'}",
               "--nSta=4", "--channel=logdistance+jakes", "--simTime=10",
               "--interval=0.5", "--channelWidth=80", "--nss=2", *args]
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            return None
        return pd.read_csv(tmp / "o.csv").throughput_mbps.sum()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pair(cfg):
    dec, sp, sd = cfg
    common = [f"--tsDecay={dec}", f"--speed={sp}",
              "--mobility=" + ("linear" if sp > 0 else "static"), f"--seed={sd}"]
    ref = run(["--raa=ThompsonSampling", *common])
    # w=0 disables propagation; Structure is set anyway so the branch is exercised
    ours = run(["--raa=Cqr", "--cqrMode=Thompson", "--cqrStructure=Monotone",
                "--cqrStructWeight=0.0", *common])
    return cfg, ref, ours


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=_ns3.workers_default())
    a = ap.parse_args()
    _ns3.require(BIN)
    grid = list(itertools.product(DECAYS, SPEEDS, SEEDS))
    print(f"{len(grid)} configurations: Decay x speed x seed")
    bad = 0
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for (dec, sp, sd), ref, ours in ex.map(pair, grid):
            if ref is None or ours is None:
                print(f"  ERROR  d={dec} v={sp} s={sd}: run failed"); bad += 1; continue
            same = ref == ours          # exact, not approximate
            if not same:
                bad += 1
            print(f"  {'ok   ' if same else 'DIFFER'} d={dec:<5g} v={sp:<5g} seed={sd}  "
                  f"{ref:.4f} vs {ours:.4f}")
    print(f"\n{len(grid) - bad}/{len(grid)} byte-identical")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
