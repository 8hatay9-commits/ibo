import hashlib, json, time, urllib.request

CORE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/46012d49d9d8f737fa936ef42443dc354d06e589/flashbot/releases/v3.6.0/backfill.py"
CORE_GIT_BLOB_SHA1="68ab71126b78ad4f3c2beed5a40401fa020e3796"
raw=urllib.request.urlopen(CORE_URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=CORE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.6 backfill mismatch: {got}")
src=raw.decode("utf-8")
marker="\nACTIVE.write_text"
if marker not in src:
    raise RuntimeError("V3.6 backfill start marker not found")
src=src.split(marker,1)[0]
v={"__name__":"flashbot_v36_backfill","__file__":__file__}
exec(compile(src,CORE_URL,"exec"),v)

ns=v["ns"]; db=v["db"]; STOP=v["STOP"]; ACTIVE=v["ACTIVE"]; save_progress=v["save_progress"]
PANCAKE_FACTORY="0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"

def seed_pancake_v3():
    if STOP.exists(): return None
    result=ns["scan_factory"](PANCAKE_FACTORY,"pancakeswap_v3",ns["UNI_TOPIC"],ns["parse_uni"])
    save_progress({"ok":True,"phase":"PANCAKESWAP_V3_ENUM_DONE","pancake_result":result})
    return result

ACTIVE.write_text(str(time.time()),encoding="utf-8")
try:
    pancake=seed_pancake_v3()
    slip=v["seed_slipstream"]()
    ns["main"]()
    try:
        (v["ROOT"]/"backfill_v37_report.json").write_text(json.dumps({
            "ok":True,"type":"V3_7_BACKFILL","pancakeswap_v3":pancake,"slipstream":slip,
            "pool_count":db.count_pools(),"timestamp":time.time()
        },indent=2),encoding="utf-8")
    except Exception: pass
finally:
    try: ACTIVE.unlink()
    except FileNotFoundError: pass
