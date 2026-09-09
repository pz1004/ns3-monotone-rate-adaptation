#!/usr/bin/env python3
"""
GATE 1 driver: 802.11be rate adaptation under mobility/contention.

Runs the adaptive managers plus a ConstantRate sweep over every EHT MCS.
The per-interval max over the ConstantRate runs is the best-fixed-rate genie
oracle -- a true upper bound, unlike IdealWifiManager.
"""
import argparse, itertools, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

import _ns3

BIN = _ns3.binary(_ns3.SCENARIO)


def one_run(cfg):
    raa, mcs, nsta, speed, width, nss, simtime, seed, interval, chan, decay = cfg
    tag = f"{raa}" + (f"-mcs{mcs}" if raa == "ConstantRate" else "")
    if raa == "ThompsonSampling" and decay is not None:
        tag += f"-d{decay}"
    run_id = f"{tag}_n{nsta}_v{speed}_w{width}_ss{nss}_{chan}_s{seed}"
    tmp = Path(tempfile.mkdtemp(prefix="g1_"))
    out = tmp / "o.csv"
    cmd = [str(BIN), f"--raa={raa}", f"--nSta={nsta}", f"--speed={speed}",
           "--mobility=" + ("linear" if speed > 0 else "static"),
           f"--channelWidth={width}", f"--nss={nss}", f"--simTime={simtime}",
           f"--seed={seed}", f"--interval={interval}", f"--channel={chan}",
           f"--out={out}"]
    if raa == "ConstantRate":
        cmd.append(f"--mcs={mcs}")
    if raa == "ThompsonSampling" and decay is not None:
        cmd.append(f"--tsDecay={decay}")
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=1800)
        wall = time.time() - t0
        if p.returncode != 0 or not out.exists():
            return run_id, None, f"rc={p.returncode} {p.stderr[-250:]}", wall
        df = pd.read_csv(out)
        df["raa"] = raa; df["mcs"] = mcs if raa == "ConstantRate" else -1
        df["nsta"] = nsta; df["speed"] = speed; df["width"] = width
        df["nss"] = nss; df["seed"] = seed; df["run_id"] = run_id; df["wall_s"] = wall
        df["channel"] = chan
        df["decay"] = decay if decay is not None else -1.0
        df["variant"] = tag
        return run_id, df, None, wall
    except subprocess.TimeoutExpired:
        return run_id, None, "timeout", time.time() - t0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--managers", nargs="+",
                    default=["MinstrelHt", "ThompsonSampling", "Ideal"])
    ap.add_argument("--mcs-list", nargs="+", type=int, default=list(range(14)))
    ap.add_argument("--nsta", nargs="+", type=int, default=[1])
    ap.add_argument("--speeds", nargs="+", type=float, default=[0.0, 2.0])
    ap.add_argument("--widths", nargs="+", type=int, default=[80])
    ap.add_argument("--nss", nargs="+", type=int, default=[2])
    ap.add_argument("--sim-time", type=float, default=20.0)
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3])
    ap.add_argument("--workers", type=int, default=_ns3.workers_default())
    ap.add_argument("--channels", nargs="+", default=["logdistance"])
    ap.add_argument("--ts-decays", nargs="+", type=float, default=[])
    ap.add_argument("--dry-run", action="store_true",
                    help="print the grid size and exit; no ns-3 build needed")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    grid = []
    for nsta, sp, w, ns, sd, ch in itertools.product(a.nsta, a.speeds, a.widths,
                                                     a.nss, a.seeds, a.channels):
        for m in a.managers:
            if m == "ThompsonSampling" and a.ts_decays:
                for dc in a.ts_decays:
                    grid.append((m, -1, nsta, sp, w, ns, a.sim_time, sd, a.interval, ch, dc))
            else:
                grid.append((m, -1, nsta, sp, w, ns, a.sim_time, sd, a.interval, ch, None))
        for k in a.mcs_list:
            grid.append(("ConstantRate", k, nsta, sp, w, ns, a.sim_time, sd,
                         a.interval, ch, None))

    print(f"[gate1] {len(grid)} runs on {a.workers} workers", flush=True)
    if a.dry_run:
        return 0                      # grid size only -- verify a sweep before spending days on it
    _ns3.require(BIN)
    frames, fails, t0 = [], [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(one_run, c) for c in grid]
        for i, f in enumerate(as_completed(futs), 1):
            rid, df, err, wall = f.result()
            if err:
                fails.append((rid, err))
            else:
                frames.append(df)
            if i % 25 == 0 or i == len(grid):
                print(f"  {i}/{len(grid)} elapsed={time.time()-t0:.0f}s fails={len(fails)}",
                      flush=True)

    if not frames:
        print("[gate1] NO DATA"); 
        for r, e in fails[:5]: print("  ", r, e)
        return 1
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.concat(frames, ignore_index=True)
    df.to_parquet(out.with_suffix(".parquet"), index=False)
    print(f"[gate1] {len(df)} rows -> {out}.parquet in {time.time()-t0:.0f}s "
          f"({len(fails)} failures)")
    for r, e in fails[:8]:
        print("   FAIL", r, e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
