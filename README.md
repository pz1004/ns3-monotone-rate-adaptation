# Monotone Evidence Sharing for Rate Adaptation in IEEE 802.11be

Artifact for the paper *Monotone Evidence Sharing for Rate Adaptation in IEEE 802.11be*
(Sooyoung Jang, Eunkyung Kim — Hanbat National University).

A rate-adaptation manager for ns-3 that, on every transmission outcome, propagates the
evidence to neighbouring rates **ordered by required SNR** rather than by data rate.
Nothing else changes: at propagation weight `w=0` the algorithm is byte-identical to
ns-3's stock `ThompsonSamplingWifiManager`, so any measured difference is attributable to
the ordering alone. The ordering is the contribution, and the data-rate ordering is
included as its negative control.

This repository contains the module, the scenario, the runners, the pre-registered
protocol, the raw per-run outputs of all 11,520 campaign simulations, and the scripts
that regenerate every number and figure in the paper from those outputs.

> **Paper:** submitted to IEEE ICC 2027, *SAC: Machine Learning for Communications and Networking*. Not yet peer-reviewed.
>
> **Cite:** see `CITATION.cff`.

---

## Layout

| Path | What it is |
|---|---|
| `ns3/contrib/cqra/` | The ns-3 contrib module: `CqrWifiManager` (the method) and `OrsWifiManager` (the ORS / SW-ORS / KL-R-UCB baselines). Self-contained — it needs no patch to ns-3's `src/`. |
| `ns3/scratch/eht-ra-gate1.cc` | The 802.11be scenario: 1 AP + N STAs, saturated downlink UDP, log-distance path loss with optional Jakes fading. |
| `runner/` | Parallel campaign drivers, plus `verify_equivalence.py` — the `w=0` equivalence gate. |
| `analysis/` | The campaign analyses, and the three generators that produce every table and figure in the paper. |
| `results/` | All released run outputs (~13 MB). `campaign/full.parquet` is the 11,520-run campaign. |
| `logs/` | The 19 run logs, each ending in the row count and destination of its campaign. |
| [`docs/protocol.md`](docs/protocol.md) | The evaluation protocol, frozen before the method was tuned. **Read [`docs/protocol.md`](docs/protocol.md) before the results.** |
| [`docs/ors_baseline.md`](docs/ors_baseline.md) | How the ORS family was reimplemented, and the fairness decisions taken. |
| `env/` | The pinned environment, and the sha256 of the ns-3 release used. |
| `reproduce.sh` | Every runner invocation, recovered and verified (see *Reproducing the runs*). |

### A note on names

The module is called `cqra` and its manager is `ns3::CqrWifiManager`, with flags
`--cqrMode`, `--cqrStructure`, `--cqrOrder` and so on. That name is a fossil: it stands
for *calibrated-quantile rate adaptation*, an earlier formulation that was refuted under
the pre-registered protocol's own criterion and replaced by the method this paper reports.
Amendment A1 in [`docs/protocol.md`](docs/protocol.md) records the refutation and the reason for it.

The names were kept because the released data depends on them: arm labels inside
`results/campaign/full.parquet`, and every invocation in `reproduce.sh`, encode these
flags. Renaming would have invalidated the data the paper reports against. Read the
mapping as:

| flag | what it selects |
|---|---|
| `--cqrStructure=Monotone --cqrOrder=RequiredSnr` | **the paper's method** — evidence propagated along the required-SNR order |
| `--cqrStructure=Monotone --cqrOrder=DataRate` | the negative control: same code, ordering by achievable data rate instead |
| `--cqrStructWeight=0` | propagation off; byte-identical to upstream `ThompsonSamplingWifiManager` |
| `--cqrMode=Quantile`, `--cqrTargetFer`, `--cqrEta`, `--cqrDecayAdapt` | the abandoned formulation and an unadopted ablation, retained so the negative results remain reproducible |

`ns3::OrsWifiManager` in the same module is unrelated to that history: it is our
reimplementation of the ORS / SW-ORS / KL-R-UCB baselines.

---

## Setup

ns-3 is **not** vendored here — it is freely available and pinned by hash.

```bash
git clone https://github.com/pz1004/ns3-monotone-rate-adaptation.git
cd ns3-monotone-rate-adaptation
conda env create -f environment.yml && conda activate icc2027

# 1. Fetch ns-3.48 and verify it is the release the paper used.
wget https://www.nsnam.org/releases/ns-allinone-3.48.tar.bz2
sha256sum -c env/tarball.sha256      # must print OK
tar xf ns-allinone-3.48.tar.bz2
export NS3_DIR=$PWD/ns-allinone-3.48/ns-3.48

# 2. Add the module and the scenario, then build.
cp -r ns3/contrib/cqra "$NS3_DIR/contrib/"
cp    ns3/scratch/eht-ra-gate1.cc "$NS3_DIR/scratch/"
cd "$NS3_DIR"
./ns3 configure --build-profile=optimized --enable-modules=wifi,applications,mobility,propagation
./ns3 build
```

