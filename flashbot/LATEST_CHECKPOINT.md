# Flashbot Latest Checkpoint

Updated: 2026-08-19 07:37:39 +03:00
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

## Current verified dual runtime
- Search engine: FLASHBOT-PRODUCTION-V3.8.4
- Arbitrage daemon: RUNNING, PID 4560, started 2026-08-19 07:37:00 +03:00
- Aave liquidation watcher: RUNNING as controller backfill process, PID 17300, started 2026-08-19 07:35:49 +03:00
- Release carrying watcher: v3.9.0, SHA-verified by controller
- Feed: HTTP_PENDING_SWAP_LOGS_ADAPTIVE_DECOUPLED_V37
- Pool count: 1,801,027
- Queue policy: LATEST_STATE_COALESCE_CAP1
- Queue depth: 1
- Latest feed RPC latency: 229.98 ms
- Daemon last_error: null
- Watcher last_error: null

## Arbitrage lane
- Latest verified restart sample: 74 feed messages, 97 logs, 24 known-pool hits, 218 structural candidates, 3 exact quote attempts.
- No gross-positive candidate and no positive-after-flash candidate.
- Best current observed edge: -4.9185 bps gross on a 2-pool Uniswap V3 USDC/WETH round trip; after 5 bps Aave premium it is -9.9185 bps before gas. Not executable.

## Aave liquidation lane
- Batched borrower discovery scans recent 12,000 Base blocks and pending-state account data.
- Watcher refresh #2 had 349 recent Borrow events and had completed 291 live HF polls with zero liquidatable positions and no error.
- Lowest current HF: 1.0099971529 for 0x6a2cc7efa2c5d91c45411d956358928158262a19. This user has ~0.0750 WETH collateral and ~0.06164 WETH debt; economically small.
- Most economically interesting near-liquidation account: 0x9f9ff4ffdf0b16dd096f649586e882d88a9bf1c0, HF 1.0319272236, 35.3459169922 cbETH collateral and 37.0104394404 WETH debt.
- The cbETH collateral liquidation bonus is 7.5%; protocol fee is 10% of the bonus, giving an estimated effective liquidator bonus of 6.75% before flash premium, swap/slippage, L1/L2 gas, and competition.
- If that account becomes liquidatable while HF remains above 0.95, Aave V3 close factor is 50%; approximate debt cover is USD 35.35k and gross liquidator bonus is about USD 2.386k before execution costs. This is a conditional opportunity, not current profit.
- If HF falls to or below 0.95, Aave V3 source code permits a 100% close factor; still requires exact pending-state simulation and execution-cost proof.
- Third tracked account: 0xfeee2af72cd54577526a3e8a6508a9d8d0942fb8, HF ~1.04665, ~4981.29 USDC collateral and ~3712.23 USDC debt, effective bonus estimate 4.5%; smaller but may be economically viable if it crosses HF < 1.
- Current liquidatable_now count: 0. No liquidation should be broadcast.

## Financial safety gate
Do not enable wallet signing, live broadcast, or spend the USD 50 gas budget until a candidate passes all of:
1. exact executor calldata/contract
2. exact/credible Base L2 execution gas
3. L1 security/data fee
4. slippage + safety buffer
5. atomic pending-state simulation
6. net positive after flash premium and all costs

## Next engineering priorities
1. Keep arbitrage daemon and liquidation watcher running in parallel.
2. Add liquidation-specific atomic simulation path: flash-borrow debt asset -> Aave liquidationCall -> seize collateral -> exact swap to debt asset -> repay flash loan -> compute final net USD.
3. Only after this path is proven net-positive should isolated signing/live broadcast be considered.

## Context continuity
This file plus MASTER_STATE.json / MASTER_STATE.md and Gmail FLASHBOT result messages are canonical context. If a ChatGPT thread freezes or becomes too long, load these sources and continue from this checkpoint instead of reconstructing from memory or asking the user where the project stopped.
