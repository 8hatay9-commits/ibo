# Chain Hunter Cloud Agent Status

Updated: 2026-08-20

## Safety mode
- READ_ONLY_VERIFIED
- wallet signing: disabled
- transaction broadcast: disabled
- no private keys or secrets in repo

## Implemented
- Base mainnet RPC failover: standard + Flashblocks
- /api/live: chain id, current block, gas price
- /api/aave-near: recent Aave Borrow discovery, getUserAccountData health-factor scoring
- dual-source liquidation proof: latest state on standard RPC plus pending state on Flashblocks RPC
- only accounts with HF < 1 on both sources enter verified_liquidatable_now

## Canonical Aave Base evidence
- Pool: 0xA238Dd80C259a72e81d7e4664a9801593F98d1c5
- Borrow topic: 0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0
- getUserAccountData selector: 0xbf92857c

## Deployment state
Vercel deployment creation requests are accepted, but the connected Vercel read API currently returns 404 for the created deployment IDs. Do not claim the endpoint is live until it can be independently fetched and verified.

## Next gates
1. Independently fetch deployed /api/live and prove chain_id=8453 with a current block.
2. Fetch /api/aave-near and record verified_liquidatable_now.
3. Add exact liquidation economics: close factor, reserve liquidation bonus/protocol fee, flash premium, collateral->debt quote, gas/L1 fee.
4. Add atomic eth_simulateV1 transaction simulation.
5. Keep broadcast disabled unless the execution layer is separately authorized and safely provisioned.
