import hashlib, urllib.request

CORE_URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/16780e2f3359b1309bd98a296d9e96dab68192af/flashbot/releases/v3.7.2/daemon.py"
CORE_GIT_BLOB_SHA1="4b2dc0bd30a6263471d5211b7cb1a784f44a7181"
raw=urllib.request.urlopen(CORE_URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=CORE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.7.2 daemon mismatch: {got}")
src=raw.decode("utf-8")
bad='marker=\'\\nseconds=int(sys.argv[1]) if len(sys.argv)>1 else 0\\ncore["main"](seconds)\\n\''
good='marker=\'\\nseconds=int(sys.argv[1]) if len(sys.argv)>1 else 0\\ncore["main"](seconds)\''
if bad not in src:
    raise RuntimeError("V3.7.2 marker declaration not found")
src=src.replace(bad,good,1).replace("FLASHBOT-PRODUCTION-V3.7.2","FLASHBOT-PRODUCTION-V3.7.3",1)
exec(compile(src,CORE_URL,"exec"),{"__name__":"__main__","__file__":__file__})
