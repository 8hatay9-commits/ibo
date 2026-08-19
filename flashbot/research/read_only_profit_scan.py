import json, time, urllib.request

FAST_RPC="https://mainnet-preconf.base.org"
STD_RPC="https://mainnet.base.org"
AAVE_POOL="0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
DATA_PROVIDER="0x0F43731EB8d45A581f4a36DD74F5f358bc90C73A"
ORACLE="0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156"
BORROW_TOPIC="0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0"
WINDOW=12000
NEAR_HF=1.20

class RPC:
    def __init__(self,url): self.url=url; self.i=0
    def call(self,method,params,timeout=25):
        self.i+=1
        body=json.dumps({"jsonrpc":"2.0","id":self.i,"method":method,"params":params}).encode()
        req=urllib.request.Request(self.url,data=body,headers={"Content-Type":"application/json","User-Agent":"flashbot-readonly-profit-scan"})
        last=None
        for k in range(4):
            try:
                with urllib.request.urlopen(req,timeout=timeout) as r:
                    obj=json.loads(r.read().decode())
                if obj.get("error"): raise RuntimeError(obj["error"])
                return obj.get("result")
            except Exception as e:
                last=e; time.sleep(0.5*(k+1))
        raise last

fast=RPC(FAST_RPC); std=RPC(STD_RPC)

def wa(a): return "0"*24+a.lower().removeprefix("0x")
def words(x):
    h=(x or "0x").removeprefix("0x")
    return [int(h[i:i+64],16) for i in range(0,len(h),64)] if len(h)%64==0 else []
def selector(sig):
    x=std.call("web3_sha3",["0x"+sig.encode().hex()],timeout=12)
    return x[2:10]
def decode_addr_array(x):
    h=(x or "0x").removeprefix("0x")
    if len(h)<128:return []
    off=int(h[:64],16)*2; n=int(h[off:off+64],16)
    return ["0x"+h[off+64+i*64:off+128+i*64][-40:] for i in range(n)]
def decode_symbol(x):
    h=(x or "0x").removeprefix("0x")
    try:
        if len(h)==64:return bytes.fromhex(h).rstrip(b"\0").decode(errors="replace")
        o=int(h[:64],16)*2;n=int(h[o:o+64],16)
        return bytes.fromhex(h[o+64:o+64+2*n]).decode(errors="replace")
    except:return "?"

def simulate_calls(calls):
    p={"blockStateCalls":[{"calls":calls,"stateOverrides":{}}],"traceTransfers":False,"validation":False}
    z=fast.call("eth_simulateV1",[p,"pending"],timeout=35)
    return (z or [{}])[0].get("calls") or []

SEL_USER="bf92857c"
SEL_RES=selector("getReservesList()")
SEL_URD=selector("getUserReserveData(address,address)")
SEL_CFG=selector("getReserveConfigurationData(address)")
SEL_FEE=selector("getLiquidationProtocolFee(address)")
SEL_PRICE=selector("getAssetPrice(address)")
SEL_SYMBOL=selector("symbol()")
SEL_DEC=selector("decimals()")
FLASH_PREMIUM_SEL="074b2e43"

def account_batch(users):
    if not users:return []
    calls=[{"to":AAVE_POOL,"data":"0x"+SEL_USER+wa(u)} for u in users]
    sim=simulate_calls(calls)
    out=[]
    for u,c in zip(users,sim):
        if c.get("status")!="0x1":continue
        v=words(c.get("returnData") or "0x")
        if len(v)<6 or v[1]<=0:continue
        out.append({"user":u,"collateral_base_raw":v[0],"debt_base_raw":v[1],"available_base_raw":v[2],"liq_threshold_bps":v[3],"ltv_bps":v[4],"hf":v[5]/1e18})
    return out

