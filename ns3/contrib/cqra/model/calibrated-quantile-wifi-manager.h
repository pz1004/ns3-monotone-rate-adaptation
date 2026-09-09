/*
 * Calibrated-Quantile Rate adaptation (CQR).
 *
 * DERIVED FROM ns-3's ThompsonSamplingWifiManager
 *   Copyright (c) 2021 IITP RAS, Author: Alexander Krotov <krotov@iitp.ru>
 *   SPDX-License-Identifier: GPL-2.0-only
 *
 * Modifications for ICC 2027 submission:
 *   - Mode=Thompson reproduces the upstream algorithm EXACTLY (validation gate).
 *   - Mode=Quantile replaces the Beta *sample* with a controlled Beta *quantile*,
 *     whose level is driven online to hit a target frame-failure rate.
 *   - Optional per-decision logging for offline analysis.
 */

#ifndef CQR_WIFI_MANAGER_H
#define CQR_WIFI_MANAGER_H

#include "ns3/random-variable-stream.h"
#include "ns3/traced-value.h"
#include "ns3/wifi-remote-station-manager.h"

#include <fstream>
#include <string>
#include <vector>

namespace ns3
{

/**
 * @brief Thompson Sampling rate control algorithm
 * @ingroup wifi
 *
 * This class implements Thompson Sampling rate control algorithm.
 *
 * It was implemented for use as a baseline in
 * https://doi.org/10.1109/ACCESS.2020.3023552
 */
class CqrWifiManager : public WifiRemoteStationManager
{
  public:
    /**
     * @brief Get the type ID.
     * @return the object TypeId
     */
    static TypeId GetTypeId();
    CqrWifiManager();
    ~CqrWifiManager() override;

    int64_t AssignStreams(int64_t stream) override;

    /// Selection rule.
    enum SelectionMode
    {
        CQR_THOMPSON = 0, //!< exact upstream ThompsonSampling behaviour (validation gate)
        CQR_QUANTILE = 1  //!< calibrated Beta-quantile selection (proposed)
    };

    /// How the quantile level is driven.
    enum CalibMode
    {
        CQR_TARGET_FER = 0, //!< drive the realised FER toward TargetFer (absolute target)
        CQR_SELF_CAL = 1    //!< drive the predicted success prob toward the observed one
    };

    /// Whether to propagate evidence across rates using monotone structure.
    enum StructureMode
    {
        CQR_NO_STRUCTURE = 0, //!< independent Beta posterior per rate (upstream)
        CQR_MONOTONE = 1      //!< share evidence along the rate order
    };

    /// Which quantity the monotone propagation is ordered along.
    enum OrderMode
    {
        CQR_ORDER_REQ_SNR = 0,  //!< required SNR: the physically monotone quantity
        CQR_ORDER_DATA_RATE = 1 //!< achievable data rate: coincides only if the table is 1-D
    };

    /// Whether the forgetting rate is fixed or driven online.
    enum DecayMode
    {
        CQR_DECAY_FIXED = 0,   //!< use the Decay attribute unchanged (upstream behaviour)
        CQR_DECAY_ADAPT = 1    //!< drive Decay from excess prediction error (drift signal)
    };

    /// Which report callbacks contribute to the outcome signal.
    enum FerSource
    {
        CQR_AMPDU_ONLY = 0, //!< A-MPDU BlockAck counts only (semantically consistent)
        CQR_ALL_REPORTS = 1 //!< also per-attempt dataOk/dataFailed (kept for ablation)
    };

  private:
    WifiRemoteStation* DoCreateStation() const override;
    void DoReportRxOk(WifiRemoteStation* station, double rxSnr, WifiMode txMode) override;
    void DoReportRtsFailed(WifiRemoteStation* station) override;
    void DoReportDataFailed(WifiRemoteStation* station) override;
    void DoReportRtsOk(WifiRemoteStation* station,
                       double ctsSnr,
                       WifiMode ctsMode,
                       double rtsSnr) override;
    void DoReportDataOk(WifiRemoteStation* station,
                        double ackSnr,
                        WifiMode ackMode,
                        double dataSnr,
                        MHz_u dataChannelWidth,
                        uint8_t dataNss) override;
    void DoReportAmpduTxStatus(WifiRemoteStation* station,
                               uint16_t nSuccessfulMpdus,
                               uint16_t nFailedMpdus,
                               double rxSnr,
                               double dataSnr,
                               MHz_u dataChannelWidth,
                               uint8_t dataNss) override;
    void DoReportFinalRtsFailed(WifiRemoteStation* station) override;
    void DoReportFinalDataFailed(WifiRemoteStation* station) override;
    WifiTxVector DoGetDataTxVector(WifiRemoteStation* station, MHz_u allowedWidth) override;
    WifiTxVector DoGetRtsTxVector(WifiRemoteStation* station) override;

    /**
     * Initializes station rate tables. If station is already initialized,
     * nothing is done.
     *
     * @param station Station which should be initialized.
     */
    void InitializeStation(WifiRemoteStation* station) const;

    /**
     * Draws a new MCS and related parameters to try next time for this
     * station.
     *
     * This method should only be called between TXOPs to avoid sending
     * multiple frames using different modes. Otherwise it is impossible
     * to tell which mode was used for succeeded/failed frame when
     * feedback is received.
     *
     * @param station Station for which a new mode should be drawn.
     */
    void UpdateNextMode(WifiRemoteStation* station) const;

    /**
     * Applies exponential decay to MCS statistics.
     *
     * @param st Remote STA for which MCS statistics is to be updated.
     * @param i MCS index.
     */
    void Decay(WifiRemoteStation* st, size_t i) const;

