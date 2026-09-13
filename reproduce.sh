#!/usr/bin/env bash
# Regenerate every released result file from scratch.
#
# These invocations were RECOVERED from the released parquets, not transcribed from a
# shell history -- the original commands were never recorded. Each one was verified by
# checking that the product of its factor levels equals the row count in the released
# file, and, where a run log exists, the count that log recorded. See README.md.
#
#   export NS3_DIR=/path/to/ns-3.48      # built per README.md
#   bash reproduce.sh                    # everything (days of CPU time)
#   bash reproduce.sh campaign_full      # just the main campaign
#   DRY_RUN=1 bash reproduce.sh          # print every grid size, run nothing
#
# Runs are written to results/, overwriting what is committed. Work on a copy if you
# want to diff against the released data.
set -euo pipefail
cd "$(dirname "$0")"
: "${NS3_DIR:?set NS3_DIR to your ns-3.48 build -- see README.md}"
WORKERS="${WORKERS:-$(( $(nproc) > 4 ? $(nproc) - 4 : 1 ))}"
only="${1:-}"
# Action set for the learning managers (protocol-v1 amendment A9.1). "Latest" enumerates
# EHT MCS 0-13 -- 84 configurations at 80 MHz / 2 streams -- which is the table
# IdealWifiManager, MinstrelHt and the ConstantRate references already use. Setting this to
# MatchUpstream reproduces the earlier HE-only (72-arm) enumeration instead.
MOD_FAMILY="${MOD_FAMILY:-Latest}"
run() {  # run <name> <script> <args...>
  local name=$1; shift
  if [[ -n "$only" && "$only" != "$name" ]]; then return 0; fi
  echo "=== $name"
  # Only the two managers we implement have an action set to choose; run_sweep.py drives
  # the stock wifi-manager-example, which does not take the flag.
  local mf=()
  case "$1" in run_ablation.py|run_gate1.py) mf=(--mod-family "$MOD_FAMILY") ;; esac
  python "runner/$1" "${@:2}" --workers "$WORKERS" "${mf[@]}" ${DRY_RUN:+--dry-run}
}


# THE MAIN CAMPAIGN. 11,520 runs; Table IV and the per-cell audit (Table VI).
#   11520 rows, recorded in logs/campaign.log
run campaign_full run_ablation.py \
  --nsta 1 4 8 \
  --speeds 0 1 2 5 10 20 \
  --channels logdistance logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 0 0.5 1 2 5 10 20 50 100 \
  --weights 0.25 \
  --const-mcs 0 1 2 3 4 5 6 7 8 9 10 11 12 13 \
  --minstrel-cols 2 5 10 20 \
  --ors KL-R-UCB:DataRate:1000 SW-ORS:DataRate:2000 SW-ORS:RequiredSnr:2000 \
  --out results/campaign/full.parquet

# Adaptive-forgetting ablation (tested, not adopted).
#   240 rows, recorded in logs/adaptdecay_tune.log
run adaptdecay_tune run_ablation.py \
  --nsta 4 \
  --speeds 0 2 10 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 2 \
  --weights 0.25 \
  --decay-targets 0.01 0.02 0.05 0.1 0.2 \
  --out results/adaptdecay/tune.parquet

# Selection-bias diagnostic. Table I, Fig. 1.
#   80 rows
run diag_bias10 run_ablation.py \
  --nsta 4 \
  --speeds 0 2 5 20 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 2 \
  --no-mono \
  --out results/diag/bias10.parquet

# Benefit vs configuration-space size (see protocol amendment A8).
#   360 rows, recorded in logs/configspace.log
run mono_configspace run_ablation.py \
  --nsta 4 \
  --speeds 2 5 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 20 40 80 \
  --nss 1 2 \
  --decay 2 \
  --weights 0.05 \
  --out results/mono/configspace.parquet

# Frontier the proposed configuration must clear. Fig. 3.
#   330 rows, recorded in logs/frontier_test.log
run mono_frontier_test run_ablation.py \
  --nsta 4 \
  --speeds 1 5 20 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 0 0.5 1 2 5 10 20 50 100 \
  --weights 0.25 \
  --out results/mono/frontier_test.parquet

# Benefit vs configuration-space size, required-SNR ordering.
#   360 rows, recorded in logs/h3_snr.log
run mono_h3_snr run_ablation.py \
  --nsta 4 \
  --speeds 5 20 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 20 40 80 \
  --nss 1 2 \
  --decay 2 \
  --ts-decays 2 \
  --weights 0.25 \
  --out results/mono/h3_snr.parquet

# Held-out speeds (protocol-v1 split S2).
#   90 rows, recorded in logs/heldout.log
run mono_heldout_S2 run_ablation.py \
  --nsta 4 \
  --speeds 1 5 20 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --weights 0.05 \
  --out results/mono/heldout_S2.parquet

# Held-out evaluation of the single selected configuration.
#   90 rows, recorded in logs/heldout_snr.log
run mono_heldout_snr run_ablation.py \
  --nsta 4 \
  --speeds 1 5 20 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --weights 0.25 \
  --out results/mono/heldout_snr.parquet

