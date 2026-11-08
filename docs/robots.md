# Robots

Every robot we have or are building, and the checklist that makes a robot "hardware-finished".
Update this file whenever a robot changes (new wiring, a fault, a part swapped). **No passwords here.**

The software is built for 4 robots from the start (with simulated robots standing in), while robot 1 is
finished on the hardware side. Robots 2-4 follow the same checklist once robot 1 passes it.

## Hardware terms, explained

| Term | What it is |
|---|---|
| Mecanum wheels | Wheels with angled rollers, so the robot can also slide sideways and turn on the spot |
| L298N | A motor driver board: the Pi's weak signals switch the motors' big current. Two channels per board, so two boards for four wheels |
| PWM | Switching a pin on and off very fast; the on-time sets the motor speed (the L298N's ENA/ENB pins) |
| GPIO | The Pi's general-purpose pins. "BCM 14" means GPIO number 14, not physical pin 14 |
| I2C | A two-wire bus (SDA data, SCL clock) for talking to small boards; each board has an address, e.g. `0x40` |
| PCA9685 | A 16-channel servo controller board on I2C; it sends the pulses that position each arm servo |
| Servo pulse (µs) | A servo's position is set by a pulse length in microseconds: about 500 = one end, 1500 = middle, 2500 = other end |
| End stop | The physical limit of a joint; driving a servo past it makes it buzz and strain (and can break it) |
| HC-SR04 | Ultrasonic distance sensor: sends a sound ping (Trig) and times the echo (Echo) |
| Voltage divider | Two resistors that drop the HC-SR04's 5 V echo to the 3.3 V a Pi pin can take |
| Brown-out | The Pi's voltage dips (usually when motors start) and it resets or misbehaves; fixed with a separate power supply |
| `i2cdetect -y 3` | A command that lists boards found on I2C bus 3; the arm board shows as `40` |

## Fleet

| # | Hub name | Linux user @ host | Pi hostname | Pi model | Token | Hardware state |
|---|---|---|---|---|---|---|
| 1 | **Clanker** | `acmpi1@10.20.63.28` | ACMpi1 | _fill in_ | shared (press Update for its own) | in progress, see below |
| 2 | _not built_ | | | | | not started |
| 3 | _not built_ | | | | | not started |
| 4 | _not built_ | | | | | not started |

Addresses change when we move to the lab router (ARCHITECTURE.md, Phase S4): give every robot a reserved
address there and update this table.

## Hardware-finished checklist

A robot is finished when every line is ✅. Tick in the robot's column. "How to check" uses the hub.

| # | Item | How to check | Clanker | R2 | R3 | R4 |
|---|---|---|---|---|---|---|
| 1 | Agent installed, starts on boot, connects | Add robot (tick Reboot once); status shows *connected* after a reboot | ✅ | | | |
| 2 | Own token | Update the robot once after `rotate` | ⬜ | | | |
| 3 | Wheels: all 4 turn | Drive panel; W, S, A, D, Q, E | _check_ | | | |
| 4 | Wheels: right directions | W goes forward, D slides right, E turns clockwise; else flip `INVERT_*` in `robot_movement.py` | _check_ | | | |
| 5 | Wheels: stop on their own | Hold W, close the laptop lid or pull Wi-Fi: wheels stop within 0.5 s | _check_ | | | |
| 6 | Arm: board found | Robot reports an arm (Arm button enabled); `i2cdetect -y 3` shows `40` | _check_ | | | |
| 7 | Arm: channels mapped | Each slider moves the joint it names | ✅ | | | |
| 8 | Arm: safe limits | Each joint's lowest/highest pulse found by hand (no buzzing at the ends), written in `ARM_JOINTS` and in the table below | ⬜ | | | |
| 9 | Ultrasonic | Sensors panel follows your hand; reads about right against a ruler | _check_ | | | |
| 10 | Camera | Camera panel shows a live picture | _check_ | | | |
| 11 | Gyro (heading) | Not wired yet; add to `sensors.py`, shows in Sensors | ⬜ | | | |
| 12 | Battery level | Not wired yet; add to `sensors.py`, shows in Sensors | ⬜ | | | |
| 13 | Power | Servos on their own supply (PCA9685 V+), grounds joined; 10 min driving without a Pi brown-out | _check_ | | | |
| 14 | Status screen | Opens on the robot's desktop after boot (if it has one) | _check_ | | | |

`_check_` means probably done, but nobody has written down that it was tested. Test it and tick it.

## Robot 1: Clanker

### Known faults
- **GPIO2/3 (the Pi's normal I2C bus 1) are damaged.** The arm uses software I2C bus 3 on GPIO5/6 instead
  (`setup_robot.sh` turns it on). Don't use GPIO2/3/5/6 for anything else on this Pi.

### Wiring (BCM GPIO numbers; source of truth is `robot/robot_movement.py` and `robot/sensors.py`)

| Part | Signal | GPIO | Notes |
|---|---|---|---|
| Front L298N, ch A (front-left) | IN1 / IN2 / ENA | 14 / 15 / 9 | ENA jumper removed (PWM) |
| Front L298N, ch B (front-right) | IN3 / IN4 / ENB | 18 / 23 / 10 | |
| Rear L298N, ch A (rear-left) | IN1 / IN2 / ENA | 25 / 8 / 17 | |
| Rear L298N, ch B (rear-right) | IN3 / IN4 / ENB | 7 / 12 / 27 | |
| PCA9685 (arm) | SDA / SCL | 5 / 6 | I2C bus 3, address 0x40, 50 Hz |
| HC-SR04 | Trig / Echo | 22 / 24 | Echo through 1 kΩ, 2 kΩ to GND (5 V → 3.3 V) |
| USB camera | | | `/dev/video0`, 640×480, 15 fps |

Wiring diagram: `docs/datasheets/Master_Pi.fzz` (open with Fritzing).

### Arm joints

| Joint | PCA9685 channel | Safe lowest (µs) | Safe highest (µs) | Notes |
|---|---|---|---|---|
| gripper | 0 | _map_ | _map_ | |
| wrist | 1 | _map_ | _map_ | |
| elbow | 2 | _map_ | _map_ | |
| shoulder | 3 | _map_ | _map_ | |
| base | 4 | _map_ | _map_ | |

Today every joint allows the servo's full 500-2500 µs, which can drive a joint into its end stop. **This
conflicts with `CLAUDE.md`**, which says the limits are kept narrow until each joint is mapped. Map each joint
(move slowly with the Arm panel, note where it buzzes or hits something, back off 50 µs), then put the values
here and in `ARM_JOINTS`.

### Log
| Date | Change |
|---|---|
| 2026-11-08 | First entry: wiring and state taken from the code |

## Adding robot 2, 3, 4

1. Build and wire it like Clanker. If anything differs (other pins, a damaged GPIO), write it in its own
   section here **and** tell the team. Today the pins live in `robot_movement.py` and `sensors.py`, so they're
   the same for every robot.
2. Flash Raspberry Pi OS, enable SSH, join the same Wi-Fi as the hub, note its address.
3. In the hub: **Add robot** (tick Reboot the first time). It gets its own token and the next free name.
4. Run the checklist above in its column.
5. Add it to the Fleet table.
