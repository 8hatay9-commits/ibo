import { getStore } from '@netlify/blobs';
import { scan } from './_core.mjs';

export default async () => {
  const startedAt = new Date().toISOString();
  try {
    const result = await scan(300);
    await getStore('flashbot-state').setJSON('latest-scan', result);
    console.log(JSON.stringify({ event: 'scheduled_scan_ok', startedAt, observedAt: result.observedAt, head: result.head, checked: result.checked, liquidatable: result.liquidatable?.length || 0, near: result.near?.length || 0, errors: result.errors }));
  } catch (e) {
    console.error(JSON.stringify({ event: 'scheduled_scan_error', startedAt, error: String(e?.message || e) }));
    throw e;
  }
};
