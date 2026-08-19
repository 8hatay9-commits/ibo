import hashlib, json, queue, socket, sys, threading, time, urllib.request
from collections import deque

CORE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/4eeffac3a0dafa2e932ebdeb95ece61517907d33/flashbot/releases/v3.2.0/daemon.py"
CORE_GIT_BLOB_SHA1="9b3ff553f35a991c09267ea313d3675e16584d0e"

raw=urllib.request.urlopen(CORE_URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=CORE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned core mismatch: {got}")

ns={"__name__":"flashbot_core","__file__":__file__}
exec(compile(raw,CORE_URL,"exec"),ns)

cfg=ns["cfg"]; cfg["version"]="FLASHBOT-PRODUCTION-V3.6.0"
qcfg=cfg["quote"]
qcfg["probe_sizes_human"]=[100]
qcfg["refine_if_gross_bps_above"]=0.0
qcfg["refine_sizes_human"]=[25,50,250,500,1000,2500,5000,10000,25000,50000,100000,250000,500000,1000000,2000000,5000000]
qcfg["route_quote_ttl_seconds"]=45
qcfg["max_cycles_per_trigger"]=128
qcfg["quote_budget_per_batch"]=12
qcfg["supported_venues"]=["uniswap_v3","aerodrome_v2","aerodrome_slipstream"]
cfg["risk"]["profit_target_usd"]=10000

db=ns["db"]; EVENTS=ns["EVENTS"]; STRUCT=ns["STRUCT"]; QUOTED=ns["QUOTED"]; PROFITABLE=ns["PROFITABLE"]
ACTIVE=ns["ACTIVE"]; STOP=ns["STOP"]; RpcClient=ns["RpcClient"]; SimpleWebSocket=ns["SimpleWebSocket"]
save=ns["save"]; rotate=ns["rotate_cycle_to_anchor"]; should_quote=ns["should_quote_route"]
quote_route=ns["quote_route"]; decode_u256=ns["decode_u256"]; word_addr=ns["word_addr"]; word_uint=ns["word_uint"]

V3_SWAP=(cfg.get("events",{}).get("v3_swap") or "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67").lower()
AERO_V2_SWAP=(cfg.get("events",{}).get("aerodrome_v2_swap") or "0xb3e2773606abfd36b5bd91394b3a54d1398336c65005baf7bf7a05efeffaf75b").lower()
SWAP_TOPICS=[V3_SWAP,AERO_V2_SWAP]
SLIP_V2_SELECTOR="9e7defe6"
SLIP_V1_SELECTOR="e864cee3"

_orig_one=ns["Quoter"].one
def _one_value_first(self,pool,token_in,amount_in):
    if pool.get("venue")!="aerodrome_slipstream":
        return _orig_one(self,pool,token_in,amount_in)
    token_in=token_in.lower()
    if token_in==pool["token0"]:token_out=pool["token1"]
    elif token_in==pool["token1"]:token_out=pool["token0"]
    else:raise ValueError("token not in pool")
    factory=(pool.get("factory") or "").lower()
    spec=(cfg.get("contracts",{}).get("slipstream_quoters") or {}).get(factory)
    if not spec:raise ValueError("unsupported slipstream factory "+factory)
    tick=int(pool.get("param") or 0)
    if tick<=0:raise ValueError("bad slipstream tick spacing")
    if spec["kind"]=="v2":
        data="0x"+SLIP_V2_SELECTOR+word_addr(token_in)+word_addr(token_out)+word_uint(amount_in)+word_uint(tick)+word_uint(0)
        raw=self.rpc.call("eth_call",[{"to":spec["address"],"data":data},"pending"],timeout=15,max_attempts=5)
        return decode_u256(raw),token_out,decode_u256(raw,3)
    data="0x"+SLIP_V1_SELECTOR+word_addr(token_in)+word_addr(token_out)+word_uint(tick)+word_uint(amount_in)+word_uint(0)
    raw=self.rpc.call("eth_call",[{"to":spec["address"],"data":data},"pending"],timeout=15,max_attempts=5)
    return decode_u256(raw),token_out,None
ns["Quoter"].one=_one_value_first

def route_key(c):
    return (c["kind"],tuple(p["address"].lower() for p in c["pools"]),tuple(t.lower() for t in c["tokens"]))

def reverse_anchored(c):
    if c["kind"]=="2pool":
        anchor=c["tokens"][0].lower();other=c["tokens"][1].lower()
        return {"kind":"2pool","pools":[c["pools"][1],c["pools"][0]],"tokens":[anchor,other,anchor]}
    if c["kind"]=="triangle":
        anchor=c["tokens"][0].lower();a=c["tokens"][1].lower();b=c["tokens"][2].lower()
        return {"kind":"triangle","pools":[c["pools"][2],c["pools"][1],c["pools"][0]],"tokens":[anchor,b,a,anchor]}
    return None

def activity_score(c):
    hits=sum(int(p.get("swap_hits") or db.pool_activity(p["address"])[0]) for p in c["pools"])
    last=max(float(p.get("last_seen") or db.pool_activity(p["address"])[1]) for p in c["pools"])
    mixed=len({p["venue"] for p in c["pools"]})>1
    return (0 if c["kind"]=="2pool" else 1,0 if mixed else 1,-hits,-last)

def cycles_value_first(pool):
    out=[]; seen=set(); t0=pool.get("token0");t1=pool.get("token1")
    if not t0 or not t1:return out
    acfg=cfg.get("activity",{})
    pair_limit=int(acfg.get("pair_neighbor_limit",96))
    tri_limit=int(acfg.get("triangle_neighbor_limit",128))
    close_limit=int(acfg.get("triangle_closer_limit",48))

    for p2 in db.pair_pools(t0,t1,pair_limit):
        if p2["address"]==pool["address"]:continue
        k=("2",pool["address"],p2["address"])
        if k in seen:continue
        seen.add(k)
        out.append({"kind":"2pool","pools":[pool,p2],"tokens":[t0,t1,t0]})

    for p2 in db.neighbors(t1,tri_limit):
        if p2["address"]==pool["address"]:continue
        nxt=p2["token1"] if p2["token0"]==t1 else p2["token0"]
        if not nxt or nxt in (t0,t1):continue
        for p3 in db.pair_pools(nxt,t0,close_limit):
            if p3["address"] in {pool["address"],p2["address"]}:continue
            k=("3",pool["address"],p2["address"],p3["address"])
            if k in seen:continue
            seen.add(k)
            out.append({"kind":"triangle","pools":[pool,p2,p3],"tokens":[t0,t1,nxt,t0]})
            if len(out)>=int(qcfg["max_cycles_per_trigger"]):return out
    return out

def write_jsonl(path,obj):
    with path.open("a",encoding="utf-8") as f:f.write(json.dumps(obj,separators=(",",":"))+"\n")

def handle_logs_value(st,logs,q,trigger=None):
    touched={}
    now=time.time()
    for lg in logs or []:
        st["logs"]=int(st.get("logs",0))+1
        a=(lg.get("address") or "").lower()
        p=db.pool(a) if a else None
        if p:
            st["known_pool_hits"]=int(st.get("known_pool_hits",0))+1
            try:db.touch_pool(a,1,now)
            except Exception:pass
            p["swap_hits"],p["last_seen"]=db.pool_activity(a)
            touched[p["address"]]=p
    if not touched:return

    tx=(trigger or {}).get("hash") or ((logs or [{}])[0].get("transactionHash"))
    block=(trigger or {}).get("blockNumber") or ((logs or [{}])[0].get("blockNumber"))
    write_jsonl(EVENTS,{"at":now,"tx":tx,"block":block,"touched":list(touched)})

    cand={}
    anchor=qcfg["anchor_token"]
    for p in touched.values():
        for c in cycles_value_first(p):
            anchored=rotate(c,anchor)
            if not anchored:continue
            if any(x["venue"] not in qcfg["supported_venues"] for x in anchored["pools"]):continue
            cand[route_key(anchored)]=anchored
            rev=reverse_anchored(anchored)
            if rev:cand[route_key(rev)]=rev

    ranked=sorted(cand.values(),key=activity_score)
    st["structural_candidates"]=int(st.get("structural_candidates",0))+len(ranked)
    st["route_candidates_last_batch"]=len(ranked)
    st["candidate_policy"]="VALUE_FIRST_ACTIVITY_RANKED_V36"
    st["active_pool_count"]=db.active_count(cfg.get("activity",{}).get("active_window_seconds",3600))

    for c in ranked[:96]:
        write_jsonl(STRUCT,{"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],
                           "venues":[x["venue"] for x in c["pools"]],"tokens":c["tokens"],
                           "at":time.time(),"trigger_tx":tx,"block":block})

    budget=int(qcfg.get("quote_budget_per_batch",12)); used=0; ttl_skipped=0
    for c in ranked:
        if used>=budget:break
        key=route_key(c)
        if not should_quote(key):
            ttl_skipped+=1;continue
        used+=1
        rows=quote_route(q,c)
        st["quote_attempts"]=int(st.get("quote_attempts",0))+1
        valid=[r for r in rows if "gross_edge_bps" in r]
        if not valid:
            st["quote_empty_or_error"]=int(st.get("quote_empty_or_error",0))+1
            continue
        best_gross=max(valid,key=lambda x:x["gross_edge_bps"]); bg=float(best_gross["gross_edge_bps"])
        if bg>float(st.get("best_gross_edge_bps_seen",-1e99)):
            st["best_gross_edge_bps_seen"]=bg
            st["best_gross_usd_seen"]=float(best_gross.get("gross_usd",0.0))
            st["best_gross_route"]={"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],
                                    "venues":[x["venue"] for x in c["pools"]],"best":best_gross}

        gross_good=[r for r in valid if r["gross_edge_bps"]>=float(qcfg["min_gross_edge_bps"])]
        after_good=[r for r in valid if r.get("profitable_after_flash_before_gas")]
        if gross_good:st["gross_positive_candidates"]=int(st.get("gross_positive_candidates",0))+1
        if after_good:
            best=max(after_good,key=lambda x:x["after_flash_fee_usd_before_gas"])
            st["positive_after_flash_before_gas"]=int(st.get("positive_after_flash_before_gas",0))+1
            if float(best["after_flash_fee_usd_before_gas"])>float(st.get("best_after_flash_before_gas_usd",0.0)):
                st["best_after_flash_before_gas_usd"]=float(best["after_flash_fee_usd_before_gas"])
                st["best_after_flash_route"]={"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],
                                               "venues":[x["venue"] for x in c["pools"]],"best":best}
            write_jsonl(PROFITABLE,{"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],
                                    "venues":[x["venue"] for x in c["pools"]],"tokens":c["tokens"],
                                    "at":time.time(),"trigger_tx":tx,"block":block,"quotes":rows,"best":best,
                                    "net_profit_verified":False,
                                    "note":"positive after live flash premium; exact execution gas/L1/slippage/atomic simulation still required"})
        elif gross_good:
            best=max(gross_good,key=lambda x:x["gross_edge_bps"])
            write_jsonl(QUOTED,{"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],
                                "venues":[x["venue"] for x in c["pools"]],"tokens":c["tokens"],
                                "at":time.time(),"trigger_tx":tx,"block":block,"quotes":rows,"best":best,
                                "net_profit_verified":False,"note":"gross positive but not positive after live Aave premium"})
    st["quote_budget_used_last_batch"]=used;st["quote_ttl_skipped_last_batch"]=ttl_skipped

def pending_filter():
    return {"topics":[SWAP_TOPICS]}

def wss_pending_loop(st,deadline,q):
    errors=[]
    for url in cfg.get("flashblocks_wss_candidates",[]):
        ws=None; workq=queue.Queue(maxsize=50000); stop_evt=threading.Event(); worker_error=[]
        def consumer():
            while not stop_evt.is_set() or not workq.empty():
                try:first=workq.get(timeout=0.25)
                except queue.Empty:continue
                batch=[first]; end=time.time()+0.12
                while len(batch)<256 and time.time()<end:
                    try:batch.append(workq.get_nowait())
                    except queue.Empty:break
                try:
                    handle_logs_value(st,batch,q,{})
                    st["pool_count"]=db.count_pools()
                    st["last_event_at"]=time.time()
                    st["last_error"]=None
                    save(st)
                except Exception as e:
                    worker_error.append(f"{type(e).__name__}: {e}")
                    st["last_error"]=worker_error[-1];save(st)
        th=None
        try:
            ws=SimpleWebSocket(url,timeout=8).connect()
            ws.send_json({"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["pendingLogs",pending_filter()]})
            ack=json.loads(ws.recv_text())
            if not ack.get("result"):raise RuntimeError("pendingLogs subscription rejected")
            st.update({"connected":True,"feed_mode":"WSS_PENDING_LOGS_VALUE_FIRST_V36","feed_url":url,
                       "subscription_id":ack["result"],"last_error":None,"swap_topic_filtered":True})
            save(st)
            th=threading.Thread(target=consumer,name="flashbot-value-consumer",daemon=True);th.start()
            while not STOP.exists() and (not deadline or time.time()<deadline):
                msg=json.loads(ws.recv_text())
                st["messages"]=int(st.get("messages",0))+1
                if msg.get("method")!="eth_subscription":continue
                lg=((msg.get("params") or {}).get("result") or {})
                if not isinstance(lg,dict):continue
                try:workq.put_nowait(lg)
                except queue.Full:
                    st["feed_dropped_logs"]=int(st.get("feed_dropped_logs",0))+1
            stop_evt.set()
            if th:th.join(timeout=5)
            return True
        except Exception as e:
            errors.append({"url":url,"error":f"{type(e).__name__}: {e}"})
        finally:
            stop_evt.set()
            if th and th.is_alive():th.join(timeout=2)
            if ws:
                try:ws.close()
                except Exception:pass
    st["wss_errors"]=errors;return False

def http_fallback_value(st,deadline,q):
    rpc=RpcClient(cfg["flashblocks_http"],min_interval=float(cfg["fallback"].get("rpc_min_interval_seconds",0.45)))
    st.update({"connected":True,"feed_mode":"HTTP_PENDING_SWAP_LOGS_VALUE_FIRST_V36",
               "feed_url":cfg["flashblocks_http"][0],"last_error":None,"swap_topic_filtered":True})
    save(st)
    seen=set();order=deque();max_seen=int(cfg["fallback"]["max_seen_log_keys"])
    while not STOP.exists() and (not deadline or time.time()<deadline):
        pause=float(cfg["fallback"]["pending_logs_poll_seconds_while_backfill"] if ACTIVE.exists()
                    else cfg["fallback"]["pending_logs_poll_seconds"])
        try:
            logs=rpc.call("eth_getLogs",[{"fromBlock":"pending","toBlock":"pending","topics":[SWAP_TOPICS]}],
                          timeout=15,max_attempts=4) or []
            fresh=[]
            for lg in logs:
                k=((lg.get("transactionHash") or ""),(lg.get("logIndex") or ""),(lg.get("address") or ""))
                if k in seen:continue
                seen.add(k);order.append(k);fresh.append(lg)
                while len(order)>max_seen:seen.discard(order.popleft())
            st["messages"]=int(st.get("messages",0))+1
            st["last_event_at"]=time.time()
            st["pending_logs_last_batch"]=len(logs);st["pending_logs_fresh_batch"]=len(fresh)
            st["pool_count"]=db.count_pools();st["last_error"]=None;st["backfill_active"]=ACTIVE.exists()
            save(st)
            handle_logs_value(st,fresh,q,{})
            st["active_pool_count"]=db.active_count(cfg.get("activity",{}).get("active_window_seconds",3600))
            save(st);time.sleep(pause)
        except Exception as e:
            st["last_error"]=f"{type(e).__name__}: {e}";save(st);time.sleep(min(20,max(2,pause*2)))

ns["handle_logs"]=handle_logs_value
ns["wss_loop"]=wss_pending_loop
ns["http_fallback"]=http_fallback_value

seconds=int(sys.argv[1]) if len(sys.argv)>1 else 0
ns["main"](seconds)
