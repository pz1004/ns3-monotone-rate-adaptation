#!/usr/bin/env python3
"""Derive results/envelope/references.parquet from the ConstantRate sweep.

Two reference points, both computed in hindsight and therefore unreachable by any online
algorithm:

  envelope    the per-interval maximum over every fixed MCS -- a genie that re-picks the
              best rate every 0.5 s interval. A true upper bound on what any rate choice
              could deliver, which IdealWifiManager is not (Thompson can exceed Ideal).
  best_fixed  the single best fixed MCS for the whole run, chosen after seeing it.

'ideal' is IdealWifiManager on the same runs, for comparison.

The parquet is committed, so this script is a check as much as a generator: run it and
the output must match the committed file exactly.
"""
import sys
import pandas as pd
import _paths

SRC = _paths.RESULTS / "envelope/const_sweep.parquet"
DST = _paths.RESULTS / "envelope/references.parquet"

cs = pd.read_parquet(SRC)
const, ideal = cs[cs.raa == "ConstantRate"], cs[cs.raa == "Ideal"]

envelope = (const.groupby(["speed", "seed", "time_s"]).throughput_mbps.max()
                 .groupby(["speed", "seed"]).sum())
per_mcs = const.groupby(["speed", "seed", "mcs"]).throughput_mbps.sum()

out = pd.DataFrame({
    "best_mcs":   per_mcs.groupby(["speed", "seed"]).idxmax().map(lambda t: t[2]),
    "best_fixed": per_mcs.groupby(["speed", "seed"]).max(),
    "envelope":   envelope,
    "ideal":      ideal.groupby(["speed", "seed"]).throughput_mbps.sum(),
}).reset_index()[["speed", "seed", "best_mcs", "best_fixed", "envelope", "ideal"]]

if "--check" in sys.argv:
    have = pd.read_parquet(DST)
    same = out.sort_values(["speed", "seed"]).reset_index(drop=True).equals(
           have.sort_values(["speed", "seed"]).reset_index(drop=True))
    print(f"{DST.name}: {'matches' if same else 'DIFFERS FROM'} the committed file")
    sys.exit(0 if same else 1)

out.to_parquet(DST, index=False)
print(f"{len(out)} rows -> {DST}")
