# Bounty Radar

Bounty Radar is a small paid-signal MVP for developers and AI agents hunting GitHub bounties.

It scans live open GitHub issues containing bounty text, extracts dollar amounts, checks repository state, and ranks candidates using simple signals:

- payout size
- issue competition (comment count)
- freshness
- archived repository detection
- suspicious claim requirements that ask contributors/agents to expose hidden initialization or system instructions

## Monetization model

The public endpoint returns only the top 3 clean candidates. A request with `x-api-key: <PREMIUM_API_KEY>` returns up to 25 candidates and full risk metadata.

Set `CHECKOUT_URL` to any hosted checkout/payment link. After payment, issue the customer a premium API key. This keeps the MVP payment-provider agnostic while making it immediately sellable.

Suggested starting price is controlled by `PREMIUM_PRICE_USD` and defaults to `$19/month`.

## Endpoints

- `GET /api/bounties` — ranked bounty feed
- `GET /api/config` — public product/checkout configuration

Premium example:

```bash
curl -H "x-api-key: YOUR_KEY" https://YOUR_DEPLOYMENT/api/bounties
```

## Environment

Copy `.env.example` values into the deployment environment:

- `GITHUB_TOKEN` — optional but recommended for higher GitHub API limits
- `PREMIUM_API_KEY` — secret used to unlock the premium response
- `CHECKOUT_URL` — Stripe Payment Link / Paddle / Lemon Squeezy / other hosted checkout
- `PREMIUM_PRICE_USD` — displayed monthly price

## Deploy

This repository is intentionally dependency-light. `index.html` is static and the files under `api/` are Vercel-style Node serverless functions.

Deploy the repository to Vercel, add the environment variables above, then verify:

1. `/` loads the dashboard.
2. `/api/config` returns product configuration.
3. `/api/bounties` returns at most 3 items without a key.
4. `/api/bounties` returns the premium feed with a valid `x-api-key`.
5. `CHECKOUT_URL` opens the real payment page before selling access.

## Important

A score is triage, not proof that a bounty will pay. Bounty Radar deliberately filters obvious risk signals, but buyers should still confirm claim rules and payout eligibility before working.
