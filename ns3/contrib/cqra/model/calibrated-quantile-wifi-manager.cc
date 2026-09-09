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

#include "calibrated-quantile-wifi-manager.h"

#include "ns3/core-module.h"
#include "ns3/double.h"
#include "ns3/log.h"
#include "ns3/wifi-phy.h"
#include "ns3/simulator.h"
#include "ns3/string.h"
#include "ns3/enum.h"

#include <cmath>
#include <algorithm>
#include <utility>
#include <limits>
#include "ns3/packet.h"
#include "ns3/wifi-phy.h"

#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

namespace ns3
{

/**
 * A structure containing parameters of a single rate and its
 * statistics.
 */
struct RateStats
{
    WifiMode mode;      ///< MCS
    MHz_u channelWidth; ///< channel width
    uint8_t nss;        ///< Number of spatial streams

    double success{0.0}; ///< averaged number of successful transmissions
    double fails{0.0};   ///< averaged number of failed transmissions
    Time lastDecay{0};   ///< last time exponential decay was applied to this rate
};

/**
 * Holds station state and collected statistics.
 *
 * This struct extends from WifiRemoteStation to hold additional
 * information required by CqrWifiManager.
 */
struct CqrWifiRemoteStation : public WifiRemoteStation
{
    size_t m_nextMode; //!< Mode to select for the next transmission
    size_t m_lastMode; //!< Most recently used mode, used to write statistics
    double m_q;        //!< current calibrated quantile level (CQR_QUANTILE mode only)
    double m_predSucc; //!< success prob predicted for m_nextMode when it was chosen
    double m_predMean; //!< posterior MEAN for m_nextMode at selection time (drift signal)
    double m_decayCur; //!< current per-station forgetting rate
    double m_errEwma;  //!< EWMA of excess prediction error
    std::vector<size_t> m_rateRank; //!< rank of each rate index in ascending data-rate order

