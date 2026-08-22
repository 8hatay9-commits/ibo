import { signToken } from "./_auth.mjs"
import {
  PAYMENT_WALLET,
  PRICE_ETH,
  PRICE_ETH_WEI,
  PRICE_USDT,
  PRICE_USDT_UNITS,
  USDT_CONTRACT,
} from "./_payment.mjs"

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

  const exp = Math.floor(Date.now() / 1000) + 30 * 60
  const quoteToken = signToken({
    type: "quote",
    claimHash,
    exp,
    priceUsdtUnits: PRICE_USDT_UNITS.toString(),
    priceEthWei: PRICE_ETH_WEI.toString(),
  })

  res.setHeader("Content-Type", "application/json; charset=utf-8")
  return res.end(JSON.stringify({
    ok: true,
    network: "Ethereum Mainnet",
    chainId: 1,
    wallet: PAYMENT_WALLET,
    usdt: { symbol: "USDT", amount: PRICE_USDT, contract: USDT_CONTRACT },
    eth: { symbol: "ETH", amount: PRICE_ETH },
    quoteToken,
    expiresAt: new Date(exp * 1000).toISOString(),
  }))
}
