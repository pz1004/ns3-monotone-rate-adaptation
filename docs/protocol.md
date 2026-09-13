# protocol.md — pre-registered evaluation protocol (FROZEN)

**Frozen 2026-09-08, before any tuning of the proposed method.**
Tagged `protocol-v1`. Cite this tag in the manuscript.

The point of freezing this is to convert "we tuned until we won" into "we pre-committed to
a measurement and report what it returned." Anything changed after this tag must be
recorded in a dated amendment section at the bottom, not edited in silently.

## 1. Claim under test
**H-main.** A calibrated-quantile rate-selection rule Pareto-dominates the entire swept
fixed-`Decay` ThompsonSampling frontier on (throughput, frame-error rate) across the
mobility range 0–20 m/s, **without being told the mobility condition**.

**H-mech.** The gain comes from removing the sign-flipping selection bias documented in
`docs/diagnostic_verdict.md`: mean-MCS bias vs the genie should move toward zero at *both*
ends (−2.32 at 0 m/s and +1.75 at 20 m/s), and retry overhead should fall at speed.

**Refutation conditions, stated in advance.** H-main is refuted if the proposed rule fails
to dominate the fixed-`Decay` frontier in the majority of (speed × channel) cells with
non-overlapping 95% CIs. H-mech is refuted if throughput improves without the bias moving,
or the bias moves without throughput following — either would mean the mechanism story is
wrong even if the numbers look good, and that must be reported.

## 2. Fixed factors
- ns-3.48, `contrib/cqra`, optimized build. Commit recorded in `env/env.lock`.
- 802.11be, 5 GHz, 80 MHz, 2 spatial streams, GI 800 ns, single link (no MLO/OFDMA).
- 1 AP, saturated downlink UDP, 1400 B payload, 600 Mb/s offered per STA.
- Channels: `logdistance` and `logdistance+jakes` (Doppler `f_d = v·f_c/c`, floored at
  1 Hz; `f_c` = 5.25 GHz).

## 3. Swept factors
- STA speed ∈ {0, 1, 2, 5, 10, 20} m/s.
- Contention ∈ {1, 4, 8} STAs.
- Baseline family: `ThompsonSampling` × `Decay` ∈ {0, 0.5, 1, 2, 5, 10, 20, 50, 100} Hz.
- Reference points: `IdealWifiManager` (genie), `MinstrelHt` at defaults and with
  `SampleColumn`/`UpdateStatistics` swept, best-fixed-rate envelope from `ConstantRate`.

## 4. Seeds and statistics
- **≥10 seeds** per cell (≥5 only under the descope ladder), `RngRun` = seed.
- Report **mean ± 95% CI**; dominance claims require **non-overlapping CIs**.
- Paired comparisons across policies at matched (speed, channel, seed); Holm correction
  across the speed family.
- ns-3 is deterministic given `RngRun`; single-run curves are not acceptable.

## 5. Generalisation splits — never IID-only
- **S1** IID within condition — the optimistic split everyone reports. Included only to
  quantify how optimistic it is.
- **S2** held-out **speeds**: tune on {0, 2, 10}, evaluate on {1, 5, 20}.
- **S3** held-out **contention**: tune at 4 STAs, evaluate at 1 and 8.
- **S4** held-out **channel**: tune on `logdistance`, evaluate on `logdistance+jakes`.
The headline claim is made on S2–S4, not S1.

## 6. Metrics
Primary: aggregate delivered throughput as % of the `IdealWifiManager` genie.
Secondary, all pre-committed: mean-MCS bias vs genie; extra PHY transmissions per
delivered MB; realised frame-error rate vs the target; per-STA Jain fairness; and the
policy's own decision cost (it is a scalar recursion, so this is reported as negligible
rather than assumed).

## 7. Honesty guards
- Report the realised FER against the target even where it misses.
- Report the **whole** fixed-`Decay` frontier, not its worst point.
- Report GPU **and** CPU hours.
- All reimplemented comparators labelled as ours.
- Do **not** report a "better-performing subset" of seeds.
- `IdealWifiManager` is a **genie, not an upper bound** — it exceeds the best-fixed-rate
  envelope. Say so wherever it is used as the normaliser.

## 8. Known limitations to state in the paper
- Single-link EHT only; no MLO, no OFDMA/MU.
- Jakes is a flat-fading model; real 80 MHz fading is frequency-selective. The 3GPP
  *spectrum* fading model cannot attach to `SpectrumWifiPhy` in ns-3.48 (it requires
  `PhasedArrayModel`, only `AntennaModel` is exposed).
- The 1 Hz Doppler floor means "static" is not perfectly static.
- Beta quantiles use a moment-matched normal approximation, not the exact inverse
  incomplete beta.

## Amendments
*Do not edit the text above.* Each entry below records a change made after the
`protocol-v1` freeze (2026-09-08 14:05), dated by when the change was made. Recorded
2026-09-10, before submission.

**What held unchanged.** §2 (fixed factors) and §3 (swept factors, except the reference
set — see A6) were followed exactly: ns-3.48, 802.11be at 80 MHz / 2 spatial streams /
GI 800 ns, 1 AP with saturated downlink UDP at 1400 B and 600 Mb/s offered per STA, both
channels, speeds {0, 1, 2, 5, 10, 20} m/s, contention {1, 4, 8} STAs, and the baseline
family `ThompsonSampling` × `Decay` ∈ {0, 0.5, 1, 2, 5, 10, 20, 50, 100} Hz. §5's splits
were followed after the violation in A3 was corrected. The equivalence gate still passes:
with propagation disabled the implementation is byte-identical to
`ns3::ThompsonSamplingWifiManager` across all 27 configurations.

---

### A1 — 2026-09-08 17:12 — H-main: the rule was refuted and replaced, and the claim narrowed to throughput

**The calibrated-quantile rule named in §1 was refuted under §1's own H-main refutation
condition, and is withdrawn.** That condition is failure "to dominate the fixed-`Decay`
frontier in the majority of (speed × channel) cells". Measured against the oracle-tuned
baseline (`Decay`=2) under fading with 4 STAs, 5 seeds, the corrected rule did not merely
fail to dominate: it ran 3.0–5.2 pp *below* the baseline at every speed from 0 to 20 m/s.

Note what did **not** happen. §1's H-mech conditions are "throughput improves without the
bias moving, or the bias moves without throughput following". Neither fired: throughput
did not improve and the bias did not move. H-mech was therefore not refuted on its own
terms; it was left with nothing to explain, and is withdrawn with the rule it described
(A2).

The cause is structural, not a tuning failure, and it determined everything after it:
**self-calibration on the arm actually played cannot correct a selection error across
arms.** Thompson's posterior is already approximately calibrated on the arms it plays, so
the calibration error is near zero and the quantile level has no gradient. But the bias
against the genie is an *off-policy* quantity — the genie would have played a *different*
arm — and no signal derived only from the played arm can observe it.

**Replacement.** H-main is now tested for *monotone evidence propagation ordered by
required SNR*: each outcome is shared along the rate order, a failure at rate *r* adding
`w × nFail` to every rate needing more SNR and a success adding `w × nSucc` to every rate
needing less, with the target discounted before the addition so inferred evidence ages on
the same schedule as observed evidence. The order comes from `WifiPhy::CalculateSnr` at
the `BerThreshold` attribute, whose default of 1e-6 matches `IdealWifiManager`, so the
ordering is derived the same way the genie derives its own rate thresholds.

**What did not change.** The dominance structure is exactly as frozen, and is what the
paper reports against: one fixed configuration, not told the mobility condition, against
the *entire* swept fixed-`Decay` frontier rather than one tuned point, with §4's ten
seeds, paired tests and Holm correction. The refutation condition and the statistics are
untouched. This is the part of the pre-registration that still constrains the result.

One detail a reader should not have to reconstruct from the data: the configuration
(w = 0.25) was selected on the tuning speeds alone (A3), but the dominance claim is then
evaluated across the **full** swept range — all six speeds, tuning speeds included — not
on the held-out three. The held-out-only comparison is a separate, narrower table. That is
not a split violation, since nothing was selected on held-out data, but §5 says the
headline claim is made on S2–S4, and the breadth of the campaign is wider than that split
rather than confined to it.

**What did change, beyond the rule itself.** Frozen H-main is a *Pareto* claim on
**(throughput, frame-error rate)**. The paper's claim is on throughput alone: it makes no
frame-error-rate claim anywhere. The FER axis went out with the absolute FER target that
the calibrated-quantile rule needed and the replacement does not (see A7). The delivered
claim is therefore **narrower than pre-registered** on that axis — dominance on one metric
where two were promised — and a reader comparing the two should read it that way.