    std::vector<RateStats> m_mcsStats; //!< Collected statistics
};

NS_OBJECT_ENSURE_REGISTERED(CqrWifiManager);

uint32_t CqrWifiManager::s_instanceCounter = 0;

NS_LOG_COMPONENT_DEFINE("CqrWifiManager");

TypeId
CqrWifiManager::GetTypeId()
{
    static TypeId tid =
        TypeId("ns3::CqrWifiManager")
            .SetParent<WifiRemoteStationManager>()
            .SetGroupName("Wifi")
            .AddConstructor<CqrWifiManager>()
            .AddAttribute(
                "Decay",
                "Exponential decay coefficient, Hz; zero is a valid value for static scenarios",
                DoubleValue(1.0),
                MakeDoubleAccessor(&CqrWifiManager::m_decay),
                MakeDoubleChecker<double>(0.0))
            .AddAttribute("Mode",
                          "Selection rule: Thompson reproduces upstream exactly; "
                          "Quantile uses the calibrated Beta-quantile rule.",
                          EnumValue(CqrWifiManager::CQR_THOMPSON),
                          MakeEnumAccessor<CqrWifiManager::SelectionMode>(&CqrWifiManager::m_mode),
                          MakeEnumChecker(CqrWifiManager::CQR_THOMPSON, "Thompson",
                                          CqrWifiManager::CQR_QUANTILE, "Quantile"))
            .AddAttribute("TargetFer",
                          "Target frame error rate the quantile level is calibrated to.",
                          DoubleValue(0.10),
                          MakeDoubleAccessor(&CqrWifiManager::m_targetFer),
                          MakeDoubleChecker<double>(0.0, 1.0))
            .AddAttribute("Eta",
                          "Step size of the quantile calibration recursion.",
                          DoubleValue(0.02),
                          MakeDoubleAccessor(&CqrWifiManager::m_eta),
                          MakeDoubleChecker<double>(0.0))
            .AddAttribute("QMin", "Lower clip for the quantile level.",
                          DoubleValue(0.05),
                          MakeDoubleAccessor(&CqrWifiManager::m_qMin),
                          MakeDoubleChecker<double>(0.0, 1.0))
            .AddAttribute("QMax", "Upper clip for the quantile level.",
                          DoubleValue(0.95),
                          MakeDoubleAccessor(&CqrWifiManager::m_qMax),
                          MakeDoubleChecker<double>(0.0, 1.0))
            .AddAttribute("Q0", "Initial quantile level.",
                          DoubleValue(0.5),
                          MakeDoubleAccessor(&CqrWifiManager::m_q0),
                          MakeDoubleChecker<double>(0.0, 1.0))
            .AddAttribute("Calib",
                          "Calibration law: TargetFer drives the realised FER to a fixed "
                          "target; SelfCal drives the predicted success probability to the "
                          "observed one (no absolute target, so it stays feasible when the "
                          "channel cannot support the target).",
                          EnumValue(CqrWifiManager::CQR_SELF_CAL),
                          MakeEnumAccessor<CqrWifiManager::CalibMode>(&CqrWifiManager::m_calib),
                          MakeEnumChecker(CqrWifiManager::CQR_TARGET_FER, "TargetFer",
                                          CqrWifiManager::CQR_SELF_CAL, "SelfCal"))
            .AddAttribute("FerSource",
                          "Which reports feed the outcome signal. AmpduOnly uses BlockAck "
                          "counts, which are true per-MPDU outcomes. All also folds in the "
                          "per-attempt dataOk/dataFailed callbacks, which are pathological "
                          "under aggregation (successes are absorbed into A-MPDUs) and are "
                          "retained only for ablation.",
                          EnumValue(CqrWifiManager::CQR_AMPDU_ONLY),
                          MakeEnumAccessor<CqrWifiManager::FerSource>(&CqrWifiManager::m_ferSource),
                          MakeEnumChecker(CqrWifiManager::CQR_AMPDU_ONLY, "AmpduOnly",
                                          CqrWifiManager::CQR_ALL_REPORTS, "All"))
            .AddAttribute("Structure",
                          "Monotone shares each observation along the rate order: a "
                          "failure at rate r is evidence against every harder rate, a "
                          "success is evidence for every easier one. This is the only "
                          "signal in the model that is informative about rates that were "
                          "NOT played, which is what an independent Beta-per-rate "
                          "posterior structurally discards.",
                          EnumValue(CqrWifiManager::CQR_NO_STRUCTURE),
                          MakeEnumAccessor<CqrWifiManager::StructureMode>(&CqrWifiManager::m_structure),
                          MakeEnumChecker(CqrWifiManager::CQR_NO_STRUCTURE, "None",
                                          CqrWifiManager::CQR_MONOTONE, "Monotone"))
            .AddAttribute("StructureWeight",
                          "Weight on propagated (inferred, not observed) evidence.",
                          DoubleValue(0.5),
                          MakeDoubleAccessor(&CqrWifiManager::m_structWeight),
                          MakeDoubleChecker<double>(0.0, 1.0))
            .AddAttribute("BerThreshold",
                          "Target BER used to derive the required-SNR ordering for "
                          "monotone propagation. Matches IdealWifiManager's default so "
                          "the ordering is derived the same way the genie derives its "
                          "own rate thresholds.",
                          DoubleValue(1e-6),
                          MakeDoubleAccessor(&CqrWifiManager::m_ber),
                          MakeDoubleChecker<double>(0.0, 1.0))
            .AddAttribute("Order",
                          "Quantity the monotone propagation is ordered along. "
                          "RequiredSnr is the physically monotone one: a rate needing "
                          "more SNR than one that just failed would also have failed. "
                          "DataRate coincides with it only when the table is "
                          "one-dimensional, and is retained as the negative control.",
                          EnumValue(CqrWifiManager::CQR_ORDER_REQ_SNR),
                          MakeEnumAccessor<CqrWifiManager::OrderMode>(&CqrWifiManager::m_order),
                          MakeEnumChecker(CqrWifiManager::CQR_ORDER_REQ_SNR, "RequiredSnr",
                                          CqrWifiManager::CQR_ORDER_DATA_RATE, "DataRate"))
            .AddAttribute("DecayAdapt",
                          "Fixed uses the Decay attribute unchanged; Adaptive drives it "
                          "from the excess prediction error on the played arm.",
                          EnumValue(CqrWifiManager::CQR_DECAY_FIXED),
                          MakeEnumAccessor<CqrWifiManager::DecayMode>(&CqrWifiManager::m_decayMode),
                          MakeEnumChecker(CqrWifiManager::CQR_DECAY_FIXED, "Fixed",
                                          CqrWifiManager::CQR_DECAY_ADAPT, "Adaptive"))
            .AddAttribute("DecayEta", "Step size of the log-scale decay recursion.",
                          DoubleValue(0.05),
                          MakeDoubleAccessor(&CqrWifiManager::m_decayEta),
                          MakeDoubleChecker<double>(0.0))
            .AddAttribute("DecayTarget", "Target excess prediction error.",
                          DoubleValue(0.05),
                          MakeDoubleAccessor(&CqrWifiManager::m_decayTarget),
                          MakeDoubleChecker<double>(0.0, 1.0))
            .AddAttribute("DecayMin", "Lower clip on the forgetting rate (Hz).",
                          DoubleValue(0.5),
                          MakeDoubleAccessor(&CqrWifiManager::m_decayMin),
                          MakeDoubleChecker<double>(0.0))
            .AddAttribute("DecayMax", "Upper clip on the forgetting rate (Hz).",
                          DoubleValue(100.0),
                          MakeDoubleAccessor(&CqrWifiManager::m_decayMax),
                          MakeDoubleChecker<double>(0.0))
            .AddAttribute("ErrBeta", "EWMA coefficient for the excess-error estimate.",
                          DoubleValue(0.05),
                          MakeDoubleAccessor(&CqrWifiManager::m_errBeta),
                          MakeDoubleChecker<double>(0.0, 1.0))
            .AddAttribute("LogFile",
                          "If non-empty, write a per-decision CSV log to this path.",
                          StringValue(""),
                          MakeStringAccessor(&CqrWifiManager::m_logFile),
                          MakeStringChecker())
            .AddTraceSource("Rate",
                            "Traced value for rate changes (b/s)",
                            MakeTraceSourceAccessor(&CqrWifiManager::m_currentRate),
                            "ns3::TracedValueCallback::Uint64");
    return tid;
}

CqrWifiManager::CqrWifiManager()
    : m_instanceId(s_instanceCounter++),
      m_currentRate{0}
{
    NS_LOG_FUNCTION(this);

    m_gammaRandomVariable = CreateObject<GammaRandomVariable>();
}

CqrWifiManager::~CqrWifiManager()
{
    NS_LOG_FUNCTION(this);
    if (!m_logFile.empty() && !m_log.empty())
    {
        std::ofstream f(m_logFile + "." + std::to_string(m_instanceId));
        f << "time_s,kind,mcs,width_mhz,nss,n_succ,n_fail,data_snr_linear,q\n";
        for (const auto& l : m_log)
        {
            f << l << "\n";
        }
        f.close();
    }
}

WifiRemoteStation*
CqrWifiManager::DoCreateStation() const
{
    NS_LOG_FUNCTION(this);
    auto station = new CqrWifiRemoteStation();
    station->m_nextMode = 0;
    station->m_lastMode = 0;
    station->m_q = m_q0;
    station->m_predSucc = -1.0;
    station->m_predMean = -1.0;
    station->m_decayCur = m_decay;
    station->m_errEwma = 0.0;
    return station;
}

void
CqrWifiManager::InitializeStation(WifiRemoteStation* st) const
{
    auto station = static_cast<CqrWifiRemoteStation*>(st);
    if (!station->m_mcsStats.empty())
    {
        return;
    }

    // Add HT, VHT or HE MCSes
    for (const auto& mode : GetPhy()->GetMcsList())
    {
        for (MHz_u j{20}; j <= GetPhy()->GetChannelWidth(); j *= 2)
        {
            WifiModulationClass modulationClass = WIFI_MOD_CLASS_HT;
            if (GetVhtSupported())
            {
                modulationClass = WIFI_MOD_CLASS_VHT;
            }
            if (GetHeSupported())
            {
                modulationClass = WIFI_MOD_CLASS_HE;
            }
            if (mode.GetModulationClass() == modulationClass)
            {
                for (uint8_t k = 1; k <= GetPhy()->GetMaxSupportedTxSpatialStreams(); k++)
                {
                    if (mode.IsAllowed(j, k))
                    {
                        RateStats stats;
                        stats.mode = mode;
                        stats.channelWidth = j;
                        stats.nss = k;

                        station->m_mcsStats.push_back(stats);
                    }
                }
            }
        }
    }

    if (station->m_mcsStats.empty())
    {
        // Add legacy non-HT modes.
        for (uint8_t i = 0; i < GetNSupported(station); i++)
        {
            RateStats stats;
            stats.mode = GetSupported(station, i);
            if (stats.mode.GetModulationClass() == WIFI_MOD_CLASS_DSSS ||
                stats.mode.GetModulationClass() == WIFI_MOD_CLASS_HR_DSSS)
            {
                stats.channelWidth = MHz_u{22};
            }
            else
            {
                stats.channelWidth = MHz_u{20};
            }
            stats.nss = 1;
            station->m_mcsStats.push_back(stats);
        }
    }

    NS_ASSERT_MSG(!station->m_mcsStats.empty(), "No usable MCS found");

    UpdateNextMode(st);
}

void
CqrWifiManager::DoReportRxOk(WifiRemoteStation* station, double rxSnr, WifiMode txMode)
{
    NS_LOG_FUNCTION(this << station << rxSnr << txMode);
}

void
CqrWifiManager::DoReportRtsFailed(WifiRemoteStation* station)
{
    NS_LOG_FUNCTION(this << station);
}

void
CqrWifiManager::DoReportDataFailed(WifiRemoteStation* st)
{
    NS_LOG_FUNCTION(this << st);
    InitializeStation(st);
    auto station = static_cast<CqrWifiRemoteStation*>(st);
    Decay(st, station->m_lastMode);
    station->m_mcsStats.at(station->m_lastMode).fails++;
    UpdateDecay(st, 0, 1);
    PropagateMonotone(st, station->m_lastMode, 0, 1);
    UpdateQuantile(st, 0, 1, false);
    LogRecord(std::to_string(Simulator::Now().GetSeconds()) + ",dataFail," +
              DescribeRate(st, station->m_lastMode) + ",0,1,nan," +
              std::to_string(station->m_q));
    UpdateNextMode(st);
}

void
CqrWifiManager::DoReportRtsOk(WifiRemoteStation* st,
                                           double ctsSnr,
                                           WifiMode ctsMode,
                                           double rtsSnr)
{
    NS_LOG_FUNCTION(this << st << ctsSnr << ctsMode.GetUniqueName() << rtsSnr);
}

void
CqrWifiManager::UpdateNextMode(WifiRemoteStation* st) const
{
    InitializeStation(st);
    auto station = static_cast<CqrWifiRemoteStation*>(st);

    double maxThroughput = 0.0;
    double frameSuccessRate = 1.0;

    NS_ASSERT(!station->m_mcsStats.empty());

    // Use the most robust MCS if frameSuccessRate is 0 for all MCS.
    station->m_nextMode = 0;

    for (uint32_t i = 0; i < station->m_mcsStats.size(); i++)
    {
        Decay(st, i);
        const auto mode{station->m_mcsStats.at(i).mode};

        const auto guardInterval = GetModeGuardInterval(st, mode);
        const auto rate = mode.GetDataRate(station->m_mcsStats.at(i).channelWidth,
                                           guardInterval,
                                           station->m_mcsStats.at(i).nss);

        // Selection rule. CQR_THOMPSON is the upstream path and must stay byte-identical:
        // it is the validation gate, and it is the only branch that consumes randomness.
        if (m_mode == CQR_THOMPSON)
        {
            frameSuccessRate = SampleBetaVariable(1.0 + station->m_mcsStats.at(i).success,
                                                  1.0 + station->m_mcsStats.at(i).fails);
        }
        else
        {
            // Calibrated-shift Thompson sampling.
            //
            // A purely DETERMINISTIC quantile is degenerate here: under fast decay every
            // arm's posterior reverts toward Beta(1,1), so all arms receive the same
            // multiplier and the score collapses to `rate`, locking the policy onto the
            // highest rate (measured: 68.8% of transmissions at MCS9 versus a genie
            // spread over MCS2-4, with +262% retry overhead). Upstream avoids this only
            // because an independent random draw per arm breaks the tie.
            //
            // So we keep the per-arm randomisation and instead *shift the sampling
            // quantile* by the calibrated level. At q = 0.5 this is inverse-CDF sampling
            // of the same posterior, i.e. Thompson sampling; q > 0.5 is systematically
            // optimistic, q < 0.5 systematically pessimistic. The baseline is therefore a
            // special case of the proposed rule.
            if (!m_uniformRandomVariable)
            {
                m_uniformRandomVariable = CreateObject<UniformRandomVariable>();
            }
            const double u = m_uniformRandomVariable->GetValue(0.0, 1.0);
            const double shifted = std::min(0.999, std::max(0.001, u + (station->m_q - 0.5)));
            frameSuccessRate = BetaQuantile(1.0 + station->m_mcsStats.at(i).success,
                                            1.0 + station->m_mcsStats.at(i).fails,
                                            shifted);
        }
        NS_LOG_DEBUG("Draw success=" << station->m_mcsStats.at(i).success
                                     << " fails=" << station->m_mcsStats.at(i).fails
                                     << " frameSuccessRate=" << frameSuccessRate
                                     << " mode=" << mode);
        if (frameSuccessRate * rate > maxThroughput)
        {
            maxThroughput = frameSuccessRate * rate;
            station->m_nextMode = i;
            station->m_predSucc = frameSuccessRate;
            {
                const double sc = station->m_mcsStats.at(i).success;
                const double fl = station->m_mcsStats.at(i).fails;
                station->m_predMean = (sc + fl) > 0.0 ? sc / (sc + fl) : -1.0;
            }
        }
    }
}

void
CqrWifiManager::DoReportDataOk(WifiRemoteStation* st,
                                            double ackSnr,
                                            WifiMode ackMode,
                                            double dataSnr,
                                            MHz_u dataChannelWidth,
                                            uint8_t dataNss)
{
    NS_LOG_FUNCTION(this << st << ackSnr << ackMode.GetUniqueName() << dataSnr);
    InitializeStation(st);
    auto station = static_cast<CqrWifiRemoteStation*>(st);
    Decay(st, station->m_lastMode);
    station->m_mcsStats.at(station->m_lastMode).success++;
    UpdateDecay(st, 1, 0);
    PropagateMonotone(st, station->m_lastMode, 1, 0);
    UpdateQuantile(st, 1, 0, false);
    LogRecord(std::to_string(Simulator::Now().GetSeconds()) + ",dataOk," +
              DescribeRate(st, station->m_lastMode) + ",1,0," +
              std::to_string(dataSnr) + "," + std::to_string(station->m_q));
    UpdateNextMode(st);
}

void
CqrWifiManager::DoReportAmpduTxStatus(WifiRemoteStation* st,
                                                   uint16_t nSuccessfulMpdus,
                                                   uint16_t nFailedMpdus,
                                                   double rxSnr,
                                                   double dataSnr,
                                                   MHz_u dataChannelWidth,
                                                   uint8_t dataNss)
{
    NS_LOG_FUNCTION(this << st << nSuccessfulMpdus << nFailedMpdus << rxSnr << dataSnr);
    InitializeStation(st);
    auto station = static_cast<CqrWifiRemoteStation*>(st);

    Decay(st, station->m_lastMode);
    station->m_mcsStats.at(station->m_lastMode).success += nSuccessfulMpdus;
    station->m_mcsStats.at(station->m_lastMode).fails += nFailedMpdus;

    UpdateDecay(st, nSuccessfulMpdus, nFailedMpdus);
    PropagateMonotone(st, station->m_lastMode, nSuccessfulMpdus, nFailedMpdus);
    UpdateQuantile(st, nSuccessfulMpdus, nFailedMpdus, true);
    LogRecord(std::to_string(Simulator::Now().GetSeconds()) + ",ampdu," +
              DescribeRate(st, station->m_lastMode) + "," +
              std::to_string(nSuccessfulMpdus) + "," + std::to_string(nFailedMpdus) + "," +
              std::to_string(dataSnr) + "," + std::to_string(station->m_q));
    UpdateNextMode(st);
}

void
CqrWifiManager::DoReportFinalRtsFailed(WifiRemoteStation* station)
{
    NS_LOG_FUNCTION(this << station);
}

void
CqrWifiManager::DoReportFinalDataFailed(WifiRemoteStation* station)
{
    NS_LOG_FUNCTION(this << station);
}

Time
CqrWifiManager::GetModeGuardInterval(WifiRemoteStation* st, WifiMode mode) const
{
    if (mode.GetModulationClass() == WIFI_MOD_CLASS_HE)
    {
        return std::max(GetGuardInterval(st), GetGuardInterval());
    }
    else if ((mode.GetModulationClass() == WIFI_MOD_CLASS_HT) ||
             (mode.GetModulationClass() == WIFI_MOD_CLASS_VHT))
    {
        auto useSgi = GetShortGuardIntervalSupported(st) && GetShortGuardIntervalSupported();
        return NanoSeconds(useSgi ? 400 : 800);
    }
    else
    {
        return NanoSeconds(800);
    }
}

WifiTxVector
CqrWifiManager::DoGetDataTxVector(WifiRemoteStation* st, MHz_u allowedWidth)
{
    NS_LOG_FUNCTION(this << st << allowedWidth);
    InitializeStation(st);
    auto station = static_cast<CqrWifiRemoteStation*>(st);

    auto& stats = station->m_mcsStats.at(station->m_nextMode);
    const auto mode = stats.mode;
    const auto channelWidth = std::min(stats.channelWidth, allowedWidth);
    const auto nss = stats.nss;
    const auto guardInterval = GetModeGuardInterval(st, mode);

    station->m_lastMode = station->m_nextMode;

    NS_LOG_DEBUG("Using mode=" << mode << " channelWidth=" << channelWidth << " nss=" << +nss
                               << " guardInterval=" << guardInterval);

    const auto rate = mode.GetDataRate(channelWidth, guardInterval, nss);
    if (m_currentRate != rate)
    {
        NS_LOG_DEBUG("New datarate: " << rate);
        m_currentRate = rate;
    }

    return WifiTxVector(
        mode,
        GetDefaultTxPowerLevel(),
        GetPreambleForTransmission(mode.GetModulationClass(), GetShortPreambleEnabled()),
        GetModeGuardInterval(st, mode),
        GetNumberOfAntennas(),
        nss,
        0, // NESS
        GetPhy()->GetTxBandwidth(mode, channelWidth),
        GetAggregation(station),
        false);
}

WifiTxVector
CqrWifiManager::DoGetRtsTxVector(WifiRemoteStation* st)
{
    NS_LOG_FUNCTION(this << st);
    InitializeStation(st);
    auto station = static_cast<CqrWifiRemoteStation*>(st);

    // Use the most robust MCS for the control channel.
    auto& stats = station->m_mcsStats.at(0);
    WifiMode mode = stats.mode;
    uint8_t nss = stats.nss;

    // Make sure control frames are sent using 1 spatial stream.
    NS_ASSERT(nss == 1);

    return WifiTxVector(
        mode,
        GetDefaultTxPowerLevel(),
        GetPreambleForTransmission(mode.GetModulationClass(), GetShortPreambleEnabled()),
        GetModeGuardInterval(st, mode),
        GetNumberOfAntennas(),
        nss,
        0, // NESS
        GetPhy()->GetTxBandwidth(mode, stats.channelWidth),
        GetAggregation(station),
        false);
}

double
CqrWifiManager::SampleBetaVariable(uint64_t alpha, uint64_t beta) const
{
    double X = m_gammaRandomVariable->GetValue(alpha, 1.0);
    double Y = m_gammaRandomVariable->GetValue(beta, 1.0);
    return X / (X + Y);
}

void
CqrWifiManager::Decay(WifiRemoteStation* st, size_t i) const
{
    NS_LOG_FUNCTION(this << st << i);
    InitializeStation(st);
    auto station = static_cast<CqrWifiRemoteStation*>(st);

    Time now = Simulator::Now();
    auto& stats = station->m_mcsStats.at(i);
    if (now > stats.lastDecay)
    {
        const double coefficient =
            std::exp(station->m_decayCur * (stats.lastDecay - now).GetSeconds());

        stats.success *= coefficient;
        stats.fails *= coefficient;
        stats.lastDecay = now;
    }
}

int64_t
CqrWifiManager::AssignStreams(int64_t stream)
{
    NS_LOG_FUNCTION(this << stream);
    m_gammaRandomVariable->SetStream(stream);
    return 1;
}

double
CqrWifiManager::NormalQuantile(double p)
{
    // Acklam's rational approximation to the inverse standard normal CDF.
    static const double a[6] = {-3.969683028665376e+01, 2.209460984245205e+02,
                                -2.759285104469687e+02, 1.383577518672690e+02,
                                -3.066479806614716e+01, 2.506628277459239e+00};
    static const double b[5] = {-5.447609879822406e+01, 1.615858368580409e+02,
                                -1.556989798598866e+02, 6.680131188771972e+01,
                                -1.328068155288572e+01};
    static const double c[6] = {-7.784894002430293e-03, -3.223964580411365e-01,
                                -2.400758277161838e+00, -2.549732539343734e+00,
                                4.374664141464968e+00, 2.938163982698783e+00};
    static const double d[4] = {7.784695709041462e-03, 3.224671290700398e-01,
                                2.445134137142996e+00, 3.754408661907416e+00};
    const double pl = 0.02425;
    if (p <= 0.0)
    {
        return -6.0;
    }
    if (p >= 1.0)
    {
        return 6.0;
    }
    if (p < pl)
    {
        const double q = std::sqrt(-2.0 * std::log(p));
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0);
    }
    if (p > 1.0 - pl)
    {
        const double q = std::sqrt(-2.0 * std::log(1.0 - p));
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0);
    }
    const double q = p - 0.5;
    const double r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0);
}

