import json, sys, time
from collections import deque
from pathlib import Path
from ws import SimpleWebSocket
from rpc import RpcClient
from db import DB

ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"settings.json").read_text(encoding="utf-8"))
db=DB(ROOT/cfg["db"])
STATE=ROOT/"daemon_state.json";STOP=ROOT/"STOP_DAEMON";ACTIVE=ROOT/"BACKFILL_ACTIVE"
EVENTS=ROOT/"events.ndjson";STRUCT=ROOT/"candidates.ndjson";QUOTED=ROOT/"quoted_candidates.ndjson"; PROFITABLE=ROOT/"after_flash_candidates.ndjson"

GET_AMOUNT_OUT="f140a35a"
DECIMALS="313ce567"
QUOTE_EXACT_INPUT_SINGLE="c6a5026a"
AAVE_PREMIUM="074b2e43"

def save(o):
    t=STATE.with_suffix(".tmp");t.write_text(json.dumps(o,indent=2),encoding="utf-8");t.replace(STATE)

def word_uint(x):return f"{int(x):064x}"
def word_addr(a):return ("0"*24)+a.lower().removeprefix("0x")
def decode_u256(raw,word=0):
    h=(raw or "0x").removeprefix("0x")
    if len(h)<64*(word+1):raise ValueError("short eth_call result")
    return int(h[word*64:(word+1)*64],16)

class Quoter:
    def __init__(self):
        self.rpc=RpcClient(cfg["flashblocks_http"],min_interval=float(cfg["quote"]["rpc_min_interval_seconds"]))
        self.dec_cache={}
        self.qv2=cfg["contracts"]["uniswap_v3_quoter_v2"]
        self.aave_pool=cfg["contracts"]["aave_pool"]
        self._premium_bps=None
        self._premium_at=0.0
    def premium_bps(self):
        now=time.time()
        ttl=float(cfg["quote"].get("aave_premium_cache_seconds",60))
        if self._premium_bps is None or now-self._premium_at>=ttl:
            raw=self.rpc.call("eth_call",[{"to":self.aave_pool,"data":"0x"+AAVE_PREMIUM},"pending"],timeout=10,max_attempts=5)
            self._premium_bps=decode_u256(raw);self._premium_at=now
        return int(self._premium_bps)
    def decimals(self,token):
        token=token.lower()
        if token in self.dec_cache:return self.dec_cache[token]
        try:
            v=decode_u256(self.rpc.call("eth_call",[{"to":token,"data":"0x"+DECIMALS},"pending"],timeout=10,max_attempts=4))
            if not 0<=v<=36:raise ValueError("bad decimals")
        except Exception:v=18
        self.dec_cache[token]=v;return v
    def one(self,pool,token_in,amount_in):
        venue=pool["venue"];token_in=token_in.lower()
        if token_in==pool["token0"]:token_out=pool["token1"]
        elif token_in==pool["token1"]:token_out=pool["token0"]
        else:raise ValueError("token not in pool")
        if venue=="aerodrome_v2":
            data="0x"+GET_AMOUNT_OUT+word_uint(amount_in)+word_addr(token_in)
            raw=self.rpc.call("eth_call",[{"to":pool["address"],"data":data},"pending"],timeout=12,max_attempts=5)
            return decode_u256(raw),token_out,None
        if venue=="uniswap_v3":
            fee=int(pool.get("param") or 0)
            data="0x"+QUOTE_EXACT_INPUT_SINGLE+word_addr(token_in)+word_addr(token_out)+word_uint(amount_in)+word_uint(fee)+word_uint(0)
            raw=self.rpc.call("eth_call",[{"to":self.qv2,"data":data},"pending"],timeout=15,max_attempts=5)
            return decode_u256(raw),token_out,decode_u256(raw,3)
        raise ValueError("unsupported venue "+venue)

def cycles_from_pool(pool):
    out=[];t0=pool.get("token0");t1=pool.get("token1")
    if not t0 or not t1:return out
    for p2 in db.neighbors(t1):
        if p2["address"]==pool["address"]:continue
        nxt=p2["token1"] if p2["token0"]==t1 else p2["token0"]
        if nxt==t0:
            out.append({"kind":"2pool","pools":[pool,p2],"tokens":[t0,t1,t0]})
            if len(out)>=cfg["quote"]["max_cycles_per_trigger"]:return out
        else:
            for p3 in db.neighbors(nxt,80):
                if p3["address"] in {pool["address"],p2["address"]}:continue
                end=p3["token1"] if p3["token0"]==nxt else p3["token0"]
                if end==t0:
                    out.append({"kind":"triangle","pools":[pool,p2,p3],"tokens":[t0,t1,nxt,t0]})
                    if len(out)>=cfg["quote"]["max_cycles_per_trigger"]:return out
    return out

def rotate_cycle_to_anchor(c,anchor):
    toks=[x.lower() for x in c["tokens"][:-1]]
    anchor=anchor.lower()
    if anchor not in toks:return None
    i=toks.index(anchor); pools=c["pools"]
    rp=pools[i:]+pools[:i]
    rt=toks[i:]+toks[:i]+[anchor]
    return {"kind":c["kind"],"pools":rp,"tokens":rt}

