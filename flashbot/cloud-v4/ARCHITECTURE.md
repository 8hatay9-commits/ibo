# FLASHBOT-CLOUD-V4

Cloud-native, evidence-first on-chain opportunity engine designed to be controlled from ChatGPT without a local PC.

## Non-negotiable rules

1. `EXECUTE` is impossible without exact state-dependent simulation.
2. Every opportunity carries chain, block, protocol, route, inputs, fees, gas, slippage buffer, flash premium, and expected net profit.
3. A model opinion is never evidence. RPC state, contract calls, quotes, simulation results, receipts and balances are evidence.
4. Live signing/broadcast remains disabled until a separate execution gate is proven.
5. Private keys must never be committed to GitHub or placed in chat.

## Runtime shape

ChatGPT -> cloud API -> RPC quorum -> scanners -> verifier -> opportunity object.

The cloud API is stateless so it can run on serverless infrastructure. Durable state can be added later without changing the opportunity schema.

## Phase 1 implemented

- Base mainnet live health endpoint.
- Aave V3 flash-loan premium read from chain.
- Recent Borrow-event discovery.
- `getUserAccountData()` live health-factor polling.
- Liquidatable and near-liquidation classification.
- RPC fallback, timeout and latency evidence.

## Next phases

- Exact Aave user reserve decomposition.
- Collateral/debt asset selection and close-factor calculation.
- DEX venue adapters for Uniswap V3 and Aerodrome Slipstream/V2.
- Atomic liquidation path simulation: flash borrow -> liquidationCall -> collateral swap -> flash repayment.
- Deterministic net-profit verifier.
- Multi-chain adapter interface.
- Independent second-RPC verification for every executable verdict.
- Signed execution gateway only after simulation and safety gates are proven.
