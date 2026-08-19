import base64, hashlib, os, socket, ssl, struct
from urllib.parse import urlparse

class WebSocketError(RuntimeError): pass

class SimpleWebSocket:
    def __init__(self,url,timeout=12,origin="https://docs.base.org"):
        self.url=url; self.timeout=timeout; self.origin=origin; self.sock=None; self._prefetch=b""

    def connect(self):
        u=urlparse(self.url)
        host=u.hostname; port=u.port or 443; path=u.path or "/"
        if u.query: path += "?"+u.query
        raw=socket.create_connection((host,port),timeout=self.timeout)
        ctx=ssl.create_default_context(); s=ctx.wrap_socket(raw,server_hostname=host); s.settimeout(self.timeout)
        key=base64.b64encode(os.urandom(16)).decode()
        req=(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
             f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: {self.origin}\r\n"
             "User-Agent: FlashbotProductionV3/3.0.1\r\n\r\n")
        s.sendall(req.encode()); buf=b""
        while b"\r\n\r\n" not in buf and len(buf)<65536:
            part=s.recv(4096)
            if not part: raise WebSocketError("handshake EOF")
            buf+=part
        head,rest=buf.split(b"\r\n\r\n",1); lines=head.decode("latin1").split("\r\n")
        if " 101 " not in lines[0]:
            try:s.close()
            except Exception:pass
            raise WebSocketError("handshake: "+lines[0])
        headers={}
        for line in lines[1:]:
            if ":" in line:
                k,v=line.split(":",1); headers[k.strip().lower()]=v.strip()
        want=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if headers.get("sec-websocket-accept")!=want: raise WebSocketError("bad Sec-WebSocket-Accept")
        self.sock=s; self._prefetch=rest; return self

    def close(self):
        try:
            if self.sock:self._send_frame(b"",8)
        except Exception:pass
        try:
            if self.sock:self.sock.close()
        except Exception:pass
        self.sock=None

    def _read_exact(self,n):
        out=b""
        if self._prefetch:
            take=self._prefetch[:n]; out+=take; self._prefetch=self._prefetch[len(take):]
        while len(out)<n:
            part=self.sock.recv(n-len(out))
            if not part: raise WebSocketError("socket EOF")
            out+=part
        return out

    def _send_frame(self,payload,opcode=1):
        if isinstance(payload,str):payload=payload.encode()
        mask=os.urandom(4); n=len(payload); head=bytearray([0x80|opcode])
        if n<126:head.append(0x80|n)
        elif n<65536:head += bytes([0x80|126])+struct.pack("!H",n)
        else:head += bytes([0x80|127])+struct.pack("!Q",n)
        masked=bytes(b ^ mask[i%4] for i,b in enumerate(payload)); self.sock.sendall(bytes(head)+mask+masked)

    def send_json(self,obj):
        import json; self._send_frame(json.dumps(obj,separators=(",",":")),1)

    def recv_text(self):
        chunks=[]; active=False
        while True:
            h=self._read_exact(2); b0,b1=h[0],h[1]; fin=bool(b0&0x80); opcode=b0&0x0f; masked=bool(b1&0x80); n=b1&0x7f
            if n==126:n=struct.unpack("!H",self._read_exact(2))[0]
            elif n==127:n=struct.unpack("!Q",self._read_exact(8))[0]
            mask=self._read_exact(4) if masked else None; p=self._read_exact(n)
            if mask:p=bytes(b ^ mask[i%4] for i,b in enumerate(p))
            if opcode==8: raise WebSocketError("server closed")
            if opcode==9:self._send_frame(p,10);continue
            if opcode==10:continue
            if opcode==1:
                chunks=[p];active=True
                if fin:return b"".join(chunks).decode("utf-8","replace")
            elif opcode==0 and active:
                chunks.append(p)
                if fin:return b"".join(chunks).decode("utf-8","replace")
