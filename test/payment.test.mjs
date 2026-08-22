import assert from "node:assert/strict"
import test from "node:test"
import { PAYMENT_WALLET, formatEthWei, verifyEthereumPayment } from "../api/_payment.mjs"

const TX_HASH = `0x${"a".repeat(64)}`
const EXPECTED = 7_900_123_456_000_000n

function installRpcMock({ value = EXPECTED, to = PAYMENT_WALLET, status = "0x1" } = {}) {
  globalThis.fetch = async (_url, options) => {
    const request = JSON.parse(options.body)
    let result
    if (request.method === "eth_getTransactionByHash") {
      result = {
        hash: TX_HASH,
        from: "0x1111111111111111111111111111111111111111",
        to,
        value: `0x${value.toString(16)}`,
      }
    } else if (request.method === "eth_getTransactionReceipt") {
      result = { status, blockNumber: "0x64", logs: [] }
    } else if (request.method === "eth_blockNumber") {
      result = "0x65"
    } else {
      throw new Error(`unexpected rpc method ${request.method}`)
    }
    return new Response(JSON.stringify({ jsonrpc: "2.0", id: 1, result }), {
      status: 200,
      headers: { "content-type": "application/json" },
    })
  }
}

test("exact quote-bound ETH payment verifies", async () => {
  installRpcMock()
  const payment = await verifyEthereumPayment(TX_HASH, EXPECTED.toString())
  assert.equal(payment.asset, "ETH")
  assert.equal(payment.amountWei, EXPECTED.toString())
  assert.equal(payment.amount, formatEthWei(EXPECTED))
  assert.equal(payment.confirmations, 2)
})

test("different amount cannot reuse a payment transaction", async () => {
  installRpcMock()
  await assert.rejects(
    verifyEthereumPayment(TX_HASH, (EXPECTED - 1_000_000n).toString()),
    /does not match this quote/,
  )
})

test("wrong recipient and failed transaction are rejected", async () => {
  installRpcMock({ to: "0x2222222222222222222222222222222222222222" })
  await assert.rejects(verifyEthereumPayment(TX_HASH, EXPECTED.toString()), /recipient/)

  installRpcMock({ status: "0x0" })
  await assert.rejects(verifyEthereumPayment(TX_HASH, EXPECTED.toString()), /failed on-chain/)
})
