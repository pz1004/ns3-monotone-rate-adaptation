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
