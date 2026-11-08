"""Sensors the robot reports to the hub in every heartbeat.

ULTRASONIC  HC-SR04 distance sensor through gpiozero (see docs/datasheets/HCSR04 Datasheet.pdf).
            The sensor's ECHO pin outputs 5 V, so put a voltage divider (e.g. 1 kΩ + 2 kΩ)
            between ECHO and the Pi's GPIO, or you will damage the Pi.

            Wiring on our robots:
              VCC  -> Pi pin 2 (5V)
              Trig -> Pi pin 15 (GPIO22)
              Echo -> 1 kΩ -> Pi pin 18 (GPIO24), with 2 kΩ from that junction to GND
              GND  -> Pi pin 6 (GND)

GYRO        MPU-6050 (GY-521 board) on its own software I2C bus 4, so a fault on it can't stop
            the arm on bus 3. setup_robot.sh turns the bus on; it works after one reboot.
            Check the wiring with:  i2cdetect -y 4   (the gyro shows up as 68)

            Wiring on our robots (power the robot off before plugging anything in):
              VCC -> Pi pin 17 (3.3V)    never 5V: the Pi's pins only take 3.3V
              GND -> Pi pin 30 (GND)
              SDA -> Pi pin 35 (GPIO19)
              SCL -> Pi pin 37 (GPIO26)
              XDA, XCL, AD0, INT: not connected

            Mount it flat, chip side up, away from the motors. For each axis printed on the board
            it reports, in degrees:
              rot_x_deg, rot_y_deg  how far the robot is tipped forward/back and side to side
              rot_z_deg             how far it has turned on the spot; positive = left
                                    (anticlockwise seen from above)
            and how fast it is turning right now, in degrees per second (0 when still):
              gyro_x_dps, gyro_y_dps, gyro_z_dps
            All rotations start at 0 when the gyro calibrates: when the agent starts, and whenever
            the hub's "Calibrate gyro" button is pressed. The robot must stay still for those
            2 seconds. X and Y are kept honest by gravity, so they don't drift. Z can only add up
            turns, so it drifts slowly (a degree or so a minute): calibrate again to zero it.

Set a pin or bus to None to turn that sensor off; the agent still runs without it.
Add more sensors (battery) the same way:
set them up in setup(), list them in names(), and add their readings in read().
"""

import math
import threading
import time

# BCM / GPIO numbers, not physical pin positions. Don't use GPIO2/3 (damaged on our first Pi),
# GPIO5/6 (the arm's I2C bus 3), GPIO19/26 (the gyro's I2C bus 4)
# or any pin used by the wheels in robot_movement.py.
ULTRASONIC_TRIGGER = 22     # physical pin 15
ULTRASONIC_ECHO = 24        # physical pin 18, through the voltage divider
ULTRASONIC_MAX_M = 2.0      # readings beyond this are reported as this distance
ULTRASONIC_EVERY = 0.1      # seconds between readings
ULTRASONIC_STALE = 2.0      # report no reading if the sensor hasn't answered for this long

GYRO_I2C_BUS = 4            # /dev/i2c-4, software I2C on GPIO19/26 (setup_robot.sh)
GYRO_ADDRESS = 0x68         # with AD0 unconnected; 0x69 if AD0 is wired to VCC
GYRO_EVERY = 0.01           # seconds between readings; rotation adds these up, so keep it short
GYRO_CALIBRATE = 2.0        # seconds of standing still to measure the gyro's offset
GYRO_STALE = 1.0            # report no reading if the gyro hasn't answered for this long
GYRO_GRAVITY_PULL = 0.02    # how strongly gravity corrects X/Y each reading; higher = less drift
                            # but more wobble from bumps

try:
    from gpiozero import DistanceSensor
except ImportError:
    DistanceSensor = None

try:
    from smbus2 import SMBus
except ImportError:
    try:
        from smbus import SMBus      # python3-smbus, installed by setup_robot.sh
    except ImportError:
        SMBus = None

ultrasonic = None           # created by setup()
# Latest reading, filled by a background thread. gpiozero's distance waits until it has heard
# enough echoes, forever if none come back (bad Echo wiring), so it must never run in the agent's
# main loop: that would freeze the heartbeats and the status window.
_latest = {"cm": None, "at": 0.0, "warned": False}

# MPU-6050 registers (see its register map)
MPU_CONFIG = 0x1A
MPU_GYRO_CONFIG = 0x1B
MPU_ACCEL_CONFIG = 0x1C
MPU_ACCEL_XOUT_H = 0x3B     # accel X/Y/Z, temperature, gyro X/Y/Z follow: 2 bytes each, high first
MPU_PWR_MGMT_1 = 0x6B
MPU_WHO_AM_I = 0x75
GYRO_LSB_PER_DPS = 131.0    # raw units per degree/second at the ±250 °/s range

GYRO_AXES = ("x", "y", "z")

