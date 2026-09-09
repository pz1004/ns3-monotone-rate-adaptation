#!/usr/bin/env python3
"""
Parallel sweep driver for ns-3 wifi-manager-example.

Runs the (manager x standard x width x nss x stepTime) grid in isolated temp dirs,
parses the gnuplot output into tidy rows, and writes one Parquet + CSV.

Schema (frozen 2026-09-07):
    run_id, manager, standard, width_mhz, nss, gi_ns, step_size_db, step_time_s,
    seed, snr_db, series, rate_mbps, wall_s
  series in {"selected", "observed"}
"""
import argparse, itertools, os, re, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

import _ns3

BIN = _ns3.binary(_ns3.WIFI_MANAGER_EXAMPLE)


def parse_plt(path: Path):
    """Return [(series, snr_db, rate_mbps)]. Two '-' series: selected then observed."""
    txt = path.read_text().splitlines()
    try:
        start = next(i for i, l in enumerate(txt) if l.startswith("plot "))
    except StopIteration:
        return []
    rows, series_idx = [], 0
    names = ["selected", "observed"]
    for line in txt[start + 1:]:
        line = line.strip()
        if line == "e":
            series_idx += 1
            if series_idx >= 2:
                break
            continue
        parts = line.split()
        if len(parts) == 2:
            try:
                rows.append((names[series_idx], float(parts[0]), float(parts[1])))
            except ValueError:
                pass
    return rows


def one_run(cfg):
    mgr, std, width, nss, gi, step_size, step_time, seed, keep_stats = cfg
    run_id = f"{mgr}_{std}_{width}MHz_{nss}ss_{gi}ns_st{step_time}_s{seed}"
    tmp = Path(tempfile.mkdtemp(prefix="ns3run_"))
    cmd = [str(BIN),
           f"--wifiManager={mgr}", f"--standard={std}",
           f"--serverChannelWidth={width}", f"--clientChannelWidth={width}",
           f"--serverNss={nss}", f"--clientNss={nss}",
           f"--serverShortGuardInterval={gi}", f"--clientShortGuardInterval={gi}",
           f"--stepSize={step_size}", f"--stepTime={step_time}",
           f"--RngRun={seed}"]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=900)
        wall = time.time() - t0
        if p.returncode != 0:
            return run_id, [], f"rc={p.returncode}: {p.stderr[-300:]}", wall
        plts = list(tmp.glob("*.plt"))
        if not plts:
            return run_id, [], "no .plt produced", wall
        rows = parse_plt(plts[0])
        if keep_stats:
            dst = Path(keep_stats) / run_id
            dst.mkdir(parents=True, exist_ok=True)
            for f in tmp.glob("minstrel*stats*.txt"):
                shutil.copy(f, dst / f.name)
        recs = [dict(run_id=run_id, manager=mgr, standard=std, width_mhz=width,
                     nss=nss, gi_ns=gi, step_size_db=step_size, step_time_s=step_time,
                     seed=seed, series=s, snr_db=snr, rate_mbps=rate, wall_s=wall)
                for (s, snr, rate) in rows]
        return run_id, recs, None, wall
    except subprocess.TimeoutExpired:
        return run_id, [], "timeout", time.time() - t0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--managers", nargs="+",
                    default=["Ideal", "MinstrelHt", "ThompsonSampling"])
    ap.add_argument("--standards", nargs="+",
                    default=["802.11n-5GHz", "802.11ac", "802.11ax-5GHz", "802.11be-5GHz"])
    ap.add_argument("--widths", nargs="+", type=int, default=[20, 40, 80])
    ap.add_argument("--nss", nargs="+", type=int, default=[1, 2])
    ap.add_argument("--gi", nargs="+", type=int, default=[800])
    ap.add_argument("--step-size", type=float, default=1.0)
    ap.add_argument("--step-times", nargs="+", type=float, default=[1.0])
    ap.add_argument("--seeds", nargs="+", type=int, default=[1])
    ap.add_argument("--workers", type=int, default=_ns3.workers_default())
    ap.add_argument("--dry-run", action="store_true",
                    help="print the grid size and exit; no ns-3 build needed")
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep-stats", default="")
    a = ap.parse_args()

    grid = [c for c in itertools.product(a.managers, a.standards, a.widths, a.nss,
                                         a.gi, [a.step_size], a.step_times, a.seeds,
                                         [a.keep_stats])]
    print(f"[runner] {len(grid)} runs on {a.workers} workers", flush=True)
    if a.dry_run:
        return 0                      # grid size only -- verify a sweep before spending days on it
    _ns3.require(BIN)
    recs, fails, t0 = [], [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one_run, c): c for c in grid}
        for i, f in enumerate(as_completed(futs), 1):
            rid, r, err, wall = f.result()
            if err:
                fails.append((rid, err))
            recs.extend(r)
            if i % 25 == 0 or i == len(grid):
                print(f"  {i}/{len(grid)}  elapsed={time.time()-t0:.0f}s "
                      f"fails={len(fails)}", flush=True)

    df = pd.DataFrame(recs)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    if not df.empty:
        df.to_parquet(out.with_suffix(".parquet"), index=False)
        df.to_csv(out.with_suffix(".csv"), index=False)
    print(f"[runner] wrote {len(df)} rows -> {out}.parquet/.csv "
          f"in {time.time()-t0:.0f}s")
    if fails:
        print(f"[runner] {len(fails)} FAILURES (first 10):")
        for rid, e in fails[:10]:
            print(f"   {rid}: {e}")
    return 0 if not df.empty else 1


if __name__ == "__main__":
    sys.exit(main())
