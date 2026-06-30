# -*- coding: utf-8 -*-
"""查看真实简历邮件格式，辅助修正正则匹配规则"""
import sys
sys.path.insert(0, ".")
import urllib3
urllib3.disable_warnings()

from ewser.connection import EWSConnection
from db.models import Rule, Mailbox
from db.connection import DBPool
from config.loader import Config

cfg = Config()

# 1. 连接 EWS
print("=" * 60)
print("  连接 EWS...")
conn = EWSConnection()
conn.connect(
    cfg.get("ews", "email"),
    cfg.get("ews", "password"),
    cfg.get("ews", "server"),
)
print(f"  已连接: {conn.account.version.fullname}")

# 2. 读取数据库中的启用的邮箱和规则
print("\n" + "=" * 60)
print("  启用的邮箱和规则：")
mailboxes = Mailbox.get_active()
for mb in mailboxes:
    rules = Rule.get_active_rules(mb["id"])
    print(f"\n  邮箱 #{mb['id']}: {mb['email']} (共 {len(rules)} 条规则)")
    for r in rules:
        print(f"    规则 #{r['id']}: {r['rule_name']}")
        print(f"      sender_pattern: {r.get('sender_pattern') or '(不限)'}")
        print(f"      subject_pattern: {r.get('subject_pattern') or '(不限)'}")
        print(f"      content_pattern: {r.get('content_pattern') or '(不限)'}")
        print(f"      reply_mode: {r.get('reply_mode')}")
        print(f"      reply_pattern: {r.get('reply_pattern', '')[:80]}")
        print(f"      reply_template: {r.get('reply_template', '')[:80]}")
        print(f"      auto_send: {r['auto_send']}")

# 3. 查看收件箱最近邮件（未读 + 已读各取5封）
print("\n" + "=" * 60)
print("  收件箱最近邮件（按时间倒序）：")
inbox = conn.account.inbox

# 未读
unread = list(inbox.filter(is_read=False).order_by("-datetime_received")[:5])
print(f"\n  未读邮件 ({len(unread)} 封):")
for i, msg in enumerate(unread):
    sender = str(getattr(msg, "sender", ""))
    subj = msg.subject or ""
    print(f"\n  [{i+1}] {subj[:80]}")
    print(f"      发件人: {sender}")
    print(f"      时间: {msg.datetime_received}")

# 最近已读
recent = list(inbox.filter(is_read=True).order_by("-datetime_received")[:5])
print(f"\n  最近已读邮件 ({len(recent)} 封):")
for i, msg in enumerate(recent):
    sender = str(getattr(msg, "sender", ""))
    subj = msg.subject or ""
    print(f"\n  [{i+1}] {subj[:80]}")
    print(f"      发件人: {sender}")
    print(f"      时间: {msg.datetime_received}")

# 4. 展示简历邮件的正文内容（前3封，前1000字符）
print("\n" + "=" * 60)
print("  简历相关邮件正文预览（前1000字符）：")
print("=" * 60)

# 收集所有可能匹配简历规则的邮件
all_messages = unread + recent
shown = 0
for msg in all_messages:
    if shown >= 5:
        break

    subj = msg.subject or ""
    sender = str(getattr(msg, "sender", ""))

    # 用规则粗略判断是否可能是简历邮件
    is_resume = False
    for r in rules:
        import re
        sp = r.get("sender_pattern")
        sup = r.get("subject_pattern")
        if sp and re.search(sp, sender, re.IGNORECASE):
            is_resume = True
            break
        if sup and re.search(sup, subj, re.IGNORECASE):
            is_resume = True
            break

    if not is_resume:
        continue

    shown += 1
    text_body = getattr(msg, "text_body", "") or ""
    body_text = text_body[:1500] if text_body else "(无纯文本正文)"

    print(f"\n--- 邮件 #{shown} ---")
    print(f"主题: {subj[:100]}")
    print(f"发件人: {sender}")
    print(f"正文预览:\n{body_text}")
    print("-" * 40)

if shown == 0:
    print("\n  没有找到匹配规则的简历邮件。")
    print("  正在展示所有邮件的前200字符作为参考...")
    for i, msg in enumerate(all_messages[:3]):
        text_body = getattr(msg, "text_body", "") or ""
        print(f"\n--- 邮件 #{i+1}: {msg.subject[:60]} ---")
        print(f"发件人: {getattr(msg, 'sender', '')}")
        print(f"正文: {text_body[:300]}")

DBPool.close_pool()
conn.disconnect()
