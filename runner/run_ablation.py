#!/usr/bin/env python3
"""Factorial ablation driver with pre-registered tune/eval speed splits (protocol-v1 S2)."""
import argparse, itertools, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import pandas as pd

import _ns3

BIN = _ns3.binary(_ns3.SCENARIO)

# Action set for the learning managers. "Latest" enumerates EHT MCS 0-13 (84 arms), which
# is the table IdealWifiManager, MinstrelHt and the ConstantRate references already use;
# "MatchUpstream" stops at HE (72 arms) and reproduces ns3::ThompsonSamplingWifiManager
# exactly. See protocol-v1 amendment A9.1. Set by --mod-family.
MOD_FAMILY = "Latest"

def one(cfg):
    arm, raa, mode, struct, w, decay, nsta, sp, chan, sd, simt, width, nss, ors, mcs, mh, dec, order = cfg
    tmp = Path(tempfile.mkdtemp(prefix="ab_")); out = tmp/"o.csv"; rl = tmp/"o.rate.csv"
    cmd = [str(BIN), f"--raa={raa}", f"--cqrMode={mode}", f"--cqrStructure={struct}",
           f"--cqrStructWeight={w}", f"--cqrOrder={order}",
           f"--tsDecay={decay}", f"--nSta={nsta}",
           f"--speed={sp}", "--mobility=" + ("linear" if sp>0 else "static"),
           f"--channel={chan}", f"--simTime={simt}", "--interval=0.5",
           f"--seed={sd}", f"--channelWidth={width}", f"--nss={nss}",
           f"--orsVariant={ors[0]}", f"--orsOrder={ors[1]}", f"--orsWindow={ors[2]}",
           f"--mcs={mcs}", f"--mhSampleColumn={mh[0]}", f"--mhUpdateMs={mh[1]}",
           f"--cqrDecayAdapt={dec[0]}", f"--cqrDecayTarget={dec[1]}",
           f"--cqrDecayEta={dec[2]}", f"--modFamily={MOD_FAMILY}",
           f"--out={out}", f"--rateLog={rl}"]
    try:
        p = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=1800)
        if p.returncode != 0 or not out.exists() or not rl.exists():
            return None, f"{arm} sp={sp} sd={sd}: rc={p.returncode}"
        samples = pd.read_csv(out).throughput_mbps
        # Sum of per-interval Mb/s AND the sample count, so mean throughput can be formed
        # without assuming how many intervals a run produced (protocol-v1 A9.4: the held-out
        # table divided 19 samples by 20).
        thr, n_int = samples.sum(), int(samples.size)
        r = pd.read_csv(rl)
        tot = int(r[r.field=="total_phy_tx"]["count"].iloc[0])
        rxb = int(r[r.field=="rx_bytes_total"]["count"].iloc[0])

        def _mean(field):
            """Count-weighted mean of a numeric marginal."""
            k = r[r.field == field]
            if k.empty:
                return float("nan")
            v = pd.to_numeric(k["value"], errors="coerce").to_numpy(dtype=float)
            c = pd.to_numeric(k["count"], errors="coerce").to_numpy(dtype=float)
            return float((v * c).sum() / c.sum())

        # The MCS index alone cannot express aggressiveness once width and streams vary:
        # a higher MCS at fewer streams can be a LOWER PHY rate. Report all three marginals
        # and the mean selected PHY rate from the joint distribution (A9.3).
        mean_mcs, mean_width, mean_nss = _mean("mcs"), _mean("width"), _mean("nss")
        mean_phyrate = _mean("phyrate")
        return dict(arm=arm, w=w, decay=decay, order=order, nsta=nsta, speed=sp, channel=chan, seed=sd,
                    ors_variant=ors[0], ors_order=ors[1], ors_window=ors[2], mcs=mcs, mh_col=mh[0], mh_ms=mh[1], dmode=dec[0], dtarget=dec[1],
                    width=width, nss=nss, mod_family=MOD_FAMILY, n_intervals=n_int,
                    thr=thr, mean_mcs=mean_mcs, mean_width=mean_width, mean_nss=mean_nss,
                    mean_phyrate=mean_phyrate,
                    tx_per_MB=tot/(rxb/1e6) if rxb else float('nan')), None
    except subprocess.TimeoutExpired:
        return None, f"{arm} sp={sp} sd={sd}: timeout"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--speeds", nargs="+", type=float, required=True)
    a.add_argument("--weights", nargs="+", type=float, default=[0.05])
    a.add_argument("--nsta", nargs="+", type=int, default=[4])
    a.add_argument("--channels", nargs="+", default=["logdistance+jakes"])
    a.add_argument("--widths", nargs="+", type=int, default=[80])
    a.add_argument("--nss", nargs="+", type=int, default=[2])
    a.add_argument("--seeds", nargs="+", type=int, default=list(range(1,11)))
    a.add_argument("--decay", type=float, default=2.0)
    a.add_argument("--ts-decays", nargs="+", type=float, default=[])
    a.add_argument("--ors", nargs="+", default=[],
                   help="ORS arms as VARIANT:ORDER:WINDOW, e.g. SW-ORS:DataRate:200")
    a.add_argument("--no-mono", action="store_true")
    a.add_argument("--cqr-orders", nargs="+", default=["RequiredSnr"],
                   help="propagation orderings to sweep: RequiredSnr and/or DataRate")
    a.add_argument("--const-mcs", nargs="+", type=int, default=[])
    a.add_argument("--minstrel-cols", nargs="+", type=int, default=[])
    a.add_argument("--decay-targets", nargs="+", type=float, default=[])
    a.add_argument("--decay-eta", type=float, default=0.05)
    a.add_argument("--checkpoint-every", type=int, default=250)
    a.add_argument("--sim-time", type=float, default=10.0)
    a.add_argument("--workers", type=int, default=24)
    a.add_argument("--dry-run", action="store_true",
                   help="print the grid size and exit, running nothing")
    a.add_argument("--mod-family", default="Latest", choices=["Latest", "MatchUpstream"],
                   help="action set for the learning managers (protocol-v1 A9.1)")
    a.add_argument("--out", required=True)
    a = a.parse_args()
    global MOD_FAMILY
    MOD_FAMILY = a.mod_family

    grid = []
    for nsta, sp, ch, sd, wd, ns in itertools.product(a.nsta, a.speeds, a.channels,
                                                      a.seeds, a.widths, a.nss):
        DEF=("SW-ORS","DataRate",200); MH=(10,50.0); DF=("Fixed",0.05,0.05)
        OD="RequiredSnr"
        grid.append(("Ideal","Ideal","Thompson","None",0.0,a.decay,nsta,sp,ch,sd,a.sim_time,wd,ns,DEF,-1,MH,DF,OD))
        for dc in (a.ts_decays or [a.decay]):
            # ns3::ThompsonSamplingWifiManager has no EHT enumeration branch, so on the
            # 84-arm table it cannot be run directly. Cqr with Structure=Monotone and
            # StructureWeight=0 takes the same code path with propagation disabled, and
            # verify_equivalence.py proves that path is byte-identical to the shipped
            # sampler on the HE table (27/27). See protocol-v1 amendment A9.1.
            if MOD_FAMILY == "Latest":
                grid.append((f"Thompson(d={dc})","Cqr","Thompson","Monotone",0.0,
                             dc,nsta,sp,ch,sd,a.sim_time,wd,ns,DEF,-1,MH,DF,OD))
            else:
                grid.append((f"Thompson(d={dc})","ThompsonSampling","Thompson","None",0.0,
                             dc,nsta,sp,ch,sd,a.sim_time,wd,ns,DEF,-1,MH,DF,OD))
        if not a.no_mono:
            for w in a.weights:
                for od in a.cqr_orders:
                    tag = f"Mono(w={w})" if od == "RequiredSnr" else f"Mono/{od}(w={w})"
                    grid.append((tag,"Cqr","Thompson","Monotone",w,a.decay,
                                 nsta,sp,ch,sd,a.sim_time,wd,ns,DEF,-1,MH,DF,od))
        for k in a.const_mcs:
            grid.append((f"Fixed(MCS{k})","ConstantRate","Thompson","None",0.0,a.decay,
                         nsta,sp,ch,sd,a.sim_time,wd,ns,DEF,k,MH,DF,OD))
        for col in a.minstrel_cols:
            grid.append((f"MinstrelHt(col={col})","MinstrelHt","Thompson","None",0.0,
                         a.decay,nsta,sp,ch,sd,a.sim_time,wd,ns,DEF,-1,(col,50.0),DF,OD))
        for dt in a.decay_targets:
            grid.append((f"Mono+AdaptDecay(t={dt})","Cqr","Thompson","Monotone",0.25,
                         a.decay,nsta,sp,ch,sd,a.sim_time,wd,ns,DEF,-1,MH,
                         ("Adaptive",dt,a.decay_eta),OD))
        for spec in a.ors:
            v,o,win = spec.split(":")
            grid.append((f"{v}/{o}/w{win}","Ors","Thompson","None",0.0,a.decay,
                         nsta,sp,ch,sd,a.sim_time,wd,ns,(v,o,int(win)),-1,MH,DF,OD))
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)  # before any run, not after
    print(f"[ablation] {len(grid)} runs on {a.workers} workers", flush=True)
    if a.dry_run:
        return
    rows, fails, t0 = [], [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for i, f in enumerate(as_completed([ex.submit(one,c) for c in grid]), 1):
            r, e = f.result()
            (rows if r else fails).append(r if r else e)
            if a.checkpoint_every and i % a.checkpoint_every == 0 and rows:
                try:
                    tmpf = out_path.with_suffix(".partial.tmp.parquet")
                    pd.DataFrame([r for r in rows if r]).to_parquet(tmpf, index=False)
                    tmpf.replace(out_path.with_suffix(".partial.parquet"))
                except Exception as ex:  # never let checkpointing abort the campaign
                    print(f"  [warn] checkpoint failed, continuing: {ex}", flush=True)
            if i % 50 == 0 or i == len(grid):
                print(f"  {i}/{len(grid)} {time.time()-t0:.0f}s fails={len(fails)}", flush=True)
    df = pd.DataFrame(rows); out = out_path
    df.to_parquet(out.with_suffix(".parquet"), index=False)
    print(f"[ablation] {len(df)} rows -> {out}.parquet ({len(fails)} failures)")
    for e in fails[:5]: print("  FAIL", e)
    return 0
if __name__ == "__main__": sys.exit(main())
