import hashlib, urllib.request
URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/4eeffac3a0dafa2e932ebdeb95ece61517907d33/flashbot/releases/v3.2.0/daemon.py"
GIT_BLOB_SHA1="9b3ff553f35a991c09267ea313d3675e16584d0e"
raw=urllib.request.urlopen(URL,timeout=30).read()
got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
if got!=GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned daemon blob mismatch: {got}")
exec(compile(raw,URL,"exec"),{"__name__":"__main__","__file__":__file__})
