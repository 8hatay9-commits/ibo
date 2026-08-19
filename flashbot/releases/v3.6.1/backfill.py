import hashlib, json, time, urllib.request

CORE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/28f8f4eeee98f56e6d30551585072b2b4a4b3727/flashbot/releases/v3.2.1/backfill.py"
CORE_GIT_BLOB_SHA1="a9537cbdea1c9aa9d1806ee52843b93f94123d51"

raw=urllib.request.urlopen(CORE_URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=CORE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned backfill core mismatch: {got}")

ns={"__name__":"flashbot_backfill_core","__file__":__file__}
exec(compile(raw,CORE_URL,"exec"),ns)

cfg=ns["cfg"]; db=ns["db"]; STOP=ns["STOP"]; ACTIVE=ns["ACTIVE"]; save_progress=ns["save_progress"]
RpcClient=ns["RpcClient"]; hexint=ns["hexint"]

ALL_POOLS_LENGTH="efde4e64"
ALL_POOLS="41d1de97"
TOKEN0="0dfe1681"
TOKEN1="d21220a7"
TICK_SPACING="d0c93a7c"

def u256_word(n):return f"{int(n):064x}"
def addr_word(raw,idx=0):
    h=(raw or "0x").removeprefix("0x")
    if len(h)<64*(idx+1):raise ValueError("short return data")
    return "0x"+h[idx*64:(idx+1)*64][-40:]
def uint_word(raw,idx=0):
    h=(raw or "0x").removeprefix("0x")
    if len(h)<64*(idx+1):raise ValueError("short return data")
    return int(h[idx*64:(idx+1)*64],16)

def seed_slipstream():
    urls=["https://base-rpc.publicnode.com"]+list(cfg.get("http_rpc") or [])
    rpc=RpcClient(urls,min_interval=float(cfg["backfill"].get("slipstream_rpc_min_interval_seconds",0.14)))
    total=0; results=[]
    verified={x.lower() for x in (cfg.get("factories",{}).get("aerodrome_slipstream") or [])}
    quoter_map={k.lower():v for k,v in (cfg.get("contracts",{}).get("slipstream_quoters") or {}).items()}
    for factory in sorted(verified):
        if STOP.exists():break
        if factory not in quoter_map:continue
        length=uint_word(rpc.call("eth_call",[{"to":factory,"data":"0x"+ALL_POOLS_LENGTH},"latest"],timeout=15,max_attempts=6))
        key="slipenum:"+factory
        i=int(db.get_progress(key,0)); started=i; last_report=0
        while i<length and not STOP.exists():
            pool=addr_word(rpc.call("eth_call",[{"to":factory,"data":"0x"+ALL_POOLS+u256_word(i)},"latest"],timeout=15,max_attempts=6))
            token0=addr_word(rpc.call("eth_call",[{"to":pool,"data":"0x"+TOKEN0},"latest"],timeout=12,max_attempts=5))
            token1=addr_word(rpc.call("eth_call",[{"to":pool,"data":"0x"+TOKEN1},"latest"],timeout=12,max_attempts=5))
            tick=uint_word(rpc.call("eth_call",[{"to":pool,"data":"0x"+TICK_SPACING},"latest"],timeout=12,max_attempts=5))
            db.upsert_pool(pool,"aerodrome_slipstream",factory,token0,token1,tick,None)
            i+=1; total+=1
            if i%25==0:db.set_progress(key,i)
            if time.time()-last_report>=5:
                save_progress({"ok":True,"phase":"SLIPSTREAM_DIRECT_ENUM","factory":factory,
                               "length":length,"next_index":i,"seeded_this_run":i-started})
                last_report=time.time()
        db.set_progress(key,i)
        results.append({"factory":factory,"length":length,"start_index":started,"next_index":i,"seeded_this_run":i-started})
    save_progress({"ok":True,"phase":"SLIPSTREAM_DIRECT_ENUM_DONE","slipstream_results":results,
                   "slipstream_seeded_total_this_run":total})
    return results

ACTIVE.write_text(str(time.time()),encoding="utf-8")
try:
    slip=seed_slipstream()
    ns["main"]()
finally:
    try:ACTIVE.unlink()
    except FileNotFoundError:pass
