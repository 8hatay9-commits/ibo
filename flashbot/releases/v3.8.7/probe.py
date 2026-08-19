import json, time
from pathlib import Path
from rpc import RpcClient

ROOT=Path(__file__).resolve().parent
cfg=json.loads((ROOT/"settings.json").read_text(encoding="utf-8"))
rpc=RpcClient(cfg["flashblocks_http"],min_interval=0.05)
std=RpcClient(cfg["http_rpc"],min_interval=0.12)

AAVE_POOL=cfg["contracts"]["aave_pool"]
DATA_PROVIDER="0x0F43731EB8d45A581f4a36DD74F5f358bc90C73A"
ORACLE="0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156"
TARGETS=[
"0x6a2cc7efa2c5d91c45411d956358928158262a19",
"0x9f9ff4ffdf0b16dd096f649586e882d88a9bf1c0",
"0xfeee2af72cd54577526a3e8a6508a9d8d0942fb8"
]

def word_addr(a): return ("0"*24)+a.lower().removeprefix("0x")
def words(raw):
    h=(raw or "0x").removeprefix("0x")
    if len(h)%64: raise ValueError("unaligned ABI result")
    return [int(h[i:i+64],16) for i in range(0,len(h),64)]
def sha3_text(s):
    return std.call("web3_sha3",["0x"+s.encode().hex()],timeout=8,max_attempts=3)
def sel(sig): return sha3_text(sig)[2:10]
def decode_addr_array(raw):
    h=(raw or "0x").removeprefix("0x")
    if len(h)<128: return []
    off=int(h[:64],16)*2
    if len(h)<off+64: return []
    n=int(h[off:off+64],16)
    out=[]; p=off+64
    for i in range(n):
        w=h[p+i*64:p+(i+1)*64]
        if len(w)==64: out.append("0x"+w[-40:])
    return out
def decode_symbol(raw):
    h=(raw or "0x").removeprefix("0x")
    try:
        if len(h)==64:
            return bytes.fromhex(h).rstrip(b"\x00").decode("utf-8","replace")
        if len(h)>=128:
            off=int(h[:64],16)*2
            n=int(h[off:off+64],16)
            data=h[off+64:off+64+n*2]
            return bytes.fromhex(data).decode("utf-8","replace")
    except Exception: pass
    return "?"

started=time.monotonic()
report={"ok":False,"type":"AAVE_NEAR_LIQUIDATION_POSITION_DETAIL_V1","targets":TARGETS,
        "data_provider":DATA_PROVIDER,"oracle":ORACLE,"positions":{},"errors":[],"timings":{},"timestamp":time.time()}
