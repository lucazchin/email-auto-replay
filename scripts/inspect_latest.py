# -*- coding: utf-8 -*-
"""查看未匹配简历邮件的详细内容"""
import sys
sys.path.insert(0, ".")
import urllib3
urllib3.disable_warnings()
from ewser.connection import EWSConnection
from config.loader import Config

cfg = Config()
conn = EWSConnection()
conn.connect(cfg.get("ews", "email"), cfg.get("ews", "password"), cfg.get("ews", "server"))

inbox = conn.account.inbox

# 找主题包含"简历0630"的邮件，按时间倒序
msgs = list(inbox.filter(subject__contains="0630").order_by("-datetime_received")[:3])

for i, msg in enumerate(msgs):
    print(f"\n{'='*60}")
    print(f"邮件 #{i+1}")
    print(f"主题: {msg.subject}")
    print(f"发件人: {msg.sender}")
    print(f"时间: {msg.datetime_received}")
    print(f"是否已读: {msg.is_read}")
    print(f"{'='*60}")

    text_body = getattr(msg, "text_body", "") or ""
    print(f"\n--- 纯文本正文 ---")
    if text_body.strip():
        print(text_body[:3000])
    else:
        print("(无纯文本正文)")

    # 也看HTML正文
    html_body = getattr(msg, "body", "")
    if html_body and str(html_body).strip():
        print(f"\n--- HTML 正文 (前3000字符) ---")
        try:
            h = str(html_body)
            print(h[:3000])
        except:
            print("(编码错误)")
    else:
        print(f"\n--- HTML 正文 ---")
        print("(无HTML正文)")

conn.disconnect()