# Structure x forgetting rate, lambda=100.
#   60 rows
run mono_monodecay_100 run_ablation.py \
  --nsta 4 8 \
  --speeds 0 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 100 \
  --ts-decays 100 \
  --weights 0.25 \
  --out results/mono/monodecay_100.parquet

# Structure x forgetting rate, lambda=2.
#   60 rows
run mono_monodecay_2 run_ablation.py \
  --nsta 4 8 \
  --speeds 0 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 2 \
  --weights 0.25 \
  --out results/mono/monodecay_2.parquet

# Structure x forgetting rate, lambda=20.
#   60 rows
run mono_monodecay_20 run_ablation.py \
  --nsta 4 8 \
  --speeds 0 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 20 \
  --ts-decays 20 \
  --weights 0.25 \
  --out results/mono/monodecay_20.parquet

# Structure x forgetting rate, lambda=50.
#   60 rows
run mono_monodecay_50 run_ablation.py \
  --nsta 4 8 \
  --speeds 0 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 50 \
  --ts-decays 50 \
  --weights 0.25 \
  --out results/mono/monodecay_50.parquet

# Matched ordering ablation: required SNR vs data rate. Table III, Fig. 3.
#   600 rows, recorded in logs/order_matched.log
run mono_order_matched run_ablation.py \
  --nsta 4 \
  --speeds 5 20 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 20 40 80 \
  --nss 1 2 \
  --decay 2 \
  --ts-decays 2 \
  --weights 0.25 \
  --cqr-orders DataRate RequiredSnr RequiredSnrPower \
  --out results/mono/order_matched.parquet

# Generalisation splits S3 (STA count) and S4 (channel).
#   240 rows, recorded in logs/s3_s4.log
run mono_s3_s4 run_ablation.py \
  --nsta 1 8 \
  --speeds 5 20 \
  --channels logdistance logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 2 \
  --weights 0.25 \
  --out results/mono/s3_s4.parquet

# Weight sweep on the TUNING split (required-SNR ordering); selects w=0.25.
#   210 rows, recorded in logs/tune_snr.log
run mono_tune_snr run_ablation.py \
  --nsta 4 \
  --speeds 0 2 10 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --weights 0.02 0.05 0.1 0.25 0.5 \
  --out results/mono/tune_snr.parquet

# Weight sweep on the TUNING split (data-rate ordering).
#   180 rows, recorded in logs/tune_split.log
run mono_tune_split run_ablation.py \
  --nsta 4 \
  --speeds 0 2 10 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --weights 0.02 0.05 0.1 0.25 \
  --out results/mono/tune_split.parquet

# ORS family on the held-out speeds.
#   180 rows, recorded in logs/ors_heldout.log
run ors_heldout run_ablation.py \
  --nsta 4 \
  --speeds 1 5 20 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 2 \
  --weights 0.25 \
  --ors KL-R-UCB:DataRate:1000 SW-ORS:DataRate:2000 SW-ORS:RequiredSnr:2000 \
  --out results/ors/heldout.parquet

# ORS family: final tuning pass.
#   450 rows, recorded in logs/ors_tune3.log
run ors_tune3 run_ablation.py \
  --nsta 4 \
  --speeds 0 2 10 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 2 \
  --no-mono \
  --ors KL-R-UCB:DataRate:1000 ORS:DataRate:1000 ORS:RequiredSnr:1000 SW-ORS:DataRate:1000 SW-ORS:DataRate:200 SW-ORS:DataRate:2000 SW-ORS:DataRate:500 SW-ORS:DataRate:5000 SW-ORS:RequiredSnr:1000 SW-ORS:RequiredSnr:200 SW-ORS:RequiredSnr:2000 SW-ORS:RequiredSnr:500 SW-ORS:RequiredSnr:5000 \
  --out results/ors/tune3.parquet

# ORS family: sliding-window sweep.
#   270 rows, recorded in logs/ors_tune.log
run ors_tune_window run_ablation.py \
  --nsta 4 \
  --speeds 0 2 10 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 2 \
  --no-mono \
  --ors SW-ORS:DataRate:100 SW-ORS:DataRate:1000 SW-ORS:DataRate:20 SW-ORS:DataRate:200 SW-ORS:DataRate:2000 SW-ORS:DataRate:50 SW-ORS:DataRate:500 \
  --out results/ors/tune_window.parquet

# ORS family: window sweep, second pass.
#   360 rows, recorded in logs/ors_tune2.log
run ors_tune_window2 run_ablation.py \
  --nsta 4 \
  --speeds 0 2 10 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 2 \
  --no-mono \
  --ors KL-R-UCB:DataRate:200 ORS:DataRate:200 SW-ORS:DataRate:100 SW-ORS:DataRate:1000 SW-ORS:DataRate:20 SW-ORS:DataRate:200 SW-ORS:DataRate:2000 SW-ORS:DataRate:50 SW-ORS:DataRate:500 SW-ORS:DataRate:5000 \
  --out results/ors/tune_window2.parquet

