# Flashbot Latest Checkpoint

Updated: 2026-08-19 06:42:14 +03:00
Host: DESKTOP-431STAP
Controller: FLASHBOT-CONTROLLER-V3
Mode: DRY_RUN_ONLY
Live trading: DISABLED
Gas budget: USD 50
Profit target: USD 10,000 (goal, not guarantee)
Verified profit: USD 0

## Current verified runtime
- Active release: v3.7.1
- Engine: FLASHBOT-PRODUCTION-V3.7.1
- Daemon: RUNNING, PID 12468, started 2026-08-19 06:41:02 +03:00
- Backfill: RUNNING, PID 11048, started 2026-08-19 06:40:26 +03:00
- Feed: HTTP_PENDING_SWAP_LOGS_ADAPTIVE_DECOUPLED_V37
- Connected: true
- Pool count: 1,796,507
- Feed RPC latency: 228.63 ms
- Feed target: 220 ms
- Queue depth: 120
- Last error: null
- PancakeSwap V3 enabled: true
- Cost gate: V37_CONSERVATIVE_L1_L2_ESTIMATE
- WSS on this host/path: disabled after V3.6.1 diagnostic confirmed Cloudflare HTTP 405; HTTP Flashblocks fallback is active.

## Latest engineering facts
- V3.7.0 probe passed Pancake factory/quoter bytecode, Base GasPriceOracle L1 upper-bound fee call, fast pending-log HTTP polling, and eth_simulateV1.
- V3.7.1 fixed cross-thread SQLite access.
- V3.7.2/V3.7.3 fast-route experiment is NOT production-safe yet; startup wrapper failed and was rolled back.
- Last useful V3.7.1 search before rollback reached 25 exact quote attempts and best observed gross edge -2.2106 bps on a 2-pool Uniswap V3 USDC/WETH round trip; after 5 bps Aave flash premium it was still negative before gas. No profit claim.
- Current bottleneck: feed can outrun quote worker; queue/backpressure/route-search throughput must be improved without stopping stable scanning.

## Financial safety gate
Do not enable wallet signing, live broadcast, or spend the USD 50 gas budget until a candidate passes:
1. exact executor calldata/contract
2. exact/credible L2 execution gas
3. L1 security/data fee
4. slippage + safety buffer
5. atomic pending-state simulation
6. net positive after flash fee and all costs

Large flash-loan notionals may be simulated (up to available liquidity and price-impact limits), but larger notional is not automatically more profitable. Live flash borrowing/execution remains disabled until the gate passes and the user explicitly confirms live execution.

## Context continuity
This file plus MASTER_STATE.json / MASTER_STATE.md and Gmail FLASHBOT result messages are canonical context. If a ChatGPT thread freezes or becomes too long, start a new chat and load these sources rather than reconstructing from memory or asking the user where the project stopped.
