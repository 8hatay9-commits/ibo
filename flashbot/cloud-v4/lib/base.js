export const RPCS=['https://mainnet.base.org','https://mainnet-preconf.base.org'];
export const AAVE_POOL='0xA238Dd80C259a72e81d7e4664a9801593F98d1c5';
export const BORROW_TOPIC='0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0';
export const GET_USER_ACCOUNT_DATA='0xbf92857c';
export const FLASH_PREMIUM_TOTAL='0x074b2e43';
let rpcId=0;
export async function rpc(method,params=[],{timeoutMs=7000}={}){const errors=[];for(const url of RPCS){const c=new AbortController();const t=setTimeout(()=>c.abort(),timeoutMs);const started=Date.now();try{const r=await fetch(url,{method:'POST',headers:{'content-type':'application/json','user-agent':'flashbot-cloud-v4'},body:JSON.stringify({jsonrpc:'2.0',id:++rpcId,method,params}),signal:c.signal,cache:'no-store'});const text=await r.text();if(!r.ok)throw new Error(`HTTP ${r.status}: ${text.slice(0,160)}`);const j=JSON.parse(text);if(j.error)throw new Error(j.error.message||JSON.stringify(j.error));return{result:j.result,rpc:url,latency_ms:Date.now()-started}}catch(e){errors.push({rpc:url,error:String(e?.message||e)})}finally{clearTimeout(t)}}const err=new Error(`${method} failed on all RPCs`);err.details=errors;throw err}
export function toHex(n){return '0x'+BigInt(n).toString(16)}
export function hexInt(x){return Number(BigInt(x))}
export function encAddress(addr){const h=addr.toLowerCase().replace(/^0x/,'');if(!/^[0-9a-f]{40}$/.test(h))throw new Error('bad address');return h.padStart(64,'0')}
export function decodeWords(data){const h=String(data||'0x').replace(/^0x/,'');const out=[];for(let i=0;i+64<=h.length;i+=64)out.push(BigInt('0x'+h.slice(i,i+64)));return out}
export function wadString(x){const n=BigInt(x);const neg=n<0n;const a=neg?-n:n;const whole=a/1000000000000000000n;const frac=(a%1000000000000000000n).toString().padStart(18,'0').replace(/0+$/,'')||'0';return `${neg?'-':''}${whole}.${frac}`}
export function wadNumber9(x){return Number(BigInt(x)/1000000000n)/1e9}
export async function ethCall(to,data,block='latest'){return rpc('eth_call',[{to,data},block])}
export async function accountData(user,block='latest'){const{result,rpc:used,latency_ms}=await ethCall(AAVE_POOL,GET_USER_ACCOUNT_DATA+encAddress(user),block);const w=decodeWords(result);if(w.length<6)throw new Error('short getUserAccountData response');return{user:user.toLowerCase(),total_collateral_base:w[0].toString(),total_debt_base:w[1].toString(),available_borrows_base:w[2].toString(),liquidation_threshold:Number(w[3]),ltv:Number(w[4]),health_factor_raw:w[5].toString(),health_factor_decimal:wadString(w[5]),health_factor:wadNumber9(w[5]),rpc:used,latency_ms}}
export async function flashPremiumBps(block='latest'){const{result,rpc:used,latency_ms}=await ethCall(AAVE_POOL,FLASH_PREMIUM_TOTAL,block);const w=decodeWords(result);return{bps:w.length?Number(w[0]):null,rpc:used,latency_ms}}
