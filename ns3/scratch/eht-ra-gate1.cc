/*
 * GATE 1 scenario — 802.11be rate adaptation under mobility and contention.
 *
 * 1 AP + nSta STAs, single EHT link, saturated downlink UDP.
 * Logs per-interval aggregate throughput so convergence / adaptation lag is visible.
 *
 * Oracle: run with --raa=ConstantRate --mcs=k for every k, then take the per-interval
 * max over k. That is the best-fixed-rate-per-interval genie, and unlike
 * IdealWifiManager it is a true upper bound on what any rate choice could deliver.
 */
#include "ns3/application-container.h"
#include "ns3/command-line.h"
#include "ns3/config.h"
#include "ns3/channel-condition-model.h"
#include "ns3/constant-velocity-mobility-model.h"
#include "ns3/jakes-propagation-loss-model.h"
#include "ns3/three-gpp-propagation-loss-model.h"
#include "ns3/double.h"
#include "ns3/internet-stack-helper.h"
#include "ns3/ipv4-address-helper.h"
#include "ns3/ipv4-interface-container.h"
#include "ns3/log.h"
#include "ns3/mobility-helper.h"
#include "ns3/multi-model-spectrum-channel.h"
#include "ns3/on-off-helper.h"
#include "ns3/packet-sink-helper.h"
#include "ns3/packet-sink.h"
#include "ns3/rng-seed-manager.h"
#include "ns3/spectrum-wifi-helper.h"
#include "ns3/ssid.h"
#include "ns3/string.h"
#include "ns3/uinteger.h"
#include "ns3/double.h"
#include "ns3/boolean.h"
#include "ns3/wifi-mac-helper.h"
#include "ns3/wifi-net-device.h"
#include "ns3/wifi-tx-vector.h"
#include "ns3/wifi-phy.h"
#include "ns3/yans-wifi-channel.h"

#include <fstream>
#include <iomanip>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("EhtRaGate1");

static std::vector<Ptr<PacketSink>> g_sinks;
// Per-STA throughput sampling (protocol-v1 §6, per-STA Jain fairness). Pure observation:
// Sample() already calls GetTotalRx() on every sink to form the aggregate, so recording
// the per-sink deltas adds no simulator interaction and cannot affect the run.
static std::ofstream g_perStaOut;
static std::vector<uint64_t> g_lastPerSta;
static uint64_t g_lastTotal = 0;
static std::ofstream g_out;
static double g_interval = 0.5;
static Ptr<Node> g_staNode0;
static Ptr<Node> g_apNode;

// --- diagnostic instrumentation: what did the manager actually transmit at? ---
static std::map<uint32_t, uint64_t> g_mcsCount;   // MCS index -> PHY transmissions
static std::map<uint32_t, uint64_t> g_widthCount; // channel width -> PHY transmissions
static std::map<uint32_t, uint64_t> g_nssCount;   // Nss -> PHY transmissions
// Joint (MCS, width, Nss) support, keyed mcs*100000 + width*10 + nss. The marginals above
// cannot express aggressiveness once width and streams vary -- a higher MCS at fewer
// streams can be a LOWER PHY rate -- so the joint distribution is recorded as well
// (protocol-v1 amendment A9.3). Also gives the observed action-set support of every
// manager, including the stock ones we do not modify.
static std::map<uint64_t, uint64_t> g_jointCount;
static std::map<uint64_t, uint64_t> g_rateCount; // PHY data rate (b/s) -> transmissions
static uint64_t g_txTotal = 0;

void
SnifferTx(Ptr<const Packet>, uint16_t, WifiTxVector txVector, MpduInfo, uint16_t)
{
    const uint32_t m = txVector.GetMode().GetMcsValue();
    const uint32_t w = static_cast<uint32_t>(txVector.GetChannelWidth());
    const uint32_t n = txVector.GetNss();
    g_mcsCount[m]++;
    g_widthCount[w]++;
    g_nssCount[n]++;
    g_jointCount[static_cast<uint64_t>(m) * 100000ULL + w * 10ULL + n]++;
    g_rateCount[txVector.GetMode().GetDataRate(txVector.GetChannelWidth(),
                                               txVector.GetGuardInterval(),
                                               n)]++;
    g_txTotal++;
}

