import json, sys, time
from collections import deque
from pathlib import Path
from ws import SimpleWebSocket
from rpc import RpcClient
from db import DB

ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"settings.json").read_text(encoding="utf-8"))
db=DB(ROOT/cfg["db"])
STATE=ROOT/"daemon_state.json"; STOP=ROOT/"STOP_DAEMON"; EVENTS=ROOT/"events.ndjson"; CANDS=ROOT/"candidates.ndjson"

def save(o):
    t=STATE.with_suffix(".tmp");t.write_text(json.dumps(o,indent=2),encoding="utf-8");t.replace(STATE)

def cycles_from_pool(pool):
    out=[];t0=pool.get("token0");t1=pool.get("token1")
    if not t0 or not t1:return out
    for p2 in db.neighbors(t1):
        nxt=p2["token1"] if p2["token0"]==t1 else p2["token0"]
        if nxt==t0 and p2["address"]!=pool["address"]:
            out.append({"kind":"2pool","pools":[pool["address"],p2["address"]],"tokens":[t0,t1,t0]})
        else:
            for p3 in db.neighbors(nxt,80):
                end=p3["token1"] if p3["token0"]==nxt else p3["token0"]
                if end==t0 and len({pool["address"],p2["address"],p3["address"]})==3:
                    out.append({"kind":"triangle","pools":[pool["address"],p2["address"],p3["address"]],"tokens":[t0,t1,nxt,t0]})
                    if len(out)>=30:return out
    return out

def handle_logs(st,logs,trigger=None):
    touched=[]
    for lg in logs or []:
        st["logs"]+=1
        a=(lg.get("address") or "").lower(); p=db.pool(a) if a else None
        if p:st["known_pool_hits"]+=1;touched.append(p)
    if not touched:return
    tx=(trigger or {}).get("hash") or (logs[0].get("transactionHash") if logs else None)
    block=(trigger or {}).get("blockNumber") or (logs[0].get("blockNumber") if logs else None)
    with EVENTS.open("a",encoding="utf-8") as f:f.write(json.dumps({"at":time.time(),"tx":tx,"block":block,"touched":[p["address"] for p in touched]})+"\n")
    seen=set()
    for p in touched:
        for c in cycles_from_pool(p):
            k=tuple(c["pools"])
            if k in seen:continue
            seen.add(k);st["structural_candidates"]+=1;c.update({"at":time.time(),"trigger_tx":tx,"block":block})
            with CANDS.open("a",encoding="utf-8") as f:f.write(json.dumps(c)+"\n")

def wss_loop(st,deadline):
    errors=[]
    for url in cfg.get("flashblocks_wss_candidates",[]):
        ws=None
        try:
            ws=SimpleWebSocket(url,timeout=8).connect();ws.send_json({"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["newFlashblockTransactions",True]})
            ack=json.loads(ws.recv_text())
            if not ack.get("result"):raise RuntimeError("subscription rejected: "+json.dumps(ack)[:500])
            st.update({"connected":True,"feed_mode":"WSS_NEW_FLASHBLOCK_TRANSACTIONS","feed_url":url,"subscription_id":ack["result"],"last_error":None});save(st)
            while not STOP.exists() and (not deadline or time.time()<deadline):
                msg=json.loads(ws.recv_text());st["messages"]+=1
                if msg.get("method")!="eth_subscription":continue
                tx=((msg.get("params") or {}).get("result") or {})
                if not isinstance(tx,dict):continue
                st["txs"]+=1;st["last_event_at"]=time.time();handle_logs(st,tx.get("logs") or [],tx)
                if st["txs"]%20==0:st["pool_count"]=db.count_pools();save(st)
            return True
        except Exception as e:errors.append({"url":url,"error":f"{type(e).__name__}: {e}"})
        finally:
            if ws:
                try:ws.close()
                except Exception:pass
    st["wss_errors"]=errors;return False

def http_fallback(st,deadline):
    rpc=RpcClient(cfg["flashblocks_http"],min_interval=max(0.7,float(cfg["fallback"]["pending_logs_poll_seconds"])*0.7))
    st.update({"connected":True,"feed_mode":"HTTP_PENDING_LOGS_FALLBACK","feed_url":cfg["flashblocks_http"][0],"last_error":None});save(st)
    seen=set();order=deque();max_seen=int(cfg["fallback"].get("max_seen_log_keys",30000));pause=float(cfg["fallback"]["pending_logs_poll_seconds"])
    while not STOP.exists() and (not deadline or time.time()<deadline):
        try:
            logs=rpc.call("eth_getLogs",[{"fromBlock":"pending","toBlock":"pending"}],timeout=15,max_attempts=6) or []
            fresh=[]
            for lg in logs:
                k=((lg.get("transactionHash") or ""),(lg.get("logIndex") or ""),(lg.get("address") or ""))
                if k in seen:continue
                seen.add(k);order.append(k);fresh.append(lg)
                while len(order)>max_seen:seen.discard(order.popleft())
            st["messages"]+=1;st["last_event_at"]=time.time();handle_logs(st,fresh,{})
            st["pool_count"]=db.count_pools();st["last_error"]=None;save(st);time.sleep(pause)
        except Exception as e:
            st["last_error"]=f"{type(e).__name__}: {e}";save(st);time.sleep(min(15,max(2,pause*3)))

def main(seconds=0):
    try:STOP.unlink()
    except FileNotFoundError:pass
    st={"ok":True,"version":cfg["version"],"mode":cfg["mode"],"started_at":time.time(),"connected":False,"feed_mode":None,
        "messages":0,"txs":0,"logs":0,"known_pool_hits":0,"structural_candidates":0,"pool_count":db.count_pools(),"last_error":None,"last_event_at":None}
    save(st);deadline=time.time()+seconds if seconds else None
    while not STOP.exists() and (not deadline or time.time()<deadline):
        if not wss_loop(st,deadline):http_fallback(st,deadline)
        if not STOP.exists() and (not deadline or time.time()<deadline):time.sleep(2)
    st["connected"]=False;st["stopped_at"]=time.time();save(st);print(json.dumps(st,indent=2))
if __name__=="__main__":main(int(sys.argv[1]) if len(sys.argv)>1 else 0)
