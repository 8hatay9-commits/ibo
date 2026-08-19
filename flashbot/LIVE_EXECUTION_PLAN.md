# Live execution gate

Status: PREPARE LIVE, broadcast disabled until all gates pass.

1. Dedicated execution wallet only; private key stays local on PC and is never sent by Gmail/GitHub/ChatGPT.
2. Deploy atomic executor contract on Base. Executor must repay Aave principal + runtime flash-loan premium in the same transaction or revert.
3. Candidate must be simulated against pending/preconfirmed state before broadcast.
4. Profit gate must include: DEX fees, Aave premium, Base L2 execution fee, Base L1 security/data fee, slippage buffer, state-staleness buffer, and a minimum-profit floor.
5. Hard controls: target/router allowlist, token allowlist, maximum gas budget, maximum notional, daily loss cap, kill switch, nonce lock, one live tx at a time.
6. Start with very small gas funding and a capped notional; scale only after observed on-chain results match simulation.
7. Do not sandwich users. Backrun/arb only.

Current system remains dry-run until the local execution wallet and atomic executor contract exist and are verified.
