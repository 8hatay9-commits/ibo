import json, time
from pathlib import Path
from rpc import RpcClient

ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"settings.json").read_text(encoding="utf-8"))
fast=RpcClient(cfg["flashblocks_http"],min_interval=0.05)
std=RpcClient(cfg["http_rpc"],min_interval=0.16)

AAVE_POOL=cfg["contracts"]["aave_pool"]

def word_addr(a):
    return ("0"*24)+a.lower().removeprefix("0x")

def words(raw):
    h=(raw or "0x").removeprefix("0x")
    if len(h)%64:
        raise ValueError("unaligned ABI result")
    return [int(h[i:i+64],16) for i in range(0,len(h),64)]

def sha3_text(text):
    return std.call("web3_sha3",["0x"+text.encode("utf-8").hex()],timeout=8,max_attempts=3)

started_all=time.monotonic()
report={
    "ok":False,
    "type":"AAVE_BASE_LIQUIDATION_RESEARCH_V2_BATCHED",
    "engine":"FLASHBOT-PRODUCTION-V3.8.4",
    "pool":AAVE_POOL,
    "window_blocks":12000,
    "borrowers_sample_cap":150,
    "recent_borrow_events":0,
    "unique_recent_borrowers":0,
    "checked_users":0,
    "near_liquidation":[],
    "liquidatable_now":[],
    "scan_errors":[],
    "timings":{},
    "timestamp":time.time()
}

try:
    t=time.monotonic()
    borrow_topic=sha3_text("Borrow(address,address,address,uint256,uint8,uint256,uint16)")
    get_user_sel=sha3_text("getUserAccountData(address)")[2:10]
    report["borrow_topic"]=borrow_topic
    report["get_user_account_data_selector"]="0x"+get_user_sel
    report["timings"]["selectors_s"]=round(time.monotonic()-t,3)

    t=time.monotonic()
    latest=int(std.call("eth_blockNumber",[],timeout=8,max_attempts=3),16)
    start=max(0,latest-int(report["window_blocks"])+1)
    report["latest_block"]=latest
    report["start_block"]=start

    events=[]
    chunk=2000
    b=start
    while b<=latest:
        e=min(latest,b+chunk-1)
        try:
            part=std.call("eth_getLogs",[{
                "address":AAVE_POOL,
                "fromBlock":hex(b),
                "toBlock":hex(e),
                "topics":[borrow_topic]
            }],timeout=12,max_attempts=3) or []
            events.extend(part)
        except Exception as ex:
            report["scan_errors"].append({
                "phase":"borrow_logs","from":b,"to":e,
                "error":f"{type(ex).__name__}: {ex}"
            })
        b=e+1
    report["timings"]["borrow_logs_s"]=round(time.monotonic()-t,3)
    report["recent_borrow_events"]=len(events)

    last_seen={}
    for lg in events:
        ts=lg.get("topics") or []
        if len(ts)<3:
            continue
        topic=ts[2].removeprefix("0x")
        if len(topic)!=64:
            continue
        user="0x"+topic[-40:]
        try:
            block=int(lg.get("blockNumber","0x0"),16)
        except Exception:
            block=0
        if block>=last_seen.get(user,0):
            last_seen[user]=block

    borrowers=sorted(last_seen.items(),key=lambda kv:kv[1],reverse=True)
    report["unique_recent_borrowers"]=len(borrowers)
    sample=borrowers[:int(report["borrowers_sample_cap"])]

    t=time.monotonic()
    ranked=[]
    batch_size=50
    for offset in range(0,len(sample),batch_size):
        batch=sample[offset:offset+batch_size]
        payload={
            "blockStateCalls":[{
                "calls":[{"to":AAVE_POOL,"data":"0x"+get_user_sel+word_addr(user)} for user,_ in batch],
                "stateOverrides":{}
            }],
            "traceTransfers":False,
            "validation":False
        }
        try:
            sim=fast.call("eth_simulateV1",[payload,"pending"],timeout=18,max_attempts=3)
            calls=((sim or [{}])[0].get("calls") or [])
            if len(calls)!=len(batch):
                raise ValueError(f"simulate call count mismatch {len(calls)} != {len(batch)}")
            for (user,last_block),call in zip(batch,calls):
                try:
                    if call.get("status")!="0x1":
                        raise ValueError("account-data simulated call failed")
                    raw=call.get("returnData") or call.get("output") or "0x"
                    vals=words(raw)
                    if len(vals)<6:
                        raise ValueError("short getUserAccountData result")
                    collateral,debt,available,liq_threshold,ltv,hf=vals[:6]
                    if debt<=0:
                        continue
                    rec={
                        "user":user,
                        "last_borrow_block":last_block,
                        "total_collateral_base_raw":str(collateral),
                        "total_debt_base_raw":str(debt),
                        "available_borrows_base_raw":str(available),
                        "liquidation_threshold_bps":liq_threshold,
                        "ltv_bps":ltv,
                        "health_factor_1e18":str(hf),
                        "health_factor":round(hf/1e18,8)
                    }
                    ranked.append(rec)
                except Exception as ex:
                    if len(report["scan_errors"])<20:
                        report["scan_errors"].append({
                            "phase":"decode_account_data","user":user,
                            "error":f"{type(ex).__name__}: {ex}"
                        })
        except Exception as ex:
            report["scan_errors"].append({
                "phase":"simulate_batch","offset":offset,"size":len(batch),
                "error":f"{type(ex).__name__}: {ex}"
            })

    report["timings"]["account_batches_s"]=round(time.monotonic()-t,3)
    report["checked_users"]=len(sample)
    ranked.sort(key=lambda x:x["health_factor"])
    report["lowest_health_factors"]=ranked[:20]
    report["near_liquidation"]=[x for x in ranked if 0<int(x["health_factor_1e18"])<1050000000000000000][:20]
    report["liquidatable_now"]=[x for x in ranked if 0<int(x["health_factor_1e18"])<1000000000000000000][:20]
    report["ok"]=True
except Exception as e:
    report["fatal_error"]=f"{type(e).__name__}: {e}"

report["timings"]["total_s"]=round(time.monotonic()-started_all,3)
(ROOT/"probe_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
raise SystemExit(0 if report["ok"] else 4)