# Mobility crossover: where not adapting wins. Fig. 4.
#   1530 rows, recorded in logs/threshold.log
run threshold_sweep run_ablation.py \
  --nsta 4 \
  --speeds 0 1 2 3 5 7 10 15 20 \
  --channels logdistance+jakes \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --widths 80 \
  --nss 2 \
  --decay 2 \
  --ts-decays 2 \
  --weights 0.25 \
  --const-mcs 0 1 2 3 4 5 6 7 8 9 10 11 12 13 \
  --out results/threshold/sweep.parquet

# ConstantRate sweep -> per-interval envelope references.
#   8550 rows, recorded in logs/envelope.log
run envelope_const_sweep run_gate1.py \
  --managers Ideal \
  --mcs-list 0 1 2 3 4 5 6 7 8 9 10 11 12 13 \
  --nsta 4 \
  --speeds 1 5 20 \
  --widths 80 \
  --nss 2 \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --channels logdistance+jakes \
  --sim-time 10 \
  --out results/envelope/const_sweep.parquet
#   4788 rows
run gate1_contention_speed run_gate1.py \
  --managers Ideal MinstrelHt ThompsonSampling \
  --mcs-list 0 2 4 6 7 8 9 10 11 12 13 \
  --nsta 1 4 8 \
  --speeds 0 10 \
  --widths 80 \
  --nss 2 \
  --seeds 1 2 3 \
  --channels logdistance \
  --out results/gate1/contention_speed.parquet

# Swept fixed-Decay frontier over speed and channel.
#   56160 rows, recorded in logs/decay_frontier.log
run gate1_decay_frontier run_gate1.py \
  --managers Ideal MinstrelHt ThompsonSampling \
  --mcs-list 9 \
  --nsta 4 \
  --speeds 0 1 2 5 10 20 \
  --widths 80 \
  --nss 2 \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --channels logdistance logdistance+jakes \
  --ts-decays 0 0.5 1 2 5 10 20 50 100 \
  --out results/gate1/decay_frontier.parquet
#   3978 rows
run gate1_eht_mobility run_gate1.py \
  --managers Ideal MinstrelHt ThompsonSampling \
  --mcs-list 0 1 2 3 4 5 6 7 8 9 10 11 12 13 \
  --nsta 1 \
  --speeds 0 2 \
  --widths 80 \
  --nss 2 \
  --seeds 1 2 3 \
  --channels logdistance \
  --out results/gate1/eht_mobility.parquet
#   17290 rows, recorded in logs/speed_fading.log
run gate1_speed_fading run_gate1.py \
  --managers Ideal MinstrelHt ThompsonSampling \
  --mcs-list 0 2 4 6 8 9 10 11 12 13 \
  --nsta 4 \
  --speeds 0 1 2 5 10 15 20 \
  --widths 80 \
  --nss 2 \
  --seeds 1 2 3 4 5 \
  --channels logdistance logdistance+jakes \
  --out results/gate1/speed_fading.parquet
#   8645 rows
run gate1_speed_sweep run_gate1.py \
  --managers Ideal MinstrelHt ThompsonSampling \
  --mcs-list 0 2 4 6 8 9 10 11 12 13 \
  --nsta 4 \
  --speeds 0 1 2 5 10 15 20 \
  --widths 80 \
  --nss 2 \
  --seeds 1 2 3 4 5 \
  --channels logdistance \
  --out results/gate1/speed_sweep.parquet

# Minstrel-HT starvation across standards (Sec. III).
#   60000 rows, recorded in logs/day3_validation.log
run day3_validation_mgr_sweep run_sweep.py \
  --managers Ideal MinstrelHt ThompsonSampling \
  --standards 802.11ac 802.11ax-5GHz 802.11be-5GHz 802.11n-5GHz \
  --widths 20 40 80 \
  --nss 1 2 \
  --gi 800 \
  --step-size 1 \
  --step-times 1 \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --out results/day3_validation/mgr_sweep.parquet

# Smoke test of the sweep harness.
#   204 rows
run smoke_tiny run_sweep.py \
  --managers Ideal MinstrelHt \
  --standards 802.11ax-5GHz \
  --widths 20 \
  --nss 1 \
  --gi 800 \
  --step-size 1 \
  --step-times 1 \
  --seeds 1 \
  --out results/smoke/tiny.parquet

# The propagated-evidence budget each ordering actually spends (protocol A9.16).
# Same grid as mono/order_matched.parquet, run once per ordering.
#   240 rows
if [[ -z "$only" || "$only" == budget ]]; then
  python runner/measure_budget.py --workers "$WORKERS" \
    --out results/mono/budget.parquet ${DRY_RUN:+--dry-run}
fi

# Derived from envelope/const_sweep.parquet, not from a simulation run.
if [[ -z "$only" || "$only" == references ]]; then python analysis/make_references.py; fi

echo "done"
