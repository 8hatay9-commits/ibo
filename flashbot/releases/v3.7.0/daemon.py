import hashlib, json, queue, sys, threading, time, urllib.request
from collections import deque

CORE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/46012d49d9d8f737fa936ef42443dc354d06e589/flashbot/releases/v3.6.0/daemon.py"
CORE_GIT_BLOB_SHA1="4ad96990f9b97cbf752f334f51213ed53d713053"
raw=urllib.request.urlopen(CORE_URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=CORE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.6 daemon mismatch: {got}")
src=raw.decode("utf-8")
marker='\nseconds=int(sys.argv[1]) if len(sys.argv)>1 else 0\nns["main"](seconds)'
if marker not in src:
    raise RuntimeError("V3.6 daemon start marker not found")
src=src.rsplit(marker,1)[0]
v={"__name__":"flashbot_v36_core","__file__":__file__}
exec(compile(src,CORE_URL,"exec"),v)

core=v["ns"]; cfg=v["cfg"]; db=v["db"]; RpcClient=v["RpcClient"]
STOP=v["STOP"]; ACTIVE=v["ACTIVE"]; save=v["save"]
word_addr=v["word_addr"]; word_uint=v["word_uint"]; decode_u256=v["decode_u256"]
cfg["version"]="FLASHBOT-PRODUCTION-V3.7.0"
qcfg=cfg["quote"]
qcfg["supported_venues"]=list(dict.fromkeys(list(qcfg.get("supported_venues") or [])+["pancakeswap_v3"]))
qcfg["quote_budget_per_batch"]=16
qcfg["route_quote_ttl_seconds"]=30
cfg["risk"]["profit_target_usd"]=10000

PANCAKE_QV2="0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997"
PANCAKE_FACTORY="0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"
QUOTE_EXACT_INPUT_SINGLE="c6a5026a"
GAS_ORACLE="0x420000000000000000000000000000000000000F"
L1_FEE_UPPER="f1c7a58b"
USDC=qcfg["anchor_token"].lower()
WETH="0x4200000000000000000000000000000000000006"
WETH_USDC_POOL="0xb4cb800910b228ed3d0834cf79d697127bbb00e5"

_orig_one=core["Quoter"].one
def _one_v37(self,pool,token_in,amount_in):
    if pool.get("venue")!="pancakeswap_v3":
        return _orig_one(self,pool,token_in,amount_in)
    token_in=token_in.lower()
    if token_in==pool["token0"]: token_out=pool["token1"]
    elif token_in==pool["token1"]: token_out=pool["token0"]
    else: raise ValueError("token not in pancake pool")
    fee=int(pool.get("param") or 0)
    if fee<=0: raise ValueError("bad pancake fee")
    data="0x"+QUOTE_EXACT_INPUT_SINGLE+word_addr(token_in)+word_addr(token_out)+word_uint(amount_in)+word_uint(fee)+word_uint(0)
    rawq=self.rpc.call("eth_call",[{"to":PANCAKE_QV2,"data":data},"pending"],timeout=15,max_attempts=5)
    return decode_u256(rawq),token_out,decode_u256(rawq,3)
core["Quoter"].one=_one_v37

_cost_cache={"eth_usd":None,"eth_usd_at":0.0}
def _eth_usd(q):
    now=time.time()
    if _cost_cache["eth_usd"] and now-_cost_cache["eth_usd_at"]<15:
        return _cost_cache["eth_usd"]
    px=None
    try:
        p=db.pool(WETH_USDC_POOL)
        if p:
            out,tok,_=q.one(p,WETH,10**18)
            if tok.lower()==USDC and out>0:
                px=float(out)/1e6
    except Exception:
        px=None
    if not px or not (100.0 < px < 100000.0):
        px=10000.0
    _cost_cache["eth_usd"]=px; _cost_cache["eth_usd_at"]=now
    return px

_orig_quote_route=v["quote_route"]
def _quote_route_v37(q,c):
    rows=_orig_quote_route(q,c)
    hops=len(c.get("pools") or [])
    for r in rows:
        if "gross_edge_bps" not in r: continue
        raw_positive=bool(r.get("profitable_after_flash_before_gas"))
        r["positive_after_flash_before_gas_raw"]=raw_positive
        r["profit_gate"]="V37_CONSERVATIVE_L1_L2_ESTIMATE"
        if not raw_positive:
            r["profitable_after_flash_before_gas"]=False
            continue
        try:
            quoted_gas=int(r.get("gas_estimate_univ3_only") or 0)
            exec_gas=max(180000+80000*hops, int(quoted_gas*1.25)+120000)
            gp=q.rpc.call("eth_gasPrice",[],timeout=10,max_attempts=4)
            gas_price=int(gp,16) if isinstance(gp,str) else int(gp)
            tx_size=700+96*hops
            l1raw=q.rpc.call("eth_call",[{"to":GAS_ORACLE,"data":"0x"+L1_FEE_UPPER+word_uint(tx_size)},"pending"],timeout=10,max_attempts=4)
            l1wei=decode_u256(l1raw)
            ethusd=_eth_usd(q)
            l2usd=(exec_gas*gas_price/1e18)*ethusd
            l1usd=(l1wei/1e18)*ethusd
            before=float(r.get("after_flash_fee_usd_before_gas") or 0.0)
            safety=max(0.05,0.25*(l1usd+l2usd))
            net=before-l1usd-l2usd-safety
            r.update({
                "estimated_execution_gas_v37":exec_gas,
                "gas_price_wei_v37":gas_price,
                "estimated_l2_fee_usd_v37":l2usd,
                "estimated_l1_fee_upper_usd_v37":l1usd,
                "eth_usd_for_cost_v37":ethusd,
                "safety_buffer_usd_v37":safety,
                "estimated_net_after_all_costs_usd_v37":net,
                "estimated_tx_size_v37":tx_size,
                "profitable_after_flash_before_gas":net>0
            })
        except Exception as e:
            r["cost_gate_error_v37"]=f"{type(e).__name__}: {e}"
            r["profitable_after_flash_before_gas"]=False
    return rows
v["quote_route"]=_quote_route_v37

def _wss_disabled(st,deadline,q):
    st["wss_errors"]=[{"url":"wss://mainnet-preconf.base.org","error":"disabled_after_V3_6_1_diag_cloudflare_405"}]
    st["wss_diag"]="V3.6.1 confirmed Cloudflare HTTP 405 for all Origin variants on this host/IP"
    return False

def _http_adaptive_v37(st,deadline,q):
    feed=RpcClient(cfg["flashblocks_http"],min_interval=0.08)
    st.update({"connected":True,"feed_mode":"HTTP_PENDING_SWAP_LOGS_ADAPTIVE_DECOUPLED_V37",
               "feed_url":cfg["flashblocks_http"][0],"last_error":None,"swap_topic_filtered":True,
               "pancakeswap_v3_enabled":True,"cost_gate":"V37_CONSERVATIVE_L1_L2_ESTIMATE"})
    save(st)
    seen=set(); order=deque(); max_seen=int(cfg["fallback"]["max_seen_log_keys"])
    workq=queue.Queue(maxsize=256); stop_evt=threading.Event()
    target=0.24; last_save=0.0

    def worker():
        while not stop_evt.is_set() or not workq.empty():
            try: batch=workq.get(timeout=0.2)
            except queue.Empty: continue
            merged=[]
            merged.extend(batch)
            for _ in range(7):
                try: merged.extend(workq.get_nowait())
                except queue.Empty: break
            try:
                v["handle_logs_value"](st,merged,q,{})
                st["active_pool_count"]=db.active_count(cfg.get("activity",{}).get("active_window_seconds",3600))
                st["worker_last_batch_logs_v37"]=len(merged)
                st["last_error"]=None
                save(st)
            except Exception as e:
                st["worker_error_v37"]=f"{type(e).__name__}: {e}"
                st["last_error"]=st["worker_error_v37"]; save(st)

    th=threading.Thread(target=worker,name="flashbot-v37-quote-worker",daemon=True); th.start()
    try:
        while not STOP.exists() and (not deadline or time.time()<deadline):
            started=time.monotonic()
            try:
                logs=feed.call("eth_getLogs",[{"fromBlock":"pending","toBlock":"pending","topics":[v["SWAP_TOPICS"]]}],
                               timeout=10,max_attempts=3) or []
                latency=time.monotonic()-started
                fresh=[]
                for lg in logs:
                    k=((lg.get("transactionHash") or ""),(lg.get("logIndex") or ""),(lg.get("address") or ""))
                    if k in seen: continue
                    seen.add(k); order.append(k); fresh.append(lg)
                    while len(order)>max_seen: seen.discard(order.popleft())
                if fresh:
                    try: workq.put_nowait(fresh)
                    except queue.Full:
                        st["feed_dropped_batches_v37"]=int(st.get("feed_dropped_batches_v37",0))+1
                st["messages"]=int(st.get("messages",0))+1
                st["last_event_at"]=time.time()
                st["pending_logs_last_batch"]=len(logs); st["pending_logs_fresh_batch"]=len(fresh)
                st["pool_count"]=db.count_pools(); st["backfill_active"]=ACTIVE.exists()
                st["feed_queue_depth_v37"]=workq.qsize()
                st["feed_rpc_latency_ms_v37"]=round(latency*1000,2)
                if latency<0.40: target=max(0.22,target*0.96)
                elif latency>0.90: target=min(1.20,target*1.20)
                st["feed_poll_target_ms_v37"]=round(target*1000,1)
                st["last_error"]=None
                now=time.monotonic()
                if now-last_save>=0.5:
                    save(st); last_save=now
                elapsed=time.monotonic()-started
                if elapsed<target: time.sleep(target-elapsed)
            except Exception as e:
                st["last_error"]=f"{type(e).__name__}: {e}"
                target=min(2.0,max(0.35,target*1.5))
                st["feed_poll_target_ms_v37"]=round(target*1000,1)
                save(st); time.sleep(target)
    finally:
        stop_evt.set(); th.join(timeout=5)

core["wss_loop"]=_wss_disabled
core["http_fallback"]=_http_adaptive_v37

seconds=int(sys.argv[1]) if len(sys.argv)>1 else 0
core["main"](seconds)
