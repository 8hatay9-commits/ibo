# Bounty Radar

Bounty Radar is a paid-signal MVP for developers and AI agents hunting GitHub bounties.

It scans live open GitHub issues containing bounty text, extracts dollar amounts, checks repository state, and ranks candidates using payout size, issue competition, freshness, archived-repository detection, and suspicious claim requirements.

## Monetization

- Free feed: top 3 clean candidates
- Premium feed: up to 25 candidates plus full risk metadata
- Premium duration: 30 days
- Checkout: native ETH on Ethereum Mainnet
- Base price: **0.008 ETH**

The checkout uses a quote-specific exact ETH amount slightly below the 0.008 ETH base price. The tiny per-quote discount is an anti-replay nonce: an old public transaction hash cannot satisfy a newly generated quote because the exact wei amount will differ.

USDT activation is intentionally disabled in this version. Stateless ERC-20 transfer verification does not provide enough claim binding by itself; it should only be re-enabled with a stateful one-time transaction store or equivalent payer proof.

## Secure payment flow

1. Buyer opens `/pay.html`.
2. Browser creates a random private claim code locally.
3. `/api/quote` signs the claim hash, issue time, expiry, and a quote-specific exact ETH amount.
4. Buyer sends exactly that quoted ETH amount on Ethereum Mainnet to the configured recipient.
5. Buyer pastes the mined transaction hash.
6. `/api/verify-payment` verifies the recipient, successful receipt, confirmation, and exact wei amount against the signed quote.
7. The server returns a signed access token whose 30-day lifetime is anchored to the original quote issue time.
8. `/api/bounties` accepts that access token through `x-api-key`.

A public transaction hash alone is not enough to obtain a fresh quote-matching access token because each new quote requires a different exact ETH amount.

## Endpoints

- `GET /api/bounties` — ranked bounty feed
- `GET /api/config` — public product/payment configuration
- `POST /api/quote` — create signed, exact-amount ETH quote
- `POST /api/verify-payment` — verify Ethereum payment and issue access token

Premium example:

```bash
curl -H "x-api-key: YOUR_PAID_ACCESS_TOKEN" https://YOUR_DEPLOYMENT/api/bounties
```

## Environment

- `GITHUB_TOKEN` — optional but recommended for higher GitHub API limits
- `PREMIUM_API_KEY` — owner/admin master key
- `ACCESS_TOKEN_SECRET` — long random HMAC secret used to sign quotes and paid access tokens
- `ETH_RPC_URL` — Ethereum Mainnet RPC; when blank the app falls back to Cloudflare's public Ethereum RPC

No seed phrase or private wallet key is required anywhere.

## Tests

The test suite covers:

- signed quote/access token tamper and type rejection
- bounty scanner viability and suspicious prompt-exfiltration filtering
- exact quote-bound ETH payment acceptance
- rejection of mismatched payment amounts, wrong recipients, and failed transactions

Run with:

```bash
ACCESS_TOKEN_SECRET=test-secret-that-is-long-enough-for-ci PREMIUM_API_KEY=test-master-key node --test test/*.test.mjs
```

## Deploy

The project is dependency-light. `index.html` and `pay.html` are static; files under `api/` are Vercel-style Node serverless functions.

After deployment verify:

1. `/` loads the bounty dashboard.
2. `/pay.html` creates a 30-minute exact-amount ETH quote.
3. `/api/config` exposes Ethereum Mainnet and the configured recipient.
4. `/api/bounties` returns at most 3 items without access.
5. A confirmed exact quoted ETH payment can be verified with its transaction hash and original browser claim code.
6. The resulting access token unlocks the premium feed.

## Important

A bounty score is triage, not proof that a bounty will pay. Buyers should still confirm claim rules and payout eligibility before working.
