---
title: Glossary
type: reference
status: complete
created: 2026-03-26
updated: 2026-03-26
tags: [drone-swarm, glossary, reference]
---

# Glossary

Key terms and acronyms used across the Drone Swarm Orchestrator project.

---

## A

### ADSB
Automatic Dependent Surveillance-Broadcast. A surveillance technology where aircraft broadcast their GPS-derived position, enabling air traffic awareness. Relevant to drone operations for traffic deconfliction.

### ArduPilot
An open-source autopilot firmware suite supporting multi-copters, fixed-wing aircraft, rovers, and submarines. The primary flight controller firmware used by this project. See [[HARDWARE_SPEC]] and [[COMMS_PROTOCOL]].

### ATAK
Android Team Awareness Kit. A geospatial mapping and situational awareness application used by the US military and first responders. Integration planned for Phase 5 to enable joint drone-ground operations.

### AUW
All-Up Weight. The total weight of the drone including frame, electronics, battery, and payload. The F450 class has a max safe AUW of ~1200g.

---

## B

### BEC
Battery Eliminator Circuit. A voltage regulator on the ESC or PDB that steps down battery voltage to 5V for the flight controller and peripherals.

### BVLOS
Beyond Visual Line of Sight. Operating a drone where the pilot cannot see it directly. Currently requires FAA waiver; Part 108 is expected to address this.

---

## C

### C2
Command and Control. The communication link and authority structure between operators and drones. In this project, C2 flows from the ground station through the orchestrator to individual drones via MAVLink.

### CBOR
Concise Binary Object Representation. A compact binary data format considered for drone-to-drone state sharing in the mesh network (Phase 4).

### CoT
Cursor on Target. An XML-based messaging format used by ATAK and other military systems for sharing position and targeting data.

---

## D

### DDTC
Directorate of Defense Trade Controls. The US State Department office that administers ITAR export controls.

### DIU
Defense Innovation Unit. A DoD organization that connects commercial technology companies with military end-users. A target for go-to-market strategy.

### DroneCAN
A lightweight protocol for communication between drone components (flight controller, GPS, ESCs). Used for Remote ID broadcast when supported by the flight controller.

---

## E

### EAR
Export Administration Regulations. US Commerce Department regulations governing export of dual-use technology. Less restrictive than ITAR but still applicable to encryption features.

### EKF
Extended Kalman Filter. The sensor fusion algorithm in ArduPilot that combines GPS, accelerometer, gyroscope, barometer, and compass data to estimate the drone's position and orientation. EKF failures indicate sensor problems.

### ESC
Electronic Speed Controller. Controls motor speed based on commands from the flight controller. Each motor has a dedicated ESC.

---

## F

### F450
A common quadcopter frame size (~450mm diagonal). The recommended frame for Class A drones in this project. See [[HARDWARE_SPEC]].

### FMS
Foreign Military Sales. The US government program for selling defense articles to allied nations.

### FPV
First Person View. A camera system that streams video from the drone to the operator, providing a pilot's-eye perspective.

---

## G

### GCS
Ground Control Station. The operator's interface for monitoring and commanding drones. In this project, a laptop running the Python orchestrator and Next.js UI.

### GUIDED Mode
An ArduPilot flight mode where the drone follows GPS waypoints sent by the ground station. The primary mode used during swarm missions.

---

## H

### HITL
Hardware-In-The-Loop. A testing method where real flight controllers run against simulated physics, bridging the gap between pure software simulation (SITL) and outdoor flight.

---

## I

### IFF
Identification Friend or Foe. A system for distinguishing friendly drones from unknown or hostile ones. Phase 5 implements transponder-based IFF; Phase 6 adds computer vision-based identification.

### ITAR
International Traffic in Arms Regulations. US State Department regulations controlling the export of defense articles and services. Defense-specific features (IFF, encrypted comms, ATAK integration) are likely ITAR-controlled. ITAR counsel must be engaged before Phase 5. See [[BUSINESS_PLAN]].

---

## L

### LAANC
Low Altitude Authorization and Notification Capability. An FAA system for automated airspace authorization in controlled airspace near airports.

### LoRa
Long Range. A low-power, wide-area network protocol operating on sub-GHz ISM bands (915MHz in the US). Used with ESP32 modules for drone-to-drone mesh networking. Range: 1-5+ km line-of-sight. See [[COMMS_PROTOCOL]].

---

## M

### MAVLink
Micro Air Vehicle Link. The standard communication protocol between drones and ground stations. Version 2 is used in this project. Supports signed messages, system identification, and extensible message types. See [[COMMS_PROTOCOL]].

---

## N

### NetID
Network Identifier. A parameter on SiK radios that ensures paired radios communicate only with each other. Each drone-ground link uses a unique NetID.

---

## P

### PDB
Power Distribution Board. Distributes battery power to ESCs, flight controller, and peripherals. Mounted on the frame.

### PID
Proportional-Integral-Derivative. A control algorithm used by ArduPilot for stabilization, position hold, and navigation. PID parameters may need tuning after first flight with real hardware.

### PX4
An alternative open-source autopilot firmware to ArduPilot. Supported by the orchestrator but ArduPilot is the primary target.

---

## R

### RBAC
Role-Based Access Control. Access control model for multi-operator support in Phase 5, defining commander, operator, and observer roles.

### Remote ID
A regulatory requirement (effective March 2024 in the US) for drones to broadcast identification and location information. Compliance is mandatory and verified during preflight checks. See [[HARDWARE_SPEC#Remote ID Compliance]].

### RTL
Return to Launch. A failsafe flight mode where the drone autonomously returns to its takeoff location. Triggered by low battery, lost communications, or operator command. RTL altitude is staggered per drone to prevent collisions.

---

## S

### SBIR
Small Business Innovation Research. A US government program providing grants ($50K-$1.5M) to small businesses for R&D with commercial and defense applications.

### SiK
A firmware for telemetry radios commonly used with ArduPilot. Operates on 915MHz (US) or 433MHz (EU). Each radio pair provides a dedicated MAVLink link between a drone and the ground station. See [[COMMS_PROTOCOL]].

### SITL
Software In The Loop. ArduPilot's simulation environment that runs the full autopilot firmware on a desktop computer with simulated physics. Used for testing without physical hardware. See [[ARCHITECTURE#Simulation (SITL) Setup]].

### SYSID
System Identifier. A MAVLink parameter (SYSID_THISMAV) that gives each drone a unique ID on the network. The ground station conventionally uses SYSID 255.

---

## V

### VIBE
Vibration. ArduPilot logs vibration levels (VIBE.VibeX/Y/Z). Levels below 30 m/s/s are acceptable; above 60 m/s/s indicates a problem that must be resolved before flight.

### VTX
Video Transmitter. Broadcasts analog FPV video from the drone to a ground receiver. Used on Class B and higher drones.

---

## Related Documents

- [[HARDWARE_SPEC]] -- Component specifications and assembly
- [[COMMS_PROTOCOL]] -- Communication protocol details
- [[SYSTEM_ARCHITECTURE]] -- System design and module breakdown
- [[PRODUCT_SPEC]] -- Feature definitions and requirements
