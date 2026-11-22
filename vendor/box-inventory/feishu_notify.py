#!/usr/bin/env python3
r"""
Kimi Work 专属飞书通知模块（带签名校验的群机器人 Webhook 发送器）。

用法一（作为模块，推荐）：
    import sys
    sys.path.insert(0, r"C:\Users\Administrator\.kimi-work")
    from feishu_notify import send_feishu_text
    send_feishu_text("任务完成")

用法二（命令行，bat / 任务计划程序可用）：
    python feishu_notify.py "任务完成"

配置保存在同目录 feishu-webhook.json（url + secret），任务脚本一律不得硬编码。
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feishu-webhook.json")


def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("url") or not cfg.get("secret"):
        raise ValueError(f"配置文件缺少 url/secret: {CONFIG_PATH}")
    return cfg["url"], cfg["secret"]


def _sign(secret, timestamp):
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _deliver(payload, timeout, label):
    """发送已组好的 payload；命中频率限制(code 11232)自动退避重试，最多 3 次。"""
    url, secret = _load_config()
    ts = str(int(time.time()))
    payload["timestamp"] = ts
    payload["sign"] = _sign(secret, ts)
    for attempt in range(3):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[feishu_notify] {label}发送异常: {e}", file=sys.stderr)
            return False
        if body.get("code") == 0 or body.get("StatusCode") == 0:
            return True
        if body.get("code") == 11232 and attempt < 2:  # 频率限制，退避后重试
            time.sleep(20)
            continue
        print(f"[feishu_notify] {label}发送被拒: {body}", file=sys.stderr)
        return False
    return False


def send_feishu_text(text, timeout=15):
    """发送文本消息到 Kimi Work 专属飞书群。成功返回 True，失败返回 False 并打印原因。"""
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    return _deliver(payload, timeout, "文本")


def send_feishu_post(title, lines=None, timeout=15):
    """发送富文本消息（标题 + 若干行文本）到 Kimi Work 专属飞书群。

    title: 消息标题（支持 emoji）
    lines: 字符串列表（每字符串一行）；也允许传单个字符串或省略。
           元组/列表会自动拼成 "a：b" 一行，其他类型转 str，避免 19002 参数错误。
    失败时返回 False 并打印原因；调用方应自行决定是否回退到 send_feishu_text。
    """
    if lines is None:
        lines = []
    if isinstance(lines, str):
        lines = [lines]
    norm = []
    for line in lines:
        if isinstance(line, str):
            norm.append(line)
        elif isinstance(line, (tuple, list)):
            norm.append("：".join(str(x) for x in line))
        else:
            norm.append(str(line))
    content = [[{"tag": "text", "text": line}] for line in norm]
    payload = {
        "msg_type": "post",
        "content": {"post": {"zh_cn": {"title": title, "content": content}}},
    }
    return _deliver(payload, timeout, "富文本")


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('用法: python feishu_notify.py "消息内容"')
        sys.exit(2)
    ok = send_feishu_text(sys.argv[1])
    print("OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)
