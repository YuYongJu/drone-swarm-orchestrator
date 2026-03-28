# Collision Avoidance Algorithm Literature Review

**Date:** 2026-03-26
**Purpose:** Select the best collision avoidance algorithm for the DSO open-source drone swarm SDK
**Constraint:** GPS-based outdoor drones, 2-5m position error, 10 drones, ground station at 10Hz

---

## Executive Summary & Recommendation

| Priority | Algorithm | Version | Rationale |
|----------|-----------|---------|-----------|
| **1st (v0.1)** | **ORCA (3D)** | MVP | Best ratio of safety guarantees to implementation effort. RVO2-3D library exists. |
| **2nd (v0.2)** | **BVC** | Near-term | Already proven in Crazyswarm firmware. Simpler math than ORCA. Good fallback. |
| **3rd (v0.3)** | **CBF-QP** | Mid-term | Formal safety guarantees. Layer on top of ORCA as a safety filter. |
| **4th (v1.0+)** | **GCBF+ (learned CBF)** | Long-term | State-of-the-art from MIT, scales to 1024 agents, but needs ML infrastructure. |
| **Skip** | APF | -- | Local minima problem is fundamental. Not suitable as primary algorithm. |
| **Skip** | Pure RL | -- | Sim-to-real gap too large. No formal safety guarantees. Not ready for production. |

**Bottom line: Start with ORCA using the RVO2-3D library (Apache 2.0). It runs in microseconds for 10 agents, has 15+ years of validation, and existing Python bindings. Add a 10m safety radius to handle GPS error.**

---

## 1. ORCA (Optimal Reciprocal Collision Avoidance)