double
CqrWifiManager::BetaQuantile(double alpha, double beta, double q)
{
    const double n = alpha + beta;
    const double mean = alpha / n;
    const double var = (alpha * beta) / (n * n * (n + 1.0));
    const double v = mean + NormalQuantile(q) * std::sqrt(var);
    return std::min(1.0, std::max(0.0, v));
}

void
CqrWifiManager::UpdateQuantile(WifiRemoteStation* st,
                               uint32_t nSucc,
                               uint32_t nFail,
                               bool fromAmpdu) const
{
    if (m_mode != CQR_QUANTILE)
    {
        return;
    }
    // The per-attempt dataOk/dataFailed callbacks are not a usable outcome signal under
    // A-MPDU aggregation: successful MPDUs are reported through DoReportAmpduTxStatus, so
    // dataOk fires almost never while dataFailed fires per retry. Measured on the
    // unmodified baseline, that source alone implies FER 0.976-0.998 irrespective of
    // channel conditions, whereas the BlockAck counts give 0.081 (static) to 0.787
    // (20 m/s). Default therefore uses A-MPDU reports only.
    if (m_ferSource == CQR_AMPDU_ONLY && !fromAmpdu)
    {
        return;
    }
    const uint32_t n = nSucc + nFail;
    if (n == 0)
    {
        return;
    }
    auto station = static_cast<CqrWifiRemoteStation*>(st);
    const double observedSucc = static_cast<double>(nSucc) / n;

    double err;
    if (m_calib == CQR_TARGET_FER)
    {
        // Too many failures => be safer (lower quantile); too few => be bolder.
        err = m_targetFer - (1.0 - observedSucc);
    }
    else
    {
        // Self-calibration: make the quantile an honest predictor of success. If we
        // predicted more success than we observed we are over-optimistic, so lower the
        // quantile; if we under-predicted, raise it. This needs no absolute target, so it
        // stays well-posed when the channel cannot support one.
        if (station->m_predSucc < 0.0)
        {
            return; // nothing selected yet
        }
        err = observedSucc - station->m_predSucc;
    }
    station->m_q += m_eta * err;
    station->m_q = std::min(m_qMax, std::max(m_qMin, station->m_q));
}

