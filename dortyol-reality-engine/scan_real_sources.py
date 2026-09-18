#!/usr/bin/env python3
import json, math, os, time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUT = os.path.join(os.path.dirname(__file__), "coverage_multi.json")
UA = "Dortyol-Reality-Engine/0.2 (+https://github.com/8hatay9-commits/ibo)"

MIN_LON, MAX_LON = 36.075, 36.55
MIN_LAT, MAX_LAT = 36.70, 37.03
STEP = 0.03

def get_json(url, timeout=25):
    req = Request(url, headers={"User-Agent": UA, "Accept":"application/json"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def safe(url):
    try:
        return get_json(url), None
    except Exception as e:
        return None, repr(e)

def scan_panoramax(lon, lat, r=0.015):
    bbox = f"{lon-r},{lat-r},{lon+r},{lat+r}"
    data, err = safe("https://api.panoramax.xyz/api/search?" + urlencode({"bbox":bbox,"limit":100}))
    feats = data.get("features",[]) if isinstance(data,dict) else []
    return {"count":len(feats), "error":err, "ids":[f.get("id") for f in feats[:10] if isinstance(f,dict)]}

def scan_kartaview(lon, lat):
    data, err = safe("https://api.openstreetcam.org/2.0/photo/?" + urlencode({"lat":lat,"lng":lon,"zoomLevel":15}))
    count = 0
    sample=[]
    if isinstance(data,dict):
        result=data.get("result") or {}
        rows=result.get("data") if isinstance(result,dict) else None
        if isinstance(rows,list):
            count=len(rows); sample=[str(x.get("id")) for x in rows[:10] if isinstance(x,dict)]
        elif isinstance(rows,dict):
            count=len(rows); sample=list(map(str,list(rows)[:10]))
    return {"count":count, "error":err, "ids":sample}

def scan_commons(lon, lat):
    params={
      "action":"query","format":"json","generator":"geosearch","ggsprimary":"all",
      "ggsnamespace":6,"ggsradius":5000,"ggscoord":f"{lat}|{lon}","ggslimit":100,
      "prop":"coordinates|imageinfo","iiprop":"url|extmetadata"
    }
    data,err=safe("https://commons.wikimedia.org/w/api.php?"+urlencode(params))
    pages=((data or {}).get("query") or {}).get("pages") or {}
    items=[]
    for p in pages.values() if isinstance(pages,dict) else []:
        if not isinstance(p,dict): continue
        ii=(p.get("imageinfo") or [{}])[0]
        meta=ii.get("extmetadata") or {}
        lic=((meta.get("LicenseShortName") or {}).get("value"))
        items.append({"title":p.get("title"),"url":ii.get("url"),"license":lic})
    return {"count":len(items),"error":err,"items":items[:10]}

cells=[]; totals={"panoramax":0,"kartaview":0,"commons":0}; errors=[]
lat=MIN_LAT+STEP/2
while lat<MAX_LAT:
  lon=MIN_LON+STEP/2
  while lon<MAX_LON:
    p=scan_panoramax(lon,lat)
    k=scan_kartaview(lon,lat)
    w=scan_commons(lon,lat)
    totals["panoramax"] += p["count"]
    totals["kartaview"] += k["count"]
    totals["commons"] += w["count"]
    cell={
      "center":[round(lon,6),round(lat,6)],
      "panoramax":p,"kartaview":k,"wikimedia_commons":w,
      "status":"VERIFIED_GROUND_CANDIDATE" if (p["count"] or k["count"]) else ("REFERENCE_PHOTO_ONLY" if w["count"] else "NO_GROUND_SOURCE_FOUND")
    }
    cells.append(cell)
    for src,d in (("panoramax",p),("kartaview",k),("commons",w)):
      if d.get("error"): errors.append({"source":src,"center":cell["center"],"error":d["error"]})
    lon += STEP
    time.sleep(0.05)
  lat += STEP

payload={
 "generated_at":datetime.now(timezone.utc).isoformat(),
 "bbox":[MIN_LON,MIN_LAT,MAX_LON,MAX_LAT],
 "step_deg":STEP,
 "truth_policy":{
   "photorealistic_walk_requires":["verified geotagged ground imagery","reuse-compatible license","capture timestamp","geolocation confidence"],
   "satellite_only_never_promoted_to_ground_truth":True
 },
 "sources":{
   "panoramax":{"license_policy":"instance license, federation accepts LO-2.0 or CC-BY-SA-4.0","role":"ground imagery / 360"},
   "kartaview":{"license":"CC-BY-SA-4.0","attribution":"© Grab and KartaView Contributors","role":"street/road imagery"},
   "wikimedia_commons":{"license":"per-file","role":"reference photos only unless geolocation and license are adequate"}
 },
 "totals_raw_hits":totals,
 "cells":cells,
 "errors":errors
}
with open(OUT,"w",encoding="utf-8") as f: json.dump(payload,f,ensure_ascii=False,indent=2)
print(json.dumps({"cells":len(cells),"raw_hits":totals,"errors":len(errors)},ensure_ascii=False))
