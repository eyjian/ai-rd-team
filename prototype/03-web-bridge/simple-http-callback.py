"""P3 Demo 2：基于 HTTP 回调的 Web Bridge 最小实现。

演示：
- 启动 Flask 服务器（端口 5000）
- 成员通过 POST /event 上报事件
- 服务器打印事件，并暴露 GET /events 查询历史

用法：
    python simple-http-callback.py        # 启动服务
    # 另开终端：
    curl -X POST http://localhost:5000/event \\
         -H 'Content-Type: application/json' \\
         -d '{"from":"architect","event":"message_sent","to":"developer"}'

如未安装 flask，会用 http.server 降级模拟。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

events: list[dict] = []


def run_flask() -> None:
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        print("[降级] 未安装 flask，使用 http.server")
        run_http_server()
        return

    app = Flask(__name__)

    @app.post("/event")
    def receive_event():
        payload = request.get_json(force=True)
        payload["_received_at"] = datetime.now().isoformat()
        events.append(payload)
        print(f"[收到] {payload}")
        return jsonify({"ok": True, "total": len(events)})

    @app.get("/events")
    def list_events():
        return jsonify(events)

    @app.get("/")
    def index():
        return "<h1>Events received: {}</h1>".format(len(events))

    print("[flask] http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)


def run_http_server() -> None:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"raw": body.decode("utf-8", errors="replace")}
            payload["_received_at"] = datetime.now().isoformat()
            events.append(payload)
            print(f"[收到] {payload}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "total": len(events)}).encode())

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(events, ensure_ascii=False).encode())

        def log_message(self, format, *args):
            pass  # 静默

    server = HTTPServer(("0.0.0.0", 5000), Handler)
    print("[http.server] http://localhost:5000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    run_flask()
