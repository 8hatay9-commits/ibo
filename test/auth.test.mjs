import assert from "node:assert/strict"
import test from "node:test"
import { sha256Hex, signToken, verifyToken } from "../api/_auth.mjs"

process.env.ACCESS_TOKEN_SECRET = "test-secret-that-is-long-enough-for-ci"

test("signed quote and access tokens verify and reject tampering", () => {
  const exp = Math.floor(Date.now() / 1000) + 60
  const quote = signToken({ type: "quote", claimHash: sha256Hex("buyer-secret"), exp })
  assert.equal(verifyToken(quote, "quote")?.claimHash, sha256Hex("buyer-secret"))
  assert.equal(verifyToken(`${quote}x`, "quote"), null)
  assert.equal(verifyToken(quote, "access"), null)

  const access = signToken({ type: "access", txHash: `0x${"1".repeat(64)}`, exp })
  assert.equal(verifyToken(access, "access")?.type, "access")
})
