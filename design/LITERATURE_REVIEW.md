# Literature Review: State Estimation, Sensor Fusion, and Telemetry for Multi-Drone Systems

**Date:** 2026-03-26
**Purpose:** Inform the design and implementation of advanced telemetry, state estimation, and observability features for the Drone Swarm Orchestrator SDK.

---

## Table of Contents

1. [Extended Kalman Filter (EKF) for Drone State Estimation](#1-extended-kalman-filter-ekf-for-drone-state-estimation)
2. [Cooperative Localization](#2-cooperative-localization)
3. [Anomaly Detection in Telemetry](#3-anomaly-detection-in-telemetry)
4. [Predictive Telemetry](#4-predictive-telemetry)
5. [Telemetry Compression and Prioritization](#5-telemetry-compression-and-prioritization)
6. [Multi-Drone Observability](#6-multi-drone-observability)
7. [Wind Estimation from Drone Telemetry](#7-wind-estimation-from-drone-telemetry)
8. [Battery Modeling and Prediction](#8-battery-modeling-and-prediction)
9. [SDK Integration Recommendations](#9-sdk-integration-recommendations)

---

## 1. Extended Kalman Filter (EKF) for Drone State Estimation

### 1.1 ArduPilot EKF3 Implementation

**Reference:** ArduPilot Dev Team. "Extended Kalman Filter Navigation Overview and Tuning." ArduPilot Dev Documentation.
- URL: https://ardupilot.org/dev/docs/extended-kalman-filter.html
- Source Code: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/AP_NavEKF3.cpp

**Summary:** EKF3 is ArduPilot's default 24-state navigation estimator that fuses rate gyroscopes, accelerometers, compass, GPS, airspeed sensors, and barometric pressure. Key architectural details:

- **24-State Vector:** Quaternion attitude (4), velocity NED (3), position NED (3), gyro biases (3), accelerometer Z bias (1), earth magnetic field (3), body magnetic field (3), wind velocity NE (2), plus 2 reserved = 24 states. The state index limit is configurable: 12 (no mag/wind), 15 (wind only), 21 (no mag), or 23 (full).
- **Multi-Core Architecture:** When multiple IMUs are available, separate EKF "cores" run in parallel on each IMU. The system selects the healthiest core for navigation output, providing hardware-level redundancy.
- **Sensor Affinity:** EKF3 introduced sensor affinity, allowing each core to bind to non-primary sensor instances (GPS, compass, barometer, airspeed), automatically switching to the best-performing sensor.
- **GSF Yaw Estimator:** An independent Gaussian Sum Filter runs alongside EKF3, using IMU + GPS data to provide yaw backup without magnetometer, critical for environments with magnetic interference.
- **Fallback to DCM:** If EKF health degrades, the system falls back to Direction Cosine Matrix (DCM) estimation.

**Implementation Complexity:** HIGH -- The full EKF3 is thousands of lines of C++ with deep ArduPilot integration. However, the SDK does not need to reimplement it; it should consume EKF3 outputs via MAVLink.

**SDK Recommendation:** Do NOT reimplement EKF3. Instead:
- Parse `ATTITUDE`, `LOCAL_POSITION_NED`, `GLOBAL_POSITION_INT`, and `EKF_STATUS_REPORT` MAVLink messages.
- Monitor EKF health flags (`EKF_STATUS_REPORT.flags`) to detect estimation degradation.
- Expose EKF innovation and variance data for fleet-level monitoring.
- Implement a lightweight application-layer EKF for inter-drone relative positioning (see Section 2).

### 1.2 Multi-Drone Cooperative State Estimation

**Reference:** "Distributed Invariant Kalman Filter for Cooperative Localization using Matrix Lie Groups." arXiv:2405.04000, 2024.
- URL: https://arxiv.org/html/2405.04000v1

**Summary:** Proposes a Distributed Invariant Extended Kalman Filter (DInEKF) for multi-robot cooperative localization in 3D. Unlike standard EKF which computes Jacobians based on linearization at the state estimate, DInEKF defines robots' motion models on matrix Lie groups, yielding state-estimate-independent Jacobians. Validated on Crazyflie 2.1 nano-drones. Outperforms quaternion-based distributed EKF in both accuracy and consistency.

**Implementation Complexity:** HIGH -- Requires matrix Lie group math (SO(3), SE(3)). Libraries exist in C++ (manif, Sophus) and Python (lietorch).

**Reference:** "Sensor Fusion for Drone Position and Attitude Estimation using Extended Kalman Filter." ResearchSquare, 2024.
- URL: https://www.researchgate.net/publication/393590343

**Summary:** Demonstrates GPS + IMU + magnetometer + barometer fusion in a standard 15-state EKF for single-drone estimation. Provides a clear mathematical framework suitable for SDK implementation of a simplified estimator.

**Implementation Complexity:** MEDIUM -- Standard EKF math with well-documented sensor models.

**SDK Recommendation:**
- Implement a lightweight "application-layer EKF" that runs on the ground station or companion computer, fusing MAVLink telemetry from all drones to maintain a unified fleet state estimate.
- This is separate from the onboard EKF3 and focuses on inter-drone relative positioning and fleet-level prediction.

---

## 2. Cooperative Localization

### 2.1 Relative Positioning Between Swarm Members

**Reference:** "Cooperative Relative Localization for UAV Swarm in GNSS-Denied Environment: A Coalition Formation Game Approach." IEEE Internet of Things Journal, 2022.
- URL: https://ieeexplore.ieee.org/iel7/6488907/6702522/09624939.pdf

**Summary:** Proposes a clustering-based cooperative relative localization scheme with a two-level framework: inter-cluster and intra-cluster localization. Uses coalition formation game theory to optimize cluster formation for localization accuracy. Particularly relevant for swarms operating where GPS is degraded.

**Implementation Complexity:** HIGH -- Requires game theory optimization and cluster management logic.

**Reference:** "Onboard Ranging-based Relative Localization and Stability for Lightweight Aerial Swarms." arXiv:2003.05853, 2020.
- URL: https://arxiv.org/html/2003.05853v3

**Summary:** Implements autonomous relative localization using Ultra-Wideband (UWB) wireless distance measurements on 13 lightweight 33-gram aerial vehicles. Demonstrates centimeter-level relative positioning achievable with inexpensive hardware. This is one of the most practical approaches for hobby/research swarms.

**Implementation Complexity:** MEDIUM -- Requires UWB hardware (e.g., DWM1001 modules, ~$10 each) and trilateration math.

**Reference:** "SwarmRaft: Leveraging Consensus for Robust Drone Swarm Coordination in GNSS-Degraded Environments." arXiv:2508.00622, 2025.
- URL: https://arxiv.org/html/2508.00622v1

**Summary:** A consensus-based protocol (building on Raft) for resilient UAV swarm localization that fuses inertial measurements with peer-to-peer ranging. Designed for adversarial and GNSS-denied environments. The consensus mechanism ensures consistency of position estimates across the swarm.

**Implementation Complexity:** HIGH -- Combines distributed consensus with sensor fusion.

### 2.2 Cooperative SLAM for Drone Swarms

**Reference:** Lajoie et al. "Swarm-SLAM: Sparse Decentralized Collaborative Simultaneous Localization and Mapping Framework for Multi-Robot Systems." arXiv:2301.06230, 2023.
- URL: https://arxiv.org/abs/2301.06230
- Code: https://github.com/MISTLab/Swarm-SLAM

**Summary:** An open-source C-SLAM system designed to be scalable, flexible, decentralized, and sparse. Supports LiDAR, stereo, and RGB-D sensing. Includes a novel inter-robot loop closure prioritization technique that reduces inter-robot communication bandwidth and accelerates map convergence. Runs on ROS2.

**Implementation Complexity:** HIGH -- Full SLAM system, but the code is open-source and well-documented.

**Reference:** "Fully Onboard SLAM for Distributed Mapping with a Swarm of Nano-Drones." arXiv:2309.03678, 2023.
- URL: https://arxiv.org/html/2309.03678v2

**Summary:** First work enabling onboard mapping with a swarm of nano-UAVs in an IoT network. Uses extremely resource-constrained hardware (Crazyflie class). Demonstrates that even tiny drones can contribute to cooperative mapping.

**Implementation Complexity:** MEDIUM -- Lightweight algorithms designed for constrained hardware.

**SDK Recommendation:**
- For V1, implement UWB-based relative positioning as the primary cooperative localization method. It is the most practical, lowest-cost, and best-documented approach.
- Provide a `RelativePositionEstimator` class that fuses GPS differences with UWB range measurements.
- For V2, integrate with Swarm-SLAM via ROS2 bridge for GPS-denied indoor operations.
- Expose a `SwarmLocalizationProvider` interface so users can plug in their preferred method (UWB, vision, LiDAR).

---

## 3. Anomaly Detection in Telemetry

### 3.1 GPS Spoofing Detection

**Reference:** "Detecting Stealthy GPS Spoofing Attack Against UAVs." NSF Publication, 2024.
- URL: https://par.nsf.gov/servlets/purl/10541394

**Summary:** Detects GPS spoofing by cross-referencing GPS-reported position with IMU-derived dead-reckoning estimates. When the discrepancy exceeds a threshold, spoofing is flagged. Achieves 98.7% detection accuracy with XGBoost on telemetry features.

**Reference:** "DeepSpoofNet: A Framework for Securing UAVs Against GPS Spoofing Attacks." PMC, 2025.
- URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC11935755/

**Summary:** Deep learning framework using CNN-LSTM on telemetry data (position, velocity, acceleration, attitude) to classify GPS signals as authentic or spoofed. Real-time detection in 0.5 seconds.

**Reference:** "CTDNN-Spoof: Compact Tiny Deep Learning Architecture for Detection and Multi-Label Classification of GPS Spoofing Attacks in Small UAVs." Nature Scientific Reports, 2025.
- URL: https://www.nature.com/articles/s41598-025-90809-3

**Summary:** A compact deep learning architecture specifically designed for resource-constrained UAV hardware. Performs both detection and classification of spoofing attack types.

**Implementation Complexity:** MEDIUM -- XGBoost approach is simplest (scikit-learn); deep learning approaches need PyTorch/TensorFlow but pretrained models can be deployed with ONNX Runtime.

**SDK Recommendation:**
- Implement a `GPSSpoofDetector` that compares GPS velocity with IMU-integrated velocity and flags divergence.
- Start with simple threshold-based detection (EKF innovation monitoring), then add ML-based detection as an optional module.
- Key features to monitor: GPS position jump rate, GPS/IMU velocity disagreement, satellite count drops, HDOP spikes.

### 3.2 Battery Anomaly Detection

**Reference:** "Predictive Maintenance on Drone Batteries Failure Using Machine Learning." RIT Thesis, Rochester Institute of Technology.
- URL: https://repository.rit.edu/cgi/viewcontent.cgi?article=12910&context=theses

**Summary:** Develops ML models to predict LiPo battery failures from discharge curves, internal resistance trends, and cycle count data. Demonstrates that random forest classifiers can predict battery failure 5-10 charge cycles in advance.

**Implementation Complexity:** LOW-MEDIUM -- Requires logging battery telemetry over time and training on historical data.

**SDK Recommendation:**
- Log per-battery telemetry: voltage, current, temperature, cell balance, cycle count.
- Implement voltage sag rate analysis (rapid voltage drop under load indicates degraded cell).
- Alert when: cell voltage differential exceeds 0.1V, voltage sag rate increases >20% from baseline, temperature exceeds 60C.

### 3.3 Motor/Propeller Degradation Detection

**Reference:** "Vibration Data-Driven Anomaly Detection in UAVs: A Deep Learning Approach." ScienceDirect, 2024.
- URL: https://www.sciencedirect.com/science/article/pii/S2215098624000880

**Summary:** Uses wavelet scattering + LSTM autoencoder on vibration signals to detect propeller cracks, faulty motors, misaligned components, and worn bearings. The autoencoder learns normal vibration patterns and flags deviations.

**Reference:** "Real-Time Drone Propeller Fault Detection Using Onboard Vibration Sensors and Optimized Machine Learning." J. Vibration Engineering & Technologies, 2025.
- URL: https://link.springer.com/article/10.1007/s42417-025-02122-y

**Summary:** Lightweight real-time diagnostic framework using ESP32 + ADXL335 accelerometer at 200 Hz. Uses optimized ML for onboard fault detection. Achieves 95% isolation accuracy.

**Reference:** "Propeller Fault Detection and Isolation for Multirotor Drones with Adaptation to Battery Voltage Drop." J. Intelligent & Robotic Systems, 2026.
- URL: https://link.springer.com/article/10.1007/s10846-026-02369-x

**Summary:** Addresses the critical problem of separating propeller faults from battery voltage drop effects. Develops powertrain models incorporating battery voltage measurements to enable accurate lift force estimation, achieving 95.04% fault isolation accuracy.

**Implementation Complexity:** MEDIUM -- Requires IMU vibration data at higher sample rates than standard telemetry (200+ Hz). ArduPilot provides `RAW_IMU` and `VIBRATION` messages.

**SDK Recommendation:**
- Monitor `VIBRATION` MAVLink messages for each drone.
- Implement vibration baseline profiling per drone (learn normal patterns during first flights).
- Detect degradation via: FFT spectral analysis of vibration data, RMS vibration level trending, frequency peak shift detection (indicates bearing wear or prop imbalance).
- Flag when vibration levels exceed 30 m/s/s (ArduPilot's clipping threshold) or trend upward by >15%.

---

## 4. Predictive Telemetry

### 4.1 Short-Term Position Prediction (1-5 seconds)

**Reference:** "Dead Reckoning and Kalman Filter Design for Trajectory Tracking of a Quadrotor UAV." IEEE Conference, 2010.
- URL: https://ieeexplore.ieee.org/document/5552088/

**Summary:** Foundational paper on combining dead reckoning with Kalman filtering for trajectory tracking. Uses analytic geometry for dead-reckoning and discrete Kalman filter for trajectory improvement. Establishes the mathematical basis for short-term position prediction.

**Reference:** "Tracking Unmanned Aerial Vehicles Based on the Kalman Filter Considering Uncertainty and Error Aware." Electronics, 2021.
- URL: https://www.mdpi.com/2079-9292/10/24/3067

**Summary:** Develops an uncertainty-aware Kalman filter for UAV tracking that explicitly models prediction error growth over time. Provides confidence bounds on predicted positions, which is critical for formation control safety margins.

**Implementation Complexity:** LOW -- Standard Kalman prediction step using current state and velocity. The prediction equations are straightforward linear algebra.

**SDK Recommendation:**
- Implement a `DroneStatePredictor` class that uses the Kalman prediction step to extrapolate each drone's position 1-5 seconds ahead.
- Use constant-velocity or constant-acceleration motion models depending on maneuver state.
- Provide uncertainty ellipsoids that grow with prediction horizon.
- This is essential for: collision avoidance lookahead, formation geometry maintenance, smooth GCS visualization (interpolating between telemetry updates).

### 4.2 Dead Reckoning During Communication Dropouts

**Reference:** "UAV Formation Control Based on Distributed Kalman Model Predictive Control Algorithm." AIP Advances, 2022.
- URL: https://pubs.aip.org/aip/adv/article/12/8/085304/2820098

**Summary:** Distributed Kalman Model Predictive Control (DK-MPC) algorithm that maintains formation even during communication disruptions. When a drone loses contact, its neighbors use Kalman prediction to estimate its position and maintain safe separation. The Kalman optimal estimation is continuously performed for the state of all UAVs in the formation.

**Implementation Complexity:** MEDIUM -- Requires implementing MPC on top of Kalman prediction, but the prediction-only component is simpler.

**SDK Recommendation:**
- When telemetry from a drone stops arriving, automatically switch to prediction mode.
- Use the last known state + velocity + acceleration to dead-reckon the position.
- Grow the uncertainty ellipsoid over time (position uncertainty grows quadratically with time for constant-velocity model).
- After 5 seconds of no telemetry: WARN. After 10 seconds: trigger formation adjustment. After 30 seconds: trigger RTL for nearby drones.
- When telemetry resumes, smoothly blend predicted state back to measured state using exponential decay.

### 4.3 Kalman Prediction for Smoother Formation Control

**Reference:** "Beyond Static Obstacles: Integrating Kalman Filter with Reinforcement Learning for Drone Navigation." Aerospace, 2024.
- URL: https://www.mdpi.com/2226-4310/11/5/395

**Summary:** Integrates Kalman filter prediction with reinforcement learning for dynamic obstacle avoidance. The Kalman filter predicts obstacle positions, which the RL agent uses to plan collision-free paths. Demonstrates 30% improvement in collision avoidance over non-predictive approaches.

**Implementation Complexity:** HIGH (for the RL component); LOW for the prediction component alone.

**SDK Recommendation:**
- Use Kalman-predicted positions of all swarm members as input to the formation controller.
- This reduces formation oscillation caused by telemetry jitter and latency.
- Implement a 2-step process: (1) predict where each drone will be at the next control cycle, (2) compute formation corrections based on predicted positions rather than last-known positions.

---

## 5. Telemetry Compression and Prioritization

### 5.1 MAVLink Efficiency

**Reference:** Koubaa et al. "Micro Air Vehicle Link (MAVLink) in a Nutshell: A Survey." IEEE Access, 2019.
- URL: https://arxiv.org/pdf/1906.10641

**Summary:** Comprehensive survey of the MAVLink protocol. Key efficiency features:
- Binary serialization with just 14 bytes of overhead per packet (MAVLink v2).
- Field reordering by size for alignment-free packing.
- No additional framing needed, making it ideal for bandwidth-constrained links.
- Typical telemetry stream: ~2-5 kbps per drone for full state.

**Implementation Complexity:** LOW -- MAVLink libraries exist for Python (pymavlink), C, C++, Rust, etc.

### 5.2 Delta Compression for Telemetry

**Reference:** "Data Transmission Between a Drone Swarm and a Ground Base: Modern Methods and Technologies." Premier Science, 2024.
- URL: https://premierscience.com/pjs-25-1302/

**Summary:** Reviews modern data transmission methods for drone swarms. Highlights that telemetry data is highly repetitive (position changes slowly relative to update rate), making delta compression extremely effective. Recommends transmitting full state periodically (keyframes) with deltas in between.

**Implementation Complexity:** LOW -- Delta encoding is straightforward: store previous message, XOR or subtract, transmit only non-zero differences.

**SDK Recommendation:**
- Implement a `TelemetryCompressor` that:
  - Sends full state keyframes every N seconds (configurable, default 5s).
  - Between keyframes, sends only changed fields using a bitmask + delta values.
  - Achieves 60-80% bandwidth reduction for hovering/slow-moving drones.
- Use MAVLink's existing message structure but add an SDK-layer delta encoding for the swarm coordination channel.

### 5.3 Priority Queuing

**Reference:** "UAV Swarm Communication and Control Architectures: A Review." Canadian J. Unmanned Vehicle Systems, 2019.
- URL: https://cdnsciencepub.com/doi/10.1139/juvs-2018-0009

**Summary:** Reviews communication architectures for UAV swarms. Establishes a priority hierarchy for message types in bandwidth-constrained environments.

**Reference:** Meshmerize. "Drone Swarm Network Features." 2024.
- URL: https://meshmerize.net/drone-swarm-network-ultimate-features-for-next-level-flight-operations/

**Summary:** Practical implementation guide for mesh networking in drone swarms. Defines traffic classes:
1. **Control traffic** (highest): Formation commands, collision avoidance, RTL triggers.
2. **Broadcast traffic**: Position announcements (5 Hz for safety bubbles).
3. **Telemetry**: Full state updates to GCS.
4. **Video/Bulk data** (lowest): Camera feeds, sensor data logs.

**Implementation Complexity:** LOW-MEDIUM -- Priority queue implementation is standard; the design challenge is defining correct priority levels.

**SDK Recommendation:**
- Implement a `TelemetryPriorityQueue` with 4 priority levels:

| Priority | Category | Examples | Max Latency |
|----------|----------|----------|-------------|
| P0 (Critical) | Safety | Collision alert, RTL command, geofence breach, EKF failure | <50ms |
| P1 (High) | Control | Formation commands, waypoint updates, mode changes | <200ms |
| P2 (Normal) | Telemetry | Position, attitude, battery, GPS status | <1000ms |
| P3 (Low) | Bulk | Video keyframes, log data, non-urgent diagnostics | Best-effort |

- When bandwidth drops, automatically suppress P3 traffic, then reduce P2 frequency, never suppress P0/P1.
- Implement bandwidth estimation and adaptive rate control.

---

## 6. Multi-Drone Observability

### 6.1 Swarm Anomaly Detection

**Reference:** "Deep Learning-Based Anomaly Detection for Individual Drone Vehicles Performing Swarm Missions." Expert Systems with Applications, 2024.
- URL: https://www.sciencedirect.com/science/article/pii/S0957417423033717

**Summary:** Proposes a novel ML framework for automatic detection of anomalous drones within a swarm and rapid identification of faulty channels (which sensor or subsystem is failing). Uses unsupervised learning to reduce dimensionality and label flight test data, followed by 1D-CNN classifiers. Key insight: comparing a drone's behavior to its swarm neighbors provides much stronger anomaly signal than monitoring the drone in isolation.

**Implementation Complexity:** MEDIUM -- Requires training on flight data. The "compare to neighbors" heuristic can be implemented simply without ML.

**Reference:** "Learning-Based Anomaly Detection and Monitoring for Swarm Drone Flights." Applied Sciences, 2019.
- URL: https://www.mdpi.com/2076-3417/9/24/5477

**Summary:** Uses moving average-based monitoring with finite time windows to detect anomalies while filtering noise. Investigates normal/abnormal probability averaged over specified time horizons. This is a practical, implementable approach that does not require deep learning.

**Implementation Complexity:** LOW -- Moving average and threshold comparison.

### 6.2 Fleet Health Metrics

**Reference:** "Review of Reliability Assessment Methods of Drone Swarm (Fleet) and a New Importance Evaluation Based Method of Drone Swarm Structure Analysis." Mathematics, 2023.
- URL: https://www.mdpi.com/2227-7390/11/11/2551

**Summary:** Defines fleet-level reliability metrics for drone swarms, including structural importance of individual drones to overall mission success. Introduces methods to evaluate which drones are most critical to the swarm's operational capability.

**Reference:** "Enhancing Drone Security Through Multi-Sensor Anomaly Detection and Machine Learning." SN Computer Science, 2024.
- URL: https://dl.acm.org/doi/abs/10.1007/s42979-024-02983-2

**Summary:** Multi-sensor anomaly detection framework that correlates anomalies across multiple data streams (GPS, IMU, battery, motor) to reduce false positives. AI-based systems increase anomaly detection rates by 65% compared to rule-based approaches.

**Implementation Complexity:** MEDIUM -- The multi-sensor correlation logic requires careful threshold tuning.

**SDK Recommendation:**
- Implement a `SwarmHealthMonitor` that computes per-drone and fleet-level health scores:

**Per-Drone Health Score** (0-100):
  - EKF health (from `EKF_STATUS_REPORT`) -- weight: 25%
  - Battery health (voltage, current, temperature) -- weight: 25%
  - GPS quality (satellite count, HDOP, fix type) -- weight: 20%
  - Vibration levels (from `VIBRATION` msg) -- weight: 15%
  - Communication quality (packet loss rate, latency) -- weight: 15%

**Fleet-Level Metrics:**
  - Swarm health score: weighted average of individual scores
  - Formation integrity: deviation from commanded formation
  - Communication mesh quality: connectivity graph metrics
  - Mission capability index: can the remaining healthy drones complete the mission?

- Implement the "compare to neighbors" heuristic: if one drone's GPS quality suddenly drops but all neighbors remain stable, flag that specific drone rather than raising a fleet-wide alert.

---

## 7. Wind Estimation from Drone Telemetry

### 7.1 Estimating Wind from Flight Data

**Reference:** Hattenberger, Bronz, Condomines. "Estimating Wind Using a Quadrotor." International J. Micro Air Vehicles, 2022.
- URL: https://journals.sagepub.com/doi/10.1177/17568293211070824

**Summary:** Demonstrates wind estimation using only IMU outputs, rotor speeds, and position data. The method works under both hovering and flight conditions. Key insight: a hovering quadrotor must tilt into the wind to maintain position; the tilt angle directly encodes wind speed and direction.

**Implementation Complexity:** LOW-MEDIUM -- Requires access to attitude data (already in MAVLink) and a drag model of the specific airframe.

**Reference:** "Wind Estimation in Unmanned Aerial Vehicles with Causal Machine Learning." arXiv:2407.01154, 2024.
- URL: https://arxiv.org/html/2407.01154v1

**Summary:** Uses causal ML to estimate wind from standard flight telemetry, avoiding the need for an explicit aerodynamic model. Achieves accurate wind estimates using only data available from standard autopilot telemetry (no additional sensors needed).

**Implementation Complexity:** MEDIUM -- Requires training ML model on flight data with ground-truth wind measurements.

**Reference:** "UAVs' Flight Dynamics Is All You Need for Wind Speed and Direction Measurement in Air." Drones, 2025.
- URL: https://www.mdpi.com/2504-446X/9/7/466

**Summary:** Shows that flight dynamics data alone (attitude, position, motor outputs) is sufficient for wind measurement without dedicated wind sensors. Validated against ground-truth anemometer data.

**Reference:** "Wind Estimation with Multirotor UAVs." Atmosphere, 2022.
- URL: https://www.mdpi.com/2073-4433/13/4/551

**Summary:** Comprehensive review of wind estimation methods for multirotors. Categorizes approaches into: (1) model-based using aerodynamic equations, (2) observer-based using Kalman filters, (3) data-driven using ML. Recommends model-based for simplicity, observer-based for accuracy, and data-driven for generality.

### 7.2 Wind Data Sharing and Wind-Aware Planning

**Reference:** Larrabee, Chao. "Wind Field Estimation in UAV Formation Flight." AIAA Guidance, Navigation, and Control Conference, 2013.
- URL: https://www.semanticscholar.org/paper/Wind-field-estimation-in-UAV-formation-flight-Larrabee-Chao/3c18e8f0eb7b4c494ab8e041029eed9c7f395460

**Summary:** Uses multiple UAVs flying in formation to estimate the spatial wind field. Each UAV contributes its local wind estimate, and the combined data reveals wind gradients and turbulence patterns across the formation volume.

**Reference:** "Towards Fully Environment-Aware UAVs: Real-Time Path Planning with Online 3D Wind Field Prediction in Complex Terrain." arXiv:1712.03608, 2017.
- URL: https://arxiv.org/abs/1712.03608

**Summary:** First real-time onboard 3D wind field prediction method for UAVs. Uses potential flow theory adjusted for terrain boundaries, mass conservation, and atmospheric stratification. Enables wind-aware path planning that reduces energy consumption by 10-30%.

**Reference:** "Integrating Wind Field Analysis in UAV Path Planning: Enhancing Safety and Energy Efficiency for Urban Logistics." Chinese J. Aeronautics, 2025.
- URL: https://www.sciencedirect.com/science/article/pii/S1000936125002110

**Summary:** Integrates CFD-computed wind fields into path planning using a wind-aware Theta* algorithm. Demonstrates significant energy savings and safety improvements in urban environments where buildings create complex wind patterns.

**Implementation Complexity:** LOW (single-drone estimation), MEDIUM (sharing), HIGH (wind-aware path planning).

**SDK Recommendation:**
- Implement a `WindEstimator` per drone using the model-based approach (attitude tilt method):
  - Input: attitude (roll, pitch), GPS velocity, commanded throttle.
  - Output: estimated wind vector (speed, direction) at the drone's altitude.
  - ArduPilot already computes wind estimates internally (accessible via `WIND` MAVLink message for fixed-wing; for multirotors, derive from `ATTITUDE` + `GLOBAL_POSITION_INT`).
- Implement `WindFieldMap` that aggregates wind estimates from all drones:
  - Spatial interpolation of wind data across the swarm volume.
  - Temporal smoothing with configurable window.
  - Share via SDK's swarm communication layer.
- Use wind data for: energy-aware path planning, formation orientation optimization (fly in V-formation relative to wind), landing site selection (choose low-wind areas).

---

## 8. Battery Modeling and Prediction

### 8.1 State of Charge (SOC) Estimation

**Reference:** "Performance Enhancement of Drone LiB State of Charge Using Extended Kalman Filter Algorithm." ScienceDirect, 2025.
- URL: https://www.sciencedirect.com/science/article/pii/S2666790825000400

**Summary:** Applies EKF to LiPo/Li-ion battery SOC estimation for drones. Uses a MATLAB-based framework for real-time monitoring. The EKF overcomes limitations of traditional coulomb counting (which drifts over time) by fusing voltage, current, and temperature measurements with a battery electrochemical model.

**Reference:** "Remaining Flying Time Prediction Implementing Battery State-of-Charge Estimation." NASA Technical Reports, 2018.
- URL: https://ntrs.nasa.gov/api/citations/20180004466/downloads/20180004466.pdf

**Summary:** NASA research on predicting remaining flight time using Adaptive Robust Extended Kalman Filter (AREKF) for SOC estimation. Uses the Shepherd battery model combined with AREKF to estimate SOC from a small amount of operational data. Establishes that SOC is the crucial factor directly affecting Remaining Flying Time (RFT).

**Implementation Complexity:** MEDIUM -- Requires a battery model (Shepherd or equivalent circuit model) and EKF implementation. The EKF here is much simpler than the navigation EKF (only 1-3 states).

### 8.2 Flight Time Prediction

**Reference:** "A Data-Driven Learning Method for Online Prediction of Drone Battery Discharge." Aerospace Science and Technology, 2022.
- URL: https://www.sciencedirect.com/science/article/pii/S1270963822005958

**Summary:** Deep learning method trained to predict time-of-flight and integral of battery current for standard path segments, enabling prediction of flight time and battery consumption along any generic path. Achieves accurate predictions even for previously unseen flight profiles.

**Reference:** "Measuring Battery Discharge Characteristics for Accurate UAV Endurance Estimation." ResearchGate, 2020.
- URL: https://www.researchgate.net/publication/339337607

**Summary:** Measures real LiPo discharge characteristics under various load profiles representative of drone flight. Key finding: battery capacity depends heavily on discharge rate (Peukert effect), temperature, and age. A 5000mAh battery may deliver only 3500mAh at high discharge rates typical of aggressive maneuvers.

### 8.3 Battery-Aware Mission Planning

**Reference:** "Prognosis & Health Management for the Prediction of UAV Flight Endurance." ResearchGate, 2018.
- URL: https://www.researchgate.net/publication/328244731

**Summary:** Combines Battery State of Health (SOH) measurement with Remaining Useful Life (RUL) estimation to compute Maximum Flight Endurance (MFE). This MFE is then used as a constraint in path planning, ensuring missions are planned within the drone's actual energy budget, not its theoretical maximum.

**Implementation Complexity:** LOW-MEDIUM -- The core is a lookup table or simple model that maps (battery voltage, current draw, temperature, SOH) to remaining flight time.

**SDK Recommendation:**
- Implement a `BatteryModel` per drone:
  - Track: voltage, current, temperature, cell count, cell balance.
  - Estimate SOC using coulomb counting with EKF correction (fuse voltage-based SOC estimate with coulomb-counted SOC).
  - Estimate SOH by tracking capacity fade over charge cycles.
- Implement a `FlightTimePredictor`:
  - Input: current SOC, average current draw, wind conditions, planned maneuvers.
  - Output: estimated remaining flight time with confidence interval.
  - Account for Peukert effect: higher current draw = less total capacity.
  - Account for temperature: cold batteries deliver less capacity.
- Implement battery-aware mission planning constraints:
  - Never plan a mission that would consume more than 80% of estimated capacity (20% reserve).
  - Adjust reserve dynamically based on wind conditions and distance to home.
  - For swarms: stagger RTL so drones land sequentially, not all at once.
- Fleet-level battery management:
  - Track per-battery SOH across the fleet.
  - Alert when a battery's capacity has degraded below 80% of rated (typical retirement threshold).
  - Recommend battery rotation schedules to equalize wear.

---

## 9. SDK Integration Recommendations

### Priority-Ordered Implementation Roadmap

Based on the literature review, here is the recommended implementation order, balancing impact, complexity, and dependencies:

#### Phase 1: Foundation (Must-Have for V1)

| Feature | Complexity | Key References | Why First |
|---------|-----------|----------------|-----------|
| EKF health monitoring (parse MAVLink) | LOW | ArduPilot EKF docs | Foundation for all other monitoring |
| Per-drone health score | LOW | Applied Sciences 2019 | Immediate fleet visibility |
| Battery SOC + flight time prediction | LOW-MED | NASA 2018, ScienceDirect 2025 | Safety-critical |
| Telemetry priority queue | LOW-MED | Meshmerize, UAV Swarm Review | Prevents data loss |
| Short-term position prediction | LOW | IEEE 2010, Electronics 2021 | Enables formation smoothing |

#### Phase 2: Intelligence (V1.x)

| Feature | Complexity | Key References | Why Second |
|---------|-----------|----------------|------------|
| GPS spoofing detection (threshold-based) | MEDIUM | NSF 2024, DeepSpoofNet 2025 | Security |
| Wind estimation (model-based) | LOW-MED | Hattenberger 2022, MDPI 2025 | Energy optimization |
| Delta telemetry compression | LOW | Premier Science 2024 | Bandwidth savings |
| Vibration monitoring + trending | MEDIUM | ScienceDirect 2024, Springer 2025 | Predictive maintenance |
| Swarm anomaly detection (neighbor comparison) | MEDIUM | Expert Systems 2024 | Fleet-level intelligence |

#### Phase 3: Advanced (V2)

| Feature | Complexity | Key References | Why Later |
|---------|-----------|----------------|-----------|
| UWB-based relative positioning | MEDIUM | arXiv 2020 UWB paper | Requires hardware |
| Wind field mapping + sharing | MEDIUM | Larrabee 2013, arXiv 2017 | Requires wind estimation first |
| ML-based GPS spoofing detection | MEDIUM | CTDNN-Spoof 2025 | Requires training data |
| Dead reckoning during dropouts | MEDIUM | AIP Advances 2022 | Requires prediction foundation |
| Battery SOH tracking + fleet management | LOW-MED | ResearchGate 2018 | Requires historical data |

#### Phase 4: Research-Grade (V3+)

| Feature | Complexity | Key References | Why Later |
|---------|-----------|----------------|-----------|
| Distributed cooperative EKF | HIGH | arXiv DInEKF 2024 | Requires Lie group math |
| Swarm-SLAM integration | HIGH | arXiv Swarm-SLAM 2023 | Requires ROS2 bridge |
| Wind-aware path planning | HIGH | arXiv 2017, ScienceDirect 2025 | Requires wind field map |
| Consensus-based localization (SwarmRaft) | HIGH | arXiv 2025 | Requires distributed consensus |
| ML propeller fault classification | HIGH | Springer 2025 | Requires vibration training data |

### Key Architectural Decisions

1. **Do not reimplement the onboard EKF.** ArduPilot's EKF3 is mature, battle-tested C++ code. The SDK should consume its outputs via MAVLink and add fleet-level intelligence on top.

2. **Application-layer EKF for fleet state.** Implement a lightweight EKF (or even simpler alpha-beta filter) in Python that maintains predicted state for each drone. This runs on the GCS/companion computer, not on the flight controller.

3. **Pluggable architecture.** Use interfaces/protocols for `LocalizationProvider`, `AnomalyDetector`, `WindEstimator`, `BatteryModel` so users can swap implementations.

4. **Compare-to-neighbors pattern.** The single most impactful insight from the anomaly detection literature: a drone's telemetry is best evaluated relative to its swarm neighbors, not in isolation. If one drone's GPS jumps but its neighbors are stable, that is a strong anomaly signal.

5. **Graceful degradation.** Every feature should have a simple fallback: ML model unavailable? Use threshold-based detection. Wind estimation inaccurate? Disable wind-aware planning. UWB not installed? Fall back to GPS-only relative positioning.

---

## Sources

- [ArduPilot EKF Documentation](https://ardupilot.org/dev/docs/extended-kalman-filter.html)
- [ArduPilot EKF3 Source Code](https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/AP_NavEKF3.cpp)
- [ArduPilot EKF Source Selection](https://ardupilot.org/copter/docs/common-ekf-sources.html)
- [Distributed Invariant Kalman Filter (DInEKF) -- arXiv:2405.04000](https://arxiv.org/html/2405.04000v1)
- [Cooperative Relative Localization for UAV Swarm -- IEEE IoT Journal](https://ieeexplore.ieee.org/iel7/6488907/6702522/09624939.pdf)
- [UWB-Based Relative Localization for Lightweight Swarms -- arXiv:2003.05853](https://arxiv.org/html/2003.05853v3)
- [SwarmRaft: Consensus for GNSS-Degraded Environments -- arXiv:2508.00622](https://arxiv.org/html/2508.00622v1)
- [Swarm-SLAM Framework -- arXiv:2301.06230](https://arxiv.org/abs/2301.06230)
- [Swarm-SLAM Source Code](https://github.com/MISTLab/Swarm-SLAM)
- [Onboard SLAM for Nano-Drone Swarms -- arXiv:2309.03678](https://arxiv.org/html/2309.03678v2)
- [Survey of Robot Swarm Relative Localization -- PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9230124/)
- [GPS Spoofing Detection for UAVs -- NSF](https://par.nsf.gov/servlets/purl/10541394)
- [DeepSpoofNet -- PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11935755/)
- [CTDNN-Spoof -- Nature Scientific Reports](https://www.nature.com/articles/s41598-025-90809-3)
- [Multi-Channel GPS Spoofing Detection -- PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12251763/)
- [GNSS Spoofing and Jamming Identification -- arXiv:2501.02352](https://arxiv.org/pdf/2501.02352)
- [Vibration-Based Anomaly Detection in UAVs -- ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2215098624000880)
- [Real-Time Propeller Fault Detection -- Springer](https://link.springer.com/article/10.1007/s42417-025-02122-y)
- [Propeller Fault Detection with Battery Adaptation -- Springer](https://link.springer.com/article/10.1007/s10846-026-02369-x)
- [ML Pre/Post Flight Rotor Defect Detection -- arXiv:2404.15880](https://arxiv.org/html/2404.15880v1)
- [Predictive Maintenance on Drone Batteries -- RIT Thesis](https://repository.rit.edu/cgi/viewcontent.cgi?article=12910&context=theses)
- [Dead Reckoning and Kalman Filter for UAV Tracking -- IEEE](https://ieeexplore.ieee.org/document/5552088/)
- [Uncertainty-Aware UAV Tracking -- MDPI Electronics](https://www.mdpi.com/2079-9292/10/24/3067)
- [Distributed Kalman MPC for UAV Formation -- AIP Advances](https://pubs.aip.org/aip/adv/article/12/8/085304/2820098)
- [Kalman Filter + RL for Drone Navigation -- MDPI Aerospace](https://www.mdpi.com/2226-4310/11/5/395)
- [MAVLink Protocol Survey -- arXiv:1906.10641](https://arxiv.org/pdf/1906.10641)
- [MAVLink Protocol Overview](https://mavlink.io/en/about/overview.html)
- [Drone Swarm Data Transmission Review -- Premier Science](https://premierscience.com/pjs-25-1302/)
- [UAV Swarm Communication Architectures -- Canadian J.](https://cdnsciencepub.com/doi/10.1139/juvs-2018-0009)
- [Drone Swarm Mesh Networking -- Meshmerize](https://meshmerize.net/drone-swarm-network-ultimate-features-for-next-level-flight-operations/)
- [Deep Learning Anomaly Detection for Swarms -- Expert Systems](https://www.sciencedirect.com/science/article/pii/S0957417423033717)
- [Learning-Based Anomaly Monitoring for Swarms -- Applied Sciences](https://www.mdpi.com/2076-3417/9/24/5477)
- [Drone Swarm Reliability Assessment -- Mathematics](https://www.mdpi.com/2227-7390/11/11/2551)
- [Multi-Sensor Anomaly Detection -- SN Computer Science](https://dl.acm.org/doi/abs/10.1007/s42979-024-02983-2)
- [Wind Estimation Using Quadrotor -- SAGE](https://journals.sagepub.com/doi/10.1177/17568293211070824)
- [Causal ML Wind Estimation -- arXiv:2407.01154](https://arxiv.org/html/2407.01154v1)
- [Flight Dynamics for Wind Measurement -- MDPI Drones](https://www.mdpi.com/2504-446X/9/7/466)
- [Wind Estimation Review for Multirotors -- MDPI Atmosphere](https://www.mdpi.com/2073-4433/13/4/551)
- [Wind Field Estimation in UAV Formation -- Semantic Scholar](https://www.semanticscholar.org/paper/Wind-field-estimation-in-UAV-formation-flight-Larrabee-Chao/3c18e8f0eb7b4c494ab8e041029eed9c7f395460)
- [Real-Time 3D Wind Field Prediction -- arXiv:1712.03608](https://arxiv.org/abs/1712.03608)
- [Wind-Aware Path Planning for Urban Logistics -- ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1000936125002110)
- [EKF for Drone Battery SOC -- ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2666790825000400)
- [NASA Remaining Flight Time Prediction](https://ntrs.nasa.gov/api/citations/20180004466/downloads/20180004466.pdf)
- [Data-Driven Battery Discharge Prediction -- ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1270963822005958)
- [Battery Discharge Characteristics for UAV Endurance -- ResearchGate](https://www.researchgate.net/publication/339337607)
- [UAV Flight Endurance Prognosis -- ResearchGate](https://www.researchgate.net/publication/328244731)
- [NASA Wind Estimation for Multi-Rotor Drones](https://ntrs.nasa.gov/api/citations/20180008712/downloads/20180008712.pdf)
