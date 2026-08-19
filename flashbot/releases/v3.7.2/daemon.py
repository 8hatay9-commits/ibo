import hashlib, sys, time, urllib.request

CORE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/f9bfd5fc90e3989b4afc88ce2f39848febd08528/flashbot/releases/v3.7.0/daemon.py"
CORE_GIT_BLOB_SHA1="6c447acdb4dfd19bfae3ee7625000bfabc4a08e4"
raw=urllib.request.urlopen(CORE_URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=CORE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.7 daemon mismatch: {got}")
src=raw.decode("utf-8")
marker='\nseconds=int(sys.argv[1]) if len(sys.argv)>1 else 0\ncore["main"](seconds)\n'
if marker not in src:
    raise RuntimeError("V3.7 daemon start marker not found")
src=src.rsplit(marker,1)[0]
v={"__name__":"flashbot_v37_core","__file__":__file__}
exec(compile(src,CORE_URL,"exec"),v)

core=v["core"]; cfg=v["cfg"]; db=v["db"]; qcfg=v["qcfg"]
cfg["version"]="FLASHBOT-PRODUCTION-V3.7.2"
qcfg["max_cycles_per_trigger"]=96
qcfg["quote_budget_per_batch"]=4

PAIR_CACHE={}
NEIGH_CACHE={}
CACHE_TTL=12.0
ANCHOR=qcfg["anchor_token"].lower()

def _other(pool,token):
    token=token.lower()
    if pool["token0"]==token:return pool["token1"]
    if pool["token1"]==token:return pool["token0"]
    return None

def _pair_cached(a,b,limit=24):
    a=a.lower();b=b.lower(); key=(a,b) if a<=b else (b,a)
    now=time.time(); item=PAIR_CACHE.get(key)
    if item and now-item[0]<CACHE_TTL:
        return item[1][:limit]
    rows=db.pair_pools(a,b,max(32,limit))
    PAIR_CACHE[key]=(now,rows)
    if len(PAIR_CACHE)>12000:
        cutoff=now-CACHE_TTL*3
        for k,x in list(PAIR_CACHE.items()):
            if x[0]<cutoff:PAIR_CACHE.pop(k,None)
    return rows[:limit]

def _neighbors_cached(token,limit=24):
    token=token.lower(); now=time.time(); item=NEIGH_CACHE.get(token)
    if item and now-item[0]<CACHE_TTL:
        return item[1][:limit]
    rows=db.neighbors(token,max(48,limit))
    NEIGH_CACHE[token]=(now,rows)
    if len(NEIGH_CACHE)>5000:
        cutoff=now-CACHE_TTL*3
        for k,x in list(NEIGH_CACHE.items()):
            if x[0]<cutoff:NEIGH_CACHE.pop(k,None)
    return rows[:limit]

def cycles_value_first_fast(pool):
    out=[]; seen=set(); t0=(pool.get("token0") or "").lower(); t1=(pool.get("token1") or "").lower()
    if not t0 or not t1:return out

    # Latency-critical fast path: same pair across venues.
    for p2 in _pair_cached(t0,t1,24):
        if p2["address"]==pool["address"]:continue
        k=("2",pool["address"],p2["address"])
        if k in seen:continue
        seen.add(k)
        out.append({"kind":"2pool","pools":[pool,p2],"tokens":[t0,t1,t0]})
        if len(out)>=48:return out

    # Anchor-aware triangles. Avoid N x SQLite queries over the million-pool registry.
    if t0!=ANCHOR and t1!=ANCHOR:
        left=_pair_cached(t1,ANCHOR,10)
        right=_pair_cached(ANCHOR,t0,10)
        for p2 in left:
            if p2["address"]==pool["address"]:continue
            for p3 in right:
                if p3["address"] in {pool["address"],p2["address"]}:continue
                k=("3",pool["address"],p2["address"],p3["address"])
                if k in seen:continue
                seen.add(k)
                out.append({"kind":"triangle","pools":[pool,p2,p3],"tokens":[t0,t1,ANCHOR,t0]})
                if len(out)>=96:return out
        return out

    # For an anchor pair, inspect only the hottest neighbors and cached closing pairs.
    if t0==ANCHOR:
        pivot=t1
        for p2 in _neighbors_cached(pivot,24):
            if p2["address"]==pool["address"]:continue
            nxt=_other(p2,pivot)
            if not nxt or nxt in {ANCHOR,pivot}:continue
            for p3 in _pair_cached(nxt,ANCHOR,8):
                if p3["address"] in {pool["address"],p2["address"]}:continue
                k=("3a",pool["address"],p2["address"],p3["address"])
                if k in seen:continue
                seen.add(k)
                out.append({"kind":"triangle","pools":[pool,p2,p3],"tokens":[ANCHOR,pivot,nxt,ANCHOR]})
                if len(out)>=96:return out
        return out

    # t1 is anchor: t0 -> anchor -> nxt -> t0.
    for p2 in _neighbors_cached(ANCHOR,24):
        if p2["address"]==pool["address"]:continue
        nxt=_other(p2,ANCHOR)
        if not nxt or nxt in {ANCHOR,t0}:continue
        for p3 in _pair_cached(nxt,t0,8):
            if p3["address"] in {pool["address"],p2["address"]}:continue
            k=("3b",pool["address"],p2["address"],p3["address"])
            if k in seen:continue
            seen.add(k)
            out.append({"kind":"triangle","pools":[pool,p2,p3],"tokens":[t0,ANCHOR,nxt,t0]})
            if len(out)>=96:return out
    return out

v["cycles_value_first"]=cycles_value_first_fast

# Expose performance policy in status through the existing handler's globals.
_orig_handle=v["handle_logs_value"]
def handle_logs_v372(st,logs,q,trigger=None):
    st["route_search_policy_v372"]="FAST_2POOL_ANCHOR_TRIANGLE_CACHED"
    st["pair_cache_entries_v372"]=len(PAIR_CACHE)
    st["neighbor_cache_entries_v372"]=len(NEIGH_CACHE)
    return _orig_handle(st,logs,q,trigger)
v["handle_logs_value"]=handle_logs_v372

seconds=int(sys.argv[1]) if len(sys.argv)>1 else 0
core["main"](seconds)
