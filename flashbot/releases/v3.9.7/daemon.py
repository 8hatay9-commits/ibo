import hashlib, json, os, sys, time, traceback, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
STATE=ROOT/"daemon_state.json"
URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/ce7215c79695c4ab732a8973bd9fe5201b019597/flashbot/releases/v3.9.5/daemon.py"
BLOB_SHA1="f2ec0dcf6205a54f0f8d14228190e62aaf6254f1"

def write_diag(obj):
    tmp=STATE.with_name(f"{STATE.name}.{os.getpid()}.v397.tmp")
    tmp.write_text(json.dumps(obj,indent=2),encoding="utf-8")
    tmp.replace(STATE)

is_worker="--worker" in sys.argv
if is_worker:
    write_diag({"ok":False,"version":"FLASHBOT-PRODUCTION-V3.9.7","mode":"DRY_RUN_ONLY","phase":"wrapper_worker_boot","last_error":None,"timestamp":time.time()})

try:
    raw=urllib.request.urlopen(URL,timeout=30).read()
    got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
    if got!=BLOB_SHA1:
        raise RuntimeError(f"pinned V3.9.5 daemon mismatch: {got}")
    src=raw.decode("utf-8")
    src=src.replace("FLASHBOT-PRODUCTION-V3.9.5","FLASHBOT-PRODUCTION-V3.9.7")
    src=src.replace("FLASHBOT-SUPERVISOR-V3.9.5","FLASHBOT-SUPERVISOR-V3.9.7")
    exec(compile(src,URL,"exec"),{"__name__":"__main__","__file__":str(Path(__file__).resolve())})
except BaseException as e:
    if is_worker:
        try:
            write_diag({"ok":False,"version":"FLASHBOT-PRODUCTION-V3.9.7","mode":"DRY_RUN_ONLY","phase":"wrapper_worker_error","last_error":f"{type(e).__name__}:{e}","traceback_tail":traceback.format_exc()[-3000:],"timestamp":time.time()})
        except Exception:
            pass
    raise
