import json,time,threading
from pathlib import Path
from rpc import RpcClient

R=Path(__file__).resolve().parent
C=json.loads((R/"settings.json").read_text())
POOL=C["contracts"]["aave_pool"]
STOP=R/"STOP_BACKFILL"
PROG=R/"backfill_progress.json"
REP=R/"backfill_report.json"
BORROW_TOPIC="0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0"
USER_SEL="bf92857c"
WINDOW=12000
REFRESH=60.0
POLL=0.35
NEAR_HF=1.12
fast=RpcClient(C["flashblocks_http"],min_interval=.03)
std=RpcClient(C["http_rpc"],min_interval=.12)
lock=threading.RLock()
targets=[]
universe=[]
stats={"ok":True,"type":"AAVE_LIQUIDATION_WATCHER_V1","started_at":time.time(),"refresh_count":0,"poll_count":0,"liquidatable_seen":0,"last_error":None}

def wa(a):return "0"*24+a.lower().removeprefix("0x")
def words(x):
 h=(x or "0x").removeprefix("0x")
 return [int(h[i:i+64],16) for i in range(0,len(h),64)] if len(h)%64==0 else []
def atomic(path,obj):
 t=path.with_suffix(".tmp");t.write_text(json.dumps(obj,indent=2));t.replace(path)
def snapshot(extra=None):
 with lock:
  o=dict(stats);o["targets"]=list(targets);o["universe_size"]=len(universe);o["timestamp"]=time.time()
 if extra:o.update(extra)
 atomic(PROG,o);atomic(REP,o)
def batch_account(users):
 if not users:return []
 p={"blockStateCalls":[{"calls":[{"to":POOL,"data":"0x"+USER_SEL+wa(u)} for u in users],"stateOverrides":{}}],"traceTransfers":False,"validation":False}
 sim=fast.call("eth_simulateV1",[p,"pending"],timeout=15,max_attempts=3)
 calls=(sim or [{}])[0].get("calls") or []
 out=[]
 for u,c in zip(users,calls):
  if c.get("status")!="0x1":continue
  v=words(c.get("returnData") or "0x")
  if len(v)<6 or v[1]<=0:continue
  out.append({"user":u,"collateral_base_raw":str(v[0]),"debt_base_raw":str(v[1]),"available_base_raw":str(v[2]),"liq_threshold_bps":v[3],"ltv_bps":v[4],"hf_1e18":str(v[5]),"hf":v[5]/1e18})
 return out
def discover():
 latest=int(std.call("eth_blockNumber",[],timeout=8,max_attempts=3),16);start=max(0,latest-WINDOW+1)
 ev=[];b=start
 while b<=latest and not STOP.exists():
  e=min(latest,b+1999)
  try:ev += std.call("eth_getLogs",[{"address":POOL,"fromBlock":hex(b),"toBlock":hex(e),"topics":[BORROW_TOPIC]}],timeout=12,max_attempts=3) or []
  except Exception as x:stats["last_error"]=f"discover_logs:{type(x).__name__}:{x}"
  b=e+1
 last={}
 for g in ev:
  t=g.get("topics") or []
  if len(t)<3:continue
  h=t[2].removeprefix("0x")
  if len(h)!=64:continue
  u="0x"+h[-40:]
  try:bn=int(g.get("blockNumber","0x0"),16)
  except:bn=0
  if bn>=last.get(u,0):last[u]=bn
 users=[u for u,_ in sorted(last.items(),key=lambda x:x[1],reverse=True)]
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
def refresher():
 while not STOP.exists():
  try:discover()
  except Exception as x:
   with lock:stats["last_error"]=f"refresh:{type(x).__name__}:{x}"
   snapshot()
  end=time.time()+REFRESH
  while time.time()<end and not STOP.exists():time.sleep(.25)

try:STOP.unlink()
except FileNotFoundError:pass
th=threading.Thread(target=refresher,daemon=True,name="aave-liq-discovery");th.start()
while not STOP.exists() and not targets:time.sleep(.1)
while not STOP.exists():
 started=time.monotonic()
 with lock:us=list(targets)
 try:
  rows=batch_account(us)
  rows.sort(key=lambda x:x["hf"])
  liq=[x for x in rows if 0<x["hf"]<1.0]
  with lock:
   stats["poll_count"]+=1;stats["last_poll_at"]=time.time();stats["lowest_live"]=rows[:20];stats["liquidatable_now"]=liq;stats["last_error"]=None
   if liq:
    stats["liquidatable_seen"]+=len(liq);stats["last_liquidatable_at"]=time.time()
  snapshot()
 except Exception as x:
  with lock:stats["last_error"]=f"poll:{type(x).__name__}:{x}"
  snapshot()
 elapsed=time.monotonic()-started
 if elapsed<POLL:time.sleep(POLL-elapsed)
with lock:stats["stopped_at"]=time.time();stats["status"]="stopped"
snapshot()
