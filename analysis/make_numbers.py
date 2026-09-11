#!/usr/bin/env python3
r"""Emit numbers.tex: every measured quantity quoted in the paper, computed from the
stored result files. Prose cites \Num... macros so no measured value is hand-typed."""
import pathlib
import numpy as np, pandas as pd
from scipy import stats

import _paths
R = _paths.RESULTS
out = {}
_DIG = str.maketrans({"0":"zero","1":"one","2":"two","3":"three","4":"four",
                      "5":"five","6":"six","7":"seven","8":"eight","9":"nine"})
def put(k, v):
    # LaTeX control sequences may contain letters only -- digits silently break them
    out[k.translate(_DIG)] = v

_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
          "fourteen fifteen sixteen seventeen eighteen nineteen twenty").split()
def putn(k, n):
    """Emit a count three ways: digits, and the spelled form the prose uses. Prose
    that spells a measured count out is as hand-typed as prose that prints it."""
    n = int(n); put(k, str(n))
    if n < len(_WORDS):
        put(k + "Word", _WORDS[n]); put(k + "WordCap", _WORDS[n].capitalize())

# ---------- starvation (Day-3 manager sweep) ----------
d = pd.read_parquet(f"{R}/day3_validation/mgr_sweep.parquet")
o = d[d.series == "observed"].copy()
nmcs = {"802.11n-5GHz": 8, "802.11ac": 10, "802.11ax-5GHz": 12, "802.11be-5GHz": 12}
o["nw"] = np.log2(o.width_mhz / 20).astype(int) + 1
o["n_rates"] = o.standard.map(nmcs) * o.nss * o.nw
o["rank"] = o.groupby("run_id").snr_db.rank(ascending=False)
e = o[o["rank"] <= 10]
p = e.pivot_table(index=["standard", "width_mhz", "nss", "n_rates"],
                  columns="manager", values="rate_mbps")
t = (100 * p.MinstrelHt / p.Ideal).rename("pct").reset_index()
put("StarveSmallPct", f"{t.loc[t.n_rates.idxmin(),'pct']:.1f}")
putn("StarveSmallN",  int(t.n_rates.min()))
be = t[(t.standard=="802.11be-5GHz") & (t.width_mhz==80) & (t.nss==2)]
put("StarveBigPct", f"{be.pct.iloc[0]:.1f}")
put("StarveBigN",   f"{int(be.n_rates.iloc[0])}")
put("StarveCorr",   f"{np.corrcoef(t.n_rates, t.pct)[0,1]:.2f}")

# ---------- per-STA Jain fairness (protocol-v1 §6 secondary metric) ----------
# Held-out speeds, both channels, 10 seeds. The index is computed per run from the
# per-STA delivered bytes; this reads the released per-run indices, it does not recompute
# them, so the paper and the artifact cannot disagree about what was measured.
jf = pd.read_parquet(f"{R}/fairness/jain.parquet")
_by = jf.groupby(["arm", "nsta"]).jain.mean()
put("JainOursFour",  f"{_by[('proposed', 4)]:.2f}")
put("JainOursEight", f"{_by[('proposed', 8)]:.2f}")
put("JainMinstrelFour",  f"{_by[('Minstrel-HT', 4)]:.2f}")
put("JainMinstrelEight", f"{_by[('Minstrel-HT', 8)]:.2f}")

_k = ["nsta", "channel", "speed", "seed"]
_p = jf[jf.arm == "proposed"].set_index(_k).jain
_t = jf[jf.arm == "Thompson"].set_index(_k).jain
_m = jf[jf.arm == "Minstrel-HT"].set_index(_k).jain
_d = (_p - _t).dropna()
assert len(_d) == 120, f"paired fairness comparison lost rows: {len(_d)}"
# A signed mean that rounds to -0.000 tells a reader nothing; the informative
# quantity is how tightly the difference is bounded.
put("JainCIThompson", f"{1.96 * _d.sem():.3f}")
put("JainPThompson",  f"{stats.ttest_rel(_p.loc[_d.index], _t.loc[_d.index]).pvalue:.2f}")
_dm = (_p - _m).dropna()
put("JainVsMinstrel", f"{_dm.mean():+.2f}")

