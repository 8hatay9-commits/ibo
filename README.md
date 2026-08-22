# Bounty Radar

Bounty Radar is a paid-signal MVP for developers and AI agents hunting GitHub bounties.

It scans live open GitHub issues containing bounty text, extracts dollar amounts, checks repository state, and ranks candidates using:

- payout size
- issue competition (comment count)
- freshness
- archived repository detection
- suspicious claim requirements that ask contributors/agents to expose hidden initialization or system instructions

## Monetization

The free endpoint returns the top 3 clean candidates. Premium returns up to 25 candidates plus full risk metadata.

Premium is sold for **30 days** through direct Ethereum checkout:

- **19 USDT** — USD₮ ERC-20 on Ethereum Mainnet
- **0.008 ETH** — native ETH on Ethereum Mainnet
- recipient: `0xDb12efE909Dc98e974e585A94c90DAa7c1c3D467`

The checkout never needs the recipient wallet private key. Buyers receive a signed payment quote, pay on-chain, then submit the transaction hash. The server verifies the mined transaction and returns a signed 30-day access token.

The official Ethereum USD₮ contract configured by the app is:

`0xdAC17F958D2ee523a2206206994597C13D831ec7`

## Payment flow

1. Buyer opens `/pay.html`.
2. Browser creates a random private claim code locally.
3. `/api/quote` signs the hash of that claim code and returns a 30-minute quote.
4. Buyer sends 19 USDT or 0.008 ETH on **Ethereum Mainnet** to the configured recipient.
5. Buyer pastes the Ethereum transaction hash.
6. `/api/verify-payment` checks the receipt and qualifying ETH/USDT transfer on-chain.
7. The buyer receives a signed access token valid for 30 days.
8. `/api/bounties` accepts that access token through `x-api-key`.

The claim-code binding prevents somebody who merely sees a public transaction hash from using it to claim access.

## Endpoints

- `GET /api/bounties` — ranked bounty feed
- `GET /api/config` — public product/payment configuration
- `POST /api/quote` — create signed payment quote
- `POST /api/verify-payment` — verify Ethereum payment and issue access token

Premium example:

```bash
curl -H "x-api-key: YOUR_PAID_ACCESS_TOKEN" https://YOUR_DEPLOYMENT/api/bounties
```

## Environment

- `GITHUB_TOKEN` — optional but recommended for higher GitHub API limits
- `PREMIUM_API_KEY` — owner/admin master key
- `ACCESS_TOKEN_SECRET` — long random HMAC secret used to sign quotes and paid access tokens
- `ETH_RPC_URL` — Ethereum mainnet RPC; when blank the app falls back to Cloudflare's public Ethereum RPC

No seed phrase or private wallet key is required anywhere.

## Deploy

The project is dependency-light. `index.html` and `pay.html` are static; files under `api/` are Vercel-style Node serverless functions.

After deployment verify:

1. `/` loads the bounty dashboard.
2. `/pay.html` shows Ethereum Mainnet, the configured recipient and both payment options.
3. `/api/config` returns the same recipient and official USDT contract.
4. `/api/bounties` returns at most 3 items without access.
5. A confirmed qualifying payment can be verified with its transaction hash and the original browser claim code.
6. The resulting access token unlocks the premium feed.

## Important

A bounty score is triage, not proof that a bounty will pay. Buyers should still confirm claim rules and payout eligibility before working. The crypto checkout intentionally accepts only Ethereum Mainnet in this version to avoid wrong-network loss.