`env/tarball.sha256` expects the filename `ns-3.48.tar.bz2`; adjust if you fetch the
`ns-allinone` bundle under a different name. Every runner reads `NS3_DIR` and prints
these instructions if the binary is missing.

---

## Verify the implementation before trusting any result

The paper's central methodological claim is that the manager is a faithful superset of
the stock one. Check it yourself:

```bash
python runner/verify_equivalence.py
```

This runs `ThompsonSampling` against `Cqr --cqrStructWeight=0.0` across 27 configurations
of forgetting rate × speed × seed and requires **exact** float equality, not closeness.
It must print `27/27 byte-identical`. Re-run it after any change to the module.

---

## Reproducing the tables and figures

The three generators read only `results/` and write to `out/`:

```bash
python analysis/make_numbers.py     # out/numbers.tex   -- every measured value in the prose
python analysis/make_figs.py        # out/f1..f3.png    -- run AFTER make_numbers.py
python analysis/make_percell.py     # out/percell.tex   -- the per-cell audit table
```

`make_figs.py` cross-checks each plotted quantity against `out/numbers.tex` and fails
rather than drawing a figure that disagrees with the prose, so the order matters.

| Paper artefact | Produced by | From |
|---|---|---|
| Table I — selection bias of discounted Thompson sampling | `make_numbers.py` | `results/diag/bias10.parquet` |
| Table II — scenario parameters | *(static)* | — |
| Table III — effect of the propagation ordering | `make_numbers.py` | `results/mono/order_matched.parquet` |
| Table IV — campaign result | `make_numbers.py` | `results/campaign/full.parquet` |
| Table V — held-out speeds, absolute throughput | `make_numbers.py` | `results/campaign/full.parquet`, `results/envelope/references.parquet` |
| Table VI — per-cell audit | `make_percell.py` | `results/campaign/full.parquet` |
| Fig. 1 — bias reverses at walking pace (`out/f1_bias.png`) | `make_figs.py` | `results/diag/bias10.parquet` |
| Fig. 3 — proposed vs the swept frontier (`out/f2_ordering.png`) | `make_figs.py` | `results/mono/{order_matched,frontier_test}.parquet` |
| Fig. 4 — mobility crossover (`out/f3_refs.png`) | `make_figs.py` | `results/threshold/sweep.parquet` |

(Fig. 2 in the paper is the algorithm diagram and has no data behind it, which is why the
generated filenames `f1`–`f3` run one behind the figure numbers from Fig. 3 onward.)

Standalone analyses, printing the pre-registered statistics to stdout:

```bash
python analysis/campaign.py         # per-cell dominance, paired tests, Holm correction
python analysis/threshold.py        # the speed above which not adapting wins
python analysis/decay_frontier.py   # does any single fixed forgetting rate win everywhere?
```

`results/campaign/analysis_output.txt` is the committed output of `analysis/campaign.py`,
so you can diff against it without re-running anything.

---

## Reproducing the runs

```bash
DRY_RUN=1 bash reproduce.sh          # print every grid size, run nothing
bash reproduce.sh campaign_full      # the 11,520-run campaign
bash reproduce.sh                    # everything (days of CPU time)
```

**On provenance, honestly:** the exact command lines were never recorded during the
project. The invocations in `reproduce.sh` were *recovered* from the released parquets —
each file encodes its own sweep grid in its factor columns — and each one was verified two
ways: the product of its factor levels equals the row count of the released file, and,
where a run log exists, the count that log recorded. All 29 agree. `DRY_RUN=1` reprints
those grid sizes so you can check the arithmetic before spending the CPU time.

Every released parquet is covered except `results/envelope/references.parquet`, which is
not a simulation output: it is derived from `envelope/const_sweep.parquet` by
`analysis/make_references.py`, and `--check` confirms the committed file matches.

Cost: the main campaign is 11,520 runs, 24 workers, zero failures — see `logs/campaign.log`.

---

## Pre-registration

[`docs/protocol.md`](docs/protocol.md) fixes the metrics, seed count, statistical tests and the
tune/evaluate splits. It was frozen and version-tagged before the method was tuned, and
the hyperparameter search that followed touched only the tuning split.

Sections 1–8 are reproduced **byte-identical to the tagged revision**: the document's own
closing line says "do not edit the text above", so nothing in it has been rewritten for
release or brought into line with what the project later did.

> **Read §1 with the `## Amendments` section, not on its own.** The protocol was frozen
> early, and the rule its hypothesis names was later refuted under the protocol's own
> refutation criterion and replaced. Eight dated amendments record that and every other
> post-freeze change, including an S2 split violation that was caught and redone, a change
> of primary metric, two inputs that fell below the seed floor and were re-run at 10 seeds, and which pre-committed secondary
> metrics went unreported.

---

## Licence

Code is **GPL-2.0-only** — the managers are derived from ns-3's
`ThompsonSamplingWifiManager` (© 2021 IITP RAS, Alexander Krotov). Data and documentation
are CC-BY-4.0. See `LICENSE` and `NOTICE`.