**A weakening a reader should weigh.** The refutation above was measured across speeds
{0, 2, 5, 10, 20}, which includes the held-out speeds 5 and 20, and at 5 seeds rather than
§4's ten. Because the outcome was abandonment rather than selection, no configuration was
chosen on held-out data — but the decision to change direction was informed by it. Every
selection made after this point used the tuning split alone (A3).

### A2 — 2026-09-08 18:55 — H-mech withdrawn and replaced; the replacement is not pre-registered

H-mech as frozen predicted that mean-MCS bias would move toward zero at *both* ends and
that retry overhead would fall at speed. It was specific to the calibration formulation
and is withdrawn with it (A1).

The mechanism claim that replaced it is that the propagation must be **physically
grounded**: monotonicity of success probability holds in *required SNR*, not in achievable
data rate. Once width and spatial streams vary, those two orders diverge — a
high-MCS/20 MHz rate and a low-MCS/80 MHz rate can carry similar bit rates while differing
by many dB in sensitivity — so ordering by data rate injects false evidence, and more of
it as the table grows. It is tested by a matched ablation in which the ordering function is
the only thing that differs: data rate gives +0.3% (p = 0.70) with the benefit shrinking
as the table grows (r = −0.59), required SNR gives +16.8% with the benefit growing
(r = +0.76).

**This replacement was formulated after the data-rate ordering was measured.** The
sequence is on the record: propagation ordered by data rate was measured first, its
benefit was found to *shrink* as the rate table grew, and the diagnosis that monotonicity
holds in required SNR rather than data rate was written down as the fix for that result.
It is therefore an explanatory hypothesis confirmed by a designed negative control, not a
pre-committed prediction, and should be read that way.

Two dates are involved and the heading carries only the first. The mechanism was replaced
on 2026-09-08; the *matched* ablation quoted above — which holds weight, speeds, seeds,
widths and streams fixed and varies only the ordering function — was run on 2026-09-09,
and its figures supersede the earlier unmatched ones. The numbers here are the matched
ones, the same the paper reports. The diagnostic that motivated the original
H-mech is retained and reported; its data is released as `results/diag/bias10.parquet`.

### A3 — 2026-09-08 17:59 — S2 violation in the first weight sweep: caught, discarded, redone

The first `StructureWeight` sweep (w ∈ {0.02 … 0.5}) was run on speeds {5, 20}, which §5
reserves for evaluation. **That was a protocol violation.** It was caught, its results were
discarded, and the selection was redone on the tuning speeds {0, 2, 10} only.

Every selection after that point used the tuning split alone, including the one carried
into the paper: `results/mono/tune_snr.parquet` sweeps w ∈ {0.02, 0.05, 0.1, 0.25, 0.5} at
speeds {0, 2, 10} with 10 seeds, and `results/mono/heldout_snr.parquet` then evaluates the
single selected configuration (w = 0.25) at the held-out speeds {1, 5, 20}. Both files are
released, so the split discipline can be checked rather than taken on trust.

### A4 — 2026-09-10 — Two inputs fell below §4's seed floor; both were re-run at 10 seeds

§4 requires **≥10 seeds** per cell, "≥5 only under the descope ladder" — a term this
protocol never defines, which is a defect in the frozen text and is left uncorrected here
because the text above is frozen. Two inputs were found below the floor during the
pre-submission audit:

- `results/day3_validation/mgr_sweep.parquet` — **2 seeds**, below the floor outright, and
  §4 also says "single-run curves are not acceptable". It supplies the motivating
  measurement in the introduction.
- `results/gate1/decay_frontier.parquet` — **5 seeds**, at the stated floor but only under
  the undefined condition. It supplies one reported quantity: how far the best single
  forgetting rate falls short of the per-speed best.

**Both were re-run at 10 seeds on 2026-09-10** with grids otherwise unchanged, and every
reported number now derives from 10 seeds. The four affected quantities moved as follows:

| quantity | before | after |
|---|---|---|
| Minstrel-HT, % of genie at 8 rates | 99.6 | 99.5 |
| Minstrel-HT, % of genie at 72 rates | 47.1 | **55.1** |
| corr(table size, % of genie) | −0.68 | **−0.79** |
| forgetting-rate compromise (pp) | 1.7 | 1.6 |

The correlation that carries the argument **strengthened** (−0.68 → −0.79) while the most
extreme single figure became less extreme (47.1% → 55.1%): the 2-seed estimate had been an
optimistic draw in the direction that flattered the claim. Both are reported, and the
direction of the finding is unchanged.

Two notes on the re-run. The manager sweep attempts 720 runs and completes 660: 802.11n at
80 MHz is rejected by `wifi-manager-example` as an invalid width, excluding 6
configurations. The original 2-seed sweep excluded exactly the same 6, so the before/after
comparison above is like-for-like. And the decay frontier is 1440 runs, 0 failures. Both
are covered by `reproduce.sh` and corroborated by `logs/`.

### A5 — 2026-09-08 21:53 — Primary metric changed to absolute throughput

§6 makes the primary metric "aggregate delivered throughput as % of the
`IdealWifiManager` genie". `IdealWifiManager` turned out not to be an upper bound — the
proposed method exceeds it — which §7 anticipated as a caveat but §6 did not accommodate
as a metric. A ratio against a reference that can be beaten is not a sound headline
quantity.

**The primary metric is now absolute delivered throughput (Mb/s)**; genie-relative figures
are retained as diagnostics only.

The static references need care, because §3 already pre-registered one — "best-fixed-rate
envelope from `ConstantRate`" — and the paper reports three things derived from that
sweep: the **per-interval envelope** (a genie re-choosing the rate every 0.5 s), the
**best fixed rate per condition** chosen in hindsight, and a **single deployment-wide
MCS**. The first two are within §3's wording. The third is not: a rate held fixed across
every condition is a different reference from the best rate for each, and it was added
after the freeze. All three are derived by `analysis/make_references.py` and
`make_percell.py` from `results/envelope/` and the campaign.

That addition is not cosmetic, and it cuts both ways. Measured against the *oracle* static
rate the method loses at 20 m/s, as does every adaptive scheme tested, and that loss is
reported. Measured against the deployment-wide MCS — the reference a real deployment
actually faces, since no one gets to pick the best rate per condition in advance —
adaptation wins at every speed, and the method extends the crossover from 3.5 to
12.4 m/s. A reference that produces a headline loss and a headline win in the same table
is exactly the kind of post-freeze addition that has to be recorded rather than left
implicit.

### A6 — 2026-09-08 19:44 — Reference set extended with the ORS family

§3 lists `IdealWifiManager`, `MinstrelHt` (defaults and swept) and the best-fixed-rate
envelope. ORS, SW-ORS and KL-R-UCB (Combes, Proutiere, Yun, Ok & Yi, INFOCOM 2014) were
added after the freeze: they are the other rate-adaptation family that exploits structure
across rates, and therefore the comparison that isolates what the required-SNR ordering
contributes.

They are our reimplementation from the paper's pseudocode, labelled as ours per §7. Window
and ordering were swept on the tuning split and the best member of each family carried
into the campaign. See `docs/ors_baseline.md`.

### A7 — 2026-09-11 — The five pre-committed secondary metrics: two in the paper, two measured late, one moot

§6 pre-commits five secondary metrics. Two are reported in the paper, both in Table I:
mean-MCS bias against the genie, and extra PHY transmissions per delivered MB. The other
three were all missing when the pre-submission audit began:

- **Realised frame-error rate against the target** — no longer defined. The absolute FER
  target was removed with the calibrated-quantile rule (A1), so there is no target to miss,
  and §7's guard requiring it to be reported is moot for the same reason.
- **Per-STA Jain fairness** — **measured** 2026-09-11. See below.
- **The policy's own decision cost** — **measured and resolved** 2026-09-11. See below.

The first is moot. The second and third are now discharged; both were outstanding until
the pre-submission audit and both required instrumenting the simulation, so each records
below what was added and how it was shown not to disturb the released results.

#### Per-STA Jain fairness: measured

This went unreported because the data to compute it did not exist: the scenario logged
per-interval *aggregate* throughput, with no per-station breakdown. The scenario now
accepts `--perStaOut`, which records each sink's per-interval delta. That is pure
observation — `Sample()` already called `GetTotalRx()` on every sink to build the
aggregate, so recording the per-sink values adds no simulator interaction. Checked, not
assumed: the per-STA deltas sum to the aggregate delta exactly, in every interval of every
run.