def quote_route_once(q,c,human):
    start=c["tokens"][0].lower()
    anchor=cfg["quote"]["anchor_token"].lower()
    if start!=anchor:return None
    dec=int(cfg["quote"]["anchor_decimals"])
    amount=int(float(human)*(10**dec))
    if amount<=0:return None
    cur=amount;token=start;gas_uni=0;hops=[]
    for pool in c["pools"]:
        if pool["venue"] not in cfg["quote"]["supported_venues"]:return None
        out,next_token,g=q.one(pool,token,cur)
        hops.append({"pool":pool["address"],"venue":pool["venue"],"token_in":token,"amount_in":str(cur),"token_out":next_token,"amount_out":str(out)})
        cur=out;token=next_token.lower();gas_uni += int(g or 0)
    if token!=anchor:return None
    gross=cur-amount;gross_bps=(gross*10000.0/amount) if amount else -1e99
    premium_bps=q.premium_bps();flash_fee=(amount*premium_bps+9999)//10000;after_flash=cur-amount-flash_fee
    return {"human_in":human,"amount_in":str(amount),"amount_out":str(cur),"gross_raw":str(gross),"gross_usd":gross/(10**dec),"gross_edge_bps":gross_bps,"aave_flash_premium_bps":premium_bps,"aave_flash_fee_usd":flash_fee/(10**dec),"after_flash_fee_usd_before_gas":after_flash/(10**dec),"after_flash_fee_bps_before_gas":(after_flash*10000.0/amount) if amount else -1e99,"profitable_after_flash_before_gas":after_flash>0,"gas_estimate_univ3_only":gas_uni,"hops":hops}

def quote_route(q,c):
    anchor=cfg["quote"]["anchor_token"].lower();c=rotate_cycle_to_anchor(c,anchor)
    if not c:return []
    rows=[];seen=set();probe=list(cfg["quote"].get("probe_sizes_human",[]))
    for h in probe:
        try:
            r=quote_route_once(q,c,h)
            if r:rows.append(r);seen.add(float(h))
        except Exception as e:rows.append({"human_in":h,"error":f"{type(e).__name__}: {e}"})
    valid=[r for r in rows if "gross_edge_bps" in r];best=max(valid,key=lambda x:x["gross_edge_bps"]) if valid else None
    if best and best["gross_edge_bps"]>=float(cfg["quote"].get("refine_if_gross_bps_above",-50)):
        for h in cfg["quote"].get("refine_sizes_human",[]):
            if float(h) in seen:continue
            try:
                r=quote_route_once(q,c,h)
                if r:rows.append(r)
            except Exception as e:rows.append({"human_in":h,"error":f"{type(e).__name__}: {e}"})
    return rows

ROUTE_LAST_QUOTED={}
def should_quote_route(key):
    now=time.time();ttl=float(cfg["quote"].get("route_quote_ttl_seconds",15));last=ROUTE_LAST_QUOTED.get(key,0.0)
    if now-last<ttl:return False
    ROUTE_LAST_QUOTED[key]=now
    if len(ROUTE_LAST_QUOTED)>20000:
        cutoff=now-max(60,ttl*4)
        for k,v in list(ROUTE_LAST_QUOTED.items()):
            if v<cutoff:ROUTE_LAST_QUOTED.pop(k,None)
    return True

def handle_logs(st,logs,q,trigger=None):
    touched=[]
    for lg in logs or []:
        st["logs"]+=1;a=(lg.get("address") or "").lower();p=db.pool(a) if a else None
        if p:st["known_pool_hits"]+=1;touched.append(p)
    if not touched:return
    tx=(trigger or {}).get("hash") or (logs[0].get("transactionHash") if logs else None);block=(trigger or {}).get("blockNumber") or (logs[0].get("blockNumber") if logs else None)
    with EVENTS.open("a",encoding="utf-8") as f:f.write(json.dumps({"at":time.time(),"tx":tx,"block":block,"touched":[p["address"] for p in touched]})+"\n")
    seen=set()
    for p in touched:
        for c in cycles_from_pool(p):
            key=tuple(x["address"] for x in c["pools"])
            if key in seen:continue
            seen.add(key);st["structural_candidates"]+=1
            plain={"kind":c["kind"],"pools":[x["address"] for x in c["pools"]],"venues":[x["venue"] for x in c["pools"]],"tokens":c["tokens"],"at":time.time(),"trigger_tx":tx,"block":block}
            with STRUCT.open("a",encoding="utf-8") as f:f.write(json.dumps(plain)+"\n")
            if cfg["quote"]["enabled"] and c["kind"] in ("2pool","triangle") and should_quote_route(key):
                anchored=rotate_cycle_to_anchor(c,cfg["quote"]["anchor_token"])
                if not anchored:continue
                rows=quote_route(q,anchored);st["quote_attempts"]+=1
                gross_good=[r for r in rows if "gross_edge_bps" in r and r["gross_edge_bps"]>=cfg["quote"]["min_gross_edge_bps"]];after_good=[r for r in rows if r.get("profitable_after_flash_before_gas")]
                if gross_good:st["gross_positive_candidates"]+=1
                if after_good:
                    best=max(after_good,key=lambda x:x["after_flash_fee_usd_before_gas"]);st["positive_after_flash_before_gas"]+=1;st["best_after_flash_before_gas_usd"]=max(float(st.get("best_after_flash_before_gas_usd",0.0)),float(best["after_flash_fee_usd_before_gas"]))
                    rec=dict(plain);rec.update({"quotes":rows,"best":best,"net_profit_verified":False,"note":"DEX exact pending-state quote + live Aave premium applied; execution gas/L1/slippage/atomic simulation still required"})
                    with PROFITABLE.open("a",encoding="utf-8") as f:f.write(json.dumps(rec)+"\n")
                elif gross_good:
                    best=max(gross_good,key=lambda x:x["gross_edge_bps"]);rec=dict(plain);rec.update({"quotes":rows,"best":best,"net_profit_verified":False,"note":"gross positive but not positive after live Aave flash premium; gas not yet applied"})
                    with QUOTED.open("a",encoding="utf-8") as f:f.write(json.dumps(rec)+"\n")

