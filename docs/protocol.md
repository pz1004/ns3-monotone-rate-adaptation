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

### A1 — 2026-09-08 17:12 — H-main: the mechanism was replaced; the form of the claim was not

**The calibrated-quantile rule named in §1 was refuted under this protocol's own
refutation criterion, and is withdrawn.** Against the oracle-tuned baseline (`Decay`=2)
under fading with 4 STAs, 5 seeds, the corrected rule ran 3–5 pp *below* the baseline at
every speed from 0 to 20 m/s while the selection bias barely moved — which is the second
of §1's two H-mech refutation conditions ("the bias moves without throughput following, or
throughput improves without the bias moving").

The cause is structural, not a tuning failure, and it determined everything after it:
**self-calibration on the arm actually played cannot correct a selection error across
arms.** Thompson's posterior is already approximately calibrated on the arms it plays, so
the calibration error is near zero and the quantile level has no gradient. But the bias
against the genie is an *off-policy* quantity — the genie would have played a different
arm — and no signal derived only from the played arm can observe it.

**Replacement.** H-main is now tested for *monotone evidence propagation ordered by
required SNR*: each outcome is shared along the rate order, a failure at rate *r* adding
`w × nFail` to every rate needing more SNR and a success adding `w × nSucc` to every rate
needing less, with the target discounted before the addition so inferred evidence ages on
the same schedule as observed evidence. The order comes from
`WifiPhy::CalculateSnr(txVector, 1e-6)`.

**Why the pre-registration still binds.** The *form* of H-main is unchanged and is what
the paper reports against: one fixed configuration dominating the entire swept
fixed-`Decay` frontier, on held-out speeds, refuted if it fails to dominate in the
majority of (speed × channel) cells with non-overlapping CIs. §4's statistics are
unchanged. What changed is the rule being tested, not the test.

**A weakening a reader should weigh.** The refutation above was measured across speeds
{0, 2, 5, 10, 20}, which includes the held-out speeds 5 and 20. Because the outcome was
abandonment rather than selection, no configuration was chosen on held-out data — but the
decision to change direction was informed by it. Every selection made after this point
used the tuning split alone (A3).

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

**This replacement was formulated after the data-rate ordering was measured.** It is an
explanatory hypothesis confirmed by a designed negative control, not a pre-committed
prediction, and should be read that way. The diagnostic that motivated the original
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

### A4 — Two inputs fall below §4's seed floor

§4 requires **≥10 seeds** per cell, "≥5 only under the descope ladder" — a term this
protocol never defines, which is itself a defect in the frozen text. The campaign and
every held-out evaluation use 10 seeds. Two smaller inputs do not:

- `results/gate1/decay_frontier.parquet` — **5 seeds**. Supplies one reported quantity:
  how many percentage points the best single forgetting rate falls short of the per-speed
  best. At §4's stated floor, but only under the undefined condition.
- `results/day3_validation/mgr_sweep.parquet` — **2 seeds**. **Below the floor.** This
  supplies the motivating measurement in the introduction: Minstrel-HT's convergence-phase
  throughput falling from 99.6% of a genie at 8 rates to 47.1% at 72, tracking table size
  at r = −0.68.

The second is the one that matters, because it is a framing claim rather than a result,
and §4 also says "single-run curves are not acceptable". It is reported here rather than
left for a reader to find. Both sweeps are inexpensive to repeat at 10 seeds.

### A5 — 2026-09-08 21:53 — Primary metric changed to absolute throughput

§6 makes the primary metric "aggregate delivered throughput as % of the
`IdealWifiManager` genie". `IdealWifiManager` turned out not to be an upper bound — the
proposed method exceeds it — which §7 anticipated as a caveat but §6 did not accommodate
as a metric. A ratio against a reference that can be beaten is not a sound headline
quantity.

**The primary metric is now absolute delivered throughput (Mb/s)**; genie-relative figures
are retained as diagnostics only. Two static references were added and are reported
alongside: the best fixed rate chosen in hindsight, and the per-interval best-fixed-rate
envelope (`results/envelope/`, derived by `analysis/make_references.py`).

This change worked against the headline rather than for it. Measured on the new metric,
the method loses to an oracle static rate at 20 m/s — as does every adaptive scheme
tested — and that loss is reported.

### A6 — 2026-09-08 19:44 — Reference set extended with the ORS family

§3 lists `IdealWifiManager`, `MinstrelHt` (defaults and swept) and the best-fixed-rate
envelope. ORS, SW-ORS and KL-R-UCB (Combes, Proutiere, Yun, Ok & Yi, INFOCOM 2014) were
added after the freeze: they are the other rate-adaptation family that exploits structure
across rates, and therefore the comparison that isolates what the required-SNR ordering
contributes.

They are our reimplementation from the paper's pseudocode, labelled as ours per §7. Window
and ordering were swept on the tuning split and the best member of each family carried
into the campaign. See `docs/ors_baseline.md`.

### A7 — Three of the five pre-committed secondary metrics are not reported

§6 pre-commits five secondary metrics. Two are reported (both in Table I of the paper):
mean-MCS bias against the genie, and extra PHY transmissions per delivered MB. Three are
not:

- **Realised frame-error rate against the target** — no longer defined. The absolute FER
  target was removed with the calibrated-quantile rule (A1), so there is no target to miss,
  and §7's guard requiring it to be reported is moot for the same reason.
- **Per-STA Jain fairness** — not reported, and not recoverable from the released data:
  the scenario logs per-interval *aggregate* throughput only, so obtaining it would require
  re-instrumenting the scenario and re-running.
- **The policy's own decision cost** — not reported as a measured number.

The first is moot; the other two are shortfalls against this protocol.

### A8 — The scaling of benefit with rate-table size is a post-freeze hypothesis

The result that the benefit grows with the size of the rate table (+11.2% at 12 rates to
+17.9% at 72, r = +0.76) is **not pre-registered.** No such hypothesis appears in §1 or
anywhere else above; it originates in project planning that predates the freeze and was
never carried into the frozen protocol. It should be read as exploratory.

Worth knowing: it was tested twice with opposite outcomes. Under data-rate ordering the
benefit *shrank* as the table grew — the opposite of what had been expected — and that
refutation is what identified the ordering as the defect and produced the required-SNR fix
in A2. Under required-SNR ordering it grows. Both directions are reported, and the sign
change between them is the ablation rather than a selected result.