Jain's index over per-STA delivered bytes, `J = (Σx)² / (n·Σx²)`, on the held-out speeds
{1, 5, 20} m/s, both channels, 10 seeds — 360 runs, 0 failures:

| arm | 4 STAs | 8 STAs |
|---|---|---|
| Minstrel-HT | 0.902 ± 0.038 | 0.781 ± 0.057 |
| Thompson (tuned) | 0.959 ± 0.022 | 0.933 ± 0.025 |
| **proposed** | **0.961 ± 0.021** | **0.930 ± 0.026** |

**The method does not trade fairness for throughput.** Paired at matched
(contention, channel, speed, seed), it is indistinguishable from the Thompson baseline it
is built on: mean difference −0.0002, 95% CI [−0.0071, +0.0068], p = 0.96, n = 120. It is
substantially fairer than Minstrel-HT: +0.105, p = 5×10⁻¹¹.

**Reported honestly: 70 of the 360 runs starve a station completely**, and that is worth
stating rather than hiding behind a healthy mean. They are concentrated almost entirely at
20 m/s — the single exception is Minstrel-HT at 8 STAs and 5 m/s. The proposed method has
the fewest (17, against 24 for Thompson and 29 for Minstrel-HT), but it does not eliminate
them. Fairness for the proposed method by speed:

| STAs | 1 m/s | 5 m/s | 20 m/s |
|---|---|---|---|
| 4 | 0.999 | 0.990 | 0.895 |
| 8 | 0.996 | 0.983 | 0.812 |

This is the same boundary the paper already reports from the throughput side: at 20 m/s
adaptation is losing to a static rate chosen in hindsight, and here it is also failing to
keep every station served. The two findings are the same phenomenon seen through different
metrics, and neither is specific to this method.

Reproduce with `runner/measure_fairness.py`; per-run indices are released as
`results/fairness/jain.parquet`.

#### Decision cost: resolved by direct instrumentation

§6 expects this cost to be negligible because the policy "is a scalar recursion". That
described the withdrawn calibrated-quantile rule, whose quantile update is a single scalar
step. The replacement is not: `PropagateMonotone` walks the entire rate order on every
outcome, so the cost is linear in rate-table size — the very quantity this paper argues is
growing.

**First attempt, which failed.** Propagation returns immediately at `StructureWeight` ≤ 0,
so the loop can be switched on and off without changing behaviour: `w = 0` against
`w = 1e-12`, which runs the full loop but adds evidence too small to alter a decision. The
isolation held exactly — throughput differed by 0.000% at every configuration — but the
cost did not resolve. Over 20 paired seeds every 95% CI straddled zero and two of four
point estimates were negative: the loop is far below what end-to-end simulation timing can
distinguish. It yielded only a bound, < 6.6 µs per decision at 72 rates.

**Resolved by instrumenting the manager.** A `CostLog` attribute, empty by default, times
the propagation with `steady_clock` and reports accumulated nanoseconds, call count,
summed rate-table size, and the cost of an empty clock read-pair measured in the same
binary — so the constant bias every timed call carries is subtracted rather than assumed
away. Measured over 5 seeds per configuration, 127,727 propagation calls in total:

| rates | calls | ns per decision | decisions/s of airtime | CPU |
|---|---|---|---|---|
| 12 | 17,635 | 430 | 353 | 0.015% |
| 24 | 22,308 | 716 | 446 | 0.032% |
| 36 | 34,933 | 825 | 699 | 0.058% |
| 72 | 52,851 | **1,345** | 1,057 | **0.142%** |

The linear structure is confirmed rather than assumed: cost regresses on rate-table size
at **14.6 ns per rate plus 302 ns fixed** (r = +0.993, p = 0.0074). The per-rate figure is
larger than a bare floating-point update because each propagated rate calls `Decay()`,
which evaluates `exp()`.

**The answer §6 asked for.** At the paper's headline configuration — 80 MHz, two streams,
72 rates — the policy costs **1.34 µs per decision** and decides once every 946 µs of
airtime, so it consumes **0.14% of one core**. That is negligible, now by measurement
rather than by an argument that no longer applied. It is also 4.9x tighter than the bound
the wall-clock experiment could reach.

**Instrumentation is behaviour-neutral, and this was verified, not asserted.** With
`CostLog` empty the wrapper branches straight through to the same code that always ran.
On the instrumented build the equivalence gate still passes 27/27 byte-identical, and
re-running a released slice reproduces every `Mono` run bit-for-bit (30/30, max absolute
difference 0). No released result changes.

Reproduce with `runner/measure_decision_cost.py` (the wall-clock bound) and
`runner/read_decision_cost.py` (the direct measurement); raw timings are released as
`results/decision_cost.parquet`.

### A8 — 2026-09-10 — The scaling of benefit with rate-table size is a post-freeze hypothesis

The result that the benefit grows with the size of the rate table (+11.2% at 12 rates to
+17.9% at 72, r = +0.76) is **not pre-registered.** No such hypothesis appears in §1 or
anywhere else above; it originates in project planning that predates the freeze and was
never carried into the frozen protocol. It should be read as exploratory.

Worth knowing: it was tested twice with opposite outcomes. Under data-rate ordering the
benefit *shrank* as the table grew — the opposite of what had been expected — and that
refutation is what identified the ordering as the defect and produced the required-SNR fix
in A2. Under required-SNR ordering it grows. Both directions are reported, and the sign
change between them is the ablation rather than a selected result.

### A9 — 2026-09-12 — Pre-submission audit: an action-set defect, two metric mislabels, and a numerical error

A colleague's review prompted an audit of the manuscript's claims against the ns-3.48
source, `contrib/cqra`, the runners and the released data rather than against the PDF.
This entry records what the audit found, **before** any code was changed in response. Six
items follow. The first is the reason the campaign is being re-run.

#### A9.1 — The genie and the learners were not on the same action set

`sim/scenarios/eht-ra-gate1.cc:255` sets `WIFI_STANDARD_80211be`, but ns-3.48's shipped
`ThompsonSamplingWifiManager::InitializeStation` has no EHT branch: its ladder runs
HT → VHT → HE and stops. `CqrWifiManager` (`:293-311`) and `OrsWifiManager` (`:159-195`)
mirror that faithfully — deliberately, because the w = 0 equivalence gate requires it. So
the proposed method, the Thompson baseline and the whole ORS family learn over **HE MCS
0–11**, 12 × 3 widths × 2 streams = **72 arms**.

`IdealWifiManager` does not. `IsCandidateModulationClass`
(`src/wifi/model/rate-control/ideal-wifi-manager.cc:617-652`) returns false for HE
"if the node and peer are both EHT capable", so the genie enumerates **EHT MCS 0–13**, 84
arms. `MinstrelHtWifiManager` initialises EHT groups with `UseLatestAmendmentOnly`
defaulting to true, and the `Fixed(MCS*)` references use `EhtMcs*`. The genie, Minstrel-HT
and the static references were on EHT; everything else was on HE.

This is measurable in the released traces, not inferred. At 0 m/s the genie spends
**73.3% of its transmissions at MCS 12–13**, configurations the sampler cannot select at
all. Recomputing §6's mean-MCS bias with the genie confined to the sampler's own range,
paired per run over seeds 1–5 (the subset with released per-run traces; these reproduce
the 10-seed table to within 0.1 MCS):

| speed | genie mean MCS | genie capped at 11 | Thompson | reported bias | corrected bias | genie share at MCS ≥ 12 |
|---|---|---|---|---|---|---|
| 0 m/s | 12.14 | 10.75 | 9.82 | **−2.32** | **−0.94** | 73.3% |
| 2 m/s | 7.39 | 7.32 | 6.84 | −0.56 | −0.49 | 4.5% |
| 5 m/s | 5.52 | 5.52 | 6.63 | +1.11 | +1.12 | 0.4% |
| 20 m/s | 3.81 | 3.81 | 5.56 | +1.75 | +1.75 | 0.0% |

**The sign change survives; roughly 60% of the at-rest magnitude does not.** The aggressive
half is clean, because the genie never reaches MCS 12–13 at speed.

