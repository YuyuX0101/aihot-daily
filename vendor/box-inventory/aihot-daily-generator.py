#!/usr/bin/env python3
r"""
AI HOT 日报自动生成脚本（Linux/box 环境适配版，CDP 直控独立 Chrome 实例）

源自惠普 aihot-daily-generator-win.py；业务逻辑（抓取/筛选/HTML/飞书）未改。
环境适配：Chrome 二进制、Linux 进程清理、仓库/日志/飞书路径、HTTPS remote。
仍禁止 headless（有头 + 移出屏外），与惠普实测一致。

用法：
    python aihot-daily-generator.py [YYYY-MM-DD] [--dry-run]

默认目标日期为昨天。--dry-run 跑完整流程但跳过 git 提交推送与飞书通知。
"""

import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from html import escape

# 定时任务环境 stdout/stderr 默认 GBK（cp936），新闻标题含 ő 等非 GBK 字符时
# print 会抛 UnicodeEncodeError 中断全流程（2026-10-13 实踩）。保留原编码，
# 只把无法编码的字符替换掉；日志文件始终写完整 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

# ==================== 配置 ====================
AIHOT_URL = "https://aihot.virxact.com/"
# box 工作区：Pages 仓已 clone 为 aihot-daily；HTTPS + askpass（与 OSR 同套）
_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.environ.get("AIHOT_REPO_DIR", os.path.join(os.path.dirname(_ROOT), "aihot-daily"))
REPO_URL = os.environ.get("AIHOT_REPO_URL", "https://github.com/YuyuX0101/aihot-daily.git")
TEMPLATE_FILE = os.path.join(REPO_DIR, "daily-template.html")
DAYS_JSON = os.path.join(REPO_DIR, "days.json")
SCORE_THRESHOLD = 75
KEEP_DAYS = 30

