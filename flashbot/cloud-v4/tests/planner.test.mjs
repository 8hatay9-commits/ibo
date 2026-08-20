import assert from 'node:assert/strict';
import { planLiquidations } from '../lib/planner.js';

function acct(hf,totalDebtBase='1000000000000'){return{health_factor_raw:String(hf),total_debt_base:String(totalDebtBase)}}
function pos(over={}){return{asset:'0x0000000000000000000000000000000000000001',decimals:6,a_token_balance_raw:'1000000000',debt_raw:'1000000000',collateral_enabled:true,emode_collateral_enabled:false,oracle_price_raw:'100000000',liquidation_bonus_bps:10500,effective_liquidation_bonus_bps:10500,liquidation_protocol_fee_bps:1000,flash_loan_enabled:true,...over}}

{
  const p=planLiquidations(acct(940000000000000000n),{positions:[pos({a_token_balance_raw:'2000000000',debt_raw:'0'}),pos({asset:'0x0000000000000000000000000000000000000002',a_token_balance_raw:'0',debt_raw:'1000000000'})]},5);
  assert.equal(p.liquidatable,true);
  assert.ok(p.plans.length>0);
  assert.equal(p.plans[0].execute,false);
  assert.equal(p.plans[0].simulation_required,true);
}
{
  const c=pos({a_token_balance_raw:'5000000000000',debt_raw:'0'}),d=pos({asset:'0x0000000000000000000000000000000000000002',a_token_balance_raw:'0',debt_raw:'4000000000000'});
  const p=planLiquidations(acct(980000000000000000n,'400000000000000'),{positions:[c,d]},5);
  assert.equal(p.liquidatable,true);
  assert.ok(p.plans.length>0);
  assert.equal(p.plans[0].execute,false);
}
{
  const p=planLiquidations(acct(1000000000000000000n),{positions:[pos()]},5);
  assert.equal(p.liquidatable,false);
  assert.equal(p.plans.length,0);
}
console.log('planner tests: PASS');