void
Sample()
{
    uint64_t total = 0;
    const bool perSta = g_perStaOut.is_open();
    if (perSta && g_lastPerSta.size() != g_sinks.size())
    {
        g_lastPerSta.assign(g_sinks.size(), 0);
    }
    for (size_t i = 0; i < g_sinks.size(); ++i)
    {
        const uint64_t rx = g_sinks[i]->GetTotalRx();
        total += rx;
        if (perSta)
        {
            g_perStaOut << std::fixed << std::setprecision(4)
                        << Simulator::Now().GetSeconds() << "," << i << ","
                        << (rx - g_lastPerSta[i]) << "\n";
            g_lastPerSta[i] = rx;
        }
    }
    const uint64_t delta = total - g_lastTotal;
    g_lastTotal = total;

    double dist = 0.0;
    if (g_staNode0 && g_apNode)
    {
        dist = g_staNode0->GetObject<MobilityModel>()->GetDistanceFrom(
            g_apNode->GetObject<MobilityModel>());
    }
    const double mbps = (delta * 8.0) / (g_interval * 1e6);
    g_out << std::fixed << std::setprecision(4) << Simulator::Now().GetSeconds() << ","
          << std::setprecision(3) << dist << "," << delta << "," << std::setprecision(4)
          << mbps << "\n";
    Simulator::Schedule(Seconds(g_interval), &Sample);
}

