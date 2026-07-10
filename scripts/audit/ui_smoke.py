"""UI 스모크 감사기 — 역할별로 실제 로그인해서 핵심 화면을 헤드리스 크롬으로 열고,
**콘솔 에러 / 실패한 네트워크 요청**을 수집하고 스크린샷을 남긴다.

코드가 아니라 화면을 본다. "이 화면이 이 역할에게 에러 없이 뜨는가"를 실측한다.

동작:
  1. 각 역할로 HTTP 로그인해서 sessionid 쿠키를 얻는다.
  2. 헤드리스 크롬을 --remote-debugging-port 로 띄우고, stdlib 만으로 만든 최소
     CDP(WebSocket) 클라이언트로 쿠키를 주입한 뒤 각 화면을 열어 스크린샷/콘솔로그
     /실패요청을 수집한다.

선행: 프론트 빌드(web/dist) + 로컬 서버 기동 + 감사 시드(_seed_users.py). run_all.sh 참고.
의존: 시스템 크롬만. 외부 파이썬 패키지 불필요.

출력: scripts/audit/out/<role>__<page>.png + 콘솔 표.
환경변수: BASE(기본 http://127.0.0.1:8899), CHROME(기본 시스템 크롬), DEVTOOLS_PORT(기본 9333).
"""

import base64
import http.cookiejar
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE = os.environ.get('BASE', 'http://127.0.0.1:8899')
CHROME = os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
PORT = int(os.environ.get('DEVTOOLS_PORT', '9333'))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
PASSWORD = 'Str0ngPass!23'

ROLES = {'super_admin': 'sa@audit.local', 'workspace_manager': 'wm@audit.local', 'annotator': 'an@audit.local'}
PAGES = [('home', '/'), ('projects', '/projects'), ('workspaces', '/workspaces'), ('account', '/user/account')]


# ─── 최소 WebSocket 클라이언트 (stdlib, 로컬 평문 전용) ──────────────────────────
class WS:
    def __init__(self, url):
        u = urllib.parse.urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port))
        key = base64.b64encode(os.urandom(16)).decode()
        path = u.path + (('?' + u.query) if u.query else '')
        req = (
            f'GET {path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n'
            f'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'
        )
        self.sock.sendall(req.encode())
        buf = b''
        while b'\r\n\r\n' not in buf:
            buf += self.sock.recv(4096)

    def send(self, data):
        payload = json.dumps(data).encode()
        header = bytearray([0x81])  # FIN + text
        n = len(payload)
        mask = os.urandom(4)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack('>H', n)
        else:
            header.append(0x80 | 127)
            header += struct.pack('>Q', n)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _recv_exact(self, n):
        out = b''
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise ConnectionError('socket closed')
            out += chunk
        return out

    def recv(self):
        b0, b1 = self._recv_exact(2)
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack('>H', self._recv_exact(2))[0]
        elif n == 127:
            n = struct.unpack('>Q', self._recv_exact(8))[0]
        data = self._recv_exact(n)
        return json.loads(data)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


class CDP:
    def __init__(self, ws_url):
        self.ws = WS(ws_url)
        self._id = 0

    def call(self, method, params=None, timeout=15):
        self._id += 1
        mid = self._id
        self.ws.send({'id': mid, 'method': method, 'params': params or {}})
        deadline = time.time() + timeout
        events = []
        while time.time() < deadline:
            msg = self.ws.recv()
            if msg.get('id') == mid:
                return msg.get('result', {}), events
            if 'method' in msg:
                events.append(msg)
        raise TimeoutError(method)


def wait(url, tries=30):
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def login(email):
    """역할 로그인 → sessionid 쿠키 값."""
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    html = op.open(f'{BASE}/user/login/', timeout=10).read().decode()
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)
    data = urllib.parse.urlencode({'csrfmiddlewaretoken': token, 'email': email, 'password': PASSWORD}).encode()
    req = urllib.request.Request(f'{BASE}/user/login/', data=data)
    req.add_header('Referer', f'{BASE}/user/login/')
    try:
        op.open(req, timeout=10)
    except Exception:
        pass
    return {c.name: c.value for c in cj}


