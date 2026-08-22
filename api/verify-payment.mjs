import { sha256Hex, signToken, verifyToken } from "./_auth.mjs"
import { verifyEthereumPayment } from "./_payment.mjs"

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.statusCode = 405
    res.setHeader("Allow", "POST")
    return res.end(JSON.stringify({ error: "method_not_allowed" }))
  }

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {})
    const txHash = String(body.txHash || "")
    const claimCode = String(body.claimCode || "")
    const quoteToken = String(body.quoteToken || "")

    const quote = verifyToken(quoteToken, "quote")
    if (!quote) {
      res.statusCode = 400
      return res.end(JSON.stringify({ ok: false, error: "invalid_or_expired_quote" }))
    }
    if (!claimCode || sha256Hex(claimCode) !== quote.claimHash) {
      res.statusCode = 403
      return res.end(JSON.stringify({ ok: false, error: "claim_code_mismatch" }))
    }
    if (!/^\d+$/.test(String(quote.priceEthWei || ""))) {
      res.statusCode = 400
      return res.end(JSON.stringify({ ok: false, error: "invalid_quote_amount" }))
    }

    const payment = await verifyEthereumPayment(txHash, quote.priceEthWei)
    const issuedAt = Number(quote.iat)
    if (!Number.isFinite(issuedAt)) throw new Error("Quote issue time is invalid")

    const exp = issuedAt + 30 * 24 * 60 * 60
    const accessToken = signToken({
      type: "access",
      txHash: txHash.toLowerCase(),
      asset: payment.asset,
      quoteClaimHash: quote.claimHash,
      exp,
    })

    res.setHeader("Content-Type", "application/json; charset=utf-8")
    return res.end(JSON.stringify({
      ok: true,
      payment,
      accessToken,
      expiresAt: new Date(exp * 1000).toISOString(),
    }))
  } catch (error) {
    res.statusCode = 400
    res.setHeader("Content-Type", "application/json; charset=utf-8")
    return res.end(JSON.stringify({
      ok: false,
      error: "payment_verification_failed",
      message: error instanceof Error ? error.message : String(error),
    }))
  }
}
