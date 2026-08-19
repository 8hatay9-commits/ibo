
import json, time, urllib.request, urllib.error
from pathlib import Path

class RpcError(RuntimeError): pass

class RpcClient:
    def __init__(self, urls, min_interval=0.4):
        self.urls=list(urls)
        self.min_interval=float(min_interval)
        self._last=0.0
        self._id=0

    def _wait(self):
        d=self.min_interval-(time.monotonic()-self._last)
        if d>0: time.sleep(d)

    def call(self, method, params=None, timeout=20, max_attempts=8):
        params=params or []
        last=None
        for attempt in range(max_attempts):
            url=self.urls[attempt % len(self.urls)]
            self._wait()
            self._id += 1
            body=json.dumps({"jsonrpc":"2.0","id":self._id,"method":method,"params":params}).encode()
            req=urllib.request.Request(url,data=body,headers={
                "Content-Type":"application/json","User-Agent":"FlashbotProductionV3"
            })
            try:
                with urllib.request.urlopen(req,timeout=timeout) as r:
                    raw=r.read()
                self._last=time.monotonic()
                obj=json.loads(raw.decode())
                if obj.get("error"):
                    msg=json.dumps(obj["error"],ensure_ascii=False)
                    if any(x in msg.lower() for x in ("rate","limit","too many","busy","timeout")):
                        time.sleep(min(30,1.5*(2**attempt)))
                        last=RpcError(msg); continue
                    raise RpcError(msg)
                return obj.get("result")
            except urllib.error.HTTPError as e:
                self._last=time.monotonic()
                last=e
                if e.code in (429,408,500,502,503,504):
                    retry_after=e.headers.get("Retry-After")
                    try: delay=float(retry_after)
                    except Exception: delay=min(30,1.5*(2**attempt))
                    time.sleep(max(1.0,delay))
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                self._last=time.monotonic()
                last=e
                time.sleep(min(20,1.0*(2**attempt)))
        raise RpcError(f"{method} failed after retries: {last!r}")

def hexint(x):
    return int(x,16) if isinstance(x,str) and x.startswith("0x") else int(x)

def addr_from_topic(t):
    h=t.lower().removeprefix("0x")
    return "0x"+h[-40:]

def addr_from_word(w):
    h=w.lower().removeprefix("0x")
    return "0x"+h[-40:]

def words(data):
    h=(data or "0x").removeprefix("0x")
    return [h[i:i+64] for i in range(0,len(h),64) if len(h[i:i+64])==64]
