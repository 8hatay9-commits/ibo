
import json, time
from pathlib import Path
from rpc import RpcClient, hexint, addr_from_topic, addr_from_word, words
from db import DB

ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"settings.json").read_text(encoding="utf-8"))
db=DB(ROOT/cfg["db"])
rpc=RpcClient(cfg["http_rpc"],cfg["backfill"]["rpc_min_interval_seconds"])
STOP=ROOT/"STOP_BACKFILL"; ACTIVE=ROOT/"BACKFILL_ACTIVE"; PROGRESS=ROOT/"backfill_progress.json"

UNI_TOPIC=cfg["events"]["uniswap_v3_pool_created"].lower()
AERO_V2_TOPIC=cfg["events"]["aerodrome_v2_pool_created"].lower()

def save_progress(o):
    o=dict(o); o["timestamp"]=time.time(); o["pool_count"]=db.count_pools()
    t=PROGRESS.with_suffix(".tmp"); t.write_text(json.dumps(o,indent=2),encoding="utf-8"); t.replace(PROGRESS)

def get_code(addr,block):
    return rpc.call("eth_getCode",[addr,hex(block) if isinstance(block,int) else block])

def deployment_block(addr,latest):
    key="deploy:"+addr.lower()
    old=db.get_progress(key)
    if old is not None:return int(old)
    lo,hi=0,latest
    if get_code(addr,hi) in ("0x","0x0"):raise RuntimeError("factory no code: "+addr)
    while lo<hi and not STOP.exists():
        mid=(lo+hi)//2
        if get_code(addr,mid) not in ("0x","0x0"):hi=mid
        else:lo=mid+1
    db.set_progress(key,lo);return lo

def parse_uni(log,venue,factory):
    t=log.get("topics") or []; w=words(log.get("data"))
    if len(t)!=4 or t[0].lower()!=UNI_TOPIC or len(w)<2:return 0
    token0=addr_from_topic(t[1]);token1=addr_from_topic(t[2]);fee=int(t[3],16)
    pool=addr_from_word(w[1])
    if int(pool,16)==0:return 0
    db.upsert_pool(pool,venue,factory,token0,token1,fee,hexint(log["blockNumber"]))
    return 1

def parse_aero(log,venue,factory):
    t=log.get("topics") or [];w=words(log.get("data"))
    if len(t)!=4 or t[0].lower()!=AERO_V2_TOPIC or len(w)<2:return 0
    stable=int(t[3],16)
    if stable not in (0,1):return 0
    token0=addr_from_topic(t[1]);token1=addr_from_topic(t[2]);pool=addr_from_word(w[0])
    if int(pool,16)==0:return 0
    db.upsert_pool(pool,"aerodrome_v2",factory,token0,token1,stable,hexint(log["blockNumber"]))
    return 1

def scan_factory(factory,venue,topic,parser):
    latest=hexint(rpc.call("eth_blockNumber"))
    dep=deployment_block(factory,latest)
    key="scan:"+factory.lower()
    pos=int(db.get_progress(key,dep))
    chunk=int(db.get_progress(key+":chunk",cfg["backfill"]["initial_chunk"]))
    mn=int(cfg["backfill"]["min_chunk"]);mx=int(cfg["backfill"]["max_chunk"])
    found=0;calls=0;last_report=0
    while pos<=latest and not STOP.exists():
        end=min(latest,pos+chunk-1)
        try:
            flt={"fromBlock":hex(pos),"toBlock":hex(end),"address":factory,"topics":[topic]}
            logs=rpc.call("eth_getLogs",[flt],timeout=35,max_attempts=8) or []
            calls+=1
            for lg in logs:found+=parser(lg,venue,factory)
            pos=end+1;db.set_progress(key,pos)
            if len(logs)==0:chunk=min(mx,max(chunk+1,int(chunk*1.8)))
            elif len(logs)<100:chunk=min(mx,max(chunk+1,int(chunk*1.35)))
            elif len(logs)>2000:chunk=max(mn,chunk//2)
            db.set_progress(key+":chunk",chunk)
            if time.time()-last_report>=cfg["backfill"]["progress_report_seconds"]:
                save_progress({"ok":True,"current_factory":factory,"venue":venue,"deployment_block":dep,
                               "latest_block":latest,"next_block":pos,"chunk":chunk,"found_this_factory":found,
                               "rpc_calls_this_factory":calls})
                last_report=time.time()
        except Exception as e:
            if chunk>mn:
                chunk=max(mn,chunk//2);db.set_progress(key+":chunk",chunk)
                save_progress({"ok":True,"current_factory":factory,"venue":venue,"next_block":pos,
                               "chunk":chunk,"recovering_from":f"{type(e).__name__}: {e}"})
                continue
            raise
    return {"factory":factory,"venue":venue,"deployment_block":dep,"next_block":pos,
            "latest_block":latest,"found":found,"rpc_calls":calls}

def main():
    try:STOP.unlink()
    except FileNotFoundError:pass
    ACTIVE.write_text(str(time.time()),encoding="utf-8")
    results=[]
    try:
        for f in cfg["factories"]["uniswap_v3"]:
            if STOP.exists():break
            results.append(scan_factory(f,"uniswap_v3",UNI_TOPIC,parse_uni))
        # Slipstream factory event ABI may differ by deployment; do not ingest it as Uniswap
        # unless the exact official event topic has been validated. This prevents corrupt registry entries.
        for f in cfg["factories"]["aerodrome_v2"]:
            if STOP.exists():break
            results.append(scan_factory(f,"aerodrome_v2",AERO_V2_TOPIC,parse_aero))
        out={"ok":True,"type":"V3_1_BACKFILL","pool_count":db.count_pools(),"results":results,
             "slipstream_status":"DEFERRED_UNTIL_EXACT_EVENT_ABI_VALIDATED",
             "stopped":STOP.exists(),"timestamp":time.time()}
        (ROOT/"backfill_report.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
        save_progress(out)
        print(json.dumps(out,indent=2))
    finally:
        try:ACTIVE.unlink()
        except FileNotFoundError:pass

if __name__=="__main__":main()
