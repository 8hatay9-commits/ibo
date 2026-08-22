export default function handler(_req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8")
  res.setHeader("Cache-Control", "s-maxage=300")
  res.end(
    JSON.stringify({
      product: "Bounty Radar",
      premiumPriceUsd: Number(process.env.PREMIUM_PRICE_USD ?? 19),
      checkoutUrl: process.env.CHECKOUT_URL ?? "",
      premiumEnabled: Boolean(process.env.PREMIUM_API_KEY),
    }),
  )
}
