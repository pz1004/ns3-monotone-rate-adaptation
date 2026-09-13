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

def _texp(v, plain=0.01):
    """p-value as LaTeX: plain decimal above `plain`, else a x 10^{-b} with no zero pad."""
    if v >= plain:
        return f"{v:.2f}"
    m, e = f"{v:.0e}".split("e")
    return rf"{m}\times10^{{{int(e)}}}"

# ---------- starvation (Day-3 manager sweep) ----------
d = pd.read_parquet(f"{R}/day3_validation/mgr_sweep.parquet")
o = d[d.series == "observed"].copy()
# MCS count per spatial stream, per amendment. EHT defines MCS 0-13 (ns-3's EhtPhy
# registers 14), not 12: 802.11be adds the two 4096-QAM rates on top of HE's twelve.
# This was 12 and understated the 802.11be table by a sixth (protocol-v1 A9.1).
nmcs = {"802.11n-5GHz": 8, "802.11ac": 10, "802.11ax-5GHz": 12, "802.11be-5GHz": 14}
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
# Table size is confounded with the amendment -- 802.11be's two extra MCS are 4096-QAM and
# rarely usable at range -- so the pooled r alone does not establish that SIZE is what
# hurts. Sec. III says "because of that scale", so report the weakest WITHIN-amendment
# correlation and the partial correlation holding the per-stream MCS count fixed. Both
# must survive for that wording to stand (protocol-v1 amendment A9.12).
put("StarveConfigs", f"{len(t)}")
_wi = {s_: np.corrcoef(g.n_rates, g.pct)[0, 1] for s_, g in t.groupby("standard") if len(g) > 2}
put("StarveCorrWithin", f"{max(_wi.values()):.2f}")      # weakest, i.e. closest to zero
def _partial(x, y, z):
    rx = x - np.polyval(np.polyfit(z, x, 1), z)
    ry = y - np.polyval(np.polyfit(z, y, 1), z)
    return np.corrcoef(rx, ry)[0, 1]
put("StarvePartial", f"{_partial(t.n_rates.to_numpy(float), t.pct.to_numpy(float), t.standard.map(nmcs).to_numpy(float)):.2f}")

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
# Report the paired difference itself with an interval. On the matched action set this
# is no longer a null result -- it favours the method -- so bounding it without stating
# its sign would now understate what was measured.
_lo, _hi = stats.t.interval(0.95, len(_d) - 1, _d.mean(), stats.sem(_d))
put("JainVsThompson",   f"{_d.mean():+.3f}")
put("JainVsThompsonLo", f"{_lo:+.3f}")
put("JainVsThompsonHi", f"{_hi:+.3f}")
put("JainCIThompson", f"{1.96 * _d.sem():.3f}")
_pv = stats.ttest_rel(_p.loc[_d.index], _t.loc[_d.index]).pvalue
put("JainPThompson", _texp(_pv))
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
# tx_per_MB counts EVERY MPDU the PHY sends, first transmissions included, so it is not a
# retry count (protocol-v1 amendment A9.2). A 1400 B payload implies a floor of
# 1e6/1400 = 714.3 MPDU per delivered MB even with zero retries; the excess over that
# floor is the retry-attributable part, and it behaves very differently.
PAYLOAD_B = 1400.0
FLOOR = 1e6 / PAYLOAD_B
# Report the excess in ABSOLUTE MPDU/MB, not as a ratio. At rest the genie sits almost
# exactly on the floor (about 9 MPDU/MB above it), so a ratio there has a near-zero
# denominator and reads as several hundred percent for a small absolute difference.
m["exc_i"] = m.i_tx - FLOOR
m["exc_t"] = m.tx_per_MB - FLOOR
# Aggressiveness in MCS index alone is ambiguous once width and streams vary; report the
# selected PHY rate too when the runner supplied it (A9.3).
_has_rate = {"mean_phyrate"}.issubset(b.columns)
if _has_rate:
    idl2 = b[b.arm=="Ideal"][["speed","seed","mean_phyrate","mean_width","mean_nss"]].rename(
        columns={"mean_phyrate":"i_rate","mean_width":"i_w","mean_nss":"i_n"})
    m = m.merge(idl2, on=["speed","seed"], how="left").merge(
        b[b.arm.str.startswith("Thompson")][["speed","seed","mean_phyrate","mean_width","mean_nss"]],
        on=["speed","seed"], how="left")
    m["ratedev"] = 100*(m.mean_phyrate/m.i_rate - 1)