void
CqrWifiManager::BuildRateOrder(WifiRemoteStation* st) const
{
    auto station = static_cast<CqrWifiRemoteStation*>(st);
    const size_t n = station->m_mcsStats.size();
    std::vector<std::pair<double, size_t>> bySnr;
    bySnr.reserve(n);
    for (size_t i = 0; i < n; ++i)
    {
        const auto& r = station->m_mcsStats.at(i);
        const auto guardInterval = GetModeGuardInterval(st, r.mode);
        if (m_order == CQR_ORDER_DATA_RATE)
        {
            // Negative control: order by what the rate delivers rather than by what it
            // costs. Identical code path otherwise, so the two differ in this key alone.
            bySnr.emplace_back(
                static_cast<double>(
                    r.mode.GetDataRate(r.channelWidth, guardInterval, r.nss)),
                i);
            continue;
        }
        WifiTxVector txVector;
        txVector.SetMode(r.mode);
        txVector.SetChannelWidth(r.channelWidth);
        txVector.SetNss(r.nss);
        txVector.SetGuardInterval(guardInterval);
        // Minimum SNR (linear W/W) required to hit m_ber for this configuration.
        double snr;
        if (txVector.IsValid(GetPhy()->GetPhyBand()))
        {
            snr = GetPhy()->CalculateSnr(txVector, m_ber);
        }
        else
        {
            // Unusable configuration: park it at the hard end so nothing propagates
            // "easier-rate" evidence to it.
            snr = std::numeric_limits<double>::max();
        }
        bySnr.emplace_back(snr, i);
    }
    std::sort(bySnr.begin(), bySnr.end());
    station->m_rateRank.assign(n, 0);
    for (size_t rank = 0; rank < n; ++rank)
    {
        station->m_rateRank[bySnr[rank].second] = rank;
    }
}

