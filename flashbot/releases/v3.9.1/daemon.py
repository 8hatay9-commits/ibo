import hashlib, sys, urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/8hatay9-commits/ibo/ad31b08280dbea26ad68454a3d45c20fe3cdaf48/flashbot/releases/v3.9.0/daemon.py"
BASE_GIT_BLOB_SHA1 = "67289d1f38bd3e4db9580948b02319436d78fd19"

raw = urllib.request.urlopen(BASE_URL, timeout=30).read()
got = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
if got != BASE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.9.0 daemon mismatch: {got}")

src = raw.decode("utf-8")

old = '''def write_state(obj):
    tmp = SUP_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    tmp.replace(SUP_STATE)
'''
new = '''def write_state(obj):
    payload = json.dumps(obj, indent=2)
    tmp = SUP_STATE.with_name(f"{SUP_STATE.name}.{os.getpid()}.tmp")
    tmp.write_text(payload, encoding="utf-8")
    last = None
    for attempt in range(8):
        try:
            tmp.replace(SUP_STATE)
            return
        except PermissionError as e:
            last = e
            time.sleep(min(0.25, 0.01 * (2 ** attempt)))
    raise last
'''
if old not in src:
    raise RuntimeError("V3.9.1 supervisor state-write marker not found")
src = src.replace(old, new, 1)

old = '''    return src

def run_worker():
'''
new = '''    old_state = 'STOP=v["STOP"]; ACTIVE=v["ACTIVE"]; save=v["save"]'
    new_state = ''' + "'''" + '''STOP=v["STOP"]; ACTIVE=v["ACTIVE"]; save=v["save"]
_state_write_lock_v391=threading.RLock()
def _save_v391(obj):
    state=core["STATE"]
    payload=json.dumps(obj,indent=2)
    with _state_write_lock_v391:
        tmp=state.with_name(f"{state.name}.{threading.get_ident()}.tmp")
        tmp.write_text(payload,encoding="utf-8")
        last=None
        for attempt in range(8):
            try:
                tmp.replace(state)
                return
            except PermissionError as e:
                last=e
                time.sleep(min(0.25,0.01*(2**attempt)))
        raise last
save=_save_v391
core["save"]=_save_v391
''' + "'''" + '''
    if old_state not in src:
        raise RuntimeError("V3.9.1 daemon state-write marker not found")
    src = src.replace(old_state, new_state, 1)
    return src

def run_worker():
'''
if old not in src:
    raise RuntimeError("V3.9.1 patch-core return marker not found")
src = src.replace(old, new, 1)

src = src.replace('src = src.replace("FLASHBOT-PRODUCTION-V3.7.0","FLASHBOT-PRODUCTION-V3.8.4",1)',
                  'src = src.replace("FLASHBOT-PRODUCTION-V3.7.0","FLASHBOT-PRODUCTION-V3.9.1",1)', 1)
src = src.replace("FLASHBOT-SUPERVISOR-V3.8.4", "FLASHBOT-SUPERVISOR-V3.9.1")

exec(compile(src, BASE_URL, "exec"), {"__name__": "__main__", "__file__": str(Path(__file__).resolve())})
