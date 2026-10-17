import http.server
import socketserver
import sys
import os
import re

PORT = 8080

class RangeFileWrapper:
    def __init__(self, file_obj, length):
        self.file_obj = file_obj
        self.remaining = length

    def read(self, size=-1):
        if self.remaining <= 0:
            return b""
        if size < 0 or size > self.remaining:
            size = self.remaining
        data = self.file_obj.read(size)
        self.remaining -= len(data)
        return data

    def close(self):
        self.file_obj.close()

class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        range_header = self.headers.get('Range')
        if not range_header or not os.path.isfile(path):
            return super().send_head()

        try:
            total_size = os.path.getsize(path)
            range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if not range_match:
                return super().send_head()

            start = int(range_match.group(1))
            end = int(range_match.group(2)) if range_match.group(2) else total_size - 1
            if start >= total_size or end >= total_size or start > end:
                self.send_error(416, "Requested Range Not Satisfiable")
                return None

            length = end - start + 1
            self.send_response(206)
            ctype = self.guess_type(path)
            self.send_header("Content-type", ctype)
            self.send_header("Content-Range", f"bytes {start}-{end}/{total_size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Last-Modified", self.date_time_string(int(os.path.getmtime(path))))
            self.end_headers()

            f = open(path, 'rb')
            f.seek(start)
            return RangeFileWrapper(f, length)
        except Exception:
            return super().send_head()

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == '__main__':
    try:
        with ThreadedHTTPServer(("", PORT), NoCacheHTTPRequestHandler) as httpd:
            print(f"Serving on port {PORT} with HTTP Range support and multithreaded no-cache headers", flush=True)
            httpd.serve_forever()
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
