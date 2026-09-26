"""测试用本地 http 服务（多线程）。

为什么必须多线程：浏览器加载 <video> 时会开长连接占住线程。单线程 TCPServer 会让后续
请求全部排队阻塞，表现为「页面卡死、CDP Runtime.evaluate 超时」——极易被误判成扩展写挂了。

为什么必须走 http 而不是 file://：扩展 manifest 只匹配 http/https，file:// 页面注入不了内容脚本。

用法：python serve.py [port]   （默认 8731，根目录 = 本文件所在目录）
"""
import http.server
import os
import socketserver
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8731


class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"      # keep-alive / Range，媒体加载更正常

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            self.close_connection = True


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    httpd = Server(("127.0.0.1", PORT), Handler)
    print("serving http://127.0.0.1:%d root=%s (threaded)" % (PORT, ROOT), flush=True)
    httpd.serve_forever()