**Resolution.** Rather than disclose the mismatch, the enumeration is being extended.
`CqrWifiManager` and `OrsWifiManager` gain a `ModulationFamily` attribute:
`MatchUpstream` (default) keeps the existing HE ladder so the byte-identity gate against
stock `ThompsonSamplingWifiManager` is preserved unchanged, and `Latest` extends to EHT
MCS 0–13 for an 84-arm table shared with the genie, Minstrel-HT and the static references.
Because stock Thompson cannot enumerate EHT, the Thompson baseline on the 84-arm table
becomes `Cqr(ModulationFamily=Latest, StructureWeight=0)` — which the `MatchUpstream` gate
proves is stock Thompson on the HE table, and which gives the baseline and the proposal
identical action sets by construction. **The whole campaign is re-run on that table**, and
every number in the paper is regenerated from it. One residual is disclosed rather than
engineered away: Minstrel-HT additionally enumerates guard-interval variants that no other
manager does, so exact equality with Minstrel-HT is not achievable.

#### A9.2 — "Extra PHY tx/MB" counts transmissions, not retries

`sim/runner/run_ablation.py:31-37` computes `total_phy_tx / (rx_bytes/1e6)`, and
`total_phy_tx` is incremented once per `MonitorSnifferTx` firing — every MPDU the AP PHY
sends, first transmissions included. §6 named this metric correctly ("extra PHY
transmissions per delivered MB"); the manuscript then described it as retries, which it is
not. Against the 714.3 MPDU/MB floor implied by a 1400 B payload, the retry-attributable
excess is very different from the reported ratio:

| speed | reported | excess over the floor |
|---|---|---|
| 0 m/s | +4.9% | +415% |
| 5 m/s | +15.2% | +38.7% |
| 20 m/s | +40.1% | +70.7% |

The metric is retained and the manuscript wording is corrected. One part of the concern
does not hold: `MonitorSnifferTx` fires once per subframe, so the metric is invariant to
A-MPDU length.

#### A9.3 — The mean-MCS bias discards data that was collected

The scenario records `mcs`, `width` and `nss` marginals, but `run_ablation.py:30-33` reads
only the `mcs` rows. §6's "mean-MCS bias vs genie" is therefore an index-only quantity,
which cannot express aggressiveness when width and streams vary. At 20 m/s the genie runs
79.8 MHz / 1.90 streams while Thompson runs 71.4 MHz / 1.76 — narrower and fewer streams
while at higher MCS. The runner now emits `mean_width` and `mean_nss`, and the paper
reports all three marginals.

#### A9.4 — Absolute throughput in the held-out table was 5% low

`thr` is the **sum of 19** per-interval samples (traffic runs 0.5 → 10.0 s, sampled from
1.0 s), but `paper/check_paper.py:79,81` divided by **20.0**. Every absolute Mb/s figure in
the held-out table was understated by 19/20. It is a uniform scale factor, so no ratio,
percentage, p-value or crossover in the paper is affected. The divisor is corrected and a
regression assertion now ties it to the actual row count. The table had been marked
"verified against the released runs"; the verifying script carried the error.

#### A9.5 — Two descriptions in the manuscript that the source does not support

- **`IdealWifiManager` is not an instantaneous-SNR oracle.** `m_lastSnrObserved` is set in
  `DoReportDataOk`/`DoReportRxOk` — feedback from the previous transmission — and
  `GetLastObservedSnr` then rescales it by the width and stream ratios before comparing it
  with a per-configuration threshold. It is a delayed-feedback threshold selector.
- **The ORS baseline is the linear variant.** `ors-wifi-manager.cc:340-348` explores
  `{k−1, k, k+1}` on a flattened total order; no graph construct exists in the module.
  Combes et al. also define a graphical variant for multiple MIMO modes, and the
  manuscript attributed the one-dimensionality to ORS rather than to the variant we
  implemented. `docs/ors_baseline.md` is corrected to say so. A separate labelling defect:
  `Window` is inert unless `Variant == SW-ORS` (`:237-240`), so tuning rows labelled
  `ORS/RequiredSnr/w1000` and `KL-R-UCB/…/w1000` carry a window the code ignores.

#### A9.6 — Three things now measured that were previously argued

- **The ordering contrast is reported directly.** The campaign tested each ordering against
  Thompson but never against the other, which is the paper's actual claim. From
  `results/mono/order_matched.parquet`, paired at matched (speed, seed, width, streams):
  required-SNR beats data-rate by **+21.1%, 95% CI [+17.9, +24.3], paired t p = 6.5×10⁻²¹,
  Wilcoxon p = 4.7×10⁻¹⁸, winning 99 of 120 matched runs**, and significantly in all five
  non-degenerate (width, streams) cells. No new simulation was needed.
- **The aggregation rule is stated.** Reported gains are a **ratio of grand means**. The
  mean of per-run ratios gives +21.8% / +1.7% against the reported +16.8% / +0.3%; the
  choice moves the headline by about 5 pp and was never stated.
- **The propagated evidence budget is instrumented.** Eq. (1) shares
  `w(n_s·r + n_f·(N−1−r))` for a report at rank `r`, so a fixed `w` does not fix the total
  pseudo-count budget across orderings. Both orderings are permutations of the same rank
  multiset, so the budget can differ only through the rank of the *played* arm, and at
  20 MHz / 1 stream the orderings coincide and the runs are bit-identical — but this is now
  measured per run rather than argued.

#### A9.7 — Two scope corrections to how the scenario is described

- **The stations are recipients, not contenders.** Every `OnOffHelper` is installed on the
  AP (`eht-ra-gate1.cc:386`); the stations carry no uplink data. There is exactly one
  contending data transmitter at every station count, so `{1, 4, 8}` varies the number of
  downlink recipients sharing one transmitter's airtime, not the number of contenders.
- **The crossover speed is interpolated across an unmeasured gap.** Speeds tested are
  {0,1,2,3,5,7,10,15,20}; the reported crossover is a linear interpolation between 10 m/s
  (ratio 1.0354) and 15 m/s (0.9626), with no measurement between, against a per-run
  hindsight-best fixed MCS. The ratio curve is non-monotone and the first downward crossing
  is taken. It is reported as a scenario-dependent estimate with its bracket stated.

#### A9.8 — The equivalence gate covers the w = 0 path only

All 27 configurations in `verify_equivalence.py` are Decay × speed × seed **at w = 0**. The
gate establishes that the reimplementation introduces no incidental difference from the
shipped sampler — which is what it is claimed for — but it does not exercise any
propagation path, and the manuscript is corrected so a reader cannot read it as doing so.
A related implementation detail now stated in the paper: `SampleBetaVariable` takes
`uint64_t` shape arguments in both stock ns-3 and our module, so propagated mass at
w = 0.25 is truncated until four shared observations accumulate.

#### A9.9 — Two run-configuration defects found while re-running

**The released `reproduce.sh` cannot reproduce the envelope references.** `run_gate1.py`
defaults to `--sim-time 20` while `run_ablation.py` defaults to `10`. The original envelope
sweep passed `10` explicitly, so its references span the same window as the campaign they
are compared against; the invocation recovered into `reproduce.sh` dropped the flag. Run as
published it yields 39 sampling intervals per run instead of 19 — 17,550 rows rather than
the 8,550 the file records — and a station that has travelled twice as far, so the static
references come out materially different at 1 m/s. The flag is restored and the row-count
assertion now checks the interval count, not just the row total, which is what let this
through. No published number was wrong; the script that regenerates them was.

**The interval count is now carried in the data.** Every run records `n_intervals`, and the
analysis divides by it rather than by a constant derived from the run length. This closes
A9.4 at the source instead of at the one call site where it happened to bite.

#### A9.10 — What the re-run covers, and what it does not

The 84-arm re-run replaced every input the paper reports from: the campaign, the bias
diagnostic, the ordering ablation, the weight selection and its held-out evaluation, the
S3/S4 splits, the forgetting-rate frontier, the static references, the threshold sweep and
the fairness measurement. `verify_equivalence.py` still passes 27/27 on the upstream
enumeration, and the released analysis scripts reproduce every macro and figure in the
manuscript byte for byte.

Three things were **not** re-run, and no reported number depends on them:

- **`results/decision_cost.parquet`.** The propagation-cost measurement in A7 was taken on
  the 72-arm table. The cost is linear in table size at 14.6 ns per rate plus 302 ns fixed,
  so an 84-arm table implies roughly 1.5 µs per decision rather than the 1.34 µs quoted
  there. That is still a fraction of a percent of one core, and the paper makes no
  numerical claim about it, but A7's table should be read as a 72-arm measurement.
- **The ORS tuning sweeps** (`results/ors/`). Window and ordering were selected on the
  72-arm table and the selected members were carried into the 84-arm campaign, so the
  comparison in the paper is on the corrected table while the *selection* behind it was
  made on the earlier one. A selection made on a smaller table can only disadvantage ORS if
  it is wrong, so this is recorded rather than corrected.
- **The earlier-phase exploratory sweeps** (`gate1/` except the decay frontier, and
  `mono/{configspace,h3_snr,heldout_S2,tune_split}`), which document how the work reached
  its current form. They are retained at 72 arms and labelled as such in the README.

#### A9.11 — The λ-robustness check reported the wrong sign, and the wrong conclusion

Added 2026-09-13, after the 84-arm re-run, during a read-through of §III.

§III defends its central finding — that the sampler's selected-MCS error reverses sign
across the speed range — against the objection that the reversal is an artefact of running
every cell at one forgetting rate. The defence cited the residual bias at rest once λ is
tuned for that cell alone, described as "0.04 steps below the genie".

`make_numbers.py` computed that macro as `abs((tz - gz).mean())`. The signed value is
**+0.036 ± 0.030 (n = 10, p = 0.046): above the genie, not below.** Tuning λ for the
resting cell does not "shrink the conservatism without removing it" — it removes it
(−1.47 → +0.04). The sentence therefore drew the opposite conclusion from its own number,
and the number it quoted had no sign.

The intended claim survives, but it needs the λ sweep rather than one tuned point. Over the
nine swept values, with the genie on the same 84-arm table:

| λ (Hz) | bias at 0 m/s | bias at 20 m/s |
|---|---|---|
| 0 | −1.86 | **+1.83** |
| 0.5 | −1.73 | +1.83 |
| 1 (ns-3 default) | −1.59 | +2.03 |
| 2 (used in Table I) | −1.47 | +2.35 |
| 5 | −0.96 | +2.81 |
| 10 | −0.49 | +3.39 |
| 20 | −0.13 | +3.73 |
| 50 | **+0.04** | +4.35 |
| 100 | +0.06 | +4.75 |

Two statements replace the withdrawn one, both read off this sweep:

1. **The reversal is not an artefact of the chosen λ.** It holds at every swept λ from 0 to
   20 Hz, the ns-3 default included — seven of nine values. It fails only at λ ≥ 50, where
   the resting error is nulled (+0.04) and the error under motion grows to +4.35 steps.
2. **The two ends are not equally reachable.** The resting error can be nulled outright by
   λ alone; the error under motion cannot. Its minimum over the whole swept range is
   **+1.83 ± 0.25 steps** (p = 1.7×10⁻⁷), at the slow end of the sweep — λ = 0 and λ = 0.5
   are indistinguishable there, 1.8273 against 1.8279. Forgetting rate is an adequate
   instrument for one end of the error and not the other.

Statement 2 is a stronger motivation for §IV than the argument it replaces, and it is
**exploratory**: the frozen protocol pre-registers neither the λ sweep as a robustness
check nor the reachability asymmetry. It is reported as such.

`BiasRestOracleAbs` is withdrawn. `BiasRevLamHi`, `BiasNullLam`, `BiasNullRest`,
`BiasNullFast`, `BiasFastFloor` and `BiasFastFloorCI` replace it, and `make_numbers.py`
now asserts that the reversal holds at the slowest swept λ rather than trusting it.

#### A9.12 — "Because of that scale" was a pooled correlation over confounded points

Added 2026-09-13, alongside A9.11.

§III concludes the starvation sweep with "Minstrel-HT degrades *because* of that scale"
from r = −0.84 between table size and convergence-phase throughput, pooled over 22
configurations. Table size is confounded with the amendment: 802.11be's two extra MCS are
4096-QAM and rarely usable at range, so the pooled r alone does not separate "the table is
bigger" from "the new rates are harder".

The check was run and the claim survives. Within each amendment separately, r is −0.95
(802.11n, 4 points), −0.80 (802.11ac, 6), −0.98 (802.11ax, 6) and −0.99 (802.11be, 6). The
partial correlation holding the per-stream MCS count fixed is **−0.83**, against the pooled
−0.84. Size, not the amendment, is doing the work.

The manuscript now reports the partial correlation. `StarveConfigs`, `StarveCorrWithin` and
`StarvePartial` are added to `make_numbers.py`; `StarveCorrWithin` is computed and released
but not cited in the 6-page manuscript, for space. This check is **exploratory** — the
frozen protocol pre-registers the scaling correlation but no confound analysis of it.

#### A9.13 — Eq. (1) is stated on required SNR, but required SNR does not order the table

Added 2026-09-13, during a read-through of §IV.

The manuscript writes the propagation rule with strict inequalities on σ: a failure at rate
*i* adds to `fails` for every *j* with σ_j > σ_i, a success adds to `success` for every *j*
with σ_j < σ_i. That is not what `PropagateMonotoneImpl` does, and the difference is not a
corner case.

`WifiPhy::CalculateSnr` delegates to `ErrorRateModel::CalculateSnr`, which binary-searches
`GetChunkSuccessRate`. For the table-based model that function reads the MCS, the coding and
the SNR — **never the channel width or the stream count**. So all six (width, Nss)
configurations of one MCS return an *identical* threshold: **14 distinct σ values across the
84 arms, six arms each.**

Under Eq. (1) as written, the five arms tied with the played one receive nothing — 6% of
propagation targets per report. `BuildRateOrder` instead sorts `std::pair<double, size_t>`,
so ties are broken by enumeration index and every tied arm *is* updated, as easier or harder
depending on that index.

The implementation is right and the equation is incomplete. A success at MCS 4 / 40 MHz /
1 SS is genuine evidence for MCS 4 / 20 MHz / 1 SS: identical per-stream SNR, less noise in
the narrower band. Eq. (1) abstains where the physics does not.

Two consequences, both now stated in the manuscript:

1. **The tie-break is the required-power order.** Enumeration within an MCS runs (20,1),
   (20,2), (40,1), (40,2), (80,1), (80,2), giving W·Nss of 20, 40, 40, 80, 80, 160 —
   monotone non-decreasing, verified against the released `armset_latest.csv`. The "raw
   required-SNR" ordering therefore already resolves every width/stream comparison, and
   resolves it by required receive power. §IV now says so where σ is defined.
2. **The third ordering tests less than §V-A claimed.** "The effect does not rest on the SNR
   convention" overstates it: `RequiredSnrPower` and `RequiredSnr` agree on every
   within-MCS comparison by construction — exactly the comparisons where the two
   conventions most sharply disagree, up to 8× in power at identical σ. They differ only in
   how MCS are interleaved across (width, stream) groups. The measured result
   (+0.54%, CI [−0.75, +1.82], p = 0.71) is unchanged; §V-A now states what it isolates.

One related check was run and **passed**, and is recorded so it is not re-litigated:
`BuildRateOrder` parks configurations failing `WifiTxVector::IsValid` at `DBL_MAX` under
both SNR keys, while the `DataRate` branch returns before that check — an asymmetry between
the two arms of the ordering ablation. It is inert here. `IsValid` rejects only certain
`VhtMcs` combinations, channel widths above 160 MHz, and MU-RU cases; all 84 SU EHT arms at
20/40/80 MHz with one or two streams pass, so the branch never fires and the arms differ in
the ordering key alone.

Neither the tie-break nor this check appears in the frozen protocol. Both are
**exploratory**, and no reported number changes because of either.

#### A9.14 — `IdealWifiManager` does not enumerate channel widths

Added 2026-09-13, during a read-through of §V.

A9.1 put the genie and the learners on the same MCS range. It did not put them on the same
action set, and the manuscript claimed it had: §V described the 84-tuple set as "the table
`IdealWifiManager` and the static references already use".

`IdealWifiManager::DoGetDataTxVector` fixes the width once, before the search:

```cpp
const auto channelWidth = std::min(GetChannelWidth(station), allowedWidth);
txVector.SetChannelWidth(channelWidth);
```

and then iterates modes and spatial streams only. The other two `SetChannelWidth` calls in
that file are in `BuildSnrThresholds` (threshold-table construction) and the non-HT path;
neither is selection. **The genie's candidate set is 14 MCS × 2 streams = 28 at the granted
width, not 84.** It cannot narrow its channel.

Confirmed in the released data: across all 360 `Ideal` runs in the campaign, mean selected
width ranges over 79.787–79.988 MHz and never falls further, while `Thompson(d=2.0)` reaches
60.2 MHz and `Mono(w=0.25)` 76.0 MHz. The genie's 80 MHz is structural, not a preference.

Three corrections follow:

1. **§V no longer claims a shared table with the genie.** The learners share one 84-tuple
   set by construction; `IdealWifiManager` and Minstrel-HT are the two unmatched arms, and
   both are now disclosed. Minstrel-HT's table is larger (it sweeps guard interval); the
   genie's is smaller.
2. **§III no longer reads the genie's width as a choice.** "no longer *choosing* the same
   shape of configuration" became "without *transmitting* the same shape". The measurement
   is unchanged, and the PHY-rate column added under A9.3 already carries the comparison
   that the MCS index cannot.
3. **The anomaly the paper reported without explaining now has a mechanism.** §V states
   that our method exceeds `IdealWifiManager`, which is why it is treated as a genie rather
   than a bound. A genie that cannot narrow its channel is a concrete reason it is
   exceedable, and that clause now sits where the claim is made.

No reported number changes: every figure in the paper is measured, and the genie's behaviour
is what it always was. What changes is the description of its action set. This is
**exploratory** — the frozen protocol pre-registers `Ideal` as the reference but says
nothing about its enumeration.

Two further checks on §V were run and passed, recorded so they are not repeated: no Wi-Fi
example shipped with ns-3 references `JakesPropagationLossModel`,
`NakagamiPropagationLossModel`, `RayleighPropagationLossModel` or `TwoRayGround` (the
manuscript's claim about the ecosystem's default evaluation setting holds), and every
`OnOffHelper` in the scenario is installed on `apNode.Get(0)`, so the A9.7 correction about
recipient rather than contending stations stands.

#### A9.15 — Two results in §VI and §VII named the wrong cell

Added 2026-09-13, during a read-through of §VI. Both are 72-arm statements that survived
the re-run because the cell *identities* were hand-typed while only the numbers came from
the data. `check_paper.py` verifies numbers against the released runs; it cannot verify a
label.

**The KL-R-UCB reversal.** §VI-B read "the unstructured KL-R-UCB edges out structured
SW-ORS in five of six cells by at most +5.1%, and is itself beaten (−0.4%) in the
single-station path-loss cell." On the 84-arm table that cell is a **+2.1% KL-R-UCB win**:

| cell | KL-R-UCB vs best SW-ORS |
|---|---|
| path loss, 1 STA | +2.10% |
| path loss, 4 STA | +5.13% |
| path loss, 8 STA | +0.52% |
| fading, 1 STA | +2.36% |
| fading, 4 STA | +1.11% |
| **fading, 8 STA** | **−0.45%** |

The reversal is in the eight-station fading cell. `make_numbers.py` now emits the label as
`KlLoCell` rather than leaving it to prose. The generator's own comment was stale in the
same direction — it claimed the reversal was by a wider margin than any cell in which the
comparison holds, which was true at 72 arms and is false at 84 (−0.4% against wins to
+5.1%). Corrected.

**Pattern A's magnitude.** §VII reported "on pure path loss with a single station a
well-tuned λ beats us by up to 12.3% at high speed". `PatternALoss` was computed as the
absolute value of the minimum over the **whole** Thompson column, and that minimum is
(logdistance+jakes, 4 STA) at 0 m/s — a **pattern B** cell, already quoted correctly two
sentences later as pattern B's upper end. The same number was therefore printed for two
distinct failure patterns, and Table V showed −5.8 for the pattern A cell three inches away.

Measured in its own cell with the margin definition `make_percell.py` uses, pattern A is
**−5.79% at 10 m/s** against `Thompson(d=10)` (next worst −5.57% at 20 m/s). The manuscript
now reports 5.8%, adds `PatternASpeed`, and `make_numbers.py` asserts that pattern A can
never again equal the table-wide minimum.

Neither error favoured the paper: the first named a cell that contradicts the claim, and the
second overstated our own worst path-loss failure by 2.1×.

#### A9.16 — The propagated-evidence budget, measured rather than argued

Added 2026-09-13, alongside A9.15.

**The instrumentation was built and never harvested.** A9.5 added accumulators for the
realised propagated mass (`succ_mass`, `fail_mass`, `targets`, `rank_sum`, written to the
cost log). §VI-A then *argued* the budget qualification from the equation instead of
measuring it. It is now measured.

**A blocking defect first.** `read_decision_cost.py` unpacked four fields from that cost
log and cast every one with `int()`. The log has had eight fields since the budget work
landed, two of them floats, so the script raised
`ValueError: invalid literal for int() with base 10: '15.75'` against the module shipped
beside it — a runner in a reproducibility artifact that could not run. It now reads by
header name, so a further column cannot break it again.

**The measurement.** `measure_budget.py` (new) runs both orderings on the grid
`results/mono/order_matched.parquet` uses — w = 0.25, λ = 2 Hz, 4 STAs,
`logdistance+jakes`, speeds {5, 20}, all six (width, streams) groups, 10 seeds — and reads
the realised masses. 240 runs, 0 failures, released as `results/mono/budget.parquet`.

Paired over the 120 matched cells:

| quantity | required SNR | data rate | paired | p |
|---|---|---|---|---|
| propagated mass per report | 98.1 | 87.4 | **+19.7%** | 1.7×10⁻¹² |
| propagation targets | 146,305 | 116,255 | +17.8% | 3.5×10⁻¹³ |
| mean played rank (of 84) | 17.9 | 23.7 | −17.5% | 1.2×10⁻¹⁵ |

**The qualification is confirmed, not removed.** The two orderings do *not* spend
comparable budgets: required SNR spends about a fifth more per report, because its played
configuration sits lower in its own order and Eq. (1) then has more harder-rate targets to
send failure mass to. The hedge in §VI-A therefore stands — the ablation identifies the
ordering as a consequential design choice, not evidence direction isolated from its
concentration — and it now rests on a measurement rather than on an argument. The stronger
claim that the ordering is *the entire* mechanism remains unearned, and is not made.

The measurement validates itself on the same null control the throughput ablation uses. At
20 MHz with one stream the two orderings are the same permutation, and the budgets agree
**exactly**: +0.000%, identical mean rank 5.6. The divergence then grows with table
dimensionality — +13.4% (20/2), +12.8% (40/1), +23.2% (40/2), +31.9% (80/1), +36.7% (80/2)
— in the same order as the heterogeneity the ordering has to resolve. `make_numbers.py`
asserts the 1-D control is exactly zero; if it ever is not, the instrument is measuring
something other than the ordering.

This measurement is **exploratory**: the frozen protocol pre-registers the ordering
ablation but no budget accounting for it.

**A second artifact defect, found while wiring the new run in.** `reproduce.sh` documents
`DRY_RUN=1 bash reproduce.sh` as "print every grid size, run nothing", and its `run()`
helper passes `--dry-run` to every runner. Only `run_sweep.py` accepted it: `run_ablation.py`
and `run_gate1.py` did not, so the documented dry run died on an argparse error at the first
of the 19 blocks and never reached the other 17. Both now accept the flag, print the grid
size and return, as `run_sweep.py` already did, and `measure_budget.py` follows the same
convention. `DRY_RUN=1 bash reproduce.sh` now completes and prints all 20 grid sizes.

#### A9.17 — A range whose ends printed identically, and an untied constant in §VII

Added 2026-09-13, during a read-through of §VII.

**"loses 17–17% under motion".** The adaptive-λ ablation loses in both moving cells of its
grid, −16.52% at 10 m/s and −16.84% at 2 m/s. `AdaptMoveLo`/`AdaptMoveHi` were formatted at
`.0f`, so both rendered as 17 and the manuscript printed a range with identical endpoints —
which reads as a typesetting fault rather than a measurement. The numbers were right; the
presentation was not. Both now print at one decimal, matching the pattern B range two
sentences earlier, and `make_numbers.py` asserts the endpoints remain distinguishable so a
future collapse is caught rather than typeset.

**Why λ = 50 in pattern B.** §VII argues that the resting-cell loss under fading is a
fixed-λ artefact, "since re-running *ours* at λ = 50 there turns both losses into gains".
`PB_LAM = 50` was a hardcoded constant, and a reader is entitled to ask whether it was
chosen to make the loss disappear. It was not: 50 Hz is the resting throughput optimum §III
measures independently (`LambdaRest`). The constant is now asserted equal to that
measurement, and the manuscript names the connection instead of leaving it to be inferred.

**One claim removed.** §VII speculated that "a signal using the *sign consistency* of
successive errors could separate them". That was a conjecture, not a result. The diagnosis
it followed — excess prediction error cannot distinguish fast fading around a stable mean
from a drifting mean — is retained, now stated as the magnitude of the error not carrying
the distinction. Nothing measured changes.

Four §VII claims were checked against the data and hold, recorded so they are not
re-litigated:

- **Three of eighteen cells, in two patterns.** The three daggered cells are (path loss,
  1 STA), (fading, 4 STA) and (fading, 8 STA); pattern A is the first and pattern B the
  other two, so the two patterns account for all three failures.
- **"A very forgetful sampler."** The winning Thompson arm in the pattern B cells is
  λ = 50 Hz at four stations and λ = 20 Hz at eight — both far more forgetful than the
  shipped λ = 1 or the campaign's λ = 2.
- **"The cell that motivated it."** The adaptive-λ grid is four stations on the fading
  channel at speeds {0, 2, 10}, all tuning-split speeds, and the motivating cell is its
  0 m/s point — one of the two pattern B cells. The ablation is consistent with the
  pattern it was built to address, and used no held-out speed.
- **Flat fading.** ns-3's `JakesPropagationLossModel` is a propagation loss model, single
  tap, so the manuscript's statement that it is flat where real 80 MHz fading is frequency
  selective is correct.

#### A9.18 — The abstract and §I did not inherit three corrections made to the body

Added 2026-09-13, during a read-through of the abstract and §I.

Three earlier amendments corrected claims in the body and left the same claims standing in
the abstract and the introduction — the two parts of the paper most people read, and the
only two a reviewer is certain to read. The paper was internally inconsistent in both.

**1. "The result does not rest on an SNR convention" (abstract).** A9.13 established that
`RequiredSnrPower` and `RequiredSnr` agree on every within-MCS comparison by construction —
precisely the comparisons where the two conventions most sharply disagree — and differ only
in how MCS interleave across (width, stream) groups. §IV and §VI-A were both corrected to
say what the comparison isolates. The abstract still claimed the general form. It now reads
"the result is robust to that normalisation", which is what was measured.

**2. "Differs from a genie on the same action set" (§I).** A9.14 established that
`IdealWifiManager` cannot narrow its channel and ranges over 28 of the 84 configurations.
§V and §III were corrected; §I's contribution list still asserted a shared action set. The
qualifier is removed — the genie's action set is stated in §V, which is where it belongs.

**3. "The deployed bandit" (§I).** ns-3's discounted Thompson sampler is shipped with the
simulator, not deployed in any product; Minstrel-HT is the deployed one. §III and Fig. 1's
caption were corrected; §I's contribution list was the last instance. Now "the shipped
bandit", matching §I's own opening sentence two paragraphs earlier.

**One further scope slip, same class.** §VI-A attributes the ordering difference "to the
ordering and to nothing else **in the implementation**"; the abstract dropped the scope and
said "to ordering alone", which reads as a stronger attribution than the null control
supports — particularly next to A9.16's finding that the realised propagation budgets
differ. The abstract now says the control "isolates the ordering from the rest of the
implementation".

**And one latent trap, fixed rather than found.** `TableGrowth` was
`StarveBigN // StarveSmallN`, and the abstract prints it as the growth "from 802.11a to
802.11be". `StarveSmallN` is the small end of the *manager sweep* — an 802.11n 20 MHz
single-stream table — which happens to hold eight rates, the same as 802.11a's eight OFDM
data rates. The abstract and §I were therefore correct only by coincidence, and a change to
the sweep grid would have silently restated the standard. 802.11a's count is now an explicit
`LegacyRates` constant, documented as the standard's own figure.

No measured value changes. The lesson is procedural and worth recording: **a correction to
a body section is not complete until the abstract and introduction have been re-read against
it.** Sections III to VII were each audited and corrected in turn, and none of those passes
looked forward to the summary that had already asserted the uncorrected claim.

#### A9.19 — §II said Minstrel-HT is ns-3's default. It is not; the default is the genie.

Added 2026-09-13, during a read-through of §II.

§II opened "Minstrel and Minstrel-HT remain the default in Linux and in ns-3". The Linux
half is right. The ns-3 half is not: `WifiHelper`'s constructor
(`src/wifi/helper/wifi-helper.cc:1006`) calls

```cpp
SetRemoteStationManager("ns3::IdealWifiManager");
```

so ns-3.48's out-of-the-box rate manager is **`IdealWifiManager`** — the same manager this
paper uses as its genie. Any reviewer who knows the tree opens that file and sees it.

The sentence now states what is true and keeps the fact, which is worth having: Minstrel-HT
is Linux's default and ships with ns-3, whose own default is the `Ideal` genie. That pairs
with §V's observation that no shipped ns-3 Wi-Fi example uses a fading model — both say
something about what this ecosystem treats as a default evaluation setting — and it tells a
reader why a "genie" is the thing sitting in the helper.

**A citation-scope slip this exposed.** The original plural subject ("Minstrel *and*
Minstrel-HT … *Their* behaviour has been studied empirically") let `\cite{minstrel}` cover
the sentence. That reference is Xia, Hart and Fu on Minstrel in **802.11g** — legacy
Minstrel, since 802.11g has no HT. Narrowing the subject to Minstrel-HT left the citation
attached to the wrong algorithm, so the text now says "its legacy predecessor was studied
empirically", which is what the cited work actually did and which also sets up the
`LookAroundRate` note two sentences later.

**Re-verified in the built tree, all exact**, since §II states them as fact:

| §II claim | source |
|---|---|
| at most 16 samples per interval | `station->m_sampleCount = 16` (`minstrel-ht-wifi-manager.cc:475`) |
| 50 ms statistics interval | `UpdateStatistics` default `MilliSeconds(50)` (`:124`) |
| wait of 16 + 2·L̄_ampdu attempts | `station->m_sampleWait = 16 + 2 * station->m_avgAmpduLen` (`:936`) |
| the "10% lookaround" is legacy-only | `LookAroundRate`'s description reads "(for legacy Minstrel)" and its one use forwards to `m_legacyManager` (`:511`) |

**What was not re-verified.** §II's claims about the *content* of cited work — Combes et
al.'s graphical variant and sliding-window extension, the WNS3 verification's 802.11ax
convergence finding, DARA's 15% over Minstrel-HT — rest on the survey record from the
planning phase, not on re-reading those papers in this audit. They are consistent with that
record; they were not independently re-checked here.

#### A9.20 — The baseline's crossover was read off a curve that crosses unity twice

Added 2026-09-13, during a read-through of §VI-C.

§VI-C reported that, against a per-speed static rate chosen in hindsight, "adaptation stops
paying at **0.5 m/s** for the Thompson baseline and 9.3 m/s for our method". Both `cross()`
in `make_numbers.py` and `crossing()` in `make_figs.py` returned the **first** downward
crossing of unity. The Thompson ratio curve is not monotone:

| speed (m/s) | 0 | 1 | 2 | 3 | 5 | 7 | 10 | 15 | 20 |
|---|---|---|---|---|---|---|---|---|---|
| Thompson / hindsight static | 1.012 | **0.985** | **1.030** | 0.994 | 0.888 | 0.813 | 0.760 | 0.693 | 0.611 |
| ours / hindsight static | 1.035 | 1.033 | 1.170 | 1.136 | 1.087 | 1.038 | **0.989** | 0.946 | 0.901 |

It falls below unity between 0 and 1 m/s, **comes back above at 2 m/s**, and only stays
below after 3 m/s. So 0.5 m/s is a speed at which the baseline demonstrably beats the static
reference two measurements later, reported as the speed above which it stops paying.

Both functions now take the **last** downward crossing — the one the curve does not recover
from, which is what the section's question asks for — and assert the ratio stays below unity
above it. The Thompson crossover becomes **2.8 m/s**, bracket [2, 3]. Ours is unchanged at
**9.3 m/s**, bracket [7, 10]: its curve crosses unity exactly once, and `make_numbers.py`
now asserts that, since our figure is only a boundary if it does.

The contrast shrinks from roughly 20x to 3.3x. The manuscript never quoted that ratio — it
said the baseline's small value made it unstable — so no reported ratio changes, and the
reason for the caution is now the right one: non-monotonicity, not smallness. §VI-C states
how many times the baseline's curve falls through unity.

**The figure cross-check earned its keep.** `make_figs.py` carries its own copy of the
crossing logic and is verified against `numbers.tex` before the PNG is written. Fixing only
the generator produced `DRIFT crossover, Thompson figure=+0.45 numbers.tex=2.8` and
`check_paper.py` refused to pass. Two independent implementations of the same rule, checked
against each other, caught a half-finished fix that a single implementation would have
hidden.

Everything else checked in §VI-C holds, and is recorded so it is not re-derived:

- **The 7 m/s bracket is a real measurement.** The threshold sweep runs a denser speed grid
  than the campaign — {0, 1, 2, 3, 5, 7, 10, 15, 20} — so interpolating between 7 and 10 m/s
  uses two tested points. (An earlier draft interpolated across 10 to 15 with nothing
  between; that is what A9.7 corrected.)
- **Fairness and starvation.** 66 of 360 runs starve a station: 12 ours, 25 Thompson, 29
  Minstrel-HT, summing exactly to 66; 63 of the 66 (95.5%) are at 20 m/s. Jain is 0.977 at
  four recipients and 0.937 at eight over the held-out speeds, and 0.825 at eight stations
  at 20 m/s. All match the manuscript.
- **Provenance.** `results/fairness/jain.parquet` is from the 84-arm re-run, and
  `measure_fairness.py` passes `--modFamily`. The fairness claims are on the corrected table.

#### A9.21 — Three presentation defects in §VIII

Added 2026-09-13, during a read-through of the conclusion. None changes a measured value;
all three are ways the summary said something the body does not.

**1. Mixed precision inside one clause.** The conclusion printed "1.5 MCS steps below the
genie at rest and 2.35 above at 20 m/s" — `BiasRestAbs` at one decimal, `BiasFastAbs` at
two. Besides reading badly, 1.5 matches no figure anywhere in the paper: Table I reports
−1.47 ± 0.13. Both now print at two decimals, and `make_numbers.py` asserts each equals its
Table I entry, so the conclusion and the table cannot drift apart.

**2. An exploratory result stated flat.** §VI-A labels the size–benefit correlation
exploratory — "not pre-registered, the correlation is over six cells, two of which share a
table size" — and §I lists "which results were exploratory rather than pre-committed" as
part of the third contribution. The conclusion then recapped `r = +0.88` against
`r = −0.59` with no marker, alongside the pre-registered results and as the last thing a
reader sees. It is now marked in place. The paired ordering contrast, which is
pre-registered, leads the sentence instead.

**3. An ambiguous denominator.** "loses in three of eighteen cells to a per-cell-tuned
Thompson frontier" invites reading eighteen as the Thompson denominator; it is the total
across three baseline families, six cells each, and the Thompson-specific figure is 3/6. Now
"three of eighteen family cells, **all** to a per-cell-tuned Thompson frontier", which is
both unambiguous and more forthcoming — every failure in the campaign is against one family.

**Checked and clean.** The conclusion inherited none of the three claims A9.18 had to
correct in the abstract and §I: it does not say the genie is on the same action set, does
not call ns-3's sampler deployed, and does not claim the result is independent of an SNR
convention. Its crossover figure (~9 m/s) is ours, unaffected by A9.20's correction to the
baseline's.

#### A9.22 — Four defects that only a sequential read of the compiled PDF exposed

Added 2026-09-13, after compiling and reading the paper end to end. Sections II–VIII had each
been audited in isolation; none of these four survives that kind of pass, and none of them is
visible in the LaTeX source.

**1. The artifact URL was typeset with a space in it.** The `url` package's default break set
includes the colon, so `\url{https://github.com/...}` wrapped as

```
... from those outputs: https:
//github.com/pz1004/ns3-monotone-rate-adaptation.
```

A reader copying the paper's one reproducibility link got `https: //github.com/...`. The
preamble now removes the colon from `\UrlNoBreaks`, so the line wraps after `https://`
instead — a legal break that leaves no token split. Checked in the rendered PDF, not in the
source, because the source looked correct either way.

**2. Table IV's caption claimed matched arm sets.** It read "Arm sets matched", written
before A9.14. Three of that table's seven rows are not on the 84-arm set: the `Ideal` genie
searches 28 configurations at one width, Minstrel-HT additionally sweeps guard interval, and
the two static references are single fixed rates. The caption now says "Learning arms share
one action set", matching §V. This is the same inheritance failure A9.18 recorded for the
abstract and §I — a claim corrected in the body and left standing in a caption, which no
prose audit reads.

**3. A bare number ending a sentence.** §III read "the error under motion grows to +4.35",
with the unit established only in the parenthesis before it. Now "+4.35 steps".

**4. An arithmetic trap in the abstract.** The abstract gives +1.0% for data-rate ordering,
+21.5% for required SNR, then "+25.8% ahead". A reader who subtracts gets 20.5 and suspects
an inconsistency. There is none — the first two are ratios of means over the grid and the
third is paired per run, as Table III's caption states — but the abstract had no signal that
a different quantity was being reported. It now says "+25.8% ahead **run for run**".

Nothing measured changes. The general point is that section-by-section auditing has a blind
spot: it does not read captions against prose written later, it does not see typesetting, and
it does not notice that three numbers in one paragraph invite an arithmetic a reader will
attempt. Compiling and reading the whole document is a distinct check, and it found four
things twenty-one amendments of section auditing had not.

#### A9.23 — §III attributed two numbers to the wrong party, and claimed a monotonicity its own sweep refutes

*2026-09-13. Exploratory re-read of §III after the preceding twenty-two amendments had
changed most of the section around it. Six corrections; no measurement changes.*

**1. The transmission-excess figures were swapped.** §III read "Its extra transmissions
there are small in absolute terms — 9 MPDU/MB above the 714 floor …, against the sampler's
72". `ExcGenieVzero` = 9 is the **genie's** excess and `ExcThomVzero` = 72 is the
**sampler's** (`make_numbers.py`, `m["exc_i"]` / `m["exc_t"]`; confirmed from
`diag/bias10.parquet` at 8.51 and 71.87). "Its" takes the sampler as antecedent from the two
preceding clauses, so the sentence assigned the sampler both figures; resolving "Its" to the
genie instead made the following clause — "they are exploration, not lag" — credit
exploration to a reference the same paragraph says never explores. The two are now named
explicitly and in the right order.

**2. "Forgetting faster pushes selection up the table at every speed" is not monotone.**
True end to end — bias at λ=100 exceeds bias at λ=0 at all six swept speeds — but at
1, 2 and 5 m/s raising λ from zero first pushes selection **down**, by 0.50, 1.16 and 0.87
MCS steps against 95% CIs of 0.10–0.15. (10 m/s dips by 0.04, inside its interval, and is
counted as monotone.) The existing hedge — "a tendency rather than a determinate choice,
since selection remains randomised" — covers the stochasticity of a single draw, not a
systematic reversal across half the sweep. This is the A9.20 failure mode a second time: a
claim about the shape of a curve that the released curve does not have.

The prose now states the endpoint claim and the non-monotonicity separately, which
strengthens the paragraph — λ being a non-monotone instrument is a better argument for "one
direction of adjustment is a poor instrument" than the monotone version was.
`make_numbers.py` now asserts the endpoint claim and emits the dipping speeds as
`\NumLamDipSpeeds`, so neither half can drift from the data again.

**3. The genie's channel width was presented as a choice.** §III contrasted "the genie runs
80 MHz … against the sampler's 68 MHz" as a difference in selected configuration shape. Per
A9.14 the genie does not enumerate widths at all: it ranges over 28 of the 84 configurations
and never drops below 79.8 MHz in any run. §V discloses this; §III, which is read first, did
not, and its own list of genie caveats named the delayed-feedback limitation but not this
one — the one that matters four lines later. The width is now stated as the fixed level the
genie never narrows from, so the narrowing is attributed to the sampler alone. The streams
comparison (1.90 against 1.72) is unchanged and remains a genuine choice contrast, since the
genie does search streams.

**4–6. Three smaller ones.** "Only at λ=50 Hz does the resting error vanish" → "Not until":
λ=100 also leaves it non-negative (+0.06), and the generator takes the smallest such λ.
"The starvation claim of Sec. I" → "Sec. I's evidence-thinning claim": §I never uses the
word, so the cross-reference named a claim the target does not make. "changing sign at
roughly walking pace" → "between 2 and 5 m/s": the interpolated crossing is ≈2.5 m/s, about
twice walking pace, and the table's own granularity is the honest statement.

Findings 1–3 are all label errors rather than value errors — which party a number belongs
to, what shape a curve has, whether a quantity was chosen or fixed. `check_paper.py`
verifies that 9 and 72 are the right numbers and cannot verify which party owns each. That
is the same blind spot A9.15 and A9.20 recorded; the durable fix remains emitting identities
and shapes as macros and assertions, which finding 2 now does.