int
main(int argc, char* argv[])
{
    std::string raa = "MinstrelHt";      // MinstrelHt|ThompsonSampling|Ideal|ConstantRate|Minstrel|Aarf|Cara|Rraa
    uint32_t mcs = 6;                    // used only when raa==ConstantRate
    uint32_t nSta = 1;
    uint32_t channelWidth = 80;
    uint32_t nss = 2;
    uint32_t gi = 800;
    double simTime = 20.0;
    double distance0 = 1.0;
    double speed = 0.0;                  // m/s, STA moves away from AP along +x
    std::string mobility = "linear";     // static|linear
    uint32_t seed = 1;
    std::string outFile = "gate1.csv";
    std::string perStaFile = "";        // per-STA throughput, for Jain fairness
    bool printMinstrelStats = false;
    std::string rateLog = "";           // if set, write MCS-usage summary here
    uint32_t payload = 1400;
    std::string offered = "600Mbps";     // per-STA offered load
    std::string channel = "logdistance"; // logdistance|logdistance+jakes|3gpp-indoor|3gpp-indoor+jakes
    double dopplerHz = -1.0;             // <0 => auto: f_d = v * f_c / c
    double freqHz = 5.25e9;              // nominal carrier for the Doppler calculation
    double tsDecay = -1.0;               // ThompsonSampling/Cqr Decay (Hz); <0 = ns-3 default
    std::string cqrMode = "Thompson";    // Cqr selection rule: Thompson|Quantile
    double cqrTargetFer = 0.10;          // Cqr target frame error rate
    double cqrEta = 0.02;                // Cqr quantile step size
    std::string cqrLog = "";             // Cqr per-decision log path
    std::string cqrCostLog = "";         // Cqr per-decision cost report path
    std::string cqrStructure = "None";   // Cqr rate-structure sharing: None|Monotone
    double cqrStructWeight = 0.5;        // weight on propagated evidence
    std::string cqrOrder = "RequiredSnr"; // propagation order: RequiredSnr|DataRate|RequiredSnrPower
    // MatchUpstream reproduces ns3::ThompsonSamplingWifiManager's HE-only ladder, which the
    // w=0 equivalence gate requires. Latest extends to EHT so the learners share an action
    // set with IdealWifiManager, MinstrelHt and the ConstantRate references (amendment A9.1).
    std::string modFamily = "MatchUpstream"; // MatchUpstream|Latest
    std::string armsLog = "";               // enumerated action-set dump; empty disables
    std::string cqrDecayAdapt = "Fixed"; // Fixed|Adaptive
    double cqrDecayTarget = 0.05;        // target excess prediction error
    double cqrDecayEta = 0.05;           // decay recursion step size
    std::string orsVariant = "SW-ORS";   // ORS|SW-ORS|KL-R-UCB
    std::string orsOrder = "DataRate";   // DataRate|RequiredSnr
    uint32_t orsWindow = 200;            // SW-ORS window tau, in reports
    uint32_t mhSampleColumn = 10;        // Minstrel-HT SampleColumn (default 10)
    double mhUpdateMs = 50.0;            // Minstrel-HT UpdateStatistics interval (ms)

    CommandLine cmd(__FILE__);
    cmd.AddValue("raa", "Rate adaptation algorithm", raa);
    cmd.AddValue("mcs", "MCS index for ConstantRate", mcs);
    cmd.AddValue("nSta", "Number of STAs (contention level)", nSta);
    cmd.AddValue("channelWidth", "Channel width in MHz", channelWidth);
    cmd.AddValue("nss", "Number of spatial streams", nss);
    cmd.AddValue("gi", "Guard interval (ns): 800|1600|3200", gi);
    cmd.AddValue("simTime", "Simulation time (s)", simTime);
    cmd.AddValue("distance0", "Initial AP-STA distance (m)", distance0);
    cmd.AddValue("speed", "STA speed (m/s), 0 = static", speed);
    cmd.AddValue("mobility", "static|linear", mobility);
    cmd.AddValue("seed", "RNG run number", seed);
    cmd.AddValue("out", "Output CSV path", outFile);
    cmd.AddValue("perStaOut", "Per-STA throughput CSV (protocol-v1 sec. 6 Jain fairness); empty disables", perStaFile);
    cmd.AddValue("interval", "Sampling interval (s)", g_interval);
    cmd.AddValue("printMinstrelStats", "Dump Minstrel-HT stats tables", printMinstrelStats);
    cmd.AddValue("rateLog", "Write per-run MCS/width/Nss usage summary here", rateLog);
    cmd.AddValue("payload", "UDP payload bytes", payload);
    cmd.AddValue("offered", "Per-STA offered load", offered);
    cmd.AddValue("channel", "logdistance|logdistance+jakes|3gpp-indoor|3gpp-indoor+jakes", channel);
    cmd.AddValue("dopplerHz", "Jakes Doppler (Hz); <0 = auto from speed", dopplerHz);
    cmd.AddValue("freqHz", "Nominal carrier frequency for Doppler calc", freqHz);
    cmd.AddValue("tsDecay", "Exponential Decay coefficient (Hz), Thompson and Cqr", tsDecay);
    cmd.AddValue("cqrMode", "Cqr selection rule: Thompson|Quantile", cqrMode);
    cmd.AddValue("cqrTargetFer", "Cqr target frame error rate", cqrTargetFer);
    cmd.AddValue("cqrEta", "Cqr quantile step size", cqrEta);
    cmd.AddValue("cqrLog", "Cqr per-decision log path", cqrLog);
    cmd.AddValue("cqrCostLog", "Cqr per-decision cost report path (protocol-v1 sec. 6)", cqrCostLog);
    cmd.AddValue("cqrStructure", "Cqr rate-structure sharing: None|Monotone", cqrStructure);
    cmd.AddValue("cqrStructWeight", "Cqr propagated-evidence weight", cqrStructWeight);
    cmd.AddValue("cqrOrder", "Cqr propagation order: RequiredSnr|DataRate|RequiredSnrPower", cqrOrder);
    cmd.AddValue("modFamily", "Rate-table modulation family for Cqr and Ors: MatchUpstream|Latest", modFamily);
    cmd.AddValue("armsLog", "Dump the enumerated action set here (Cqr only); empty disables", armsLog);
    cmd.AddValue("cqrDecayAdapt", "Cqr decay mode: Fixed|Adaptive", cqrDecayAdapt);
    cmd.AddValue("cqrDecayTarget", "Cqr target excess prediction error", cqrDecayTarget);
    cmd.AddValue("cqrDecayEta", "Cqr decay recursion step size", cqrDecayEta);
    cmd.AddValue("orsVariant", "ORS|SW-ORS|KL-R-UCB", orsVariant);
    cmd.AddValue("orsOrder", "ORS neighbourhood ordering: DataRate|RequiredSnr", orsOrder);
    cmd.AddValue("orsWindow", "SW-ORS sliding-window size (reports)", orsWindow);
    cmd.AddValue("mhSampleColumn", "Minstrel-HT SampleColumn", mhSampleColumn);
    cmd.AddValue("mhUpdateMs", "Minstrel-HT UpdateStatistics interval (ms)", mhUpdateMs);
    cmd.Parse(argc, argv);

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(seed);

    NodeContainer apNode;
    apNode.Create(1);
    NodeContainer staNodes;
    staNodes.Create(nSta);

    SpectrumWifiPhyHelper phy(1);
    auto spectrumChannel = CreateObject<MultiModelSpectrumChannel>();

    // ---- propagation chain: [large-scale path loss] -> [optional Jakes fast fading] ----
    // Doppler is set explicitly from the STA speed, f_d = v * f_c / c, because ns-3's
    // JakesProcess takes DopplerFrequencyHz as a fixed attribute rather than deriving it
    // from node velocity. Coherence time T_c ~ 0.423 / f_d, so faster motion => shorter
    // coherence => per-rate statistics go stale faster. That is the mechanism under test.
    const double c0 = 299792458.0;
    double fd = (dopplerHz >= 0.0) ? dopplerHz : (speed * freqHz / c0);
    // Guard: JakesProcess degenerates at f_d = 0 (the process never advances, and the
    // link can sit in a frozen deep fade -> zero throughput, which is a numerical
    // artefact, not physics). Floor it at 1 Hz, representing residual scatterer motion
    // in an otherwise static environment. This keeps the channel model family identical
    // across all speeds so that speed sweeps stay comparable.
    if (channel.find("jakes") != std::string::npos)
    {
        if (fd < 1.0)
        {
            fd = 1.0;
        }
        Config::SetDefault("ns3::JakesProcess::DopplerFrequencyHz", DoubleValue(fd));
    }

    Ptr<PropagationLossModel> head;
    if (channel.rfind("3gpp-indoor", 0) == 0)
    {
        auto ccm = CreateObject<ThreeGppIndoorOpenOfficeChannelConditionModel>();
        auto tgpp = CreateObject<ThreeGppIndoorOfficePropagationLossModel>();
        tgpp->SetAttribute("Frequency", DoubleValue(freqHz));
        tgpp->SetAttribute("ShadowingEnabled", BooleanValue(true));
        tgpp->SetChannelConditionModel(ccm);
        head = tgpp;
    }
    else
    {
        head = CreateObject<LogDistancePropagationLossModel>();
    }
    if (channel.find("jakes") != std::string::npos)
    {
        head->SetNext(CreateObject<JakesPropagationLossModel>());
    }
    spectrumChannel->AddPropagationLossModel(head);
    phy.AddChannel(spectrumChannel, WIFI_SPECTRUM_5_GHZ);
    std::ostringstream chSet;
    chSet << "{0, " << channelWidth << ", BAND_5GHZ, 0}";
    phy.Set("ChannelSettings", StringValue(chSet.str()));
    phy.Set("Antennas", UintegerValue(nss));
    phy.Set("MaxSupportedTxSpatialStreams", UintegerValue(nss));
    phy.Set("MaxSupportedRxSpatialStreams", UintegerValue(nss));

    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211be);
    if (raa == "ConstantRate")
    {
        std::ostringstream mode;
        mode << "EhtMcs" << mcs;
        wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                     "DataMode", StringValue(mode.str()),
                                     "ControlMode", StringValue("OfdmRate24Mbps"));
    }
    else if (raa == "MinstrelHt")
    {
        wifi.SetRemoteStationManager("ns3::MinstrelHtWifiManager",
                                     "SampleColumn", UintegerValue(mhSampleColumn),
                                     "UpdateStatistics", TimeValue(MilliSeconds(mhUpdateMs)),
                                     "PrintStats", BooleanValue(printMinstrelStats));
    }
    else if (raa == "__never_MinstrelHt" && printMinstrelStats)
    {
        wifi.SetRemoteStationManager("ns3::MinstrelHtWifiManager",
                                     "PrintStats", BooleanValue(true));
    }
    else if (raa == "Ors")
    {
        wifi.SetRemoteStationManager("ns3::OrsWifiManager",
                                     "Variant", StringValue(orsVariant),
                                     "Order", StringValue(orsOrder),
                                     "ModulationFamily", StringValue(modFamily),
                                     "Window", UintegerValue(orsWindow));
    }
    else if (raa == "Cqr")
    {
        // Mode=Thompson must reproduce ns3::ThompsonSamplingWifiManager exactly.
        wifi.SetRemoteStationManager("ns3::CqrWifiManager",
                                     "Mode", StringValue(cqrMode),
                                     "Decay", DoubleValue(tsDecay >= 0.0 ? tsDecay : 1.0),
                                     "TargetFer", DoubleValue(cqrTargetFer),
                                     "Eta", DoubleValue(cqrEta),
                                     "LogFile", StringValue(cqrLog),
                                     "CostLog", StringValue(cqrCostLog),
                                     "Structure", StringValue(cqrStructure),
                                     "StructureWeight", DoubleValue(cqrStructWeight),
                                     "Order", StringValue(cqrOrder),
                                     "ModulationFamily", StringValue(modFamily),
                                     "ArmsLog", StringValue(armsLog),
                                     "DecayAdapt", StringValue(cqrDecayAdapt),
                                     "DecayTarget", DoubleValue(cqrDecayTarget),
                                     "DecayEta", DoubleValue(cqrDecayEta));
    }
    else if (raa == "ThompsonSampling" && tsDecay >= 0.0)
    {
        // ns-3's ThompsonSamplingWifiManager is already a *discounted* Thompson sampler:
        // success/fail counts are multiplied by exp(-Decay * dt). Default Decay = 1.0 Hz
        // (a 1 s forgetting time constant). Exposing it lets us sweep the tuned-baseline
        // frontier rather than beating an untuned default.
        wifi.SetRemoteStationManager("ns3::ThompsonSamplingWifiManager",
                                     "Decay", DoubleValue(tsDecay));
    }
    else
    {
        wifi.SetRemoteStationManager("ns3::" + raa + "WifiManager");
    }

    WifiMacHelper mac;
    Ssid ssid = Ssid("eht-ra-gate1");
    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid));
    NetDeviceContainer staDevices = wifi.Install(phy, mac, staNodes);
    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid),
                "EnableBeaconJitter", BooleanValue(false));
    NetDeviceContainer apDevice = wifi.Install(phy, mac, apNode);

    int64_t stream = 100;
    stream += WifiHelper::AssignStreams(apDevice, stream);
    stream += WifiHelper::AssignStreams(staDevices, stream);

    std::ostringstream giPath;
    Config::Set("/NodeList/*/DeviceList/*/$ns3::WifiNetDevice/HeConfiguration/GuardInterval",
                TimeValue(NanoSeconds(gi)));

    // ---- mobility: AP at origin, STAs on a line starting at distance0 ----
    MobilityHelper mob;
    Ptr<ListPositionAllocator> pos = CreateObject<ListPositionAllocator>();
    pos->Add(Vector(0.0, 0.0, 0.0));
    for (uint32_t i = 0; i < nSta; ++i)
    {
        pos->Add(Vector(distance0, 1.0 * i, 0.0));
    }
    mob.SetPositionAllocator(pos);
    if (mobility == "linear" && speed > 0.0)
    {
        mob.SetMobilityModel("ns3::ConstantVelocityMobilityModel");
    }
    else
    {
        mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    }
    mob.Install(apNode);
    mob.Install(staNodes);
    apNode.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(0, 0, 0));
    if (mobility == "linear" && speed > 0.0)
    {
        apNode.Get(0)->GetObject<ConstantVelocityMobilityModel>()->SetVelocity(
            Vector(0, 0, 0));
        for (uint32_t i = 0; i < nSta; ++i)
        {
            staNodes.Get(i)->GetObject<ConstantVelocityMobilityModel>()->SetVelocity(
                Vector(speed, 0, 0));
        }
    }

    InternetStackHelper stack;
    stack.Install(apNode);
    stack.Install(staNodes);
    Ipv4AddressHelper addr;
    addr.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer apIf = addr.Assign(apDevice);
    Ipv4InterfaceContainer staIf = addr.Assign(staDevices);

    // ---- saturated downlink UDP: AP -> each STA ----
    ApplicationContainer sinkApps, srcApps;
    const uint16_t port = 5001;
    for (uint32_t i = 0; i < nSta; ++i)
    {
        PacketSinkHelper sinkH("ns3::UdpSocketFactory",
                               InetSocketAddress(Ipv4Address::GetAny(), port + i));
        ApplicationContainer a = sinkH.Install(staNodes.Get(i));
        sinkApps.Add(a);
        g_sinks.push_back(DynamicCast<PacketSink>(a.Get(0)));

        OnOffHelper onoff("ns3::UdpSocketFactory",
                          InetSocketAddress(staIf.GetAddress(i), port + i));
        onoff.SetAttribute("OnTime", StringValue("ns3::ConstantRandomVariable[Constant=1]"));
        onoff.SetAttribute("OffTime", StringValue("ns3::ConstantRandomVariable[Constant=0]"));
        onoff.SetAttribute("DataRate", DataRateValue(DataRate(offered)));
        onoff.SetAttribute("PacketSize", UintegerValue(payload));
        srcApps.Add(onoff.Install(apNode.Get(0)));
    }
    sinkApps.Start(Seconds(0.0));
    srcApps.Start(Seconds(0.5));
    srcApps.Stop(Seconds(simTime));

    g_out.open(outFile);
    g_out << "time_s,distance_m,rx_bytes,throughput_mbps\n";
    if (!perStaFile.empty())
    {
        g_perStaOut.open(perStaFile);
        g_perStaOut << "time_s,sta,rx_bytes\n";
    }
    g_staNode0 = staNodes.Get(0);
    g_apNode = apNode.Get(0);
    Simulator::Schedule(Seconds(0.5 + g_interval), &Sample);

    if (!rateLog.empty())
    {
        Config::ConnectWithoutContext(
            "/NodeList/0/DeviceList/*/$ns3::WifiNetDevice/Phys/*/MonitorSnifferTx",
            MakeCallback(&SnifferTx));
    }

    Simulator::Stop(Seconds(simTime + 0.1));
    Simulator::Run();
    Simulator::Destroy();
    g_out.close();

    if (!rateLog.empty())
    {
        std::ofstream rl(rateLog);
        rl << "field,value,count\n";
        for (const auto& kv : g_mcsCount)
        {
            rl << "mcs," << kv.first << "," << kv.second << "\n";
        }
        for (const auto& kv : g_widthCount)
        {
            rl << "width," << kv.first << "," << kv.second << "\n";
        }
        for (const auto& kv : g_jointCount)
        {
            // "mcs_width_nss" as a single field value, so the CSV schema is unchanged.
            rl << "joint," << (kv.first / 100000ULL) << "_" << ((kv.first % 100000ULL) / 10ULL)
               << "_" << (kv.first % 10ULL) << "," << kv.second << "\n";
        }
        for (const auto& kv : g_rateCount)
        {
            rl << "phyrate," << kv.first << "," << kv.second << "\n";
        }
        for (const auto& kv : g_nssCount)
        {
            rl << "nss," << kv.first << "," << kv.second << "\n";
        }
        rl << "total_phy_tx,0," << g_txTotal << "\n";
        rl << "rx_bytes_total,0," << g_lastTotal << "\n";
        rl.close();
    }
    return 0;
}
