import hashlib, urllib.request
from pathlib import Path
BASE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/984a788e12f152d22fc1ad99d0a508242730d775/flashbot/releases/v3.9.2/probe.py"
BASE_GIT_BLOB_SHA1="c05aa5ba1e43ee2edc377bded3e160a639ea6211"
raw=urllib.request.urlopen(BASE_URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=BASE_GIT_BLOB_SHA1:raise RuntimeError(f"pinned V3.9.2 probe mismatch: {got}")
src=raw.decode("utf-8")
marker='if len(out)>=6:return out,"backfill_report"'
if src.count(marker)!=2:raise RuntimeError(f"V3.9.3 probe cap markers found {src.count(marker)}")
src=src.replace(marker,'if len(out)>=15:return out,"backfill_report"')
src=src.replace('AAVE_NEAR_LIQUIDATION_DETAIL_V3','AAVE_NEAR_LIQUIDATION_DETAIL_V4')
exec(compile(src,BASE_URL,"exec"),{"__name__":"__main__","__file__":str(Path(__file__).resolve())})
