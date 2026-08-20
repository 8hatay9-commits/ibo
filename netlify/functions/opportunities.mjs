import { getStore } from '@netlify/blobs';
import { json } from './_core.mjs';

export default async () => {
  try {
    const latest = await getStore('flashbot-state').get('latest-scan', { type: 'json', consistency: 'strong' });
    if (!latest) return json({ ok: false, error: 'NO_SCAN_YET', signingEnabled: false, broadcastEnabled: false }, 404);
    return json({
      ok: true,
      chain: latest.chain,
      chainId: latest.chainId,
      head: latest.head,
      observedAt: latest.observedAt,
      checked: latest.checked,
      errors: latest.errors,
      liquidatable: latest.liquidatable || [],
      near: latest.near || [],
      lowest: latest.lowest || [],
      signingEnabled: false,
      broadcastEnabled: false
    });
  } catch (e) {
    return json({ ok: false, error: String(e?.message || e), signingEnabled: false, broadcastEnabled: false }, 502);
  }
};
