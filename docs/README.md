# docs/

Two documents, both about how the evaluation was set up rather than what it found — the
findings are in the paper, and the numbers behind them are in `results/`.

### `protocol.md` — the pre-registered evaluation protocol

Frozen 2026-09-08 and version-tagged `protocol-v1` before the proposed method was tuned.
It fixes the hypotheses, the swept and fixed factors, the seed count, the statistical
tests, the generalisation splits, and a set of honesty guards.

**Sections 1–8 are byte-identical to the tagged revision.** The document's own closing
line says "do not edit the text above", so nothing in the frozen text has been rewritten
for release, tidied up, or brought into line with what the project later did. Read it that
way. Everything that changed after the freeze is recorded in `## Amendments`, appended
2026-09-10, which is the mechanism the preamble mandates.

Three things worth knowing before you open it:

- **§1 names the hypothesis as it stood on 2026-09-08, and that hypothesis was refuted.**
  The calibrated-quantile rule §1 names failed under §1's own refutation criterion and was
  replaced by monotone evidence propagation ordered by required SNR. Amendment A1 records
  the refutation, the reason, and what survived unchanged — the *form* of the claim and
  the statistics, which is why the pre-registration still constrains anything.
- **The amendments record the failures too**, not just the substitutions: an S2 split
  violation caught and redone (A3), two inputs below §4's seed floor (A4), a primary metric
  that had to change because the genie turned out not to be an upper bound (A5), three
  pre-committed secondary metrics that went unreported (A7), and one headline scaling
  result that is post-freeze and should be read as exploratory (A8).
- **§1 cites `docs/diagnostic_verdict.md`**, an internal working note that is not part of
  this release. Nothing is lost: the two numbers it supplied are quoted inline in §1
  itself (mean-MCS bias of −2.32 at 0 m/s and +1.75 at 20 m/s), and the diagnostic that
  produced them is `results/diag/bias10.parquet`, which is released — it is the data
  behind Table I and Fig. 1.

### `ors_baseline.md` — the reimplemented baselines

ORS, SW-ORS and KL-R-UCB are not shipped with ns-3; `ns3::OrsWifiManager` is our
implementation from the pseudocode in Combes et al., INFOCOM 2014. This note records what
was implemented, the fairness decisions taken when tuning it, and the tuning and held-out
results. Any defect in that implementation is ours, not the original authors'.

### What is not here

The project's internal working notes — session logs, go/no-go memos, and records of
hypotheses that were refuted along the way — are not part of this artifact. What survived
those decisions is in the paper; what the measurements actually returned is in `results/`,
and `reproduce.sh` regenerates it.
