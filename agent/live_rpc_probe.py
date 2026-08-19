import json
import time
import urllib.request
from datetime import datetime, timezone

RPCS = {
    "base_standard": "https://mainnet.base.org",
    "base_flashblocks": "https://mainnet-preconf.base.org",
}


def rpc(url: str, method: str, params=None, timeout=15):
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or [],
    }).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "chatgpt-live-agent/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    if "error" in data:
        raise RuntimeError(f"RPC error {method}: {data['error']}")
    return data["result"]


def hx(x):
    return int(x, 16)


def main():
    out = {
        "probe_time_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "chains": {},
    }

    for name, url in RPCS.items():
        t0 = time.perf_counter()
        try:
            chain_id = hx(rpc(url, "eth_chainId"))
            block_hex = rpc(url, "eth_blockNumber")
            block_number = hx(block_hex)
            block = rpc(url, "eth_getBlockByNumber", [block_hex, False])
            gas_price = hx(rpc(url, "eth_gasPrice"))
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            out["chains"][name] = {
                "rpc": url,
                "chain_id": chain_id,
                "block_number": block_number,
                "block_hash": block.get("hash"),
                "block_timestamp_utc": datetime.fromtimestamp(hx(block["timestamp"]), tz=timezone.utc).isoformat(),
                "gas_price_wei": gas_price,
                "latency_ms": latency_ms,
                "verified_base_mainnet": chain_id == 8453,
            }
        except Exception as e:
            out["status"] = "PARTIAL_FAIL"
            out["chains"][name] = {"rpc": url, "error": repr(e)}

    print(json.dumps(out, indent=2, sort_keys=True))
    if not any(v.get("verified_base_mainnet") for v in out["chains"].values() if isinstance(v, dict)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
