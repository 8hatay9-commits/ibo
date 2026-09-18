#!/usr/bin/env python3
import json, math, os, sys, time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUT = os.path.join(os.path.dirname(__file__), "coverage.json")
PANORAMAX = "https://api.panoramax.xyz/api/search"

# Dörtyol + western/central Amanos working envelope.
MIN_LON, MAX_LON = 36.10, 36.55
MIN_LAT, MAX_LAT = 36.70, 37.02
STEP = 0.04
HALF = STEP / 2

def fetch_json(url, timeout=25):
    req = Request(url, headers={"User-Agent":"Dortyol-Reality-Engine/0.1 (+github-actions)"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

cells=[]
unique={}
errors=[]
lat=MIN_LAT+HALF
while lat < MAX_LAT:
    lon=MIN_LON+HALF
    while lon < MAX_LON:
        bbox=[lon-HALF, lat-HALF, lon+HALF, lat+HALF]
        q=urlencode({"bbox": ",".join(f"{x:.6f}" for x in bbox), "limit": 100})
        url=f"{PANORAMAX}?{q}"
        try:
            data=fetch_json(url)
            feats=data.get("features",[]) if isinstance(data,dict) else []
            for f in feats:
                if isinstance(f,dict) and f.get("id"):
                    unique[f["id"]]=f
            cells.append({
                "center":[round(lon,6),round(lat,6)],
                "bbox":[round(x,6) for x in bbox],
                "panoramax_count_sample":len(feats),
                "status":"VERIFIED_GROUND" if feats else "NO_PANORAMAX_SAMPLE"
            })
        except Exception as e:
            cells.append({
                "center":[round(lon,6),round(lat,6)],
                "bbox":[round(x,6) for x in bbox],
                "panoramax_count_sample":None,
                "status":"SCAN_ERROR"
            })
            errors.append({"url":url,"error":repr(e)})
        lon += STEP
        time.sleep(0.10)
    lat += STEP

dates=[]
for f in unique.values():
    p=f.get("properties") or {}
    dt=p.get("datetime") or p.get("datetimetz")
    if dt:
        dates.append(str(dt))

payload={
    "generated_at":datetime.now(timezone.utc).isoformat(),
    "bbox":[MIN_LON,MIN_LAT,MAX_LON,MAX_LAT],
    "step_deg":STEP,
    "source":{
        "name":"Panoramax federated STAC catalog",
        "endpoint":"https://api.panoramax.xyz/api",
        "search":"https://api.panoramax.xyz/api/search"
    },
    "summary":{
        "cells":len(cells),
        "cells_with_ground_imagery":sum(1 for c in cells if (c.get("panoramax_count_sample") or 0)>0),
        "unique_picture_ids_sampled":len(unique),
        "oldest_capture":min(dates) if dates else None,
        "newest_capture":max(dates) if dates else None,
        "scan_errors":len(errors)
    },
    "cells":cells,
    "errors":errors[:50]
}
os.makedirs(os.path.dirname(OUT),exist_ok=True)
with open(OUT,"w",encoding="utf-8") as f:
    json.dump(payload,f,ensure_ascii=False,indent=2)
print(json.dumps(payload["summary"],ensure_ascii=False))
