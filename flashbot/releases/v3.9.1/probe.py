import hashlib, urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/8hatay9-commits/ibo/ad31b08280dbea26ad68454a3d45c20fe3cdaf48/flashbot/releases/v3.9.0/probe.py"
BASE_GIT_BLOB_SHA1 = "c9753aae966e7ca615feb0ee370131dbfd3de8ae"

raw = urllib.request.urlopen(BASE_URL, timeout=30).read()
got = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
if got != BASE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.9.0 probe mismatch: {got}")
src = raw.decode("utf-8")

old = 'U=["0x6a2cc7efa2c5d91c45411d956358928158262a19","0x9f9ff4ffdf0b16dd096f649586e882d88a9bf1c0","0xfeee2af72cd54577526a3e8a6508a9d8d0942fb8"]'
new = '''DEFAULT_U=["0x6a2cc7efa2c5d91c45411d956358928158262a19","0x9f9ff4ffdf0b16dd096f649586e882d88a9bf1c0","0xfeee2af72cd54577526a3e8a6508a9d8d0942fb8"]
def dynamic_targets():
 out=[];src="fallback_static"
 try:
  p=R/"backfill_report.json"
  if p.exists():
   b=json.loads(p.read_text())
   for key in ("liquidatable_now","lowest_live","lowest_discovered"):
    for row in b.get(key) or []:
     u=(row.get("user") or "").lower()
     if len(u)==42 and u.startswith("0x") and u not in out:out.append(u)
     if len(out)>=6:return out,"backfill_report"
   for u in b.get("targets") or []:
    u=(u or "").lower()
    if len(u)==42 and u.startswith("0x") and u not in out:out.append(u)
    if len(out)>=6:return out,"backfill_report"
   if out:src="backfill_report"
 except Exception:pass
 return (out or DEFAULT_U),src
U,TARGET_SOURCE=dynamic_targets()'''
if old not in src:
    raise RuntimeError("V3.9.1 probe target marker not found")
src = src.replace(old, new, 1)

old = 't=time.monotonic();q={"ok":False,"type":"AAVE_NEAR_LIQUIDATION_DETAIL_V2","targets":U,"positions":{},"errors":[]}'
new = 't=time.monotonic();q={"ok":False,"type":"AAVE_NEAR_LIQUIDATION_DETAIL_V3","targets":U,"target_source":TARGET_SOURCE,"positions":{},"errors":[]}'
if old not in src:
    raise RuntimeError("V3.9.1 probe report marker not found")
src = src.replace(old, new, 1)

exec(compile(src, BASE_URL, "exec"), {"__name__":"__main__", "__file__":str(Path(__file__).resolve())})
