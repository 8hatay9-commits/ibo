
import json, time
from pathlib import Path
from ws import SimpleWebSocket
from rpc import RpcClient

ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"settings.json").read_text(encoding="utf-8"))
report={"ok":False,"type":"V3_1_PROBE","version":cfg["version"],"wss":[],"http_pending_logs":{},"timestamp":time.time()}

for url in cfg.get("flashblocks_wss_candidates",[]):
    item={"url":url,"ok":False,"events":0}
    ws=None
    try:
        ws=SimpleWebSocket(url,timeout=5).connect()
        ws.send_json({"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["newFlashblockTransactions",True]})
        ack=json.loads(ws.recv_text())
        if not ack.get("result"):raise RuntimeError("subscription rejected")
        item["ok"]=True;item["subscription_id"]=ack["result"]
    except Exception as e:item["error"]=f"{type(e).__name__}: {e}"
    finally:
        if ws:
            try:ws.close()
            except Exception:pass
    report["wss"].append(item)
    if item["ok"]:break

try:
    rpc=RpcClient(cfg["flashblocks_http"],min_interval=0.8)
    samples=[]
    for _ in range(2):
        logs=rpc.call("eth_getLogs",[{"fromBlock":"pending","toBlock":"pending"}],timeout=15,max_attempts=4) or []
        samples.append(len(logs));time.sleep(0.8)
    report["http_pending_logs"]={"ok":True,"samples":samples}
except Exception as e:
    report["http_pending_logs"]={"ok":False,"error":f"{type(e).__name__}: {e}"}

report["ok"]=any(x.get("ok") for x in report["wss"]) or report["http_pending_logs"].get("ok",False)
(ROOT/"probe_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
raise SystemExit(0 if report["ok"] else 4)
