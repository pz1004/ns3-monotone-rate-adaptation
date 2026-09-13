# ORS baseline — implemented faithfully, tuned fairly, and reported honestly

Date 2026-09-08. `ns3::OrsWifiManager` in `contrib/cqra`, after Combes, Proutiere, Yun,
Ok & Yi, *Optimal Rate Sampling in 802.11 Systems*, INFOCOM 2014 (arXiv:1307.7309).

This is the one comparison a reviewer who knows the rate-adaptation literature will
demand, because ORS also exploits rate structure. It was implemented from the paper's
pseudocode, not from memory.

## What was implemented
All three algorithms from the paper:
- **ORS** (Algorithm 1) — leader `L(n) = argmax_k r_k·θ̂_k`; neighbourhood
  `N(k) = {k−1, k, k+1}`; KL-UCB index
  `b_k = max{q ∈ [0,r_k] : t_k·I(μ̂_k/r_k, q/r_k) ≤ log l_L + c·log log l_L}`;
  exploit the leader when `(l_L − 1) mod 3 = 0`, else play `argmax_{k∈N(L)} b_k`;
  initialise by playing each rate once.
- **SW-ORS** (Algorithm 3) — the paper's own **non-stationary** variant, computing every
  quantity over a sliding window of τ reports. This is the fair comparator in a mobile
  scenario; using only stationary ORS would have been a straw man.
- **KL-R-UCB** (Algorithm 2) — the paper's *unstructured* control.

The KL-UCB index is solved by 40-step bisection on the Bernoulli KL divergence.

## What was NOT implemented, and the attribution this corrects

Recorded 2026-09-12 with protocol-v1 amendment A9.5, after a reviewer pointed out that the
manuscript characterised ORS through a linear neighbourhood and stationary asymptotics.

**We implemented the linear variant.** `N(k) = {k−1, k, k+1}` is arithmetic on a position
in a flat `std::vector` that holds every (mode, width, Nss) triple collapsed into one total
order (`ors-wifi-manager.cc:340-348`). There is no adjacency structure anywhere in the
module.

Combes *et al.* also define a **graphical** variant (G-ORS) in which the neighbourhood is a
graph over configurations rather than two positions on a line, precisely for the
multiple-MIMO-mode case, and they give a sliding-window extension for non-stationary
settings with guarantees under their assumptions. **SW-ORS below is their sliding-window
algorithm; the graphical neighbourhood is not implemented here.**

Two consequences, both of which the manuscript now states:

1. A comparison against our linear SW-ORS supports a conclusion about *that* variant. It
   does not support a conclusion about graphical ORS, and the paper must not generalise to
   the broader class.
2. The observation below that unstructured KL-R-UCB edges out structured SW-ORS is a
   finite-horizon result measured outside the theorem's assumptions. Describing it as "a
   reversal of the stationary theory" overstates it: a result outside a theorem's
   hypotheses does not reverse the theorem. The wording is corrected.

**A labelling defect in the same area.** `Window` is inert unless `Variant == SW-ORS`
(`EvictWindow` returns immediately otherwise, `ors-wifi-manager.cc:237-240`), so tuning rows
labelled `ORS/RequiredSnr/w1000` and `KL-R-UCB/DataRate/w1000` advertise a window the code
never applies. No result changes — KL-R-UCB is unwindowed by design — but the labels are
misleading and are corrected.

## Two fairness problems found and fixed before reporting any number
1. **Unmatched arm set.** My first version enumerated every (mode, width, Nss) triple
   passing `IsValid()`, while `ThompsonSamplingWifiManager` filters to a single modulation
   class and requires `mode.IsAllowed(width, nss)`. ORS was therefore exploring a strictly
   larger, partly redundant table than the baseline it was compared against — a serious
   handicap, since its neighbourhood advances only one step per decision. Fixed to build
   the **identical** arm set (verified: 12 MCS × 2 Nss × 3 widths for both). This alone
   lifted ORS from 74 → 102 Mb/s at 5 m/s.
