# Flashbot Searcher Architecture

Status: research/dry-run first. No wallet secrets in this repository.

## Objective
Build an event-driven, multi-worker EVM searcher that discovers and simulates atomic arbitrage/liquidation opportunities and only hands a candidate to an execution layer after strict profitability and safety gates.

## Data plane
1. Historical backfill: factory/pool events with eth_getLogs; persist pool registry and deployment ranges.
2. Live Base feed: Flashblocks WebSocket subscriptions (`newFlashblocks`, `newFlashblockTransactions`, `pendingLogs`).
3. State cache: pool slot/reserve/tick state keyed by chain + block/flashblock payload.
4. Reorg/finality reconciliation: preconfirmed -> sealed -> safe/finalized state transitions.

## Search plane
- Directed multigraph of token/pool edges.
- 2-pool cross-DEX cycles.
- Triangular cycles.
- Multi-hop cycles with bounded hop count and liquidity/fee pruning.
- Stablecoin imbalance routes.
- Backrun-only post-swap opportunities.
- Aave liquidation opportunity research.
- Dynamic funding-source selection: Aave flashLoanSimple first; DEX-native flash where objectively cheaper and supported.

## Simulation plane
- Fast local quote/math pass.
- Pending-state RPC verification.
- Base `eth_simulateV1` bundle simulation against preconfirmed state.
- Foundry/Anvil fork regression suite for contracts and route execution.
- Reject on revert, stale state, insufficient repayment, or net profit below gate.

## Profit gate
Net = final asset value - principal - flash premium - DEX fees - estimated execution gas - L1 data fee - slippage buffer - safety buffer.

No candidate reaches live execution unless net is positive after every cost and configured minimum profit/risk thresholds are satisfied.

## Execution plane (later, isolated)
- Dedicated execution wallet only; never main wallet.
- Private key stays local on the PC, never Gmail/ChatGPT/GitHub.
- Contract target/spender allowlists.
- Max gas budget, max notional, daily loss cap, kill switch.
- Atomic repayment-or-revert.
- Profit beneficiary configured separately from controller transport.

## Worker model
- feed-worker: WebSocket ingestion.
- registry-worker: historical/event-driven pool discovery.
- state-worker: state/tick/reserve cache.
- route-workers: CPU-parallel graph search and sizing.
- simulation-workers: concurrent RPC/Anvil simulation.
- controller: Gmail high-level commands and status only.
- executor: disabled until explicit live authorization.

## Non-goals
- No sandwiching users.
- No secret material in email or repository.
- No blind broadcasting based on quoted price alone.
- No claim of guaranteed profit.
