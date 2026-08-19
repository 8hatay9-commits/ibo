import hashlib, json, sys, time, urllib.request
from collections import deque

CORE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/4eeffac3a0dafa2e932ebdeb95ece61517907d33/flashbot/releases/v3.2.0/daemon.py"
CORE_GIT_BLOB_SHA1="9b3ff553f35a991c09267ea313d3675e16584d0e"

raw=urllib.request.urlopen(CORE_URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=CORE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned core mismatch: {got}")

ns={"__name__":"flashbot_core","__file__":__file__}
exec(compile(raw,CORE_URL,"exec"),ns)

cfg=ns["cfg"]
cfg["version"]="FLASHBOT-PRODUCTION-V3.5.0"
qcfg=cfg["quote"]
# Scarce-RPC / scarce-gas policy:
# one tiny probe finds the sign of the edge; only a gross-positive route earns sizing calls.
qcfg["probe_sizes_human"]=[100]
qcfg["refine_if_gross_bps_above"]=0.0
qcfg["refine_sizes_human"]=[25,50,250,500,1000,2500,5000,10000,25000,50000,100000,250000,500000,1000000,2000000,5000000]
qcfg["route_quote_ttl_seconds"]=75
qcfg["max_cycles_per_trigger"]=64
qcfg["quote_budget_per_batch"]=8
qcfg["triangle_neighbor_limit"]=100
cfg["risk"]["profit_target_usd"]=10000

db=ns["db"]; EVENTS=ns["EVENTS"]; STRUCT=ns["STRUCT"]; QUOTED=ns["QUOTED"]; PROFITABLE=ns["PROFITABLE"]
ACTIVE=ns["ACTIVE"]; STOP=ns["STOP"]; RpcClient=ns["RpcClient"]
save=ns["save"]; cycles_from_pool=ns["cycles_from_pool"]; rotate=ns["rotate_cycle_to_anchor"]
should_quote=ns["should_quote_route"]; quote_route=ns["quote_route"]

def route_key(c):
    return (c["kind"],tuple(p["address"].lower() for p in c["pools"]),tuple(t.lower() for t in c["tokens"]))

def reverse_anchored(c):
    if c["kind"]=="2pool":
        anchor=c["tokens"][0].lower()
        other=c["tokens"][1].lower()
        return {"kind":"2pool","pools":[c["pools"][1],c["pools"][0]],"tokens":[anchor,other,anchor]}
    if c["kind"]=="triangle":
        anchor=c["tokens"][0].lower()
        a=c["tokens"][1].lower(); b=c["tokens"][2].lower()
        return {"kind":"triangle","pools":[c["pools"][2],c["pools"][1],c["pools"][0]],"tokens":[anchor,b,a,anchor]}
    return None

def priority(c):
    venues=[p["venue"] for p in c["pools"]]
    mixed=len(set(venues))>1
    return (0 if c["kind"]=="2pool" else 1, 0 if mixed else 1)

def write_jsonl(path,obj):
    with path.open("a",encoding="utf-8") as f:
        f.write(json.dumps(obj,separators=(",",":"))+"\n")

def handle_logs_breadth(st,logs,q,trigger=None):
    touched=[]
    for lg in logs or []:
        st["logs"]=int(st.get("logs",0))+1
        a=(lg.get("address") or "").lower()
        p=db.pool(a) if a else None
        if p:
            st["known_pool_hits"]=int(st.get("known_pool_hits",0))+1
            touched.append(p)
    if not touched:return

    tx=(trigger or {}).get("hash") or (logs[0].get("transactionHash") if logs else None)
    block=(trigger or {}).get("blockNumber") or (logs[0].get("blockNumber") if logs else None)
    write_jsonl(EVENTS,{"at":time.time(),"tx":tx,"block":block,"touched":list(dict.fromkeys(p["address"] for p in touched))})

    # Build and rank candidates locally first. This is CPU work, so we spend no extra RPC on losers.
    cand={}
    anchor=qcfg["anchor_token"]
    for p in {x["address"]:x for x in touched}.values():
        for c in cycles_from_pool(p):
            anchored=rotate(c,anchor)
            if not anchored:continue
            if any(x["venue"] not in qcfg["supported_venues"] for x in anchored["pools"]):continue
            cand[route_key(anchored)]=anchored
            rev=reverse_anchored(anchored)
            if rev:cand[route_key(rev)]=rev

    ranked=sorted(cand.values(),key=priority)
    st["structural_candidates"]=int(st.get("structural_candidates",0))+len(ranked)
    st["route_candidates_last_batch"]=len(ranked)

    # Keep a compact structural audit trail.
    for c in ranked[:64]:
        write_jsonl(STRUCT,{"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],
                            "venues":[x["venue"] for x in c["pools"]],"tokens":c["tokens"],
                            "at":time.time(),"trigger_tx":tx,"block":block})

    budget=int(qcfg["quote_budget_per_batch"]); used=0; ttl_skipped=0
    for c in ranked:
        if used>=budget:break
        key=route_key(c)
        # Critical: do not burn the TTL for a route that was skipped only because the batch budget was full.
        if not should_quote(key):
            ttl_skipped+=1
            continue

        used+=1
        rows=quote_route(q,c)
        st["quote_attempts"]=int(st.get("quote_attempts",0))+1
        valid=[r for r in rows if "gross_edge_bps" in r]
        if not valid:
            st["quote_empty_or_error"]=int(st.get("quote_empty_or_error",0))+1
            continue

        best_gross=max(valid,key=lambda x:x["gross_edge_bps"])
        bg=float(best_gross["gross_edge_bps"])
        if bg>float(st.get("best_gross_edge_bps_seen",-1e99)):
            st["best_gross_edge_bps_seen"]=bg
            st["best_gross_usd_seen"]=float(best_gross.get("gross_usd",0.0))
            st["best_gross_route"]={"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],
                                    "venues":[x["venue"] for x in c["pools"]],"best":best_gross}

        gross_good=[r for r in valid if r["gross_edge_bps"]>=float(qcfg["min_gross_edge_bps"])]
        after_good=[r for r in valid if r.get("profitable_after_flash_before_gas")]
        if gross_good:
            st["gross_positive_candidates"]=int(st.get("gross_positive_candidates",0))+1
        if after_good:
            best=max(after_good,key=lambda x:x["after_flash_fee_usd_before_gas"])
            st["positive_after_flash_before_gas"]=int(st.get("positive_after_flash_before_gas",0))+1
            if float(best["after_flash_fee_usd_before_gas"])>float(st.get("best_after_flash_before_gas_usd",0.0)):
                st["best_after_flash_before_gas_usd"]=float(best["after_flash_fee_usd_before_gas"])
                st["best_after_flash_route"]={"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],
                                               "venues":[x["venue"] for x in c["pools"]],"best":best}
            rec={"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],
                 "venues":[x["venue"] for x in c["pools"]],"tokens":c["tokens"],
                 "at":time.time(),"trigger_tx":tx,"block":block,"quotes":rows,"best":best,
                 "net_profit_verified":False,
                 "note":"pending exact DEX quote + live Aave premium; execution gas/L1/slippage/atomic simulation still required"}
            write_jsonl(PROFITABLE,rec)
        elif gross_good:
            best=max(gross_good,key=lambda x:x["gross_edge_bps"])
            write_jsonl(QUOTED,{"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],
                                "venues":[x["venue"] for x in c["pools"]],"tokens":c["tokens"],
                                "at":time.time(),"trigger_tx":tx,"block":block,"quotes":rows,"best":best,
                                "net_profit_verified":False,
                                "note":"gross positive but not positive after live Aave premium; gas not yet applied"})
    st["quote_budget_used_last_batch"]=used
    st["quote_ttl_skipped_last_batch"]=ttl_skipped

def http_fallback_breadth(st,deadline,q):
    rpc=RpcClient(cfg["flashblocks_http"],min_interval=0.9)
    st.update({"connected":True,"feed_mode":"HTTP_PENDING_LOGS_BREADTH_V35",
               "feed_url":cfg["flashblocks_http"][0],"last_error":None})
    save(st)
    seen=set();order=deque();max_seen=int(cfg["fallback"]["max_seen_log_keys"])
    while not STOP.exists() and (not deadline or time.time()<deadline):
        pause=float(cfg["fallback"]["pending_logs_poll_seconds_while_backfill"] if ACTIVE.exists()
                    else cfg["fallback"]["pending_logs_poll_seconds"])
        try:
            logs=rpc.call("eth_getLogs",[{"fromBlock":"pending","toBlock":"pending"}],timeout=15,max_attempts=4) or []
            fresh=[]
            for lg in logs:
                k=((lg.get("transactionHash") or ""),(lg.get("logIndex") or ""),(lg.get("address") or ""))
                if k in seen:continue
                seen.add(k);order.append(k);fresh.append(lg)
                while len(order)>max_seen:seen.discard(order.popleft())

            st["messages"]=int(st.get("messages",0))+1
            st["last_event_at"]=time.time()
            st["pending_logs_last_batch"]=len(logs)
            st["pending_logs_fresh_batch"]=len(fresh)
            st["pool_count"]=db.count_pools()
            st["last_error"]=None
            st["backfill_active"]=ACTIVE.exists()
            save(st)  # liveness first; expensive quotes cannot hide feed progress.

            handle_logs_breadth(st,fresh,q,{})
            st["pool_count"]=db.count_pools()
            save(st)
            time.sleep(pause)
        except Exception as e:
            st["last_error"]=f"{type(e).__name__}: {e}"
            save(st)
            time.sleep(min(20,max(3,pause*2)))

ns["handle_logs"]=handle_logs_breadth
ns["http_fallback"]=http_fallback_breadth

seconds=int(sys.argv[1]) if len(sys.argv)>1 else 0
ns["main"](seconds)