# Fairness at the speed where every scheme breaks down, and the starvation count.
put("JainOursFast", f"{jf[(jf.arm=='proposed') & (jf.nsta==8) & (jf.speed==20)].jain.mean():.2f}")
_z = jf[jf.min_share == 0]
putn("StarvedRuns", len(_z)); putn("StarvedTotal", len(jf))
for _a, _n in (("proposed", "Ours"), ("Thompson", "Thompson"), ("Minstrel-HT", "Minstrel")):
    putn(f"Starved{_n}", int((_z.arm == _a).sum()))
# The claim in the prose is that starvation is a high-mobility phenomenon, not a
# property of any one scheme. Check it rather than print it on trust.
assert (_z.speed >= 5).all(), "starvation appears below 5 m/s; the prose says it does not"
putn("StarvedFastPct", int(round(100 * (_z.speed == 20).mean())))

# ---------- selection bias (ten seeds) ----------
b = pd.read_parquet(f"{R}/diag/bias10.parquet")
idl = b[b.arm=="Ideal"][["speed","seed","mean_mcs","tx_per_MB"]].rename(
    columns={"mean_mcs":"i_mcs","tx_per_MB":"i_tx"})
ts = b[b.arm.str.startswith("Thompson")][["speed","seed","mean_mcs","tx_per_MB"]]
m = ts.merge(idl, on=["speed","seed"])
m["bias"] = m.mean_mcs - m.i_mcs
m["txoh"] = 100*(m.tx_per_MB/m.i_tx - 1)
for sp in sorted(m.speed.unique()):
    s = m[m.speed==sp]
    tag = "V" + str(int(sp))
    put(f"Bias{tag}",   f"{s.bias.mean():+.2f}")
    put(f"BiasCI{tag}", f"{1.96*s.bias.std(ddof=1)/np.sqrt(len(s)):.2f}")
    put(f"TxOh{tag}",   f"{s.txoh.mean():+.1f}")
put("BiasRestAbs", f"{abs(m[m.speed==0].bias.mean()):.1f}")
put("BiasFastAbs", f"{m[m.speed==20].bias.mean():.2f}")
put("TxOhFastAbs", f"{m[m.speed==20].txoh.mean():.1f}")

# ---------- ordering ablation (matched: one function differs, nothing else) ----
# Both orderings come from ONE grid -- same weight, speeds, widths, streams and seeds.
# Earlier the two were read from separate experiments that also differed in w and in
# speed, so "the two differ in one function" was not something the runs established.
om = pd.read_parquet(f"{R}/mono/order_matched.parquet")
OM_REF = "Thompson(d=2.0)"
KEYW = ["speed", "seed", "width", "nss"]

def order_gain(arm):
    j = om[om.arm == arm].merge(om[om.arm == OM_REF][KEYW + ["thr"]], on=KEYW,
                                suffixes=("", "_t"))
    return 100 * (j.thr.mean() / j.thr_t.mean() - 1), stats.ttest_rel(j.thr, j.thr_t).pvalue

def order_scaling(arm, mcs_per_ss=12):
    """% throughput gain over the same Thompson reference, against rate-table size."""
    rows = []
    for (wd, ns), k in om.groupby(["width", "nss"]):
        tt = k[k.arm == OM_REF]; qq = k[k.arm == arm]
        rows.append((mcs_per_ss * ns * (int(np.log2(wd / 20)) + 1),
                     100 * (qq.thr.mean() / tt.thr.mean() - 1)))
    rows.sort(); a = np.array(rows)
    return np.corrcoef(a[:, 0], a[:, 1])[0, 1], a

