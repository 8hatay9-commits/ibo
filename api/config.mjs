import {
  PAYMENT_WALLET,
  PRICE_ETH,
  PRICE_USDT,
  USDT_CONTRACT,
} from "./_payment.mjs"

export default function handler(_req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8")
  res.setHeader("Cache-Control", "s-maxage=300")
  res.end(
    JSON.stringify({
      product: "Bounty Radar",
      premiumPriceUsd: 19,
      premiumEnabled: Boolean(process.env.ACCESS_TOKEN_SECRET || process.env.PREMIUM_API_KEY),
      payment: {
        network: "Ethereum Mainnet",
        chainId: 1,
        wallet: PAYMENT_WALLET,
        eth: { symbol: "ETH", amount: PRICE_ETH },
        usdt: { symbol: "USDT", amount: PRICE_USDT, contract: USDT_CONTRACT },
      },
    }),
  )
}