# Gyro state, filled by its background thread. dps is None while calibrating.
# calibrate is set by calibrate_gyro() (the hub's button) and cleared by the thread.
_gyro = {"bus": None, "dps": None, "rot": [0.0, 0.0, 0.0], "at": 0.0, "warned": False,
         "calibrate": False}


def _ultrasonic_loop():
    while True:
        try:
            cm = round(ultrasonic.distance * 100, 1)
        except Exception:
            cm = None
        _latest["cm"], _latest["at"] = cm, time.monotonic()
        time.sleep(ULTRASONIC_EVERY)


def _setup_ultrasonic():
    global ultrasonic
    if ULTRASONIC_TRIGGER is None or ULTRASONIC_ECHO is None:
        print("[robot] ultrasonic pins aren't filled in (see sensors.py); ultrasonic disabled", flush=True)
        return
    if DistanceSensor is None:
        print("[robot] gpiozero isn't installed; ultrasonic disabled", flush=True)
        return
    try:
        ultrasonic = DistanceSensor(echo=ULTRASONIC_ECHO, trigger=ULTRASONIC_TRIGGER,
                                    max_distance=ULTRASONIC_MAX_M)
    except Exception as err:
        ultrasonic = None
        print("[robot] couldn't set up the ultrasonic sensor ({}: {}); disabled".format(
            type(err).__name__, err), flush=True)
        return
    _latest["at"] = time.monotonic()      # give it a moment before calling it silent
    threading.Thread(target=_ultrasonic_loop, name="ultrasonic", daemon=True).start()
    print("[robot] ultrasonic ready (trigger GPIO{}, echo GPIO{})".format(
        ULTRASONIC_TRIGGER, ULTRASONIC_ECHO), flush=True)


def _gyro_wake(bus):
    bus.write_byte_data(GYRO_ADDRESS, MPU_PWR_MGMT_1, 0x01)    # wake up; clock from the gyro (steadier)
    bus.write_byte_data(GYRO_ADDRESS, MPU_CONFIG, 0x03)        # 44 Hz filter: smooths motor vibration
    bus.write_byte_data(GYRO_ADDRESS, MPU_GYRO_CONFIG, 0x00)   # ±250 °/s, the most sensitive range
    bus.write_byte_data(GYRO_ADDRESS, MPU_ACCEL_CONFIG, 0x00)  # ±2 g, the most sensitive range
    time.sleep(0.1)                                            # let it settle after waking


def _gyro_read(bus):
    """One reading: (accelerometer x/y/z in raw units, gyro x/y/z in degrees per second)."""
    data = bus.read_i2c_block_data(GYRO_ADDRESS, MPU_ACCEL_XOUT_H, 14)  # one read, so all match
    values = []
    for i in range(0, 14, 2):
        raw = (data[i] << 8) | data[i + 1]
        values.append(raw - 0x10000 if raw >= 0x8000 else raw)
    return values[0:3], [v / GYRO_LSB_PER_DPS for v in values[4:7]]


def _tilt(accel):
    """Which way gravity pulls, as X and Y rotation in degrees. Only the direction matters."""
    ax, ay, az = accel
    return [math.degrees(math.atan2(ay, az)), math.degrees(math.atan2(-ax, math.hypot(ay, az)))]


def _wrap(angle):
    """Keep an angle between -180 and 180."""
    return (angle + 180.0) % 360.0 - 180.0


def _gyro_calibrate(bus):
    """Measure the offsets while the robot stands still and start every rotation at 0.
    Returns (gyro offsets, the tilt to count as level)."""
    _gyro["dps"] = None                       # read() reports no reading meanwhile,
    _gyro["at"] = time.monotonic() + GYRO_CALIBRATE + 0.5   # without calling the gyro silent
    _gyro_wake(bus)
    accels, rates = [], []
    end = time.monotonic() + GYRO_CALIBRATE
    while time.monotonic() < end:
        accel, dps = _gyro_read(bus)
        accels.append(accel)
        rates.append(dps)
        time.sleep(GYRO_EVERY)
    # A still gyro reads a little above or below zero on each axis; subtract that, or the
    # rotation would run away. The tilt now counts as level, so the floor needn't be flat.
    offset = [sum(axis) / len(rates) for axis in zip(*rates)]
    level = _tilt([sum(axis) / len(accels) for axis in zip(*accels)])
    _gyro["rot"] = [0.0, 0.0, 0.0]
    print("[robot] gyro calibrated: rotation is 0, 0, 0 (offset x {:.2f}, y {:.2f}, z {:.2f} deg/s)".format(
        *offset), flush=True)
    return offset, level