# The matched grid runs a SUBSET of the held-out speeds; the caption must say which,
# or a reader assumes the same three tab:heldout reports.
_sp = sorted(om.speed.unique())
assert set(_sp) <= {1.0, 5.0, 20.0}, "matched ablation must stay on held-out speeds"
put("OrderSpeeds", ", ".join(f"{v:g}" for v in _sp))
putn("OrderSeeds", om.seed.nunique())

ARM_SNR, ARM_RATE = "Mono(w=0.25)", "Mono/DataRate(w=0.25)"
g_snr, p_snr = order_gain(ARM_SNR)
g_rate, p_rate = order_gain(ARM_RATE)
put("GainReqSnr", f"{g_snr:+.1f}"); put("GainDataRate", f"{g_rate:+.1f}")
put("PDataRate", f"{p_rate:.2f}")
c_new, arr = order_scaling(ARM_SNR)
c_old, _ = order_scaling(ARM_RATE)
put("CorrDataRate", f"{c_old:.2f}")
put("CorrReqSnr",   f"{c_new:+.2f}")
put("ScaleSmallN", f"{int(arr[0,0])}");  put("ScaleSmallPct", f"{arr[0,1]:+.1f}")
put("ScaleBigN",   f"{int(arr[-1,0])}"); put("ScaleBigPct",   f"{arr[-1,1]:+.1f}")

# On a one-dimensional table the two orderings ARE the same function, so the control
# must reproduce the treatment exactly. It does, bit for bit -- state the check, and
# fail loudly rather than quietly print a claim that has stopped being true.
one = om[(om.width == 20) & (om.nss == 1)]
xa = one[one.arm == ARM_SNR].set_index(KEYW).thr
xb = one[one.arm == ARM_RATE].set_index(KEYW).thr.reindex(xa.index)
assert np.array_equal(xa.values, xb.values), "orderings differ on a 1-D rate table"
put("OneDimN", f"{int(arr[0,0])}")
# largest p-value over the (width, nss) cells, so the prose can say "all p below"
pmax = max(stats.ttest_rel(
              om[(om.arm == ARM_SNR) & (om.width == wd) & (om.nss == ns)]
                .sort_values(["speed", "seed"]).thr.values,
              om[(om.arm == OM_REF) & (om.width == wd) & (om.nss == ns)]
                .sort_values(["speed", "seed"]).thr.values).pvalue
           for wd, ns in om.groupby(["width", "nss"]).groups)
# Round the bound UP: "{:.0e}" rounds to nearest, which can print a bound the data
# does not satisfy (4.6e-6 and 5.4e-6 both render as 5e-6, and only one is < 5e-6).
_e = int(np.floor(np.log10(pmax))); _m = int(np.ceil(pmax / 10.0 ** _e))
if _m == 10: _m, _e = 1, _e + 1
assert pmax < _m * 10.0 ** _e, "p-value bound must hold, not merely round to"
put("ScalePmax", f"{_m}\\times10^{{{_e}}}")

# ---------- campaign ----------
c = pd.read_parquet(f"{R}/campaign/full.parquet")
put("NRuns", f"{len(c):,}".replace(",", "{,}"))
put("NArms", f"{c.arm.nunique()}")
KEY=["channel","nsta","speed","seed"]
ours = c[c.arm=="Mono(w=0.25)"][KEY+["thr"]].rename(columns={"thr":"ours"})
fam = {"Minstrel": c[c.arm.str.startswith("MinstrelHt(")],
       "ORS": c[c.arm.str.contains("ORS|KL-R", regex=True)],
       "Thompson": c[c.arm.str.startswith("Thompson(")]}
