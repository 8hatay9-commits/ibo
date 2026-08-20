# IBO Live Scanner — Persistent System State

Updated: 2026-08-20

## Goal
Run a cloud-hosted, PC-free, read-only Base mainnet/Aave scanner with a live health endpoint, persistent latest opportunities, scheduled scans, and dashboard. No private keys, signing, or transaction broadcast until proof gates are satisfied.

## Canonical repository
- Repository: `8hatay9-commits/ibo`
- Branch: `main`
- Cloud v4 scanner merged from PR #7.
- Original Cloud v4 merge commit: `8aa7145c73af85700e9702f9222d13fe3f3d4fa3`
- Latest Netlify-ready dashboard/backend commit: `5e74d76af4a8bbabd9d641f9c88aed5593803239`

## Canonical read-only rules
- Base chain ID expected: `8453`.
- Mode: `READ_ONLY_PROOF_FIRST`.
- Signing: disabled.
- Broadcast: disabled.
- Never claim a transaction was executed unless a future signing/broadcast layer is explicitly added and independently proven.

## Netlify cloud runtime — CURRENT DEPLOY TARGET
The repository is now prepared for a Netlify deploy that does not use GitHub Actions as its runtime.

Root config:
- `package.json` — installs `@netlify/blobs`.
- `netlify.toml` — publishes `live/`, configures Functions, API redirects, and a scheduled scanner every 2 minutes.

Functions:
- `netlify/functions/_core.mjs` — Base JSON-RPC failover/retries/timeouts + Aave Borrow-event/user-health scan core.
- `netlify/functions/health.mjs` — `/api/health`.
- `netlify/functions/scan-now.mjs` — `/api/scan` manual/on-demand scan and persistence.
- `netlify/functions/opportunities.mjs` — `/api/opportunities`, reads persistent latest result from Netlify Blobs.
- `netlify/functions/scheduled-scan.mjs` — scheduled scan every 2 minutes and persists result to Netlify Blobs.

RPC failover order:
1. `https://mainnet.base.org`
2. `https://mainnet-preconf.base.org`
3. `https://base-rpc.publicnode.com`

Aave Pool:
- `0xA238Dd80C259a72e81d7e4664a9801593F98d1c5`

Scanner safety/rate controls:
- Recent-block window defaults to 300 and is capped at 600.
- Log chunks: 150 blocks.
- Max recent borrowers checked: 80.
- Health-factor concurrency: 6.
- Near-liquidation threshold: HF < 1.08.
- Liquidatable: HF < 1.
- No signing or broadcast code.

Persistent state:
- Netlify Blobs store: `flashbot-state`.
- Key: `latest-scan`.

Dashboard:
- `live/index.html` now calls `/api/health`, `/api/opportunities`, and `/api/scan?blocks=300` rather than being only a browser-direct RPC proof page.

Important: the Netlify code is DEPLOY-READY but is not yet allowed to be called LIVE until a real `*.netlify.app` production deployment is created and externally verified.

## Netlify deployment requirement
Netlify can deploy a public GitHub repository via its official Deploy to Netlify flow. The only unavoidable user-side step is authenticating/authorizing the hosting account/GitHub access because this ChatGPT session has no connected Netlify write credential. Once authorization is completed, Netlify should read the root `netlify.toml` and deploy the functions/site.

Production acceptance test after deploy:
1. Fetch `/api/health` and require `ok:true`, `chainId:8453`, advancing block number, gas price, RPC latency, timestamp, `signingEnabled:false`, `broadcastEnabled:false`.
2. Fetch `/api/scan?blocks=300` and require a valid Aave scan response.
3. Fetch `/api/opportunities` and require persisted scan state.
4. Wait for scheduled scanner and confirm `observedAt`/head updates without a manual scan.
5. Only after these checks call the service LIVE.

## GitHub Actions incident
Multiple workflows failed before any step started. Jobs returned zero steps and log download returned `BlobNotFound`. The run API showed normal workflow creation but job records had no steps/logs, indicating failure at runner/job provisioning rather than application scripts.

Affected workflows were converted to manual/read-only to stop failure spam:
- `.github/workflows/live-rpc-probe.yml`
- `.github/workflows/hash-v396.yml`
- `.github/workflows/base-live-proof-v2.yml`
- `.github/workflows/read-only-profit-scan.yml`

Do NOT make production depend on GitHub Actions until runner provisioning is independently proven healthy.

## Vercel incident
Connected Vercel team: `8hatay9-9554s-projects` (`team_QdLiIFCRto7ARsx42NDlbzcH`). At investigation time it listed zero projects. The deploy connector exposes a no-argument schema while its backend requires `target`, `name`, and `files`, so direct deployment cannot currently be completed through that connector. Treat old Vercel URLs as dead/unverified until a real project/deployment exists.

## Render incident
A Render Blueprint config was added, but the user's Render Blueprint page rendered as a white screen in the in-app browser. Render is not the current preferred deployment path.

## Gmail evidence channel
GitHub CI notifications arrive in connected Gmail. Gmail is evidence/notification only, not the compute plane.

## Truth rule
Never report LIVE/PASS from configuration, commit success, or a dashboard file alone. LIVE requires an externally fetched production endpoint with current Base mainnet evidence and a verified scheduled scan update.