def wss_loop(st,deadline,q):
    errors=[]
    for url in cfg.get("flashblocks_wss_candidates",[]):
        ws=None
        try:
            ws=SimpleWebSocket(url,timeout=8).connect();ws.send_json({"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["newFlashblockTransactions",True]});ack=json.loads(ws.recv_text())
            if not ack.get("result"):raise RuntimeError("subscription rejected")
            st.update({"connected":True,"feed_mode":"WSS_NEW_FLASHBLOCK_TRANSACTIONS","feed_url":url,"subscription_id":ack["result"],"last_error":None});save(st)
            while not STOP.exists() and (not deadline or time.time()<deadline):
                msg=json.loads(ws.recv_text());st["messages"]+=1
                if msg.get("method")!="eth_subscription":continue
                tx=((msg.get("params") or {}).get("result") or {})
                if not isinstance(tx,dict):continue
                st["txs"]+=1;st["last_event_at"]=time.time();handle_logs(st,tx.get("logs") or [],q,tx)
                if st["txs"]%20==0:st["pool_count"]=db.count_pools();save(st)
            return True
        except Exception as e:errors.append({"url":url,"error":f"{type(e).__name__}: {e}"})
        finally:
            if ws:
                try:ws.close()
                except Exception:pass
    st["wss_errors"]=errors;return False

def http_fallback(st,deadline,q):
    rpc=RpcClient(cfg["flashblocks_http"],min_interval=0.9);st.update({"connected":True,"feed_mode":"HTTP_PENDING_LOGS_FALLBACK","feed_url":cfg["flashblocks_http"][0],"last_error":None});save(st)
    seen=set();order=deque();max_seen=int(cfg["fallback"]["max_seen_log_keys"])
    while not STOP.exists() and (not deadline or time.time()<deadline):
        pause=float(cfg["fallback"]["pending_logs_poll_seconds_while_backfill"] if ACTIVE.exists() else cfg["fallback"]["pending_logs_poll_seconds"])
        try:
            logs=rpc.call("eth_getLogs",[{"fromBlock":"pending","toBlock":"pending"}],timeout=15,max_attempts=5) or [];fresh=[]
            for lg in logs:
                k=((lg.get("transactionHash") or ""),(lg.get("logIndex") or ""),(lg.get("address") or ""))
                if k in seen:continue
                seen.add(k);order.append(k);fresh.append(lg)
                while len(order)>max_seen:seen.discard(order.popleft())
            st["messages"]+=1;st["last_event_at"]=time.time();handle_logs(st,fresh,q,{});st["pool_count"]=db.count_pools();st["last_error"]=None;st["backfill_active"]=ACTIVE.exists();save(st);time.sleep(pause)
        except Exception as e:st["last_error"]=f"{type(e).__name__}: {e}";save(st);time.sleep(min(20,max(3,pause*2)))

def main(seconds=0):
    try:STOP.unlink()
    except FileNotFoundError:pass
    q=Quoter();st={"ok":True,"version":cfg["version"],"mode":cfg["mode"],"started_at":time.time(),"connected":False,"feed_mode":None,"messages":0,"txs":0,"logs":0,"known_pool_hits":0,"structural_candidates":0,"quote_attempts":0,"gross_positive_candidates":0,"positive_after_flash_before_gas":0,"best_after_flash_before_gas_usd":0.0,"profit_target_usd":float(cfg["risk"].get("profit_target_usd",10000)),"pool_count":db.count_pools(),"last_error":None,"last_event_at":None}
    save(st);deadline=time.time()+seconds if seconds else None
    while not STOP.exists() and (not deadline or time.time()<deadline):
        if not wss_loop(st,deadline,q):http_fallback(st,deadline,q)
        if not STOP.exists() and (not deadline or time.time()<deadline):time.sleep(2)
    st["connected"]=False;st["stopped_at"]=time.time();save(st);print(json.dumps(st,indent=2))
if __name__=="__main__":main(int(sys.argv[1]) if len(sys.argv)>1 else 0)
