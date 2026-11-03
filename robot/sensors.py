"""Sensors the robot reports to the hub in every heartbeat.

ULTRASONIC  HC-SR04 distance sensor through gpiozero (see docs/datasheets/HCSR04 Datasheet.pdf).
            The sensor's ECHO pin outputs 5 V, so put a voltage divider (e.g. 1 kΩ + 2 kΩ)
            between ECHO and the Pi's GPIO, or you will damage the Pi.

The pins below are None until someone wires the sensor and fills them in, so it starts
disabled and the agent runs without it. Add more sensors (gyro, battery) the same way:
set them up in setup(), list them in names(), and add their readings in read().
"""

# BCM / GPIO numbers, not physical pin positions. Don't use GPIO2/3 or GPIO5/6 (the arm's I2C buses)
# or any pin used by the wheels in robot_movement.py.
ULTRASONIC_TRIGGER = None
ULTRASONIC_ECHO = None
ULTRASONIC_MAX_M = 2.0      # readings beyond this are reported as this distance

try:
    from gpiozero import DistanceSensor
except ImportError:
    DistanceSensor = None

ultrasonic = None           # created by setup()


def setup():
    """Set up every sensor that is configured. Missing ones stay disabled."""
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
    print("[robot] ultrasonic ready", flush=True)


def names():
    """The readings this robot can send, for the hub."""
    return ["distance_cm"] if ultrasonic is not None else []


def read():
    """Current readings, e.g. {"distance_cm": 42.1}. A sensor that fails a read reports None."""
    out = {}
    if ultrasonic is not None:
        try:
            out["distance_cm"] = round(ultrasonic.distance * 100, 1)
        except Exception:
            out["distance_cm"] = None
    return out
