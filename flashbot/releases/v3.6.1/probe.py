import importlib.util, json, socket, ssl, time
from pathlib import Path
from ws import SimpleWebSocket
from rpc import RpcClient

ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"settings.json").read_text(encoding="utf-8"))
topics=[[cfg["events"]["v3_swap"],cfg["events"]["aerodrome_v2_swap"]]]
SUB={"jsonrpc":"2.0","id":1,"method":"eth_subscribe","params":["pendingLogs",{"topics":topics}]}
report={"ok":False,"type":"V3_6_1_WSS_DIAG","engine_version":cfg["version"],"libraries":{},"dns":{},"native_variants":[],"websocket_client":{},"websockets_sync":{},"http_pending_swap_logs":{},"simulate_v1":{},"timestamp":time.time()}

for name in ("websocket","websockets"):
    try:
        spec=importlib.util.find_spec(name)
        report["libraries"][name]={"available":bool(spec),"origin":getattr(spec,"origin",None) if spec else None}
    except Exception as e:
        report["libraries"][name]={"available":False,"error":f"{type(e).__name__}: {e}"}

try:
    infos=socket.getaddrinfo("mainnet-preconf.base.org",443,type=socket.SOCK_STREAM)
    report["dns"]={"ok":True,"addresses":list(dict.fromkeys(x[4][0] for x in infos))[:8]}
except Exception as e:
    report["dns"]={"ok":False,"error":f"{type(e).__name__}: {e}"}

for origin in (None,"https://docs.base.org","https://mainnet-preconf.base.org"):
    item={"url":"wss://mainnet-preconf.base.org","origin":origin,"ok":False}
    ws=None
    try:
        ws=SimpleWebSocket(item["url"],timeout=6,origin=origin).connect()
        ws.send_json(SUB)
        ack=json.loads(ws.recv_text())
        if not ack.get("result"):raise RuntimeError("pendingLogs subscription rejected: "+json.dumps(ack))
        item["ok"]=True; item["subscription_id"]=ack["result"]
    except Exception as e:
        item["error"]=f"{type(e).__name__}: {e}"
        if ws:
            item["status"]=ws.handshake_status; item["headers"]=ws.handshake_headers
    finally:
        if ws:
            try:ws.close()
            except Exception:pass
    report["native_variants"].append(item)

if report["libraries"].get("websocket",{}).get("available"):
    w=None
    try:
        import websocket
        w=websocket.create_connection("wss://mainnet-preconf.base.org",timeout=6,suppress_origin=True)
        w.send(json.dumps(SUB,separators=(",",":")))
        ack=json.loads(w.recv())
        if not ack.get("result"):raise RuntimeError("subscription rejected: "+json.dumps(ack))
        report["websocket_client"]={"ok":True,"subscription_id":ack["result"],"version":getattr(websocket,"__version__",None)}
    except Exception as e:
        report["websocket_client"]={"ok":False,"error":f"{type(e).__name__}: {e}"}
    finally:
        if w:
            try:w.close()
            except Exception:pass

if report["libraries"].get("websockets",{}).get("available"):
    try:
        from websockets.sync.client import connect
        with connect("wss://mainnet-preconf.base.org",open_timeout=6,close_timeout=1,origin=None) as w:
            w.send(json.dumps(SUB,separators=(",",":")))
            ack=json.loads(w.recv(timeout=6))
            if not ack.get("result"):raise RuntimeError("subscription rejected: "+json.dumps(ack))
            import websockets
            report["websockets_sync"]={"ok":True,"subscription_id":ack["result"],"version":getattr(websockets,"__version__",None)}
    except Exception as e:
        report["websockets_sync"]={"ok":False,"error":f"{type(e).__name__}: {e}"}

try:
    rpc=RpcClient(cfg["flashblocks_http"],min_interval=0.55)
    samples=[]
    for _ in range(3):
        logs=rpc.call("eth_getLogs",[{"fromBlock":"pending","toBlock":"pending","topics":topics}],timeout=15,max_attempts=4) or []
        samples.append(len(logs)); time.sleep(0.35)
    report["http_pending_swap_logs"]={"ok":True,"samples":samples}
except Exception as e:
    report["http_pending_swap_logs"]={"ok":False,"error":f"{type(e).__name__}: {e}"}

try:
    rpc=RpcClient(cfg["flashblocks_http"],min_interval=0.5)
    payload={"blockStateCalls":[{"calls":[{"to":cfg["quote"]["anchor_token"],"data":"0x313ce567"}],"stateOverrides":{}}],
             "traceTransfers":False,"validation":False}
    sim=rpc.call("eth_simulateV1",[payload,"pending"],timeout=20,max_attempts=3)
    call=((sim or [{}])[0].get("calls") or [{}])[0]
    report["simulate_v1"]={"ok":call.get("status")=="0x1","status":call.get("status"),"gasUsed":call.get("gasUsed"),
                           "returnData":call.get("returnData"),"error":call.get("error")}
except Exception as e:
    report["simulate_v1"]={"ok":False,"error":f"{type(e).__name__}: {e}"}

report["wss_any_ok"]=any(x.get("ok") for x in report["native_variants"]) or report["websocket_client"].get("ok",False) or report["websockets_sync"].get("ok",False)
report["ok"]=report["wss_any_ok"] or report["http_pending_swap_logs"].get("ok",False)
(ROOT/"probe_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
raise SystemExit(0 if report["ok"] else 4)
