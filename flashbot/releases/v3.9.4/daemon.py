import hashlib, sys, urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/8hatay9-commits/ibo/ad31b08280dbea26ad68454a3d45c20fe3cdaf48/flashbot/releases/v3.9.0/daemon.py"
BASE_GIT_BLOB_SHA1 = "67289d1f38bd3e4db9580948b02319436d78fd19"

raw = urllib.request.urlopen(BASE_URL, timeout=30).read()
got = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
if got != BASE_GIT_BLOB_SHA1:
    raise RuntimeError(f"pinned V3.9.0 daemon mismatch: {got}")
src = raw.decode("utf-8")

old = 'def write_state(obj):\n    tmp = SUP_STATE.with_suffix(".tmp")\n    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")\n    tmp.replace(SUP_STATE)\n'
new = 'def write_state(obj):\n    payload = json.dumps(obj, indent=2)\n    tmp = SUP_STATE.with_name(f"{SUP_STATE.name}.{os.getpid()}.tmp")\n    tmp.write_text(payload, encoding="utf-8")\n    last = None\n    for attempt in range(8):\n        try:\n            tmp.replace(SUP_STATE)\n            return\n        except PermissionError as e:\n            last = e\n            time.sleep(min(0.25, 0.01 * (2 ** attempt)))\n    raise last\n'
if old not in src:
    raise RuntimeError("V3.9.4 supervisor state-write marker not found")
src = src.replace(old, new, 1)

old = '    return src\n\ndef run_worker():\n'
new = '    old_state = \'STOP=v["STOP"]; ACTIVE=v["ACTIVE"]; save=v["save"]\'\n    new_state = """STOP=v["STOP"]; ACTIVE=v["ACTIVE"]; save=v["save"]\n_state_write_lock_v394=threading.RLock()\ndef _save_v394(obj):\n    state=core["STATE"]\n    payload=json.dumps(obj,indent=2)\n    with _state_write_lock_v394:\n        tmp=state.with_name(f"{state.name}.{threading.get_ident()}.tmp")\n        tmp.write_text(payload,encoding="utf-8")\n        last=None\n        for attempt in range(8):\n            try:\n                tmp.replace(state)\n                return\n            except PermissionError as e:\n                last=e\n                time.sleep(min(0.25,0.01*(2**attempt)))\n        raise last\nsave=_save_v394\ncore["save"]=_save_v394\n"""\n    if old_state not in src:\n        raise RuntimeError("V3.9.4 daemon state-write marker not found")\n    src = src.replace(old_state, new_state, 1)\n\n    old_probe = \'qcfg["probe_sizes_human"]=[100]\'\n    new_probe = \'qcfg["probe_sizes_human"]=[25,100]\'\n    if old_probe not in src:\n        raise RuntimeError("V3.9.4 probe-size marker not found")\n    src = src.replace(old_probe, new_probe, 1)\n\n    old_rank = \'    ranked=sorted(cand.values(),key=activity_score)\'\n    new_rank = """    tri_ranked=sorted([c for c in cand.values() if c["kind"]=="triangle"],key=activity_score)\n    two_ranked=sorted([c for c in cand.values() if c["kind"]=="2pool"],key=activity_score)\n    ranked=[]\n    for i in range(max(len(tri_ranked),len(two_ranked))):\n        if i<len(tri_ranked):ranked.append(tri_ranked[i])\n        if i<len(two_ranked):ranked.append(two_ranked[i])"""\n    if old_rank not in src:\n        raise RuntimeError("V3.9.4 balanced-ranking marker not found")\n    src = src.replace(old_rank, new_rank, 1)\n\n    old_policy = \'    st["route_candidates_last_batch"]=len(ranked)\\n    st["candidate_policy"]="VALUE_FIRST_ACTIVITY_RANKED_V36"\'\n    new_policy = \'    st["route_candidates_last_batch"]=len(ranked)\\n    st["triangle_candidates_last_batch"]=len(tri_ranked)\\n    st["two_pool_candidates_last_batch"]=len(two_ranked)\\n    st["candidate_policy"]="ARB_BALANCED_TRI_2POOL_V394"\'\n    if old_policy not in src:\n        raise RuntimeError("V3.9.4 ranking-policy marker not found")\n    src = src.replace(old_policy, new_policy, 1)\n\n    return src\n\ndef run_worker():\n'
if old not in src:
    raise RuntimeError("V3.9.4 patch-core return marker not found")
src = src.replace(old, new, 1)

src = src.replace('src = src.replace("FLASHBOT-PRODUCTION-V3.7.0","FLASHBOT-PRODUCTION-V3.8.4",1)',
                  'src = src.replace("FLASHBOT-PRODUCTION-V3.7.0","FLASHBOT-PRODUCTION-V3.9.4",1)', 1)
src = src.replace("FLASHBOT-SUPERVISOR-V3.8.4", "FLASHBOT-SUPERVISOR-V3.9.4")

exec(compile(src, BASE_URL, "exec"), {"__name__": "__main__", "__file__": str(Path(__file__).resolve())})
