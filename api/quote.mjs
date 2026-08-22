import crypto from "node:crypto"
import { signToken } from "./_auth.mjs"
import { PAYMENT_WALLET, PRICE_ETH, PRICE_ETH_WEI, formatEthWei } from "./_payment.mjs"

const QUOTE_TTL_SECONDS = 30 * 60
const ANTI_REPLAY_STEP_WEI = 1_000_000n
const ANTI_REPLAY_STEPS = 281_474_976

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.statusCode = 405
    res.setHeader("Allow", "POST")
    return res.end(JSON.stringify({ error: "method_not_allowed" }))
  }

  const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {})
  const claimHash = String(body.claimHash || "").toLowerCase()
  if (!/^[0-9a-f]{64}$/.test(claimHash)) {
    res.statusCode = 400
    return res.end(JSON.stringify({ error: "invalid_claim_hash" }))
  }

  const offsetWei = BigInt(crypto.randomInt(0, ANTI_REPLAY_STEPS)) * ANTI_REPLAY_STEP_WEI
  const priceEthWei = PRICE_ETH_WEI - offsetWei
  const iat = Math.floor(Date.now() / 1000)
  const exp = iat + QUOTE_TTL_SECONDS

  const quoteToken = signToken({
    type: "quote",
    claimHash,
    priceEthWei: priceEthWei.toString(),
    iat,
    exp,
  })

  res.setHeader("Content-Type", "application/json; charset=utf-8")
  return res.end(JSON.stringify({
    ok: true,
    network: "Ethereum Mainnet",
    chainId: 1,
    wallet: PAYMENT_WALLET,
    eth: {
      symbol: "ETH",
      baseAmount: PRICE_ETH,
      amount: formatEthWei(priceEthWei),
      amountWei: priceEthWei.toString(),
    },
    quoteToken,
    expiresAt: new Date(exp * 1000).toISOString(),
  }))
}
