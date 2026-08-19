import json, time
from pathlib import Path
from rpc import RpcClient

ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"settings.json").read_text(encoding="utf-8"))
rpc=RpcClient(cfg["flashblocks_http"],min_interval=0.05)
std=RpcClient(cfg["http_rpc"],min_interval=0.15)
PANCAKE_FACTORY="0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"
PANCAKE_QV2="0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997"
GPO="0x420000000000000000000000000000000000000F"
L1_UPPER="f1c7a58b"
def word_uint(x): return f"{int(x):064x}"
def u256(x):
    h=(x or "0x").removeprefix("0x")
    return int(h[:64],16) if len(h)>=64 else 0
report={"ok":False,"type":"V3_7_PROBE","version":"FLASHBOT-PRODUCTION-V3.7.0","pancake":{},
        "l1_fee_upper":{},"http_fast_poll":{},"simulate_v1":{},"timestamp":time.time()}

try:
    f=std.call("eth_getCode",[PANCAKE_FACTORY,"latest"],timeout=12,max_attempts=4)
    q=std.call("eth_getCode",[PANCAKE_QV2,"latest"],timeout=12,max_attempts=4)
    report["pancake"]={"ok":f not in ("0x","0x0") and q not in ("0x","0x0"),
                       "factory_code_bytes":max(0,(len(f)-2)//2),"quoter_code_bytes":max(0,(len(q)-2)//2)}
except Exception as e:
    report["pancake"]={"ok":False,"error":f"{type(e).__name__}: {e}"}

try:
    raw=rpc.call("eth_call",[{"to":GPO,"data":"0x"+L1_UPPER+word_uint(900)},"pending"],timeout=12,max_attempts=4)
    fee=u256(raw)
    report["l1_fee_upper"]={"ok":fee>0,"unsigned_tx_size":900,"fee_wei":fee}
except Exception as e:
    report["l1_fee_upper"]={"ok":False,"error":f"{type(e).__name__}: {e}"}

try:
    lats=[]; counts=[]; started=time.monotonic()
    topics=[[cfg["events"]["v3_swap"],cfg["events"]["aerodrome_v2_swap"]]]
    for _ in range(8):
        t=time.monotonic()
        logs=rpc.call("eth_getLogs",[{"fromBlock":"pending","toBlock":"pending","topics":topics}],timeout=10,max_attempts=3) or []
        lats.append(round((time.monotonic()-t)*1000,2)); counts.append(len(logs))
        time.sleep(0.22)
    report["http_fast_poll"]={"ok":True,"calls":8,"elapsed_s":round(time.monotonic()-started,3),
                              "latency_ms":lats,"counts":counts,"max_latency_ms":max(lats)}
except Exception as e:
    report["http_fast_poll"]={"ok":False,"error":f"{type(e).__name__}: {e}"}

try:
    payload={"blockStateCalls":[{"calls":[{"to":cfg["quote"]["anchor_token"],"data":"0x313ce567"}],"stateOverrides":{}}],
             "traceTransfers":False,"validation":False}
    sim=rpc.call("eth_simulateV1",[payload,"pending"],timeout=20,max_attempts=3)
    call=((sim or [{}])[0].get("calls") or [{}])[0]
    report["simulate_v1"]={"ok":call.get("status")=="0x1","status":call.get("status"),"gasUsed":call.get("gasUsed")}
except Exception as e:
    report["simulate_v1"]={"ok":False,"error":f"{type(e).__name__}: {e}"}

report["ok"]=all(report[x].get("ok",False) for x in ("pancake","l1_fee_upper","http_fast_poll","simulate_v1"))
(ROOT/"probe_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
raise SystemExit(0 if report["ok"] else 4)
