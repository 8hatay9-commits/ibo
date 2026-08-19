
import json, os, sys, time, traceback
from pathlib import Path
from rpc import RpcClient, hexint, addr_from_topic, addr_from_word, words
from db import DB

ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"settings.json").read_text(encoding="utf-8"))
db=DB(ROOT/cfg["db"])
rpc=RpcClient(cfg["http_rpc"],cfg["backfill"]["rpc_min_interval_seconds"])
STOP=ROOT/"STOP_BACKFILL"

def get_code(addr,block):
    return rpc.call("eth_getCode",[addr,hex(block) if isinstance(block,int) else block])

def deployment_block(addr,latest):
    key="deploy:"+addr.lower()
    old=db.get_progress(key)
    if old is not None:return int(old)
    lo,hi=0,latest
    if get_code(addr,hi) in ("0x","0x0"): raise RuntimeError("factory has no code at latest: "+addr)
    while lo<hi:
        mid=(lo+hi)//2
        code=get_code(addr,mid)
        if code not in ("0x","0x0"): hi=mid
        else: lo=mid+1
    db.set_progress(key,lo); return lo

def parse_uni(log,venue,factory):
    t=log.get("topics") or []; w=words(log.get("data"))
    if len(t)!=4 or len(w)<2:return 0
    token0=addr_from_topic(t[1]); token1=addr_from_topic(t[2]); param=int(t[3],16)
    pool=addr_from_word(w[1])
    db.upsert_pool(pool,venue,factory,token0,token1,param,hexint(log["blockNumber"]))
    return 1

def parse_aero_v2(log,factory):
    t=log.get("topics") or []; w=words(log.get("data"))
    # PoolCreated(address indexed token0,address indexed token1,bool indexed stable,address pool,uint256)
    if len(t)!=4 or len(w)<2:return 0
    stable=int(t[3],16)
    if stable not in (0,1):return 0
    token0=addr_from_topic(t[1]); token1=addr_from_topic(t[2]); pool=addr_from_word(w[0])
    if int(pool,16)==0:return 0
    db.upsert_pool(pool,"aerodrome_v2",factory,token0,token1,stable,hexint(log["blockNumber"]))
    return 1

def scan_factory(factory,venue,parser):
    latest=hexint(rpc.call("eth_blockNumber"))
    dep=deployment_block(factory,latest)
    key="scan:"+factory.lower()
    pos=int(db.get_progress(key,dep))
    chunk=int(db.get_progress(key+":chunk",cfg["backfill"]["initial_chunk"]))
    mn=cfg["backfill"]["min_chunk"]; mx=cfg["backfill"]["max_chunk"]
    found=0
    while pos<=latest and not STOP.exists():
        end=min(latest,pos+chunk-1)
        try:
            logs=rpc.call("eth_getLogs",[{"fromBlock":hex(pos),"toBlock":hex(end),"address":factory}],timeout=35)
            for lg in logs or []: found += parser(lg,venue,factory) if parser==parse_uni else parser(lg,factory)
            pos=end+1; db.set_progress(key,pos)
            if len(logs or [])<200: chunk=min(mx,int(chunk*1.4))
            db.set_progress(key+":chunk",chunk)
        except Exception as e:
            msg=str(e).lower()
            if chunk>mn:
                chunk=max(mn,chunk//2); db.set_progress(key+":chunk",chunk); continue
            raise
    return {"factory":factory,"venue":venue,"deployment_block":dep,"next_block":pos,"found":found}

def main():
    try:STOP.unlink()
    except FileNotFoundError:pass
    results=[]
    for f in cfg["factories"]["uniswap_v3"]:
        if STOP.exists():break
        results.append(scan_factory(f,"uniswap_v3",parse_uni))
    for f in cfg["factories"]["aerodrome_slipstream"]:
        if STOP.exists():break
        # Slipstream factory is Uniswap-V3-style; only exact PoolCreated selector is accepted.
        results.append(scan_factory(f,"aerodrome_slipstream",parse_uni))
    for f in cfg["factories"]["aerodrome_v2"]:
        if STOP.exists():break
        results.append(scan_factory(f,"aerodrome_v2",parse_aero_v2))
    out={"ok":True,"type":"V3_BACKFILL","pool_count":db.count_pools(),"results":results,"stopped":STOP.exists(),"timestamp":time.time()}
    (ROOT/"backfill_report.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
    print(json.dumps(out,indent=2))
if __name__=="__main__":
    main()
