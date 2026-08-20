# IBO Live Scanner — Persistent System State

Updated: 2026-08-20

## Goal
Run a cloud-hosted, PC-free, read-only Base mainnet scanner with a live health endpoint and dashboard. No private keys, signing, or transaction broadcast until proof gates are satisfied.

## Canonical repository
- Repository: `8hatay9-commits/ibo`
- Branch: `main`
- Cloud v4 scanner was merged from PR #7.
- Merge commit: `8aa7145c73af85700e9702f9222d13fe3f3d4fa3`

## Canonical app
- Source: `flashbot/cloud-v4/api/index.js`
- Package: `flashbot/cloud-v4/package.json`
- Vercel config: `flashbot/cloud-v4/vercel.json`
- Intended endpoints: `/api/health`, `/api/aave`, `/api/verify`, `/api/dashboard`.
- Base chain ID expected: `8453`.
- Mode: `READ_ONLY_PROOF_FIRST`.
- Signing: disabled.
- Broadcast: disabled.

## Zero-backend fallback dashboard
A browser-only live Base health dashboard now exists at `live/index.html`.
It does not require GitHub Actions, Vercel, Render, or any server-side runtime.
The page queries live Base JSON-RPC directly every 15 seconds with failover across:
- `https://mainnet.base.org`
- `https://mainnet-preconf.base.org`
- `https://base-rpc.publicnode.com`
It proves chain ID, block number, gas price, RPC latency, selected RPC, observation timestamp, and keeps signing/broadcast disabled.
Latest dashboard commit: `55344f48ca692acf1fe5e29f7d4cbcd7533dd03c`.
This is a fallback health surface, not a replacement for the full `/api/aave` server-side scanner.

## GitHub Actions incident
Multiple workflows failed before any step started. Jobs returned zero steps and log download returned `BlobNotFound`. This means failures occurred at GitHub hosted-runner/job provisioning level, before checkout/scripts/RPC code executed.

Affected workflows were converted to manual/read-only to stop failure spam:
- `.github/workflows/live-rpc-probe.yml`
- `.github/workflows/hash-v396.yml`
- `.github/workflows/base-live-proof-v2.yml`
- `.github/workflows/read-only-profit-scan.yml`

Relevant cleanup commits:
- `0425f7f60a930e29795da3ed40a8dd984a9713a4`
- `9b7dc8618c41aabe5f3f50c8fa030b7be93e5738`
- `9ec242627c651190778a6bb6f998284a1aa5ce60`
- `352089490bcf0401e02d4511e864978839661937`

Do NOT make the production service depend on GitHub Actions unless runner provisioning is independently proven healthy.

## Vercel incident
Connected Vercel team: `8hatay9-9554s-projects` (`team_QdLiIFCRto7ARsx42NDlbzcH`). At investigation time, the team listed zero projects. The old `live-chain-agent-...vercel.app` hostname failed DNS resolution. Treat that URL as dead/unverified.

The available Vercel deploy connector currently rejects deployment because its backend expects `target`, `name`, and `files`, while the exposed tool schema accepts no arguments. Do not claim a Vercel deployment succeeded until a real project/deployment ID and externally fetched endpoint exist.

## Gmail evidence channel
GitHub CI notification emails arrive in the connected Gmail inbox. These confirmed failures such as Hash V396 and Base Live Proof V2 dying in 2–4 seconds before steps began. Gmail is evidence/notification only, not the compute plane.

## Next execution objective
1. Use the zero-backend dashboard as the immediate live Base health surface.
2. Obtain a cloud deploy surface that can actually be written from the current tool environment (Vercel once create/deploy API is usable, Cloudflare if connected, or another connected hosting provider).
3. Deploy the canonical `flashbot/cloud-v4` app without GitHub Actions.
4. Independently fetch `/api/health`.
5. Accept production only if response proves `chainId: 8453`, current block number, gas price, RPC latency, timestamp, and `signingEnabled:false`, `broadcastEnabled:false`.
6. Then verify `/api/aave` and dashboard.

## Truth rule
Never report LIVE/PASS from configuration alone. LIVE requires an externally fetched HTTP response from the deployed endpoint with current Base mainnet evidence.