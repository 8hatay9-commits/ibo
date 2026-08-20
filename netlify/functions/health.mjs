import { getStore } from '@netlify/blobs';
import { health, json } from './_core.mjs';

export default async () => {
  try {
    const live = await health();
    let latestScan = null;
    try {
      latestScan = await getStore('flashbot-state').get('latest-scan', { type: 'json', consistency: 'strong' });
    } catch {}
    return json({ ...live, latestScan: latestScan ? {
      observedAt: latestScan.observedAt,
      head: latestScan.head,
      checked: latestScan.checked,
      liquidatableCount: latestScan.liquidatable?.length || 0,
      nearCount: latestScan.near?.length || 0,
      errors: latestScan.errors
    } : null });
  } catch (e) {
    return json({ ok: false, error: String(e?.message || e), signingEnabled: false, broadcastEnabled: false, observedAt: new Date().toISOString() }, 502);
  }
};
