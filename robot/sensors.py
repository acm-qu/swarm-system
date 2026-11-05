"""Sensors the robot reports to the hub in every heartbeat.

ULTRASONIC  HC-SR04 distance sensor through gpiozero (see docs/datasheets/HCSR04 Datasheet.pdf).
            The sensor's ECHO pin outputs 5 V, so put a voltage divider (e.g. 1 kΩ + 2 kΩ)
            between ECHO and the Pi's GPIO, or you will damage the Pi.

            Wiring on our robots:
              VCC  -> Pi pin 2 (5V)
              Trig -> Pi pin 15 (GPIO22)
              Echo -> 1 kΩ -> Pi pin 18 (GPIO24), with 2 kΩ from that junction to GND
              GND  -> Pi pin 6 (GND)

Set a pin to None to turn the sensor off; the agent still runs without it.
Add more sensors (gyro, battery) the same way:
set them up in setup(), list them in names(), and add their readings in read().
"""

# BCM / GPIO numbers, not physical pin positions. Don't use GPIO2/3 or GPIO5/6 (the arm's I2C buses)
# or any pin used by the wheels in robot_movement.py.
ULTRASONIC_TRIGGER = 22     # physical pin 15
ULTRASONIC_ECHO = 24        # physical pin 18, through the voltage divider
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
    print("[robot] ultrasonic ready (trigger GPIO{}, echo GPIO{})".format(
        ULTRASONIC_TRIGGER, ULTRASONIC_ECHO), flush=True)


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
