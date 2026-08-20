import {ethCall,decodeWords,encAddress} from './base.js';
export const UNISWAP_V3_QUOTER_V2='0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a';
const QUOTE_EXACT_INPUT_SINGLE='0xc6a5026a';
const FEE_TIERS=[100,500,3000,10000];
const encUint=x=>BigInt(x).toString(16).padStart(64,'0');
export function encodeQuoteExactInputSingle(tokenIn,tokenOut,amountIn,fee,sqrtPriceLimitX96=0n){return QUOTE_EXACT_INPUT_SINGLE+encAddress(tokenIn)+encAddress(tokenOut)+encUint(amountIn)+encUint(fee)+encUint(sqrtPriceLimitX96)}
export async function quoteUniswapV3Single(tokenIn,tokenOut,amountIn,block='latest',feeTiers=FEE_TIERS){const quotes=[];for(const fee of feeTiers){try{const data=encodeQuoteExactInputSingle(tokenIn,tokenOut,amountIn,fee,0n);const{result,rpc,latency_ms}=await ethCall(UNISWAP_V3_QUOTER_V2,data,block);const w=decodeWords(result);if(w.length<4)throw new Error('short QuoterV2 response');quotes.push({venue:'uniswap_v3',fee,amount_out_raw:w[0].toString(),sqrt_price_x96_after:w[1].toString(),initialized_ticks_crossed:Number(w[2]),quoter_gas_estimate:w[3].toString(),rpc,latency_ms})}catch(e){quotes.push({venue:'uniswap_v3',fee,error:String(e?.message||e)})}}const valid=quotes.filter(q=>!q.error&&BigInt(q.amount_out_raw)>0n).sort((a,b)=>BigInt(a.amount_out_raw)===BigInt(b.amount_out_raw)?0:BigInt(a.amount_out_raw)>BigInt(b.amount_out_raw)?-1:1);return{best:valid[0]||null,quotes}}