report={"ok":False,"type":"READ_ONLY_AAVE_PROFIT_SCAN_V1","started_at":time.time(),"rpc":{"fast":FAST_RPC,"std":STD_RPC},"errors":[]}
try:
    latest=int(std.call("eth_blockNumber",[],timeout=12),16); start=max(0,latest-WINDOW+1)
    ev=[]; b=start
    while b<=latest:
        e=min(latest,b+1999)
        try:
            ev += std.call("eth_getLogs",[{"address":AAVE_POOL,"fromBlock":hex(b),"toBlock":hex(e),"topics":[BORROW_TOPIC]}],timeout=20) or []
        except Exception as x: report["errors"].append("logs:%s:%s"%(type(x).__name__,x))
        b=e+1
    last={}
    for g in ev:
        t=g.get("topics") or []
        if len(t)<3:continue
        h=t[2].removeprefix("0x")
        if len(h)!=64:continue
        u="0x"+h[-40:]
        try:bn=int(g.get("blockNumber","0x0"),16)
        except:bn=0
        if bn>=last.get(u,0):last[u]=bn
    users=[u for u,_ in sorted(last.items(),key=lambda x:x[1],reverse=True)]
    ac=[]
    for i in range(0,len(users),50): ac+=account_batch(users[i:i+50])
    ac.sort(key=lambda x:x["hf"])
    near=[x for x in ac if 0<x["hf"]<NEAR_HF][:30]

    reserves_raw=std.call("eth_call",[{"to":AAVE_POOL,"data":"0x"+SEL_RES},"pending"],timeout=15)
    reserves=decode_addr_array(reserves_raw)
    meta={a:{} for a in reserves}
    calls=[]; tags=[]
    for a in reserves:
        calls += [{"to":a,"data":"0x"+SEL_SYMBOL},{"to":a,"data":"0x"+SEL_DEC},{"to":ORACLE,"data":"0x"+SEL_PRICE+wa(a)},{"to":DATA_PROVIDER,"data":"0x"+SEL_CFG+wa(a)},{"to":DATA_PROVIDER,"data":"0x"+SEL_FEE+wa(a)}]
        tags += [("s",a),("d",a),("p",a),("c",a),("f",a)]
    sim=simulate_calls(calls)
    for tag,c in zip(tags,sim):
        if c.get("status")!="0x1":continue
        x=c.get("returnData") or "0x"; a=tag[1]
        if tag[0]=="s":meta[a]["symbol"]=decode_symbol(x)
        elif tag[0]=="d":
            v=words(x); meta[a]["decimals"]=v[0] if v else 18
        elif tag[0]=="p":
            v=words(x); meta[a]["price"]=v[0] if v else 0
        elif tag[0]=="c":
            v=words(x)
            if len(v)>=10: meta[a].update({"liq_threshold_bps":v[2],"liq_bonus_bps":v[3]})
        elif tag[0]=="f":
            v=words(x); meta[a]["protocol_fee_bps"]=v[0] if v else 0

    user_positions={}
    detail_calls=[]; detail_tags=[]
    for row in near:
        u=row["user"]
        for a in reserves:
            detail_calls.append({"to":DATA_PROVIDER,"data":"0x"+SEL_URD+wa(a)+wa(u)})
            detail_tags.append((u,a))
    for i in range(0,len(detail_calls),300):
        sim=simulate_calls(detail_calls[i:i+300])
        for tag,c in zip(detail_tags[i:i+300],sim):
            if c.get("status")!="0x1":continue
            v=words(c.get("returnData") or "0x")
            if len(v)<9:continue
            bal=v[0]; debt=v[1]+v[2]; use=bool(v[8])
            if not bal and not debt:continue
            u,a=tag; m=meta[a]; dec=m.get("decimals",18); px=m.get("price",0)
            user_positions.setdefault(u,[]).append({
                "asset":a,"symbol":m.get("symbol","?"),"collateral":bal/(10**dec),"debt":debt/(10**dec),"use_as_collateral":use,
                "collateral_usd_est":bal*px/(10**dec)/1e8,"debt_usd_est":debt*px/(10**dec)/1e8,
                "liq_bonus_bps":m.get("liq_bonus_bps",10000),"protocol_fee_bps":m.get("protocol_fee_bps",0)
            })

    try:
        prem=words(std.call("eth_call",[{"to":AAVE_POOL,"data":"0x"+FLASH_PREMIUM_SEL},"pending"],timeout=12))[0]
    except Exception: prem=None

    candidates=[]
    for row in near:
        u=row["user"]; pos=user_positions.get(u,[])
        close_factor=1.0 if row["hf"]<=0.95 else 0.5
        best=None
        for col in pos:
            if not col["use_as_collateral"] or col["collateral_usd_est"]<=0:continue
            eff_bonus=max(0,col["liq_bonus_bps"]-10000)*(10000-col["protocol_fee_bps"])/10000
            for debt in pos:
                if debt["debt_usd_est"]<=0:continue
                max_cover=close_factor*debt["debt_usd_est"]
                max_cover=min(max_cover,col["collateral_usd_est"]/(1.0+eff_bonus/10000.0) if eff_bonus>0 else col["collateral_usd_est"])
                gross=max_cover*eff_bonus/10000.0
                flash=(max_cover*(prem or 0)/10000.0) if prem is not None else None
                pre_swap=(gross-flash) if flash is not None else None
                cand={"collateral":col["symbol"],"debt":debt["symbol"],"max_debt_cover_usd_est":max_cover,"effective_bonus_bps_est":eff_bonus,"gross_bonus_usd_est":gross,"flash_fee_usd_est":flash,"after_flash_before_swap_gas_usd_est":pre_swap}
                if best is None or cand["gross_bonus_usd_est"]>best["gross_bonus_usd_est"]:best=cand
        candidates.append({"user":u,"hf":row["hf"],"collateral_usd_total":row["collateral_base_raw"]/1e8,"debt_usd_total":row["debt_base_raw"]/1e8,"liquidatable_now":row["hf"]<1.0,"close_factor_assumed":close_factor,"best_pair":best,"positions":pos})
    candidates.sort(key=lambda x:((not x["liquidatable_now"]),x["hf"],-(x.get("best_pair") or {}).get("gross_bonus_usd_est",0)))
    report.update({"ok":True,"latest_block":latest,"start_block":start,"borrow_events":len(ev),"unique_recent_borrowers":len(users),"checked_users":len(ac),"near":candidates,"liquidatable_now":[x for x in candidates if x["liquidatable_now"]],"aave_flash_premium_bps":prem,"note":"Read-only estimate only. Full net gate still requires exact swap route, Base L2 gas, L1/data fee, slippage buffer and atomic executor simulation."})
except Exception as e:
    report["fatal_error"]="%s: %s"%(type(e).__name__,e)
report["finished_at"]=time.time(); report["elapsed_s"]=round(report["finished_at"]-report["started_at"],3)
open("profit_scan_report.json","w",encoding="utf-8").write(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
raise SystemExit(0 if report.get("ok") else 2)