for fname, fdf in fam.items():
    dom, worsts = 0, []
    for (ch,ns), _ in c.groupby(["channel","nsta"]):
        o = ours[(ours.channel==ch)&(ours.nsta==ns)]
        sub = fdf[(fdf.channel==ch)&(fdf.nsta==ns)]
        # worst over arms, PER SPEED -- the summary table's range spans (cell x speed)
        per_speed, sig, pv = {}, False, []
        for arm,a in sub.groupby("arm"):
            mm = o.merge(a[KEY+["thr"]], on=KEY)
            for sp,s2 in mm.groupby("speed"):
                rel = 100*(s2.ours.mean()/s2.thr.mean()-1)
                per_speed[sp] = min(per_speed.get(sp, 1e9), rel)
                pv.append((rel, stats.ttest_rel(s2.ours.values,s2.thr.values).pvalue))
        k=len(pv)
        for rank,(rel,pp) in enumerate(sorted(pv,key=lambda z:z[1])):
            if rel<0 and min(1.0,(k-rank)*pp)<0.05: sig=True
        if not sig: dom += 1
        worsts.extend(per_speed.values())
    put(f"Dom{fname}", f"{dom}/6")
    put(f"Lo{fname}", f"{min(worsts):+.1f}"); put(f"Hi{fname}", f"{max(worsts):+.0f}")
ncell = c.groupby(["channel", "nsta"]).ngroups
tot = sum(int(out[f"Dom{f}"].split('/')[0]) for f in fam)
putn("DomCells", len(fam) * ncell)
put("DomTotal", f"{tot}/{len(fam)*ncell}"); putn("DomFail", len(fam)*ncell - tot)
putn("SweepThompson", fam["Thompson"].arm.nunique())
putn("SweepMinstrel", fam["Minstrel"].arm.nunique())
putn("Speeds", c.speed.nunique()); putn("Contention", c.nsta.nunique())
putn("Channels", c.channel.nunique()); putn("Seeds", c.seed.nunique())
putn("HeldoutStas", 4)            # the slice tab:heldout reports; check_paper asserts it

fx = c[c.arm.str.startswith("Fixed(")].copy(); fx["mcs"]=fx.arm.str.extract(r"MCS(\d+)").astype(int)
gb = int(fx.groupby("mcs").thr.mean().idxmax())
dep = fx[fx.mcs==gb].rename(columns={"thr":"ref"})[KEY+["ref"]]
mm = ours.merge(dep, on=KEY)
rels = [100*(s.ours.mean()/s.ref.mean()-1) for _,s in mm.groupby(["channel","nsta","speed"])]
put("DeployMcs", f"{gb}"); put("DeployCells", f"{sum(r>0 for r in rels)}/{len(rels)}")
put("DeployLo", f"{min(rels):+.1f}"); put("DeployHi", f"{max(rels):+.1f}")

# ---------- decay-frontier compromise (pp short of the per-speed best) ----------
fr = pd.read_parquet(f"{R}/gate1/decay_frontier.parquet")
ii = fr[fr.raa=="Ideal"][["channel","speed","seed","throughput_mbps"]].groupby(
        ["channel","speed","seed"]).throughput_mbps.sum().rename("ideal").reset_index()
tt = fr[fr.raa=="ThompsonSampling"].groupby(
        ["channel","speed","seed","decay"]).throughput_mbps.sum().rename("thr").reset_index()
jj = tt.merge(ii, on=["channel","speed","seed"]); jj["pct"]=100*jj.thr/jj.ideal
piv = jj[jj.channel=="logdistance+jakes"].pivot_table(index="decay",columns="speed",values="pct")
put("DecayCompromisePp", f"{piv.max().mean() - piv.mean(axis=1).max():.1f}")

put("DeployN", f"{len(rels)}")

