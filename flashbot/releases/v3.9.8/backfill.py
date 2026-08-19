import hashlib, urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/8hatay9-commits/ibo/89e7062cfe5fbe1d904d9cac974c189432891188/flashbot/releases/v3.9.0/backfill.py"
BASE_GIT_BLOB_SHA1 = "c5366562bfc93f9b47a1935c09aeb1d921754fee"

raw = urllib.request.urlopen(BASE_URL, timeout=30).read()
got = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
if got != BASE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.9.0 backfill mismatch: {got}")
src = raw.decode("utf-8")

old = 'lock=threading.RLock()\ntargets=[]\nuniverse=[]'
new = '''lock=threading.RLock()
io_lock=threading.Lock()
targets=[]
universe=[]
STICKY=R/"liquidation_targets.json"
RETAIN_HF=1.25
TARGET_CAP=200
SEED_TARGETS=[
 "0x01a5bb36b5fce28903529b6f1e5ca0390ed60db4",
 "0x9f9ff4ffdf0b16dd096f649586e882d88a9bf1c0",
 "0x6a2cc7efa2c5d91c45411d956358928158262a19",
 "0xfeee2af72cd54577526a3e8a6508a9d8d0942fb8",
]'''
if old not in src:
    raise RuntimeError("V3.9.2 backfill target marker not found")
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
    raise RuntimeError("V3.9.2 backfill atomic marker not found")
src = src.replace(old, new, 1)

old = 'stats={"ok":True,"type":"AAVE_LIQUIDATION_WATCHER_V1","started_at":time.time(),"refresh_count":0,"poll_count":0,"liquidatable_seen":0,"last_error":None}'
new = 'stats={"ok":True,"type":"AAVE_LIQUIDATION_WATCHER_V2","started_at":time.time(),"refresh_count":0,"poll_count":0,"liquidatable_seen":0,"last_error":None,"state_write_policy":"V392_LOCK_UNIQUE_TMP_RETRY","target_policy":"V392_STICKY_PERSISTENT_NEAR_HF","retain_hf":RETAIN_HF,"target_cap":TARGET_CAP}'
if old not in src:
    raise RuntimeError("V3.9.2 backfill stats marker not found")
src = src.replace(old, new, 1)

old = ''' users=[u for u,_ in sorted(last.items(),key=lambda x:x[1],reverse=True)]
 rows=[]
 for i in range(0,len(users),50):
  if STOP.exists():break
  try:rows += batch_account(users[i:i+50])
  except Exception as x:stats["last_error"]=f"discover_accounts:{type(x).__name__}:{x}"
 rows.sort(key=lambda x:x["hf"])
 near=[x["user"] for x in rows if 0<x["hf"]<NEAR_HF][:40]
 with lock:
  universe[:] = users
  targets[:] = near
  stats["refresh_count"]+=1
  stats["last_discovery_at"]=time.time()
  stats["borrow_events"]=len(ev)
  stats["lowest_discovered"]=rows[:20]
  stats["last_error"]=None if rows else stats.get("last_error")
 snapshot()
'''
new = ''' users=[u for u,_ in sorted(last.items(),key=lambda x:x[1],reverse=True)]
 with lock:prev=list(targets)
 score_users=list(dict.fromkeys(users+prev+SEED_TARGETS))
 rows=[]
 for i in range(0,len(score_users),50):
  if STOP.exists():break
  try:rows += batch_account(score_users[i:i+50])
  except Exception as x:stats["last_error"]=f"discover_accounts:{type(x).__name__}:{x}"
 rows.sort(key=lambda x:x["hf"])
 row_by={x["user"].lower():x for x in rows}
 fresh=[x["user"].lower() for x in rows if 0<x["hf"]<NEAR_HF]
 retained=[]
 for u in list(dict.fromkeys(prev+SEED_TARGETS)):
  r=row_by.get(u.lower())
  if r and 0<r["hf"]<RETAIN_HF:retained.append(u.lower())
 ranked=list(dict.fromkeys(fresh+retained))
 ranked.sort(key=lambda u:row_by.get(u,{"hf":99})["hf"])
 chosen=ranked[:TARGET_CAP]
 with lock:
  universe[:] = score_users
  targets[:] = chosen
  stats["refresh_count"]+=1
  stats["last_discovery_at"]=time.time()
  stats["borrow_events"]=len(ev)
  stats["recent_borrower_count"]=len(users)
  stats["scored_user_count"]=len(score_users)
  stats["sticky_retained_count"]=len(retained)
  stats["target_count"]=len(chosen)
  stats["lowest_discovered"]=rows[:20]
  stats["last_error"]=None if rows else stats.get("last_error")
 atomic(STICKY,{"targets":chosen,"updated_at":time.time(),"retain_hf":RETAIN_HF,"policy":"V392_STICKY_PERSISTENT_NEAR_HF"})
 snapshot()
'''
if old not in src:
    raise RuntimeError("V3.9.2 backfill discover marker not found")
src = src.replace(old, new, 1)

old = '''try:STOP.unlink()
except FileNotFoundError:pass
th=threading.Thread(target=refresher,daemon=True,name="aave-liq-discovery");th.start()
'''
new = '''try:STOP.unlink()
except FileNotFoundError:pass
try:
 d=json.loads(STICKY.read_text()) if STICKY.exists() else {}
 prior=[str(u).lower() for u in d.get("targets",[]) if isinstance(u,str) and len(u)==42 and u.startswith("0x")]
except Exception:prior=[]
with lock:targets[:]=list(dict.fromkeys(prior+SEED_TARGETS))[:TARGET_CAP]
th=threading.Thread(target=refresher,daemon=True,name="aave-liq-discovery");th.start()
'''
if old not in src:
    raise RuntimeError("V3.9.2 backfill startup marker not found")
src = src.replace(old, new, 1)

exec(compile(src, BASE_URL, "exec"), {"__name__":"__main__", "__file__":str(Path(__file__).resolve())})
