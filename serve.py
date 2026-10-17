#!/usr/bin/env python3
# ==============================================================================
# FOCUS PHOTOCOMPANY — HARDENED PRODUCTION WEB SERVER (FocusShield 3.0)
# Complete Security Shield:
# 1. Server-Side Authentication Guard (Basic Auth & Bearer Token with PBKDF2)
# 2. Strict Endpoint Rate Limiting (General + Lead Anti-Spam + Anti-Bruteforce)
# 3. Path Traversal, Dotfile (.git, .env) & Root Secret File Protection
# 4. Anti-CSRF Origin Verification (No CORS Wildcard)
# 5. Payload Size Caps (16KB) & Defensive Input Gates
# 6. HTTP Range Streaming (Audio / 4K Video)
# ==============================================================================

from __future__ import annotations

import http.server
import json
import os
import re
import signal
import socketserver
import sys
import threading
import time
import urllib.parse
from collections import defaultdict

import lead_dispatcher

PORT = int(os.environ.get('PORT', '8080'))
DOC_ROOT = os.path.abspath(os.path.dirname(__file__))

# ── IN-MEMORY SLIDING-WINDOW IP RATE LIMITER (ANTI-DDOS FLOOD SHIELD) ──────────
class IPRateLimiter:
    def __init__(self, limit=80, window=1.0):
        self.limit = limit
        self.window = window
        self.requests = defaultdict(list)
        self.lock = threading.Lock()
        self.last_cleanup = time.time()

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        now = time.time()
        with self.lock:
            if now - self.last_cleanup > 30.0:
                self._cleanup(now)

            ts_list = self.requests[client_ip]
            cutoff = now - self.window
            valid = [t for t in ts_list if t > cutoff]
            if len(valid) >= self.limit:
                self.requests[client_ip] = valid
                return False, int(self.window - (now - valid[0])) + 1
            valid.append(now)
            self.requests[client_ip] = valid
            return True, 0

    def _cleanup(self, now: float):
        cutoff = now - self.window - 15.0
        stale = [ip for ip, ts in self.requests.items() if not ts or ts[-1] < cutoff]
        for ip in stale:
            del self.requests[ip]
        self.last_cleanup = now


# General anti-flood: max 80 requests/sec per IP
rate_limiter = IPRateLimiter(limit=80, window=1.0)

# Lead submission rate limiter: max 5 leads per 600s (10 min) per IP
lead_rate_limiter = IPRateLimiter(limit=5, window=600.0)


# Admin auth failure tracker: max 5 failed attempts per 300s (5 min) per IP
class AuthFailureTracker:
    def __init__(self, max_failures=5, window=300.0):
        self.max_failures = max_failures
        self.window = window
        self.failures = defaultdict(list)
        self.lock = threading.Lock()

    def is_locked_out(self, client_ip: str) -> tuple[bool, int]:
        now = time.time()
        with self.lock:
            ts_list = self.failures[client_ip]
            cutoff = now - self.window
            valid = [t for t in ts_list if t > cutoff]
            self.failures[client_ip] = valid
            if len(valid) >= self.max_failures:
                retry_after = int(self.window - (now - valid[0])) + 1
                return True, max(1, retry_after)
            return False, 0

    def record_failure(self, client_ip: str):
        now = time.time()
        with self.lock:
            self.failures[client_ip].append(now)

    def reset(self, client_ip: str):
        with self.lock:
            if client_ip in self.failures:
                del self.failures[client_ip]


auth_failure_limiter = AuthFailureTracker(max_failures=5, window=300.0)

concurrency_semaphore = threading.BoundedSemaphore(64)


# ── HTTP RANGE STREAMING FILE WRAPPER ──────────────────────────────────────────
class RangeFileWrapper:
    def __init__(self, file_obj, length: int):
        self.file_obj = file_obj
        self.remaining = length

    def read(self, size: int = -1) -> bytes:
        if self.remaining <= 0:
            return b""
        if size < 0 or size > self.remaining:
            size = self.remaining
        data = self.file_obj.read(size)
        self.remaining -= len(data)
        return data

    def close(self):
        self.file_obj.close()