# ---------- how the forgetting-rate optimum moves with speed -------------------
# Sec. diag claims the optimum is LambdaRatio x higher at rest than at 20 m/s, and
# that per-cell tuning does not remove the conservative bias at rest. Both are read
# off the campaign slice the bias table uses (fading, 4 STAs), never hand-typed.
sl = c[(c.channel=="logdistance+jakes") & (c.nsta==4)].copy()
tl = sl[sl.arm.str.startswith("Thompson(")].copy()
tl["lam"] = tl.arm.str.extract(r"d=([\d.]+)").astype(float)
lam = tl.groupby(["speed","lam"]).thr.mean().unstack()
l_rest, l_fast = lam.loc[0.0].idxmax(), lam.loc[20.0].idxmax()
put("LambdaRest", f"{l_rest:g}"); put("LambdaFast", f"{l_fast:g}")
put("LambdaRatio", f"{l_rest/l_fast:g}")
# The bias table is run at ONE lambda, described as the best single value over the
# whole speed range. That is a different quantity from the 20 m/s optimum even where
# the two coincide, so compute it separately -- and check the run really used it,
# rather than trusting that a hand-set arm still matches what the data now says.
l_best = lam.div(lam.max(axis=1), axis=0).mean(axis=0).idxmax()   # best per-speed ratio
put("LambdaBest", f"{l_best:g}")
_bias_arms = set(b[b.arm.str.startswith("Thompson")].arm.unique())
assert _bias_arms == {f"Thompson(d={l_best})"}, (
    f"tab:bias caption prints lambda={l_best:g} but the run used {_bias_arms}")
# residual conservatism at rest once lambda is tuned for that cell specifically
gz = sl[(sl.arm=="Ideal") & (sl.speed==0)].set_index("seed").mean_mcs
tz = sl[(sl.arm==f"Thompson(d={l_rest})") & (sl.speed==0)].set_index("seed").mean_mcs
put("BiasRestOracleAbs", f"{abs((tz-gz).mean()):.2f}")

# ---------- unstructured KL-R-UCB vs structured ORS ----------
# Sec. VI-B called this "consistent". It is not: it reverses in one cell, by a wider
# margin than any cell in which it holds. Count the cells and quote the spread.
_of = c[c.arm.str.contains("ORS|KL-R", regex=True)]
_rel = []
for _, k in _of.groupby(["channel", "nsta"]):
    g2 = k.groupby("arm").thr.mean()
    _kl = max(v for i, v in g2.items() if "KL-R" in i)
    _or = max(v for i, v in g2.items() if "KL-R" not in i)
    _rel.append(100 * (_kl / _or - 1))
putn("KlWins", sum(r > 0 for r in _rel)); putn("KlCells", len(_rel))
put("KlHi", f"{max(_rel):+.1f}"); put("KlLo", f"{min(_rel):+.1f}")

# ---------- the equivalence grid, read from the script that runs it ----------
# Sec. IV and Sec. V-A both print this count; neither was tied to the checker, so a
# change to its grid would leave two sentences quietly overstating what was verified.
import ast as _ast
_tree = _ast.parse((_paths.RUNNER / "verify_equivalence.py").read_text())
_grid = next(_ast.literal_eval(n.value) for n in _ast.walk(_tree)
             if isinstance(n, _ast.Assign) and isinstance(n.targets[0], _ast.Tuple)
             and [e.id for e in n.targets[0].elts] == ["DECAYS", "SPEEDS", "SEEDS"])
put("EquivConfigs", str(len(_grid[0]) * len(_grid[1]) * len(_grid[2])))


# ---------- rate-table growth, 802.11a -> 802.11be ----------
put("TableGrowth", f"{int(out['StarveBigN'])//int(out['StarveSmallN'])}")

# ---------- worst Thompson-frontier loss (Pattern A) ----------
put("PatternALoss", f"{abs(float(out['LoThompson'])):.1f}")

