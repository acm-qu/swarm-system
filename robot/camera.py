"""USB camera, streamed to the hub as JPEG frames by robot_agent.py.

Needs OpenCV:  sudo apt install python3-opencv
The camera only runs while someone is watching it in the hub (the hub says so in
each heartbeat reply), so it costs nothing the rest of the time.
"""

import threading
import time

try:
    import cv2
except ImportError:
    cv2 = None

CAMERA_INDEX = 0          # /dev/video0. If it's the wrong one, try 2, 4, ... (see: v4l2-ctl --list-devices)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 15           # frames per second sent to the hub
JPEG_QUALITY = 70         # 1-100; lower = smaller frames
MAX_BUFFERED = 256 * 1024  # skip a frame if this much is still waiting to be sent (slow Wi-Fi)


class Camera:
    """Grabs frames on a background thread while `want` is True; keeps the latest JPEG."""

    def __init__(self):
        self.want = False
        self.frame = None
        self.frame_id = 0
        self.error = ""
        self.thread = None

    def available(self):
        """True if OpenCV is installed (whether a camera is plugged in shows up when it's opened)."""
        return cv2 is not None

    def set_wanted(self, want):
        self.want = bool(want)
        if self.want and (self.thread is None or not self.thread.is_alive()):
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def _run(self):
        if cv2 is None:
            self.error = "OpenCV isn't installed (sudo apt install python3-opencv)"
            return
        while self.want:
            cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
            if not cap.isOpened():
                self.error = "can't open camera {} (is it plugged in?)".format(CAMERA_INDEX)
                cap.release()
                time.sleep(2)
                continue
            # Most USB cameras give JPEG natively, which is far lighter than raw video.
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            last = 0.0
            bad = 0
            while self.want:
                ok, img = cap.read()
                if not ok:
                    bad += 1
                    if bad > 30:
                        self.error = "camera stopped giving frames"
                        break
                    time.sleep(0.05)
                    continue
                bad = 0
                now = time.monotonic()
                if now - last < 1.0 / CAMERA_FPS:
                    continue                      # too soon; drop it
                last = now
                ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if ok:
                    self.frame = jpg.tobytes()
                    self.frame_id += 1
                    self.error = ""
            cap.release()
            if self.want:
                time.sleep(2)
        self.frame = None


camera = Camera()