try:
    t=time.monotonic()
    s_reserves=sel("getReservesList()")
    s_user=sel("getUserReserveData(address,address)")
    s_cfg=sel("getReserveConfigurationData(address)")
    s_liqfee=sel("getLiquidationProtocolFee(address)")
    s_price=sel("getAssetPrice(address)")
    s_baseunit=sel("BASE_CURRENCY_UNIT()")
    s_basecur=sel("BASE_CURRENCY()")
    s_symbol=sel("symbol()")
    s_decimals=sel("decimals()")
    report["timings"]["selectors_s"]=round(time.monotonic()-t,3)

    raw_res=rpc.call("eth_call",[{"to":AAVE_POOL,"data":"0x"+s_reserves},"pending"],timeout=10,max_attempts=3)
    reserves=decode_addr_array(raw_res)
    report["reserve_count"]=len(reserves)
    report["reserves"]=reserves

    base_calls=[{"to":ORACLE,"data":"0x"+s_baseunit},{"to":ORACLE,"data":"0x"+s_basecur}]
    sim=rpc.call("eth_simulateV1",[{"blockStateCalls":[{"calls":base_calls,"stateOverrides":{}}],
                                    "traceTransfers":False,"validation":False},"pending"],timeout=15,max_attempts=3)
    bcalls=(sim or [{}])[0].get("calls") or []
    base_unit=words((bcalls[0].get("returnData") if len(bcalls)>0 else "0x"))[0]
    base_cur_word=words((bcalls[1].get("returnData") if len(bcalls)>1 else "0x"))[0]
    base_cur="0x"+f"{base_cur_word:064x}"[-40:]
    report["base_currency_unit"]=base_unit
    report["base_currency"]=base_cur

    calls=[]; tags=[]
    for asset in reserves:
        calls += [
            {"to":asset,"data":"0x"+s_symbol},
            {"to":asset,"data":"0x"+s_decimals},
            {"to":ORACLE,"data":"0x"+s_price+word_addr(asset)},
            {"to":DATA_PROVIDER,"data":"0x"+s_cfg+word_addr(asset)},
            {"to":DATA_PROVIDER,"data":"0x"+s_liqfee+word_addr(asset)}
        ]
        tags += [("symbol",asset),("decimals",asset),("price",asset),("config",asset),("liqfee",asset)]
    for user in TARGETS:
        for asset in reserves:
            calls.append({"to":DATA_PROVIDER,"data":"0x"+s_user+word_addr(asset)+word_addr(user)})
            tags.append(("user",user,asset))

    t=time.monotonic()
    sim=rpc.call("eth_simulateV1",[{"blockStateCalls":[{"calls":calls,"stateOverrides":{}}],
                                    "traceTransfers":False,"validation":False},"pending"],timeout=20,max_attempts=3)
    outs=(sim or [{}])[0].get("calls") or []
    report["timings"]["detail_batch_s"]=round(time.monotonic()-t,3)
    if len(outs)!=len(tags): raise ValueError(f"detail call mismatch {len(outs)} != {len(tags)}")

    meta={a:{} for a in reserves}; userrows={u:{} for u in TARGETS}
    for tag,out in zip(tags,outs):
        if out.get("status")!="0x1":
            report["errors"].append({"tag":tag,"status":out.get("status")}); continue
        raw=out.get("returnData") or "0x"
        if tag[0]=="symbol": meta[tag[1]]["symbol"]=decode_symbol(raw)
        elif tag[0]=="decimals": meta[tag[1]]["decimals"]=words(raw)[0]
        elif tag[0]=="price": meta[tag[1]]["price_base_raw"]=words(raw)[0]
        elif tag[0]=="config":
            v=words(raw)
            if len(v)>=10:
                meta[tag[1]].update({"config_decimals":v[0],"ltv_bps":v[1],"liquidation_threshold_bps":v[2],
                                     "liquidation_bonus_bps":v[3],"reserve_factor_bps":v[4],
                                     "usage_as_collateral_enabled":bool(v[5]),"borrowing_enabled":bool(v[6]),
                                     "active":bool(v[8]),"frozen":bool(v[9])})
        elif tag[0]=="liqfee": meta[tag[1]]["liquidation_protocol_fee_bps"]=words(raw)[0]
        elif tag[0]=="user":
            v=words(raw)
            if len(v)>=9:
                userrows[tag[1]][tag[2]]={"a_token_balance":v[0],"stable_debt":v[1],"variable_debt":v[2],
                                          "usage_as_collateral":bool(v[8])}

    for user in TARGETS:
        pos=[]
        for asset,row in userrows[user].items():
            bal=int(row.get("a_token_balance",0)); debt=int(row.get("stable_debt",0))+int(row.get("variable_debt",0))
            if bal<=0 and debt<=0: continue
            m=meta.get(asset,{})
            dec=int(m.get("decimals",m.get("config_decimals",18)))
            px=int(m.get("price_base_raw",0)); unit=10**dec
            collateral_base=(bal*px/unit) if px else 0; debt_base=(debt*px/unit) if px else 0
            bonus=int(m.get("liquidation_bonus_bps",10000)); fee=int(m.get("liquidation_protocol_fee_bps",0))
            gross_bonus_bps=max(0,bonus-10000); liquidator_bonus_bps=gross_bonus_bps*(10000-fee)/10000
            pos.append({
                "asset":asset,"symbol":m.get("symbol","?"),"decimals":dec,
                "a_token_balance_raw":str(bal),"debt_raw":str(debt),
                "collateral_base_raw_est":str(int(collateral_base)),"debt_base_raw_est":str(int(debt_base)),
                "usage_as_collateral":bool(row.get("usage_as_collateral")),
                "liquidation_bonus_bps":bonus,"liquidation_protocol_fee_bps":fee,
                "effective_liquidator_bonus_bps_est":round(liquidator_bonus_bps,4)
            })
        pos.sort(key=lambda x:(int(x["debt_base_raw_est"]),int(x["collateral_base_raw_est"])),reverse=True)
        report["positions"][user]=pos

    report["asset_meta"]=meta; report["ok"]=True
except Exception as e:
    report["fatal_error"]=f"{type(e).__name__}: {e}"

report["timings"]["total_s"]=round(time.monotonic()-started,3)
(ROOT/"probe_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
raise SystemExit(0 if report["ok"] else 4)
