import hashlib, urllib.request

CORE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/f9bfd5fc90e3989b4afc88ce2f39848febd08528/flashbot/releases/v3.7.0/daemon.py"
CORE_GIT_BLOB_SHA1="6c447acdb4dfd19bfae3ee7625000bfabc4a08e4"
raw=urllib.request.urlopen(CORE_URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=CORE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.7 daemon mismatch: {got}")
src=raw.decode("utf-8").replace("FLASHBOT-PRODUCTION-V3.7.0","FLASHBOT-PRODUCTION-V3.8.0")
exec(compile(src,CORE_URL,"exec"),{"__name__":"__main__","__file__":__file__})