# ── HARDENED HTTP REQUEST HANDLER ──────────────────────────────────────────────
class HardenedHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    server_version = "FocusShield/3.0"
    sys_version = ""

    def setup(self):
        super().setup()
        if self.connection:
            try:
                self.connection.settimeout(10.0)
            except OSError:
                pass

    def get_client_ip(self) -> str:
        try:
            if hasattr(self, 'headers') and self.headers:
                forwarded_for = self.headers.get('X-Forwarded-For')
                if forwarded_for:
                    return forwarded_for.split(',')[0].strip()
                cf_ip = self.headers.get('CF-Connecting-IP')
                if cf_ip:
                    return cf_ip.strip()
        except (AttributeError, IndexError):
            pass
        if self.client_address:
            return self.client_address[0]
        return '127.0.0.1'

    def send_security_headers(self):
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob:; "
            "media-src 'self' blob:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self';"
        )
        self.send_header('Content-Security-Policy', csp)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-XSS-Protection', '1; mode=block')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')

    def end_headers(self):
        self.send_security_headers()
        super().end_headers()

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (TimeoutError, BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        # Suppress noisy standard stdout logs; only security events are printed
        pass

    def check_rate_limit(self) -> bool:
        client_ip = self.get_client_ip()
        allowed, retry_after = rate_limiter.is_allowed(client_ip)
        if not allowed:
            self.send_response(429, "Too Many Requests")
            self.send_header("Retry-After", str(retry_after))
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"429 Too Many Requests: Flood protection active. Please retry shortly.\n")
            return False
        return True

    def is_safe_origin(self) -> bool:
        """CSRF / Origin Check: Ensures POST requests come only from allowed domains."""
        origin = self.headers.get('Origin') or self.headers.get('Referer')
        if not origin:
            # Allow requests without origin (direct scripts/curl) if same-origin host
            return True

        parsed = urllib.parse.urlparse(origin)
        origin_host = parsed.netloc.split(':')[0].lower()

        allowed_hosts = {
            'localhost', '127.0.0.1', '::1',
            'focusphotocompany.com', 'www.focusphotocompany.com',
            'focus-photo.ru', 'www.focus-photo.ru'
        }

        # Also permit the exact host requested in HTTP Host header
        http_host = self.headers.get('Host', '').split(':')[0].lower()
        if http_host:
            allowed_hosts.add(http_host)

        return origin_host in allowed_hosts

    def require_admin_auth(self) -> bool:
        """
        Validates administrator authentication.
        If invalid, sends 401 Unauthorized with WWW-Authenticate header.
        Protects against brute-force attacks via auth_failure_limiter.
        """
        client_ip = self.get_client_ip()
        auth_header = self.headers.get('Authorization', '')

        # Check brute force lockout
        locked, retry_after = auth_failure_limiter.is_locked_out(client_ip)
        if locked:
            self.send_response(429, "Too Many Requests")
            self.send_header("Retry-After", str(retry_after))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"ok": false, "error": "Brute-force lockout active. Please wait 5 minutes."}')
            return False

        ok, _user = lead_dispatcher.verify_admin_authorization(auth_header)
        if not ok:
            auth_failure_limiter.record_failure(client_ip)
            self.send_response(401, "Unauthorized")
            self.send_header("WWW-Authenticate", 'Basic realm="Focus Administration", charset="UTF-8"')
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"ok": false, "error": "Authentication required"}')
            return False

        # Reset failed attempts counter upon successful authorization
        auth_failure_limiter.reset(client_ip)
        return True

    def is_safe_request(self, raw_path: str) -> tuple[bool, int, str]:
        parsed = urllib.parse.urlparse(raw_path).path
        unquoted = urllib.parse.unquote(parsed)

        # 1. Block directory traversal
        if '..' in unquoted or '..' in parsed:
            return False, 403, "Directory traversal prohibited"

        # 2. Block hidden files and dotfiles (.git, .env, .DS_Store, etc.)
        parts = unquoted.replace('\\', '/').strip('/').split('/')
        for part in parts:
            if part.startswith('.') and part != '':
                return False, 403, "Access to hidden files prohibited"

        # 3. Block sensitive extensions and system files
        forbidden_exts = {
            '.py', '.pyc', '.pyo', '.sh', '.bash', '.zsh', '.env',
            '.log', '.db', '.sqlite', '.sqlite3', '.bak', '.sql',
            '.conf', '.ini', '.yaml', '.yml'
        }
        _, ext = os.path.splitext(unquoted)
        if ext.lower() in forbidden_exts:
            return False, 403, "Access to system files prohibited"

        # 4. Block direct unauthenticated access to database/secret files
        protected_root_files = {
            'config.json', 'leads.json', 'leads.csv',
            'config.example.json'
        }
        filename = os.path.basename(unquoted.strip('/'))
        if filename.lower() in protected_root_files:
            return False, 403, "Direct access to database files prohibited"

        # 5. Verify absolute path confinement within DOC_ROOT
        full_path = os.path.abspath(os.path.join(DOC_ROOT, unquoted.lstrip('/')))
        try:
            common = os.path.commonpath([DOC_ROOT, full_path])
            if common != DOC_ROOT:
                return False, 403, "Access out of document root prohibited"
        except (ValueError, OSError):
            return False, 400, "Invalid path resolution"

        return True, 200, full_path

    # ── GET REQUEST ROUTER ─────────────────────────────────────────────────────
    def do_GET(self):
        if not self.check_rate_limit():
            return

        parsed = urllib.parse.urlparse(self.path).path

        # 1. Protected Admin Dashboard HTML
        if parsed == '/leads_dashboard.html':
            if not self.require_admin_auth():
                return
            full_path = os.path.join(DOC_ROOT, 'leads_dashboard.html')
            try:
                with open(full_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except OSError:
                self.send_error(500, "Dashboard unavailable")
            return

        # 2. Protected Admin Leads JSON API
        if parsed == '/api/leads':
            if not self.require_admin_auth():
                return
            leads_file = lead_dispatcher.LEADS_JSON
            leads = []
            if os.path.exists(leads_file):
                try:
                    with open(leads_file, 'r', encoding='utf-8') as f:
                        leads = json.load(f)
                except (OSError, ValueError, json.JSONDecodeError):
                    leads = []
            response_bytes = json.dumps({"ok": True, "count": len(leads), "leads": leads[-100:]}, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response_bytes)))
            self.end_headers()
            self.wfile.write(response_bytes)
            return

        # 3. Protected Leads CSV Export
        if parsed == '/leads.csv':
            if not self.require_admin_auth():
                return
            csv_path = lead_dispatcher.LEADS_CSV
            if not os.path.exists(csv_path):
                self.send_error(404, "Leads CSV not found")
                return
            try:
                with open(csv_path, 'rb') as f:
                    csv_data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="leads_focus.csv"')
                self.send_header('Content-Length', str(len(csv_data)))
                self.end_headers()
                self.wfile.write(csv_data)
            except OSError:
                self.send_error(500, "Error reading CSV")
            return

        super().do_GET()

    # ── OPTIONS PREFLIGHT HANDLER (NO CORS WILDCARD) ───────────────────────────
    def do_OPTIONS(self):
        if not self.check_rate_limit():
            return
        origin = self.headers.get('Origin', '')
        self.send_response(204)
        if self.is_safe_origin() and origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    # ── POST REQUEST ROUTER ────────────────────────────────────────────────────
    def do_POST(self):
        if not self.check_rate_limit():
            return

        parsed = urllib.parse.urlparse(self.path).path

        # 1. Lead Submission API
        if parsed == '/api/send-lead':
            client_ip = self.get_client_ip()

            # Anti-CSRF Origin Guard
            if not self.is_safe_origin():
                self.send_response(403)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'{"ok": false, "error": "Cross-site request forbidden"}')
                return

            # Endpoint-specific rate limiter: max 5 submissions / 10 mins
            allowed, retry_after = lead_rate_limiter.is_allowed(client_ip)
            if not allowed:
                self.send_response(429)
                self.send_header('Retry-After', str(retry_after))
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                err_msg = json.dumps({
                    "ok": False,
                    "error": f"Слишком много заявок с вашего адреса. Подождите {retry_after} сек. или позвоните нам напрямую: +7 (929) 850-85-03"
                }, ensure_ascii=False).encode('utf-8')
                self.wfile.write(err_msg)
                return

            try:
                content_length = int(self.headers.get('Content-Length', 0))
                # Payload size cap: max 16 KB
                if content_length > 16384:
                    self.send_error(413, "Payload Too Large (Max 16KB)")
                    return

                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body.decode('utf-8'))
                except (ValueError, UnicodeDecodeError):
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(b'{"ok": false, "error": "Invalid JSON format"}')
                    return

                result = lead_dispatcher.process_new_lead(data, client_ip)
                status_code = result.get('status_code', 200)

                response_bytes = json.dumps(result, ensure_ascii=False).encode('utf-8')
                self.send_response(status_code)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(response_bytes)))
                self.end_headers()
                self.wfile.write(response_bytes)

            except Exception as e:  # noqa: BLE001
                err_bytes = json.dumps({"ok": False, "error": "Внутренняя ошибка сервера", "detail": str(e)}, ensure_ascii=False).encode('utf-8')
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(err_bytes)))
                self.end_headers()
                self.wfile.write(err_bytes)
            return

        self.send_error(404, "Endpoint Not Found")

    def do_HEAD(self):
        if not self.check_rate_limit():
            return
        super().do_HEAD()

    def send_head(self):
        safe, code, result = self.is_safe_request(self.path)
        if not safe:
            self.send_error(code, result)
            return None

        path = result
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

            f = open(path, 'rb')  # noqa: SIM115
            f.seek(start)
            return RangeFileWrapper(f, length)
        except (OSError, ValueError):
            return super().send_head()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 128


