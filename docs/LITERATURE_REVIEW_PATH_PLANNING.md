# Literature Review: Multi-Drone Path Planning and Trajectory Optimization

**Date:** 2026-03-26
**Purpose:** Comprehensive survey to guide path planning module upgrades for the Drone Swarm Orchestrator SDK.

---

## Table of Contents

1. [Dubins Paths / Smooth Trajectories](#1-dubins-paths--smooth-trajectories)
2. [A* and RRT for Drone Path Planning](#2-a-and-rrt-for-drone-path-planning)
3. [Trajectory Optimization](#3-trajectory-optimization)
4. [Potential Field Path Planning](#4-potential-field-path-planning)
5. [Decentralized Path Planning](#5-decentralized-path-planning)
6. [Energy-Aware Path Planning](#6-energy-aware-path-planning)
7. [Dynamic Obstacle Avoidance](#7-dynamic-obstacle-avoidance)
8. [Geofencing and Airspace Compliance](#8-geofencing-and-airspace-compliance)
9. [Implementation Roadmap](#9-implementation-roadmap)

---

## 1. Dubins Paths / Smooth Trajectories

### 1.1 Dubins (1957) -- The Foundation

**Citation:** Dubins, L.E. "On Curves of Minimal Length with a Constraint on Average Curvature, and with Prescribed Initial and Terminal Positions and Tangents." *American Journal of Mathematics*, 79, 497-516, 1957.

**Summary:** Proves that the shortest path between two oriented points (position + heading) for a vehicle with a bounded turning radius consists of at most three segments, each being either a straight line (S) or an arc of minimum turning radius (C). The optimal path is always one of six types: CSC (CLC, CRC, etc.) or CCC. This is the theoretical bedrock for all curvature-constrained path planning.

**Complexity:** O(1) for a single pair of configurations (closed-form solutions for all six candidate paths). Chaining N waypoints is O(N).

**Real-drone results:** Not originally for drones. 2D model, applicable to fixed-wing UAVs in the horizontal plane.

**Implementation recommendation:** Use the `dubins` Python library (PyPI) for 2D Dubins paths. Useful as a baseline smoother for waypoint-to-waypoint segments in fixed-wing or hybrid VTOL missions. Not directly suitable for multirotors (which can stop and turn in place) but valuable for generating smooth, flyable arcs when speed is maintained.

---

### 1.2 Dubins Airplane Model -- 3D Extension

**Citation:** Chitsaz, H. and LaValle, S.M. "Time-optimal paths for a Dubins airplane." *IEEE Conference on Decision and Control (CDC)*, 2007. Also: Owen, M., Beard, R.W., and McLain, T.W. "Implementing Dubins Airplane Paths on Fixed-Wing UAVs." *Handbook of Unmanned Aerial Vehicles*, Springer, 2014.

**Summary:** Extends Dubins paths to 3D by adding a bounded climb/descent rate to the turning-radius constraint. The 3D path is decomposed into a horizontal Dubins path plus altitude management via helical segments when the altitude change exceeds what can be achieved in a straight climb/descent. Three cases arise: low altitude (add spirals), medium altitude (standard), and high altitude (extend path with loops).

**Complexity:** O(1) per segment pair. Slightly more complex than 2D due to altitude case analysis.

**Real-drone results:** Validated on fixed-wing UAV platforms (ArduPilot-based). The vector-field guidance law for following Dubins airplane paths has been flight-tested.

**Implementation recommendation:** Implement for fixed-wing or VTOL cruise-mode planning. Use the altitude-case decomposition (low/medium/high) as described by Owen et al. For multirotors at speed, this provides smooth altitude transitions. Chain multiple Dubins airplane segments for multi-waypoint missions using heading-constrained waypoint sequences.

---

### 1.3 Recent Advances: 3D Dubins with Full Orientation

**Citation:** Kumar, D.P., Darbha, S., Manyam, S.G., and Casbeer, D. "A Novel Model for 3D Motion Planning for a Generalized Dubins Vehicle with Pitch and Yaw Rate Constraints." *arXiv:2509.24143*, 2025.

**Summary:** Generalizes the Dubins airplane to a full body-frame model with bounded pitch and yaw rates as two independent control inputs. Constructs shortest paths using Pontryagin's minimum principle. More realistic for fixed-wing UAVs where pitch and yaw are independently constrained.

**Complexity:** Higher than classic Dubins (numerical optimization for some path types), but still tractable for real-time use.

**Real-drone results:** Theoretical with numerical validation. No flight tests reported yet.

**Implementation recommendation:** Monitor for future library releases. For now, the classic Dubins airplane model is sufficient for SDK integration.

---

### 1.4 Trajectory Smoothing for UAV Reference Paths

**Citation:** arXiv:2603.21713, "Simple Trajectory Smoothing for UAV Reference Path Planning Based on Decoupling, Spatial Modeling and Linear Programming," 2026.

**Summary:** Decouples 3D trajectory smoothing into spatial curve design and temporal parameterization. Uses linear programming for computational efficiency. Converts piecewise-linear waypoint paths into smooth, flyable trajectories.

**Complexity:** LP-based, polynomial time. Efficient for real-time replanning.

**Real-drone results:** Simulation-validated for UAV reference path scenarios.

**Implementation recommendation:** Good candidate for a post-processing smoothing layer that takes any waypoint path (from A*, RRT, etc.) and produces a smooth trajectory. Lightweight enough for onboard computation.

---

## 2. A* and RRT for Drone Path Planning

### 2.1 A* and Grid-Based Planners

**Citation:** Hart, P.E., Nilsson, N.J., and Raphael, B. "A Formal Basis for the Heuristic Determination of Minimum Cost Paths." *IEEE Transactions on Systems Science and Cybernetics*, 4(2), 100-107, 1968. Modern UAV survey: arXiv:2508.16515, "Comparative Analysis of UAV Path Planning Algorithms for Efficient Navigation in Urban 3D Environments," 2025.

**Summary:** A* searches a discretized grid/graph using a heuristic (typically Euclidean distance) to find the shortest path. In 3D, the grid becomes a voxel space. A* consistently offers shorter path lengths and faster generation times than RRT in structured 3D environments. However, A* struggles with high-dimensional spaces due to exponential memory growth (the curse of dimensionality -- O(b^d) where b is branching factor, d is depth).

**Complexity:** Time O(b^d), Space O(b^d). For a 3D grid of resolution r over volume V: nodes = V/r^3. At 1m resolution over a 500x500x100m volume, that is 25 million nodes -- feasible but memory-heavy.

**Real-drone results:** Extensively validated. A* is the default planner in many ArduPilot and PX4 mission planners for structured environments.

**Implementation recommendation:** Use A* (or its variant Theta* for any-angle paths) as the **global planner** for structured environments with known maps. Pair with a local planner for real-time obstacle avoidance. Use 3D occupancy grids at 1-2m resolution. For large outdoor areas, use hierarchical A* (coarse grid first, then refine).

---

### 2.2 RRT* -- Asymptotically Optimal Sampling-Based Planning

**Citation:** Karaman, S. and Frazzoli, E. "Sampling-based algorithms for optimal motion planning." *International Journal of Robotics Research*, 30(7), 846-894, 2011.

**Summary:** RRT* extends RRT with a rewiring step that reconnects the tree through lower-cost paths as more samples are added, guaranteeing convergence to the optimal path given infinite samples. Probabilistically complete and asymptotically optimal. Works in continuous space without discretization.

**Complexity:** Per-iteration: O(log n) for nearest-neighbor search with kd-trees. Convergence rate to optimal: slow (requires many iterations). Practical: 5,000-50,000 iterations for good paths in 3D.

**Real-drone results:** Widely used in autonomous drone racing (ETH Zurich), indoor navigation, and unknown environment exploration.

**Implementation recommendation:** Use RRT* as the **global planner for unstructured/unknown environments** where a grid is impractical. Good for GPS-denied indoor flight, forest canopy navigation, and exploration missions.

---

### 2.3 Informed RRT* -- Faster Convergence

**Citation:** Gammell, J.D., Srinivasa, S.S., and Barfoot, T.D. "Informed RRT*: Optimal sampling-based path planning focused via direct sampling of an admissible ellipsoidal heuristic." *IEEE/RSJ IROS*, 2014. UAV extension: IEEE 8665162, "UAV Path Planning System Based on 3D Informed RRT* for Dynamic Obstacle Avoidance."

**Summary:** After finding an initial path, Informed RRT* restricts sampling to an ellipsoidal subset of the space defined by the current best path cost. This dramatically accelerates convergence to the optimal solution (often 10x fewer samples than vanilla RRT*).

**Complexity:** Same per-iteration as RRT*, but converges much faster. Practical: 1,000-10,000 iterations for near-optimal paths.

**Real-drone results:** Validated for 3D UAV obstacle avoidance with dynamic replanning.

**Implementation recommendation:** **Preferred over vanilla RRT* for all applications.** The ellipsoidal sampling is trivial to implement and provides major speedups. Use as the default sampling-based planner in the SDK.

---

### 2.4 Neural Informed RRT* -- Learning-Enhanced Planning

**Citation:** arXiv:2309.14595, "Neural Informed RRT*: Learning-based Path Planning with Point Cloud State Representations under Admissible Ellipsoidal Constraints," 2023.

**Summary:** Feeds point cloud data through PointNet++ to learn a sampling distribution within the Informed RRT* ellipsoid. The neural network guides sampling toward promising regions, reducing iterations by another order of magnitude in cluttered environments.

**Complexity:** Inference: ~5ms per sample on GPU. Training: requires dataset of solved planning problems.

**Real-drone results:** Simulation with point cloud environments. No flight tests reported.

**Implementation recommendation:** Future enhancement. Requires onboard GPU (Jetson-class). Flag for v2.0 of the path planning module.

---

### 2.5 Multi-Goal RRT for UAV Cooperative Planning

**Citation:** arXiv:2504.11823, "Multi-goal Rapidly Exploring Random Tree with Safety and Dynamic Constraints for UAV Cooperative Path Planning," 2025.

**Summary:** Extends RRT to handle multiple UAVs with multiple goal locations simultaneously. Introduces safety corridors and dynamic constraints directly into the tree expansion, ensuring inter-drone separation and kinodynamic feasibility during planning rather than as a post-processing step.

**Complexity:** Scales with O(n * k) where n is tree size and k is number of drones. Practical for 5-20 drones.

**Real-drone results:** Simulation with up to 10 UAVs in obstacle-rich environments.

**Implementation recommendation:** Strong candidate for the multi-drone mission planner. The integrated safety constraints eliminate the need for a separate deconfliction layer.

---

## 3. Trajectory Optimization

### 3.1 Minimum Snap Trajectories -- Mellinger & Kumar (2011)

**Citation:** Mellinger, D. and Kumar, V. "Minimum snap trajectory generation and control for quadrotors." *IEEE International Conference on Robotics and Automation (ICRA)*, 2011. IEEE 5980409.

**Summary:** The foundational paper for polynomial trajectory optimization for quadrotors. Exploits the differential flatness property of quadrotor dynamics: the full state (position, velocity, orientation, angular rates) can be derived from the flat outputs (x, y, z, yaw) and their derivatives. Since motor forces depend on the snap (4th derivative of position), minimizing snap produces smooth, dynamically feasible trajectories. Formulated as a quadratic program (QP) over piecewise polynomial coefficients.

**Complexity:** QP with O(N * p) variables where N is number of segments and p is polynomial order (typically 7-9). Solvable in milliseconds for typical missions (10-50 waypoints).

**Real-drone results:** Demonstrated aggressive quadrotor flight through narrow windows and gaps. The paper that launched a decade of polynomial trajectory research.

**Implementation recommendation:** **Must-implement. This is the core trajectory generator for the SDK.** Use 7th-order (minimum snap) or 5th-order (minimum jerk) piecewise polynomials. Solve the QP using OSQP or similar. This should be the default trajectory representation for all multirotor missions.

---

### 3.2 Polynomial Trajectory Planning for Dense Environments

**Citation:** Richter, C., Bry, A., and Roy, N. "Polynomial trajectory planning for aggressive quadrotor flight in dense indoor environments." *International Symposium of Robotics Research (ISRR)*, 2013.

**Summary:** Extends Mellinger-Kumar by adding free intermediate waypoint derivatives (velocity, acceleration at waypoints are optimized, not fixed). Adds corridor constraints to keep trajectories within safe flight corridors. Uses unconstrained QP with closed-form solution for speed, then iteratively adjusts time allocation.

**Complexity:** Closed-form QP: O((N*p)^3) for matrix inversion, but N*p is typically small. Real-time capable.

**Real-drone results:** Aggressive indoor flight through cluttered rooms at high speed.

**Implementation recommendation:** Use this as an enhancement over basic Mellinger-Kumar. The free-derivative formulation produces better trajectories with the same computational cost. Implement corridor constraints for obstacle avoidance.

---

### 3.3 Robust and Efficient Quadrotor Trajectory Generation (Fast-Planner)

**Citation:** Zhou, B., Gao, F., Wang, L., Liu, C., and Shen, S. "Robust and efficient quadrotor trajectory generation for fast autonomous flight." *IEEE Robotics and Automation Letters*, 4(4), 3529-3536, 2019. arXiv:1907.01531.

**Summary:** Introduces a complete planning pipeline: (1) kinodynamic A* for a coarse initial path respecting dynamics, (2) B-spline trajectory optimization with gradient-based refinement for smoothness, obstacle clearance, and dynamic feasibility. The B-spline representation enables efficient local adjustment without affecting distant segments.

**Complexity:** Kinodynamic A*: O(n log n). B-spline optimization: converges in 5-20 iterations, ~10ms total.

**Real-drone results:** Real-time flight at up to 3 m/s in unknown environments with onboard sensing. One of the most-replicated results in drone planning.

**Implementation recommendation:** **High priority. Implement the two-stage pipeline (kinodynamic search + B-spline optimization).** The B-spline representation is more numerically stable than raw polynomials and supports efficient replanning. This is the architecture used by many successful autonomous drone systems.

---

### 3.4 EGO-Planner / EGO-Swarm

**Citation:** Zhou, X., Wang, Z., Ye, H., Xu, C., and Gao, F. "EGO-Planner: An ESDF-free Gradient-based Local Planner for Quadrotors." *IEEE Robotics and Automation Letters*, 6(2), 478-485, 2021. IEEE 9309347. Extension: Zhou, X. et al. "EGO-Swarm: A Fully Autonomous and Decentralized Quadrotor Swarm System in Cluttered Environments." arXiv:2011.04183.

**Summary:** Eliminates the expensive Euclidean Signed Distance Field (ESDF) computation that most gradient-based planners require. Instead, directly penalizes collisions by comparing the trajectory against a dynamically constructed collision-free guiding path. Only extracts obstacle information when the trajectory actually hits obstacles, dramatically reducing computation. EGO-Swarm extends this to multiple drones with decentralized planning and inter-drone collision avoidance.

**Complexity:** ~3ms per replanning cycle (vs ~50ms for ESDF-based planners). Supports 10+ Hz replanning.

**Real-drone results:** EGO-Swarm demonstrated fully autonomous decentralized flight of multiple quadrotors in dense forests and indoor environments using only onboard sensing. One of the strongest multi-drone results in the literature.

**Implementation recommendation:** **Top priority for the swarm module.** EGO-Swarm provides the exact architecture needed: decentralized planning where each drone runs its own planner, shares trajectory broadcasts, and avoids both obstacles and other drones. Open-source code available.

---

### 3.5 Time-Optimal Multi-Drone Trajectory Generation

**Citation:** arXiv:2402.18021, "Online Time-Optimal Trajectory Generation for Two Quadrotors with Multi-Waypoints Constraints," 2024.

**Summary:** Generates time-optimal (not just minimum-snap) trajectories for multiple quadrotors that must pass through shared waypoints without collision. Uses alternating optimization between trajectory shape and time allocation.

**Complexity:** Iterative optimization, ~100ms for 2-drone, 10-waypoint problems.

**Real-drone results:** Demonstrated with two quadrotors performing coordinated waypoint visits.

**Implementation recommendation:** Useful for time-critical multi-drone missions (racing, inspection). Implement as an optional "aggressive mode" trajectory generator.

---

### 3.6 Crazyswarm / Crazyswarm2 -- The Reference Multi-Drone Platform

**Citation:** Preiss, J.A., Honig, W., Sukhatme, G.S., and Ayanian, N. "Crazyswarm: A large nano-quadcopter swarm." *IEEE ICRA*, 2017. Crazyswarm2: imrclab.github.io/crazyswarm2/.

**Summary:** The de facto standard testbed for multi-drone research. Demonstrates swarms of up to 49 Crazyflie nano-quadcopters flying in tight formation with <2cm tracking error. Uses polynomial trajectory upload, motion capture for state estimation, and a compressed broadcast communication architecture. Crazyswarm2 ports the system to ROS 2.

**Complexity:** System-level (not algorithmic). Supports real-time trajectory execution at 100Hz control rate.

**Real-drone results:** 49 drones in coordinated formation flight. Used at dozens of universities worldwide.

**Implementation recommendation:** **Use Crazyswarm2 as the primary hardware testbed for validating SDK algorithms.** The Crazyflie platform is affordable (~$200/drone), well-documented, and has the largest open-source swarm codebase. Design the SDK's trajectory interface to be compatible with Crazyswarm2's polynomial trajectory format.

---

## 4. Potential Field Path Planning

### 4.1 Classical Artificial Potential Fields (APF)

**Citation:** Khatib, O. "Real-time obstacle avoidance for manipulators and mobile robots." *International Journal of Robotics Research*, 5(1), 90-98, 1986. Drone application: arXiv:2306.16276, "Path Planning with Potential Field-Based Obstacle Avoidance in a 3D Environment by an Unmanned Aerial Vehicle."

**Summary:** The goal generates an attractive potential (pulls the drone toward it), while obstacles generate repulsive potentials (push the drone away). The drone follows the negative gradient of the combined potential field. Simple, elegant, and fast -- but suffers from the classic local minima problem where attractive and repulsive forces cancel out, trapping the drone.

**Complexity:** O(n) per step where n is number of obstacles. Extremely fast, suitable for >100Hz reactive control.

**Real-drone results:** Widely implemented on real drones for basic obstacle avoidance. The 3D extension has been validated in simulation and limited real-world tests.

**Implementation recommendation:** Use APF as the **innermost reactive safety layer** (the last line of defense). Do NOT use as the primary planner due to local minima. Pair with a global planner (A*, RRT*) and use APF only for real-time collision avoidance adjustments.

---

### 4.2 Improved APF with Local Minima Escape

**Citation:** IEEE 11199033, "Improved Artificial Potential Field Method for UAV Path Planning," 2025.

**Summary:** Introduces three mechanisms to solve APF limitations: (1) a target-distance-weighted attractive function that prevents excessive pull at long range, (2) a local exploration factor that adds a random perturbation to escape local minima, and (3) a directional weighting factor to suppress path oscillations near obstacles.

**Complexity:** O(n) per step, marginally more expensive than classical APF due to the weighting calculations.

**Real-drone results:** Simulation-validated with significant improvement in success rate (95%+ vs 60-70% for classical APF).

**Implementation recommendation:** If APF is used as a reactive layer, implement these three improvements. The local exploration factor is particularly important -- without it, drones will get stuck between closely spaced obstacles.

---

### 4.3 Velocity-Adaptive APF for Dynamic Environments

**Citation:** arXiv:2512.07609, "Obstacle Avoidance of UAV in Dynamic Environments Using Direction and Velocity-Adaptive Artificial Potential Field," 2025.

**Summary:** Dynamically scales the repulsive potential based on the drone's velocity vector relative to the obstacle's motion. When the drone moves toward an obstacle, repulsion increases; when moving away, it decreases. This velocity weighting prevents the force-cancellation that causes local minima, since the repulsive field is no longer purely position-dependent.

**Complexity:** O(n) per step. Requires velocity estimation for dynamic obstacles.

**Real-drone results:** Simulation with moving obstacles. Shows 30% reduction in near-miss events compared to classical APF.

**Implementation recommendation:** Implement for dynamic obstacle avoidance scenarios. The velocity-dependent repulsion is a clean, efficient enhancement that integrates naturally with the APF reactive layer.

---

### 4.4 SwarmPath -- APF + Impedance Control for Drone Swarms

**Citation:** arXiv:2410.07848, "SwarmPath: Drone Swarm Navigation through Cluttered Environments Leveraging Artificial Potential Field and Impedance Control," 2024.

**Summary:** Combines APF with impedance control for swarm navigation. Drones create virtual mechanical links with nearby obstacles; the impedance controller regulates the "stiffness" and "damping" of these links, allowing drones to smoothly deform around obstacles rather than making sharp avoidance maneuvers. A virtual leader uses APF for global navigation while physical follower drones use impedance control for formation maintenance and local collision avoidance.

**Complexity:** O(n * k) per step where n is obstacles and k is swarm size. Real-time capable for 10-20 drones.

**Real-drone results:** Tested on real Crazyflie drones. 30% reduction in total travel time compared to conventional APF. Average 6% trajectory error between simulation and real-world.

**Implementation recommendation:** **Strong candidate for the swarm formation module.** The impedance control paradigm naturally handles the tension between formation keeping and obstacle avoidance. The 6% sim-to-real gap is excellent. Consider this for tight-formation missions (inspection, mapping).

---

### 4.5 APF-SA: Simulated Annealing for Global Optimality

**Citation:** arXiv:2501.09338, "Robust UAV Path Planning with Obstacle Avoidance for Emergency Rescue," 2025.

**Summary:** Combines APF with simulated annealing (SA) to escape local minima and converge to globally optimal solutions. The SA component periodically accepts worse solutions with decreasing probability, enabling the planner to explore beyond local minima basins.

**Complexity:** O(n * T) where T is the SA cooling schedule length. Slower than pure APF but guarantees escape from local minima.

**Real-drone results:** Validated for emergency rescue path planning scenarios in simulation.

**Implementation recommendation:** Consider for offline mission planning where APF-style paths are desired but global optimality matters. Not suitable for real-time reactive control due to SA overhead.

---

## 5. Decentralized Path Planning

### 5.1 Conflict-Based Search (CBS) -- The Foundation

**Citation:** Sharon, G., Stern, R., Felner, A., and Sturtevant, N. "Conflict-based search for optimal multi-agent pathfinding." *Artificial Intelligence*, 219, 40-66, 2015.

**Summary:** CBS is a two-level algorithm for multi-agent pathfinding (MAPF). The **low level** plans optimal paths for individual agents independently (using A*). The **high level** searches a Conflict Tree (CT): when two agents' paths conflict (same location at same time), CBS branches -- in one child, agent A is constrained to avoid the conflict; in the other, agent B is constrained. This continues until a conflict-free solution is found. CBS is **optimal** -- it finds the minimum-cost solution.

**Complexity:** Worst case exponential in number of agents. In practice, much faster than joint-space A* because most agent pairs don't conflict. Handles 50-100 agents in grid worlds.

**Real-drone results:** Originally for grid-based MAPF. Extended to continuous spaces and kinodynamic drones (K-CBS).

**Implementation recommendation:** **Implement CBS as the centralized multi-drone deconfliction algorithm.** Use it for mission planning (offline or near-real-time). The two-level structure is elegant: swap in any single-drone planner at the low level. For real-time operation, use the bounded-suboptimal variant (ECBS) which trades optimality for speed.

---

### 5.2 Kinodynamic CBS (K-CBS)

**Citation:** arXiv:2207.00576, "Conflict-based Search for Multi-Robot Motion Planning with Kinodynamic Constraints," 2022.

**Summary:** Extends CBS to handle agents with kinodynamic constraints (bounded velocity, acceleration, turning rate) rather than simple grid movement. The low-level planner uses kinodynamic RRT* instead of A*. Conflicts are detected in continuous space-time.

**Complexity:** More expensive than grid CBS due to continuous-space collision checking. Practical for 5-15 drones with kinodynamic constraints.

**Real-drone results:** Simulation with quadrotor dynamics models.

**Implementation recommendation:** Use for multi-drone missions where dynamic feasibility of paths matters (fast flight, aggressive maneuvers). The integration of CBS with kinodynamic planning is the right architecture for real drones.

---

### 5.3 ORCA -- Decentralized Velocity Obstacle Avoidance

**Citation:** van den Berg, J., Lin, M., and Manocha, D. "Reciprocal Velocity Obstacles for Real-Time Multi-Agent Navigation." *IEEE ICRA*, 2008. Voronoi extension: arXiv:2102.13281, "V-RVO: Decentralized Multi-Agent Collision Avoidance using Voronoi Diagrams."

**Summary:** Each agent computes a set of velocities that would lead to collision with other agents (the velocity obstacle). ORCA assumes all agents follow the same reciprocal avoidance protocol, so each agent only needs to adjust by half the required avoidance. V-RVO further constrains agents to their Voronoi cell for guaranteed safety even with double-integrator dynamics.

**Complexity:** O(k^2) per agent where k is number of nearby agents. Very fast for real-time decentralized control.

**Real-drone results:** ORCA has been validated on ground robots extensively. V-RVO includes quadrotor simulation. DCAD (Decentralized Collision Avoidance with Dynamics) tested in PX4 SITL.

**Implementation recommendation:** **Implement ORCA as the decentralized collision avoidance layer.** This runs on each drone independently, requires only position/velocity broadcasts from neighbors, and provides real-time safety. Use V-RVO variant if double-integrator dynamics are needed for smoother avoidance.

---

### 5.4 Priority-Based Planning

**Citation:** Erdmann, M. and Lozano-Perez, T. "On multiple moving objects." *Algorithmica*, 2, 477-521, 1987. Modern multi-drone: arXiv:2109.08403, "Robust Trajectory Planning for Spatial-Temporal Multi-Drone Coordination in Large Scenes."

**Summary:** Assign each drone a priority (based on task urgency, proximity to goal, etc.). Higher-priority drones plan first; lower-priority drones treat higher-priority drone trajectories as moving obstacles. Simple, fast, but suboptimal -- poor priority orderings can lead to deadlocks or highly inefficient paths.

**Complexity:** O(k * T_single) where k is number of drones and T_single is single-drone planning time. Linear scaling with swarm size.

**Real-drone results:** Used in large-scale drone shows (100+ drones) where optimality is less important than scalability and predictability.

**Implementation recommendation:** Use as a **fallback/scalability mode** when CBS is too slow (>20 drones). Implement with dynamic priority reassignment to mitigate poor orderings. Good for drone show choreography and large-scale survey missions.

---

### 5.5 Multi-Agent Reinforcement Learning (MARL) for Drone Swarms

**Citation:** arXiv:2406.04159, "MARLander: A Local Path Planning for Drone Swarms using Multiagent Deep Reinforcement Learning," 2024. Also: arXiv:2312.06250, "Robust and Decentralized Reinforcement Learning for UAV Path Planning in IoT Networks."

**Summary:** Each drone learns a decentralized policy that maps local observations (own state, nearby drones, obstacles) to actions. Training uses centralized critic with decentralized actors (CTDE paradigm). Once trained, each drone runs its policy independently with no communication required.

**Complexity:** Training: expensive (millions of episodes). Inference: O(1) forward pass per drone per timestep (~1ms on embedded GPU).

**Real-drone results:** MARLander demonstrated sim-to-real transfer on Crazyflie drones. Gap between simulation and real-world performance remains a challenge.

**Implementation recommendation:** Research-stage for production swarms. Include as an experimental module. The sim-to-real gap is the main barrier. Useful for specialized scenarios (landing, formation flight) where a policy can be pre-trained.

---

## 6. Energy-Aware Path Planning

### 6.1 Energy-Optimal vs Distance-Optimal UAV Planning

**Citation:** arXiv:2410.17585, "Energy-Optimal Planning of Waypoint-Based UAV Missions - Does Minimum Distance Mean Minimum Energy?", 2024.

**Summary:** Demonstrates that minimum-distance paths are NOT minimum-energy paths for quadrotors. Energy consumption depends on speed profile, altitude changes, wind, and hover time. A drone flying a longer but flatter path may use less energy than a shorter path with altitude changes. The paper formulates energy-optimal waypoint ordering as a variant of the Traveling Salesman Problem with energy costs.

**Complexity:** TSP-based, NP-hard. Solved with heuristics for practical mission sizes (10-50 waypoints).

**Real-drone results:** Validated with energy models calibrated against real DJI quadrotor flight data. Energy savings of 15-30% over distance-optimal paths.

**Implementation recommendation:** **Integrate an energy cost model into the path planner.** Replace Euclidean distance heuristics with energy-based costs that account for altitude, speed, and wind. This is a relatively easy modification to A*/RRT* that yields significant real-world benefits.

---

### 6.2 Energy-Aware Multi-UAV Coverage with Optimal Speed

**Citation:** arXiv:2402.10529, "Energy-aware Multi-UAV Coverage Mission Planning with Optimal Speed of Flight," 2024.

**Summary:** For coverage missions (mapping, inspection), computes the optimal flight speed that maximizes area covered per battery charge. The optimal speed is not the maximum speed (high drag) or the minimum speed (high hover power), but a specific intermediate speed that depends on the drone's mass, rotor efficiency, and air density. Integrates this into multi-drone task allocation.

**Complexity:** Speed optimization is closed-form. Task allocation uses auction-based methods, O(k * n) for k drones and n tasks.

**Real-drone results:** Validated with energy models. Optimal speed calculation matches empirical measurements.

**Implementation recommendation:** **Compute and store optimal cruise speed for each drone type in the SDK configuration.** Use this speed as the default for mission planning. Allow override for time-critical missions.

---

### 6.3 Wind-Aware Energy-Efficient Path Planning

**Citation:** arXiv:2004.00182, "Energy-Efficiency Path Planning for Quadrotor UAV Under Wind Conditions."

**Summary:** Models wind as a spatially varying vector field and optimizes trajectories to exploit tailwinds and avoid headwinds. By adjusting the yaw angle relative to the wind vector, a quadrotor can improve its range by 30% on the same battery. The planner generates energy-optimal paths through a known wind field using graph search with energy-weighted edges.

**Complexity:** Same as A* with modified edge weights. Requires a wind field model (from weather data or onboard anemometer).

**Real-drone results:** Simulation with realistic wind models. The 30% improvement is consistent across scenarios.

**Implementation recommendation:** Integrate wind data (from weather APIs or onboard sensors) into the energy cost model. Even a simple constant-wind model provides significant benefits. For outdoor missions, query wind forecasts at mission planning time and adjust paths accordingly.

---

### 6.4 EcoFlight -- Energy-Efficient A* Through Obstacles

**Citation:** arXiv:2511.12618, "EcoFlight: Finding Low-Energy Paths Through Obstacles for Autonomous Sensing Drones," 2025.

**Summary:** An A*-based planner that uses energy (not distance) as the primary cost metric. Incorporates altitude changes, flight speed, and acceleration into edge costs. Dynamically selects optimal speed for each path segment based on terrain and obstacles.

**Complexity:** Same as A* with energy-weighted edges. Marginal overhead for energy computation.

**Real-drone results:** Validated in obstacle-rich environments (forests, urban canyons). Significant energy savings in environments with altitude variation.

**Implementation recommendation:** Use as the energy-aware variant of the A* global planner. The key insight (energy-weighted edges) is straightforward to implement on top of existing A* infrastructure.

---

### 6.5 Return-to-Base and Emergency Landing

**Citation:** IEEE 10397242, "How to Save a Drone in Case of Low Battery? A New Algorithm for Determining Safe Landing," 2024. Also: arXiv:2505.20423, "Vision-Based Risk Aware Emergency Landing for UAVs in Complex Urban Environments," 2025.

**Summary:** Addresses the critical safety problem of what to do when battery is low. Uses depth camera data with RANSAC and KD-Tree methods to identify safe landing surfaces in real-time. The risk-aware system uses semantic segmentation to evaluate hazards and identifies Safe Landing Zones (SLZ) with altitude-dependent safety thresholds. Emergency landing decisions factor in remaining battery, distance to base, wind conditions, and terrain safety.

**Complexity:** RANSAC surface detection: O(n) per frame. Semantic segmentation: ~30ms on Jetson Nano.

**Real-drone results:** Validated on real drones with depth cameras. Reduces landing time by performing short maneuvers toward nearest safe surface.

**Implementation recommendation:** **Must-implement for safety.** The SDK needs: (1) continuous battery monitoring with return-to-base threshold, (2) precomputed emergency landing zones along the route, (3) real-time safe surface detection as a fallback. This is a regulatory requirement for most commercial drone operations.

---

### 6.6 Autonomous Recharging and Mission Continuation

**Citation:** arXiv:1703.10049, "Autonomous Recharging and Flight Mission Planning for Battery-operated Autonomous Drones," 2017.

**Summary:** Plans multi-leg missions where drones autonomously return to charging stations, recharge, and continue the mission. The planner jointly optimizes mission waypoint ordering and charging station visits to minimize total mission time.

**Complexity:** Mixed-integer programming for joint optimization. Heuristic solutions for real-time.

**Real-drone results:** Demonstrated with autonomous landing on charging pads.

**Implementation recommendation:** Design the mission planner to be "battery-aware" from the start. Each mission plan should include explicit battery checkpoints and designated return-to-charge waypoints. Support for battery-swap stations and wireless charging pads.

---

## 7. Dynamic Obstacle Avoidance

### 7.1 DPMPC-Planner -- Predict-Then-Plan Framework

**Citation:** arXiv:2109.07024, Xu, Z. et al. "DPMPC-Planner: A real-time UAV trajectory planning framework for complex static environments with dynamic obstacles," 2021.

**Summary:** A two-phase framework: (1) generate a static trajectory using iterative corridor shrinking through the known environment, (2) apply reactive chance-constrained Model Predictive Control (MPC) to avoid dynamic obstacles. The MPC predicts obstacle positions using a uniform acceleration model and plans risk-bounded avoidance trajectories. Separating static and dynamic planning reduces computational load.

**Complexity:** Static planning: ~50ms. MPC replanning: ~10ms per cycle. Total: real-time at 20+ Hz.

**Real-drone results:** Simulation with realistic dynamic obstacles. The two-phase architecture is practical.

**Implementation recommendation:** **Implement this two-phase architecture.** Plan against the static map first, then layer dynamic avoidance on top. This separation of concerns is clean and efficient. Use the chance-constrained MPC formulation to handle prediction uncertainty.

---

### 7.2 DWA-3D -- Reactive Dynamic Window for Drones

**Citation:** arXiv:2409.05421, "DWA-3D: A Reactive Planner for Robust and Efficient Autonomous UAV Navigation," 2024.

**Summary:** Extends the Dynamic Window Approach (DWA) from ground robots to 3D UAV navigation. Samples candidate velocity commands within the drone's dynamic limits, simulates short trajectories for each, and selects the velocity that best balances goal progress, obstacle clearance, and smoothness. Purely reactive -- no map or prediction required.

**Complexity:** O(v) per cycle where v is number of velocity samples (~100-500). Runs at 50+ Hz.

**Real-drone results:** Demonstrated on real quadrotors for basic obstacle avoidance.

**Implementation recommendation:** Use as the **lowest-level reactive controller** when other planners fail or are too slow. DWA-3D is the "panic mode" avoidance -- simple, fast, and always available. Sits below APF in the control hierarchy.

---

### 7.3 SPOT -- Spatio-Temporal Obstacle-Free Trajectory Planning

**Citation:** arXiv:2602.01189, "SPOT: Spatio-Temporal Obstacle-free Trajectory Planning for UAVs in Unknown Dynamic Environments," 2026.

**Summary:** A 4D (x, y, z, t) planner that constructs spatio-temporal safe flight corridors by predicting obstacle trajectories and carving time-varying free-space volumes. Trajectory optimization then finds smooth paths within these 4D corridors. Handles unknown environments with dynamic obstacles using vision-based detection and tracking.

**Complexity:** Corridor generation: ~20ms. Trajectory optimization: ~15ms. Total: real-time at 30 Hz.

**Real-drone results:** Tested with onboard sensing in environments with moving obstacles.

**Implementation recommendation:** **Leading-edge approach for dynamic environments.** The spatio-temporal corridor concept is the most principled way to handle moving obstacles. Implement as the primary dynamic avoidance module, with DWA-3D/APF as reactive fallbacks.

---

### 7.4 Velocity and Acceleration Obstacles

**Citation:** arXiv:2506.06255, "From NLVO to NAO: Reactive Robot Navigation using Velocity and Acceleration Obstacles," 2025.

**Summary:** Extends Velocity Obstacles to Nonlinear Velocity Obstacles (NLVO) for curved obstacle trajectories, and further to Acceleration Obstacles (NAO) that account for the drone's acceleration limits. This provides tighter, more realistic avoidance constraints than linear VO methods. Requires fewer velocity adjustments when obstacles follow curved paths.

**Complexity:** O(k) per obstacle for VO computation. Real-time for 10-20 obstacles.

**Real-drone results:** Simulation with curved-trajectory obstacles.

**Implementation recommendation:** Integrate with ORCA (Section 5.3) for inter-drone avoidance. The acceleration-obstacle formulation is more realistic for quadrotors, which have bounded thrust.

---

### 7.5 Intent Prediction for Dynamic Avoidance

**Citation:** arXiv:2409.15633, "Intent Prediction-Driven Model Predictive Control for UAV Planning and Navigation in Dynamic Environments," 2024.

**Summary:** Uses learned intent prediction models to forecast where dynamic obstacles (people, vehicles, other drones) will go, rather than assuming constant velocity. The predicted intent distributions feed into a stochastic MPC that plans risk-bounded trajectories. Significantly outperforms constant-velocity prediction for structured obstacle motion (e.g., pedestrians following sidewalks).

**Complexity:** Intent prediction: ~15ms (neural network inference). MPC: ~10ms. Requires training data for the prediction model.

**Real-drone results:** Simulation with pedestrian and vehicle models.

**Implementation recommendation:** Future enhancement for urban drone operations. For initial SDK release, constant-velocity prediction (as in DPMPC-Planner) is sufficient. Add intent prediction as a v2.0 feature when operating in pedestrian-dense environments.

---

## 8. Geofencing and Airspace Compliance

### 8.1 Dynamic Geofencing for UAVs

**Citation:** arXiv:2110.09453, "A New Approach to Complex Dynamic Geofencing for Unmanned Aerial Vehicles," 2021.

**Summary:** Defines two types of geofences: keep-in (the drone must stay inside) and keep-out (the drone must not enter). Dynamic geofences can change shape and position over time (e.g., temporary flight restrictions, moving emergency zones). The system compares the UAV's current position against geofence boundaries and triggers enforcement actions: warnings at the enhanced warning zone, control takeover at the geofence boundary, and immediate landing if violated.

**Complexity:** Point-in-polygon testing: O(e) per geofence where e is number of edges. For convex geofences, O(log e). Real-time for hundreds of geofences.

**Real-drone results:** Implemented in DJI and ArduPilot firmware. GPS-based enforcement is standard on commercial drones.

**Implementation recommendation:** **Must-implement for regulatory compliance.** The SDK needs: (1) a geofence database (preloaded + dynamic updates), (2) continuous position checking at the control loop rate, (3) graduated response (warn -> slow -> stop -> land). Support both polygon and cylindrical geofence shapes. Integrate with AirMap or similar geofence data providers.

---

### 8.2 NASA UTM -- Unmanned Traffic Management

**Citation:** IEEE 9081718, "Flight Demonstration of Unmanned Aircraft System (UAS) Traffic Management (UTM) at Technical Capability Level 3." Also: IEEE 8730856, "Drone Flight Planning for Safe Urban Operations: UTM Requirements and Tools."

**Summary:** NASA's UTM system defines four Technical Capability Levels (TCL). TCL-3 (demonstrated in 2019) includes: strategic deconfliction (pre-flight path approval), conformance monitoring (real-time tracking), contingency management (what-if scenarios), and dynamic airspace management. The UTM ecosystem uses UAS Service Suppliers (USS) as intermediaries between drone operators and air traffic control. Drones submit flight plans, receive approval/denial, and report position during flight.

**Complexity:** System architecture complexity (REST APIs, real-time telemetry). Algorithmic complexity is low (geofence checking, flight plan validation).

**Real-drone results:** NASA flight demonstrations with multiple operators and USS providers in urban environments. FAA has adopted UTM concepts into operational LAANC system.

**Implementation recommendation:** **Integrate USS API connectivity into the SDK.** The SDK should: (1) submit flight plans to a USS before takeoff, (2) report real-time telemetry during flight, (3) receive and respond to dynamic airspace constraints, (4) handle flight plan modifications. Use the InterUSS Platform (open-source) for testing. This is required for legal commercial operations in the US.

---

### 8.3 Geofence Sizing for Safety

**Citation:** IEEE 9925807, "Airspace Geofencing Volume Sizing with an Advanced Air Mobility Vehicle Performance Model."

**Summary:** Determines how large a geofence volume needs to be around a drone's planned trajectory to statistically guarantee the drone stays inside despite wind, GPS error, control delays, and emergency maneuvers. Uses vehicle performance models (max speed, max climb rate, response time) to compute safety buffers. The buffer size depends on the vehicle's kinetic energy and worst-case stopping distance.

**Complexity:** Closed-form calculation based on vehicle parameters. O(1) per trajectory segment.

**Real-drone results:** Validated with Advanced Air Mobility vehicle models.

**Implementation recommendation:** **Implement geofence buffer calculation based on vehicle dynamics.** Each drone type in the SDK should have a performance model (max speed, max acceleration, GPS accuracy) that determines the minimum safe buffer distance from geofence boundaries. Build this into the path planner as a hard constraint.

---

### 8.4 UTM Security Challenges

**Citation:** arXiv:2408.11125, "Towards the Unmanned Aerial Vehicle Traffic Management Systems (UTMs): Security Risks and Challenges," 2024. Also: arXiv:2601.08229, "A Survey of Security Challenges and Solutions for UAS Traffic Management (UTM) and small Unmanned Aerial Systems (sUAS)," 2026.

**Summary:** Identifies critical security vulnerabilities in UTM systems: GPS spoofing, communication jamming, unauthorized airspace access, and man-in-the-middle attacks on USS communications. Proposes countermeasures including multi-sensor navigation (GPS + visual + IMU), encrypted communication channels, blockchain-based flight logging, and anomaly detection for spoofing.

**Complexity:** Security implementation varies. Encrypted communications add minimal overhead. Multi-sensor fusion requires additional hardware.

**Real-drone results:** Security analyses based on real UTM deployments. GPS spoofing attacks demonstrated in controlled settings.

**Implementation recommendation:** Design the UTM integration layer with security from the start: TLS for all USS communications, GPS spoofing detection (compare GPS with IMU dead-reckoning), and signed flight logs. These are not optional for commercial deployment.

---

## 9. Implementation Roadmap

Based on this literature review, here is the recommended implementation priority for the SDK's path planning module:

### Phase 1: Core Foundation (Must-Have)

| Component | Paper/Method | Rationale |
|-----------|-------------|-----------|
| Trajectory representation | Mellinger-Kumar minimum snap polynomials | Industry standard, QP-solvable, differential flatness |
| Global planner (known maps) | A* with energy-weighted edges | Fast, optimal, well-understood |
| Global planner (unknown) | Informed RRT* | Asymptotically optimal, fast convergence |
| Reactive safety layer | APF with velocity-adaptive improvements | O(n) per step, last line of defense |
| Geofencing | Keep-in/keep-out with safety buffers | Regulatory requirement |
| Battery management | Return-to-base with emergency landing zones | Safety requirement |

### Phase 2: Multi-Drone (High Priority)

| Component | Paper/Method | Rationale |
|-----------|-------------|-----------|
| Centralized deconfliction | CBS (bounded-suboptimal ECBS) | Optimal, proven for MAPF |
| Decentralized avoidance | ORCA / V-RVO | Fast, runs on each drone independently |
| Swarm trajectory planner | EGO-Swarm architecture | Best demonstrated decentralized swarm result |
| Formation control | SwarmPath impedance control | Validated on real Crazyflies, 6% sim-to-real gap |

### Phase 3: Advanced Features (Enhancement)

| Component | Paper/Method | Rationale |
|-----------|-------------|-----------|
| Local planning pipeline | Fast-Planner (kinodynamic A* + B-spline) | Proven real-time performance |
| Dynamic obstacle avoidance | DPMPC-Planner (two-phase) + SPOT corridors | Principled predict-then-plan architecture |
| Energy optimization | Wind-aware planning + optimal cruise speed | 15-30% energy savings |
| UTM integration | NASA UTM / InterUSS APIs | Required for commercial operations |
| Smooth trajectory post-processing | Dubins airplane + LP smoothing | Improves flyability of any planner output |

### Phase 4: Research/Experimental

| Component | Paper/Method | Rationale |
|-----------|-------------|-----------|
| Learned planning | Neural Informed RRT* | Requires onboard GPU, training data |
| MARL swarm control | MARLander-style policies | Sim-to-real gap still challenging |
| Intent prediction | Intent-driven MPC | Requires training data for obstacle types |
| Time-optimal trajectories | Alternating peak optimization | For aggressive/racing applications |

### Hardware Testbed Recommendation

Use **Crazyswarm2** (Crazyflie 2.1 drones + VICON/OptiTrack) for initial development and validation. The Crazyflie platform costs ~$200/unit, supports polynomial trajectory upload, and has the largest open-source swarm codebase. Design all trajectory interfaces to be compatible with Crazyswarm2's format, then abstract for other platforms (PX4, ArduPilot).

---

## Sources

### Dubins Paths / Smooth Trajectories
- [Path planning using 3D Dubins Curve for UAVs](https://ieeexplore.ieee.org/document/6842268/)
- [A literature review of UAV 3D path planning](https://ieeexplore.ieee.org/document/7053093/)
- [A Novel Model for 3D Motion Planning for a Generalized Dubins Vehicle](https://arxiv.org/abs/2509.24143)
- [Simple Trajectory Smoothing for UAV Reference Path Planning](https://arxiv.org/abs/2603.21713)
- [Implementing Dubins Airplane Paths on Fixed-Wing UAVs](https://link.springer.com/rwe/10.1007/978-90-481-9707-1_120)
- [dubins Python library](https://pypi.org/project/dubins/)

### A* and RRT
- [Motion Planning for Robotics: A Review for Sampling-based Planners](https://arxiv.org/html/2410.19414v1)
- [Comparative Analysis of UAV Path Planning Algorithms in Urban 3D](https://arxiv.org/html/2508.16515v1)
- [UAV Path Planning System Based on 3D Informed RRT*](https://ieeexplore.ieee.org/document/8665162/)
- [Neural Informed RRT*](https://arxiv.org/abs/2309.14595)
- [Multi-goal RRT with Safety and Dynamic Constraints](https://arxiv.org/html/2504.11823)
- [Systematic Comparison of Path Planning Algorithms using PathBench](https://ar5iv.labs.arxiv.org/html/2203.03092)

### Trajectory Optimization
- [Minimum snap trajectory generation and control for quadrotors -- Mellinger & Kumar](https://ieeexplore.ieee.org/document/5980409/)
- [Robust and Efficient Quadrotor Trajectory Generation (Fast-Planner)](https://arxiv.org/pdf/1907.01531)
- [EGO-Planner: An ESDF-free Gradient-based Local Planner](https://ieeexplore.ieee.org/document/9309347/)
- [EGO-Swarm: Decentralized Quadrotor Swarm System](https://arxiv.org/abs/2011.04183)
- [Online Time-Optimal Trajectory Generation for Two Quadrotors](https://arxiv.org/html/2402.18021v1)
- [Aggressive Trajectory Generation for Racing Drone Swarms](https://arxiv.org/abs/2303.00851)
- [Crazyswarm: A large nano-quadcopter swarm](https://whoenig.github.io/publications/2017_ICRA_Preiss_Hoenig.pdf)
- [Crazyswarm2 Documentation](https://imrclab.github.io/crazyswarm2/)

### Potential Field Planning
- [Path Planning with Potential Field-Based Obstacle Avoidance in 3D](https://arxiv.org/html/2306.16276)
- [Improved Artificial Potential Field Method for UAV Path Planning](https://ieeexplore.ieee.org/document/11199033/)
- [Velocity-Adaptive Artificial Potential Field](https://arxiv.org/html/2512.07609)
- [SwarmPath: Drone Swarm Navigation with APF and Impedance Control](https://arxiv.org/html/2410.07848v1)
- [Robust UAV Path Planning with APF-SA](https://arxiv.org/html/2501.09338v1)
- [Path Planning for Dense Drone Formation with Modified APF](https://ieeexplore.ieee.org/document/9189345/)

### Decentralized Planning
- [Conflict-Based Search for Optimal Multi-Agent Pathfinding -- Sharon et al.](https://www.sciencedirect.com/science/article/pii/S0004370214001386)
- [CBS for Multi-Robot Motion Planning with Kinodynamic Constraints](https://arxiv.org/abs/2207.00576)
- [V-RVO: Decentralized Multi-Agent Collision Avoidance using Voronoi](https://arxiv.org/pdf/2102.13281)
- [MARLander: Drone Swarm Planning with MARL](https://arxiv.org/html/2406.04159v1)
- [Robust and Decentralized RL for UAV Path Planning](https://arxiv.org/html/2312.06250v1)
- [Robust Trajectory Planning for Multi-Drone Coordination in Large Scenes](https://ar5iv.labs.arxiv.org/html/2109.08403)
- [Integrated Multi-Drone Task Allocation and Trajectory Generation](https://arxiv.org/html/2603.24908)

### Energy-Aware Planning
- [Energy-Optimal Planning of Waypoint-Based UAV Missions](https://arxiv.org/html/2410.17585v1)
- [Energy-aware Multi-UAV Coverage with Optimal Speed](https://arxiv.org/html/2402.10529v1)
- [Energy-Efficiency Path Planning Under Wind Conditions](https://ar5iv.labs.arxiv.org/html/2004.00182)
- [EcoFlight: Low-Energy Paths Through Obstacles](https://arxiv.org/html/2511.12618v1)
- [How to Save a Drone in Case of Low Battery](https://ieeexplore.ieee.org/document/10397242)
- [Vision-Based Risk Aware Emergency Landing](https://arxiv.org/html/2505.20423v1)
- [Autonomous Recharging and Flight Mission Planning](https://arxiv.org/pdf/1703.10049)
- [Overview of Drone Energy Consumption Factors](https://arxiv.org/pdf/2206.10775)
- [ARENA: Adaptive Risk-aware Energy-efficient Navigation](https://arxiv.org/html/2502.19401v1)

### Dynamic Obstacle Avoidance
- [DPMPC-Planner: Real-time UAV Trajectory with Dynamic Obstacles](https://arxiv.org/abs/2109.07024)
- [DWA-3D: Reactive Planner for UAV Navigation](https://arxiv.org/html/2409.05421v1)
- [SPOT: Spatio-Temporal Obstacle-free Trajectory Planning](https://arxiv.org/html/2602.01189v1)
- [From NLVO to NAO: Velocity and Acceleration Obstacles](https://arxiv.org/html/2506.06255)
- [Intent Prediction-Driven MPC for UAV Navigation](https://arxiv.org/html/2409.15633)
- [Real-Time Obstacle Avoidance Algorithms Survey](https://arxiv.org/html/2506.20311v1)

### Geofencing and Airspace Compliance
- [Complex Dynamic Geofencing for UAVs](https://arxiv.org/pdf/2110.09453)
- [UTM Flight Demonstration at Technical Capability Level 3](https://ieeexplore.ieee.org/document/9081718/)
- [Drone Flight Planning for Safe Urban Operations: UTM Requirements](https://ieeexplore.ieee.org/document/8730856/)
- [Airspace Geofencing Volume Sizing](https://ieeexplore.ieee.org/document/9925807/)
- [UTM Security Risks and Challenges](https://arxiv.org/html/2408.11125v1)
- [Survey of Security Challenges for UTM and sUAS](https://arxiv.org/html/2601.08229)