2. **The runner silently dropped the ORS flags.** A patch anchor did not match, so
   `--orsVariant/--orsOrder/--orsWindow` never reached the binary and every window value
   produced byte-identical results. Caught precisely *because* the sweep showed no
   variation across τ — a sweep that produces identical numbers is evidence of a
   plumbing bug, not of an insensitive parameter.

## Tuning (tuning split {0, 2, 10} m/s only, 10 seeds)
τ swept over {200, 500, 1000, 2000, 5000}, both orderings, all three variants — the same
treatment Thompson's `Decay` received.

| config | mean Mb/s |
|---|---|
| Ideal (genie) | 369.4 |
| Thompson (`Decay`=2) | 312.2 |
| **KL-R-UCB / w1000** | **263.1** ← best ORS-family |
| SW-ORS / RequiredSnr / w2000 | 256.4 |
| SW-ORS / DataRate / w2000 | 255.2 |
| ORS / RequiredSnr / w1000 | 255.2 |
| SW-ORS / DataRate / w200 | 137.1 |

Performance rises monotonically with τ and saturates by ~1000–2000, i.e. SW-ORS converges
toward stationary ORS: **the sliding window is not the binding constraint here.**

## Held-out result (speeds 1, 5, 20 m/s, 10 seeds, absolute Mb/s)

| arm | v=1 | v=5 | v=20 | mean |
|---|---|---|---|---|
| Ideal (genie) | 509.8 | 147.5 | 23.8 | 227.0 |
| **Mono (ours)** | **426.7** | **156.0** | **24.1** | **202.3** |
| Thompson (`Decay`=2) | 411.3 | 134.7 | 18.0 | 188.0 |
| SW-ORS / DataRate / w2000 | 338.4 | 93.6 | 11.4 | 147.8 |
| SW-ORS / RequiredSnr / w2000 | 333.8 | 91.3 | 11.7 | 145.6 |
| KL-R-UCB / w1000 | 337.8 | 87.9 | 10.4 | 145.4 |

Ours vs the best ORS-family configuration: **+26.3% / +77.4% / +131.5%** at 1 / 5 / 20 m/s,
all p ≤ 1.3e-7.

## How this must be framed in the paper — ORS is not "bad"
ORS underperforms **Thompson** here too (≈146 vs 188 Mb/s), so it would be dishonest to
present it as a defeated state of the art. The regime is simply outside its design
envelope, and the paper says so itself:

- **Its guarantee is asymptotic and stationary.** Theorem 6.1 fixes θ ∈ T ∩ U. Our channel
  drifts continuously under mobility.
- **`N(k) = {k−1, k, k+1}` advances one step per decision.** With 72 arms and a 10 s run,
  it cannot traverse the table fast enough when the optimum jumps many steps. ORS's
  celebrated property — regret independent of K — is an *asymptotic* statement, and the
  transient is exactly what a mobile Wi-Fi link lives in.
- **Corroborating evidence:** the *unstructured* KL-R-UCB slightly **beats** structured
  ORS/SW-ORS here (263.1 vs ≈255). That is what one expects if the neighbourhood
  restriction is a liability under drift rather than an asset. It is a finite-horizon
  measurement outside the theorem's assumptions, not a contradiction of it.

## A nuance worth reporting
The required-SNR ordering, which is decisive for our method (+1.3 pp → +14.4 pp), gives
ORS **no reliable benefit**: 256.4 vs 255.2 on the tuning split, and 145.6 vs 147.8 on
held-out — within noise, and with the sign flipping between splits. This is mechanistically
coherent rather than awkward: ORS only ever inspects `k ± 1`, so a global re-ordering
barely changes what it can reach, whereas our method propagates evidence across the
*entire* table and is therefore acutely sensitive to whether that order is physically
correct.