for sp in sorted(m.speed.unique()):
    s = m[m.speed==sp]
    tag = "V" + str(int(sp))
    put(f"Bias{tag}",   f"{s.bias.mean():+.2f}")
    put(f"BiasCI{tag}", f"{1.96*s.bias.std(ddof=1)/np.sqrt(len(s)):.2f}")
    put(f"TxOh{tag}",   f"{s.txoh.mean():+.1f}")
    put(f"ExcGenie{tag}", f"{s.exc_i.mean():.0f}")
    put(f"ExcThom{tag}",  f"{s.exc_t.mean():.0f}")
    if _has_rate:
        put(f"RateDev{tag}", f"{s.ratedev.mean():+.1f}")
        # Sec. III claims the two stop choosing the same SHAPE of configuration under
        # motion; tie that sentence to the marginals rather than asserting it.
        put(f"GenieW{tag}", f"{s.i_w.mean():.0f}");  put(f"GenieNss{tag}", f"{s.i_n.mean():.2f}")
        put(f"ThomW{tag}",  f"{s.mean_width.mean():.0f}")
        put(f"ThomNss{tag}", f"{s.mean_nss.mean():.2f}")
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

# MCS per spatial stream, read from the released action-set dump so it tracks the
# amendment actually simulated (EHT defines 14, HE 12) instead of being pinned.
_MCS_PER_SS = int(pd.read_csv(_paths.RESULTS / "exactness/armset_latest.csv").mcs.nunique())

def order_scaling(arm, mcs_per_ss=_MCS_PER_SS):
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

# THE contrast the paper's claim is actually about. Testing each ordering against
# Thompson separately is not the same as testing them against each other, and the
# campaign never reported the latter. Paired at matched (speed, seed, width, nss).
def order_paired(arm_a, arm_b):
    j = (om[om.arm == arm_a].set_index(KEYW).thr
         .to_frame("a").join(om[om.arm == arm_b].set_index(KEYW).thr.to_frame("b"),
                             how="inner").dropna())
    d = 100 * (j.a / j.b - 1)
    n = len(d)
    lo, hi = stats.t.interval(0.95, n - 1, d.mean(), stats.sem(d))
    return dict(pct=d.mean(), lo=lo, hi=hi, n=n, wins=int((j.a > j.b).sum()),
                p=stats.ttest_rel(j.a, j.b).pvalue,
                pw=stats.wilcoxon(j.a, j.b).pvalue)

_pr = order_paired(ARM_SNR, ARM_RATE)
put("OrderPairedPct",  f"{_pr['pct']:+.1f}")
put("OrderPairedLo",   f"{_pr['lo']:+.1f}")
put("OrderPairedHi",   f"{_pr['hi']:+.1f}")
putn("OrderPairedN",    _pr["n"])
putn("OrderPairedWins", _pr["wins"])
put("OrderPairedP",    _texp(_pr["p"]))

# The aggregation rule is not neutral: ratio-of-means and mean-of-ratios differ by ~5 pp
# on this grid, and the paper never said which it used. State it, and print both.
def _mean_of_ratios(arm):
    j = (om[om.arm == arm].set_index(KEYW).thr.to_frame("a")
         .join(om[om.arm == OM_REF].set_index(KEYW).thr.to_frame("t"), how="inner").dropna())
    return 100 * (j.a / j.t - 1).mean()
put("GainReqSnrMoR",   f"{_mean_of_ratios(ARM_SNR):+.1f}")
put("GainDataRateMoR", f"{_mean_of_ratios(ARM_RATE):+.1f}")

# The bandwidth/stream-normalised ordering. ns-3's own genie compares a candidate's
# threshold against an observed SNR divided by (width/widthObs) and (nss/nssObs), so the
# key that is monotone in required RECEIVE power is threshold x width x nss, not the raw
# threshold this method sorts on. Running it as a third arm settles whether the result
# depends on the SNR reference convention (protocol-v1 amendment A9.5).
ARM_PWR = "Mono/RequiredSnrPower(w=0.25)"
if (om.arm == ARM_PWR).any():
    g_pwr, _ = order_gain(ARM_PWR)
    put("GainPowerOrder", f"{g_pwr:+.1f}")
    _pw = order_paired(ARM_PWR, ARM_SNR)
    put("PowerVsSnrPct", f"{_pw['pct']:+.2f}")
    put("PowerVsSnrLo",  f"{_pw['lo']:+.2f}")
    put("PowerVsSnrHi",  f"{_pw['hi']:+.2f}")
    put("PowerVsSnrP",   f"{_pw['p']:.2f}")
    putn("PowerVsSnrWins", _pw["wins"])
    c_pwr, _ = order_scaling(ARM_PWR)
    put("CorrPowerOrder", f"{c_pwr:+.2f}")

# ---------- the evaluated controller, stated rather than left to be reconstructed ------
# Sec. V never named the campaign configuration; a reader could not identify the system
# being reported (protocol-v1 amendment A9.6).
_camp = pd.read_parquet(f"{R}/campaign/full.parquet")
_mono = _camp[_camp.arm == "Mono(w=0.25)"]
assert _mono.w.nunique() == 1 and _mono.decay.nunique() == 1, "campaign arm is not unique"
put("CampW", f"{_mono.w.iloc[0]:g}")
put("CampLambda", f"{_mono.decay.iloc[0]:g}")

