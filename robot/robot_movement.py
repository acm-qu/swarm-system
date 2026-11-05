"""Robot movement: the four mecanum wheels and the arm.

robot_agent.py calls into this file and nothing else touches the hardware, so
all pin numbers, servo channels and limits live here. The hub copies this file
onto the robot together with robot_agent.py (Add robot / Update).

WHEELS  four mecanum wheels on two L298N drivers, through gpiozero (comes with
        Raspberry Pi OS; on a Pi 5 it uses python3-lgpio).

ARM     servos on a PCA9685 servo controller over I2C bus 3: software I2C on
        GPIO5 (SDA, header pin 29) and GPIO6 (SCL, pin 31). We use it because
        GPIO2/3 (the Pi's normal bus 1) are damaged on our first Pi. Needs this
        line under [all] in /boot/firmware/config.txt, then a reboot:
          dtoverlay=i2c-gpio,i2c_gpio_sda=5,i2c_gpio_scl=6,bus=3
        and: sudo apt install python3-smbus   (or: pip install smbus2)
        The arm is optional: if I2C or the board isn't there, the arm is
        disabled and the wheels still work (and the other way round).

The servos get their power from their own supply on the PCA9685's V+ terminal,
never from the Pi, and that supply's GND must be joined to the Pi's GND.
"""

import math
import threading
import time

# ---------------------------------------------------------------------------
# WHEELS: four mecanum wheels on two L298N drivers
# ---------------------------------------------------------------------------
#   Driver 1 -> FRONT wheels: channel A = front-left,  channel B = front-right
#   Driver 2 -> REAR wheels:  channel A = rear-left,   channel B = rear-right
#
# PIN SETUP (BCM / GPIO numbers, not physical pin positions). Each channel has:
#   IN_x1 / IN_x2 = the two direction pins (L298N IN1/IN2 for A, IN3/IN4 for B)
#   EN_x          = the enable pin (L298N ENA / ENB), used for PWM speed control
# Remember to remove the ENA/ENB jumpers on the L298N boards.
# GPIO5/6 are the arm's I2C bus and GPIO2/3 are damaged on our first Pi; don't use them here.

# Driver 1 - FRONT wheels
FRONT_IN_A1 = 14
FRONT_IN_A2 = 15
FRONT_EN_A = 9
FRONT_IN_B1 = 18
FRONT_IN_B2 = 23
FRONT_EN_B = 10

# Driver 2 - REAR wheels
REAR_IN_A1 = 25
REAR_IN_A2 = 8
REAR_EN_A = 17
REAR_IN_B1 = 7
REAR_IN_B2 = 12
REAR_EN_B = 27

# If a wheel spins the wrong way, flip its value here.
# Motors on opposite sides are mirrored, so one side usually needs flipping.
INVERT_FRONT_LEFT = False
INVERT_FRONT_RIGHT = False
INVERT_REAR_LEFT = False
INVERT_REAR_RIGHT = False

try:
    from gpiozero import Motor
except ImportError:
    Motor = None

fl = fr = rl = rr = None    # the four Motor objects; created by setup_wheels()


def make_motor(in1, in2, enable):
    # pwm=True lets us set speeds between 0 and 1 using the enable pin.
    return Motor(forward=in1, backward=in2, enable=enable, pwm=True)


def setup_wheels():
    """Create the four motors. If anything is missing, leave them disabled (the agent still runs)."""
    global fl, fr, rl, rr
    pins = (FRONT_IN_A1, FRONT_IN_A2, FRONT_EN_A, FRONT_IN_B1, FRONT_IN_B2, FRONT_EN_B,
            REAR_IN_A1, REAR_IN_A2, REAR_EN_A, REAR_IN_B1, REAR_IN_B2, REAR_EN_B)
    if any(p is None for p in pins):
        print("[robot] motor pins aren't filled in (see the WHEELS section of robot_movement.py); "
              "motors disabled", flush=True)
        return
    if Motor is None:
        print("[robot] gpiozero isn't installed (sudo apt install python3-gpiozero python3-lgpio); "
              "motors disabled", flush=True)
        return
    try:
        fl = make_motor(FRONT_IN_A1, FRONT_IN_A2, FRONT_EN_A)   # front-left
        fr = make_motor(FRONT_IN_B1, FRONT_IN_B2, FRONT_EN_B)   # front-right
        rl = make_motor(REAR_IN_A1, REAR_IN_A2, REAR_EN_A)      # rear-left
        rr = make_motor(REAR_IN_B1, REAR_IN_B2, REAR_EN_B)      # rear-right
    except Exception as err:
        fl = fr = rl = rr = None
        print("[robot] couldn't set up the motors ({}: {}); motors disabled".format(
            type(err).__name__, err), flush=True)
        return
    print("[robot] motors ready", flush=True)


