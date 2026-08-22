import crypto from "node:crypto"

function secret() {
  const value = process.env.ACCESS_TOKEN_SECRET || process.env.PREMIUM_API_KEY
  if (!value) throw new Error("ACCESS_TOKEN_SECRET or PREMIUM_API_KEY is required")
  return value
}

function encode(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url")
}

function signature(body) {
  return crypto.createHmac("sha256", secret()).update(body).digest("base64url")
}

export function signToken(payload) {
  const body = encode(payload)
  return `${body}.${signature(body)}`
}

export function verifyToken(token, expectedType) {
  if (typeof token !== "string") return null
  const [body, sig, ...extra] = token.split(".")
  if (!body || !sig || extra.length) return null

  const expected = signature(body)
  const a = Buffer.from(sig)
  const b = Buffer.from(expected)
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null

  let payload
  try {
    payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8"))
  } catch {
    return null
  }

  if (expectedType && payload.type !== expectedType) return null
  if (!Number.isFinite(payload.exp) || payload.exp <= Math.floor(Date.now() / 1000)) return null
  return payload
}

export function sha256Hex(value) {
  return crypto.createHash("sha256").update(String(value)).digest("hex")
}