def _gyro_loop():
    bus = _gyro["bus"]
    offset = level = None
    last = time.monotonic()
    while True:
        try:
            if offset is None or _gyro["calibrate"]:
                _gyro["calibrate"] = False
                offset, level = _gyro_calibrate(bus)
                last = time.monotonic()
            accel, raw_dps = _gyro_read(bus)
            now = time.monotonic()
            dt = min(now - last, 0.1)         # after a hiccup, don't add one huge step
            last = now
            dps = [v - o for v, o in zip(raw_dps, offset)]
            tilt = _tilt(accel)
            rot = _gyro["rot"]
            for i in range(3):
                rot[i] += dps[i] * dt                       # add up the turning
            for i in range(2):
                # Gravity says how far X and Y are really tipped; nudge toward it so they can't drift.
                rot[i] += GYRO_GRAVITY_PULL * _wrap(tilt[i] - level[i] - rot[i])
            _gyro["rot"] = [_wrap(r) for r in rot]
            _gyro["dps"], _gyro["at"] = dps, now
        except Exception:
            # A loose wire or a power dip. If it lost power it went back to sleep, so wake it and
            # calibrate again once it answers. read() reports no reading meanwhile.
            offset = None
            time.sleep(1.0)
            continue
        time.sleep(GYRO_EVERY)


def _setup_gyro():
    if GYRO_I2C_BUS is None:
        print("[robot] gyro is turned off in sensors.py", flush=True)
        return
    if SMBus is None:
        print("[robot] python3-smbus isn't installed; gyro disabled", flush=True)
        return
    try:
        bus = SMBus(GYRO_I2C_BUS)
    except Exception:
        print("[robot] I2C bus {} isn't turned on yet; gyro disabled. In the hub, press Update and tick "
              "'Reboot the robot when done'.".format(GYRO_I2C_BUS), flush=True)
        return
    try:
        who = bus.read_byte_data(GYRO_ADDRESS, MPU_WHO_AM_I)
    except Exception:
        bus.close()
        print("[robot] no gyro answered at 0x{:02x} on I2C bus {}; gyro disabled. Check SDA (pin 35), "
              "SCL (pin 37), VCC (pin 17, 3.3V) and GND, then run: i2cdetect -y {}".format(
                  GYRO_ADDRESS, GYRO_I2C_BUS, GYRO_I2C_BUS), flush=True)
        return
    if who != 0x68:
        # Many cheap boards carry a compatible copy of the chip that answers differently
        # (ours says 0x72). It works the same.
        print("[robot] the gyro says it is 0x{:02x} rather than 0x68 (a compatible copy of the "
              "MPU-6050); using it".format(who), flush=True)
    _gyro["bus"] = bus
    _gyro["at"] = time.monotonic() + GYRO_CALIBRATE     # not silent while it calibrates
    threading.Thread(target=_gyro_loop, name="gyro", daemon=True).start()
    print("[robot] gyro found on I2C bus {}; keep the robot still for {:.0f} seconds while it "
          "calibrates".format(GYRO_I2C_BUS, GYRO_CALIBRATE), flush=True)


def calibrate_gyro():
    """Ask the gyro to measure its offsets again and start every rotation at 0 (the hub's
    "Calibrate gyro" button). Takes GYRO_CALIBRATE seconds; the robot must stay still.
    Returns False if there's no gyro."""
    if _gyro["bus"] is None:
        return False
    _gyro["calibrate"] = True
    return True


def setup():
    """Set up every sensor that is configured. Missing ones stay disabled."""
    _setup_ultrasonic()
    _setup_gyro()


def names():
    """The readings this robot can send, for the hub."""
    out = []
    if ultrasonic is not None:
        out.append("distance_cm")
    if _gyro["bus"] is not None:
        out += ["rot_{}_deg".format(a) for a in GYRO_AXES]
        out += ["gyro_{}_dps".format(a) for a in GYRO_AXES]
    return out


def read():
    """Current readings, e.g. {"distance_cm": 42.1}. A sensor that fails a read reports None.
    Never waits on hardware: it returns the latest values the background threads collected."""
    out = {}
    now = time.monotonic()
    if ultrasonic is not None:
        if now - _latest["at"] > ULTRASONIC_STALE:
            out["distance_cm"] = None
            if not _latest["warned"]:
                _latest["warned"] = True
                print("[robot] ultrasonic isn't answering (no echo); check the Echo wire and the "
                      "voltage divider", flush=True)
        else:
            out["distance_cm"] = _latest["cm"]
            _latest["warned"] = False
    if _gyro["bus"] is not None:
        stale = now - _gyro["at"] > GYRO_STALE
        if stale and not _gyro["warned"]:
            _gyro["warned"] = True
            print("[robot] the gyro stopped answering; check its 4 wires (pins 17, 30, 35, 37)",
                  flush=True)
        dps = None if stale else _gyro["dps"]                 # None while calibrating, too
        rot = _gyro["rot"]
        for i, axis in enumerate(GYRO_AXES):
            # "+ 0.0" turns -0.0 into 0.0, which reads better
            out["rot_{}_deg".format(axis)] = None if dps is None else round(rot[i], 1) + 0.0
            out["gyro_{}_dps".format(axis)] = None if dps is None else round(dps[i], 1) + 0.0
        if not stale:
            _gyro["warned"] = False
    return out
