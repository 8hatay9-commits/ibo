import hashlib, urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/8hatay9-commits/ibo/89e7062cfe5fbe1d904d9cac974c189432891188/flashbot/releases/v3.9.1/daemon.py"
BASE_GIT_BLOB_SHA1 = "ecdd03c9b5829d2d3b86d21e16dae3f6cd6cc47c"

raw = urllib.request.urlopen(BASE_URL, timeout=30).read()
got = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
if got != BASE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.9.1 daemon mismatch: {got}")
src = raw.decode("utf-8")
if "FLASHBOT-PRODUCTION-V3.9.1" not in src or "FLASHBOT-SUPERVISOR-V3.9.1" not in src:
    raise RuntimeError("V3.9.2 daemon version markers not found")
src = src.replace("FLASHBOT-PRODUCTION-V3.9.1", "FLASHBOT-PRODUCTION-V3.9.2")
src = src.replace("FLASHBOT-SUPERVISOR-V3.9.1", "FLASHBOT-SUPERVISOR-V3.9.2")
exec(compile(src, BASE_URL, "exec"), {"__name__":"__main__", "__file__":str(Path(__file__).resolve())})