# ---------- the action set, read from the released enumeration dump --------------------
_arms = pd.read_csv(_paths.RESULTS / "exactness/armset_latest.csv")
putn("ArmsTotal", len(_arms))
putn("ArmsMcs", _arms.mcs.nunique())
putn("ArmsMcsMax", int(_arms.mcs.max()))
putn("ArmsWidths", _arms.width.nunique())
putn("ArmsNss", _arms.nss.nunique())
put("ArmsFamily", str(_arms["mode"].iloc[0])[:3].upper())
_up = pd.read_csv(_paths.RESULTS / "exactness/armset_matchupstream.csv")
# IdealWifiManager does NOT enumerate widths: DoGetDataTxVector fixes channelWidth to
# min(negotiated, allowedWidth) before the search and then loops over modes and streams
# only. Its candidate set is therefore the distinct (mcs, nss) pairs at one width, not the
# full table, and its selected width never narrows (protocol-v1 amendment A9.14).
put("GenieArms", f"{_arms.groupby(['mcs','nss']).ngroups}")
put("GenieWMin", f"{_camp[_camp.arm=='Ideal'].mean_width.min():.1f}")
putn("ArmsUpstream", len(_up))

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
# Sec. III has to answer whether the sign reversal is an artefact of running at ONE
# lambda. It is not -- but the check this replaces took abs() of the per-cell-tuned
# resting bias and the prose then called it "below the genie", when it is ABOVE
# (protocol-v1 amendment A9.11). Sweep lambda instead and report where the reversal holds.
_gen = sl[sl.arm == "Ideal"].groupby(["speed", "seed"]).mean_mcs.mean().rename("g")
_bj = tl.merge(_gen, on=["speed", "seed"])
_bj["bias"] = _bj.mean_mcs - _bj.g
_bp = _bj.pivot_table(index="lam", columns="speed", values="bias")
_rev = [l for l in _bp.index if _bp.loc[l, 0.0] < 0 < _bp.loc[l, 20.0]]
assert min(_rev) == _bp.index.min(), "reversal must hold at the slowest swept lambda"
put("BiasRevLamHi", f"{max(_rev):g}")
_null = min(l for l in _bp.index if _bp.loc[l, 0.0] >= 0)
put("BiasNullLam",  f"{_null:g}")
put("BiasNullRest", f"{_bp.loc[_null, 0.0]:+.2f}")
put("BiasNullFast", f"{_bp.loc[_null, 20.0]:+.2f}")
# The two ends are not equally reachable: no swept lambda nulls the error under motion.
_lff = _bp[20.0].idxmin()
_ff  = _bj[(_bj.speed == 20.0) & (_bj.lam == _lff)].bias
put("BiasFastFloor",   f"{_bp.loc[_lff, 20.0]:+.2f}")
put("BiasFastFloorCI", f"{1.96*_ff.std(ddof=1)/np.sqrt(len(_ff)):.2f}")

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
# The crossover is an interpolation between TESTED speeds, and the bracket matters: it
# is not a measured boundary (protocol-v1 amendment A9.7). Emit the bracket so the paper
# can state it rather than implying a resolution the sweep does not have.
def cross_bracket(arm):
    a = th[th.arm == arm].groupby(["speed", "seed"]).thr.sum().rename("ad").reset_index()
    j = a.merge(orc, on=["speed", "seed"]).groupby("speed").mean(numeric_only=True)
    x, y = j.index.values, (j.ad / j.ref).values
    for i in range(len(x) - 1):
        if y[i] >= 1.0 > y[i + 1]:
            return x[i], x[i + 1], y[i], y[i + 1]
    return (float("nan"),) * 4

def cross(arm):
    a = th[th.arm==arm].groupby(["speed","seed"]).thr.sum().rename("ad").reset_index()
    j = a.merge(orc,on=["speed","seed"]).groupby("speed").mean(numeric_only=True)
    x,y = j.index.values, (j.ad/j.ref).values
    for i in range(len(x)-1):
        if y[i]>=1.0>y[i+1]:
            return x[i]+(1.0-y[i])/(y[i+1]-y[i])*(x[i+1]-x[i])
    return float("nan")
put("CrossOurs", f"{cross('Mono(w=0.25)'):.1f}")
_lo, _hi, _ylo, _yhi = cross_bracket("Mono(w=0.25)")
put("CrossOursLo", f"{_lo:g}"); put("CrossOursHi", f"{_hi:g}")
put("CrossOursRatioLo", f"{_ylo:.3f}"); put("CrossOursRatioHi", f"{_yhi:.3f}")
_tlo, _thi, _, _ = cross_bracket("Thompson(d=2.0)")
put("CrossThompsonLo", f"{_tlo:g}"); put("CrossThompsonHi", f"{_thi:g}")
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
# The two aggregations disagree in SIGN on this ablation -- the grand-mean ratio is
# dominated by the high-throughput resting cell while per-run ratios weight cells
# equally -- and a paired test detects no difference at all. Quoting one net number
# would make a conclusion out of an aggregation choice, so emit the test as well.
put("AdaptNetMoR", f"{(100*(j.adapt/j.fixed - 1)).mean():+.1f}")
put("AdaptP", f"{stats.ttest_rel(j.adapt, j.fixed).pvalue:.2f}")
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
