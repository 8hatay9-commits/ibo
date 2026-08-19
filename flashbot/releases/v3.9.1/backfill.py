import hashlib, urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/8hatay9-commits/ibo/ad31b08280dbea26ad68454a3d45c20fe3cdaf48/flashbot/releases/v3.9.0/backfill.py"
BASE_GIT_BLOB_SHA1 = "c5366562bfc93f9b47a1935c09aeb1d921754fee"

raw = urllib.request.urlopen(BASE_URL, timeout=30).read()
got = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
if got != BASE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.9.0 backfill mismatch: {got}")
src = raw.decode("utf-8")

old = 'lock=threading.RLock()\ntargets=[]'
new = 'lock=threading.RLock()\nio_lock=threading.Lock()\ntargets=[]'
if old not in src:
    raise RuntimeError("V3.9.1 backfill lock marker not found")
src = src.replace(old, new, 1)

old = '''def atomic(path,obj):
 t=path.with_suffix(".tmp");t.write_text(json.dumps(obj,indent=2));t.replace(path)
'''
new = '''def atomic(path,obj):
 payload=json.dumps(obj,indent=2)
 with io_lock:
  t=path.with_name(f"{path.name}.{threading.get_ident()}.tmp")
  t.write_text(payload)
  last=None
  for attempt in range(8):
   try:t.replace(path);return
   except PermissionError as e:
    last=e;time.sleep(min(.25,.01*(2**attempt)))
  raise last
'''
if old not in src:
    raise RuntimeError("V3.9.1 backfill atomic marker not found")
src = src.replace(old, new, 1)

old = 'stats={"ok":True,"type":"AAVE_LIQUIDATION_WATCHER_V1","started_at":time.time(),"refresh_count":0,"poll_count":0,"liquidatable_seen":0,"last_error":None}'
new = 'stats={"ok":True,"type":"AAVE_LIQUIDATION_WATCHER_V1","started_at":time.time(),"refresh_count":0,"poll_count":0,"liquidatable_seen":0,"last_error":None,"state_write_policy":"V391_LOCK_UNIQUE_TMP_RETRY"}'
if old not in src:
    raise RuntimeError("V3.9.1 backfill stats marker not found")
src = src.replace(old, new, 1)

exec(compile(src, BASE_URL, "exec"), {"__name__":"__main__", "__file__":str(Path(__file__).resolve())})