# ---------- pattern B: is the resting-cell loss a fixed-lambda artefact? ----------
# Sec. VII claims a forgetful sampler recovers it. That was asserted from memory with
# no run behind it; these are the runs. Both failing cells, ours at several lambda,
# against the best Thompson the campaign found in the same cell.
PB_LAM = 50
pb = {d: pd.read_parquet(f"{R}/mono/monodecay_{d}.parquet") for d in (2, PB_LAM)}
lo, hi, flo, fhi = [], [], [], []
for ns in (4, 8):
    th = c[(c.channel == "logdistance+jakes") & (c.nsta == ns) & (c.speed == 0.0)
           & (c.arm.str.startswith("Thompson("))]
    ref = th.groupby("arm").thr.mean().max()
    base = pb[2][(pb[2].nsta == ns) & (pb[2].arm == "Mono(w=0.25)")].thr.mean()
    fixed = pb[PB_LAM][(pb[PB_LAM].nsta == ns) & (pb[PB_LAM].arm == "Mono(w=0.25)")].thr.mean()
    lo.append(100 * (base / ref - 1)); flo.append(100 * (fixed / ref - 1))
put("PatternBLo", f"{abs(max(lo)):.1f}"); put("PatternBHi", f"{abs(min(lo)):.1f}")
put("PatternBLambda", f"{PB_LAM}")
put("PatternBFixLo", f"{min(flo):+.1f}"); put("PatternBFixHi", f"{max(flo):+.1f}")

# ---------- crossovers ----------
th = pd.read_parquet(f"{R}/threshold/sweep.parquet")
tf = th[th.arm.str.startswith("Fixed(")]
orc = tf.sort_values("thr").groupby(["speed","seed"]).tail(1).rename(columns={"thr":"ref"})[["speed","seed","ref"]]
def cross(arm):
    a = th[th.arm==arm].groupby(["speed","seed"]).thr.sum().rename("ad").reset_index()
    j = a.merge(orc,on=["speed","seed"]).groupby("speed").mean(numeric_only=True)
    x,y = j.index.values, (j.ad/j.ref).values
    for i in range(len(x)-1):
        if y[i]>=1.0>y[i+1]:
            return x[i]+(1.0-y[i])/(y[i+1]-y[i])*(x[i+1]-x[i])
    return float("nan")
put("CrossOurs", f"{cross('Mono(w=0.25)'):.1f}")
put("CrossThompson", f"{cross('Thompson(d=2.0)'):.1f}")
put("CrossRatio", f"{cross('Mono(w=0.25)')/cross('Thompson(d=2.0)'):.1f}")
put("CrossOursRound", f"{cross('Mono(w=0.25)'):.0f}")

# ---------- adaptive-decay ablation ----------
ad = pd.read_parquet(f"{R}/adaptdecay/tune.parquet")
fixm = ad[ad.arm=="Mono(w=0.25)"][["speed","seed","thr"]].rename(columns={"thr":"fixed"})
best, bestmean = None, -1e9
for arm in [a for a in ad.arm.unique() if a.startswith("Mono+Adapt")]:
    mm = ad[ad.arm==arm].groupby("speed").thr.mean()
    if mm.mean() > bestmean: best, bestmean = arm, mm.mean()
aa = ad[ad.arm==best][["speed","seed","thr"]].rename(columns={"thr":"adapt"})
j = fixm.merge(aa, on=["speed","seed"])
net = 100*(j.adapt.mean()/j.fixed.mean() - 1)
z = j[j.speed==0]
put("AdaptNet",  f"{net:+.1f}")
put("AdaptRest", f"{100*(z.adapt.mean()/z.fixed.mean()-1):+.1f}")
mv = j[j.speed>0]
lo = min(100*(g.adapt.mean()/g.fixed.mean()-1) for _,g in mv.groupby("speed"))
hi = max(100*(g.adapt.mean()/g.fixed.mean()-1) for _,g in mv.groupby("speed"))
put("AdaptMoveLo", f"{abs(hi):.0f}"); put("AdaptMoveHi", f"{abs(lo):.0f}")

with open(_paths.OUT / "numbers.tex","w") as f:
    for k,v in sorted(out.items()):
        f.write("\\newcommand{\\Num%s}{%s}\n" % (k, v))
print(f"wrote numbers.tex with {len(out)} macros")
for k,v in sorted(out.items()): print(f"   \\Num{k:16s} = {v}")
