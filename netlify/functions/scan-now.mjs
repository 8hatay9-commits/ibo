import { getStore } from '@netlify/blobs';
import { scan, json } from './_core.mjs';

export default async (req) => {
  try {
    const url = new URL(req.url);
    const blocks = Number(url.searchParams.get('blocks') || 300);
    const result = await scan(blocks);
    await getStore('flashbot-state').setJSON('latest-scan', result);
    return json(result);
  } catch (e) {
    return json({ ok: false, error: String(e?.message || e), signingEnabled: false, broadcastEnabled: false, observedAt: new Date().toISOString() }, 502);
  }
};
