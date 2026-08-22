import { isPremium, scanBounties } from "./_lib.mjs"

export default async function handler(req, res) {
  if (req.method !== "GET") {
    res.statusCode = 405
    res.setHeader("Allow", "GET")
    return res.end(JSON.stringify({ error: "method_not_allowed" }))
  }

  try {
    const premium = isPremium(req)
    const rows = await scanBounties()
    const clean = rows.filter((row) => row.viable)
    const limit = premium ? 25 : 3
    const selected = clean.slice(0, limit)

    const results = selected.map((row) =>
      premium
        ? row
        : {
            repo: row.repo,
            title: row.title,
            url: row.url,
            amountUsd: row.amountUsd,
            score: row.score,
            comments: row.comments,
          },
    )

    res.setHeader("Content-Type", "application/json; charset=utf-8")
    res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate=120")
    return res.end(
      JSON.stringify({
        ok: true,
        tier: premium ? "premium" : "free",
        returned: results.length,
        totalClean: clean.length,
        filteredOut: rows.length - clean.length,
        results,
      }),
    )
  } catch (error) {
    res.statusCode = 502
    res.setHeader("Content-Type", "application/json; charset=utf-8")
    return res.end(
      JSON.stringify({
        ok: false,
        error: "scan_failed",
        message: error instanceof Error ? error.message : String(error),
      }),
    )
  }
}
