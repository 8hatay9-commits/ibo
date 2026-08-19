import json,time
from pathlib import Path
from rpc import RpcClient
R=Path(__file__).resolve().parent
c=json.loads((R/"settings.json").read_text())
r=RpcClient(c["flashblocks_http"],min_interval=.05)
s=RpcClient(c["http_rpc"],min_interval=.1)
P=c["contracts"]["aave_pool"];D="0x0F43731EB8d45A581f4a36DD74F5f358bc90C73A";O="0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156"
U=["0x6a2cc7efa2c5d91c45411d956358928158262a19","0x9f9ff4ffdf0b16dd096f649586e882d88a9bf1c0","0xfeee2af72cd54577526a3e8a6508a9d8d0942fb8"]
wa=lambda a:"0"*24+a.lower().removeprefix("0x")
def w(x):
 h=(x or "0x").removeprefix("0x");return [int(h[i:i+64],16) for i in range(0,len(h),64)] if len(h)%64==0 else []
def sh(x):return s.call("web3_sha3",["0x"+x.encode().hex()],timeout=8,max_attempts=3)
def sl(x):return sh(x)[2:10]
def aa(x):
 h=(x or "0x").removeprefix("0x")
 if len(h)<128:return []
 o=int(h[:64],16)*2;n=int(h[o:o+64],16);return ["0x"+h[o+64+i*64:o+128+i*64][-40:] for i in range(n)]
def sym(x):
 h=(x or "0x").removeprefix("0x")
 try:
  if len(h)==64:return bytes.fromhex(h).rstrip(b"\0").decode(errors="replace")
  o=int(h[:64],16)*2;n=int(h[o:o+64],16);return bytes.fromhex(h[o+64:o+64+2*n]).decode(errors="replace")
 except:return "?"
t=time.monotonic();q={"ok":False,"type":"AAVE_NEAR_LIQUIDATION_DETAIL_V2","targets":U,"positions":{},"errors":[]}
try:
 sr=sl("getReservesList()");su=sl("getUserReserveData(address,address)");sc=sl("getReserveConfigurationData(address)");sf=sl("getLiquidationProtocolFee(address)");sp=sl("getAssetPrice(address)");ss=sl("symbol()");sd=sl("decimals()")
 A=aa(r.call("eth_call",[{"to":P,"data":"0x"+sr},"pending"],timeout=10,max_attempts=3));q["reserve_count"]=len(A)
 C=[];T=[]
 for a in A:
  C += [{"to":a,"data":"0x"+ss},{"to":a,"data":"0x"+sd},{"to":O,"data":"0x"+sp+wa(a)},{"to":D,"data":"0x"+sc+wa(a)},{"to":D,"data":"0x"+sf+wa(a)}]
  T += [("s",a),("d",a),("p",a),("c",a),("f",a)]
 for u in U:
  for a in A:C.append({"to":D,"data":"0x"+su+wa(a)+wa(u)});T.append(("u",u,a))
 z=r.call("eth_simulateV1",[{"blockStateCalls":[{"calls":C,"stateOverrides":{}}],"traceTransfers":False,"validation":False},"pending"],timeout=20,max_attempts=3)
 OX=(z or [{}])[0].get("calls") or []
 if len(OX)!=len(T):raise ValueError(f"count {len(OX)} != {len(T)}")
 M={a:{} for a in A};X={u:{} for u in U}
 for tag,o in zip(T,OX):
  if o.get("status")!="0x1":q["errors"].append({"tag":tag,"status":o.get("status")});continue
  x=o.get("returnData") or "0x"
  if tag[0]=="s":M[tag[1]]["symbol"]=sym(x)
  elif tag[0]=="d":M[tag[1]]["decimals"]=w(x)[0]
  elif tag[0]=="p":M[tag[1]]["price"]=w(x)[0]
  elif tag[0]=="c":
   v=w(x)
   if len(v)>=10:M[tag[1]].update({"liq_bonus_bps":v[3],"liq_threshold_bps":v[2]})
  elif tag[0]=="f":M[tag[1]]["protocol_fee_bps"]=w(x)[0]
  else:
   v=w(x)
   if len(v)>=9:X[tag[1]][tag[2]]=(v[0],v[1]+v[2],bool(v[8]))
 for u in U:
  a=[]
  for k,(bal,debt,use) in X[u].items():
   if not bal and not debt:continue
   m=M[k];dec=m.get("decimals",18);px=m.get("price",0);bonus=m.get("liq_bonus_bps",10000);fee=m.get("protocol_fee_bps",0)
   eff=max(0,bonus-10000)*(10000-fee)/10000
   a.append({"asset":k,"symbol":m.get("symbol","?"),"collateral":bal/(10**dec),"debt":debt/(10**dec),"collateral_base_est":bal*px/(10**dec),"debt_base_est":debt*px/(10**dec),"use_as_collateral":use,"liquidation_bonus_bps":bonus,"protocol_fee_bps":fee,"effective_liquidator_bonus_bps_est":round(eff,4)})
  a.sort(key=lambda x:max(x["collateral_base_est"],x["debt_base_est"]),reverse=True);q["positions"][u]=a
 q["ok"]=True
except Exception as e:q["fatal_error"]=f"{type(e).__name__}: {e}"
q["total_s"]=round(time.monotonic()-t,3)
(R/"probe_report.json").write_text(json.dumps(q,indent=2))
print(json.dumps(q))
raise SystemExit(0 if q["ok"] else 4)
