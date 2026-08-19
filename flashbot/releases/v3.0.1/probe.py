import json, time
from pathlib import Path
from ws import SimpleWebSocket
from rpc import RpcClient

ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"settings.json").read_text(encoding="utf-8"))
report={"ok":False,"type":"V3_PROBE","version":cfg["version"],"wss":[],"http_pending_logs":{},"timestamp":time.time()}

for url in cfg.get("flashblocks_wss_candidates",[]):
    item={"url":url,"ok":False,"events":0}
    ws=None
    try:
        ws=SimpleWebSocket(url,timeout=6).connect()
        ws.send_json({"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["newFlashblockTransactions",True]})
        ack=json.loads(ws.recv_text()); item["ack"]=ack
        if not ack.get("result"): raise RuntimeError("subscription rejected")
        end=time.time()+3.0
        while time.time()<end and item["events"]<2:
            msg=json.loads(ws.recv_text())
            if msg.get("method")=="eth_subscription":item["events"]+=1
        item["ok"]=item["events"]>0
    except Exception as e:item["error"]=f"{type(e).__name__}: {e}"
    finally:
        if ws:
            try:ws.close()
            except Exception:pass
    report["wss"].append(item)
    if item["ok"]:break

try:
    rpc=RpcClient(cfg["flashblocks_http"],min_interval=0.7)
    samples=[]
    for _ in range(2):
        logs=rpc.call("eth_getLogs",[{"fromBlock":"pending","toBlock":"pending"}],timeout=15,max_attempts=4)
        samples.append(len(logs or [])); time.sleep(0.8)
    report["http_pending_logs"]={"ok":True,"samples":samples}
except Exception as e:
    report["http_pending_logs"]={"ok":False,"error":f"{type(e).__name__}: {e}"}

report["ok"]=any(x.get("ok") for x in report["wss"]) or report["http_pending_logs"].get("ok",False)
(ROOT/"probe_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
raise SystemExit(0 if report["ok"] else 4)
