const CACHE_TTL_MS = 90_000
let cache = { at: 0, rows: [] }

const SUSPICIOUS_TERMS = [
  "system prompt",
  "pre-conversation",
  "pre conversation",
  "initialization payload",
  "initial directives",
  "platform_instructions",
  "platform instructions",
  "boot_context",
  "session instructions",
  "paste everything",
  "paste verbatim",
  "complete startup instructions",
]

function githubHeaders() {
  const headers = {
    Accept: "application/vnd.github+json",
    "User-Agent": "bounty-radar-mvp",
    "X-GitHub-Api-Version": "2022-11-28",
  }
  if (process.env.GITHUB_TOKEN) {
    headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`
  }
  return headers
}

async function gh(url) {
  const response = await fetch(url, { headers: githubHeaders() })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`GitHub ${response.status}: ${text.slice(0, 240)}`)
  }
  return response.json()
}

function parseMoney(text = "") {
  const patterns = [
    /\/bounty\s+\$?\s*([\d,.]+)\s*([kK])?/i,
    /bounty[^\n$]{0,30}\$\s*([\d,.]+)\s*([kK])?/i,
  ]
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (!match) continue
    let value = Number(match[1].replaceAll(",", ""))
    if (!Number.isFinite(value)) continue
    if (match[2]) value *= 1000
    return Math.round(value)
  }
  return 0
}

function suspiciousReasons(text = "") {
  const lower = text.toLowerCase()
  return SUSPICIOUS_TERMS.filter((term) => lower.includes(term))
}

function daysSince(date) {
  const ms = Date.now() - new Date(date).getTime()
  return Math.max(0, ms / 86_400_000)
}

function scoreRow({ amount, comments, updatedAt, archived, suspicious }) {
  if (archived || suspicious.length) return 0
  const value = Math.min(50, Math.log10(amount + 1) * 16)
  const competition = Math.min(32, comments * 2.5)
  const staleness = Math.min(18, daysSince(updatedAt) / 10)
  return Math.max(0, Math.round((value - competition - staleness) * 10) / 10)
}

function repoFullNameFromIssue(issue) {
  const parts = new URL(issue.html_url).pathname.split("/").filter(Boolean)
  return `${parts[0]}/${parts[1]}`
}

export async function scanBounties() {
  if (Date.now() - cache.at < CACHE_TTL_MS) return cache.rows

  const query = encodeURIComponent("bounty in:body is:issue is:open")
  const search = await gh(
    `https://api.github.com/search/issues?q=${query}&sort=updated&order=desc&per_page=30`,
  )

  const candidates = (search.items ?? [])
    .map((issue) => ({ issue, amount: parseMoney(issue.body ?? "") }))
    .filter((x) => x.amount > 0)
    .slice(0, 15)

  const repoNames = [...new Set(candidates.map(({ issue }) => repoFullNameFromIssue(issue)))]
  const repoEntries = await Promise.all(
    repoNames.map(async (name) => {
      try {
        const repo = await gh(`https://api.github.com/repos/${name}`)
        return [name, repo]
      } catch {
        return [name, null]
      }
    }),
  )
  const repoMap = new Map(repoEntries)

  const rows = candidates.map(({ issue, amount }) => {
    const repoFullName = repoFullNameFromIssue(issue)
    const repo = repoMap.get(repoFullName)
    const suspicious = suspiciousReasons(`${issue.title}\n${issue.body ?? ""}`)
    const archived = repo?.archived === true
    const comments = issue.comments ?? 0
    const updatedAt = issue.updated_at
    const score = scoreRow({ amount, comments, updatedAt, archived, suspicious })

    return {
      repo: repoFullName,
      title: issue.title,
      url: issue.html_url,
      amountUsd: amount,
      comments,
      updatedAt,
      archived,
      suspicious,
      score,
      viable: !archived && suspicious.length === 0,
    }
  })

  rows.sort((a, b) => b.score - a.score || b.amountUsd - a.amountUsd)
  cache = { at: Date.now(), rows }
  return rows
}

export function isPremium(req) {
  const expected = process.env.PREMIUM_API_KEY
  if (!expected) return false
  const presented = req.headers["x-api-key"]
  return typeof presented === "string" && presented === expected
}