### Citation
- van den Berg, J., Guy, S.J., Lin, M., & Manocha, D. (2011). "Reciprocal n-Body Collision Avoidance." *Robotics Research*, Springer. [ORCA Project Page](https://gamma.cs.unc.edu/ORCA/)
- Snape, J., van den Berg, J., Guy, S.J., & Manocha, D. (2011). "The Hybrid Reciprocal Velocity Obstacle." *IEEE Trans. on Robotics*, 27(4).

### How It Works
Each agent computes a set of "ORCA half-planes" -- velocity constraints that guarantee collision-free motion if both agents respect them. Each agent takes exactly half the responsibility for avoiding each pairwise collision. The optimal collision-free velocity is found by solving a **low-dimensional linear program** (LP) over the intersection of all half-planes, selecting the velocity closest to the agent's preferred velocity.

### Computational Complexity
- **O(n)** per agent, where n = number of neighbors (each neighbor adds one half-plane constraint)
- For 10 drones: 10 agents x 9 neighbors = 90 LP constraints total. Solves in **microseconds**.
- The RVO2 library computes collision-free actions for **thousands of agents in a few milliseconds**.
- **Verdict: Easily runs at 100Hz+ for 10 drones on any modern hardware.**

### Variants
| Variant | Description | Relevance |
|---------|-------------|-----------|
| **RVO2-3D** | 3D extension of ORCA, open-source (Apache 2.0) | **Direct fit for drones** |
| **NH-ORCA** | Non-holonomic ORCA for differential-drive constraints | Less relevant (drones are ~holonomic) |
| **AVO** | Acceleration-Velocity Obstacles -- accounts for acceleration limits | Useful enhancement for smoother trajectories |
| **d-ORCA** | Distributed ORCA for quadrotor swarms (UMD) | Simulation package for up to 50 quads |
| **H-ORCA** | Hierarchical ORCA for UAVs in unstructured terrain (2025) | Addresses local minima + velocity optimization |
| **ORCA-FLC** | ORCA + Fuzzy Logic Controller (2025) | Improved obstacle avoidance |

### Real Drone Implementations
- **d-ORCA** (UMD GAMMA Lab): Decentralized collision avoidance simulation for up to 50 quadrotors. [d-ORCA Project](https://gamma.umd.edu/researchdirections/aerialswarm/dorca/)
- **Crazyswarm** originally used BVC but ORCA variants have been tested on iRobot Create robots and e-puck swarms (14 robots).
- **ORCA-A* hybrid** (2024): Combined ORCA with A* for drone path planning. [SIDs 2024 Paper](https://www.sesarju.eu/sites/default/files/documents/sid/2024/papers/SIDs_2024_paper_059%20final.pdf)
- H-ORCA (2025): Tested for multi-UAV navigation in unstructured environments.

### Pros/Cons for GPS-Based Outdoor Drones

| Pros | Cons |
|------|------|
| Extremely fast (microseconds for 10 agents) | Assumes perfect position knowledge -- GPS error requires large safety radius |
| Formal collision-free guarantee (under assumptions) | Velocity-only model; ignores acceleration dynamics |
| Decentralized -- each drone computes independently | Can get stuck in symmetric deadlock configurations |
| Mature open-source library (RVO2, Apache 2.0) | Original formulation is 2D; need RVO2-3D for drones |
| Python bindings available (mit-acl/Python-RVO2) | Does not handle static obstacles natively in 3D version |

### Implementation Difficulty
- **Using RVO2-3D library:** ~200-400 lines of integration code (Python wrapper already exists)
- **From scratch:** ~1000-1500 lines (LP solver + half-plane computation)
- **Key repos:**
  - C++ core: [snape/RVO2](https://github.com/snape/RVO2)
  - Python 3D bindings: [mtreml/Python-RVO2-3D](https://github.com/mtreml/Python-RVO2-3D)
  - Python 2D bindings: [mit-acl/Python-RVO2](https://github.com/mit-acl/Python-RVO2)

### GPS Error Mitigation Strategy
With 2-5m GPS error, set ORCA's agent radius to **actual_radius + GPS_error + safety_margin** = 0.5m + 5m + 2m = **7.5m effective radius**. This means drones maintain ~15m minimum separation. Conservative but safe. Can shrink with RTK-GPS (5cm error).

### **Recommendation: YES -- implement in v0.1 (MVP)**

---

## 2. Velocity Obstacles (VO / RVO)

### Citation
- Fiorini, P. & Shiller, Z. (1998). "Motion Planning in Dynamic Environments Using Velocity Obstacles." *Int. Journal of Robotics Research*, 17(7), 760-772. [Sage Publication](https://journals.sagepub.com/doi/10.1177/027836499801700706)
- van den Berg, J., Lin, M., & Manocha, D. (2008). "Reciprocal Velocity Obstacles for Real-Time Multi-Agent Navigation." *ICRA 2008*. [PDF](https://gamma.cs.unc.edu/RVO/icra2008.pdf)

### How It Works
A Velocity Obstacle (VO) is the set of all velocities that would cause a collision with another agent within a time horizon. The robot selects a velocity outside all VOs. **RVO** improves on VO by having each agent take half the responsibility for avoidance (same principle as ORCA). ORCA is the further refinement that linearizes the VO boundary for computational efficiency.

### Evolution: VO --> RVO --> HRVO --> ORCA
| Algorithm | Year | Key Improvement |
|-----------|------|-----------------|
| VO | 1998 | Original concept -- velocity space collision cones |
| RVO | 2008 | Reciprocal avoidance -- eliminates oscillations |
| HRVO | 2009 | Hybrid -- combines VO and RVO for better behavior |
| ORCA | 2011 | Linearized half-planes -- LP-solvable, formal guarantees |

### Computational Complexity
- VO/RVO: O(n) per agent, similar to ORCA but ORCA is more efficient due to LP formulation
- All variants easily run at 10Hz+ for 10 drones

### Best for GPS-Based Outdoor Drones?
**ORCA is strictly better than VO/RVO** for our use case:
- VO causes oscillatory motion (each agent assumes others are passive)
- RVO fixes oscillation but lacks formal guarantees
- ORCA provides guarantees AND is computationally simpler

### **Recommendation: NO -- use ORCA instead (VO/RVO are superseded)**

---

## 3. Artificial Potential Fields (APF)

### Citation
- Khatib, O. (1986). "Real-Time Obstacle Avoidance for Manipulators and Mobile Robots." *Int. Journal of Robotics Research*, 5(1), 90-98.
- Recent: SwarmPath (2024), Quantum-APF (2025), GWO-APF (2024)

### How It Works
Each drone experiences virtual attractive forces toward its goal and repulsive forces from obstacles and other drones. The gradient of the combined potential field determines the velocity command. Simple and intuitive -- like charged particles repelling each other.

### The Local Minima Problem
The fundamental flaw: when attractive and repulsive forces cancel exactly, the drone gets stuck. This is **mathematically guaranteed to occur** in certain configurations (e.g., goal directly behind an obstacle).

### Recent Solutions (2020-2025)
| Approach | Year | Fix |
|----------|------|-----|
| Enhanced curl-free vector field | 2020 | Modified potential to eliminate equilibria |
| Rotational force addition | 2024 | Adds tangential force to escape minima |
| GWO-APF (Grey Wolf Optimizer) | 2024 | Meta-heuristic optimization of potential params |
| Vortex APF + RL | 2025 | RL dynamically adjusts target position |
| Quantum-Enhanced APF | 2025 | Probabilistic exploration via superposed decision states |
| SwarmPath (APF + Impedance Control) | 2024 | Cluttered environment navigation |

### Computational Complexity
- O(n) per agent -- just sum forces from all neighbors
- **Extremely fast** -- cheaper than ORCA
- 10 drones at 10Hz: trivial

### Pros/Cons for GPS-Based Outdoor Drones

| Pros | Cons |
|------|------|
| Simplest to implement (~200 lines) | **Local minima** -- fundamental unsolved problem |
| Very fast computation | No formal collision-free guarantee |
| Intuitive tuning (adjust force magnitudes) | Parameter tuning is fragile (gain values) |
| Works well as a secondary repulsive layer | Oscillatory behavior near obstacles |
| Good for geofencing / keep-out zones | Poor in narrow passages or symmetric configs |

### Implementation Difficulty
- **~100-200 lines** for basic implementation
- **~500 lines** with local minima fixes (rotational forces, random perturbation)

### **Recommendation: PARTIAL -- use as supplementary repulsive force layer, not primary algorithm**
APF is useful as a simple "emergency repulsion" backup underneath ORCA. If ORCA fails for any reason, a repulsive potential field at close range provides a last line of defense. Do NOT use as the primary collision avoidance algorithm.

---

## 4. Buffered Voronoi Cells (BVC)

### Citation
- Zhou, D., Wang, Z., Bandyopadhyay, S., & Schwager, M. (2017). "Fast, On-line Collision Avoidance for Dynamic Vehicles Using Buffered Voronoi Cells." *IEEE Robotics and Automation Letters*, 2(2). [Stanford PDF](https://msl.stanford.edu/papers/zhou_fast_2017.pdf)
- Zhu, H., Alonso-Mora, J. (2019). "B-UAVC: Buffered Uncertainty-Aware Voronoi Cells." *MRS 2019*. [PDF](https://autonomousrobots.nl/assets/files/publications/19-zhu-mrs.pdf)

### How It Works
Each robot computes its Voronoi cell (the region of space closer to it than to any other robot), then shrinks it inward by a safety buffer radius. Each robot is constrained to move only within its Buffered Voronoi Cell. Since BVCs never overlap by construction, **collision avoidance is guaranteed** as long as each agent stays in its cell. Planning is done in a receding-horizon fashion within the BVC.

### Computational Complexity
- Voronoi computation: O(n log n) per agent
- Path planning within cell: depends on method (simple projection is O(1))
- **Same order as ORCA** -- runs in milliseconds for 10 drones
- Crazyswarm firmware runs BVC **onboard** tiny Crazyflie microcontrollers

### Real Drone Implementations
- **Crazyswarm / Crazyswarm2**: BVC is the **official collision avoidance algorithm** in the Crazyflie firmware. Requires motion capture for position knowledge. [Crazyswarm2 Docs](https://imrclab.github.io/crazyswarm2/)
- **B-UAVC** (Buffered Uncertainty-Aware Voronoi Cells): Extension that accounts for position uncertainty. Validated with 2 real Crazyflie quadrotors on crossing paths, and 4 quadrotors in CoppeliaSim.
- Simulations with 6+ quadrotors demonstrated same safety level as centralized methods.

### Pros/Cons for GPS-Based Outdoor Drones

| Pros | Cons |
|------|------|
| **Proven in real drone firmware** (Crazyswarm) | Requires all agents to know all neighbors' positions |
| Guaranteed collision-free (by construction) | Conservative -- large BVC buffers limit density |
| Decentralized computation | Voronoi cells can become very small in tight formations |
| B-UAVC variant handles position uncertainty | Original assumes single-integrator dynamics |
| Simple conceptually -- "stay in your cell" | Performance degrades with many agents in small area |

### Implementation Difficulty
- **~300-500 lines** for core BVC (Voronoi + buffering + projection)
- **~800 lines** with B-UAVC uncertainty handling
- Need a Voronoi library (scipy.spatial.Voronoi works for 2D; 3D is harder)

### GPS Error Handling
B-UAVC explicitly accounts for position uncertainty by further shrinking the Voronoi cell based on the uncertainty bound. With 2-5m GPS error, cells shrink significantly -- works but very conservative. Better with RTK-GPS.

### **Recommendation: YES -- implement in v0.2 as alternative/fallback to ORCA**
BVC is battle-tested in Crazyswarm. Having both ORCA and BVC gives users a choice. BVC is conceptually simpler and may be easier for users to understand and debug.

---

## 5. Control Barrier Functions (CBF)

### Citation
- Ames, A.D., Coogan, S., Egerstedt, M., Notomista, G., Sreenath, K., & Tabuada, P. (2019). "Control Barrier Functions: Theory and Applications." *ECC 2019*. [PDF](https://coogan.ece.gatech.edu/papers/pdf/amesecc19.pdf)
- Ames, A.D., Xu, X., Grizzle, J.W., & Tabuada, P. (2017). "Control Barrier Function Based Quadratic Programs for Safety Critical Systems." *IEEE TAC*. [Paper](https://arxiv.org/abs/1609.06408)
- Luo, W., Sun, W., & Kapoor, A. (2024). "Multi-Robot Collision Avoidance using CBFs." [Caltech PDF](http://ames.caltech.edu/chen2021guaranteed.pdf)

### How It Works
A Control Barrier Function (CBF) defines a "safe set" in the state space (e.g., "all states where inter-drone distance > d_min"). The CBF condition constrains the control input so the system state **never leaves the safe set**. At each timestep, the controller solves a **Quadratic Program (QP)**: minimize deviation from desired control input, subject to CBF safety constraints. This gives **mathematically provable safety guarantees** -- the strongest of any method in this review.

### Computational Complexity
- Solving a QP with n safety constraints: O(n^2) to O(n^3) depending on solver
- For 10 drones (45 pairwise constraints): solvable in **< 1ms** with modern QP solvers (OSQP, qpOASES)
- Has been demonstrated on racing drones at 100+ km/h on a **10-gram microcontroller**
- Can solve for hundreds of robots within milliseconds
- **Verdict: Feasible at 10Hz for 10 drones. Tight at 100Hz for 50+ drones.**

### Scalability Challenges
- **Coupled CBF-QP**: All agents in one QP -- optimal but O(n^3), doesn't scale past ~20 agents
- **Decentralized CBF-QP**: Each agent solves its own QP -- scales well but can deadlock
- **GCBF+** (MIT, 2024-2025): Neural network parameterized CBF, scales to 1024 agents (see Section 7)

### Pros/Cons for GPS-Based Outdoor Drones

| Pros | Cons |
|------|------|
| **Strongest safety guarantee** (formal proof of invariance) | More complex math than ORCA or BVC |
| Works as a "safety filter" on top of any controller | QP solver dependency (need OSQP or similar) |
| Handles nonlinear dynamics naturally | Designing the CBF requires domain expertise |
| Can encode multiple safety constraints (altitude, geofence, etc.) | Decentralized version can deadlock |
| Proven on real racing drones at high speed | Conservative when safety margin is large |

### Implementation Difficulty
- **~500-800 lines** for CBF-QP safety filter (using OSQP)
- **~1500+ lines** for full multi-agent CBF with deadlock resolution
- Requires understanding of Lyapunov stability and optimization

### **Recommendation: YES -- implement in v0.3 as a safety filter layer**
CBF is best used as a **safety filter** that wraps around ORCA or any other controller. The ORCA output becomes the "desired input" to the CBF-QP, which adjusts it minimally to maintain safety. This gives you both ORCA's efficiency and CBF's formal guarantees.

---

## 6. Deep Reinforcement Learning (DRL) Approaches

### Key Citations
- Loquercio, A. et al. (2021). "Learning High-Speed Flight in the Wild." *Science Robotics*. (Single drone, not swarm)
- Zhou, X. et al. (2022). "Swarm of Micro Flying Robots in the Wild." *Science Robotics*. [Paper](https://www.science.org/doi/10.1126/scirobotics.abm5954) (Uses optimization, not RL)
- Multi-UAV Formation Control with RL (2024): PPO achieved 92% collision-free success rate. [arXiv](https://arxiv.org/html/2410.18495v2)
- Sim-to-Real DRL Obstacle Avoidance under Measurement Uncertainty (2024): [IEEE](https://ieeexplore.ieee.org/document/10553074/)
- Decentralized Control of Quadrotor Swarms with End-to-End DRL: [USC RESL](https://uscresl.org/wp-content/uploads/2024/03/decentralized-control-of-quadrotor-swarms.pdf)
- Survey on UAV Control with MARL (2025): [MDPI](https://www.mdpi.com/2504-446X/9/7/484)

### How It Works
Train a neural network policy in simulation (AirSim, Gazebo, Isaac Sim) to output velocity/acceleration commands that avoid collisions. Multi-agent variants (MAPPO, MADDPG, QMIX) train cooperative policies. Transfer to real drones via domain randomization and action smoothing.

### State of the Art (2024-2026)
- **PPO**: 92% collision-free rate in simulation
- **SAC**: Best for continuous control and environmental uncertainty
- **AM-MAPPO**: Action-mask-based MAPPO for 3D UAV search with collision avoidance
- **Sim-to-real**: Still a major challenge. Works for single drones; multi-drone sim-to-real is immature.

### Computational Complexity
- **Inference**: O(1) per agent -- just a forward pass through a neural network (~1ms on GPU, ~10ms on CPU)
- **Training**: Hours to days on GPU clusters
- **Verdict: Fast at inference, but training pipeline is heavy**

### Pros/Cons for GPS-Based Outdoor Drones

| Pros | Cons |
|------|------|
| Can learn complex behaviors end-to-end | **No formal safety guarantees** |
| Adapts to sensor noise naturally (if trained with it) | **Sim-to-real gap** -- 92% is not enough for safety |
| Can handle high-dimensional state spaces | Requires GPU for training, significant compute |
| Active research area with rapid progress | Black box -- hard to debug failures |
| MAPPO shows promise for cooperative behavior | Needs massive training data/simulation infrastructure |

### Implementation Difficulty
- **~2000-5000 lines** for training pipeline + inference
- Requires simulation environment (Gazebo, AirSim)
- Requires ML framework (PyTorch, JAX)
- Domain randomization for sim-to-real transfer

### **Recommendation: NO for primary collision avoidance. WATCH for v1.0+.**
92% collision-free is unacceptable for safety-critical systems. RL is promising for high-level swarm coordination (task allocation, formation planning) but should NOT be the collision avoidance layer. Consider GCBF+ (Section 7) which combines learned policies with formal CBF guarantees.

---

## 7. GCBF+ (Neural Graph Control Barrier Functions) -- State of the Art

### Citation
- Zhang, S., So, O., Garg, K., & Fan, C. (2024/2025). "GCBF+: A Neural Graph Control Barrier Function Framework for Distributed Safe Multi-Agent Control." *IEEE Transactions on Robotics*, 2025. [arXiv](https://arxiv.org/abs/2401.14554) | [Project Page](https://mit-realm.github.io/gcbfplus/) | [GitHub (JAX)](https://github.com/MIT-REALM/gcbfplus)

### How It Works
Uses a **Graph Neural Network (GNN)** to parameterize both the Control Barrier Function and the distributed control policy. Each agent receives neighbor information through graph edges, computes a CBF value and control action. The GNN is trained to satisfy CBF conditions, giving **learned safety guarantees that generalize to any swarm size**. Key insight: a GCBF certified for n agents can certify safety for any number of agents.

### Performance
- Outperforms hand-crafted CBF methods by up to **20%** for up to 256 agents
- Outperforms RL methods by up to **40%** for 1024 agents
- Validated on **real Crazyflie drone swarms** (position exchange, moving target docking)
- Can take raw **LiDAR point clouds** as input

### Computational Complexity
- GNN inference: O(n * k) where k = neighbor count (sparse graph)
- Faster than coupled CBF-QP for large swarms
- Requires JAX + GPU for training; inference can run on CPU

### Pros/Cons for GPS-Based Outdoor Drones

| Pros | Cons |
|------|------|
| **Formal safety guarantees** (CBF theory) | Requires ML training infrastructure (JAX, GPU) |
| Scales to 1000+ agents | Newer -- less battle-tested than ORCA |
| Works with raw sensor data (LiDAR) | Model needs retraining for new dynamics |
| Validated on real Crazyflie drones | More complex to debug than geometric methods |
| State-of-the-art results (IEEE T-RO 2025) | JAX ecosystem less mature than PyTorch |

### **Recommendation: YES for v1.0+ (long-term)**
This is the most promising direction for large-scale swarms with safety guarantees. But it requires significant ML infrastructure. Plan for it in the roadmap but don't block the MVP.

---

## 8. EGO-Swarm (Bonus -- Trajectory Planning)

### Citation
- Zhou, X., Zhu, J., Zhou, H., Xu, C., & Gao, F. (2021). "EGO-Swarm: A Fully Autonomous and Decentralized Quadrotor Swarm System in Cluttered Environments." *ICRA 2021*. [GitHub](https://github.com/ZJU-FAST-Lab/ego-planner-swarm)
- Zhou, X. et al. (2022). "Swarm of Micro Flying Robots in the Wild." *Science Robotics*. [Paper](https://www.science.org/doi/10.1126/scirobotics.abm5954)

### How It Works
Not a collision avoidance algorithm per se, but a full **trajectory planning system** for drone swarms. Uses B-spline trajectory optimization with inter-robot collision penalties, combined with topological path planning to escape local minima. Each drone shares its planned trajectory with neighbors and replans asynchronously. The Science Robotics 2022 paper demonstrated **10 drones navigating autonomously through a forest** without GPS, using only onboard stereo cameras.

### Relevance to DSO
- This is the gold standard for **onboard autonomous swarm navigation**
- Uses vision-based localization (not GPS) -- different paradigm from DSO's GPS-based approach
- Open source (ROS 1) but complex (~10,000+ lines)
- Not directly applicable to our GPS-based ground-station-controlled architecture

### **Recommendation: STUDY but don't implement. Different architecture paradigm.**

---

## 9. Comparison Matrix

| Algorithm | Safety Guarantee | Complexity (10 drones) | GPS Error Tolerance | Implementation LOC | Maturity | Real Drone Tested |
|-----------|-----------------|----------------------|--------------------|--------------------|----------|-------------------|
| **ORCA** | Yes (under assumptions) | O(n), ~0.1ms | Needs large radius (15m sep) | 200-400 (with lib) | High (15yr) | Yes (ground robots) |
| **VO/RVO** | Weaker than ORCA | O(n), ~0.1ms | Same as ORCA | 300-500 | High | Yes (ground robots) |
| **APF** | No | O(n), ~0.01ms | OK with large repulsion | 100-200 | High | Yes (many) |
| **BVC** | Yes (by construction) | O(n log n), ~1ms | B-UAVC handles uncertainty | 300-500 | Medium | Yes (Crazyswarm) |
| **CBF-QP** | **Yes (formal proof)** | O(n^2), ~1ms | Encodable in constraints | 500-800 | Medium | Yes (racing drones) |
| **DRL** | No | O(1) inference, ~10ms | Trained with noise | 2000-5000 | Low | Partial |
| **GCBF+** | **Yes (formal proof)** | O(n*k), ~5ms | Learnable | 1000-2000 | Low-Med | Yes (Crazyflie) |

---

## 10. Recommended Implementation Roadmap

### v0.1 (MVP) -- ORCA with Safety Radius
```
Algorithm: RVO2-3D (via Python-RVO2-3D bindings)
Safety radius: 7.5m per drone (0.5m physical + 5m GPS error + 2m margin)
Min separation: 15m between drones
Update rate: 10Hz on ground station
Fallback: APF emergency repulsion at < 8m
LOC estimate: ~400 lines integration code
```

### v0.2 -- Add BVC Alternative
```
Algorithm: Buffered Voronoi Cells (3D)
Why: Give users a choice; BVC is simpler to understand/debug
B-UAVC: Add uncertainty-aware variant for GPS error
LOC estimate: ~500 additional lines
```

### v0.3 -- CBF Safety Filter
```
Algorithm: CBF-QP safety filter wrapping ORCA
Why: Formal safety guarantee on top of ORCA output
QP Solver: OSQP (open source, fast, Python bindings)
Encodes: inter-drone separation, altitude bounds, geofence
LOC estimate: ~800 additional lines
```

### v1.0+ -- GCBF+ for Scale
```
Algorithm: GCBF+ (MIT, JAX-based)
Why: Scales to 1000+ drones with safety guarantees
Prerequisite: ML training infrastructure
LOC estimate: ~2000 lines (adapt from MIT's open-source code)
```

---

## 11. Key Insight: GPS Error Dominates Everything

With standard GPS (2-5m error), **the position uncertainty is larger than the drones themselves**. This means:

1. **All algorithms must use inflated safety radii** -- minimum 10m separation is prudent
2. **RTK-GPS (5cm accuracy) would be transformative** -- enables tight formations
3. **The choice of algorithm matters less than the choice of positioning system** at this error level
4. At 15m separation, even APF works fine -- the algorithms differentiate at closer ranges

**Practical implication:** For v0.1 with standard GPS, ORCA with a 7.5m agent radius is more than sufficient. Invest in RTK-GPS support early -- it unlocks the full potential of all these algorithms.

---

## Sources

- [ORCA Project Page - UNC](https://gamma.cs.unc.edu/ORCA/)
- [RVO2 C++ Library - GitHub](https://github.com/snape/RVO2)
- [Python-RVO2-3D Bindings - GitHub](https://github.com/mtreml/Python-RVO2-3D)
- [Python-RVO2 (MIT ACL) - GitHub](https://github.com/mit-acl/Python-RVO2)
- [d-ORCA: Distributed ORCA for Quadrotors - UMD](https://gamma.umd.edu/researchdirections/aerialswarm/dorca/)
- [H-ORCA Hierarchical Framework for UAVs (2025) - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0957417425028210)
- [ORCA-A* Hybrid (2024) - SESAR](https://www.sesarju.eu/sites/default/files/documents/sid/2024/papers/SIDs_2024_paper_059%20final.pdf)
- [VO Original Paper - Fiorini & Shiller 1998](https://journals.sagepub.com/doi/10.1177/027836499801700706)
- [RVO for Multi-Agent Navigation - ICRA 2008](https://gamma.cs.unc.edu/RVO/icra2008.pdf)
- [VO Approaches Survey - Westlake University](https://shiyuzhao.westlake.edu.cn/3.pdf)
- [SwarmPath: APF + Impedance Control (2024)](https://arxiv.org/html/2410.07848v1)
- [Quantum-Enhanced APF for Drone Swarms (2025)](https://www.nature.com/articles/s41598-025-25863-y)
- [Vortex APF + RL for Local Minima (2025)](https://www.mdpi.com/2075-1702/13/7/600)
- [BVC Original Paper - Zhou et al. 2017 (Stanford)](https://msl.stanford.edu/papers/zhou_fast_2017.pdf)
- [B-UAVC: Uncertainty-Aware Voronoi Cells (2019)](https://autonomousrobots.nl/assets/files/publications/19-zhu-mrs.pdf)
- [Crazyswarm2 Documentation](https://imrclab.github.io/crazyswarm2/)
- [CBF Theory and Applications - Ames et al. 2019](https://coogan.ece.gatech.edu/papers/pdf/amesecc19.pdf)
- [CBF-QP for Safety Critical Systems - Ames 2017](https://arxiv.org/abs/1609.06408)
- [Multi-Robot CBF Collision Avoidance (Caltech)](http://ames.caltech.edu/chen2021guaranteed.pdf)
- [Safe Multi-Agent Drone Control using CBF (2023)](https://www.sciencedirect.com/science/article/abs/pii/S0921889023002403)
- [GCBF+ - MIT REALM (2024/2025)](https://arxiv.org/abs/2401.14554)
- [GCBF+ Project Page](https://mit-realm.github.io/gcbfplus/)
- [GCBF+ GitHub (JAX)](https://github.com/MIT-REALM/gcbfplus)
- [Sim-to-Real DRL Obstacle Avoidance (2024)](https://ieeexplore.ieee.org/document/10553074/)
- [Multi-UAV Formation with RL (2024)](https://arxiv.org/html/2410.18495v2)
- [Collision Avoidance in UAV Swarms: Learning-Centric Survey (2025)](https://www.sciencedirect.com/science/article/pii/S092523122502692X)
- [MARL for UAV Control Survey (2025)](https://www.mdpi.com/2504-446X/9/7/484)
- [EGO-Swarm - GitHub (ZJU FAST Lab)](https://github.com/ZJU-FAST-Lab/ego-planner-swarm)
- [Swarm of Micro Flying Robots in the Wild - Science Robotics 2022](https://www.science.org/doi/10.1126/scirobotics.abm5954)
- [Collision Avoidance Mechanism for Swarms of Drones (2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11858889/)
- [UAV Swarms: Research, Challenges, Future Directions (2025)](https://link.springer.com/article/10.1186/s44147-025-00582-3)
