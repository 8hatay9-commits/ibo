
import json, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
out={"ok":True,"timestamp":time.time()}
for name in ["daemon_state.json","backfill_report.json","probe_report.json"]:
    p=ROOT/name
    if p.exists():
        try:out[name]=json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:out[name]={"error":repr(e)}
try:
    import sqlite3
    cx=sqlite3.connect(ROOT/"flashbot_v3.sqlite3")
    out["pool_count"]=cx.execute("select count(*) from pools").fetchone()[0]
except Exception as e:out["db_error"]=repr(e)
print(json.dumps(out,indent=2))
