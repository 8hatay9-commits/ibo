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

AERO_ALL_POOLS_LENGTH="efde4e64"
AERO_ALL_POOLS="41d1de97"
AERO_METADATA="392f37e9"

def u256_word(n):return f"{int(n):064x}"
def addr_word(raw,idx=0):
    h=(raw or "0x").removeprefix("0x")
    if len(h)<64*(idx+1):raise ValueError("short return data")
    return "0x"+h[idx*64:(idx+1)*64][-40:]
def uint_word(raw,idx=0):
    h=(raw or "0x").removeprefix("0x")
    if len(h)<64*(idx+1):raise ValueError("short return data")
    return int(h[idx*64:(idx+1)*64],16)

def seed_aerodrome_v2():
    urls=["https://base-rpc.publicnode.com"]+list(cfg.get("http_rpc") or [])
    rpc=RpcClient(urls,min_interval=0.12)
    total_seeded=0
    results=[]
    for factory in cfg["factories"]["aerodrome_v2"]:
        if STOP.exists():break
        length=uint_word(rpc.call("eth_call",[{"to":factory,"data":"0x"+AERO_ALL_POOLS_LENGTH},"latest"],timeout=15,max_attempts=6))
        key="aeroenum:"+factory.lower()
        i=int(db.get_progress(key,0))
        started=i; last_report=0
        while i<length and not STOP.exists():
            pool_raw=rpc.call("eth_call",[{"to":factory,"data":"0x"+AERO_ALL_POOLS+u256_word(i)},"latest"],timeout=15,max_attempts=6)
            pool=addr_word(pool_raw)
            meta=rpc.call("eth_call",[{"to":pool,"data":"0x"+AERO_METADATA},"latest"],timeout=15,max_attempts=6)
            stable=uint_word(meta,4)
            token0=addr_word(meta,5); token1=addr_word(meta,6)
            if stable not in (0,1):raise ValueError("bad stable flag")
            db.upsert_pool(pool,"aerodrome_v2",factory,token0,token1,stable,None)
            i+=1; total_seeded+=1
            if i%25==0:db.set_progress(key,i)
            if time.time()-last_report>=5:
                save_progress({"ok":True,"phase":"AERODROME_DIRECT_ENUM","factory":factory,
                               "aerodrome_length":length,"aerodrome_next_index":i,
                               "aerodrome_seeded_this_run":i-started})
                last_report=time.time()
        db.set_progress(key,i)
        latest=hexint(rpc.call("eth_blockNumber"))
        db.set_progress("scanv31:"+factory.lower(),latest+1)
        results.append({"factory":factory,"length":length,"start_index":started,"next_index":i,
                        "seeded_this_run":i-started})
    save_progress({"ok":True,"phase":"AERODROME_DIRECT_ENUM_DONE","aerodrome_results":results,
                   "aerodrome_seeded_total_this_run":total_seeded})
    return results

ACTIVE.write_text(str(time.time()),encoding="utf-8")
try:
    seed_aerodrome_v2()
    ns["main"]()
finally:
    try:ACTIVE.unlink()
    except FileNotFoundError:pass
