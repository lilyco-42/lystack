#!/usr/bin/env python3
"""signal relay —— zerostack 节点网格 WebRTC 信令中继 (零依赖 stdlib)。

POST /s/<channel>   body=消息体 → 存储 (每频道保留最新一条, 300s 过期)
GET  /s/<channel>   → 最新消息 JSON {msg, ts}
GET  /healthz       → 存活 + 频道数
DELETE /s/<channel> → 清除
仅监听 127.0.0.1:9920, 外部经 pingap /signal/ 反代。
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

TTL = 300.0
LOCK = threading.Lock()
STORE: dict[str, tuple[float, bytes]] = {}


def sweep():
    now = time.time()
    with LOCK:
        dead = [k for k, (ts, _) in STORE.items() if now - ts > TTL]
        for k in dead:
            del STORE[k]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def norm(self, p: str) -> str:
        """pingap 透传完整路径: /signal/healthz→/healthz, /signal/<ch>→/s/<ch>"""
        if p == "/signal/healthz":
            return "/healthz"
        if p.startswith("/signal/"):
            return "/s/" + p[len("/signal/"):]
        return p

    def do_GET(self):
        sweep()
        p = self.norm(urlparse(self.path).path)
        if p == "/healthz":
            with LOCK:
                n = len(STORE)
            self._send(200, json.dumps({"ok": True, "channels": n, "ts": time.time()}).encode())
            return
        if p.startswith("/s/"):
            ch = p[3:]
            with LOCK:
                item = STORE.get(ch)
            if not item:
                self._send(404, b'{"error":"no message"}')
                return
            ts, body = item
            self._send(200, json.dumps({"msg": body.decode("utf-8", "replace"),
                                        "ts": ts, "age": round(time.time() - ts, 1)}).encode())
            return
        self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        sweep()
        p = self.norm(urlparse(self.path).path)
        if not p.startswith("/s/") or len(p) <= 3:
            self._send(400, b'{"error":"need /s/<channel>"}')
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = 0
        if n <= 0 or n > 1_048_576:
            self._send(400, b'{"error":"body 1B..1MB"}')
            return
        body = self.rfile.read(n)
        with LOCK:
            STORE[p[3:]] = (time.time(), body)
        self._send(200, json.dumps({"ok": True, "channel": p[3:], "bytes": n}).encode())

    def do_DELETE(self):
        p = self.norm(urlparse(self.path).path)
        if p.startswith("/s/"):
            with LOCK:
                STORE.pop(p[3:], None)
            self._send(200, b'{"ok":true}')
            return
        self._send(404, b'{"error":"not found"}')

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", 9920), Handler)
    print("signal relay on 127.0.0.1:9920")
    srv.serve_forever()
