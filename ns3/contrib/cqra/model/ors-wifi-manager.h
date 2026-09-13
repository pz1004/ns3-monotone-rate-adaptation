/*
 * ORS / SW-ORS / KL-R-UCB rate adaptation, after
 *   R. Combes, A. Proutiere, D. Yun, J. Ok, Y. Yi,
 *   "Optimal Rate Sampling in 802.11 Systems", INFOCOM 2014 (arXiv:1307.7309).
 *
 * Implemented here as a faithful BASELINE for the ICC 2027 submission, including the
 * paper's own sliding-window variant (Algorithm 3) so that the comparison in a mobile
 * scenario is fair rather than a straw man.
 *
 * SPDX-License-Identifier: GPL-2.0-only
 */
#ifndef ORS_WIFI_MANAGER_H
#define ORS_WIFI_MANAGER_H

#include "ns3/traced-value.h"
#include "ns3/wifi-remote-station-manager.h"

#include <deque>
#include <string>
#include <vector>

namespace ns3
{

/**
 * @brief ORS family of rate adaptation algorithms (Combes et al., INFOCOM 2014).
 * @ingroup wifi
 */
class OrsWifiManager : public WifiRemoteStationManager
{
  public:
    static TypeId GetTypeId();
    OrsWifiManager();
    ~OrsWifiManager() override;

    /// Which algorithm from the paper to run.
    enum Variant
    {
        ORS_STATIONARY = 0, //!< Algorithm 1: ORS
        ORS_SLIDING = 1,    //!< Algorithm 3: SW-ORS (non-stationary)
        ORS_KLRUCB = 2      //!< Algorithm 2: KL-R-UCB (unstructured control)
    };

    /// How the rate index is ordered, which defines the neighbourhood N(k).
    enum Order
    {
        ORS_BY_RATE = 0,     //!< by achievable data rate, as published
        ORS_BY_SNR = 1,      //!< by required SNR threshold
        ORS_BY_SNR_POWER = 2 //!< by required SNR x width x streams (required receive power)
    };

    /// Which modulation classes the rate table enumerates. See CqrWifiManager::ModFamily.
    enum ModFamily
    {
        ORS_MOD_MATCH_UPSTREAM = 0, //!< HT -> VHT -> HE, as ns3::ThompsonSamplingWifiManager
        ORS_MOD_LATEST = 1          //!< ... -> EHT when both peers support it
    };

  private:
    WifiRemoteStation* DoCreateStation() const override;
    void DoReportRxOk(WifiRemoteStation* station, double rxSnr, WifiMode txMode) override;
    void DoReportRtsFailed(WifiRemoteStation* station) override;
    void DoReportDataFailed(WifiRemoteStation* station) override;
    void DoReportRtsOk(WifiRemoteStation* station, double ctsSnr, WifiMode ctsMode,
                       double rtsSnr) override;
    void DoReportDataOk(WifiRemoteStation* station, double ackSnr, WifiMode ackMode,
                        double dataSnr, MHz_u dataChannelWidth, uint8_t dataNss) override;
    void DoReportAmpduTxStatus(WifiRemoteStation* station, uint16_t nSuccessfulMpdus,
                               uint16_t nFailedMpdus, double rxSnr, double dataSnr,
                               MHz_u dataChannelWidth, uint8_t dataNss) override;
    void DoReportFinalRtsFailed(WifiRemoteStation* station) override;
    void DoReportFinalDataFailed(WifiRemoteStation* station) override;
    WifiTxVector DoGetDataTxVector(WifiRemoteStation* station, MHz_u allowedWidth) override;
    WifiTxVector DoGetRtsTxVector(WifiRemoteStation* station) override;

    /// Build the rate table and its ordering.
    void InitializeStation(WifiRemoteStation* station) const;
    /// Record an observation of nSucc successes / nFail failures on the last used rate.
    void Observe(WifiRemoteStation* station, uint32_t nSucc, uint32_t nFail) const;
    /// Run the ORS decision rule and set the next rate.
    void UpdateNextMode(WifiRemoteStation* station) const;
    /// Drop observations that fall outside the sliding window (SW-ORS only).
    void EvictWindow(WifiRemoteStation* station) const;

    /// KL divergence between two Bernoulli distributions.
    static double Kl(double p, double q);
    /// KL-UCB upper confidence bound on theta given t observations and budget f.
    static double KlUcb(double thetaHat, double t, double f);

    Variant m_variant;  //!< algorithm variant
    Order m_order;      //!< rate ordering defining the neighbourhood
    ModFamily m_modFamily; //!< which modulation classes the rate table enumerates
    uint32_t m_window;  //!< sliding-window size tau, in reports (SW-ORS only)
    double m_c;         //!< the constant c in the index budget
    double m_ber;       //!< target BER for the required-SNR ordering

    TracedValue<uint64_t> m_currentRate; //!< trace rate changes
};

} // namespace ns3

#endif /* ORS_WIFI_MANAGER_H */
