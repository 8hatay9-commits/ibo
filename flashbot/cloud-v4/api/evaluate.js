import{rpc,hexInt,accountData,flashPremiumBps}from'../lib/base.js';
import{userPositions}from'../lib/aave.js';
import{planLiquidations}from'../lib/planner.js';
import{quoteUniswapV3Single}from'../lib/dex.js';

const SAFETY_BUFFER_BPS=30n;
const BPS=10000n;
const ceilDiv=(a,b)=>a===0n?0n:(a+b-1n)/b;

export default async function handler(req,res){
  const observed_at=new Date().toISOString();
  try{
    const user=String(req.query?.user||'').toLowerCase();
    if(!/^0x[0-9a-f]{40}$/.test(user))return res.status(400).json({ok:false,error:'valid ?user=0x... required'});

    const head=await rpc('eth_blockNumber');
    const block=hexInt(head.result), tag='0x'+block.toString(16);
    const [acct,pos,premium]=await Promise.all([
      accountData(user,tag),
      userPositions(user,tag),
      flashPremiumBps(tag)
    ]);

    const planned=planLiquidations(acct,pos,premium.bps);
    const positionMap=new Map(pos.positions.map(p=>[p.asset.toLowerCase(),p]));
    const evaluated=[];

    for(const p of planned.plans.slice(0,8)){
      if(p.status!=='NEEDS_SWAP_SIMULATION'){
        evaluated.push({...p,quote:null,net_after_quote_raw:null,verdict:p.status});
        continue;
      }
      const collateral=positionMap.get(p.collateral_asset.toLowerCase());
      const debt=positionMap.get(p.debt_asset.toLowerCase());
      if(!collateral||!debt){
        evaluated.push({...p,quote:null,net_after_quote_raw:null,verdict:'REJECT_POSITION_LOOKUP'});
        continue;
      }
      const amountIn=BigInt(p.collateral_to_liquidator_raw);
      const q=await quoteUniswapV3Single(collateral.asset,debt.asset,amountIn,tag);
      if(!q.best){
        evaluated.push({...p,quote:q,net_after_quote_raw:null,verdict:'REJECT_NO_UNISWAP_QUOTE'});
        continue;
      }
      const debtToCover=BigInt(p.debt_to_cover_raw);
      const flashPremium=ceilDiv(debtToCover*BigInt(premium.bps||0),BPS);
      const safety=ceilDiv(debtToCover*SAFETY_BUFFER_BPS,BPS);
      const repayRequired=debtToCover+flashPremium+safety;
      const amountOut=BigInt(q.best.amount_out_raw);
      const net=amountOut-repayRequired;
      const verdict=net>0n?'NEEDS_ATOMIC_TX_SIMULATION':'REJECT_AFTER_EXACT_QUOTE';
      evaluated.push({...p,quote:q,repay_required_raw:repayRequired.toString(),safety_buffer_bps:Number(SAFETY_BUFFER_BPS),net_after_quote_raw:net.toString(),verdict,execute:false});
    }

    evaluated.sort((a,b)=>{
      if(a.net_after_quote_raw==null&&b.net_after_quote_raw==null)return 0;
      if(a.net_after_quote_raw==null)return 1;
      if(b.net_after_quote_raw==null)return -1;
      const x=BigInt(a.net_after_quote_raw),y=BigInt(b.net_after_quote_raw);
      return x===y?0:x>y?-1:1;
    });

    res.setHeader('cache-control','no-store');
    res.status(200).json({
      ok:true,
      agent:'FLASHBOT-CLOUD-V4',
      evidence_level:'ONCHAIN_SINGLE_BLOCK_PLUS_EXACT_UNISWAP_QUOTE',
      head_block:block,
      user,
      flash_loan_premium_bps:premium.bps,
      safety_buffer_bps:Number(SAFETY_BUFFER_BPS),
      account:acct,
      evaluated,
      final_verdict:evaluated.some(x=>x.verdict==='NEEDS_ATOMIC_TX_SIMULATION')?'CANDIDATE_EXISTS_BUT_NOT_EXECUTABLE_YET':'NO_EXECUTABLE_CANDIDATE',
      execute:false,
      observed_at
    });
  }catch(e){
    res.status(502).json({ok:false,error:String(e?.message||e),details:e?.details||null,observed_at});
  }
}