    /**
     * Returns guard interval for the given mode.
     *
     * @param st Remote STA
     * @param mode The WifiMode
     * @return the guard interval
     */
    Time GetModeGuardInterval(WifiRemoteStation* st, WifiMode mode) const;

    /**
     * Sample beta random variable with given parameters
     * @param alpha first parameter of beta distribution
     * @param beta second parameter of beta distribution
     * @return beta random variable sample
     */
    double SampleBetaVariable(uint64_t alpha, uint64_t beta) const;

    /**
     * Quantile of a Beta(alpha, beta) distribution, via a moment-matched normal
     * approximation. Deterministic: unlike a Thompson draw it consumes no randomness.
     * @param alpha first Beta parameter
     * @param beta second Beta parameter
     * @param q quantile level in (0,1)
     * @return the approximate quantile, clipped to [0,1]
     */
    static double BetaQuantile(double alpha, double beta, double q);

    /**
     * Inverse standard normal CDF (Acklam's rational approximation).
     * @param p probability in (0,1)
     * @return z such that Phi(z) = p
     */
    static double NormalQuantile(double p);

    /**
     * Drive the quantile level toward the target frame-error rate.
     * @param st remote station
     * @param nSucc successful MPDUs observed
     * @param nFail failed MPDUs observed
     */
    /**
     * Propagate an observation across rates using the monotonicity of success
     * probability in the achievable data rate: a failure at rate r is evidence against
     * every harder rate, and a success at rate r is evidence for every easier rate.
     * @param st remote station
     * @param idx the rate the observation was made on
     * @param nSucc successful MPDUs
     * @param nFail failed MPDUs
     */
    void PropagateMonotone(WifiRemoteStation* st,
                           size_t idx,
                           uint32_t nSucc,
                           uint32_t nFail) const;

    /**
     * Build the ordering used by PropagateMonotone.
     *
     * Ordered by **required SNR**, not by achievable data rate. Monotonicity of success
     * probability holds in required SNR: if the channel cannot sustain a rate needing
     * X dB, it cannot sustain any rate needing more than X dB. Ordering by data rate is
     * only equivalent within a fixed (width, Nss) group -- across groups the two orders
     * diverge (a high-MCS/20 MHz rate and a low-MCS/80 MHz rate can carry similar bit
     * rates while requiring very different SNR), which injects false evidence and was
     * measured to make the gain SHRINK as the rate table grew (r = -0.748).
     */
    void BuildRateOrder(WifiRemoteStation* st) const;

    /**
     * Drive the per-station forgetting rate from the drift signal.
     *
     * A stale posterior systematically mis-predicts the arm it plays, so |observed −
     * predicted| on the played arm is observable on-policy (unlike a cross-arm selection
     * error). Binomial sampling noise is subtracted first, so only the EXCESS error --
     * the part attributable to drift rather than to a finite batch -- moves the rate.
     */
    void UpdateDecay(WifiRemoteStation* st, uint32_t nSucc, uint32_t nFail) const;

    void UpdateQuantile(WifiRemoteStation* st,
                        uint32_t nSucc,
                        uint32_t nFail,
                        bool fromAmpdu) const;

    /// Append one record to the decision log (no-op unless m_logFile is set).
    void LogRecord(const std::string& line) const;

    /**
     * Render the rate-table entry at @p idx as "mcs,width,nss" for the decision log.
     * The internal index enumerates (mode x width x nss), so it is NOT an MCS value.
     */
    std::string DescribeRate(WifiRemoteStation* st, size_t idx) const;

    Ptr<GammaRandomVariable>
        m_gammaRandomVariable; //!< Variable used to sample beta-distributed random variables

    /// Per-arm draw for CQR_QUANTILE. Created LAZILY on first use: constructing a
    /// RandomVariableStream consumes a global stream index, so eagerly creating it would
    /// shift every other RNG consumer in the simulation (including the fading model) and
    /// silently invalidate the Mode=Thompson equivalence gate.
    mutable Ptr<UniformRandomVariable> m_uniformRandomVariable;

    double m_decay; //!< Exponential decay coefficient, Hz

    SelectionMode m_mode;   //!< which selection rule to use
    double m_targetFer;     //!< target frame error rate the quantile is calibrated to
    double m_eta;           //!< step size of the quantile recursion
    double m_qMin;          //!< lower clip for the quantile level
    double m_qMax;          //!< upper clip for the quantile level
    double m_q0;            //!< initial quantile level
    CalibMode m_calib;      //!< which calibration law drives the quantile level
    FerSource m_ferSource;  //!< which reports feed the outcome signal
    StructureMode m_structure; //!< whether to share evidence across rates
    DecayMode m_decayMode;     //!< fixed or adaptive forgetting rate
    double m_decayEta;         //!< step size of the (log-scale) decay recursion
    double m_decayTarget;      //!< target excess prediction error
    double m_decayMin;         //!< clip
    double m_decayMax;         //!< clip
    double m_errBeta;          //!< EWMA coefficient for the error estimate
    double m_structWeight;     //!< weight applied to propagated (inferred) evidence
    double m_ber;              //!< target BER used to derive the required-SNR ordering
    OrderMode m_order;         //!< quantity the propagation order is built from

    std::string m_logFile;                  //!< decision-log path; empty disables logging
    uint32_t m_instanceId;                  //!< disambiguates the per-instance log file
    static uint32_t s_instanceCounter;      //!< running count of manager instances
    mutable std::vector<std::string> m_log; //!< buffered decision log

    TracedValue<uint64_t> m_currentRate; //!< Trace rate changes
};

} // namespace ns3

#endif /* CQR_WIFI_MANAGER_H */
