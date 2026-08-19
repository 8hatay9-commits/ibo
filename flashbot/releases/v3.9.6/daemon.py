import hashlib, urllib.request
from pathlib import Path

URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/ce7215c79695c4ab732a8973bd9fe5201b019597/flashbot/releases/v3.9.5/daemon.py"
BLOB_SHA1="f2ec0dcf6205a54f0f8d14228190e62aaf6254f1"

raw=urllib.request.urlopen(URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=BLOB_SHA1:
    raise RuntimeError(f"pinned V3.9.5 daemon mismatch: {got}")

src=raw.decode("utf-8")
src=src.replace("FLASHBOT-PRODUCTION-V3.9.5","FLASHBOT-PRODUCTION-V3.9.6")
src=src.replace("FLASHBOT-SUPERVISOR-V3.9.5","FLASHBOT-SUPERVISOR-V3.9.6")
exec(compile(src,URL,"exec"),{"__name__":"__main__","__file__":str(Path(__file__).resolve())})
