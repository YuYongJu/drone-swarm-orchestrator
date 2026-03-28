# Literature Review: Drone Swarm Communication, Mesh Networking, and Resilient Coordination

**Date**: 2026-03-26
**Purpose**: Inform SDK upgrade decisions for the Drone Swarm Orchestrator
**Scope**: 2019-2026 academic and defense research across 8 topic areas

---

## Table of Contents

1. [MAVLink Optimization for Multi-Vehicle](#1-mavlink-optimization-for-multi-vehicle)
2. [Mesh Networking for Drone Swarms](#2-mesh-networking-for-drone-swarms)
3. [Geographic Routing](#3-geographic-routing)
4. [Anti-Jamming / Electronic Warfare Resilience](#4-anti-jamming--electronic-warfare-resilience)
5. [Consensus Under Communication Constraints](#5-consensus-under-communication-constraints)
6. [Starlink/LTE/5G for Drone BVLOS](#6-starlinklte5g-for-drone-bvlos)
7. [Multi-Drone Relative Positioning Without GPS](#7-multi-drone-relative-positioning-without-gps)
8. [2024-2026 State of the Art](#8-2024-2026-state-of-the-art)
9. [SDK Upgrade Recommendation Summary](#9-sdk-upgrade-recommendation-summary)

---

## 1. MAVLink Optimization for Multi-Vehicle

### 1.1 MAVLink v2 Protocol Fundamentals

**Citation**: Koubaa, A. et al., "Micro Air Vehicle Link (MAVLink) in a Nutshell: A Survey," *IEEE Access*, 2019.
**Link**: https://arxiv.org/pdf/1906.10641

**Summary**: Comprehensive survey of the MAVLink protocol. MAVLink v2 has 14 bytes of overhead per packet (v1 had 8 bytes). The protocol supports up to 255 vehicles on a single network via system ID addressing. Messages are sent with built-in priority ordering across application and transport layers. The protocol uses multicast for telemetry streams and point-to-point with retransmission for guaranteed-delivery operations (mission protocol, parameter protocol).

**Practical Feasibility**: HIGH. MAVLink is the de facto standard for PX4/ArduPilot. The 255-vehicle limit is a hard protocol constraint that must be considered in swarm architecture.

### 1.2 MAVLink Security -- Signing and Encryption

**Citation**: Kwon, Y. et al., "MAVSec: Securing the MAVLink Protocol for Ardupilot/PX4 Unmanned Aerial Systems," *arXiv:1905.00265*, 2019.
**Link**: https://arxiv.org/abs/1905.00265

**Summary**: MAVLink v2 introduced optional 48-bit packet signing (SHA-256 based) for authentication, but provides NO encryption -- all messages are transmitted in plaintext. This enables man-in-the-middle, replay, and spoofing attacks. MAVSec proposes adding AES-CBC, AES-CTR, and RC4 encryption layers to the MAVLink stack.

**Citation**: Al-Tameemi, G. et al., "A Novel Cipher for Enhancing MAVLink Security: Design, Security Analysis, and Performance Evaluation Using a Drone Testbed," *arXiv:2504.20626*, April 2025.
**Link**: https://arxiv.org/html/2504.20626v1

**Summary**: Proposes ChaCha20-based encryption for MAVLink. Testing on real drone hardware shows only marginal overhead: 0.024% memory increase, 5.653% battery consumption increase, and 2.937% CPU load increase relative to unencrypted MAVLink. ChaCha20 outperforms AES in constrained environments.

**Citation**: Daoud, L. et al., "A Survey of Security Challenges and Solutions for UAV Communication," *arXiv:2601.08229*, January 2026.
**Link**: https://arxiv.org/pdf/2601.08229

**Summary**: Comprehensive 2026 survey identifying key security gaps: no confidentiality in MAVLink, limited adoption of message signing, vulnerability to cross-layer attacks during swarm operations. Identifies post-quantum cryptography for UAV swarms as an open research challenge.

**Practical Feasibility**: HIGH. ChaCha20 encryption is lightweight enough for onboard implementation. Message signing should be mandatory in any swarm deployment.

**SDK Recommendation**: Implement ChaCha20 encryption as a configurable layer on top of MAVLink v2. Make message signing mandatory by default. Add key rotation mechanism for in-flight rekeying.

### 1.3 Bandwidth Management at Scale

**Citation**: Adapted from MAVLink protocol documentation and PX4 developer forums.
**Link**: https://mavlink.io/en/about/overview.html

**Summary**: MAVLink's 14-byte overhead and lack of built-in compression mean bandwidth scales linearly with drone count. For N drones on a shared 915 MHz radio at 250 kbps, the practical limit is approximately 10-15 drones sending full telemetry at 10 Hz. There are no published papers specifically on MAVLink message compression or prioritization at scale -- this is a significant gap in the literature.

**Citation**: Pascarella, D. et al., "Towards a Unified Decentralized Swarm Management and Maintenance Coordination Based on MAVLink," *ResearchGate*, 2016.
**Link**: https://www.researchgate.net/publication/307937283

**Summary**: Proposes a compact `VehicleStatus` message that aggregates essential telemetry for swarm coordination, reducing per-vehicle bandwidth requirements. This is a pragmatic approach to bandwidth management rather than compression.

**SDK Recommendation**: Implement a message priority queue (safety-critical > navigation > telemetry > debug). Add configurable message rate decimation per drone count. Design a compact swarm-status message that aggregates essential fields (position, velocity, battery, state) into a single MAVLink message. Consider delta-encoding for slowly-changing fields.

---

## 2. Mesh Networking for Drone Swarms

### 2.1 Ad-Hoc Networking Protocols (AODV, OLSR, BATMAN)

**Citation**: Lakew, D. et al., "Simulation-Based Comparison of AODV, OLSR and HWMP Protocols for Flying Ad Hoc Networks," *Springer LNCS*, 2014.
**Link**: https://link.springer.com/chapter/10.1007/978-3-319-10353-2_21

**Summary**: Comparative study of reactive (AODV), proactive (OLSR), and hybrid (HWMP) routing in FANETs. OLSR outperforms AODV in dense networks due to precomputed routes, but AODV has lower overhead in sparse topologies. HWMP (used in 802.11s) provides a middle ground.

**Citation**: TU Munich, "B.A.T.M.A.N Unpacked: A Guide to the Protocol's Fundamental Concepts," *NET-2024-09*, 2024.
**Link**: https://www.net.in.tum.de/fileadmin/TUM/NET/NET-2024-09-1/NET-2024-09-1_02.pdf

**Summary**: BATMAN Advanced operates at Layer 2 (data link layer), making it transparent to higher protocols. Unlike OLSR and AODV (Layer 3), BATMAN-adv doesn't require IP address configuration on the mesh, simplifying deployment. Testing shows approximately 130-meter single-hop range with Raspberry Pi nodes.

**Citation**: Sliwa, B. et al., "Performance analysis of mesh routing protocols for UAV swarming applications," *ResearchGate*.
**Link**: https://www.researchgate.net/publication/220825932

**Summary**: Recommends BATMAN-Advanced and open80211s for reliable multihop mesh establishment in swarming applications. Babel protocol outperforms both OLSR and BATMAN in some mobility scenarios.

**Practical Feasibility**: HIGH. All three protocols have mature Linux implementations. BATMAN-adv is available in the Linux kernel. OLSR has the `olsrd` daemon. Babel has `babeld`.

**SDK Recommendation**: Default to BATMAN-adv for Layer 2 mesh (simplest deployment, kernel-native). Support OLSR as alternative for networks requiring Layer 3 routing. Implement automatic mesh formation on boot with configurable protocol selection.

### 2.2 LoRa Mesh for Long-Range Drone Communication

**Citation**: Davoli, L. et al., "Hybrid LoRa-IEEE 802.11s Opportunistic Mesh Networking for Flexible UAV Swarming," *Drones (MDPI)*, 5(2):26, 2021.
**Link**: https://www.mdpi.com/2504-446X/5/2/26

**Summary**: The seminal paper on hybrid LoRa + WiFi mesh for drone swarms. LoRa provides long-range (multi-km) low-bandwidth command/control, while 802.11s provides short-range high-bandwidth data exchange. Uses TDMA scheduling for LoRa with fields for node ID, positioning, and mesh configuration. Architecture uses a "root node" in the 802.11s mesh connected to the ground station.

**Citation**: Gupta, A. et al., "Swarm of Drones Using LoRa Flying Ad-Hoc Network," *IEEE*, 2021.
**Link**: https://ieeexplore.ieee.org/document/9491655/

**Summary**: Implements a FANET using LoRa with customized DSDV routing protocol optimized for single-channel operation. GPS coordinates shared via LoRa enable geographic awareness. Demonstrates that LoRa's line-of-sight advantage at altitude significantly extends range compared to ground-level applications.

**Citation**: PMC, "LoRa Technology in Flying Ad Hoc Networks: A Survey of Challenges and Open Issues," 2023.
**Link**: https://pmc.ncbi.nlm.nih.gov/articles/PMC10007589/

**Summary**: Comprehensive survey identifying LoRa's characteristics for FANETs: LPWAN class, low cost, low power, large coverage area, high device count support. Key challenges: low data rate (0.3-50 kbps), half-duplex operation, duty cycle limitations in some regions.

**Practical Feasibility**: MEDIUM-HIGH. LoRa modules (SX1276/SX1262) are inexpensive ($5-15) and well-supported. Data rate is only suitable for command/control, not video or bulk data. The hybrid approach (LoRa + WiFi) is the most practical architecture.

**SDK Recommendation**: Implement dual-radio architecture: LoRa for long-range heartbeat/command/emergency, WiFi mesh for high-bandwidth data. Abstract the radio layer so the SDK can route messages to the appropriate radio based on message type and priority.

### 2.3 WiFi Mesh (802.11s) for Short-Range High-Bandwidth

**Citation**: Souza, E. & Nikolaidis, I., "A Novel Routing Metric for IEEE 802.11s-based Swarm-of-Drones Applications," *ACM MobiQuitous*, 2019.
**Link**: https://dl.acm.org/doi/10.1145/3360774.3368197

**Summary**: Develops customized routing metrics for 802.11s in drone swarms. Standard 802.11s metrics (Airtime Link Metric) don't account for 3D mobility. Proposes metrics incorporating link quality, node velocity, and expected link lifetime for more stable routing in mobile swarms.

**Citation**: Souza, E. et al., "Extending IEEE 802.11s Mesh Routing for 3-D Mobile Drone Applications in ns-3," *ACM ns-3 Workshop*, 2020.
**Link**: https://dl.acm.org/doi/10.1145/3389400.3389406

**Summary**: Extends the HWMP (Hybrid Wireless Mesh Protocol) in 802.11s with 3D awareness for drone networks. Standard HWMP was designed for stationary nodes; this extension accounts for altitude and 3D movement vectors.

**Practical Feasibility**: HIGH. 802.11s is supported natively in Linux via `iw` and `wpa_supplicant`. Most modern WiFi chipsets support mesh mode. 5 GHz band recommended for inter-drone links (less interference), 2.4 GHz for ground coverage.

**SDK Recommendation**: Use 802.11s as the primary high-bandwidth mesh layer. Implement custom routing metrics that factor in 3D position, velocity vectors, and link quality. Configure 5 GHz for drone-to-drone, 2.4 GHz for drone-to-ground.

### 2.4 Delay-Tolerant Networking (DTN)

**Citation**: Various DTN research for FANETs (multiple authors).
**Links**: https://ieeexplore.ieee.org/document/8566956/ | https://arxiv.org/pdf/2308.06732

**Summary**: DTN uses store-carry-and-forward (SCF) technique for intermittent connectivity. UD-MAC protocol provides delay-tolerant CSMA-based medium access for UAVs. Key insight: DTN is critical for search-and-rescue and large-area surveillance where maintaining continuous mesh connectivity is impractical.

**Practical Feasibility**: MEDIUM. DTN adds complexity but is essential for missions where drones operate beyond mesh range. IBR-DTN is an open-source DTN implementation for Linux.

**SDK Recommendation**: Implement a message store-and-forward buffer for when mesh connectivity is lost. Priority queue ensures safety-critical messages are forwarded first when connectivity is restored. This is a "nice-to-have" for v2 of the SDK.

---

## 3. Geographic Routing

### 3.1 GPSR and Variants for FANETs

**Citation**: Kumar, S. et al., "UF-GPSR: Modified Geographical Routing Protocol for Flying Ad-hoc Networks," *Trans. Emerging Telecomm. Tech.*, 2023.
**Link**: https://onlinelibrary.wiley.com/doi/abs/10.1002/ett.4813

**Summary**: UF-GPSR optimizes the greedy forwarding strategy by incorporating residual energy ratio, distance degree, movement direction, link risk degree, and speed as routing parameters. Significantly outperforms vanilla GPSR in high-mobility FANET scenarios by reducing packet loss during topology changes.

**Citation**: Alsaade, F. et al., "A new version of the greedy perimeter stateless routing scheme in flying ad hoc networks," *Journal of King Saud University*, 2024.
**Link**: https://www.sciencedirect.com/science/article/pii/S1319157824001551

**Summary**: Combines GPSR with AODV (GPSR+AODV). Each UAV adjusts hello broadcast period based on predicted future spatial coordinates, and modifies greedy forwarding by restricting the search space using fitness functions based on relative velocity, energy level, buffer capacity, and distance.

**Citation**: MDPI Electronics, "Geographic Routing Decision Method for Flying Ad Hoc Networks Based on Mobile Prediction," 2025.
**Link**: https://www.mdpi.com/2079-9292/14/7/1456

**Summary**: MP-QGRD combines Extended Kalman Filter (EKF) for node position prediction with reinforcement learning for routing decisions. Hello packet intervals are dynamically adjusted based on network conditions, addressing the Temporary Communication Blindness (TCB) problem in standard GPSR.

**Citation**: An, J. et al., "Empowering Adaptive Geolocation-Based Routing for UAV Networks with Reinforcement Learning," *Drones (MDPI)*, 2023.
**Link**: https://www.mdpi.com/2504-446X/7/6/387

**Summary**: Uses RL to learn optimal geographic routing decisions, considering link stability, energy consumption, and communication distance. Demonstrates that ML-enhanced geographic routing outperforms static protocols in dynamic FANET environments.

**Practical Feasibility**: MEDIUM. Geographic routing is powerful for large swarms where maintaining full topology knowledge is expensive. However, it requires accurate position information from all nodes -- chicken-and-egg problem if GPS is denied.

**SDK Recommendation**: Implement position-aware routing as a module. Each drone broadcasts position + velocity in mesh beacons. The routing layer can use this for greedy geographic forwarding when the network is large enough (>20 drones) that proactive routing becomes expensive. Fall back to BATMAN-adv/OLSR for smaller swarms.

---

## 4. Anti-Jamming / Electronic Warfare Resilience

### 4.1 Frequency Hopping Spread Spectrum (FHSS)

**Citation**: YTTEK Technology, "Frequency Switching in Military Drones," 2025.
**Link**: https://yttek.com/frequency-switching-in-military-drones-how-advanced-drone-communication-modules-counter-jamming/

**Summary**: Military-grade drone communication modules utilize FHSS across 300 MHz to 6 GHz with hopping rates exceeding 2,000 hops/second. This prevents a jammer from concentrating energy on any single frequency long enough to deny communication.

**Citation**: Chrysovalantis et al., "Enhancing Communication Security in Drones Using QRNG in Frequency Hopping Spread Spectrum," *Future Internet (MDPI)*, 16(11):412, 2024.
**Link**: https://www.mdpi.com/1999-5903/16/11/412

**Summary**: Integrates Quantum Random Number Generators (QRNG) into FHSS for truly unpredictable hopping sequences. Multi-drone framework demonstrates significant improvement in jamming resistance compared to pseudo-random hopping sequences.

**Citation**: arXiv:2508.11687, "Agent-Based Anti-Jamming Techniques for UAV Communications in Adversarial Environments: A Comprehensive Survey," August 2025.
**Link**: https://arxiv.org/html/2508.11687v1

**Summary**: Deep reinforcement learning enables autonomous anti-jamming: drones learn optimal frequency hopping speed and transmission power in real-time. Genetic algorithms can additionally optimize hopping patterns for covertness. This is the most comprehensive recent survey on the topic.

**Practical Feasibility**: LOW-MEDIUM for civilian SDK. True FHSS requires SDR hardware (not standard WiFi/LoRa modules). However, WiFi channel hopping and LoRa frequency diversity provide some resilience with COTS hardware.

**SDK Recommendation**: For the near-term, implement WiFi channel rotation and LoRa frequency diversity as basic anti-jamming measures. Add a "contested environment" mode that reduces transmission power and uses directional antenna profiles if available. For future versions, support SDR backends (HackRF, LimeSDR) for true FHSS capability.

### 4.2 Fiber-Optic Tethered Communication

**Citation**: IEEE Spectrum, "How Autonomous Drone Warfare Is Emerging in Ukraine," 2025; Militarnyi.com, PowerHornet.com coverage.
**Links**: https://spectrum.ieee.org/autonomous-drone-warfare | https://powerhornet.com/how-ukrainian-startups-forged-a-new-era-of-gps-free-drone-navigation/

**Summary**: Russia and Ukraine both deploy fiber-optic tethered FPV drones that are completely unjammable. Ukraine's "Shovkopryad" (Silkworm) is a universal fiber-optic module for air, ground, and sea drones. Fiber spools allow multi-kilometer control links immune to all RF jamming. Deployed at scale since mid-2024.

**Practical Feasibility**: LOW for swarms (each drone needs its own fiber), but HIGH for single critical relay drones. A fiber-tethered relay drone could serve as an unjammable bridge between a ground station and a WiFi mesh swarm.

**SDK Recommendation**: Not directly applicable to swarm mesh networking, but document the architecture for a fiber-tethered relay node that bridges ground station to swarm mesh. This is a valuable field deployment pattern.

### 4.3 Autonomous Navigation Without GPS

**Citation**: OKSI.ai, "OMNInav: A Breakthrough in GPS-Denied Navigation for UAS," 2025.
**Link**: https://oksi.ai/omninav-gps-denied-navigation/

**Citation**: ModalAI, "VIO Development Drones," 2024-2025.
**Link**: https://www.modalai.com/pages/vio-drone

**Summary**: Visual-Inertial Odometry (VIO) fuses camera and IMU data for GPS-free navigation. ModalAI's VOXL 2 runs VIO onboard at >30 Hz. Ukrainian companies (NORDA Dynamics and others) have developed AI-powered terrain-matching systems that compare live video against pre-loaded 3D maps for GPS-denied strike missions.

**Citation**: Palantir, "Visual Navigation for Drones," 2025.
**Link**: https://blog.palantir.com/the-future-of-drone-navigation-7236075fdedf

**Summary**: Palantir/DJI-backed approaches use map-matching (visual comparison against satellite imagery) for GPS-denied navigation. Pittsburgh-based Swan and Auterion are partnering with Ukrainian attack-drone makers under the DOD's Artemis project to build GPS-denied navigation by end of FY2025.

**Practical Feasibility**: HIGH for VIO (PX4 supports it natively via VOXL 2 or similar). MEDIUM for terrain matching (requires pre-loaded maps and significant compute).

**SDK Recommendation**: Integrate VIO as a primary position source alongside GPS. Support PX4's existing VIO interfaces (MAVLink VISION_POSITION_ESTIMATE). Add a GPS-denied mode that switches to VIO-only with appropriate safety margins and swarm behavior adjustments.

### 4.4 Cognitive Radio for Dynamic Spectrum Access

**Citation**: Bhardwaj, A. et al., "Cognitive Radio and Dynamic TDMA for efficient UAVs swarm communications," *Computer Networks*, 2021.
**Link**: https://www.sciencedirect.com/science/article/abs/pii/S1389128621002929

**Summary**: Ground Control Station acts as central coordinator for spectrum allocation. CR and SDR are used to select, allocate, and share available frequencies using Dynamic TDMA. The GCS handles bandwidth allocation for all UAVs in its coverage zone.

**Citation**: DTIC, "Cognitive Radio Clustering Algorithm for Swarms," US Department of Defense, 2023.
**Link**: https://apps.dtic.mil/sti/trecms/pdf/AD1200510.pdf

**Summary**: Military research on CR clustering for swarms. Machine learning-based adaptive channel selection reduces latency and enhances link resilience. Proposes decentralized spectrum sensing where each drone contributes to a shared spectrum map.

**Practical Feasibility**: LOW for near-term. Requires SDR hardware and significant computational resources. Regulatory issues in civilian spectrum.

**SDK Recommendation**: Long-term research item. For now, implement multi-channel awareness -- the SDK should be able to detect congested channels and switch autonomously within legal ISM bands.

---

## 5. Consensus Under Communication Constraints

### 5.1 SwarmRaft -- Crash-Fault-Tolerant Consensus for Drones

**Citation**: SwarmRaft, "Leveraging Consensus for Robust Drone Swarm Coordination in GNSS-Degraded Environments," *arXiv:2508.00622*, August 2025. Also published in *IEEE Internet of Things Journal*.
**Link**: https://arxiv.org/html/2508.00622v2

**Summary**: Adapts the Raft consensus algorithm for lightweight, crash-tolerant decision-making in resource-constrained aerial swarms. Uses peer-to-peer distance measurements + consensus + Byzantine-resilient evaluation to detect and correct malicious or faulty position reports. Unlike heavy BFT protocols, SwarmRaft is designed for the CPU/memory constraints of flight controllers.

**Practical Feasibility**: HIGH. Raft is well-understood and has many open-source implementations. The adaptation for drones addresses real deployment constraints.

**SDK Recommendation**: Implement SwarmRaft or a similar lightweight consensus protocol for swarm state agreement (leader election, mission waypoint confirmation, emergency votes). This is a critical building block.

### 5.2 Byzantine Fault Tolerance for UAV Swarms

**Citation**: DTPBFT, "A Dynamic and Highly Trusted PBFT Algorithm for UAV Swarm," *Journal of Computer Networks*, 2024.
**Link**: https://www.sciencedirect.com/science/article/pii/S1389128624004341

**Summary**: DTPBFT achieves 0.24 second consensus time with 200 UAVs, demonstrating scalability without communication congestion. Uses dynamic trust scoring to exclude potentially compromised nodes from consensus.

**Citation**: Springer, "Reputation-Enhanced Practical Byzantine Fault Tolerance Algorithm for Node Capture Attacks on UAV Networks," 2025.
**Link**: https://link.springer.com/article/10.1007/s43926-025-00164-y

**Summary**: RePA adds reputation scoring to PBFT to mitigate node capture attacks (physical compromise of a drone leading to injection of malicious messages). Trust values are computed from historical behavior and used to weight votes.

**Practical Feasibility**: MEDIUM. Full BFT is computationally expensive for small flight controllers, but feasible on companion computers (Raspberry Pi, Jetson Nano). DTPBFT's 0.24s consensus at 200 nodes is promising.

**SDK Recommendation**: Implement a tiered approach: lightweight crash-fault-tolerance (SwarmRaft) on flight controllers, full BFT (DTPBFT-style) on companion computers for critical decisions. Support configurable fault tolerance level.

### 5.3 Time Synchronization Across Swarm Members

**Citation**: ScienceDirect, "High-precision Time Synchronization Algorithm for UAV Ad Hoc Networks based on Bidirectional Pseudo-range Measurements," 2024.
**Link**: https://www.sciencedirect.com/science/article/pii/S1570870523002469

**Summary**: Fully distributed time sync algorithm for multi-hop dynamic ad hoc networks. Uses bidirectional pseudo-range measurements (similar to how GPS works but between drones) to compute clock offsets without requiring a central time server.

**Citation**: Bettstetter, C. et al., "One Time for All: Synchronizing Time in Drone Swarms," University of Klagenfurt.
**Link**: https://bettstetter.com/one-time-for-all/

**Summary**: Bio-inspired synchronization based on firefly pulse coupling. Drones achieve synchronization without centralized control by adjusting their clocks based on received timing pulses from neighbors. Converges even with packet loss and variable network delays.

**Citation**: Swarm-Sync framework, "A Distributed Global Time Synchronization Framework for Swarm Robotic Systems," *ScienceDirect*.
**Link**: https://www.sciencedirect.com/science/article/abs/pii/S1574119217303735

**Summary**: Swarm-Sync provides a distributed global time synchronization framework achieving microsecond-level precision. Uses cluster heads for hierarchical synchronization with intermediate drones bridging clusters.

**Practical Feasibility**: HIGH. Time synchronization is essential for coordinated maneuvers, sensor fusion, and TDMA-based communication. PTP (Precision Time Protocol, IEEE 1588) provides a starting point, with drone-specific enhancements for wireless networks.

**SDK Recommendation**: Implement distributed time sync using a hybrid approach: PTP-based sync when a ground station is reachable, firefly-inspired peer sync when disconnected. Target microsecond-level accuracy for sensor fusion, millisecond-level for coordinated maneuvers.

---

## 6. Starlink/LTE/5G for Drone BVLOS

### 6.1 LTE/4G for Drone Operations

**Citation**: PMC, "Experimental Study on LTE Mobile Network Performance Parameters for Controlled Drone Flights," 2024.
**Link**: https://pmc.ncbi.nlm.nih.gov/articles/PMC11511506/

**Citation**: MDPI Drones, "Real-Time Long-Range Control of an Autonomous UAV Using 4G LTE Network," 2025.
**Link**: https://www.mdpi.com/2504-446X/9/12/812

**Summary**: Flight tests demonstrate stable remote control over LTE with average control delay under 150 ms. Video streaming at 640x480. LTE bandwidth ranges from 3-55 Mbps depending on tower proximity and congestion. Farthest test: 4,200 km from UAV to operator. LTE is viable for command-and-control BVLOS but uplink data rate limits high-quality video streaming.

**Practical Feasibility**: HIGH. LTE modems are small, cheap, and widely available. Coverage gaps remain the main limitation for rural/remote BVLOS.

### 6.2 5G for Drone Operations

**Citation**: PMC, "5G-enabled UAVs for Energy-efficient Opportunistic Networking," 2024.
**Link**: https://pmc.ncbi.nlm.nih.gov/articles/PMC11237935/

**Summary**: 5G provides ultra-low latency (<10ms) and high bandwidth for real-time drone control, HD video streaming, and multi-drone coordination. However, 5G coverage is urban-centric, and mmWave 5G has very limited range at altitude due to lack of ground reflections.

**Practical Feasibility**: MEDIUM. 5G offers excellent performance where available, but coverage is limited. Sub-6GHz 5G is more practical for drones than mmWave.

### 6.3 Starlink for Drone BVLOS

**Citation**: FAA BAA004, "Conducting Extended BVLOS Operations in Challenging Terrain," uAvionix/FAA, 2024.
**Link**: https://www.faa.gov/uas/programs_partnerships/BAA/BAA004-uAvionix-Conducting-Extended-BVLOS-Operations-in-challenging-terrain.pdf

**Summary**: FAA-sponsored demonstration integrating LTE, C-Band radio, and Starlink into a unified C2 link system. Successfully tested Starlink LEO for SATCOM on a Watts Prism quadcopter in Montana. The Link Executive Manager (LEM) dynamically selects the best available link.

**Citation**: DroneDJ, "Event38 Adding SpaceX Starlink to Drones for BVLOS Flights," August 2024.
**Link**: https://dronedj.com/2024/08/12/event38-adding-spacex-starlink-to-drones-for-bvlos-flights/

**Summary**: Event38 is integrating Starlink terminals into fixed-wing drones for BVLOS survey operations. Key challenge: Starlink Mini terminal weight (~1.1 kg) and power draw (~40W) limit integration to larger platforms.

**Citation**: Ground Control, "Drone Satcoms: Power, Payload & Performance," 2025.
**Link**: https://www.groundcontrol.com/blog/satellite-connectivity-drones-faqs/

**Summary**: Starlink LEO latency: typically 500-1,500 ms round-trip for IP-based services. This is adequate for supervisory control but marginal for real-time swarm coordination. Beam switching (July 2025) allows terminals to maintain connections across multiple satellites, improving reliability during movement.

**Citation**: Militarnyi.com, "Blyskavka UAV Can Be Controlled via Starlink," 2025.
**Link**: https://militarnyi.com/en/news/blyskavka-uav-can-be-controlled-starlink/

**Summary**: Ukrainian military drones (Blyskavka) now support Starlink, fiber optics, and LTE as interchangeable control links, demonstrating the hybrid multi-link approach in combat.

**Practical Feasibility**: MEDIUM. Starlink terminals are still heavy/power-hungry for small drones. Excellent for large fixed-wing platforms or as a ground station backhaul. Latency is too high for tight swarm formation flying but fine for supervisory control.

**SDK Recommendation**: Implement a multi-link manager that can use LTE, WiFi, LoRa, and Starlink simultaneously, selecting the best available link per message type. Design the swarm to be autonomous during high-latency periods (Starlink) and accept supervisory commands when they arrive. This "autonomy with supervision" architecture is critical for BVLOS.

---

## 7. Multi-Drone Relative Positioning Without GPS

### 7.1 UWB Ranging Between Drones

**Citation**: Li, S. et al., "Onboard Ranging-based Relative Localization and Stability for Lightweight Aerial Swarms," *arXiv:2003.05853v3* (extended version, updated 2024).
**Link**: https://arxiv.org/html/2003.05853v3

**Summary**: First fully autonomous onboard relative localization system on a team of 13 Crazyflie drones. Uses many-to-many UWB protocol for efficient distance computation. EKF-based relative estimator achieves <0.2m position error at 16 Hz update rate. Code is open-source.

**Citation**: Bitcraze, "Ultra-Wideband Swarm Ranging," 2021-2024.
**Link**: https://www.bitcraze.io/2021/06/ultra-wideband-swarm-ranging/

**Summary**: Open-source UWB swarm ranging protocol for Crazyflie platforms. The protocol is simple, efficient, adaptive, robust, and scalable. 25-second flight test with 3 drones showed mean absolute error of ~0.03 meters.

**Citation**: Scientific Data (Nature), "Dataset for UWB Cooperative Navigation and Positioning of UAV Cluster," 2025.
**Link**: https://www.nature.com/articles/s41597-025-04808-0

**Summary**: Public dataset for UWB cooperative positioning research, collected under different flight formations in indoor and outdoor environments. Valuable for benchmarking relative localization algorithms.

**Practical Feasibility**: HIGH. UWB modules (DW1000/DW3000) are available for ~$10-20 per drone. The Crazyflie implementation provides a proven open-source starting point. Scalability to larger drones requires adapting the protocol for longer ranges and different UWB hardware.

**SDK Recommendation**: Integrate UWB-based relative localization as a core module. Support Decawave DW3000 chipset. Use the Bitcraze protocol as a starting point, extending it with the EKF-based approach from the 13-drone paper. This enables GPS-denied swarm operation.

### 7.2 Visual Relative Localization (AprilTags, LEDs, UVDAR)

**Citation**: arXiv:2412.02393, "Bio-inspired Visual Relative Localization for Large Swarms of UAVs," December 2024.
**Link**: https://arxiv.org/html/2412.02393v1

**Summary**: UVDAR (Ultraviolet Direction and Ranging) system uses UV LED markers and UV-sensitive cameras for inter-drone detection. Provides bearing and range to neighbors without infrastructure. Bio-inspired approach scales to large swarms because each drone only needs to detect nearby neighbors.

**Citation**: Various AprilTag-based localization papers, 2024-2025.
**Links**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4815151

**Summary**: AprilTags provide 6-DOF pose estimation from a single camera image when tag dimensions are known. Limited to short range (typically <10m for reliable detection) and requires line of sight. Useful for precision landing, docking, and close-formation operations.

**Practical Feasibility**: MEDIUM. UVDAR requires specialized UV LEDs and cameras. AprilTags work with standard cameras but limited range. Both are complementary to UWB (visual for bearing, UWB for range).

**SDK Recommendation**: Support AprilTag-based relative pose estimation for close-proximity operations (landing, docking, formation). Investigate UVDAR for medium-range visual tracking. Fuse visual bearing estimates with UWB range measurements for robust relative localization.

### 7.3 Cooperative SLAM for Swarms

**Citation**: ETH Zurich, "Fully Onboard SLAM for Distributed Mapping with a Swarm of Nano-Drones," *arXiv:2309.03678*, 2023-2024.
**Link**: https://arxiv.org/abs/2309.03678 | https://github.com/ETH-PBL/Nano_Swarm_Mapping

**Summary**: Distributed mapping on nano-UAVs (35g payload limit). Achieves 12 cm mapping accuracy over 180 m^2. Total system RAM: ~50 kB. Mapping time inversely proportional to swarm size. Uses GAP9 SoC for onboard processing. Fully open-source.

**Citation**: MISTLab, "Swarm-SLAM: Sparse Decentralized Collaborative SLAM for Multi-Robot Systems," *arXiv:2301.06230*, 2023-2024.
**Link**: https://github.com/MISTLab/Swarm-SLAM

**Summary**: ROS 2-compatible decentralized collaborative SLAM framework. Supports LiDAR and stereo visual SLAM. Each robot maintains a local map and exchanges sparse descriptors with neighbors for loop closure. Designed for bandwidth-constrained inter-robot communication.

**Citation**: HKUST, "D2SLAM: Decentralized and Distributed Collaborative Visual-Inertial SLAM System for Aerial Swarm," 2024.
**Link**: https://github.com/HKUST-Aerial-Robotics/D2SLAM

**Summary**: Visual-inertial SLAM specifically for aerial swarms. Decentralized architecture -- no central server required. Each drone runs VIO locally and exchanges compressed map features with neighbors for global consistency.

**Citation**: Springer, "Distributed UAV Swarm Collaborative SLAM Based on Visual-Inertial-Ranging Measurement," 2025.
**Link**: https://link.springer.com/chapter/10.1007/978-981-96-2220-7_18

**Summary**: Combines VIO with UWB ranging for collaborative SLAM. UWB accelerates initialization and provides scale reference for visual systems. Optimized inter-UAV communication for real-time operation.

**Practical Feasibility**: MEDIUM-HIGH. Swarm-SLAM and D2SLAM are open-source and ROS 2 compatible. Computational requirements are significant for full SLAM, but the nano-drone paper shows it's possible even on extremely constrained hardware with the right algorithms.

**SDK Recommendation**: Integrate Swarm-SLAM or D2SLAM as an optional cooperative mapping module. For constrained platforms, offer the ETH nano-drone approach. The key insight is that drones should exchange compressed map features, not raw sensor data, to conserve bandwidth.

---

## 8. 2024-2026 State of the Art

### 8.1 Semantic Communication for Swarms

**Citation**: arXiv:2508.12043, "Talk Less, Fly Lighter: Autonomous Semantic Compression for UAV Swarm Communication via LLMs," August 2025.
**Link**: https://arxiv.org/abs/2508.12043

**Summary**: Evaluates LLM-driven semantic compression for swarm communication. Instead of transmitting raw data, drones encode task-relevant semantics, achieving significant bandwidth reduction while preserving mission-critical information. Tested with 9 mainstream LLMs.

**Citation**: arXiv:2503.00053, "AI and Semantic Communication for Infrastructure Monitoring in 6G-Driven Drone Swarms," February 2025.
**Link**: https://arxiv.org/abs/2503.00053

**Summary**: Proposes 6G-enabled swarm system integrating URLLC, edge AI, and semantic communication. Each drone captures multimodal sensor data, encodes it via AI-based semantic encoder, transmits wirelessly, and decodes using shared knowledge base. Represents the convergence of AI and communication for next-generation swarms.

### 8.2 LLM/Agentic AI for Swarm Coordination

**Citation**: arXiv:2501.02341, "UAVs Meet LLMs: Overviews and Perspectives Toward Agentic Low-Altitude Mobility," January 2025.
**Link**: https://arxiv.org/html/2501.02341v1

**Citation**: arXiv:2506.08045, "UAVs Meet Agentic AI: A Multidomain Survey," June 2025.
**Link**: https://arxiv.org/html/2506.08045v1

**Summary**: Emerging paradigm where LLMs serve as high-level mission planners for drone swarms, translating natural language mission descriptions into task allocations and coordination strategies. The agentic UAV architecture consists of four layers: perception, cognition, control, and communication.

### 8.3 Comprehensive Surveys (2025)

**Citation**: Springer, "UAV Swarms: Research, Challenges, and Future Directions," January 2025.
**Link**: https://link.springer.com/article/10.1186/s44147-025-00582-3

**Summary**: Comprehensive survey covering coordinated path planning, task assignment, formation control, and security. AI and ML integration for decision-making and adaptability is the dominant trend.

**Citation**: MDPI Drones, "A Survey on UxV Swarms and the Role of Artificial Intelligence," October 2025.
**Link**: https://www.mdpi.com/2504-446X/9/10/700

**Summary**: Examines swarms from intelligence, communication, and security perspectives. AI is positioned as the key technological enabler for scalable swarm operations.

**Citation**: Premier Science, "Data Transmission Between a Drone Swarm and Ground Base: Modern Methods and Technologies," October 2025.
**Link**: https://premierscience.com/pjs-25-1302/

**Summary**: Narrative review of 2015-2024 literature on swarm-to-ground communication. Covers FANETs, mesh protocols, cellular links, and hybrid architectures. Concludes that hybrid multi-link approaches are the most resilient.

### 8.4 Key 2024-2026 Trends

1. **Hybrid multi-link communication** (LoRa + WiFi + LTE + Starlink) with intelligent link selection is becoming the standard architecture.
2. **AI/ML permeation**: reinforcement learning for routing, anti-jamming, and spectrum access; LLMs for mission planning; semantic communication for bandwidth reduction.
3. **GPS-denied operation** driven by Ukraine conflict lessons: VIO, terrain matching, UWB relative positioning are moving from research to production.
4. **Lightweight BFT consensus** (SwarmRaft, DTPBFT) making distributed agreement practical on resource-constrained platforms.
5. **Cooperative SLAM** frameworks becoming open-source and ROS 2 native, enabling shared spatial awareness without central servers.
6. **Fiber-optic tethered drones** proving the concept that unjammable communication links change battlefield calculus.

---

## 9. SDK Upgrade Recommendation Summary

### Priority 1 -- Core Communication (Implement First)

| Feature | Based On | Effort | Impact |
|---------|----------|--------|--------|
| ChaCha20 encryption for MAVLink | Al-Tameemi 2025 | Medium | Critical for security |
| BATMAN-adv mesh auto-formation | Multiple mesh studies | Low | Foundation for multi-drone |
| Dual-radio architecture (LoRa + WiFi) | Davoli 2021 | High | Enables range + bandwidth |
| Message priority queue | Gap in literature | Medium | Bandwidth management |
| Compact swarm-status message | Pascarella 2016 | Low | Reduces bandwidth per drone |

### Priority 2 -- Resilient Positioning (Implement Second)

| Feature | Based On | Effort | Impact |
|---------|----------|--------|--------|
| UWB relative localization | Li 2024, Bitcraze | Medium | GPS-denied capability |
| VIO integration (PX4 native) | ModalAI, OKSI | Low | GPS backup |
| Distributed time sync | Bidirectional pseudo-range paper | Medium | Coordinated maneuvers |
| SwarmRaft consensus protocol | SwarmRaft 2025 | Medium | Fault-tolerant decisions |

### Priority 3 -- Advanced Capabilities (v2 of SDK)

| Feature | Based On | Effort | Impact |
|---------|----------|--------|--------|
| Geographic routing module | UF-GPSR, GPSR+AODV | High | Large swarm scalability |
| Multi-link manager (LTE/Starlink) | FAA BAA004, hybrid research | High | BVLOS capability |
| Cooperative SLAM integration | Swarm-SLAM, D2SLAM | High | Shared spatial awareness |
| Store-and-forward DTN buffer | DTN literature | Medium | Intermittent connectivity |
| WiFi channel rotation (basic anti-jam) | FHSS literature | Low | Basic EW resilience |

### Priority 4 -- Research/Future (Track but Don't Implement Yet)

| Feature | Based On | Maturity |
|---------|----------|----------|
| Semantic communication / LLM compression | arXiv 2508.12043 | Early research |
| Cognitive radio / dynamic spectrum access | Bhardwaj 2021 | Needs SDR hardware |
| Full BFT consensus (DTPBFT) | DTPBFT 2024 | Needs companion computer |
| QRNG-enhanced FHSS | Chrysovalantis 2024 | Needs specialized hardware |
| LLM-based mission planning | arXiv 2501.02341 | Early research |

---

## Key Sources

### Protocol and Security
- [MAVLink Survey (arXiv 1906.10641)](https://arxiv.org/pdf/1906.10641)
- [MAVSec (arXiv 1905.00265)](https://arxiv.org/abs/1905.00265)
- [ChaCha20 for MAVLink (arXiv 2504.20626)](https://arxiv.org/html/2504.20626v1)
- [UAV Security Survey 2026 (arXiv 2601.08229)](https://arxiv.org/pdf/2601.08229)
- [MAVLink Protocol Overview](https://mavlink.io/en/about/overview.html)

### Mesh Networking
- [Hybrid LoRa-802.11s Mesh (MDPI)](https://www.mdpi.com/2504-446X/5/2/26)
- [LoRa FANET Survey (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10007589/)
- [LoRa FANET (IEEE)](https://ieeexplore.ieee.org/document/9491655/)
- [BATMAN Unpacked (TU Munich)](https://www.net.in.tum.de/fileadmin/TUM/NET/NET-2024-09-1/NET-2024-09-1_02.pdf)
- [802.11s Custom Metrics (ACM)](https://dl.acm.org/doi/10.1145/3360774.3368197)
- [802.11s 3D Extension (ACM)](https://dl.acm.org/doi/10.1145/3389400.3389406)
- [Mesh Secure (arXiv)](https://arxiv.org/pdf/2108.13154)

### Geographic Routing
- [UF-GPSR (Wiley)](https://onlinelibrary.wiley.com/doi/abs/10.1002/ett.4813)
- [GPSR+AODV (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S1319157824001551)
- [MP-QGRD Geographic Routing (MDPI)](https://www.mdpi.com/2079-9292/14/7/1456)
- [RL Geographic Routing (MDPI)](https://www.mdpi.com/2504-446X/7/6/387)
- [FANET Routing Strategies Survey (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S1110016824010469)

### Anti-Jamming and EW
- [QRNG FHSS (MDPI)](https://www.mdpi.com/1999-5903/16/11/412)
- [Agent Anti-Jamming Survey (arXiv 2508.11687)](https://arxiv.org/html/2508.11687v1)
- [EW Cyberattacks Survey (arXiv 2504.07358)](https://arxiv.org/html/2504.07358v1)
- [Ukraine GPS-Free Navigation (PowerHornet)](https://powerhornet.com/how-ukrainian-startups-forged-a-new-era-of-gps-free-drone-navigation/)
- [Autonomous Drone Warfare (IEEE Spectrum)](https://spectrum.ieee.org/autonomous-drone-warfare)
- [Cognitive Radio UAV (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S1389128621002929)

### Consensus and Synchronization
- [SwarmRaft (arXiv 2508.00622)](https://arxiv.org/html/2508.00622v2)
- [DTPBFT (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S1389128624004341)
- [RePA BFT (Springer)](https://link.springer.com/article/10.1007/s43926-025-00164-y)
- [Time Sync Bidirectional (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S1570870523002469)
- [Firefly Time Sync (Bettstetter)](https://bettstetter.com/one-time-for-all/)
- [Swarm-Sync (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S1574119217303735)

### Cellular and Satellite
- [LTE Drone Experiments (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11511506/)
- [LTE Long-Range UAV Control (MDPI)](https://www.mdpi.com/2504-446X/9/12/812)
- [FAA Starlink BVLOS Demo (FAA)](https://www.faa.gov/uas/programs_partnerships/BAA/BAA004-uAvionix-Conducting-Extended-BVLOS-Operations-in-challenging-terrain.pdf)
- [Event38 Starlink (DroneDJ)](https://dronedj.com/2024/08/12/event38-adding-spacex-starlink-to-drones-for-bvlos-flights/)
- [Drone Satcoms FAQ (Ground Control)](https://www.groundcontrol.com/blog/satellite-connectivity-drones-faqs/)

### Relative Positioning and SLAM
- [UWB Relative Localization 13 Drones (arXiv)](https://arxiv.org/html/2003.05853v3)
- [Bitcraze UWB Swarm Ranging](https://www.bitcraze.io/2021/06/ultra-wideband-swarm-ranging/)
- [UWB Dataset (Nature)](https://www.nature.com/articles/s41597-025-04808-0)
- [UVDAR Bio-Inspired Visual Localization (arXiv)](https://arxiv.org/html/2412.02393v1)
- [Nano Swarm Mapping (GitHub/arXiv)](https://github.com/ETH-PBL/Nano_Swarm_Mapping)
- [Swarm-SLAM (GitHub)](https://github.com/MISTLab/Swarm-SLAM)
- [D2SLAM (GitHub)](https://github.com/HKUST-Aerial-Robotics/D2SLAM)
- [VIO-UWB SLAM (Springer)](https://link.springer.com/chapter/10.1007/978-981-96-2220-7_18)
- [Crazyswarm2 (GitHub)](https://github.com/IMRCLab/crazyswarm2)

### State of the Art Surveys (2025-2026)
- [LLM Semantic Compression (arXiv 2508.12043)](https://arxiv.org/abs/2508.12043)
- [6G Semantic Communication (arXiv 2503.00053)](https://arxiv.org/abs/2503.00053)
- [Agentic UAVs Survey (arXiv 2506.08045)](https://arxiv.org/html/2506.08045v1)
- [UAV Swarms Survey 2025 (Springer)](https://link.springer.com/article/10.1186/s44147-025-00582-3)
- [UxV Swarms + AI Survey (MDPI)](https://www.mdpi.com/2504-446X/9/10/700)
- [Swarm-Ground Transmission Review (Premier Science)](https://premierscience.com/pjs-25-1302/)