def shutdown_handler(signum, frame):
    print("\n[FocusShield] Received shutdown signal. Gracefully exiting...", flush=True)
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print(f"[FocusShield 3.0] Initializing hardened web server on port {PORT}...", flush=True)
    print("  • Anti-DDoS Rate Limiter active (80 req/sec burst window)", flush=True)
    print("  • Lead Anti-Spam Gate active (max 5 leads/10 min/IP)", flush=True)
    print("  • Admin Auth Guard active (/leads_dashboard.html & /api/leads protected by PBKDF2)", flush=True)
    print("  • Anti-Bruteforce Lockout active (5 failed attempts / 5 min)", flush=True)
    print("  • CSV Formula Injection Shield & Unpredictable CSPRNG IDs active", flush=True)
    print("  • Path Traversal, Dotfile & Secret File Shield active", flush=True)
    print("  • Enterprise Security Headers & Strict Same-Origin CORS active", flush=True)
    print("  • HTTP Range streaming active for 4K video and audio reviews", flush=True)

    # Initialize lead dispatcher / admin credentials if not set
    lead_dispatcher.load_config()

    try:
        with ThreadedHTTPServer(("", PORT), HardenedHTTPRequestHandler) as httpd:
            print(f"[FocusShield 3.0] Server listening on http://0.0.0.0:{PORT}", flush=True)
            httpd.serve_forever()
    except Exception as e:  # noqa: BLE001
        print(f"[FocusShield 3.0] Fatal server error: {e}", file=sys.stderr)
