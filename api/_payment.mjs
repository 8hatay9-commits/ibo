export const PAYMENT_WALLET = "0xDb12efE909Dc98e974e585A94c90DAa7c1c3D467"
export const USDT_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
export const PRICE_USDT_UNITS = 19_000_000n
export const PRICE_USDT = "19"
export const PRICE_ETH_WEI = 8_000_000_000_000_000n
export const PRICE_ETH = "0.008"

const TRANSFER_TOPIC =
  "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

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

function topicAddress(topic = "") {
  if (!/^0x[0-9a-fA-F]{64}$/.test(topic)) return ""
  return `0x${topic.slice(-40)}`.toLowerCase()
}

export async function verifyEthereumPayment(txHash) {
  if (!/^0x[0-9a-fA-F]{64}$/.test(txHash || "")) {
    throw new Error("Invalid transaction hash")
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
  if ((tx.to || "").toLowerCase() === wallet && BigInt(tx.value || "0x0") >= PRICE_ETH_WEI) {
    return {
      asset: "ETH",
      amount: PRICE_ETH,
      confirmations,
      from: (tx.from || "").toLowerCase(),
    }
  }

  for (const log of receipt.logs || []) {
    if ((log.address || "").toLowerCase() !== USDT_CONTRACT.toLowerCase()) continue
    if ((log.topics?.[0] || "").toLowerCase() !== TRANSFER_TOPIC) continue
    if (topicAddress(log.topics?.[2]) !== wallet) continue
    if (BigInt(log.data || "0x0") < PRICE_USDT_UNITS) continue

    return {
      asset: "USDT",
      amount: PRICE_USDT,
      confirmations,
      from: topicAddress(log.topics?.[1]),
    }
  }

  throw new Error("No qualifying ETH or Ethereum USDT payment to the configured wallet was found")
}
