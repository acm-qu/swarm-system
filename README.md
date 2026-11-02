# Swarm System idea:

A scout robot scans an object, a server plans how each MasterPi should  be positioned and controls the swarm to execute commands together.
The final vision
The perfect final project is a swarm of different robot types that take a job, work out who should do what, and do it together, using only what their own sensors tell them. What we build first is much simpler, and is described under Current scope below.

1. Relative localization. No homing and no stickers. Each robot works out where it is relative to the target object and to the other robots, using its own sensors.
2. Scanning together. All robots scan the object at the same time. The system combines their sensor data into one model, so the scan is faster and more accurate than any single robot's.
3. Many jobs. A job can be a predetermined recipe, or a custom one that an AI planner puts together for the situation.
4. Many robot types, chosen per job. The fleet mixes types, for example a robot with a carrying hand and another with a flat bed for carrying things. For each job the system checks which types are available, calls the ones it needs, and decides the best way to do the job with them.

# Current scope: 

This is the simpler version we are actually building first:

one scout, a server and a few identical robots, with homing and stickers as scaffolding. The final vision above replaces the scaffolding later.
The CE/CS department already owns several Hiwonder MasterPi robots: Raspberry Pi robots with a a 5-DOF arm with gripper, a camera on the arm and an ultrasonic sensor.

**The goal is to make them work as a swarm that carries objects one robot cannot lift alone.
The robots sense and move. A server (outside PC) does all the thinking and sends each robot its job.**

1. Start homed. Every robot starts in a known slot with a known heading, so we skip global localization at first.
2. Scout scans. One robot, ideally the one with the best camera, drives to the object, reads the stickers (tags) on it and reports its shape, size and position. Then it stops and waits.
3. Server plans. From the object's size and the number of robots available, the server picks the grip points that keep the lift most stable.
4. Helpers join. The other robots drive to their assigned points and align with the object using its tags.
5. Lift together. The server sends synchronized commands so every robot grips, lifts and moves at the same time.

# Project Phases:
The phases for the current scope of the project and how to achieve it, each phase will have some goals that have to be achieved before moving to the next phase.

## Phase 0 (Current Phase):
This phase aims to get a singular robot working and controllable through software 

- Optain one of the robots ✅
- control it manually
- make it able to identify its location (relative to some stickers) + gyro
- Control it's movement by defining target cords and angles

## Phase 1:
This phase aims to provide a simple interface/Hub to connect to and control all the robots from one place 
(control stays manual and per robot, but in the same interface), and to access sensor and camera data from each robot.

- Build a simple interface (a web page served from the PC)
- Connect to every robot from it, with a list showing each robot's connection status
- Control each robot manually and individually from the same page
- Add a Run/Stop button for each robot
- Show each robot's sensor data live (ultrasonic, gyro, battery)
- Show each robot's camera feed
- Keep it general: a robot reports its type and what it can do, so new robot types can be added to the hub later

## Phase 2:
This phase aims to get the scout robot to scan an object and report its shape and size to the server

for this phase we are using the stickers to just determine the size of the object, we will only use predetermined geometric shapes for this phase  

- The robot should be able to determine only the shape using the sensor and camera feeeds
- Read the stickers
- Determine the size of the object and its location using the stickers 
- Calibrate the robot's camera
- Send the scan result/data to the server

## Phase 3:
This phase aims to work out the best points to hold an object, given its size and the number of robots available

- Write the grip-point algorithm on a PC for simple predetermined shapes (box, cylinder, etc...)
- Score each set of points for stability and an even load on every robot
- Check the chosen points in a physics simulation
- Calculate target position for each robot

## Phase 4:
This phase aims to run several robots from one server, each doing its own job

- Put all robots and the server on one Wi-Fi network
- Send each robot its job from the server: go to its grip point (target coordinates and angle)
- Fine-align each robot against the object using its stickers
- Wait until every robot reports ready, and abort if one fails

## Phase 5:
This phase aims to have the robots lift and carry the object together

• Make every robot grip and confirm
• Send one synchronized lift command
• Move together in formation over a short distance
• Put the object down and release

## Phase 6:
Profit 🎉
