import http.server
import socketserver
import sys

PORT = 8080

class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == '__main__':
    try:
        with ThreadedHTTPServer(("", PORT), NoCacheHTTPRequestHandler) as httpd:
            print(f"Serving on port {PORT} with multithreaded no-cache headers", flush=True)
            httpd.serve_forever()
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
