# FLASHBOT CLOUD V5.1 CHECKPOINT

Mode: READ_ONLY
Execution: DISABLED
Signing: DISABLED
Principle: NO EVIDENCE = NO CLAIM

## Runtime
Production alias: https://live-chain-agent-8hatay9-9554s-projects.vercel.app
Deployment created through the connected Vercel deployment tool.

## Endpoints
- `/api/live` — Base, Ethereum, Arbitrum chain ID/block/gas with RPC failover.
- `/api/selftest` — offline ABI/topic/pool sanity checks with evidence SHA-256.
- `/api/verify_user?user=0x...` — Aave Base `getUserAccountData` + live flash-loan premium; does not infer profitability.
- `/api/aave_scan?lookback=3000&max_users=100` — scans recent Aave Borrow events, deduplicates borrowers, batches HF reads, reports HF<1 and near-liquidation accounts.

## Evidence rules
Every response is wrapped with `kind`, `observed_at`, `payload`, `meta`, and `evidence_sha256`.
An HF<1 account is not called profitable. Execution stays disabled until reserve-level collateral/debt reconstruction, exact swap quote, flash premium, L2 gas, L1 data fee, competition/MEV cost, and atomic simulation all pass.

## Verified locally
- Node syntax check: PASS
- Compact self-test: PASS (calldata, HF decode, Borrow topic format, Aave Pool format)
- Combined legacy + new local suite: PASS

## Current blocker
The connected Vercel deployment creation tool returns valid deployment IDs/URLs, but the separate Vercel project/deployment lookup connector currently returns 404 for those IDs. External endpoint verification is scheduled separately and must be treated as authoritative before claiming the production endpoint is live.