def set_wheel(motor, speed, invert):
    """Set one wheel. speed goes from -1 (full reverse) to 1 (full forward)."""
    if invert:
        speed = -speed
    motor.value = max(-1.0, min(1.0, speed))


def drive(forward=0.0, strafe=0.0, rotate=0.0):
    """
    Mix the three mecanum movements into the four wheel speeds.
      forward: +1 = forward,        -1 = backward
      strafe:  +1 = slide right,    -1 = slide left
      rotate:  +1 = turn clockwise, -1 = turn counter-clockwise
    Values can be combined (e.g. forward + strafe = diagonal movement).
    """
    if fl is None:
        return                                  # motors disabled
    front_left = forward + strafe + rotate
    front_right = forward - strafe - rotate
    rear_left = forward - strafe + rotate
    rear_right = forward + strafe - rotate

    # If any wheel goes above 1, scale everything down so the direction stays correct.
    biggest = max(abs(front_left), abs(front_right), abs(rear_left), abs(rear_right), 1.0)

    set_wheel(fl, front_left / biggest, INVERT_FRONT_LEFT)
    set_wheel(fr, front_right / biggest, INVERT_FRONT_RIGHT)
    set_wheel(rl, rear_left / biggest, INVERT_REAR_LEFT)
    set_wheel(rr, rear_right / biggest, INVERT_REAR_RIGHT)


def stop_wheels(reason):
    """Stop all four wheels (the arm is left alone)."""
    print("[robot] STOP wheels ({})".format(reason), flush=True)
    for m in (fl, fr, rl, rr):
        if m is not None:
            try:
                m.stop()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# ARM: servos on a PCA9685 over I2C bus 3 (GPIO5/6)
# ---------------------------------------------------------------------------

ARM_I2C_BUS = 3             # /dev/i2c-3, software I2C on GPIO5/6; see the top of this file
PCA9685_ADDRESS = 0x40      # the board's default; check with:  i2cdetect -y 3
SERVO_FREQUENCY = 50        # Hz; standard servos expect a pulse every 20 ms

# One entry per joint:  name: (PCA9685 channel, lowest pulse, highest pulse)  in microseconds.
#
# Channels were mapped on the real arm with the hub's Arm panel. The limits are the servos'
# full 500-2500 us range, so a joint can still be driven into its end stop: if a servo
# buzzes or strains at either end, back off and narrow that joint's limits here.
ARM_JOINTS = {
    "gripper":  (0, 500, 2500),
    "wrist":    (1, 500, 2500),
    "elbow":    (2, 500, 2500),
    "shoulder": (3, 500, 2500),
    "base":     (4, 500, 2500),
}

ARM_MAX_SPEED = 600         # fastest a joint may move, in microseconds of pulse per second
                            # (about 55 degrees per second on a 500-2500 us / 180 degree servo)
ARM_UPDATE_EVERY = 0.02     # seconds between small steps toward the target


class PCA9685:
    """The few things we need from a PCA9685: set the frequency, set a pulse width, switch a channel off."""

    MODE1 = 0x00
    PRESCALE = 0xFE
    LED0_ON_L = 0x06        # each channel has 4 registers: ON low/high, OFF low/high
    CLOCK = 25_000_000      # the chip's internal oscillator, Hz

    def __init__(self, bus_number, address, frequency):
        try:
            from smbus2 import SMBus
        except ImportError:
            from smbus import SMBus      # raises ImportError if neither is installed
        self.bus = SMBus(bus_number)
        self.address = address
        self.period_us = 1_000_000.0 / frequency
        prescale = int(round(self.CLOCK / (4096.0 * frequency))) - 1
        try:
            self.bus.write_byte_data(address, self.MODE1, 0x10)   # sleep, so the frequency can change
            self.bus.write_byte_data(address, self.PRESCALE, prescale)
            self.bus.write_byte_data(address, self.MODE1, 0x00)   # wake
            time.sleep(0.005)
            self.bus.write_byte_data(address, self.MODE1, 0xA0)   # restart + auto-increment registers
        except OSError:
            self.bus.close()             # no board on this bus; don't leave it open while we try the next
            raise
        # Channel values are left alone here, so a servo that was already holding keeps holding.

    def set_pulse(self, channel, microseconds):
        ticks = int(round(microseconds / self.period_us * 4096.0))
        ticks = max(0, min(4095, ticks))
        self.bus.write_i2c_block_data(self.address, self.LED0_ON_L + 4 * channel,
                                      [0, 0, ticks & 0xFF, ticks >> 8])

    def off(self, channel):
        """Stop sending pulses on a channel; the servo goes limp."""
        self.bus.write_i2c_block_data(self.address, self.LED0_ON_L + 4 * channel, [0, 0, 0, 0x10])


