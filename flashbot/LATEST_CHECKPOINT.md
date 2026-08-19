# Flashbot Latest Checkpoint

Updated: 2026-08-19 07:13:24 +03:00
Host: DESKTOP-431STAP
Controller: FLASHBOT-CONTROLLER-V3
Mode: DRY_RUN_ONLY
Live trading: DISABLED
Broadcast: DISABLED
Gas budget: USD 50
Profit target: USD 10,000 (goal, not guarantee)
Verified profit: USD 0

## Binding rules
- No lies and no hallucinated success. Unknown facts must be verified or reported unknown.
- Real success metric is verified net USD profit, not pool/candidate/log counts.
- Do not spend the scarce USD 50 gas budget on blind deployment, reverts, or unverified execution.
- Keep signing/private keys local to the PC when the execution layer is eventually enabled; never put private keys in Gmail, GitHub, or chat.

## Current verified runtime
- Active release: v3.8.4
- Engine: FLASHBOT-PRODUCTION-V3.8.4
- Daemon: RUNNING, PID 14344, started 2026-08-19 07:12:55 +03:00
- Backfill: STOPPED to prioritize live search
- Feed: HTTP_PENDING_SWAP_LOGS_ADAPTIVE_DECOUPLED_V37
- Connected: true
- Pool count: 1,801,027
- Feed RPC latency: 209.06 ms
- Feed target: 220 ms
- Queue policy: LATEST_STATE_COALESCE_CAP1
- Queue depth: 1
- Last error: null
- PancakeSwap V3 enabled: true
- Cost gate: V37_CONSERVATIVE_L1_L2_ESTIMATE
- WSS on this host/path remains disabled after V3.6.1 diagnostics returned Cloudflare HTTP 405; Base Flashblocks HTTP pending Swap-log fallback is active.

## V3.8 progression
- V3.8.2 added a self-supervisor so the daemon can restart its worker after crashes with backoff/crash-loop protection.
- V3.8.2 exposed a critical FIFO problem: queue depth hit 256 and 397 feed batches were dropped while stale pending state accumulated.
- V3.8.3 changed the feed queue to capacity 1 with latest-state coalescing. Verified queue depth fell to 1 while feed latency stayed around 216-232 ms.
- V3.8.3 then exposed the next bottleneck: known pool hits occurred but route generation/quoting was too slow on the 1.8M-pool SQLite registry.
- V3.8.4 bounded topology fanout and shortened the route requote TTL while preserving the queue/supervisor architecture.
- First verified V3.8.4 status (29 seconds after start): 75 feed messages, 8 processed logs, 1 known-pool hit, 48 structural candidates, 6 exact quote attempts, queue depth 1, last_error null.
- Best V3.8.4 edge in that first sample: -5.0549 bps gross on a 2-pool Uniswap V3 USDC/WETH round trip; after the 5 bps Aave flash premium it was -10.0549 bps before gas. Not profitable and must not be executed.

## Next engineering priority
Use pending Swap-event state as a cheap price/edge prefilter so the engine does not spend SQLite/RPC work on routes that cannot plausibly clear fees. Exact on-chain quoting and atomic simulation remain the correctness gate. Prioritize fresh state over breadth; stale pending-state work has no MEV value.

## Financial safety gate
Do not enable wallet signing, live broadcast, or spend the USD 50 gas budget until a candidate passes all of:
1. exact executor calldata/contract
2. exact/credible Base L2 execution gas
3. L1 security/data fee
4. slippage + safety buffer
5. atomic pending-state simulation via eth_simulateV1 or equivalent verified method
6. net positive after flash premium and all costs

Large flash-loan notionals may be simulated, but larger notional is not automatically more profitable. No live flash borrowing/execution until this gate passes and the user explicitly confirms live execution.

## Context continuity
This file plus MASTER_STATE.json / MASTER_STATE.md and Gmail FLASHBOT result messages are canonical context. If a ChatGPT thread freezes or becomes too long, load these sources and continue from the latest verified checkpoint instead of reconstructing from memory or asking the user where the project stopped.
