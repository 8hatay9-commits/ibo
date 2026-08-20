const C = Object.freeze({
  chain: 'base',
  chainId: 8453,
  rpcs: [
    'https://mainnet.base.org',
    'https://mainnet-preconf.base.org',
    'https://base-rpc.publicnode.com'
  ],
  aavePool: '0xA238Dd80C259a72e81d7e4664a9801593F98d1c5',
  borrowTopic: '0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0',
  userDataSel: 'bf92857c',
  defaultWindow: 300,
  chunk: 150,
  maxBorrowers: 80,
  concurrency: 6,
  nearHf: 1.08,
  timeoutMs: 6000
});

let rpcId = 0;

function timeoutSignal(ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  return { signal: controller.signal, clear: () => clearTimeout(timer) };
}

export async function rpc(method, params = [], timeoutMs = C.timeoutMs) {
  const errors = [];
  for (const url of C.rpcs) {
    const t = Date.now();
    const to = timeoutSignal(timeoutMs);
    try {
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json', 'user-agent': 'ibo-live-scanner/1.0' },
        body: JSON.stringify({ jsonrpc: '2.0', id: ++rpcId, method, params }),
        signal: to.signal,
        cache: 'no-store'
      });
      if (!r.ok) throw new Error(`HTTP_${r.status}`);
      const j = await r.json();
      if (j.error) throw new Error(j.error.message || JSON.stringify(j.error));
      return { result: j.result, ms: Date.now() - t, url };
    } catch (e) {
      errors.push(`${url}:${String(e?.message || e)}`);
    } finally {
      to.clear();
    }
  }
  throw new Error(`RPC_FAIL ${method} :: ${errors.join(' | ')}`);
}

const h2n = h => Number(BigInt(h));
const n2h = n => `0x${BigInt(n).toString(16)}`;

function addressWord(a) {
  const h = String(a).toLowerCase().replace(/^0x/, '');
  if (!/^[0-9a-f]{40}$/.test(h)) throw new Error('INVALID_ADDRESS');
  return h.padStart(64, '0');
}

function words(x) {
  const h = String(x || '0x').replace(/^0x/, '');
  if (!h || h.length % 64) return [];
  const out = [];
  for (let i = 0; i < h.length; i += 64) out.push(BigInt(`0x${h.slice(i, i + 64)}`));
  return out;
}

function borrower(log) {
  const t = log?.topics || [];
  if (t.length < 3) return null;
  const h = String(t[2]).replace(/^0x/, '');
  return /^[0-9a-fA-F]{64}$/.test(h) ? `0x${h.slice(-40).toLowerCase()}` : null;
}

async function mapLimit(items, limit, fn) {
  if (!items.length) return [];
  const out = new Array(items.length);
  let cursor = 0;
  async function worker() {
    while (true) {
      const i = cursor++;
      if (i >= items.length) return;
      out[i] = await fn(items[i], i);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return out;
}

async function userData(user) {
  const { result, ms, url } = await rpc('eth_call', [{ to: C.aavePool, data: `0x${C.userDataSel}${addressWord(user)}` }, 'latest']);
  const w = words(result);
  if (w.length < 6) throw new Error('BAD_USER_DATA');
  return {
    user,
    totalCollateralUsd: Number(w[0]) / 1e8,
    totalDebtUsd: Number(w[1]) / 1e8,
    availableBorrowsUsd: Number(w[2]) / 1e8,
    liquidationThresholdBps: Number(w[3]),
    ltvBps: Number(w[4]),
    healthFactor: w[5] === (2n ** 256n - 1n) ? null : Number(w[5]) / 1e18,
    rpcLatencyMs: ms,
    rpcUrl: url
  };
}

export async function health() {
  const [ch, b, g] = await Promise.all([
    rpc('eth_chainId'),
    rpc('eth_blockNumber'),
    rpc('eth_gasPrice')
  ]);
  const chainId = h2n(ch.result);
  return {
    ok: chainId === C.chainId,
    mode: 'READ_ONLY_PROOF_FIRST',
    chain: C.chain,
    chainId,
    blockNumber: h2n(b.result),
    gasPriceWei: BigInt(g.result).toString(),
    rpcLatencyMs: { chain: ch.ms, block: b.ms, gas: g.ms },
    rpc: { chain: ch.url, block: b.url, gas: g.url },
    signingEnabled: false,
    broadcastEnabled: false,
    observedAt: new Date().toISOString()
  };
}

export async function scan(windowBlocks = C.defaultWindow) {
  const safeWindow = Math.max(120, Math.min(600, Number(windowBlocks) || C.defaultWindow));
  const head = h2n((await rpc('eth_blockNumber')).result);
  const start = Math.max(0, head - safeWindow + 1);
  const logs = [];

  for (let from = start; from <= head; from += C.chunk) {
    const to = Math.min(head, from + C.chunk - 1);
    const { result } = await rpc('eth_getLogs', [{
      address: C.aavePool,
      fromBlock: n2h(from),
      toBlock: n2h(to),
      topics: [C.borrowTopic]
    }], 9000);
    logs.push(...(result || []));
  }

  const seen = new Map();
  for (const g of logs) {
    const u = borrower(g);
    if (!u) continue;
    const b = h2n(g.blockNumber || '0x0');
    if (b >= (seen.get(u) || 0)) seen.set(u, b);
  }

  const borrowers = [...seen.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, C.maxBorrowers)
    .map(([user, lastBorrowBlock]) => ({ user, lastBorrowBlock }));

  const states = await mapLimit(borrowers, C.concurrency, async x => {
    try {
      return { ...x, ...(await userData(x.user)) };
    } catch (e) {
      return { ...x, error: String(e?.message || e) };
    }
  });

  const valid = states
    .filter(x => Number.isFinite(x.healthFactor) && x.totalDebtUsd > 0)
    .sort((a, b) => a.healthFactor - b.healthFactor);

  return {
    ok: true,
    type: 'AAVE_LIQUIDATION_RADAR',
    chain: C.chain,
    chainId: C.chainId,
    head,
    start,
    windowBlocks: safeWindow,
    borrowLogCount: logs.length,
    uniqueBorrowers: borrowers.length,
    checked: states.length,
    errors: states.filter(x => x.error).length,
    liquidatable: valid.filter(x => x.healthFactor < 1).slice(0, 25),
    near: valid.filter(x => x.healthFactor >= 1 && x.healthFactor < C.nearHf).slice(0, 25),
    lowest: valid.slice(0, 25),
    signingEnabled: false,
    broadcastEnabled: false,
    observedAt: new Date().toISOString()
  };
}

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'access-control-allow-origin': '*'
    }
  });
}