arm_pwm = None                    # the PCA9685; created by setup_arm()
arm_lock = threading.Lock()
arm_now = {}                      # joint -> pulse (us) we last sent it
arm_goal = {}                     # joint -> pulse (us) it is moving toward
arm_thread = None
arm_error = ""                    # last I2C problem, printed once per change


def setup_arm():
    """Connect to the PCA9685. If I2C or the board isn't there, leave the arm disabled."""
    global arm_pwm, arm_thread
    try:
        arm_pwm = PCA9685(ARM_I2C_BUS, PCA9685_ADDRESS, SERVO_FREQUENCY)
    except ImportError:
        print("[robot] no smbus library, so the arm is disabled (sudo apt install python3-smbus)", flush=True)
        return
    except OSError as err:
        print("[robot] can't reach the PCA9685 at 0x{:02X} on I2C bus {} ({}); arm disabled. Check the "
              "board's power LED, the wiring and the dtoverlay line (see the top of robot_movement.py), "
              "then run i2cdetect -y {} and look for {:02x}".format(
                  PCA9685_ADDRESS, ARM_I2C_BUS, err, ARM_I2C_BUS, PCA9685_ADDRESS), flush=True)
        return
    arm_thread = threading.Thread(target=arm_loop, daemon=True)
    arm_thread.start()
    print("[robot] arm ready (PCA9685 at 0x{:02X} on I2C bus {}); servos stay limp until the first arm "
          "command".format(PCA9685_ADDRESS, ARM_I2C_BUS), flush=True)


def arm_write(joint, microseconds):
    """Send one pulse to a joint. Caller holds arm_lock."""
    global arm_error
    channel = ARM_JOINTS[joint][0]
    try:
        arm_pwm.set_pulse(channel, microseconds)
        arm_error = ""
    except OSError as err:
        if str(err) != arm_error:
            arm_error = str(err)
            print("[robot] arm I2C error: {}".format(err), flush=True)


def arm_loop():
    """Move every joint a small step toward its goal, so no joint can swing at full servo speed."""
    max_step = ARM_MAX_SPEED * ARM_UPDATE_EVERY
    while True:
        time.sleep(ARM_UPDATE_EVERY)
        with arm_lock:
            for joint, goal in arm_goal.items():
                current = arm_now.get(joint)
                if current is None or current == goal:
                    continue
                current += max(-max_step, min(max_step, goal - current))
                arm_now[joint] = current
                arm_write(joint, current)


def arm_move(targets):
    """Move joints toward pulse widths. targets looks like {"base": 1500, "gripper": 1200} (microseconds).

    Each value is limited to that joint's range in ARM_JOINTS. Unknown joint names are ignored.
    A joint's very first move jumps straight to the target, because its real position isn't known;
    after that it moves smoothly, at most ARM_MAX_SPEED."""
    if arm_pwm is None:
        return
    with arm_lock:
        for joint, value in targets.items():
            spec = ARM_JOINTS.get(joint)
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if spec is None or not math.isfinite(value):
                continue
            _, low, high = spec
            value = max(low, min(high, value))
            arm_goal[joint] = value
            if joint not in arm_now:
                arm_now[joint] = value
                arm_write(joint, value)


def arm_hold():
    """Stop every joint where it is now (keeps holding; it does not go limp)."""
    with arm_lock:
        for joint, current in arm_now.items():
            arm_goal[joint] = current


def arm_release():
    """Stop sending pulses to every joint so the arm goes limp. It will sag, so support it first."""
    if arm_pwm is None:
        return
    with arm_lock:
        for joint, (channel, _, _) in ARM_JOINTS.items():
            try:
                arm_pwm.off(channel)
            except OSError:
                pass
        arm_now.clear()
        arm_goal.clear()


# ---------------------------------------------------------------------------
# Everything together
# ---------------------------------------------------------------------------

def setup():
    """Set up the wheels and the arm. Either may stay disabled; the agent still runs."""
    setup_wheels()
    setup_arm()


def wheels_ready():
    """True if the four motors were set up."""
    return fl is not None


def arm_limits():
    """joint -> [lowest, highest] pulse (us) for the hub's Arm panel; empty if the arm is disabled."""
    if arm_pwm is None:
        return {}
    return {joint: [low, high] for joint, (_, low, high) in ARM_JOINTS.items()}


def stop_all(reason):
    """The emergency stop: wheels stop, and the arm holds where it is."""
    stop_wheels(reason)
    arm_hold()
