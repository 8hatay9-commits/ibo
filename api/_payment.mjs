export const PAYMENT_WALLET = "0xDb12efE909Dc98e974e585A94c90DAa7c1c3D467"
export const PRICE_ETH_WEI = 8_000_000_000_000_000n
export const PRICE_ETH = "0.008"

function rpcUrl() {
  return process.env.ETH_RPC_URL || "https://cloudflare-eth.com"
}

async function rpc(method, params) {
  const response = await fetch(rpcUrl(), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  })
  if (!response.ok) throw new Error(`Ethereum RPC HTTP ${response.status}`)
  const data = await response.json()
  if (data.error) throw new Error(data.error.message || "Ethereum RPC error")
  return data.result
}

export function formatEthWei(value) {
  const wei = BigInt(value)
  const base = 1_000_000_000_000_000_000n
  const whole = wei / base
  const fraction = (wei % base).toString().padStart(18, "0").replace(/0+$/, "")
  return fraction ? `${whole}.${fraction}` : whole.toString()
}

export async function verifyEthereumPayment(txHash, expectedEthWei) {
  if (!/^0x[0-9a-fA-F]{64}$/.test(txHash || "")) {
    throw new Error("Invalid transaction hash")
  }

  let expected
  try {
    expected = BigInt(expectedEthWei)
  } catch {
    throw new Error("Invalid quoted ETH amount")
  }
  if (expected <= 0n || expected > PRICE_ETH_WEI) {
    throw new Error("Invalid quoted ETH amount")
  }

  const [tx, receipt, latestHex] = await Promise.all([
    rpc("eth_getTransactionByHash", [txHash]),
    rpc("eth_getTransactionReceipt", [txHash]),
    rpc("eth_blockNumber", []),
  ])

  if (!tx || !receipt) throw new Error("Transaction is not mined yet")
  if (receipt.status !== "0x1") throw new Error("Transaction failed on-chain")

  const latest = BigInt(latestHex)
  const mined = BigInt(receipt.blockNumber)
  const confirmations = Number(latest - mined + 1n)
  if (confirmations < 1) throw new Error("Transaction has no confirmation")

  const wallet = PAYMENT_WALLET.toLowerCase()
  if ((tx.to || "").toLowerCase() !== wallet) {
    throw new Error("Payment recipient does not match checkout wallet")
  }

  const paidWei = BigInt(tx.value || "0x0")
  if (paidWei !== expected) {
    throw new Error("Payment amount does not match this quote")
  }

  return {
    asset: "ETH",
    amount: formatEthWei(expected),
    amountWei: expected.toString(),
    confirmations,
    from: (tx.from || "").toLowerCase(),
  }
}