void
CqrWifiManager::PropagateMonotone(WifiRemoteStation* st,
                                  size_t idx,
                                  uint32_t nSucc,
                                  uint32_t nFail) const
{
    if (m_structure != CQR_MONOTONE || m_structWeight <= 0.0)
    {
        return;
    }
    auto station = static_cast<CqrWifiRemoteStation*>(st);
    if (station->m_rateRank.size() != station->m_mcsStats.size())
    {
        BuildRateOrder(st);
    }
    if (idx >= station->m_rateRank.size())
    {
        return;
    }
    const size_t r0 = station->m_rateRank[idx];
    for (size_t j = 0; j < station->m_mcsStats.size(); ++j)
    {
        if (j == idx)
        {
            continue;
        }
        const size_t rj = station->m_rateRank[j];
        // Decay the target before adding, so the inferred evidence carries the correct
        // timestamp and is discounted on the same schedule as observed evidence.
        if (rj > r0 && nFail > 0)
        {
            Decay(st, j);
            station->m_mcsStats.at(j).fails += m_structWeight * nFail;
        }
        else if (rj < r0 && nSucc > 0)
        {
            Decay(st, j);
            station->m_mcsStats.at(j).success += m_structWeight * nSucc;
        }
    }
}

std::string
CqrWifiManager::DescribeRate(WifiRemoteStation* st, size_t idx) const
{
    auto station = static_cast<CqrWifiRemoteStation*>(st);
    if (idx >= station->m_mcsStats.size())
    {
        return "nan,nan,nan";
    }
    const auto& r = station->m_mcsStats.at(idx);
    return std::to_string(r.mode.GetMcsValue()) + "," +
           std::to_string(static_cast<uint32_t>(r.channelWidth)) + "," +
           std::to_string(static_cast<uint32_t>(r.nss));
}