LOG_DIR = os.environ.get("AIHOT_LOG_DIR", os.path.join(_ROOT, "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "aihot-daily-generator.log")

# 独立浏览器实例临时配置目录（每次运行前清空）。变量名沿用 EDGE_* 以减小 diff。
EDGE_PROFILE_DIR = os.path.join(LOG_DIR, "chrome-runtime-profile")

# Kimi Work 共享飞书通知模块（box 已拷贝）
KIMI_WORK_DIR = os.environ.get(
    "AIHOT_KIMI_WORK_DIR",
    "/home/box/agent-data/daily-radar/kimi-work",
)
sys.path.insert(0, KIMI_WORK_DIR)

_log_fh = open(LOG_FILE, "a", encoding="utf-8")


def log(msg):
    """统一日志：同时写日志文件和标准输出。"""
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    _log_fh.write(line + "\n")
    _log_fh.flush()
    print(line, flush=True)


# 分类映射
CATEGORY_MAP = {
    "模型发布/更新": ["模型", "开源", "发布", "GPT", "Claude", "Gemini", "DeepSeek", "Grok", "Llama", "Mistral", "Qwen", "Kimi", "Ornith", "VibeThinker"],
    "产品发布/更新": ["产品", "上线", "推出", "发布", "API", "App", "应用", "输入法", "工具", "平台"],
    "行业动态": ["收购", "合并", "融资", "IPO", "上市", "监管", "政策", "法案", "诉讼", "起诉", "利润", "财报", "市场", "行业"],
    "论文研究": ["论文", "研究", "框架", "基准", "Benchmark", "模型架构", "训练", "解码", "投机解码"],
    "技巧与观点": ["技巧", "观点", "Prompt", "Vibe Coding", "经验", "分享", "分析", "报告"],
}


# ==================== 标准库 WebSocket 客户端（CDP 用） ====================

class MiniWS:
    """最小化 RFC6455 WebSocket 客户端（仅 localhost CDP 用途，文本帧）。"""

    def __init__(self, url, timeout=120):
        m = re.match(r"ws://([^:/]+):(\d+)(/.*)", url)
        if not m:
            raise ValueError(f"非法 ws 地址: {url}")
        host, port, path = m.group(1), int(m.group(2)), m.group(3)
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        handshake = (
            f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(handshake.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("WebSocket 握手失败：连接被关闭")
            resp += chunk
        if b" 101" not in resp.split(b"\r\n", 1)[0]:
            raise ConnectionError(f"WebSocket 握手被拒绝: {resp.split(chr(13).encode())[0]}")

    def _read_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("WebSocket 连接中断")
            data += chunk
        return data

    def send_text(self, text):
        payload = text.encode("utf-8")
        header = bytearray([0x81])  # FIN + text
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n <= 0xFFFF:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _send_frame(self, opcode, payload=b""):
        header = bytearray([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n <= 0xFFFF:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def recv_text(self):
        """接收一条完整文本消息（处理分片与 ping）。连接关闭抛异常。"""
        parts = []
        while True:
            b1, b2 = self._read_exact(2)
            fin = b1 & 0x80
            opcode = b1 & 0x0F
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read_exact(8))[0]
            payload = self._read_exact(length) if length else b""
            if opcode == 0x9:  # ping -> pong
                self._send_frame(0xA, payload)
                continue
            if opcode == 0x8:
                raise ConnectionError("WebSocket 收到关闭帧")
            if opcode in (0x0, 0x1, 0x2):
                parts.append(payload)
                if fin:
                    return b"".join(parts).decode("utf-8", "replace")

    def close(self):
        try:
            self._send_frame(0x8)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


# ==================== CDP 控制 ====================

class CDPBrowser:
    """通过 CDP 控制一个独立 Edge 实例中的单个标签页。"""

    def __init__(self, port):
        self.port = port
        self.ws = None
        self._msg_id = 0

    @staticmethod
    def _http_json(path, port, timeout=5):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def wait_ready(self, timeout=45):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                self._http_json("/json/version", self.port, timeout=3)
                return True
            except Exception:
                time.sleep(1)
        return False

    def attach_page(self):
        """连接到实例中已有的页面标签页（优先 about:blank）。"""
        targets = [t for t in self._http_json("/json/list", self.port) if t.get("type") == "page"]
        if not targets:
            raise RuntimeError("CDP 实例中没有可用的页面标签页")
        target = next((t for t in targets if t.get("url", "").startswith("about:blank")), targets[0])
        self.ws = MiniWS(target["webSocketDebuggerUrl"])
        return target

    def call(self, method, params=None):
        self._msg_id += 1
        mid = self._msg_id
        self.ws.send_text(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv_text())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method} 失败: {msg['error']}")
                return msg.get("result", {})

    def navigate(self, url, wait_secs=3, ready_timeout=20):
        self.call("Page.navigate", {"url": url})
        deadline = time.time() + ready_timeout
        while time.time() < deadline:
            try:
                state = self.evaluate("document.readyState")
                if state == "complete":
                    break
            except Exception:
                pass
            time.sleep(0.5)
        time.sleep(wait_secs)  # 等异步内容

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": False,
        })
        remote = result.get("result", {})
        if result.get("exceptionDetails"):
            raise RuntimeError(f"页面 JS 执行异常: {result['exceptionDetails'].get('text')}")
        return remote.get("value")

    def close_browser(self):
        """通过 CDP 优雅关闭整个浏览器实例。"""
        try:
            ver = self._http_json("/json/version", self.port, timeout=3)
            browser_ws = MiniWS(ver["webSocketDebuggerUrl"])
            browser_ws.send_text(json.dumps({"id": 1, "method": "Browser.close", "params": {}}))
            time.sleep(1)
            browser_ws.close()
        except Exception as e:
            log(f"[CLEANUP] CDP Browser.close 未生效: {e}")
        if self.ws:
            self.ws.close()


# ==================== Edge 实例管理 ====================

_EDGE_PROC = None


def _pick_free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _write_edge_preferences(user_data_dir):
    """预写 Preferences，压制首次运行向导/同步提示。"""
    default_dir = os.path.join(user_data_dir, "Default")
    os.makedirs(default_dir, exist_ok=True)
    prefs = {
        "browser": {"show_welcome_page": False, "has_seen_welcome_page": True},
        "edge": {"first_run": False, "show_first_run_experience": False},
        "signin": {"allowed_on_next_startup": False},
        "sync_promo": {"show_sync_promo": False, "showed_sync_promo": True},
    }
    with open(os.path.join(default_dir, "Preferences"), "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False)


def _kill_edge_by_profile_dir():
    """按命令行中的临时配置目录精确关闭 Chrome 进程（Linux）。

    启动器进程（Popen.pid）可能秒退，真正的浏览器进程是另一批 PID；
    但它们的命令行都带有本脚本独有的 user-data-dir，匹配它只会命中本脚本实例。"""
    marker = EDGE_PROFILE_DIR
    pids = []
    try:
        r = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True, timeout=30)
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line or marker not in line:
                continue
            # 只杀 chrome/google-chrome，避免误伤编辑器等碰巧打开同路径的进程
            low = line.lower()
            if "chrome" not in low and "chromium" not in low:
                continue
            try:
                pid = int(line.split(None, 1)[0])
            except ValueError:
                continue
            if pid == os.getpid():
                continue
            pids.append(pid)
    except Exception as e:
        log(f"[CLEANUP] 查询 Chrome 进程失败: {e}")
        return
    for pid in pids:
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
        except Exception as e:
            log(f"[CLEANUP] kill PID={pid} 失败: {e}")
    if pids:
        log(f"[CLEANUP] 按配置目录关闭 {len(pids)} 个 Chrome 进程: {pids}")


def _find_chrome_binary():
    env = os.environ.get("AIHOT_CHROME_BIN")
    if env and os.path.exists(env):
        return env
    for p in (
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        shutil.which("google-chrome-stable") or "",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
    ):
        if p and os.path.exists(p):
            return p
    return None


def start_edge():
    """启动独立 Chrome 实例（有头但窗口移出屏幕外 + 空配置目录 + CDP 端口），返回 CDPBrowser。

    语义对齐惠普 Edge 版：--window-position=-32000,-32000 有头模式；禁止 headless
    （2026-07-20 实测 headless 抽不到 aihot 数据）。box 无 Edge，改用 google-chrome；
    Linux 容器另加 --no-sandbox / --disable-dev-shm-usage。
    """
    global _EDGE_PROC
    edge_path = _find_chrome_binary()
    if not edge_path:
        raise RuntimeError("未找到 Chrome/Chromium 可执行文件（box 无 Edge，需 google-chrome）")

    # 与惠普相同：最多 3 次尝试，每次换新端口、等待 60 秒，失败后彻底清理再重试。
    last_error = None
    for attempt in range(1, 4):
        if os.path.exists(EDGE_PROFILE_DIR):
            _kill_edge_by_profile_dir()
            time.sleep(1)
            shutil.rmtree(EDGE_PROFILE_DIR, ignore_errors=True)
        os.makedirs(EDGE_PROFILE_DIR, exist_ok=True)
        _write_edge_preferences(EDGE_PROFILE_DIR)

        port = _pick_free_port()
        args = [
            edge_path,
            "--new-window",
            "--window-position=-32000,-32000",
            f"--user-data-dir={EDGE_PROFILE_DIR}",
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-default-apps",
            "--mute-audio",
            "--disable-session-crashed-bubble",
            "--hide-crash-restore-bubble",
            "--window-size=1280,900",
            # Linux/box 环境适配（容器/无特权常见需要）
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "about:blank",
        ]
        env = os.environ.copy()
        # 保证有显示；调用方可显式传 DISPLAY=:4
        env.setdefault("DISPLAY", ":4")
        _EDGE_PROC = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
        )
        log(f"[INFO] 已启动独立 Chrome 实例（PID={_EDGE_PROC.pid}, CDP 端口={port}，第 {attempt}/3 次尝试）")

        cdp = CDPBrowser(port)
        if cdp.wait_ready(timeout=60):
            cdp.attach_page()
            log("[INFO] CDP 已连接到实例标签页")
            return cdp

        last_error = f"Chrome 实例 CDP 端口 60 秒内未就绪（第 {attempt}/3 次尝试）"
        log(f"[WARN] {last_error}，清理后重试")
        try:
            cleanup_edge()
        except Exception as e:
            log(f"[WARN] 重试前清理异常: {e}")

    raise RuntimeError(f"Chrome 实例 CDP 端口连续 3 次未就绪: {last_error}")


def cleanup_edge():
    """关闭本脚本启动的 Chrome 实例并删除临时配置目录。只动自己启动的进程树。"""
    global _EDGE_PROC
    if _EDGE_PROC is not None:
        if _EDGE_PROC.poll() is None:
            try:
                os.kill(_EDGE_PROC.pid, 9)
                log(f"[CLEANUP] 已关闭 Chrome 启动进程（PID={_EDGE_PROC.pid}）")
            except ProcessLookupError:
                pass
            except Exception as e:
                log(f"[CLEANUP] kill 启动进程失败: {e}")
        _EDGE_PROC = None
    _kill_edge_by_profile_dir()
    time.sleep(3)
    for attempt in range(3):
        try:
            shutil.rmtree(EDGE_PROFILE_DIR, ignore_errors=False)
            log("[CLEANUP] 已删除 Chrome 临时配置目录")
            break
        except Exception as e:
            log(f"[CLEANUP] 删除临时配置目录失败（尝试 {attempt+1}/3）: {e}")
            time.sleep(2)


# ==================== 页面抓取 ====================

def extract_items_from_page(cdp):
    """从 aihot 首页提取所有新闻条目分组（2026-09-29 起站点改为 Tailwind 语义结构：
    日期分组为 section[aria-label="YYYY-MM-DD"]，条目为 li[data-card-key]，
    标题在 h3 a[href*='/items/']，评分在 [title^="AI 评分"]，推荐理由在以该前缀开头的 p）"""
    code = """
    (function() {
        var groups = [];
        var sections = document.querySelectorAll("section[aria-label]");
        for (var i = 0; i < sections.length; i++) {
            var g = sections[i];
            var label = g.getAttribute("aria-label") || "";
            var dm = /^(\\d{4})-(\\d{2})-(\\d{2})$/.exec(label);
            if (!dm) continue;
            var day = parseInt(dm[2], 10) + "月" + parseInt(dm[3], 10) + "日";
            var rows = [];
            var items = g.querySelectorAll("li[data-card-key]");
            for (var j = 0; j < items.length; j++) {
                var r = items[j];
                var timeEl = r.querySelector("time[dateTime]");
                var srcEl = r.querySelector("header span");
                var scoreEl = r.querySelector("[title^='AI 评分']");
                var score = "";
                if (scoreEl) {
                    var sm = /(\\d+)/.exec(scoreEl.getAttribute("title") || "");
                    if (sm) score = sm[1];
                }
                var titleEl = r.querySelector("h3 a[href*='/items/']") || r.querySelector("a[href*='/items/']");
                var reason = "";
                var ps = r.querySelectorAll("p");
                for (var k = 0; k < ps.length; k++) {
                    var t = ps[k].textContent.trim();
                    if (t.indexOf("推荐理由：") === 0) { reason = t.replace(/^推荐理由：/, ""); break; }
                }
                rows.push({time: timeEl ? timeEl.textContent.trim() : "",
                           src: srcEl ? srcEl.textContent.trim() : "",
                           score: score,
                           title: titleEl ? titleEl.textContent.trim() : "",
                           reason: reason,
                           link: titleEl ? titleEl.href : ""});
            }
            groups.push({day: day, rows: rows});
        }
        return JSON.stringify(groups);
    })()
    """
    result = cdp.evaluate(code)
    if not result:
        return []
    try:
        return json.loads(result)
    except Exception:
        return []


def get_detail_summary(cdp, item_link):
    """导航到详情页并提取摘要（多选择器取最长）"""
    if not item_link:
        return ""
    try:
        cdp.navigate(item_link, wait_secs=4)
        code = """
        (function() {
            var results = [];
            var meta = document.querySelector("meta[name='twitter:description']") ||
                       document.querySelector("meta[property='og:description']");
            if (meta) {
                var mt = (meta.getAttribute("content") || "").trim();
                if (mt.length > 30) results.push({text: mt.substring(0, 800)});
            }
            var selectors = [".m-detail-summary-text", ".dt-summary-text", ".timeline-summary",
                             ".article-summary", ".detail-summary"];
            for (var i = 0; i < selectors.length; i++) {
                var el = document.querySelector(selectors[i]);
                if (el) {
                    var text = el.textContent.trim();
                    if (text.length > 30) results.push({text: text.substring(0, 800)});
                }
            }
            if (results.length === 0) {
                var paragraphs = document.querySelectorAll("article p, .content p, .article-body p, main p, .detail-content p, .m-detail-content p");
                var combined = "";
                for (var j = 0; j < Math.min(paragraphs.length, 2); j++) {
                    var t = paragraphs[j].textContent.trim();
                    if (t.length > 20) combined += t + " ";
                }
                if (combined.length > 50) results.push({text: combined.substring(0, 800)});
            }
            return JSON.stringify(results);
        })()
        """
        result = cdp.evaluate(code)
        summaries = json.loads(result) if result else []
        if not summaries:
            return ""
        text = max(summaries, key=lambda x: len(x.get("text", ""))).get("text", "")
        if "login" in text.lower() or "登录" in text or "虚实传媒" in text:
            return ""
        return text
    except Exception as e:
        log(f"[WARN] 详情页摘要获取失败 {item_link}: {e}")
        return ""


def parse_date(day_str):
    m = re.match(r'(\d+)月(\d+)日', day_str)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def filter_target_items(groups, target_date):
    items = []
    for g in groups:
        day_str = g.get("day", "")
        month, day = parse_date(day_str)
        if day_str == "今天":
            month, day = datetime.now().month, datetime.now().day
        if month == target_date.month and day == target_date.day:
            for r in g.get("rows", []):
                try:
                    score = int(r.get("score", "0"))
                except ValueError:
                    score = 0
                if score >= SCORE_THRESHOLD:
                    items.append({"title": r.get("title", ""), "score": score,
                                  "src": r.get("src", ""), "link": r.get("link", ""),
                                  "reason": r.get("reason", "")})
    items.sort(key=lambda x: (-x["score"], x["title"]))
    return items


def classify_item(title):
    title_lower = title.lower()
    best_cat, best_score = "行业动态", 0
    for cat, keywords in CATEGORY_MAP.items():
        score = sum(kw.lower() in title_lower for kw in keywords)
        if score > best_score:
            best_cat, best_score = cat, score
    return best_cat


# ==================== HTML 生成 ====================

def generate_top5_html(items):
    top5 = items[:5]
    if not top5:
        return ""
    html = '<section class="top5-section">\n  <div class="top5-header">\n'
    html += '    <span class="top5-title">Top 5 精选</span>\n    <span class="top5-badge">编辑精选</span>\n  </div>\n'
    for i, item in enumerate(top5, 1):
        summary = item.get("summary", item.get("reason", ""))
        html += '  <article class="top5-item">\n    <div class="top5-item-header">\n'
        html += f'      <div class="top5-item-rank">{i}</div>\n'
        html += f'      <div class="top5-item-title">{escape(item["title"])}</div>\n'
        html += f'      <span class="top5-item-score">{item["score"]}分</span>\n    </div>\n'
        html += f'    <div class="top5-item-source">{escape(item["src"])}</div>\n'
        html += f'    <div class="top5-item-summary">{escape(summary)}</div>\n'
        if item.get("link"):
            html += f'    <a href="{escape(item["link"])}" class="item-link" target="_blank">查看原文 &rarr;</a>\n'
        html += '  </article>\n'
    html += '</section>\n'
    return html


def generate_sections_html(items):
    seen, unique_items = set(), []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique_items.append(item)
    categories = {}
    for item in unique_items:
        categories.setdefault(classify_item(item["title"]), []).append(item)
    order = ["模型发布/更新", "产品发布/更新", "行业动态", "论文研究", "技巧与观点"]
    html = ""
    for cat in order:
        cat_items = categories.get(cat)
        if not cat_items:
            continue
        html += '<section class="section">\n  <div class="section-header">\n'
        html += f'    <span class="section-title">{cat}</span>\n    <span class="section-count">{len(cat_items)} 条</span>\n  </div>\n'
        for i, item in enumerate(cat_items, 1):
            summary = item.get("summary", item.get("reason", ""))
            html += '  <article class="item">\n    <div class="item-header">\n'
            html += f'      <div class="item-num">{i}</div>\n'
            html += f'      <div class="item-title">{escape(item["title"])}</div>\n    </div>\n'
            html += f'    <div class="item-source">{escape(item["src"])} &middot; {item["score"]}分</div>\n'
            html += f'    <div class="item-summary">{escape(summary)}</div>\n'
            if item.get("link"):
                html += f'    <a href="{escape(item["link"])}" class="item-link" target="_blank">查看原文 &rarr;</a>\n'
            html += '  </article>\n'
        html += '</section>\n'
    return html


def generate_daily_html(target_date, items, template):
    html = template.replace("{{DATE}}", target_date.strftime("%Y年%m月%d日"), 1)
    html = html.replace("{{DATE}}", target_date.strftime("%Y-%m-%d"), 1)
    html = html.replace("{{LEAD}}", f"精选 {len(items)} 条 AI 行业动态，涵盖模型发布、产品更新、行业事件与前沿研究。")
    html = html.replace("{{ITEM_COUNT}}", str(len(items)))
    html = html.replace("{{TOP5}}", generate_top5_html(items))
    html = html.replace("{{SECTIONS}}", generate_sections_html(items))
    html = html.replace("{{FLASHES}}", "")
    return html


# ==================== Git 与仓库 ====================

def ensure_repo():
    if not os.path.exists(REPO_DIR):
        log(f"[INFO] 克隆仓库到 {REPO_DIR}")
        r = subprocess.run(["git", "clone", REPO_URL, REPO_DIR], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            log(f"[ERROR] 克隆失败: {r.stderr}")
            return False
    else:
        r = subprocess.run(["git", "-C", REPO_DIR, "pull", "--rebase"], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            # pull 失败（如本地有未提交改动、网络抖动）不阻断主流程：
            # 生成只依赖本地模板；若远端真有分叉，最终 push 会报错并触发失败通知。
            log(f"[WARN] git pull --rebase 失败（继续用本地仓库生成）: {r.stderr.strip()}")
    return os.path.exists(TEMPLATE_FILE)


def update_days_json(target_date):
    date_str = target_date.strftime("%Y-%m-%d")
    days = []
    if os.path.exists(DAYS_JSON):
        try:
            with open(DAYS_JSON, "r", encoding="utf-8") as f:
                days = json.load(f)
        except Exception:
            days = []
    if date_str not in days:
        days.insert(0, date_str)
        with open(DAYS_JSON, "w", encoding="utf-8") as f:
            json.dump(days, f, ensure_ascii=False, indent=2)
        return True
    return False


def prune_old_reports(repo_dir, keep_days=KEEP_DAYS):
    """删除早于 今天-keep_days 的日报 html，并同步 days.json。返回删除的文件名列表。"""
    days_json_path = os.path.join(repo_dir, "days.json")
    cutoff = (datetime.now() - timedelta(days=keep_days)).date()
    log(f"[INFO] 清理旧日报: 删除早于 {cutoff} 的日报（保留近 {keep_days} 天）")
    date_file_re = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")
    deleted = []
    for fname in sorted(os.listdir(repo_dir)):
        m = date_file_re.match(fname)
        if not m:
            continue
        try:
            file_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date < cutoff:
            try:
                os.remove(os.path.join(repo_dir, fname))
                deleted.append(fname)
                log(f"[OK] 删除过期日报 {fname}")
            except OSError as e:
                log(f"[WARN] 删除过期日报失败 {fname}: {e}")
    if deleted and os.path.exists(days_json_path):
        deleted_dates = {os.path.splitext(f)[0] for f in deleted}
        try:
            with open(days_json_path, "r", encoding="utf-8") as f:
                days = json.load(f)
        except Exception:
            days = []
        new_days = [d for d in days if d not in deleted_dates]
        if new_days != days:
            with open(days_json_path, "w", encoding="utf-8") as f:
                json.dump(new_days, f, ensure_ascii=False, indent=2)
            log(f"[INFO] days.json 已移除 {len(days) - len(new_days)} 个过期日期")
    log(f"[INFO] 旧日报清理完成，共删除 {len(deleted)} 个文件")
    return deleted


def git_commit_and_push(target_date):
    date_str = target_date.strftime("%Y-%m-%d")
    subprocess.run(["git", "-C", REPO_DIR, "add", "-A"], capture_output=True, timeout=30)
    r = subprocess.run(["git", "-C", REPO_DIR, "commit", "-m", f"update: {date_str} daily"],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr).lower():
        log(f"[ERROR] git commit 失败: {r.stderr}")
        return False
    r = subprocess.run(["git", "-C", REPO_DIR, "push", "origin", "main"],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        log(f"[ERROR] git push 失败: {r.stderr}")
        return False
    return True


# ==================== 验证 ====================

def verify_html(html_file):
    with open(html_file, "r", encoding="utf-8") as f:
        content = f.read()
    checks = {
        "sidebar-toggle": "sidebar-toggle" in content,
        "sidebar-overlay": "sidebar-overlay" in content,
        "openSidebar": "openSidebar" in content,
        "top5-section": "top5-section" in content,
        "item-summary": "item-summary" in content,
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        log(f"[WARN] HTML 验证失败: {', '.join(failed)}")
        return False
    empty = len(re.findall(r'<div class="item-summary"></div>', content))
    empty += len(re.findall(r'<div class="top5-item-summary"></div>', content))
    if empty > 0:
        log(f"[WARN] 发现 {empty} 条空摘要")
        return False
    empty_titles = len(re.findall(r'<div class="item-title"></div>', content))
    empty_titles += len(re.findall(r'<div class="top5-item-title"></div>', content))
    if empty_titles > 0:
        log(f"[WARN] 发现 {empty_titles} 条空标题")
        return False
    return True


def verify_online(target_date):
    """推送后对线上页面做一次即时检查（不等待、不重试、失败静默）。

    GitHub Pages CDN 传播需要时间，刚推送完 404 属正常情况，一律视为成功，
    不写日志、不体现在通知里。"""
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"https://yuyux0101.github.io/aihot-daily/{date_str}.html"
    try:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log(f"[OK] 线上页面已可访问: {url}")
                return True
    except Exception:
        pass
    return False


# ==================== 飞书通知 ====================

def send_feishu(items, date_str, success=True, error_msg="", empty=False):
    """通过 Kimi Work 共享 webhook 模块发送通知。通知失败不影响主流程。"""
    if empty:
        text = (f"📰 AI HOT 日报 · {date_str}\n\n"
                f"今日无 {SCORE_THRESHOLD} 分以上的条目，本期为空日报，属正常情况。")
    elif success:
        lines = [f"📰 AI HOT 日报 · {date_str}", "", f"共 {len(items)} 条精选（{SCORE_THRESHOLD}分以上）", "", "🔥 Top 5："]
        for i, item in enumerate(items[:5], 1):
            lines.append(f"{i}. [{item['score']}分] {item['title']}")
        lines += ["", "👉 https://yuyux0101.github.io/aihot-daily/"]
        text = "\n".join(lines)
    else:
        text = f"❌ AI HOT 日报 · {date_str} 生成失败\n\n原因：{error_msg}"
    try:
        from feishu_notify import send_feishu_text
        ok = send_feishu_text(text)
        log("[OK] 飞书推送成功" if ok else "[WARN] 飞书推送被 webhook 拒绝（详见 stderr）")
        return ok
    except Exception as e:
        log(f"[WARN] 飞书推送异常: {e}")
        return False


# ==================== 主流程 ====================

def fail(date_str, msg, dry_run=False):
    log(f"[ERROR] {msg}")
    if not dry_run:
        send_feishu([], date_str, success=False, error_msg=msg)
    sys.exit(1)


def done_empty(date_str, msg, dry_run=False):
    """允许的'空结果'：目标日无达标条目属正常情况，发通知但不视为失败。
    exit 0 让 run-if-missed 写入当天 stamp，避免每次登录都被补跑。"""
    log(f"[OK] {msg}（空日报，正常结束）")
    if not dry_run:
        send_feishu([], date_str, empty=True)
    sys.exit(0)


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv
    if args:
        try:
            target_date = datetime.strptime(args[0], "%Y-%m-%d").date()
        except ValueError:
            print("[ERROR] 日期格式错误，应为 YYYY-MM-DD")
            sys.exit(1)
    else:
        target_date = (datetime.now() - timedelta(days=1)).date()

    date_str = target_date.strftime("%Y-%m-%d")
    log(f"[INFO] AI HOT 日报生成 — 目标日期: {date_str}" + ("（dry-run）" if dry_run else ""))

    # 1. 启动独立 Edge 实例并连接 CDP
    log("[STEP 1/7] 启动独立 Chrome 实例...")
    cdp = start_edge()

    # 2. 准备仓库
    log("[STEP 2/7] 准备仓库...")
    if not ensure_repo():
        fail(date_str, "仓库准备失败", dry_run)

    # 3. 导航到 aihot 首页（在同一个标签页工作，不开第二个）
    log("[STEP 3/7] 导航到 aihot...")
    try:
        cdp.navigate(AIHOT_URL, wait_secs=5)
    except Exception as e:
        fail(date_str, f"导航到 aihot 失败: {e}", dry_run)

    # 4. 提取并筛选
    log("[STEP 4/7] 提取新闻数据...")
    groups = extract_items_from_page(cdp)
    if not groups:
        fail(date_str, "未提取到任何数据", dry_run)
    total_rows = sum(len(g.get("rows", [])) for g in groups)
    log(f"[OK] 提取到 {len(groups)} 天分组，共 {total_rows} 条新闻")

    items = filter_target_items(groups, target_date)
    if not items:
        done_empty(date_str, f"目标日期 {date_str} 无符合条件（>={SCORE_THRESHOLD}分）的条目", dry_run)
    log(f"[OK] 筛选出 {len(items)} 条 >={SCORE_THRESHOLD} 分的条目")

    # 5. 获取摘要（逐条详情页，无需返回首页）
    log("[STEP 5/7] 获取详情页摘要...")
    for i, item in enumerate(items):
        log(f"  [{i+1}/{len(items)}] {item['title'][:30]}...")
        summary = get_detail_summary(cdp, item.get("link", ""))
        if summary and len(summary) > 20:
            item["summary"] = summary
            log(f"    详情页摘要: {len(summary)} 字符")
        else:
            reason = item.get("reason", "")
            item["summary"] = reason if len(reason) > 20 else item["title"]
            log(f"    回退首页推荐理由: {len(item['summary'])} 字符")

    # 6. 生成并验证 HTML，更新 days.json，清理旧日报
    log("[STEP 6/7] 生成日报 HTML...")
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        template = f.read()
    html = generate_daily_html(target_date, items, template)
    html_file = os.path.join(REPO_DIR, f"{date_str}.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"[OK] 生成 {html_file} ({len(html)} 字节)")

    if not verify_html(html_file):
        fail(date_str, "HTML 验证失败", dry_run)
    update_days_json(target_date)
    prune_old_reports(REPO_DIR)

    # 7. 提交推送 + 线上验证 + 飞书通知
    log("[STEP 7/7] 推送到 GitHub...")
    if dry_run:
        log("[DRY-RUN] 跳过 git 提交推送、线上验证与飞书通知")
        log("[OK] AI HOT 日报已生成并推送（dry-run：未实际推送）")
        return

    if not git_commit_and_push(target_date):
        fail(date_str, "Git 推送失败", dry_run)
    log("[OK] Git 推送完成")

    verify_online(target_date)
    log("[OK] 全流程完成")

    send_feishu(items, date_str, success=True)
    log("[OK] AI HOT 日报已生成并推送")


if __name__ == "__main__":
    exit_code = 0
    try:
        main()
    except SystemExit as e:
        exit_code = e.code or 0
        raise
    except Exception as e:
        exit_code = 1
        log(f"[ERROR] 未捕获异常: {type(e).__name__}: {e}")
        if "--dry-run" not in sys.argv:
            try:
                from feishu_notify import send_feishu_text
                send_feishu_text(f"❌ AI HOT 日报脚本异常终止\n\n{type(e).__name__}: {e}")
            except Exception:
                pass
        sys.exit(1)
    finally:
        log("[CLEANUP] 开始清理 Chrome 实例...")
        try:
            cleanup_edge()
        except Exception as e:
            log(f"[CLEANUP] 清理异常: {e}")
        _log_fh.close()
