import http from 'node:http';
import handler from './api/index.js';

const port = Number(process.env.PORT || 10000);

function makeRes(res) {
  res.status = code => { res.statusCode = code; return res; };
  res.json = value => {
    if (!res.headersSent) res.setHeader('content-type', 'application/json; charset=utf-8');
    res.end(JSON.stringify(value));
    return res;
  };
  res.send = value => { res.end(value); return res; };
  return res;
}

const server = http.createServer(async (req, res) => {
  let body = '';
  req.on('data', chunk => { body += chunk; });
  req.on('end', async () => {
    if (body) {
      try { req.body = JSON.parse(body); }
      catch { req.body = {}; }
    } else req.body = {};
    try { await handler(req, makeRes(res)); }
    catch (e) {
      res.statusCode = 500;
      res.setHeader('content-type', 'application/json; charset=utf-8');
      res.end(JSON.stringify({ok:false,error:String(e?.message || e)}));
    }
  });
});

server.listen(port, '0.0.0.0', () => console.log(`flashbot-cloud-v4 listening on ${port}`));