void
CqrWifiManager::UpdateDecay(WifiRemoteStation* st, uint32_t nSucc, uint32_t nFail) const
{
    if (m_decayMode != CQR_DECAY_ADAPT)
    {
        return;
    }
    const uint32_t n = nSucc + nFail;
    if (n == 0)
    {
        return;
    }
    auto station = static_cast<CqrWifiRemoteStation*>(st);
    if (station->m_predMean < 0.0)
    {
        return;
    }
    const double observed = static_cast<double>(nSucc) / n;
    const double p = station->m_predMean;
    // Expected |error| from a finite batch alone, so only drift moves the rate.
    const double noise = std::sqrt(std::max(1e-12, p * (1.0 - p) / n));
    const double excess = std::max(0.0, std::fabs(observed - p) - noise);
    station->m_errEwma = (1.0 - m_errBeta) * station->m_errEwma + m_errBeta * excess;
    // Multiplicative on a log scale: the useful range of Decay spans two decades.
    station->m_decayCur *= std::exp(m_decayEta * (station->m_errEwma - m_decayTarget));
    station->m_decayCur = std::min(m_decayMax, std::max(m_decayMin, station->m_decayCur));
}

void
CqrWifiManager::LogRecord(const std::string& line) const
{
    if (!m_logFile.empty())
    {
        m_log.push_back(line);
    }
}

} // namespace ns3
