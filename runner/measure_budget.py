#!/usr/bin/env python3
"""Measure the propagated-evidence budget each ordering actually spends.

Sec. VI-A qualifies the ordering ablation: Eq. (1) shares w*(n_s*r + n_f*(N-1-r)) for a
report at rank r, so a fixed w does not fix the TOTAL propagated pseudo-count -- it depends
on where the played configuration sits, which differs between orderings. The manuscript
argued that from the equation. The manager has accumulated the realised quantities per run
since the budget instrumentation landed (succ_mass, fail_mass, targets, rank_sum in the
cost log); this harvests them, on the same grid as the ordering ablation, so the
qualification can be settled by measurement (protocol-v1 amendment A9.16).

Grid mirrors results/mono/order_matched.parquet exactly: w=0.25, lambda=2 Hz, 4 STAs,
logdistance+jakes, speeds {5, 20}, all six (width, streams) groups, 10 seeds -- run once
per ordering.

    python measure_budget.py --workers 24 -o results/mono/budget.parquet
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import _ns3

BIN = _ns3.binary(_ns3.SCENARIO)
ORDERS = ["RequiredSnr", "DataRate"]
SPEEDS = [5.0, 20.0]
GROUPS = [(20, 1), (20, 2), (40, 1), (40, 2), (80, 1), (80, 2)]
SEEDS = range(1, 11)
W, LAM, NSTA, CHANNEL, SIMTIME = 0.25, 2.0, 4, "logdistance+jakes", 10


def one(cfg):
    order, speed, width, nss, seed = cfg
    tmp = Path(tempfile.mkdtemp(prefix="bud_"))
    try:
        subprocess.run(
            [str(BIN), f"--out={tmp/'o.csv'}", "--raa=Cqr", "--cqrMode=Thompson",
             "--cqrStructure=Monotone", f"--cqrStructWeight={W}", f"--cqrOrder={order}",
             "--modFamily=Latest", f"--tsDecay={LAM}", f"--nSta={NSTA}",
             f"--channel={CHANNEL}", f"--simTime={SIMTIME}", "--interval=0.5",
             f"--channelWidth={width}", f"--nss={nss}", f"--speed={speed}",
             "--mobility=linear", f"--seed={seed}", f"--cqrCostLog={tmp/'c'}"],
            cwd=tmp, capture_output=True, text=True, timeout=900, check=True)
        rows = []
        for f in tmp.glob("c.*"):
            ln = f.read_text().splitlines()
            if len(ln) < 2:
                continue
            rec = dict(zip(ln[0].split(","), (float(x) for x in ln[1].split(","))))
            rows.append(rec)
        if not rows:
            return None
        # One manager instance per station; the budget is spent across all of them.
        agg = {k: sum(r[k] for r in rows) for k in rows[0]}
        n_arms = int(round(agg["sum_rates"] / agg["calls"])) if agg["calls"] else 0
        return dict(order=order, speed=speed, width=width, nss=nss, seed=seed,
                    n_arms=n_arms, calls=agg["calls"], targets=agg["targets"],
                    succ_mass=agg["succ_mass"], fail_mass=agg["fail_mass"],
                    total_mass=agg["succ_mass"] + agg["fail_mass"],
                    mean_rank=agg["rank_sum"] / agg["calls"] if agg["calls"] else float("nan"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the grid size and exit, running nothing")
    ap.add_argument("-o", "--out", default="results/mono/budget.parquet")
    a = ap.parse_args()
    _ns3.require(BIN)

    grid = [(o, sp, w, n, s) for o in ORDERS for sp in SPEEDS
            for (w, n) in GROUPS for s in SEEDS]
    print(f"[budget] {len(grid)} runs on {a.workers} workers", flush=True)
    if a.dry_run:
        return
    rows, fails = [], 0
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(one, c) for c in grid]
        for i, f in enumerate(as_completed(futs), 1):
            try:
                r = f.result()
            except Exception as e:                      # noqa: BLE001
                fails += 1
                print(f"  run failed: {e}", file=sys.stderr)
                continue
            if r is None:
                fails += 1
            else:
                rows.append(r)
            if i % 20 == 0 or i == len(grid):
                print(f"  {i}/{len(grid)} fails={fails}", flush=True)

    df = pd.DataFrame(rows)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.out)
    print(f"[budget] {len(df)} rows -> {a.out} ({fails} failures)")


if __name__ == "__main__":
    main()
