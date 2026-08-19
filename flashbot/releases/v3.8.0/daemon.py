import json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STOP = ROOT / "STOP_DAEMON"
STATE = ROOT / "supervisor_state.json"
WORKER = ROOT / "worker.py"

BACKOFF = [1, 2, 5, 15, 30, 60, 120]
STABLE_RESET_SECONDS = 300
CRASH_LOOP_WINDOW_SECONDS = 600
CRASH_LOOP_LIMIT = 8
CRASH_LOOP_COOLDOWN_SECONDS = 300

def write_state(obj):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    tmp.replace(STATE)

def stop_child(p):
    if p.poll() is not None:
        return
    try:
        p.wait(timeout=8)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        p.terminate()
        p.wait(timeout=5)
        return
    except Exception:
        pass
    try:
        p.kill()
    except Exception:
        pass

def main():
    restart_count = 0
    crash_times = []
    last_exit = None
    last_runtime = None

    try:
        STOP.unlink()
    except FileNotFoundError:
        pass

    while True:
        if STOP.exists():
            write_state({
                "ok": True,
                "version": "FLASHBOT-SUPERVISOR-V3.8.0",
                "status": "stopped",
                "restart_count": restart_count,
                "last_exit_code": last_exit,
                "last_runtime_seconds": last_runtime,
                "timestamp": time.time(),
            })
            return 0

        started = time.time()
        cmd = [sys.executable, str(WORKER)] + sys.argv[1:]
        p = subprocess.Popen(cmd, cwd=str(ROOT))
        write_state({
            "ok": True,
            "version": "FLASHBOT-SUPERVISOR-V3.8.0",
            "status": "running",
            "supervisor_pid": os.getpid(),
            "child_pid": p.pid,
            "restart_count": restart_count,
            "last_exit_code": last_exit,
            "timestamp": time.time(),
        })

        while p.poll() is None:
            if STOP.exists():
                stop_child(p)
                break
            time.sleep(0.5)

        rc = p.poll()
        if rc is None:
            stop_child(p)
            rc = p.poll()

        runtime = max(0.0, time.time() - started)
        last_exit = rc
        last_runtime = runtime

        if STOP.exists():
            write_state({
                "ok": True,
                "version": "FLASHBOT-SUPERVISOR-V3.8.0",
                "status": "stopped",
                "supervisor_pid": os.getpid(),
                "child_pid": None,
                "restart_count": restart_count,
                "last_exit_code": rc,
                "last_runtime_seconds": runtime,
                "timestamp": time.time(),
            })
            return 0

        now = time.time()
        crash_times = [t for t in crash_times if now - t <= CRASH_LOOP_WINDOW_SECONDS]
        crash_times.append(now)
        restart_count += 1

        if runtime >= STABLE_RESET_SECONDS:
            crash_times = []
            delay = BACKOFF[0]
        else:
            delay = BACKOFF[min(restart_count - 1, len(BACKOFF) - 1)]

        if len(crash_times) >= CRASH_LOOP_LIMIT:
            delay = max(delay, CRASH_LOOP_COOLDOWN_SECONDS)

        write_state({
            "ok": False,
            "version": "FLASHBOT-SUPERVISOR-V3.8.0",
            "status": "backoff",
            "supervisor_pid": os.getpid(),
            "child_pid": None,
            "restart_count": restart_count,
            "recent_crashes": len(crash_times),
            "last_exit_code": rc,
            "last_runtime_seconds": runtime,
            "restart_in_seconds": delay,
            "timestamp": time.time(),
        })

        end = time.time() + delay
        while time.time() < end:
            if STOP.exists():
                break
            time.sleep(0.5)

if __name__ == "__main__":
    raise SystemExit(main())
