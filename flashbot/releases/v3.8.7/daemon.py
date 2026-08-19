import hashlib, json, os, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STOP = ROOT / "STOP_DAEMON"
SUP_STATE = ROOT / "supervisor_state.json"
SELF = Path(__file__).resolve()

CORE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/f9bfd5fc90e3989b4afc88ce2f39848febd08528/flashbot/releases/v3.7.0/daemon.py"
CORE_GIT_BLOB_SHA1="6c447acdb4dfd19bfae3ee7625000bfabc4a08e4"

BACKOFF = [1, 2, 5, 15, 30, 60, 120]
STABLE_RESET_SECONDS = 300
CRASH_LOOP_WINDOW_SECONDS = 600
CRASH_LOOP_LIMIT = 8
CRASH_LOOP_COOLDOWN_SECONDS = 300

def write_state(obj):
    tmp = SUP_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    tmp.replace(SUP_STATE)

def patch_core(src):
    src = src.replace("FLASHBOT-PRODUCTION-V3.7.0","FLASHBOT-PRODUCTION-V3.8.4",1)

    old = 'workq=queue.Queue(maxsize=256); stop_evt=threading.Event()'
    new = 'workq=queue.Queue(maxsize=1); stop_evt=threading.Event()'
    if old not in src:
        raise RuntimeError("V3.8.4 queue marker not found")
    src = src.replace(old,new,1)

    old = '''            merged=[]
            merged.extend(batch)
            for _ in range(7):
                try: merged.extend(workq.get_nowait())
                except queue.Empty: break
'''
    new = '''            merged=batch
            stale=0
            while True:
                try:
                    merged=workq.get_nowait()
                    stale+=1
                except queue.Empty:
                    break
            if stale:
                st["worker_coalesced_stale_batches_v384"]=int(st.get("worker_coalesced_stale_batches_v384",0))+stale
'''
    if old not in src:
        raise RuntimeError("V3.8.4 worker marker not found")
    src = src.replace(old,new,1)

    old = '''                if fresh:
                    try: workq.put_nowait(fresh)
                    except queue.Full:
                        st["feed_dropped_batches_v37"]=int(st.get("feed_dropped_batches_v37",0))+1
'''
    new = '''                if fresh:
                    try:
                        workq.put_nowait(fresh)
                    except queue.Full:
                        try:
                            workq.get_nowait()
                            st["feed_coalesced_batches_v384"]=int(st.get("feed_coalesced_batches_v384",0))+1
                        except queue.Empty:
                            pass
                        try:
                            workq.put_nowait(fresh)
                        except queue.Full:
                            st["feed_dropped_batches_v37"]=int(st.get("feed_dropped_batches_v37",0))+1
'''
    if old not in src:
        raise RuntimeError("V3.8.4 producer marker not found")
    src = src.replace(old,new,1)

    old = '"pancakeswap_v3_enabled":True,"cost_gate":"V37_CONSERVATIVE_L1_L2_ESTIMATE"})'
    new = '"pancakeswap_v3_enabled":True,"cost_gate":"V37_CONSERVATIVE_L1_L2_ESTIMATE","queue_policy_v384":"LATEST_STATE_COALESCE_CAP1"})'
    if old not in src:
        raise RuntimeError("V3.8.4 status marker not found")
    src = src.replace(old,new,1)
    old = 'qcfg["route_quote_ttl_seconds"]=30'
    new = 'qcfg["route_quote_ttl_seconds"]=2.0\ncfg["activity"]["pair_neighbor_limit"]=16\ncfg["activity"]["triangle_neighbor_limit"]=12\ncfg["activity"]["triangle_closer_limit"]=4\nqcfg["max_cycles_per_trigger"]=24'
    if old not in src:
        raise RuntimeError("V3.8.4 topology marker not found")
    src = src.replace(old,new,1)

    return src

def run_worker():
    raw=urllib.request.urlopen(CORE_URL,timeout=30).read()
    got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
    if got!=CORE_GIT_BLOB_SHA1:
        raise RuntimeError(f"pinned V3.7 daemon mismatch: {got}")
    src=patch_core(raw.decode("utf-8"))
    sys.argv=[str(SELF)]+sys.argv[2:]
    exec(compile(src,CORE_URL,"exec"),{"__name__":"__main__","__file__":str(SELF)})

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

def supervise():
    restart_count=0
    crash_times=[]
    last_exit=None
    last_runtime=None

    try:
        STOP.unlink()
    except FileNotFoundError:
        pass

    while True:
        if STOP.exists():
            write_state({
                "ok":True,"version":"FLASHBOT-SUPERVISOR-V3.8.4","status":"stopped",
                "supervisor_pid":os.getpid(),"child_pid":None,
                "restart_count":restart_count,"last_exit_code":last_exit,
                "last_runtime_seconds":last_runtime,"timestamp":time.time()
            })
            return 0

        started=time.time()
        cmd=[sys.executable,str(SELF),"--worker"]+sys.argv[1:]
        p=subprocess.Popen(cmd,cwd=str(ROOT))
        write_state({
            "ok":True,"version":"FLASHBOT-SUPERVISOR-V3.8.4","status":"running",
            "supervisor_pid":os.getpid(),"child_pid":p.pid,
            "restart_count":restart_count,"last_exit_code":last_exit,
            "timestamp":time.time()
        })

        while p.poll() is None:
            if STOP.exists():
                stop_child(p)
                break
            time.sleep(0.5)

        rc=p.poll()
        if rc is None:
            stop_child(p)
            rc=p.poll()
        runtime=max(0.0,time.time()-started)
        last_exit=rc
        last_runtime=runtime

        if STOP.exists():
            write_state({
                "ok":True,"version":"FLASHBOT-SUPERVISOR-V3.8.4","status":"stopped",
                "supervisor_pid":os.getpid(),"child_pid":None,
                "restart_count":restart_count,"last_exit_code":rc,
                "last_runtime_seconds":runtime,"timestamp":time.time()
            })
            return 0

        now=time.time()
        crash_times=[t for t in crash_times if now-t<=CRASH_LOOP_WINDOW_SECONDS]
        crash_times.append(now)
        restart_count+=1

        if runtime>=STABLE_RESET_SECONDS:
            crash_times=[]
            delay=BACKOFF[0]
        else:
            delay=BACKOFF[min(restart_count-1,len(BACKOFF)-1)]
        if len(crash_times)>=CRASH_LOOP_LIMIT:
            delay=max(delay,CRASH_LOOP_COOLDOWN_SECONDS)

        write_state({
            "ok":False,"version":"FLASHBOT-SUPERVISOR-V3.8.4","status":"backoff",
            "supervisor_pid":os.getpid(),"child_pid":None,
            "restart_count":restart_count,"recent_crashes":len(crash_times),
            "last_exit_code":rc,"last_runtime_seconds":runtime,
            "restart_in_seconds":delay,"timestamp":time.time()
        })

        end=time.time()+delay
        while time.time()<end:
            if STOP.exists():
                break
            time.sleep(0.5)

if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--worker":
        run_worker()
    else:
        raise SystemExit(supervise())