def launch_chrome():
    profile = os.path.join(OUT, '.chrome-profile')
    proc = subprocess.Popen(
        [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
         f'--remote-debugging-port={PORT}', f'--user-data-dir={profile}', '--window-size=1440,900',
         'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        try:
            meta = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/version', timeout=1))
            return proc, meta['webSocketDebuggerUrl']
        except Exception:
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError('DevTools 가 안 뜸')


def capture(browser_ws, host, cookies, url):
    """새 탭을 만들고 쿠키 주입 후 url 을 열어 (png_path 여부, 콘솔에러, 실패요청) 수집."""
    b = CDP(browser_ws)
    tgt, _ = b.call('Target.createTarget', {'url': 'about:blank'})
    tid = tgt['targetId']
    info = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json', timeout=2))
    ws_url = next(t['webSocketDebuggerUrl'] for t in info if t['id'] == tid)
    p = CDP(ws_url)
    p.call('Network.enable')
    p.call('Runtime.enable')
    p.call('Page.enable')
    for name, val in cookies.items():
        p.call('Network.setCookie', {'name': name, 'value': val, 'domain': host, 'path': '/'})
    console, failed = [], []
    p.call('Page.navigate', {'url': url})
    time.sleep(3.5)  # 렌더/네트워크 정착 대기
    # 이벤트 배수: 남은 메시지를 훑어 콘솔 에러/네트워크 실패를 모은다
    p.ws.sock.settimeout(0.5)
    try:
        while True:
            msg = p.ws.recv()
            m = msg.get('method')
            if m == 'Runtime.consoleAPICalled' and msg['params'].get('type') in ('error',):
                console.append(str(msg['params'].get('args', ''))[:160])
            elif m == 'Runtime.exceptionThrown':
                console.append('exception: ' + str(msg['params'])[:160])
            elif m == 'Network.loadingFailed':
                failed.append(msg['params'].get('errorText', '') + ' ' + msg['params'].get('type', ''))
    except (socket.timeout, Exception):
        pass
    p.ws.sock.settimeout(None)
    shot, _ = p.call('Page.captureScreenshot', {'format': 'png'})
    out_path = None
    if shot.get('data'):
        out_path = True
    b.call('Target.closeTarget', {'targetId': tid})
    return shot.get('data'), console, failed


def main():
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(CHROME):
        print(f'[중단] 크롬 없음: {CHROME}'); sys.exit(1)
    if not wait(f'{BASE}/user/login/'):
        print(f'[중단] 서버 무응답: {BASE} (run_all.sh 로 먼저 기동)'); sys.exit(1)

    host = urllib.parse.urlparse(BASE).hostname
    proc, browser_ws = launch_chrome()
    print(f'BASE={BASE}\n')
    header = f'{"화면":12}' + ' '.join(f'{r:>20}' for r in ROLES)
    print(header); print('-' * len(header))
    findings = {}
    try:
        sessions = {role: login(email) for role, email in ROLES.items()}
        for name, path in PAGES:
            cells = []
            for role in ROLES:
                try:
                    data, console, failed = capture(browser_ws, host, sessions[role], f'{BASE}{path}')
                    if data:
                        with open(os.path.join(OUT, f'{role}__{name}.png'), 'wb') as f:
                            f.write(base64.b64decode(data))
                    mark = 'shot'
                    if console or failed:
                        mark += f'/{len(console) + len(failed)}!'
                        findings[f'{role}/{name}'] = (console + failed)[:4]
                    cells.append(mark)
                except Exception as e:
                    cells.append(f'ERR:{type(e).__name__}')
            print(f'{name:12}' + ' '.join(f'{c:>20}' for c in cells))
    finally:
        proc.kill()

    print('\n' + '=' * 60)
    if findings:
        print(f'⚠ 콘솔에러/실패요청이 잡힌 화면 {len(findings)}개:')
        for k, v in findings.items():
            print(f'  {k}:')
            for e in v:
                print(f'    {e[:130]}')
    else:
        print('✅ 잡힌 콘솔에러/실패요청 없음')
    print(f'\n스크린샷: {OUT}/')


if __name__ == '__main__':
    main()
