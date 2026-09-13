/*
 * ORS / SW-ORS / KL-R-UCB (Combes et al., INFOCOM 2014, arXiv:1307.7309).
 * SPDX-License-Identifier: GPL-2.0-only
 */
#include "ors-wifi-manager.h"

#include "ns3/double.h"
#include "ns3/enum.h"
#include "ns3/log.h"
#include "ns3/uinteger.h"
#include "ns3/wifi-phy.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <utility>

namespace ns3
{

NS_LOG_COMPONENT_DEFINE("OrsWifiManager");

/// One (mode, width, nss) rate together with its windowed statistics.
struct OrsRate
{
    WifiMode mode;
    MHz_u channelWidth;
    uint8_t nss;
    double rate{0.0};    ///< achievable data rate, b/s
    double succ{0.0};    ///< successes inside the window
    double fail{0.0};    ///< failures inside the window
    uint32_t leader{0};  ///< times this rate has been the leader, inside the window
};

/// One report, retained so it can be evicted from the sliding window.
struct OrsEvent
{
    size_t k;        ///< rate index the observation was made on
    double succ;
    double fail;
    size_t leaderIdx; ///< which rate was leader at that step
};

struct OrsWifiRemoteStation : public WifiRemoteStation
{
    std::vector<OrsRate> rates;   ///< rate table, sorted by the configured order
    std::deque<OrsEvent> window;  ///< retained reports (SW-ORS)
    size_t nextMode{0};
    size_t lastMode{0};
    uint64_t n{0};                ///< step counter
    bool init{false};
};

NS_OBJECT_ENSURE_REGISTERED(OrsWifiManager);

TypeId
OrsWifiManager::GetTypeId()
{
    static TypeId tid =
        TypeId("ns3::OrsWifiManager")
            .SetParent<WifiRemoteStationManager>()
            .SetGroupName("Wifi")
            .AddConstructor<OrsWifiManager>()
            .AddAttribute("Variant",
                          "ORS (Alg.1, stationary), SW-ORS (Alg.3, sliding window, the "
                          "paper's own non-stationary variant), or KL-R-UCB (Alg.2, the "
                          "unstructured control).",
                          EnumValue(OrsWifiManager::ORS_SLIDING),
                          MakeEnumAccessor<OrsWifiManager::Variant>(&OrsWifiManager::m_variant),
                          MakeEnumChecker(OrsWifiManager::ORS_STATIONARY, "ORS",
                                          OrsWifiManager::ORS_SLIDING, "SW-ORS",
                                          OrsWifiManager::ORS_KLRUCB, "KL-R-UCB"))
            .AddAttribute("Order",
                          "Ordering that defines the neighbourhood N(k). The paper orders "
                          "by data rate, which coincides with required SNR only within a "
                          "fixed (width, Nss) group.",
                          EnumValue(OrsWifiManager::ORS_BY_RATE),
                          MakeEnumAccessor<OrsWifiManager::Order>(&OrsWifiManager::m_order),
                          MakeEnumChecker(OrsWifiManager::ORS_BY_RATE, "DataRate",
                                          OrsWifiManager::ORS_BY_SNR, "RequiredSnr",
                                          OrsWifiManager::ORS_BY_SNR_POWER,
                                          "RequiredSnrPower"))
            .AddAttribute("ModulationFamily",
                          "Which modulation classes the rate table enumerates. "
                          "MatchUpstream stops at HE, as ns3::ThompsonSamplingWifiManager "
                          "does; Latest extends to EHT, matching IdealWifiManager.",
                          EnumValue(OrsWifiManager::ORS_MOD_MATCH_UPSTREAM),
                          MakeEnumAccessor<OrsWifiManager::ModFamily>(&OrsWifiManager::m_modFamily),
                          MakeEnumChecker(OrsWifiManager::ORS_MOD_MATCH_UPSTREAM, "MatchUpstream",
                                          OrsWifiManager::ORS_MOD_LATEST, "Latest"))
            .AddAttribute("Window", "Sliding-window size tau, in reports (SW-ORS only).",
                          UintegerValue(200),
                          MakeUintegerAccessor(&OrsWifiManager::m_window),
                          MakeUintegerChecker<uint32_t>(1))
            .AddAttribute("C", "Constant c in the index budget log(l) + c*log(log(l)).",
                          DoubleValue(3.0),
                          MakeDoubleAccessor(&OrsWifiManager::m_c),
                          MakeDoubleChecker<double>(0.0))
            .AddAttribute("BerThreshold", "Target BER for the required-SNR ordering.",
                          DoubleValue(1e-6),
                          MakeDoubleAccessor(&OrsWifiManager::m_ber),
                          MakeDoubleChecker<double>(0.0, 1.0))
            .AddTraceSource("Rate", "Traced value for rate changes (b/s)",
                            MakeTraceSourceAccessor(&OrsWifiManager::m_currentRate),
                            "ns3::TracedValueCallback::Uint64");
    return tid;
}

OrsWifiManager::OrsWifiManager()
    : m_currentRate{0}
{
    NS_LOG_FUNCTION(this);
}

OrsWifiManager::~OrsWifiManager()
{
    NS_LOG_FUNCTION(this);
}

double
OrsWifiManager::Kl(double p, double q)
{
    const double e = 1e-9;
    p = std::min(1.0 - e, std::max(e, p));
    q = std::min(1.0 - e, std::max(e, q));
    return p * std::log(p / q) + (1.0 - p) * std::log((1.0 - p) / (1.0 - q));
}

double
OrsWifiManager::KlUcb(double thetaHat, double t, double f)
{
    // max{ u in [thetaHat, 1] : t * KL(thetaHat, u) <= f }, by bisection.
    if (t <= 0.0)
    {
        return 1.0;
    }
    double lo = std::min(1.0, std::max(0.0, thetaHat));
    double hi = 1.0;
    for (int i = 0; i < 40; ++i)
    {
        const double mid = 0.5 * (lo + hi);
        if (t * Kl(thetaHat, mid) <= f)
        {
            lo = mid;
        }
        else
        {
            hi = mid;
        }
    }
    return lo;
}

WifiRemoteStation*
OrsWifiManager::DoCreateStation() const
{
    NS_LOG_FUNCTION(this);
    return new OrsWifiRemoteStation();
}

void
OrsWifiManager::InitializeStation(WifiRemoteStation* st) const
{
    auto s = static_cast<OrsWifiRemoteStation*>(st);
    if (s->init)
    {
        return;
    }
    // Build the SAME arm set as ns3::ThompsonSamplingWifiManager, so the comparison is
    // over identical rates. Without the modulation-class filter and mode.IsAllowed()
    // check, ORS would explore a strictly larger (and partly redundant) table than the
    // baseline it is being compared against -- an unfair handicap, since ORS's
    // neighbourhood moves only one step per decision.
    WifiModulationClass mc = WIFI_MOD_CLASS_HT;
    if (GetVhtSupported())
    {
        mc = WIFI_MOD_CLASS_VHT;
    }
    if (GetHeSupported())
    {
        mc = WIFI_MOD_CLASS_HE;
    }
    if (m_modFamily == ORS_MOD_LATEST && GetEhtSupported())
    {
        mc = WIFI_MOD_CLASS_EHT;
    }
    for (const auto& mode : GetPhy()->GetMcsList())
    {
        if (mode.GetModulationClass() != mc)
        {
            continue;
        }
        for (MHz_u w{20}; w <= GetPhy()->GetChannelWidth(); w *= 2)
        {
            for (uint8_t nss = 1; nss <= GetPhy()->GetMaxSupportedTxSpatialStreams(); ++nss)
            {
                if (!mode.IsAllowed(w, nss))
                {
                    continue;
                }
                OrsRate r;
                r.mode = mode;
                r.channelWidth = w;
                r.nss = nss;
                r.rate = mode.GetDataRate(w, GetGuardInterval(st), nss);
                s->rates.push_back(r);
            }
        }
    }
    NS_ABORT_MSG_IF(s->rates.empty(), "OrsWifiManager: empty rate table");

    // Order the table. The neighbourhood N(k) = {k-1,k,k+1} is defined on this order, so
    // the choice of ordering is what the structural assumption actually rests on.
    std::vector<std::pair<double, size_t>> key;
    key.reserve(s->rates.size());
    for (size_t i = 0; i < s->rates.size(); ++i)
    {
        double k;
        if (m_order == ORS_BY_SNR || m_order == ORS_BY_SNR_POWER)
        {
            WifiTxVector tv;
            tv.SetMode(s->rates[i].mode);
            tv.SetChannelWidth(s->rates[i].channelWidth);
            tv.SetNss(s->rates[i].nss);
            tv.SetGuardInterval(GetGuardInterval(st));
            k = tv.IsValid(GetPhy()->GetPhyBand())
                    ? GetPhy()->CalculateSnr(tv, m_ber)
                    : std::numeric_limits<double>::max();
            if (m_order == ORS_BY_SNR_POWER && k != std::numeric_limits<double>::max())
            {
                // See CqrWifiManager::BuildRateOrder: CalculateSnr is referenced to the
                // noise in the configuration's own bandwidth, so raw thresholds are not
                // comparable across widths or stream counts.
                k *= static_cast<double>(s->rates[i].channelWidth) *
                     static_cast<double>(s->rates[i].nss);
            }
        }
        else
        {
            k = s->rates[i].rate;
        }
        key.emplace_back(k, i);
    }
    std::sort(key.begin(), key.end());
    std::vector<OrsRate> sorted;
    sorted.reserve(s->rates.size());
    for (const auto& kv : key)
    {
        sorted.push_back(s->rates[kv.second]);
    }
    s->rates.swap(sorted);
    s->init = true;
}

void
OrsWifiManager::EvictWindow(WifiRemoteStation* st) const
{
    auto s = static_cast<OrsWifiRemoteStation*>(st);
    if (m_variant != ORS_SLIDING)
    {
        return;
    }
    while (s->window.size() > m_window)
    {
        const auto& e = s->window.front();
        s->rates[e.k].succ -= e.succ;
        s->rates[e.k].fail -= e.fail;
        if (s->rates[e.leaderIdx].leader > 0)
        {
            s->rates[e.leaderIdx].leader--;
        }
        s->window.pop_front();
    }
}

void
OrsWifiManager::Observe(WifiRemoteStation* st, uint32_t nSucc, uint32_t nFail) const
{
    InitializeStation(st);
    auto s = static_cast<OrsWifiRemoteStation*>(st);
    if (nSucc + nFail == 0)
    {
        return;
    }
    s->rates[s->lastMode].succ += nSucc;
    s->rates[s->lastMode].fail += nFail;
    s->n++;
    if (m_variant == ORS_SLIDING)
    {
        s->window.push_back({s->lastMode, static_cast<double>(nSucc),
                             static_cast<double>(nFail), s->lastMode});
        EvictWindow(st);
    }
}

void
OrsWifiManager::UpdateNextMode(WifiRemoteStation* st) const
{
    InitializeStation(st);
    auto s = static_cast<OrsWifiRemoteStation*>(st);
    const size_t K = s->rates.size();

    // Initialisation phase: play each rate once (n = 1..K in the paper).
    if (s->n < K)
    {
        s->nextMode = s->n;
        return;
    }

    auto tk = [&](size_t k) { return s->rates[k].succ + s->rates[k].fail; };
    auto theta = [&](size_t k) {
        const double t = tk(k);
        return t > 0.0 ? s->rates[k].succ / t : 0.0;
    };

    // Leader: highest empirical throughput r_k * theta_k.
    size_t L = 0;
    double best = -1.0;
    for (size_t k = 0; k < K; ++k)
    {
        const double m = s->rates[k].rate * theta(k);
        if (m > best)
        {
            best = m;
            L = k;
        }
    }
    s->rates[L].leader++;
    if (m_variant == ORS_SLIDING && !s->window.empty())
    {
        s->window.back().leaderIdx = L;
    }

    if (m_variant == ORS_KLRUCB)
    {
        // Algorithm 2: unstructured, budget log(n) + c log log(n), argmax over ALL rates.
        const double nn = std::max<double>(2.0, static_cast<double>(s->n));
        const double f = std::log(nn) + m_c * std::log(std::log(nn));
        double bi = -1.0;
        for (size_t k = 0; k < K; ++k)
        {
            const double q = s->rates[k].rate * KlUcb(theta(k), tk(k), f);
            if (q > bi)
            {
                bi = q;
                s->nextMode = k;
            }
        }
        return;
    }

    // Algorithms 1 and 3: exploit unimodality via the leader's neighbourhood.
    const double lL = std::max<double>(2.0, static_cast<double>(s->rates[L].leader));
    if (static_cast<uint32_t>(s->rates[L].leader - 1) % 3 == 0)
    {
        s->nextMode = L; // exploit the leader
        return;
    }
    const double f = std::log(lL) + m_c * std::log(std::log(lL));
    double bi = -1.0;
    s->nextMode = L;
    for (size_t k = (L > 0 ? L - 1 : 0); k <= std::min(K - 1, L + 1); ++k)
    {
        const double b = s->rates[k].rate * KlUcb(theta(k), tk(k), f);
        if (b > bi)
        {
            bi = b;
            s->nextMode = k;
        }
    }
}

void
OrsWifiManager::DoReportDataOk(WifiRemoteStation* st, double, WifiMode, double, MHz_u, uint8_t)
{
    Observe(st, 1, 0);
    UpdateNextMode(st);
}

void
OrsWifiManager::DoReportDataFailed(WifiRemoteStation* st)
{
    Observe(st, 0, 1);
    UpdateNextMode(st);
}

void
OrsWifiManager::DoReportAmpduTxStatus(WifiRemoteStation* st, uint16_t nSuccessfulMpdus,
                                      uint16_t nFailedMpdus, double, double, MHz_u, uint8_t)
{
    Observe(st, nSuccessfulMpdus, nFailedMpdus);
    UpdateNextMode(st);
}

void OrsWifiManager::DoReportRxOk(WifiRemoteStation*, double, WifiMode) {}
void OrsWifiManager::DoReportRtsFailed(WifiRemoteStation*) {}
void OrsWifiManager::DoReportRtsOk(WifiRemoteStation*, double, WifiMode, double) {}
void OrsWifiManager::DoReportFinalRtsFailed(WifiRemoteStation*) {}
void OrsWifiManager::DoReportFinalDataFailed(WifiRemoteStation*) {}

WifiTxVector
OrsWifiManager::DoGetDataTxVector(WifiRemoteStation* st, MHz_u allowedWidth)
{
    InitializeStation(st);
    auto s = static_cast<OrsWifiRemoteStation*>(st);
    s->nextMode = std::min(s->nextMode, s->rates.size() - 1);
    // Respect the currently allowed width; fall back to the widest permitted entry.
    size_t k = s->nextMode;
    if (s->rates[k].channelWidth > allowedWidth)
    {
        for (size_t j = 0; j < s->rates.size(); ++j)
        {
            if (s->rates[j].channelWidth <= allowedWidth)
            {
                k = j;
            }
        }
    }
    s->lastMode = k;
    const auto& r = s->rates[k];
    if (m_currentRate != static_cast<uint64_t>(r.rate))
    {
        m_currentRate = static_cast<uint64_t>(r.rate);
    }
    return WifiTxVector(r.mode, GetDefaultTxPowerLevel(),
                        GetPreambleForTransmission(r.mode.GetModulationClass(),
                                                   GetShortPreambleEnabled()),
                        GetGuardInterval(st), 1, r.nss, 0, r.channelWidth,
                        GetAggregation(st));
}

WifiTxVector
OrsWifiManager::DoGetRtsTxVector(WifiRemoteStation* st)
{
    InitializeStation(st);
    auto s = static_cast<OrsWifiRemoteStation*>(st);
    const auto& r = s->rates[0]; // most robust entry
    return WifiTxVector(r.mode, GetDefaultTxPowerLevel(),
                        GetPreambleForTransmission(r.mode.GetModulationClass(),
                                                   GetShortPreambleEnabled()),
                        GetGuardInterval(st), 1, 1, 0, r.channelWidth, GetAggregation(st));
}

} // namespace ns3
