# Safety, Verification, and Fault Tolerance for Multi-Drone Systems
## Comprehensive Literature Review

**Date:** 2026-03-26
**Purpose:** Ensure the Drone Swarm Orchestrator (DSO) open-source SDK is safe for real-world operations.
**Scope:** 9 domains -- formal verification, control barrier functions, geofencing, fault detection, graceful degradation, pre-flight/in-flight checks, emergency protocols, safety standards, and human-in-the-loop safety.

---

## Table of Contents

1. [Formal Verification of Drone Swarm Behavior](#1-formal-verification-of-drone-swarm-behavior)
2. [Control Barrier Functions (CBF) for Safety](#2-control-barrier-functions-cbf-for-safety)
3. [Geofencing Algorithms](#3-geofencing-algorithms)
4. [Fault Detection and Isolation (FDI)](#4-fault-detection-and-isolation-fdi)
5. [Graceful Degradation](#5-graceful-degradation)
6. [Pre-Flight and In-Flight Safety Checks](#6-pre-flight-and-in-flight-safety-checks)
7. [Emergency Protocols](#7-emergency-protocols)
8. [Safety Standards and Certification](#8-safety-standards-and-certification)
9. [Human-in-the-Loop Safety](#9-human-in-the-loop-safety)
10. [Implementation Roadmap Summary](#10-implementation-roadmap-summary)

---

## 1. Formal Verification of Drone Swarm Behavior

### 1.1 Model Checking for Multi-Agent Systems

**Citation:** Luckcuck, M., Farrell, M., Dennis, L., Dixon, C., Fisher, M. (2019). "Formal Specification and Verification of Autonomous Robotic Systems: A Survey." *ACM Computing Surveys*, 52(5).
- **Summary:** Comprehensive survey of formal methods applied to autonomous robotic systems. Covers temporal logic specifications (LTL, CTL, PCTL*), model checking with NuSMV and PRISM, and theorem proving approaches. Identifies that Discrete-Time Markov Chains (DTMCs) with PCTL* specifications verified via PRISM are particularly suited to probabilistic multi-agent behavior.
- **Applicability to DSO:** Directly applicable. Swarm coordination protocols (formation keeping, task allocation consensus) can be modeled as finite-state systems and verified against safety/liveness properties before deployment.
- **Implementation Recommendation:** Model the DSO state machine for swarm coordination in UPPAAL timed automata. Verify properties such as "no two drones occupy the same airspace cell simultaneously" and "all drones eventually return to base on mission abort." Start with offline verification of the protocol design; graduate to runtime checks.

**Citation:** Zhou et al. (2025). "A Comprehensive Survey of UPPAAL-Assisted Formal Modeling and Verification." *Software: Practice and Experience*, Wiley.
- **Summary:** Systematic review of 200+ papers using UPPAAL across cyber-physical systems, network protocols, and multi-agent systems. UPPAAL's timed automata formalism handles real-time constraints naturally -- critical for drone systems where timing guarantees matter (e.g., heartbeat intervals, command latency).
- **Applicability to DSO:** UPPAAL can model the DSO communication protocol timing, verifying that mesh network message delivery meets real-time deadlines.
- **Implementation Recommendation:** Use UPPAAL to verify the mesh networking protocol handles message ordering and timing under various network degradation scenarios.

**Citation:** ScienceDirect (2025). "Modeling and Verifying Resources and Capabilities of Ubiquitous Scenarios for UAV Swarm." *Journal of Systems and Software*.
- **Summary:** Applies UPPAAL model checking to UAV swarm scenarios (highway inspection), transforming mission specifications into timed automata to verify resource constraints and capability matching.
- **Applicability to DSO:** Directly models the kind of mission planning and resource management DSO needs.
- **Implementation Recommendation:** Create UPPAAL models of DSO mission types (survey, monitoring, delivery) and verify resource adequacy before mission launch.

### 1.2 Runtime Verification

**Citation:** Desai, A., Dreossi, T., Seshia, S.A. (2017). "Combining Model Checking and Runtime Verification for Safe Robotics." *RV 2017*, UC Berkeley.
- **Summary:** Presents DRONA, a framework combining offline model checking with online runtime monitors. The runtime monitor checks safety properties during execution and can trigger corrective actions. Key insight: offline verification covers design-time properties; runtime verification catches environment-induced violations.
- **Applicability to DSO:** Core architecture pattern for DSO safety layer. Design-time verification ensures protocol correctness; runtime monitors catch real-world deviations.
- **Implementation Recommendation:** Implement a runtime monitor service in DSO that checks safety invariants at each control loop iteration (10-50 Hz). Monitor properties: minimum separation distance, geofence containment, battery reserves, communication link quality.

**Citation:** Torens, C. et al. (2024). "Monitoring Unmanned Aircraft: Specification, Integration, and Lessons-Learned." *arXiv:2404.12035*.
- **Summary:** Reports on integrating runtime monitors into Volocopter eVTOL aircraft. The monitor recognizes hazardous situations and system faults in real-time. Development followed aeronautical safety standards. Key lesson: monitor instrumentation must collect GPS coordinates, attitude, and mission status with minimal overhead.
- **Applicability to DSO:** Provides a real-world template for how to instrument drone telemetry for runtime monitoring.
- **Implementation Recommendation:** Define a telemetry schema that runtime monitors consume. Include GPS, IMU, battery, motor RPM, and inter-drone distances. Implement both online (real-time alert) and offline (post-flight analysis) monitoring modes.

**Citation:** Dinh, H.T. et al. (2024). "Runtime Verification and Field Testing for ROS-Based Robotic Systems." *arXiv:2404.11498*.
- **Summary:** Covers runtime verification for ROS-based robots, including UAVs. Reactive synthesis generates monitors from specified system properties. Addresses both online monitoring (checking on-the-fly) and offline monitoring (post-mortem analysis).
- **Applicability to DSO:** DSO uses ROS2-compatible interfaces; this paper provides direct guidance on integrating monitors into the ROS message pipeline.
- **Implementation Recommendation:** Build DSO monitors as ROS2 nodes that subscribe to relevant topics and publish safety verdicts. Use ROSMonitoring or a similar framework.

**Citation:** Osama, M. et al. (2024). "Safe Networked Robotics with Probabilistic Verification." *arXiv:2302.09182*.
- **Summary:** Introduces a "shield" -- a runtime monitor constructed offline that disallows unsafe actions in networked robots, accounting for communication delays. Uses probabilistic model checking to handle uncertainty.
- **Applicability to DSO:** Mesh network communication in DSO will have variable latency. This shielding approach can prevent unsafe commands from propagating through the swarm.
- **Implementation Recommendation:** Implement a command validation shield that filters swarm commands through safety checks before execution, accounting for worst-case communication delay.

### 1.3 Tool Recommendations for DSO

| Tool | Best For | Integration Path |
|------|----------|-----------------|
| UPPAAL | Timed protocol verification | Offline, CI/CD pipeline |
| PRISM | Probabilistic swarm behavior | Offline, mission planning |
| NuSMV | Finite-state safety properties | Offline, design validation |
| ROSMonitoring | Runtime property checking | Online, ROS2 node |

---

## 2. Control Barrier Functions (CBF) for Safety

### 2.1 Foundational Theory

**Citation:** Ames, A.D., Coogan, S., Egerstedt, M., Notomista, G., Sreenath, K., Tabuada, P. (2019). "Control Barrier Functions: Theory and Applications." *European Control Conference*.
- **Summary:** Defines Control Barrier Functions as Lyapunov-like functions that guarantee forward invariance of a safe set. If the system state starts in the safe region and the CBF constraint is enforced at every timestep, the state is guaranteed to remain safe. The CBF constraint is enforced via a Quadratic Program (QP) that minimally modifies the nominal control input.
- **Applicability to DSO:** CBFs provide mathematically provable collision avoidance -- the strongest safety guarantee possible for the inter-drone separation problem.
- **Implementation Recommendation:** Implement a CBF-QP safety filter as a layer between the DSO path planner and the low-level flight controller. The filter takes the desired velocity command and outputs the closest safe velocity that maintains minimum separation from all neighbors.

### 2.2 Multi-Robot CBF Applications

**Citation:** Chen, Y., Jankovic, M., Santillo, M., Ames, A.D. (2021). "Guaranteed Obstacle Avoidance for Multi-Robot Operations with Limited Actuation." Caltech.
- **Summary:** Develops a backup-strategy-based CBF approach for multiple agents with limited actuation. The decentralized CBF-QP is always feasible when h(x) >= 0. Each agent solves its own local QP considering only nearby agents, making the approach scalable.
- **Applicability to DSO:** Directly applicable to DSO's multi-drone collision avoidance. The decentralized formulation means each drone computes its own safe control independently.
- **Implementation Recommendation:** Each drone maintains a local CBF for every neighbor within sensing range. The QP solves for the safe velocity that respects all pairwise CBF constraints simultaneously. Use OSQP solver for efficiency.

**Citation:** Borrmann, U., Wang, L., Ames, A.D., Egerstedt, M. (2015). "Control Barrier Certificates for Safe Swarm Behavior." *ADHS 2015*, Caltech.
- **Summary:** Extends CBFs to swarm robotics, defining barrier certificates that guarantee collision-free behavior for the entire swarm. Proves that if each agent enforces its local barrier constraint, global safety follows.
- **Applicability to DSO:** Provides the theoretical foundation for DSO's collision avoidance subsystem.
- **Implementation Recommendation:** Use the pairwise barrier certificate formulation: h_ij(x) = ||p_i - p_j||^2 - D_safe^2 >= 0, where D_safe is the minimum allowed separation.

**Citation:** Garg, K., Dawson, C., Li, K., Chuchu, F. (2024). "GCBF+: A Neural Graph Control Barrier Function Framework for Distributed Safe Multi-Agent Control." MIT.
- **Summary:** Uses Graph Neural Networks (GNNs) to learn distributed CBFs that scale to large numbers of agents. The GNN architecture handles variable numbers of neighbors, making it distributed and scalable.
- **Applicability to DSO:** For swarms larger than ~10 drones, hand-designed CBFs become cumbersome. Learned GNN-CBFs can handle heterogeneous swarm sizes.
- **Implementation Recommendation:** Phase 1: implement hand-crafted CBFs for small swarms (3-10). Phase 2: evaluate GCBF+ for larger swarm deployments. The GNN inference is lightweight enough for onboard computation.

**Citation:** Santos, M. et al. (2023). "Safe Multi-Agent Drone Control Using Control Barrier Functions and Acceleration Fields." *Robotics and Autonomous Systems*.
- **Summary:** Combines CBFs with acceleration fields for multi-drone control. The QP provides accelerations with formal guarantees of obstacle avoidance, inter-agent avoidance, and speed/acceleration limits. The optimization is always feasible by proper CBF construction.
- **Applicability to DSO:** Provides a complete collision avoidance pipeline that respects drone dynamics.
- **Implementation Recommendation:** Implement the acceleration-field CBF approach for DSO's formation control mode.

### 2.3 Computational Cost Analysis

**Citation:** Breeden, J., Panagou, D. (2025). "Explicit Control Barrier Function-Based Safety Filters and Their Resource-Aware Computation." *arXiv:2512.10118*.
- **Summary:** Addresses the core challenge: solving a QP at every control loop iteration is expensive for embedded systems. Introduces closed-form CBF solutions by partitioning the state space into regions, each with an analytic solution. This eliminates the need for a QP solver in many timesteps.
- **Applicability to DSO:** Critical for DSO running on companion computers (Raspberry Pi, Jetson Nano). QP solvers may not meet real-time deadlines consistently.
- **Implementation Recommendation:** Start with OSQP-based QP solving at 50 Hz. Profile computational load on target hardware. If QP solving exceeds budget, implement the explicit CBF partition approach for the most common operating regions.

**Citation:** MDPI (2020). "A QP Solver Implementation for Embedded Systems Applied to Control Allocation."
- **Summary:** Benchmarks QP solvers on embedded platforms. OSQP achieves solve times under 1ms for problems with ~20 constraints on ARM Cortex processors.
- **Applicability to DSO:** For a swarm of N drones, each drone's CBF-QP has approximately 2*k constraints (k = number of neighbors within range, typically 3-6). This is well within OSQP's real-time capability.
- **Implementation Recommendation:** Use OSQP as the default QP solver. Target 100 Hz control frequency. For a 6-neighbor CBF-QP, expect ~0.5ms solve time on Jetson Nano.

### 2.4 CBF Implementation Summary for DSO

```
Nominal Controller --> CBF Safety Filter (QP) --> Flight Controller
     (path plan)       (enforce separation)         (PX4/ArduPilot)

CBF constraint: h_ij = ||p_i - p_j||^2 - D_safe^2 >= 0
QP: min ||u - u_nominal||^2  subject to  dh/dt + alpha(h) >= 0 for all neighbors
Solver: OSQP at 50-100 Hz
```

---

## 3. Geofencing Algorithms

### 3.1 Point-in-Polygon and Containment

**Citation:** Narkawicz, A., Munoz, C., Dutle, A. (2019). "A Geofence Violation Prevention Mechanism for Small UAS." NASA Langley, NTRS.
- **Summary:** Presents NASA's approach to geofence enforcement using PolyCARP (Algorithms and Software for Computations with Polygons). PolyCARP provides formally verified algorithms for point-in-polygon testing, collision detection with moving polygons, and resolution/recovery maneuvers. The algorithms are available in Java, C++, and Python.
- **Applicability to DSO:** PolyCARP is open-source, formally verified, and specifically designed for UAS geofencing. This is the gold standard for DSO's geofence implementation.
- **Implementation Recommendation:** Integrate PolyCARP directly into DSO's safety layer. Use it for both keep-in (operational volume) and keep-out (no-fly zones) geofence checking. Run at minimum 10 Hz per drone.

**Citation:** NASA Langley. "PolyCARP: Algorithms and Software for Computations with Polygons." Formal Methods Program.
- **Summary:** PolyCARP provides: (1) point-in-polygon containment testing, (2) collision detection between a moving point and a polygon, (3) resolution vectors to escape/return to polygons, (4) near-miss detection. All algorithms are formally verified using PVS theorem prover.
- **Applicability to DSO:** Every function in PolyCARP maps to a DSO safety requirement.
- **Implementation Recommendation:** Use PolyCARP's containment check for real-time geofence monitoring, collision detection for lookahead geofence violation prediction, and resolution vectors for automatic return-to-fence maneuvers.

### 3.2 Dynamic Geofencing

**Citation:** Pham, H., Smolka, S., Stoller, S., Phan, D., Yang, J. (2021). "A New Approach to Complex Dynamic Geofencing for Unmanned Aerial Vehicles." *arXiv:2110.09453*.
- **Summary:** Introduces dynamic geofencing where boundaries change in real-time (e.g., moving emergency zones, shifting weather cells). Uses 3D flight volumization algorithms to manage airspace compartments. Key challenge: updating geofence databases fast enough for real-time compliance.
- **Applicability to DSO:** DSO must handle dynamic no-fly zones (emergency helicopters, temporary flight restrictions). Static geofences alone are insufficient.
- **Implementation Recommendation:** Implement a geofence subscription service that receives TFR (Temporary Flight Restriction) updates from FAA LAANC or UTM providers. Update the geofence database in real-time and propagate to all swarm members via the mesh network.

**Citation:** Bulusu, V. et al. (2022). "Airspace Geofencing and Flight Planning for Low-Altitude, Urban, Small UAS." *Applied Sciences*, 12(2), 576.
- **Summary:** Develops 3D geofence management with altitude ceiling enforcement for urban UAS operations. Integrates with UTM flight volumization. Addresses the challenge of 3D polygons with minimum and maximum altitude constraints.
- **Applicability to DSO:** Urban swarm operations require 3D geofencing with altitude bands. This paper provides the algorithmic framework.
- **Implementation Recommendation:** Model geofences as 2D polygons with min/max altitude attributes. Check both lateral containment (PolyCARP) and vertical containment (simple range check) at each timestep.

### 3.3 NASA ICAROUS Integration

**Citation:** NASA. "ICAROUS: Integrated Configurable Algorithms for Reliable Operations of Unmanned Systems."
- **Summary:** ICAROUS is NASA's open-source software architecture for UAS that integrates PolyCARP (geofencing), DAIDALUS (detect-and-avoid), and path planning. It uses PolyCARP to constantly monitor for imminent keep-in and keep-out geofence violations based on the current position and velocity of the UAS.
- **Applicability to DSO:** ICAROUS provides a complete, flight-tested, open-source safety architecture. Rather than building geofencing from scratch, DSO can integrate ICAROUS components.
- **Implementation Recommendation:** Evaluate ICAROUS as a dependency for DSO's safety layer. At minimum, extract PolyCARP and DAIDALUS. Ideally, adopt the full ICAROUS architecture as DSO's safety subsystem and extend it for swarm-specific needs.

### 3.4 Performance Requirements for N Drones

| Swarm Size (N) | Geofence Checks/sec | Computation Budget (10 Hz) | Approach |
|----------------|---------------------|---------------------------|----------|
| 1-5 | 50 | 20ms per check | Single-thread PolyCARP |
| 5-20 | 200 | 5ms per check | Bounding-box pre-filter + PolyCARP |
| 20-100 | 1000 | 1ms per check | Spatial index (R-tree) + PolyCARP |
| 100+ | 1000+ | <1ms per check | GPU-accelerated batch checking |

---

## 4. Fault Detection and Isolation (FDI)

### 4.1 Sensor Failure Detection

**Citation:** Baskaya, E. et al. (2022). "UAV Fault Detection Methods, State-of-the-Art." *Drones*, 6(11), 330.
- **Summary:** Comprehensive survey of FDI methods for UAVs. Classifies approaches into model-based (observer, Kalman filter, parity space), data-driven (neural networks, SVM), and hybrid methods. Covers faults in pitot tube, gyro, accelerometer, magnetometer, and GPS. Model-based approaches achieve >95% detection rates with <1s detection latency.
- **Applicability to DSO:** DSO needs sensor FDI on every drone. Model-based methods are preferred for their interpretability and certifiability.
- **Implementation Recommendation:** Implement Extended Kalman Filter (EKF) based sensor fault detection as the primary method. Cross-validate IMU, GPS, barometer, and magnetometer readings. Flag inconsistencies that exceed 3-sigma thresholds.

**Citation:** ScienceDirect (2018). "Fault Detection and Isolation for Unmanned Aerial Vehicle Sensors by Using Extended PMI Filter."
- **Summary:** Applies extended Parametric Model Interference (PMI) filters for sensor FDI on UAVs. Can detect and isolate faults in individual sensors by comparing predicted vs. actual measurements.
- **Applicability to DSO:** Provides a specific algorithm for sensor-level FDI.
- **Implementation Recommendation:** Implement residual-based detection: compute the difference between EKF-predicted and actual sensor readings. When residuals exceed thresholds for a configurable number of consecutive samples, declare a fault and isolate the sensor.

### 4.2 Motor/Actuator Failure Detection

**Citation:** MDPI (2023). "Deep Learning-Based Robust Actuator Fault Detection and Isolation Scheme for Highly Redundant Multirotor UAVs." *Drones*, 7(7), 437.
- **Summary:** Uses LSTM networks for real-time actuator FDI. Achieves >95% sensitivity in detecting and isolating individual motor faults. The framework combines fault detection (is there a fault?) with faulty actuator localization (which motor?).
- **Applicability to DSO:** Motor failure is the most critical actuator fault for multirotors. Fast detection (<100ms) is essential for engaging fault-tolerant control.
- **Implementation Recommendation:** Implement a two-stage motor FDI: (1) fast detection via RPM/current anomaly threshold (within 1 control cycle), (2) isolation via cross-correlation of motor commands vs. achieved RPM.

**Citation:** Springer (2024). "Motor Fault Detection and Isolation for Multi-Rotor UAVs Based on External Wrench Estimation and Recurrent Deep Neural Network." *J. Intelligent & Robotic Systems*.
- **Summary:** Estimates the external wrench (force/torque) on the vehicle from IMU data and compares it with expected values. Deviations indicate motor faults. Uses RNN for robust fault isolation.
- **Applicability to DSO:** Wrench-based detection does not require motor RPM sensors, making it applicable to simpler drone builds.
- **Implementation Recommendation:** As a backup FDI method, implement wrench estimation from IMU data. This provides redundancy if RPM sensors fail.

**Citation:** ScienceDirect (2023). "Real-Time Propeller Fault Detection for Multirotor Drones Based on Vibration Data Analysis."
- **Summary:** Detects propeller damage through vibration signature analysis using onboard accelerometers. Can distinguish between balanced, chipped, and cracked propellers before complete failure.
- **Applicability to DSO:** Predictive fault detection -- catch degrading propellers before they fail in flight.
- **Implementation Recommendation:** Implement vibration spectrum analysis during hover or steady-state flight segments. Alert if vibration signatures deviate from calibrated baselines. This enables pre-emptive landing before catastrophic failure.

### 4.3 Communication Failure Handling

**Citation:** Stojcsics, D. et al. (2020). "UAV Swarm Exploration With Byzantine Fault Tolerance." *IEEE Conference*.
- **Summary:** Addresses communication failures in UAV swarms, integrating Byzantine fault tolerance into the exploration algorithm. Uses the weighted-mean-subsequence-reduced (W-MSR) consensus algorithm to handle up to f Byzantine agents in a swarm of 3f+1 agents.
- **Applicability to DSO:** Communication link loss or corruption is the most common swarm failure mode. DSO needs Byzantine-resilient consensus.
- **Implementation Recommendation:** Implement the W-MSR algorithm for all consensus decisions (formation updates, task allocation, emergency votes). Require 3f+1 participating drones for consensus on critical decisions.

**Citation:** Frontiers (2020). "Blockchain Technology Secures Robot Swarms: A Comparison of Consensus Protocols and Their Resilience to Byzantine Robots."
- **Summary:** Compares PBFT, Proof-of-Work, and Proof-of-Authority consensus in robot swarms. Finds that PBFT is most suitable for small-to-medium swarms (<50 agents) due to its deterministic finality and low latency. A single Byzantine robot keeping a constant value will make all non-Byzantine robots converge to that value without protection.
- **Applicability to DSO:** DSO must protect against compromised or malfunctioning drones poisoning swarm consensus.
- **Implementation Recommendation:** Use PBFT-style consensus for critical swarm decisions. For non-critical telemetry aggregation, use median-based filtering (robust to outliers). Implement "trust scores" that decay for drones whose reports consistently differ from the swarm majority.

**Citation:** Wang et al. (2025). "Parallel Byzantine Fault Tolerance Consensus for Blockchain Secured Swarm Robots." *J. Field Robotics*, Wiley.
- **Summary:** Develops a parallel BFT consensus specifically optimized for swarm robots, reducing consensus latency compared to standard PBFT.
- **Applicability to DSO:** For time-critical swarm decisions, standard PBFT may be too slow. Parallel BFT reduces consensus rounds.
- **Implementation Recommendation:** Evaluate parallel BFT for time-critical swarm decisions (collision avoidance votes, emergency landing consensus). Standard PBFT for non-time-critical decisions (task allocation, formation changes).

### 4.4 FDI Architecture for DSO

```
Sensor Layer:     IMU | GPS | Baro | Mag | RPM | Current | Vibration
                    |
FDI Layer:       EKF Residual Monitor  |  Motor RPM Anomaly Detector  |  Vibration Analyzer
                    |
Decision Layer:  Fault Severity Assessment --> {Continue | Degrade | Land | Emergency}
                    |
Action Layer:    Fault-Tolerant Control  |  Mission Replanning  |  Swarm Notification
```

---

## 5. Graceful Degradation

### 5.1 Swarm Response to Member Loss

**Citation:** ScienceDirect (2021). "Mission Reliability Modeling of UAV Swarm and Its Structure Optimization Based on Importance Measure."
- **Summary:** Models swarm mission reliability as a function of individual drone reliability and swarm structure. Defines "importance measures" for each drone's role -- losing a relay drone vs. a sensor drone has different mission impact. Optimizes swarm structure to maximize mission reliability for a given swarm size.
- **Applicability to DSO:** DSO must quantify how losing specific drones affects mission success probability. Role-based importance ranking guides degradation decisions.
- **Implementation Recommendation:** Assign importance scores to each drone based on its current role (leader, relay, sensor, backup). When degradation is necessary, sacrifice lowest-importance roles first. Implement a mission reliability calculator that updates in real-time as drones join/leave.

**Citation:** ScienceDirect (2025). "Enhancing Resilience of Unmanned Autonomous Swarms Through Game Theory-Based Cooperative Reconfiguration."
- **Summary:** Uses game theory to optimally reconfigure the swarm after member loss. Each remaining drone independently evaluates the cost/benefit of taking over failed drone responsibilities. Nash equilibrium determines the new role assignment.
- **Applicability to DSO:** Provides a principled, decentralized approach to task redistribution after member loss.
- **Implementation Recommendation:** Implement auction-based task reallocation. When a drone exits the swarm, its tasks are "auctioned" to remaining drones based on proximity, capability, and remaining battery.

**Citation:** MDPI (2024). "Robust Optimization Models for Planning Drone Swarm Missions."
- **Summary:** Develops robust mission plans that account for potential drone losses. Plans are optimized to maintain minimum coverage even with k drone failures. Introduces the concept of "failure margin" -- how many drones can be lost before mission failure.
- **Applicability to DSO:** DSO should plan missions with explicit failure margins.
- **Implementation Recommendation:** During mission planning, DSO should compute the failure margin for each mission type and require it to be >= 1 (i.e., the mission can tolerate at least 1 drone loss). Display the failure margin to the operator.

### 5.2 Mission Replanning After Member Loss

**Citation:** arXiv (2025). "Onboard Mission Replanning for Adaptive Cooperative Multi-Robot Systems."
- **Summary:** Introduces the Cooperative Mission Replanning Problem (CMRP) and solves it onboard the robots for the first time. Previous approaches required a ground station for replanning. The distributed algorithm adjusts task assignments and paths in <1 second after detecting a member loss.
- **Applicability to DSO:** Critical capability for DSO. Swarms operating beyond reliable comms range must replan autonomously.
- **Implementation Recommendation:** Implement onboard replanning as a fallback. Primary replanning path: ground station computes optimal reassignment. Fallback: each drone uses local CMRP solver. Replanning must complete within 5 seconds of detecting member loss.

**Citation:** Nature (2025). "Dynamic Reconnaissance Operations With UAV Swarms: Adapting to Environmental Changes."
- **Summary:** Uses Ant Colony Optimization for real-time trajectory replanning when UAV swarms face environmental changes or member loss. The optimization framework handles modifications in the UAV swarm (vehicle loss or deployment) within a unified model.
- **Applicability to DSO:** ACO is a lightweight, distributed optimization suitable for onboard replanning.
- **Implementation Recommendation:** Evaluate ACO-based replanning for DSO survey/reconnaissance missions where area coverage must be redistributed after drone loss.

### 5.3 Minimum Viable Swarm Size

**Citation:** Springer CARE (2019). "Cooperative Autonomy for Resilience and Efficiency of Robot Teams for Complete Coverage."
- **Summary:** Defines minimum viable team size as the smallest number of robots that can complete the mission within time and coverage constraints. Uses Discrete Event Supervisors to trigger task reallocations when team size drops below the minimum.
- **Applicability to DSO:** DSO needs per-mission-type minimum viable swarm sizes.
- **Implementation Recommendation:** Define minimum viable swarm sizes for each DSO mission type:

| Mission Type | Min Viable | Recommended | Failure Margin |
|-------------|-----------|-------------|----------------|
| Area Survey | 1 | 3+ | N-1 |
| Formation Flight | 3 | 5+ | N-3 |
| Perimeter Patrol | 2 | 4+ | N-2 |
| Relay Network | 2 (for any link) | 3+ per link | N-2 |
| Search & Rescue | 2 | 5+ | N-2 |

### 5.4 Degradation Response Ladder

```
Full Swarm (N drones)
  |
  v  [Lose 1 drone]
Redistribute tasks, continue mission at reduced efficiency
  |
  v  [Lose 2+ drones OR below minimum viable]
Reduce mission scope (smaller area, fewer objectives)
  |
  v  [Below critical threshold OR safety risk]
Abort mission, orderly return to base
  |
  v  [Communication loss with ground]
Autonomous safe landing at nearest safe site
```

---

## 6. Pre-Flight and In-Flight Safety Checks

### 6.1 ArduPilot Pre-Arm Check System

**Citation:** ArduPilot Documentation. "Pre-Arm Safety Checks." (ardupilot.org)
- **Summary:** ArduPilot implements a comprehensive suite of pre-arm checks that prevent the vehicle from arming if issues are discovered. Checks include:
  - **GPS:** 3D fix required, HDOP < 2.0, position not drifting
  - **Accelerometer/Gyro:** Calibrated, healthy, consistent across redundant units
  - **Compass:** Calibrated, consistent with GPS heading, not near magnetic interference
  - **Barometer:** Healthy, altitude estimate reasonable
  - **Battery:** Voltage above minimum, failsafe configured
  - **RC Input:** Valid signal, failsafe configured
  - **Safety Switch:** Hardware safety engaged until explicitly disarmed
  - **Logging:** Storage available for flight logs
  - **Fence:** Geofence loaded if required
- **Applicability to DSO:** ArduPilot's pre-arm system is the industry baseline. DSO must implement equivalent checks plus swarm-specific checks.
- **Implementation Recommendation:** Implement all ArduPilot pre-arm checks plus additional swarm checks:
  - **Mesh Network:** All swarm members connected, latency < threshold
  - **Swarm Agreement:** All drones agree on mission parameters
  - **Mutual Position:** All drones have valid position estimates of neighbors
  - **Formation Check:** Initial formation achievable from current positions
  - **Collective Battery:** Swarm has sufficient aggregate battery for mission + reserve

### 6.2 In-Flight Continuous Checks

**Citation:** ArduPilot Documentation. "Pre-Flight Checklist (Copter)."
- **Summary:** Beyond pre-arm checks, ArduPilot continuously monitors during flight: battery voltage/current, GPS fix quality, compass consistency, vibration levels, EKF innovation, and failsafe triggers. The ARMING_SKIPCHK parameter controls which checks can be bypassed -- documentation strongly advises against disabling any checks.
- **Applicability to DSO:** DSO must implement continuous in-flight monitoring at swarm level.
- **Implementation Recommendation:** Implement tiered in-flight monitoring:

| Check | Frequency | Action on Failure |
|-------|-----------|-------------------|
| Motor RPM consistency | 50 Hz | Fault-tolerant control |
| IMU/GPS consistency | 10 Hz | Position hold, alert operator |
| Battery voltage | 1 Hz | RTL if below threshold |
| Mesh network connectivity | 2 Hz | Increase transmit power, alert |
| Neighbor position freshness | 5 Hz | Increase separation distance |
| Geofence containment | 10 Hz | Boundary correction maneuver |
| Mission progress | 0.1 Hz | Replan if behind schedule |

### 6.3 Swarm-Specific Pre-Flight Validation

**Implementation Recommendation:** DSO pre-flight checklist (all must pass before swarm arm):

```python
class SwarmPreFlightChecks:
    # Per-drone checks (delegated to ArduPilot/PX4)
    - gps_fix_quality >= 3D_FIX
    - hdop < 2.0
    - imu_calibrated and imu_healthy
    - compass_calibrated and compass_consistent
    - battery_voltage > min_voltage
    - battery_capacity_remaining > mission_requirement + 20% reserve
    - rc_failsafe_configured
    - geofence_loaded

    # Swarm-level checks (DSO-specific)
    - all_drones_connected_to_mesh
    - mesh_latency < 200ms for all pairs
    - mission_parameters_agreed (hash match across swarm)
    - initial_positions_safe (no pair closer than D_safe)
    - aggregate_battery_sufficient
    - operator_confirmed_mission
    - weather_data_current (wind < max_wind_threshold)
    - airspace_authorization_valid (LAANC approval)
```

---

## 7. Emergency Protocols

### 7.1 Emergency Landing Algorithms

**Citation:** Patterson, M., Quinlan, J., Cornman, L. (2019). "Safe2Ditch: Emergency Landing for Small Unmanned Aircraft Systems." NSF/NASA.
- **Summary:** Safe2Ditch is a crash management system that provides emergency landing capability. It communicates with vehicle sensors and autopilot to react to emergencies. The system evaluates terrain, obstacles, and current vehicle state to select the optimal landing site. Key features: works with both rotorcraft and fixed-wing, integrates with existing autopilots.
- **Applicability to DSO:** Safe2Ditch provides a proven emergency landing framework. DSO can integrate it as the last-resort emergency handler.
- **Implementation Recommendation:** Implement a Safe2Ditch-inspired emergency landing pipeline: (1) Detect emergency condition (motor failure, critical battery, loss of control), (2) Query terrain/obstacle database for nearby safe sites, (3) Select optimal site based on distance, terrain slope, proximity to people, (4) Execute emergency descent to selected site, (5) Broadcast emergency to swarm and ground station.

### 7.2 Landing Site Selection

**Citation:** Springer (2024). "An Integrated Method for Landing Site Selection and Autonomous Reactive Landing for Multirotors."
- **Summary:** Uses 3D point cloud data to classify terrain safety in real-time. The Landing Site Selection (LSS) algorithm uses SVM to classify landing safety from terrain features and a cost function to compute the best site. Works both offline (pre-mapped terrain database) and online (using onboard depth sensor).
- **Applicability to DSO:** DSO drones may need to emergency-land in unmapped areas. Online LSS from depth sensors is essential.
- **Implementation Recommendation:** Implement a two-tier approach: (1) Pre-compute safe landing sites along planned routes from satellite/map data, (2) If pre-computed sites are unreachable, use onboard camera + ML classifier to identify flat, unobstructed surfaces in real-time.

**Citation:** MDPI (2021). "Emergency Landing Spot Detection Algorithm for Unmanned Aerial Vehicles." *Remote Sensing*, 13(10), 1930.
- **Summary:** Analyzes LiDAR point cloud data for geometric features (slope, roughness, size) to detect suitable emergency landing spots. The algorithm classifies landing zones by safety level and distance.
- **Applicability to DSO:** LiDAR-based detection provides high-confidence landing site assessment.
- **Implementation Recommendation:** If DSO drones carry LiDAR, implement geometric analysis for landing site validation. If camera-only, use monocular depth estimation + terrain classification.

### 7.3 Motor-Out Procedures for Multirotors

**Citation:** Wang, X., Sun, S. (TU Delft). "Quadrotor Fault Tolerant Control."
- **Summary:** Comprehensive research program on quadrotor flight after rotor failure. Key finding: a quadrotor can maintain controlled flight with one failed rotor by sacrificing yaw control and spinning around the vertical axis. With two opposite rotors failed, the vehicle can still maintain altitude control. Uses Incremental Nonlinear Dynamic Inversion (INDI) for fault-tolerant control.
- **Applicability to DSO:** Quadrotors are the most common DSO platform. Single-rotor failure should not cause a crash.
- **Implementation Recommendation:** Integrate fault-tolerant control modes into DSO's flight controller interface:
  - **1 rotor out:** Switch to spinning-yaw mode, navigate to safe landing site
  - **2 opposite rotors out:** Altitude-only control, immediate descent to safe site
  - **2 adjacent rotors out:** Uncontrolled, deploy parachute if equipped
  - **For hexarotors/octorotors:** Redistribute thrust to remaining motors, continue limited mission

**Citation:** arXiv (2024). "Prototyping of a Multirotor UAV for Precision Landing Under Rotor Failures."
- **Summary:** Demonstrates precision landing with a quadrotor after single rotor failure. The vehicle can achieve <2m landing accuracy despite spinning. Uses vision-based landing target detection during the spinning descent.
- **Applicability to DSO:** Even in motor-out scenarios, precision landing is achievable.
- **Implementation Recommendation:** Implement vision-based landing target detection for emergency landings. Pre-mark safe landing zones with visual markers (ArUco tags or similar).

**Citation:** Nature (2025). "Nonlinear Control of Quadrotor UAV Under Rotor Failure for Robust Trajectory Tracking."
- **Summary:** Develops nonlinear model predictive control (NMPC) for post-failure trajectory tracking. Accounts for thrust constraints of remaining motors. Suitable for real-time emergency maneuvers.
- **Applicability to DSO:** NMPC provides optimal trajectory planning during degraded flight.
- **Implementation Recommendation:** Pre-compute emergency descent trajectories for common failure modes during mission planning. Store onboard for immediate execution upon failure detection.

### 7.4 Emergency Protocol State Machine for DSO

```
NOMINAL --> [fault detected] --> ASSESS
ASSESS  --> [non-critical] --> DEGRADED (continue with reduced capability)
ASSESS  --> [critical, flyable] --> EMERGENCY_LAND (navigate to safe site)
ASSESS  --> [critical, not flyable] --> CRASH_MITIGATE (parachute/controlled descent)

At each state:
  1. Broadcast status to swarm
  2. Notify ground station
  3. Log all data at max rate
  4. Swarm members increase separation from affected drone
```

---

## 8. Safety Standards and Certification

### 8.1 JARUS SORA (Specific Operations Risk Assessment)

**Citation:** JARUS (2024). "SORA v2.5: Specific Operations Risk Assessment Main Body." JARUS-doc-25.
- **Summary:** SORA is a 10-step risk assessment methodology for UAS operations. Steps: (1) Define ConOps, (2) Determine intrinsic ground risk class, (3) Apply strategic mitigations, (4) Determine final ground risk class, (5) Determine initial air risk class, (6) Apply strategic mitigations for air risk, (7) Determine SAIL (Specific Assurance and Integrity Level), (8) Identify Operational Safety Objectives, (9) Evaluate adjacent area/airspace, (10) Compile portfolio for authority approval. SAIL ranges from I (lowest) to VI (highest).
- **Applicability to DSO:** Any real-world DSO operation in regulated airspace must complete a SORA assessment. DSO should automate as much of SORA as possible.
- **Implementation Recommendation:** Build a SORA assistant into DSO that: (1) Accepts mission parameters (location, altitude, swarm size, population density), (2) Automatically calculates ground risk class and air risk class, (3) Identifies required mitigations (parachute, geofencing, detect-and-avoid), (4) Generates a SORA-compliant operations document, (5) Flags when a mission requires authority approval vs. can fly under standard scenarios.

**Citation:** EASA. "Specific Operations Risk Assessment (SORA)." European Union Aviation Safety Agency.
- **Summary:** EASA has adopted SORA as the basis for UAS operations in the "Specific" category (between Open and Certified). Operations above SAIL IV generally require full type certification. The SAIL determines the required robustness of operational safety objectives (OSOs) related to: technical design, maintenance, crew competence, operational procedures, and organizational requirements.
- **Applicability to DSO:** DSO swarm operations will likely fall in SAIL II-IV range, depending on population density and airspace class.
- **Implementation Recommendation:** Target DSO safety features to meet SAIL III requirements as the default. This requires "medium" robustness for most OSOs. Document how DSO's safety features (geofencing, FDI, emergency landing, CBF collision avoidance) satisfy each OSO.

### 8.2 DO-178C Applicability

**Citation:** RTCA. "DO-178C: Software Considerations in Airborne Systems and Equipment Certification."
- **Summary:** DO-178C is the primary standard for certifying airborne software. Defines 5 Design Assurance Levels (DAL): A (catastrophic), B (hazardous), C (major), D (minor), E (no effect). Each DAL requires increasing rigor in requirements, design, coding, verification, and configuration management. Full DO-178C compliance for DAL A requires 100% MC/DC coverage -- extremely expensive for complex software.
- **Applicability to DSO:** Full DO-178C certification is impractical for an open-source SDK. However, DSO should follow DO-178C principles for safety-critical modules.
- **Implementation Recommendation:** Stratify DSO code by criticality:
  - **DAL-C equivalent** (safety-critical): Geofence enforcement, collision avoidance CBF, emergency landing, FDI. Require 100% statement + branch coverage, code review by 2+ reviewers, formal requirements traceability.
  - **DAL-D equivalent** (mission-critical): Path planning, formation control, task allocation. Require 100% statement coverage, code review.
  - **DAL-E equivalent** (non-critical): UI, logging, analytics. Standard open-source development practices.

### 8.3 ASTM F3269 and Run-Time Assurance (RTA)

**Citation:** ASTM International. "F3269-17: Standard Practice for Methods to Safely Bound Flight Behavior of UAS Containing Complex Functions."
- **Summary:** ASTM F3269 defines a Run-Time Assurance (RTA) architecture as an alternative to DO-178C for UAS with complex functions (like ML-based navigation or swarm AI). The core idea: the complex function does not need to be certified if a certified "safety monitor" can detect unsafe outputs and switch to a certified "reversionary system." The safety monitor and reversionary system are simple enough for traditional certification.
- **Applicability to DSO:** This is the most practical certification path for DSO. The swarm AI (complex function) runs behind a certified safety monitor + reversionary system.
- **Implementation Recommendation:** Architect DSO with an explicit RTA layer:
  ```
  Complex Function (swarm AI, ML planners) --> Safety Monitor --> Reversionary System
       |                                          |                    |
       v                                          v                    v
  Nominal commands                        Check safety bounds    Simple safe behavior
  (high performance)                      (formally verified)    (hover, RTL, land)
  ```
  The Safety Monitor checks: geofence, separation distance, altitude, speed limits, battery. If any bound is violated, the Reversionary System takes over with a pre-certified safe behavior (hover, return-to-launch, or land).

### 8.4 ASTM F38 UAS Standards

**Citation:** ASTM Committee F38 on Unmanned Aircraft Systems.
- **Summary:** ASTM F38 develops standards for UAS including: F3322 (Design, Construction, Maintenance of Small UAS), F3478 (Remote ID), F3548 (UTM USS Interoperability), and F3269 (RTA). These standards are referenced by FAA in its rulemaking.
- **Applicability to DSO:** DSO should track and comply with relevant ASTM F38 standards.
- **Implementation Recommendation:** Ensure DSO supports Remote ID (F3478) broadcast, is compatible with UTM USS interfaces (F3548), and implements RTA architecture (F3269).

### 8.5 Safety Case Framework

**Implementation Recommendation:** Build a Goal Structuring Notation (GSN) safety case for DSO:

```
[G1: DSO Swarm Operations Are Acceptably Safe]
  |
  +-- [G1.1: Individual drones are airworthy]
  |     +-- [S: Pre-arm checks, continuous monitoring]
  |     +-- [E: ArduPilot/PX4 pre-arm system + DSO extensions]
  |
  +-- [G1.2: Drones do not collide with each other]
  |     +-- [S: CBF safety filter + separation monitoring]
  |     +-- [E: CBF-QP solver verification + flight test data]
  |
  +-- [G1.3: Drones stay within authorized airspace]
  |     +-- [S: PolyCARP geofencing + altitude enforcement]
  |     +-- [E: PolyCARP formal verification + NASA ICAROUS heritage]
  |
  +-- [G1.4: Failures are detected and handled safely]
  |     +-- [S: FDI system + graceful degradation + emergency landing]
  |     +-- [E: FDI test results + emergency landing flight tests]
  |
  +-- [G1.5: Operator can intervene at any time]
        +-- [S: Human-in-the-loop override + emergency stop]
        +-- [E: Interface usability testing + response time measurements]
```

---

## 9. Human-in-the-Loop Safety

### 9.1 Operator Override Design

**Citation:** ScienceDirect (2025). "Towards Human-Centered Interaction with UAV Swarms: Framework, System Design, and User Study."
- **Summary:** Develops a three-level control interface for swarm operators: macroscopic (entire swarm), mesoscopic (task groups), microscopic (individual drone). Key finding: operators need to flexibly transition between levels. Future work recommends metrics for time-to-transition, recovery efficiency, and operator workload.
- **Applicability to DSO:** DSO's operator interface must support all three control levels with seamless transitions.
- **Implementation Recommendation:** Implement three control modes in DSO's ground station:
  - **Swarm Mode:** Issue high-level commands (go to area, form pattern, RTL all). Default mode.
  - **Group Mode:** Select a subset and issue commands. For managing sub-teams.
  - **Individual Mode:** Direct control of one drone. For emergencies and troubleshooting.
  - **Emergency Override:** Single button to pause all drones (position hold), with options to RTL all or land all.

### 9.2 Operator Workload Management

**Citation:** Agrawal, A., Steghöfer, J.-P. et al. (2020). "Model-Driven Requirements for Humans-on-the-Loop Multi-UAV Missions." *arXiv:2009.10267*.
- **Summary:** Distinguishes "human-in-the-loop" (human must approve every action) from "human-on-the-loop" (human monitors and can intervene). For multi-UAV missions, human-in-the-loop is impractical beyond 2-3 drones. Proposes model-driven requirements that specify exactly when the human must be consulted vs. when the system can act autonomously.
- **Applicability to DSO:** DSO must be human-on-the-loop by default, with clear escalation rules for when operator approval is required.
- **Implementation Recommendation:** Define escalation tiers:

| Situation | Autonomy Level | Operator Role |
|-----------|---------------|---------------|
| Nominal flight | Full auto | Monitor |
| Minor deviation (e.g., wind gust) | Auto correct | Informed via telemetry |
| Geofence approach (<50m) | Auto correct + alert | Acknowledge alert |
| Drone FDI trigger | Auto response + alert | Confirm or override |
| Swarm member loss | Auto replan + alert | Approve new plan or abort |
| Critical battery (any drone) | Auto RTL + alert | Acknowledge |
| Loss of comms with drone | Auto safe-landing + alert | Acknowledge |
| Collision risk detected | Auto CBF avoidance | Informed post-hoc |
| Airspace intrusion detected | Auto avoidance + alert | May need to abort mission |

### 9.3 Interface Design for Emergencies

**Citation:** NASA (2021). "A Cognitive Walkthrough of Multiple Drone Delivery Operations." NTRS.
- **Summary:** Cognitive walkthrough study of operators managing multiple drone deliveries. Found that information overload is the primary threat to safe operations. Recommends: progressive disclosure (show detail only on demand), exception-based alerting (only interrupt for abnormal conditions), and spatial awareness displays (map-centric with drone icons).
- **Applicability to DSO:** DSO's ground station must minimize cognitive load during normal operations and maximize situational awareness during emergencies.
- **Implementation Recommendation:** Design DSO ground station with:
  - **Normal mode:** Clean map view with drone icons, mission progress bar, aggregate battery indicator. Minimal text.
  - **Alert mode:** Flashing drone icon, audio alert, one-line summary. Operator can click for details or dismiss.
  - **Emergency mode:** Full-screen emergency panel. Affected drone(s) highlighted. Clear action buttons: "Pause All", "RTL All", "Land All", "Override Drone X". No ambiguity about what each button does.

**Citation:** Notre Dame (2022). "Human-Drone Collaborations in Human-on-the-Loop Emergency Response Systems."
- **Summary:** Studies the DroneResponse system for emergency response. Bidirectional communication between operators and drones is essential. Operators need to understand why the swarm is doing what it's doing. System must explain autonomous decisions in real-time.
- **Applicability to DSO:** DSO should provide explainable autonomy -- log and display the reasoning behind autonomous decisions.
- **Implementation Recommendation:** Implement a "swarm reasoning feed" that shows: "Drone 3 rerouting: obstacle detected at waypoint 7" or "Formation adjusting: Drone 5 battery at 35%, reducing its patrol segment." Keep messages short, timestamped, and filterable by severity.

### 9.4 When the Operator MUST Be Able to Override

Based on the literature, the operator must always have the ability to:

1. **Emergency Stop (E-Stop):** Immediately halt all drone movement (position hold). Latency: <1 second from button press to drone response.
2. **Return-to-Launch All:** Command all drones to return to their launch positions. Must work even if individual drone comms are degraded (broadcast on all channels).
3. **Land All:** Command all drones to land at their current positions. For situations where RTL is unsafe.
4. **Individual Override:** Take direct control of any single drone, overriding swarm AI.
5. **Mission Abort:** Cancel the current mission and transition to a safe state.

**Implementation Recommendation:** E-Stop must be implemented at the hardware level (dedicated radio channel/frequency) in addition to software. A single button on a physical remote that broadcasts a "land now" command on a dedicated frequency, independent of the mesh network and ground station software.

---

## 10. Implementation Roadmap Summary

### Priority 1 -- Must Have Before Any Flight (Safety-Critical)

| Feature | Key Paper/Standard | Effort |
|---------|-------------------|--------|
| Pre-arm safety checks (ArduPilot parity + swarm extensions) | ArduPilot docs | Medium |
| Geofencing with PolyCARP | NASA NTRS, PolyCARP | Medium |
| E-Stop / RTL All / Land All | Human-in-the-loop papers | Low |
| Basic FDI (sensor + motor) | Baskaya et al. (2022) | Medium |
| Battery failsafe with reserve margin | ArduPilot docs | Low |
| Communication loss safe-landing | BFT papers | Medium |

### Priority 2 -- Must Have Before Multi-Drone Operations

| Feature | Key Paper/Standard | Effort |
|---------|-------------------|--------|
| CBF collision avoidance safety filter | Ames et al., Chen et al. (2021) | High |
| Runtime safety monitoring | Torens et al. (2024), DRONA | High |
| Graceful degradation + task reallocation | CMRP (2025), CARE (2019) | High |
| Emergency landing site selection | Safe2Ditch, LSS | Medium |
| Byzantine-resilient consensus | W-MSR, PBFT papers | High |

### Priority 3 -- Required for Regulatory Compliance

| Feature | Key Paper/Standard | Effort |
|---------|-------------------|--------|
| SORA assessment automation | JARUS SORA v2.5 | Medium |
| RTA architecture (ASTM F3269) | ASTM F3269-17 | High |
| Remote ID broadcast | ASTM F3478 | Low |
| Safety case documentation (GSN) | DO-178C principles | Medium |
| UTM integration | NASA UTM ConOps | High |

### Priority 4 -- Competitive Advantage

| Feature | Key Paper/Standard | Effort |
|---------|-------------------|--------|
| Formal verification of protocols (UPPAAL) | Luckcuck et al. (2019) | High |
| GNN-based scalable CBFs | GCBF+ (MIT, 2024) | High |
| Predictive fault detection (vibration) | ScienceDirect (2023) | Medium |
| Motor-out fault-tolerant control | TU Delft FTC research | High |
| Adaptive operator workload management | Agrawal et al. (2020) | Medium |

---

## Sources

### Formal Verification
- [Formal Specification and Verification of Autonomous Robotic Systems: A Survey (ACM)](https://dl.acm.org/doi/10.1145/3342355)
- [A Comprehensive Survey of UPPAAL-Assisted Formal Modeling and Verification (Wiley)](https://onlinelibrary.wiley.com/doi/10.1002/spe.3372?af=R)
- [Modeling and Verifying Resources and Capabilities of UAV Swarm (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0164121225000846)
- [Combining Model Checking and Runtime Verification for Safe Robotics (Berkeley)](https://people.eecs.berkeley.edu/~sseshia/pubdir/rv17-drona.pdf)
- [Monitoring Unmanned Aircraft: Specification, Integration, and Lessons-Learned (arXiv)](https://arxiv.org/html/2404.12035)
- [Runtime Verification and Field Testing for ROS-Based Robotic Systems (arXiv)](https://arxiv.org/html/2404.11498v1)
- [Safe Networked Robotics with Probabilistic Verification (arXiv)](https://arxiv.org/html/2302.09182)

### Control Barrier Functions
- [Guaranteed Obstacle Avoidance for Multi-Robot Operations (Caltech/Ames)](http://ames.caltech.edu/chen2021guaranteed.pdf)
- [Control Barrier Certificates for Safe Swarm Behavior (Caltech/Ames)](http://ames.caltech.edu/ADHS15_Swarm_Barrier.pdf)
- [GCBF+: A Neural Graph Control Barrier Function (MIT)](https://dspace.mit.edu/bitstream/handle/1721.1/158072/GCBF_.pdf)
- [Safe Multi-Agent Drone Control Using CBF and Acceleration Fields (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0921889023002403)
- [CBF-Based Collision Avoidance for Multi-Fixed-Wing UAV (MDPI)](https://www.mdpi.com/2504-446X/8/8/415)
- [Explicit CBF-Based Safety Filters and Resource-Aware Computation (arXiv)](https://arxiv.org/html/2512.10118v1)
- [QP Solver Implementation for Embedded Systems (MDPI)](https://www.mdpi.com/2079-3197/8/4/88)

### Geofencing
- [A Geofence Violation Prevention Mechanism for Small UAS (NASA NTRS)](https://ntrs.nasa.gov/api/citations/20190000716/downloads/20190000716.pdf)
- [PolyCARP: Algorithms and Software for Computations with Polygons (NASA Langley)](https://shemesh.larc.nasa.gov/fm/PolyCARP/)
- [ICAROUS: Integrated Configurable Algorithms for Reliable Operations of Unmanned Systems (NASA)](https://nasa.github.io/icarous/)
- [A New Approach to Complex Dynamic Geofencing for UAVs (arXiv)](https://arxiv.org/pdf/2110.09453)
- [Airspace Geofencing and Flight Planning for Low-Altitude Urban Small UAS (MDPI)](https://www.mdpi.com/2076-3417/12/2/576)
- [Geofencing Motion Planning Using Anticipatory Range Control (MDPI)](https://www.mdpi.com/2075-1702/12/1/36)

### Fault Detection and Isolation
- [UAV Fault Detection Methods, State-of-the-Art (MDPI Drones)](https://www.mdpi.com/2504-446X/6/11/330)
- [Deep Learning-Based Actuator FDI for Multirotor UAVs (MDPI)](https://www.mdpi.com/2504-446X/7/7/437)
- [Motor Fault Detection Based on External Wrench Estimation and RNN (Springer)](https://link.springer.com/article/10.1007/s10846-024-02176-2)
- [Real-Time Propeller Fault Detection via Vibration Analysis (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S0952197623005274)
- [PADRE Repository for UAV Propeller FDI Research (Springer)](https://link.springer.com/article/10.1007/s10846-024-02101-7)

### Byzantine Fault Tolerance
- [UAV Swarm Exploration With Byzantine Fault Tolerance (IEEE)](https://ieeexplore.ieee.org/document/9727874/)
- [Blockchain Technology Secures Robot Swarms: Consensus Protocol Comparison (Frontiers)](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2020.00054/full)
- [Parallel BFT Consensus for Blockchain Secured Swarm Robots (Wiley)](https://onlinelibrary.wiley.com/doi/10.1002/rob.70010)
- [Byzantine Fault Detection in Swarm-SLAM (Springer)](https://link.springer.com/chapter/10.1007/978-3-031-70932-6_4)

### Graceful Degradation
- [Mission Reliability Modeling of UAV Swarm (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0951832021003987)
- [Enhancing Resilience via Game Theory-Based Cooperative Reconfiguration (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0951832025001541)
- [Robust Optimization Models for Planning Drone Swarm Missions (MDPI)](https://www.mdpi.com/2504-446X/8/10/572)
- [Onboard Mission Replanning for Adaptive Cooperative Multi-Robot Systems (arXiv)](https://arxiv.org/html/2506.06094)
- [CARE: Cooperative Autonomy for Resilience and Efficiency (Springer)](https://link.springer.com/article/10.1007/s10514-019-09870-3)
- [Dynamic Reconnaissance Operations With UAV Swarms (Nature)](https://www.nature.com/articles/s41598-025-00201-4)
- [Systematic Literature Review on Multi-Robot Task Allocation (ACM)](https://dl.acm.org/doi/10.1145/3700591)

### Emergency Protocols
- [Safe2Ditch: Emergency Landing for Small UAS (NSF/NASA)](https://par.nsf.gov/servlets/purl/10135586)
- [Integrated Landing Site Selection and Autonomous Reactive Landing (Springer)](https://link.springer.com/chapter/10.1007/978-3-031-59167-9_24)
- [Emergency Landing Spot Detection Algorithm for UAVs (MDPI Remote Sensing)](https://www.mdpi.com/2072-4292/13/10/1930)
- [Quadrotor Fault Tolerant Control (TU Delft)](https://xueruiwangtud.github.io/project/quadrotorftc/)
- [Fault Tolerant Motion Planning for Quadrotor (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S127096382400659X)
- [Nonlinear Control of Quadrotor Under Rotor Failure (Nature)](https://www.nature.com/articles/s41598-025-26264-x)
- [Prototyping of Multirotor UAV for Precision Landing Under Rotor Failures (arXiv)](https://arxiv.org/html/2408.01676v1)

### Safety Standards
- [JARUS SORA v2.5 Main Body (JARUS)](http://jarus-rpas.org/wp-content/uploads/2024/06/SORA-v2.5-Main-Body-Release-JAR_doc_25.pdf)
- [Specific Operations Risk Assessment (EASA)](https://www.easa.europa.eu/en/domains/drones-air-mobility/operating-drone/specific-category-civil-drones/specific-operations-risk-assessment-sora)
- [ASTM F3269-17: Methods to Safely Bound UAS Flight Behavior (ASTM)](https://store.astm.org/f3269-17.html)
- [DO-178C: Software Considerations in Airborne Systems (RTCA)](https://www.rtca.org/do-178/)
- [Building Your Operational Risk Assessment (FAA)](https://www.faa.gov/sites/faa.gov/files/uas/resources/events_calendar/archive/Building_Your_Operational_Risk_Assessment.pdf)

### NASA UTM
- [UTM ConOps v2.0 (NASA/FAA)](https://www.nasa.gov/wp-content/uploads/2024/04/2020-03-faa-nextgen-utm-conops-v2-508-1.pdf)
- [UTM ConOps v1.0 (NASA)](https://www.nasa.gov/wp-content/uploads/2024/04/2018-utm-conops-v1-0-508.pdf)
- [UTM NASA Technical Documents Collection (NASA)](https://www.nasa.gov/directorates/armd/aosp/utm/utm-nasa-technical-documents-papers-and-presentations/)
- [Global UTM Architecture (GUTMA)](https://www.gutma.org/docs/Global_UTM_Architecture_V1.pdf)

### Human-in-the-Loop
- [Towards Human-Centered Interaction with UAV Swarms (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S3050741325000291)
- [Model-Driven Requirements for Humans-on-the-Loop Multi-UAV Missions (arXiv)](https://arxiv.org/abs/2009.10267)
- [Cognitive Walkthrough of Multiple Drone Delivery Operations (NASA NTRS)](https://ntrs.nasa.gov/api/citations/20210018022/downloads/Cognitive%20Walkthrough%20of%20Multi-Drone%20Delivery%20Ops.Smith%20et%20al.AIAA.2021.pdf)
- [Human-Drone Collaborations in Emergency Response Systems (Notre Dame)](https://curate.nd.edu/show/hd76rx94g17)
