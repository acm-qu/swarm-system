"""Background jobs: installs, updates and removals run on a thread and report their steps to the app."""

import secrets
import threading
import time

jobs = {}    # id -> install / update / remove job, shown live in the app
jobs_lock = threading.Lock()


class DeployError(Exception):
    """A problem to show the user, in plain words."""


def step(job, text):
    for s in job["steps"]:
        if s["state"] == "run":
            s["state"] = "ok"
    job["steps"].append({"text": text, "state": "run"})


def info(job, text):
    job["steps"].append({"text": text, "state": "info"})


def start(action, robot, fn, **kwargs):
    """Run fn(job, **kwargs) in the background. Returns None if a job is already running for that robot."""
    job = {"id": secrets.token_hex(8), "action": action, "robot": robot, "state": "running",
           "steps": [], "message": "", "warning": None, "started": time.time()}
    with jobs_lock:
        if robot and any(j["robot"] == robot and j["state"] == "running" for j in jobs.values()):
            return None
        jobs[job["id"]] = job
        for old in sorted(jobs.values(), key=lambda j: j["started"])[:-30]:
            if old["state"] != "running":
                jobs.pop(old["id"], None)

    def runner():
        try:
            fn(job, **kwargs)
            final = "warning" if job["warning"] else "done"
            for s in job["steps"]:
                if s["state"] == "run":
                    s["state"] = "fail" if final == "warning" else "ok"
            job["message"] = job["warning"] or job["message"] or "Done."
            job["state"] = final
        except Exception as err:
            if not isinstance(err, DeployError):
                err = f"Unexpected error: {type(err).__name__}: {err}"
            for s in job["steps"]:
                if s["state"] == "run":
                    s["state"] = "fail"
            job["message"] = str(err)
            job["state"] = "failed"
        finally:
            kwargs.clear()          # drop the password

    threading.Thread(target=runner, daemon=True).start()
    return job


def busy_robots():
    """robot name -> what its running job is doing now."""
    with jobs_lock:
        busy = {}
        for j in jobs.values():
            if j["state"] == "running" and j["robot"]:
                current = [s["text"] for s in j["steps"] if s["state"] == "run"]
                busy[j["robot"]] = (current[-1] + "…") if current else "working…"
    return busy


def snapshot(job_id):
    """A copy of a job for the app, or None."""
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return None
        out = {k: job[k] for k in ("state", "robot", "message", "action")}
        out["steps"] = list(job["steps"])
        return out
