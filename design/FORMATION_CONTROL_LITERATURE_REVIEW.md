# Formation Control Algorithms: Comprehensive Literature Review

**Purpose:** Upgrade DSO from basic waypoint-based formations to state-of-the-art formation control.
**Date:** 2026-03-26
**Scope:** Consensus, flocking, virtual structure, MPC, feedback/correction, dynamic switching, GPS uncertainty, and 2024-2026 state of the art.

---

## Table of Contents

1. [Consensus-Based Formation Control](#1-consensus-based-formation-control)
2. [Reynolds Flocking Rules](#2-reynolds-flocking-rules)
3. [Virtual Structure Approach](#3-virtual-structure-approach)
4. [Model Predictive Control (MPC) for Formation](#4-model-predictive-control-for-formation)
5. [Formation Feedback and Correction](#5-formation-feedback-and-correction)
6. [Dynamic Formation Switching](#6-dynamic-formation-switching)
7. [Formation Control Under GPS Uncertainty](#7-formation-control-under-gps-uncertainty)
8. [2024-2026 State of the Art](#8-2024-2026-state-of-the-art)
9. [SDK Recommendations Summary](#9-sdk-recommendations-summary)
10. [Implementation Roadmap](#10-implementation-roadmap)

---

## 1. Consensus-Based Formation Control

### 1.1 Foundational Work

**Citation:** R. Olfati-Saber and R. M. Murray, "Consensus problems in networks of agents with switching topology and time-delays," IEEE Transactions on Automatic Control, vol. 49, no. 9, pp. 1520-1533, 2004.

**Citation:** R. Olfati-Saber, J. A. Fax, and R. M. Murray, "Consensus and Cooperation in Networked Multi-Agent Systems," Proceedings of the IEEE, vol. 95, no. 1, pp. 215-233, 2007.

**Citation:** J. A. Fax and R. M. Murray, "Information flow and cooperative control of vehicle formations," IEEE Transactions on Automatic Control, vol. 49, no. 9, pp. 1465-1476, 2004.

### 1.2 How It Works

Consensus-based formation control uses graph theory to model communication between drones. Each drone is a node; communication links are edges. The core idea:

1. **Graph Laplacian (L):** Encodes the communication topology. For n agents with adjacency matrix A and degree matrix D: `L = D - A`. The Laplacian always has at least one zero eigenvalue (associated with the eigenvector of ones).

2. **Consensus Protocol:** Each agent updates its state based on the weighted difference between its state and its neighbors' states:
   ```
   x_i_dot = -sum_j(a_ij * (x_i - x_j))   (continuous time)
   x_i[k+1] = x_i[k] + epsilon * sum_j(a_ij * (x_j[k] - x_i[k]))   (discrete time)
   ```

3. **Formation offset:** To maintain a formation (not just rendezvous), each agent tracks a desired offset from a virtual reference:
   ```
   u_i = -sum_j(a_ij * ((x_i - d_i) - (x_j - d_j)))
   ```
   where `d_i` is drone i's desired offset in the formation.

4. **Convergence:** Consensus is guaranteed if and only if the communication graph has a spanning tree. With switching topologies, convergence holds if the union of graphs over bounded time intervals has a spanning tree.

### 1.3 Three Formation Paradigms

| Paradigm | Description | Pros | Cons |
|----------|-------------|------|------|
| **Leader-Follower** | One drone is leader; followers track offsets from leader | Simple, deterministic, easy waypoint integration | Single point of failure; leader must be reliable |
| **Virtual Structure** | Formation treated as a rigid body; all drones track positions on structure | Precise geometry, easy formation shape definition | Rigid; hard to adapt to obstacles; centralized reference |
| **Behavior-Based** | Each drone runs multiple behaviors (separation, goal-seeking, formation-keeping) weighted and summed | Flexible, handles obstacles naturally | Hard to analyze stability; tuning-heavy |

### 1.4 Handling Wind and GPS Drift

- Wind disturbance appears as a common-mode bias on all agents; consensus naturally rejects it because agents track *relative* offsets, not absolute positions.
- GPS drift: If all drones drift together (correlated error), formation shape is maintained. Uncorrelated drift requires either RTK correction or relative sensing (UWB/vision).
- Olfati-Saber's 2006 flocking algorithm adds a navigational feedback term that anchors the swarm to a virtual leader, preventing unbounded drift.

### 1.5 Complexity

- **Communication:** O(|E|) per timestep, where |E| is the number of edges in the communication graph.
- **Computation per drone:** O(degree(i)) -- each drone only processes messages from its neighbors.
- **Convergence rate:** Determined by the algebraic connectivity (second-smallest eigenvalue of L, called the Fiedler value). Higher connectivity = faster convergence.

### 1.6 Real-Drone Results

- Fax and Murray (2004) demonstrated on experimental testbeds with 4 vehicles.
- Ren and Beard (2005) validated leader-follower consensus on multiple aircraft.
- ResearchGate (2016): Implementation of leader-follower linear consensus on 4x Parrot AR Drone 2.0 using motion capture + wireless communication.

### 1.7 SDK Recommendation

**Priority: HIGH -- implement as the foundational layer.**

Consensus-based control should be the backbone of the DSO formation system because:
- It is mathematically well-understood with provable convergence guarantees.
- It naturally handles communication topology changes (drones joining/leaving).
- It is computationally lightweight (runs easily on a ground station at 10-50 Hz).
- Leader-follower consensus is the simplest starting point and integrates directly with existing waypoint navigation.

**Implementation approach:**
1. Define a communication graph (start with fully connected for small swarms).
2. Implement the consensus protocol with formation offsets as the inner loop.
3. Use the existing autopilot (ArduPilot) for low-level position control; consensus outputs velocity or position setpoints.

---

## 2. Reynolds Flocking Rules

### 2.1 Foundational Work

**Citation:** C. W. Reynolds, "Flocks, herds and schools: A distributed behavioral model," ACM SIGGRAPH Computer Graphics, vol. 21, no. 4, pp. 25-34, 1987.

### 2.2 Three Rules

1. **Separation:** Steer away from nearby flockmates to avoid collision. Generates a repulsive velocity vector inversely proportional to distance.
2. **Alignment:** Steer toward the average heading of nearby flockmates. Generates a velocity matching term.
3. **Cohesion:** Steer toward the average position (center of mass) of nearby flockmates. Generates an attractive velocity vector.

The control input for each drone is a weighted sum:
```
u_i = w_sep * v_separation + w_ali * v_alignment + w_coh * v_cohesion + w_mig * v_migration
```
where `v_migration` is an optional waypoint-tracking term.

### 2.3 Modern Extensions for Drones (2018-2025)

**Citation:** G. Vasarhelyi, Cs. Viragh, G. Somorjai, T. Nepusz, A. E. Eiben, and T. Vicsek, "Optimized flocking of autonomous drones in confined environments," Science Robotics, vol. 3, no. 20, eaat3536, 2018.

This is the landmark real-world flocking paper:
- **30 drones** flown outdoors at up to **8 m/s** with no central control.
- Used evolutionary optimization to tune flocking parameters (separation distance, alignment gain, etc.).
- Noise-tolerant: works with standard GPS (no RTK required).
- Achieved collective collision avoidance and obstacle avoidance.
- Largest outdoor autonomous flocking demonstration reported as of 2024.

**Key extensions beyond Reynolds 1987:**
- **Self-propelled particle (SPP) model:** Agents have preferred speed, not just velocity matching.
- **Evolutionary parameter optimization:** Instead of hand-tuning weights, an evolutionary algorithm optimized 24 parameters in simulation, then transferred to real drones.
- **Wall/obstacle avoidance:** Additional repulsive term from virtual GPS walls and physical obstacles.
- **Communication-based:** Agents broadcast position and velocity; no vision required.

**Citation:** Adaptive Weighting Mechanism (PMC, 2021): Proposed adaptive weighting for Reynolds rules that improved flock compactness by up to 14.14% and reduced collisions compared to fixed-weight approaches.

**Citation:** Vision-based drone flocking (ResearchGate, 2021): Extended flocking to use onboard cameras for neighbor detection, eliminating the need for GPS-based position sharing.

### 2.4 Combining Flocking with Waypoint Navigation

The standard approach is to add a **migration term**:
```
v_migration = K_mig * (waypoint - position_i) / ||waypoint - position_i||
```

The migration weight must be balanced against cohesion/separation:
- Too high: drones ignore each other, collisions likely.
- Too low: swarm never reaches the waypoint.

Vasarhelyi (2018) solved this by treating migration as a "virtual leader" that all drones are attracted to, with the attraction strength decaying as drones get close to the target.

### 2.5 Complexity

- **Computation:** O(N) per drone per timestep (must check all N-1 neighbors, or O(k) with k-nearest-neighbor cutoff).
- **Communication:** Each drone broadcasts its position and velocity. O(N) messages per timestep.
- **Parameter tuning:** 10-25 parameters depending on extensions. Evolutionary optimization recommended.

### 2.6 SDK Recommendation

**Priority: MEDIUM -- implement as a supplementary behavior layer.**

Flocking is excellent for:
- Swarm transit (moving the whole group from A to B).
- Emergent obstacle avoidance.
- Graceful degradation (drones can be added/removed without reconfiguration).

But it is NOT ideal for precise geometric formations (V-shape, line, grid) because the emergent shape is stochastic. For precise formations, use consensus-based control and overlay flocking rules for collision avoidance during transitions.

**Implementation approach:**
1. Implement separation as a safety layer (always active, highest priority).
2. Use cohesion + migration for swarm transit mode.
3. Disable alignment/cohesion when in precise formation mode (consensus handles it).

---

## 3. Virtual Structure Approach

### 3.1 Foundational Work

**Citation:** R. W. Beard, J. Lawton, and F. Y. Hadaegh, "A coordination architecture for spacecraft formation control," IEEE Transactions on Control Systems Technology, vol. 9, no. 6, pp. 777-790, 2001.

**Citation:** R. W. Beard, J. M. Kelsey, and B. Young, "A control scheme for improving multi-vehicle formation maneuvers," American Control Conference, pp. 704-709, IEEE, 2001.

### 3.2 How It Works

The formation is treated as a **virtual rigid body** moving through space:

1. **Define the virtual structure:** A reference frame with desired positions for each drone relative to the structure's center. For example, a V-formation defines 5 positions at fixed offsets.

2. **Virtual structure dynamics:** The structure has its own position, velocity, and heading that evolve according to a desired trajectory:
   ```
   p_vs_dot = v_desired
   theta_vs_dot = omega_desired
   ```

3. **Individual drone control:** Each drone i tracks its assigned position on the virtual structure:
   ```
   p_desired_i = p_vs + R(theta_vs) * offset_i
   u_i = K_p * (p_desired_i - p_i) + K_v * (v_vs - v_i)
   ```
   where `R(theta_vs)` is the rotation matrix of the virtual structure.

4. **Formation feedback:** The virtual structure's dynamics can incorporate feedback from the actual drone positions:
   ```
   p_vs = (1/N) * sum(p_i)  (centroid tracking)
   ```
   This closes the loop: if drones lag, the structure slows down.

### 3.3 Handling Formation Changes Mid-Flight

Formation switching with virtual structures is straightforward:

1. **Define new offset vectors** for the target formation.
2. **Interpolate offsets** from current to target over a transition time T:
   ```
   offset_i(t) = (1 - t/T) * offset_old_i + (t/T) * offset_new_i
   ```
3. **Collision checking:** During interpolation, verify that no two drone paths intersect. If they do, use the **Hungarian algorithm** (O(N^3)) to find the optimal assignment of drones to new positions that minimizes total distance traveled.

### 3.4 Complexity

- **Computation:** O(N) per timestep for the virtual structure update + O(1) per drone for position tracking.
- **Formation switching:** O(N^3) for optimal assignment via Hungarian algorithm (one-time cost at switch).
- **Communication:** Centralized -- the ground station computes the virtual structure and sends position commands to each drone. Or semi-distributed: drones share positions and each computes the centroid locally.

### 3.5 Real-Drone Results

- Beard et al. (2001): Validated on spacecraft formation control simulations.
- UAV Formation Control via Virtual Structure (ASCE, 2014): Demonstrated on multi-UAV systems with position tracking errors under 1m.
- Commonly used in commercial drone show systems (e.g., Intel Shooting Star, Ehang) where precise geometric patterns are required.

### 3.6 SDK Recommendation

**Priority: HIGH -- implement as the primary formation shape controller.**

Virtual structure is the best approach for our SDK because:
- Users define formations as offset vectors (intuitive).
- Formation switching is a simple interpolation of offsets.
- It integrates cleanly with the consensus layer (consensus maintains the offsets; virtual structure defines them).
- It is what commercial drone show systems use.

**Implementation approach:**
1. Define formation shapes as YAML/JSON configs: list of (x, y, z) offsets.
2. Virtual structure tracks the lead waypoint trajectory.
3. Use Hungarian algorithm for optimal drone-to-position assignment during switches.
4. Each drone runs a PID/LQR position controller to track its assigned point.

---

## 4. Model Predictive Control (MPC) for Formation

### 4.1 Overview

MPC solves an optimization problem at each timestep, predicting future states over a horizon and finding the control sequence that minimizes a cost function subject to constraints.

### 4.2 Key Papers

**Citation:** "Distributed Model Predictive Formation Control for UAVs and Cooperative Capability Evaluation of Swarm," Drones (MDPI), vol. 9, no. 5, 366, 2025. Uses DMPC to coordinate UAV formations in obstacle environments with formation cost functions and collision avoidance.

**Citation:** "Distributed model predictive control for unmanned aerial vehicles and vehicle platoon systems: a review," Intelligent Robotics (OAE), 2024. Comprehensive review of DMPC for UAVs and platoons.

**Citation:** "DMPC-Swarm: distributed model predictive control on nano UAV swarms," Autonomous Robots (Springer), 2025. First distributed hardware realization of DMPC on nano-quadcopters (Crazyflie platform).

**Citation:** Y. Li and C. Hu, "New distributed model predictive control method for UAVs formation with communication anomalies," Proc. IMechE Part I, 2025. Handles communication delay and packet loss.

**Citation:** "LLM-Guided Distributed Model Predictive Control for Decentralized UAV Formations," ResearchGate, 2024. Combines LLMs with DMPC for high-level mission planning while MPC handles low-level trajectory optimization.

### 4.3 How Distributed MPC Works for Formations

Each drone solves a local optimization problem:

```
minimize: sum_{k=0}^{H} [ ||x_i(k) - x_ref_i(k)||^2_Q + ||u_i(k)||^2_R ]
subject to:
  x_i(k+1) = A*x_i(k) + B*u_i(k)          (drone dynamics)
  ||x_i(k) - x_j(k)|| >= d_safe  for all j  (collision avoidance)
  u_min <= u_i(k) <= u_max                    (actuator limits)
  v_min <= v_i(k) <= v_max                    (velocity limits)
```

where H is the prediction horizon, Q and R are weighting matrices.

**Distributed approach:** Drones share their predicted trajectories with neighbors. Each drone solves its local problem assuming neighbors will follow their predicted trajectories. Iterate until convergence (typically 2-5 iterations).

### 4.4 DMPC-Swarm: Hardware Results

The DMPC-Swarm project (2025) demonstrated:
- **Platform:** Up to 16 Crazyflie nano-quadcopters.
- **Communication:** Bluetooth Low Energy mesh network.
- **Key innovation:** Message-Loss-Recovery DMPC (MLR-DMPC) that maintains collision avoidance guarantees even with packet loss.
- **Computation:** Distributed off-board computing units (one per drone or shared). Performance scales with the number of computing units.
- **Open source:** Available on GitHub (Data-Science-in-Mechanical-Engineering/DMPC-Swarm).

### 4.5 Computational Feasibility on a Ground Station

| Swarm Size | Horizon | Solve Time (per iteration) | Feasibility |
|-----------|---------|---------------------------|-------------|
| 5 drones  | 10 steps | ~5-10 ms | Easily real-time at 10 Hz |
| 10 drones | 10 steps | ~20-50 ms | Real-time at 10 Hz |
| 20 drones | 10 steps | ~100-500 ms | Feasible at 2-5 Hz |
| 50 drones | 10 steps | ~1-5 seconds | Requires distributed solve |

For a ground station with a modern CPU, centralized MPC is feasible for up to ~10-15 drones at 10 Hz. Beyond that, distributed MPC (each drone solves locally, ground station only coordinates) is required.

**Solver options:**
- OSQP (open source, fast for QP): Best for linear MPC.
- ACADOS (open source, real-time NMPC): Handles nonlinear drone dynamics.
- CasADi + IPOPT: Flexible but slower; good for prototyping.

### 4.6 SDK Recommendation

**Priority: MEDIUM-HIGH -- implement as an advanced formation maintenance option.**

MPC provides the best formation tracking performance, especially with:
- Wind disturbances (predictive rejection).
- Obstacle avoidance (constraint-based).
- Velocity/acceleration limits (hard constraints).

But it has higher computational cost and implementation complexity than consensus + PID.

**Implementation approach:**
1. Start with centralized MPC on the ground station for small swarms (5-10).
2. Use OSQP or ACADOS as the solver.
3. Formation offsets come from the virtual structure layer.
4. MPC computes velocity commands sent to each drone's autopilot.
5. Later: distribute computation for larger swarms.

---

## 5. Formation Feedback and Correction

### 5.1 Controller Comparison

**Citation:** A. Okulski et al., "Design and Experimental Comparison of PID, LQR and MPC Stabilizing Controllers for Parrot Mambo Mini-Drone," Aerospace (MDPI), vol. 9, no. 6, 298, 2022.

| Controller | Steady-State Error | Disturbance Rejection | Tuning Effort | Computation | Best For |
|-----------|-------------------|----------------------|---------------|-------------|----------|
| **PID** | Moderate (oscillations in XY) | Poor (reactive only) | Low (3 gains per axis) | Negligible | Single-drone position hold, inner loop |
| **LQR** | Low (best orientation) | Good (optimal for linear systems) | Medium (Q, R matrices) | Low | Formation offset tracking |
| **MPC** | Lowest (predictive) | Best (anticipates disturbances) | High (model + constraints) | Highest | Obstacle-rich environments, tight formations |

**Experimental data (Okulski 2022):**
- PID: 0.075 rad max pitch deviation (steady state), 0.3 rad after disturbance impulse.
- LQR: 0.025 rad max pitch deviation (steady state), 0.06 rad after disturbance.
- MPC: 0.04 rad max pitch deviation (steady state), 0.17 rad after disturbance.

### 5.2 Formation Error Measurement

**Formation error** is the deviation of each drone from its desired position in the virtual structure:
```
e_i = p_i - p_desired_i
formation_error = (1/N) * sum(||e_i||)
```

**Additional metrics:**
- **Max error:** max(||e_i||) -- worst-case drone deviation.
- **Shape error:** Deviation of inter-drone distances from desired distances.
- **Heading error:** Deviation of formation heading from desired heading.

### 5.3 How Commercial Systems Handle Formation Drift

**Shield AI (Hivemind):**
- Uses onboard AI for autonomous collaborative flight.
- Hivemind EdgeOS enables coordinated multi-drone missions without centralized human control.
- Demonstrated formation maintenance despite simulated GPS jamming and drone removals.
- Uses multi-sensor fusion (GPS, IMU, vision) for robust state estimation.
- Closed architecture; algorithmic details not published.

**Airbus/Quantum Systems (August 2024 demo):**
- 7 mixed-type drones in formation with mission-AI.
- Maintained alignment despite simulated jamming and mid-flight drone removal.
- Demonstrates commercial readiness of fault-tolerant formation control.

**Intel Shooting Star (Drone Shows):**
- Uses RTK GPS for centimeter-level positioning.
- Centralized choreography with pre-planned trajectories.
- Each drone runs a local PID controller tracking its assigned waypoint sequence.
- Formation "drift" is essentially zero because of RTK accuracy.

**Crazyflie/Crazyswarm (Research Platform):**
- Uses motion capture (Vicon/OptiTrack) for millimeter-level positioning indoors.
- Demonstrates that with good state estimation, simple PID is sufficient for tight formations.
- Crazyswarm supports 49+ drones in formation.

### 5.4 SDK Recommendation

**Priority: HIGH -- implement a layered control architecture.**

```
Layer 3: Mission Planner (waypoints, formation shapes)
    |
Layer 2: Formation Controller (consensus + virtual structure)
    |       outputs: desired position/velocity per drone
    |
Layer 1: Position Controller (PID or LQR per drone)
    |       outputs: velocity/attitude commands
    |
Layer 0: Autopilot (ArduPilot -- attitude + motor control)
```

**Start with PID** at Layer 1 (ArduPilot already has this). Use **consensus + virtual structure** at Layer 2. Add **LQR or MPC** at Layer 1 later for tighter formation tracking under wind.

---

## 6. Dynamic Formation Switching

### 6.1 Key Papers

**Citation:** "Multi-robot formation reconfiguration via adaptive horizon planning," Control Engineering Practice (Elsevier), 2025. Uses adaptive horizon planning with temporal rescaling for hexagonal-to-triangular transitions.

**Citation:** "Environment-adaptive multi-robot formation planning and control in confined spaces," IJCAS (Springer), 2025. Dynamically selects collision-free formations from a predefined set based on local occupancy grid maps.

**Citation:** "Path Planning for the Rapid Reconfiguration of a Multi-Robot Formation Using an Integrated Algorithm," Electronics (MDPI), vol. 12, no. 16, 3483, 2023. Combines genetic algorithm + ant colony algorithm for optimal reconfiguration paths.

### 6.2 How Formation Switching Works

**Step 1: Target Assignment**
When switching from formation A to formation B, each drone must be assigned a new target position. The optimal assignment minimizes total distance traveled:
```
Assignment = argmin sum(||p_current_i - p_target_sigma(i)||^2)
```
This is the **Linear Assignment Problem**, solved optimally by the **Hungarian Algorithm** in O(N^3).

**Step 2: Trajectory Generation**
Each drone plans a trajectory from its current position to its new target:
- **Straight-line interpolation:** Simplest, but may cause collisions.
- **Polynomial trajectories:** 5th or 7th-order polynomials ensure smooth acceleration profiles.
- **Time-staggered transitions:** Drones at higher collision risk move first/last.

**Step 3: Collision Avoidance During Transition**
- **Velocity obstacles:** Each drone avoids regions in velocity space that would lead to collision.
- **Priority-based:** Assign priorities (e.g., by drone ID); lower-priority drones yield.
- **DMPC-based:** Include anti-collision constraints in the MPC optimization during transition.
- **Height staggering:** During transition, assign different altitudes to crossing drones. Simple and effective for outdoor operations.

### 6.3 Practical Formation Transitions

| Transition | Difficulty | Recommended Method |
|-----------|-----------|-------------------|
| V -> Line | Low (similar structure) | Linear interpolation + Hungarian assignment |
| Line -> Circle | Medium (topology change) | Polynomial trajectories + height stagger |
| Grid -> V | Medium | Hungarian assignment + priority-based avoidance |
| Any -> Any (arbitrary) | High | DMPC with collision constraints |
| Emergency scatter | Low | Each drone flies outward from centroid |

### 6.4 SDK Recommendation

**Priority: HIGH -- essential for practical swarm operations.**

**Implementation approach:**
1. Define formations as named presets (V, line, circle, grid, diamond, custom).
2. Use Hungarian algorithm for optimal drone-to-slot assignment.
3. Generate minimum-jerk polynomial trajectories for each drone.
4. Use altitude staggering as primary collision avoidance during transitions (simple, reliable).
5. Add DMPC-based collision avoidance as an advanced option.

---

## 7. Formation Control Under GPS Uncertainty

### 7.1 GPS Accuracy Tiers

| Technology | Horizontal Accuracy | Update Rate | Cost per Unit | Notes |
|-----------|-------------------|-------------|--------------|-------|
| Standard GPS | 2-5 m CEP | 5-10 Hz | $20-50 | Sufficient for loose formations (>10m spacing) |
| SBAS (WAAS/EGNOS) | 1-2 m CEP | 5-10 Hz | $20-50 | Marginal improvement |
| RTK GPS | 2-5 cm CEP | 10-20 Hz | $200-1000 | Centimeter-level; requires base station |
| PPK GPS | 2-5 cm CEP | Post-process | $200-500 | Not real-time; for mapping only |
| UWB Ranging | 10-30 cm | 10-100 Hz | $30-100 | Relative only; short range (50-200m) |
| Visual-Inertial (VIO) | 1-5 cm (drift over time) | 30-100 Hz | Camera + IMU | Relative; drifts without GPS anchor |

### 7.2 The Core Problem: 1-2m Formation with 2-5m GPS Error

With standard GPS (2-5m error), maintaining a 2m formation spacing is physically impossible using absolute GPS alone. The errors are larger than the desired spacing.

**Solutions ranked by practicality:**

**Solution 1: RTK GPS (Recommended)**
- 2-5 cm accuracy eliminates the problem.
- Requires a base station ($500-2000) and RTK-capable GPS on each drone ($200-500).
- Works outdoors with good sky visibility.
- Limitation: Degrades in urban canyons, under trees, or near buildings due to multipath.

**Citation:** "Reliability of RTK Positioning for Low-Cost Drones across GNSS Critical Environments," Sensors (MDPI), 2024. RTK achieves centimetric accuracy in ideal conditions but has significant limitations under poor sky visibility or strong multipath.

**Solution 2: Relative Positioning (UWB + Visual-Inertial)**

**Citation:** "Onboard cooperative relative positioning system for Micro-UAV swarm based on UWB/Vision/INS fusion through distributed graph optimization," Measurement (Elsevier), 2024. Lightweight system (150g platform) achieving centimeter-level relative positioning using UWB + camera + IMU.

**Citation:** "Decentralized Visual-Inertial-UWB Fusion for Relative State Estimation of Aerial Swarm," ICRA 2020 + arXiv. Achieves centimeter-level relative state estimation with global consistency.

**Citation:** "Binocular stereo vision-based relative positioning algorithm for drone swarm," Scientific Reports, 2025. Uses stereo cameras for drone-to-drone relative positioning.

Key insight: For formation control, you need **relative** accuracy (drone-to-drone), not **absolute** accuracy (drone-to-world). UWB ranging between drones gives direct inter-drone distances at centimeter level, even when GPS is poor.

**Solution 3: Consensus Filtering**
Use consensus among drones to improve position estimates:
- Each drone shares its GPS reading.
- If drone i knows its offset from drone j should be d_ij, and both have noisy GPS, the consensus filter estimates the true relative positions.
- This is essentially a distributed Kalman filter.

**Citation:** "UAV formation control based on distributed Kalman model predictive control algorithm," AIP Advances, vol. 12, 085304, 2022.

**Solution 4: Formation Control in Relative Coordinates**
Design the formation controller to operate entirely in relative coordinates:
- UWB provides inter-drone ranges.
- Each drone computes its position relative to neighbors.
- Formation offsets are tracked in a local relative frame.
- Only the lead drone needs accurate absolute GPS for waypoint navigation.

### 7.3 SDK Recommendation

**Priority: CRITICAL -- this determines what formations are actually achievable.**

**Phase 1 (MVP):** Use standard GPS with loose formations (5-10m spacing). Consensus filtering to smooth GPS noise. Formation error tolerance of 2-3m.

**Phase 2:** Add RTK GPS support. Tight formations (1-3m spacing). Formation error tolerance of 10-30cm.

**Phase 3:** Add UWB inter-drone ranging for relative positioning. Works in GPS-degraded environments. Formation error tolerance of 10-50cm even without RTK.

**Phase 4 (Advanced):** Visual-Inertial-UWB fusion for GPS-denied environments (indoor, urban canyon).

---

## 8. 2024-2026 State of the Art

### 8.1 Comprehensive Surveys

**Citation:** "UAV swarms: research, challenges, and future directions," Journal of Engineering and Applied Science (Springer), 2025. Covers coordinated path planning, task assignment, formation control, and security.

**Citation:** "Advancement Challenges in UAV Swarm Formation Control: A Comprehensive Review," Drones (MDPI), vol. 8, no. 7, 320, 2024. Reviews conventional methods (leader-follower, virtual structure, behavior-based, consensus, artificial potential field) and AI-based methods (neural networks, deep reinforcement learning).

### 8.2 What Works in Practice (Field-Validated)

| System | Drones | Environment | Formation Method | Positioning | Key Result |
|--------|--------|-------------|-----------------|-------------|------------|
| Vasarhelyi 2018 | 30 | Outdoor, confined | Optimized flocking (Reynolds+) | GPS (no RTK) | 8 m/s, collision-free, self-organized |
| DMPC-Swarm 2025 | 16 | Indoor (Crazyflie) | Distributed MPC | Motion capture | First DMPC hardware demo on nano-drones |
| Airbus/Quantum 2024 | 7 | Outdoor | Mission AI | GPS + multi-sensor | Robust to jamming + drone removal |
| Shield AI Hivemind | 2-4+ | Outdoor | Proprietary AI | Multi-sensor fusion | Commercial autonomous formation flight |
| Crazyswarm2 | 49+ | Indoor | Centralized trajectory | Motion capture | Precision choreography |
| GIST (Korea) 2024 | 5-25 | Outdoor | DRL + Lidar | Lidar-based relative | GPS-denied formation control |

### 8.3 Emerging Trends (2024-2026)

1. **Deep Reinforcement Learning (DRL) for Formation Control**
   - MADDPG and MAPPO are the dominant algorithms for multi-agent drone control.
   - Training in simulation (AirSim, Gazebo), transfer to real drones.
   - Reduces collision rates by up to 95% in cluttered environments.
   - 20% improvement in real-time path efficiency over classical algorithms.
   - **Limitation:** Still requires significant sim-to-real tuning. Not yet reliable enough for safety-critical applications without a classical safety layer.

   **Citation:** "Leader-follower UAVs formation control based on a deep Q-network collaborative framework," Scientific Reports, 2024.

   **Citation:** "Reinforcement learning based UAV formation control in GPS-denied environment," Chinese Journal of Aeronautics, 2024.

2. **Bio-Inspired and Hybrid Methods**
   - Combining decentralized bio-inspired rules with reference-follower mechanisms.
   - Drones dynamically select reference units based on spatial proximity.
   - Improved fault tolerance and scalability.

   **Citation:** "Enhancing drone swarm efficiency through a high-flexibility biomimetic formation algorithm," Drone Systems and Applications (NRC), 2024.

3. **LLM-Guided Formation Control**
   - Using Large Language Models for high-level mission planning and task decomposition.
   - LLM outputs mission goals; DMPC handles low-level trajectory optimization.
   - Very early stage (2024); not yet field-validated.

   **Citation:** "LLM-Guided Distributed Model Predictive Control for Decentralized UAV Formations," ResearchGate, 2024.

4. **Communication-Resilient Formation**
   - MLR-DMPC (Message-Loss-Recovery) maintains collision avoidance despite packet loss.
   - Event-triggered communication reduces bandwidth by 50-80%.
   - Demonstrated on hardware (DMPC-Swarm, 2025).

5. **Dense Forest / Confined Space Navigation**
   - 10 drones through dense bamboo forest with zero collisions.
   - Each drone senses neighbor positions and replans in real time.
   - Demonstrates feasibility of tight formation control in cluttered environments.

### 8.4 What Does NOT Work Yet

- **Fully decentralized DRL in real outdoor flights** -- still mostly sim-only for large swarms.
- **Reliable GPS-denied outdoor formation** for consumer-grade drones -- requires expensive sensor suites.
- **100+ drone formations with real-time replanning** -- commercial drone shows use pre-planned trajectories, not real-time formation control.
- **Heterogeneous swarm formation** (mixing fixed-wing and multirotor in tight formation) -- different dynamics make this very hard.

---

## 9. SDK Recommendations Summary

### Algorithm Selection Matrix

| Use Case | Recommended Algorithm | Complexity | GPS Requirement |
|----------|----------------------|-----------|-----------------|
| Basic formation hold | Consensus + Virtual Structure + PID | Low | Standard GPS (loose) or RTK (tight) |
| Swarm transit (A to B) | Reynolds flocking + migration | Low-Medium | Standard GPS |
| Precise geometric patterns | Virtual Structure + LQR | Medium | RTK GPS |
| Formation switching | Hungarian Assignment + polynomial trajectories | Medium | RTK GPS |
| Obstacle-rich environment | DMPC with collision constraints | High | RTK + relative sensing |
| GPS-denied | Consensus + UWB relative positioning | Medium-High | UWB + VIO |
| Maximum performance | DMPC + RTK + UWB | High | RTK + UWB |

### Recommended Architecture for DSO

```
+------------------------------------------------------------------+
|                     MISSION PLANNER (Layer 4)                     |
|  Waypoints, geofence, mission logic, formation shape selection    |
+------------------------------------------------------------------+
            |                                       |
            v                                       v
+---------------------------+    +---------------------------+
|  FORMATION MANAGER (L3)   |    |  SAFETY MONITOR (L3)      |
|  Virtual structure offsets |    |  Geofence, battery, RTH   |
|  Hungarian assignment      |    |  Emergency scatter         |
|  Formation switching logic |    |                           |
+---------------------------+    +---------------------------+
            |
            v
+------------------------------------------------------------------+
|              FORMATION CONTROLLER (Layer 2)                       |
|  Consensus protocol (maintains relative offsets)                  |
|  + Reynolds separation (collision avoidance)                      |
|  Mode A: Consensus + VS (precise formation)                      |
|  Mode B: Flocking + migration (swarm transit)                    |
+------------------------------------------------------------------+
            |
            v
+------------------------------------------------------------------+
|              POSITION CONTROLLER (Layer 1)                        |
|  PID (default) or LQR (advanced) or MPC (premium)               |
|  Outputs: velocity setpoints to autopilot                        |
+------------------------------------------------------------------+
            |
            v
+------------------------------------------------------------------+
|              AUTOPILOT -- ArduPilot (Layer 0)                    |
|  Attitude control, motor mixing, sensor fusion                   |
|  Accepts MAVLink velocity/position commands                      |
+------------------------------------------------------------------+
```

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)
- [ ] Implement virtual structure formation definitions (YAML configs for V, line, circle, grid)
- [ ] Implement consensus protocol with formation offsets (leader-follower mode)
- [ ] Integrate with ArduPilot via MAVLink SET_POSITION_TARGET_LOCAL_NED
- [ ] Test in SITL with 3-5 simulated drones
- [ ] Formation error logging and visualization

### Phase 2: Formation Switching (Weeks 5-8)
- [ ] Implement Hungarian algorithm for drone-to-slot assignment
- [ ] Implement minimum-jerk polynomial trajectory generation
- [ ] Implement altitude staggering during transitions
- [ ] Add Reynolds separation as always-on safety layer
- [ ] Test V -> line -> circle -> grid transitions in SITL

### Phase 3: Robustness (Weeks 9-12)
- [ ] Add RTK GPS support for tight formations
- [ ] Implement formation error metrics and auto-correction
- [ ] Add wind disturbance compensation (feedforward from wind estimate)
- [ ] Add communication loss handling (hold position on timeout)
- [ ] Field test with 3-5 real drones

### Phase 4: Advanced Features (Weeks 13-20)
- [ ] Implement LQR position controller option (better than PID for formation)
- [ ] Add UWB-based relative positioning support
- [ ] Implement DMPC for obstacle-aware formation control
- [ ] Add flocking mode for swarm transit
- [ ] Scale testing to 10+ drones in SITL

---

## Sources

### Foundational Papers
- [Olfati-Saber & Murray 2004 - Consensus Problems](https://www.semanticscholar.org/paper/Consensus-problems-in-networks-of-agents-with-and-Olfati-Saber-Murray/9839ed2281ba4b589bf88c7e4acc48c9fa6fb933)
- [Olfati-Saber, Fax & Murray 2007 - Consensus and Cooperation](https://ieeexplore.ieee.org/document/4118472/)
- [Reynolds 1987 - Boids (Flocks, Herds, Schools)](https://en.wikipedia.org/wiki/Boids)
- [Beard, Lawton & Hadaegh 2001 - Virtual Structure](https://ascelibrary.org/doi/10.1061/%28ASCE%29AS.1943-5525.0000351)

### Landmark Experimental Work
- [Vasarhelyi et al. 2018 - Optimized Flocking of 30 Drones (Science Robotics)](https://www.science.org/doi/10.1126/scirobotics.aat3536)
- [DMPC-Swarm 2025 - Distributed MPC on Nano UAVs (GitHub)](https://github.com/Data-Science-in-Mechanical-Engineering/DMPC-Swarm)
- [Crazyswarm - Large Nano-Quadcopter Swarm](https://whoenig.github.io/publications/2017_ICRA_Preiss_Hoenig.pdf)

### Controller Comparison
- [Okulski 2022 - PID vs LQR vs MPC on Mini-Drone](https://www.mdpi.com/2226-4310/9/6/298)

### Surveys and Reviews (2024-2025)
- [UAV Swarms: Research, Challenges, Future Directions (Springer 2025)](https://link.springer.com/article/10.1186/s44147-025-00582-3)
- [Advancement Challenges in UAV Swarm Formation Control (MDPI 2024)](https://www.mdpi.com/2504-446X/8/7/320)
- [DMPC Review for UAVs and Platoons (OAE 2024)](https://www.oaepublish.com/articles/ir.2024.19)
- [Formation Control Algorithms: Comprehensive Survey (EAI)](https://publications.eai.eu/index.php/inis/article/view/223)

### GPS and Relative Positioning
- [RTK Reliability for Low-Cost Drones (Sensors 2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11435761/)
- [UWB/Vision/INS Fusion for Micro-UAV Swarm (Measurement 2024)](https://www.sciencedirect.com/science/article/abs/pii/S0263224124007826)
- [Visual-Inertial-UWB Fusion for Aerial Swarm (arXiv)](https://arxiv.org/pdf/2003.05138)
- [Binocular Vision Relative Positioning for Drone Swarm (Scientific Reports 2025)](https://www.nature.com/articles/s41598-025-86981-1)

### Formation Switching and Reconfiguration
- [Multi-Robot Formation Reconfiguration via Adaptive Horizon (Elsevier 2025)](https://www.sciencedirect.com/science/article/abs/pii/S0016003225004284)
- [Environment-Adaptive Formation Planning (IJCAS 2025)](https://link.springer.com/article/10.1007/s12555-025-0473-z)

### Deep Reinforcement Learning
- [Leader-Follower UAV Formation via DQN (Scientific Reports 2024)](https://www.nature.com/articles/s41598-024-54531-w)
- [RL-based UAV Formation in GPS-Denied Environments (CJA 2024)](https://www.sciencedirect.com/science/article/pii/S1000936123002364)
- [MARL Survey for UAV Control (Drones 2025)](https://www.mdpi.com/2504-446X/9/7/484)

### Commercial Systems
- [Shield AI Hivemind](https://shield.ai/hivemind-solutions/)
- [Shield AI Swarming Capability](https://shield.ai/hivemind-for-operational-read-and-react-swarming/)

### MPC for Formation
- [DMPC Formation Control for UAVs (Drones/MDPI 2025)](https://www.mdpi.com/2504-446X/9/5/366)
- [DMPC-Swarm (Autonomous Robots/Springer 2025)](https://link.springer.com/article/10.1007/s10514-025-10211-w)
- [DMPC with Communication Anomalies (SAGE 2025)](https://journals.sagepub.com/doi/abs/10.1177/09596518251346033)
- [LLM-Guided DMPC for UAV Formations (ResearchGate 2024)](https://www.researchgate.net/publication/398557201_LLM-Guided_Distributed_Model_Predictive_Control_for_Decentralized_UAV_Formations)
