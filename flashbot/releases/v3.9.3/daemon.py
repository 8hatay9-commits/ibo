import hashlib, urllib.request
from pathlib import Path
BASE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/984a788e12f152d22fc1ad99d0a508242730d775/flashbot/releases/v3.9.2/daemon.py"
BASE_GIT_BLOB_SHA1="d6dd6e663cb421db773f820c3612c62092cf74c9"
raw=urllib.request.urlopen(BASE_URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=BASE_GIT_BLOB_SHA1:raise RuntimeError(f"pinned V3.9.2 daemon mismatch: {got}")
src=raw.decode("utf-8")
if "FLASHBOT-PRODUCTION-V3.9.2" not in src or "FLASHBOT-SUPERVISOR-V3.9.2" not in src:raise RuntimeError("V3.9.3 daemon version markers not found")
src=src.replace("FLASHBOT-PRODUCTION-V3.9.2","FLASHBOT-PRODUCTION-V3.9.3").replace("FLASHBOT-SUPERVISOR-V3.9.2","FLASHBOT-SUPERVISOR-V3.9.3")
exec(compile(src,BASE_URL,"exec"),{"__name__":"__main__","__file__":str(Path(__file__).resolve())})
