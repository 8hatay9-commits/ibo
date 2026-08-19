import base64, hashlib, json, os, re, sys, time, traceback, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
STATE=ROOT/"daemon_state.json"
URL="https://raw.githubusercontent.com/8hatay9-commits/ibo/513563da78c7931c7501bcc4cc72561cc3e7cd12/flashbot/releases/v3.9.8/daemon.py"
BLOB_SHA1="b3dc961ea1195ae0a7fa1862038cfe95ddf8948b"

def diag(obj):
    tmp=STATE.with_name(f"{STATE.name}.{os.getpid()}.v3101.tmp")
    tmp.write_text(json.dumps(obj,indent=2),encoding="utf-8")
    last=None
    for attempt in range(8):
        try:
            tmp.replace(STATE)
            return
        except PermissionError as e:
            last=e
            time.sleep(min(0.25,0.01*(2**attempt)))
    raise last

def replace_b64_assignment(text,var,transform):
    pat=re.compile(r'('+re.escape(var)+r'\s*=\s*[A-Za-z0-9_]+\.b64decode\("([^"]+)"\)\.decode\("utf-8"\))')
    m=pat.search(text)
    if not m:
        raise RuntimeError(f"{var} base64 assignment not found")
    decoded=base64.b64decode(m.group(2)).decode("utf-8")
    changed=transform(decoded)
    if changed==decoded:
        raise RuntimeError(f"{var} transform made no change")
    enc=base64.b64encode(changed.encode("utf-8")).decode("ascii")
    return text[:m.start(2)]+enc+text[m.end(2):]

worker="--worker" in sys.argv
diag({"ok":False,"version":"FLASHBOT-PRODUCTION-V3.10.1","mode":"DRY_RUN_ONLY",
      "phase":"outer_worker_boot_v3101" if worker else "outer_supervisor_boot_v3101",
      "last_error":None,"timestamp":time.time()})
try:
    raw=urllib.request.urlopen(URL,timeout=30).read()
    got=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
    if got!=BLOB_SHA1:
        raise RuntimeError(f"pinned V3.9.8 daemon mismatch: {got}")
    src=raw.decode("utf-8")

    bad='f"blob {len(raw)}\\\\0".encode()+raw'
    good='f"blob {len(raw)}\\0".encode()+raw'
    if bad not in src:
        raise RuntimeError("V3.10.1 bad blob-header marker not found")
    src=src.replace(bad,good,1)

    def patch_outer_new(patch_src):
        def patch_nested(nested_src):
            def patch_probe(probe_src):
                if "[25,100]" not in probe_src:
                    raise RuntimeError("V3.10.1 [25,100] probe marker not found")
                return probe_src.replace("[25,100]","[25]",1)
            return replace_b64_assignment(nested_src,"_new_probe_v398",patch_probe)
        return replace_b64_assignment(patch_src,"_new_nested",patch_nested)

    src=replace_b64_assignment(src,"new",patch_outer_new)
    src=src.replace("V3.9.8","V3.10.1")
    compile(src,URL,"exec")
    exec(compile(src,URL,"exec"),{"__name__":"__main__","__file__":str(Path(__file__).resolve())})
except BaseException as e:
    try:
        diag({"ok":False,"version":"FLASHBOT-PRODUCTION-V3.10.1","mode":"DRY_RUN_ONLY",
              "phase":"outer_worker_error_v3101" if worker else "outer_supervisor_error_v3101",
              "last_error":f"{type(e).__name__}:{e}",
              "traceback_tail":traceback.format_exc()[-5000:],"timestamp":time.time()})
    except Exception:
        pass
    raise
