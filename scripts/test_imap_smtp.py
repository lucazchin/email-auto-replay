#!/usr/bin/env python3
"""
mail.hengtiansoft.com IMAP / SMTP 连接快速测试工具。

无需安装任何第三方依赖，纯标准库。
用法:
    python test_imap_smtp.py

会交互式询问账号密码，分别测试 IMAP 和 SMTP 连接。
"""

import imaplib
import smtplib
import ssl
import sys
from getpass import getpass

# ── 服务器信息 ──────────────────────────────────────────
IMAP_HOST = "mail.hengtiansoft.com"
IMAP_PORT = 993
SMTP_HOST = "mail.hengtiansoft.com"
SMTP_PORT = 587


def test_imap(username: str, password: str) -> bool:
    """测试 IMAP 连接：登录 → 列出邮箱 → 查收件箱 → 登出。"""
    print("\n" + "=" * 56)
    print("  [1/2] 测试 IMAP 连接 (收件协议)")
    print("=" * 56)
    conn = None
    try:
        # 创建 SSL 上下文
        ctx = ssl.create_default_context()
        print(f"  连接 {IMAP_HOST}:{IMAP_PORT} (SSL) ...", end=" ")
        conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
        print("OK")

        print(f"  登录 {username} ...", end=" ")
        conn.login(username, password)
        print("OK")

        # 列出邮箱
        print("  列出邮箱目录 ...", end=" ")
        status, mailboxes = conn.list()
        if status != "OK":
            print(f"失败: {mailboxes}")
            return False
        print(f"OK ({len(mailboxes)} 个邮箱)")

        # 尝试选中收件箱
        print("  选中 INBOX ...", end=" ")
        status, data = conn.select("INBOX")
        if status != "OK":
            print(f"失败: {data}")
            return False
        msg_count = int(data[0])
        print(f"OK (共 {msg_count} 封邮件)")

        # 如果有邮件，显示最新一封的主题
        if msg_count > 0:
            status, msg_ids = conn.search(None, "ALL")
            if status == "OK" and msg_ids[0]:
                latest_id = msg_ids[0].split()[-1]
                status, msg_data = conn.fetch(latest_id, "(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
                if status == "OK" and msg_data and msg_data[0]:
                    # 简单解析头部
                    raw = msg_data[0][1]
                    try:
                        text = raw.decode(errors="replace")
                        for line in text.splitlines():
                            line = line.strip()
                            if line.lower().startswith(("subject:", "from:", "date:")):
                                print(f"         {line}")
                    except Exception:
                        pass

        print("\n  ✅ IMAP 连接测试通过！")
        return True

    except imaplib.IMAP4.error as e:
        print(f"\n  ❌ IMAP 登录失败: {e}")
        print("     可能原因: 账号密码错误 / 未开启 IMAP / 服务器限制")
        return False
    except Exception as e:
        print(f"\n  ❌ IMAP 连接失败: {e}")
        return False
    finally:
        if conn:
            try:
                conn.logout()
            except Exception:
                pass


def test_smtp(username: str, password: str) -> bool:
    """测试 SMTP 连接：连接 → STARTTLS → 登录 → 退出。"""
    print("\n" + "=" * 56)
    print("  [2/2] 测试 SMTP 连接 (发件协议)")
    print("=" * 56)
    conn = None
    try:
        print(f"  连接 {SMTP_HOST}:{SMTP_PORT} ...", end=" ")
        conn = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        conn.set_debuglevel(False)
        print("OK")

        # 读取服务器的 ehlo 响应
        print("  EHLO ...", end=" ")
        code, _ = conn.ehlo()
        print("OK" if code == 250 else f"响应码 {code}")

        # 启动 TLS
        print("  STARTTLS ...", end=" ")
        conn.starttls()
        print("OK")

        # TLS 后再次 EHLO
        conn.ehlo()

        # 登录
        print(f"  登录 {username} ...", end=" ")
        conn.login(username, password)
        print("OK")

        print("\n  ✅ SMTP 连接测试通过！")
        print("     (未实际发送邮件，仅验证登录)")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"\n  ❌ SMTP 认证失败: {e}")
        print("     可能原因: 账号密码错误 / 未开启 SMTP / 需要独立密码")
        return False
    except smtplib.SMTPException as e:
        print(f"\n  ❌ SMTP 连接失败: {e}")
        return False
    except Exception as e:
        print(f"\n  ❌ SMTP 错误: {e}")
        return False
    finally:
        if conn:
            try:
                conn.quit()
            except Exception:
                pass


def main():
    print("=" * 56)
    print("  mail.hengtiansoft.com IMAP/SMTP 连接测试")
    print("=" * 56)
    print()
    print("此工具会测试你的账号能否通过 IMAP/SMTP 协议")
    print("直连邮箱服务器，无需浏览器。")
    print()

    # 读取账号密码
    try:
        username = input("邮箱账号 (完整地址): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        sys.exit(0)

    if not username:
        print("❌ 账号不能为空")
        sys.exit(1)

    try:
        password = getpass("邮箱密码 (输入不显示): ")
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        sys.exit(0)

    if not password:
        print("❌ 密码不能为空")
        sys.exit(1)

    # 依次测试
    imap_ok = test_imap(username, password)
    smtp_ok = test_smtp(username, password)

    # 总结
    print("\n" + "=" * 56)
    print("  测试总结")
    print("=" * 56)
    print(f"  IMAP (收件): {'✅ 通过' if imap_ok else '❌ 失败'}")
    print(f"  SMTP (发件): {'✅ 通过' if smtp_ok else '❌ 失败'}")
    print()

    if imap_ok and smtp_ok:
        print("  🎉 全部通过！可以用 IMAP + SMTP 替代浏览器自动化方案。")
        print()
        print("  下一步建议:")
        print("    - IMAP 收件无需 Playwright，更稳定高效")
        print("    - 可以参考此脚本改写 monitor/inbox_checker.py")
        print("    - 参考 reply_sender.py 用 smtplib 发送回复")
    elif imap_ok:
        print("  ⚠️  IMAP 可用，但 SMTP 有问题。收发邮件的账号可能不同。")
    elif smtp_ok:
        print("  ⚠️  SMTP 可用，但 IMAP 有问题。检查服务器是否开启 IMAP。")
    else:
        print("  ❌ 两个协议都失败了。可能原因:")
        print("    1. 账号密码错误")
        print("    2. 邮箱服务器未开启 IMAP/SMTP（需管理员开通）")
        print("    3. 公司网络策略阻止了这些端口")
        print("    4. 需要使用独立的应用密码（非登录密码）")
        print()
        print("  如果确实无法使用标准协议，可以继续用现有的")
        print("  Playwright OWA 方案。运行:")
        print("    cd d:/AI/email-auto-replay")
        print("    python main.py")

    sys.exit(0 if (imap_ok and smtp_ok) else 1)


if __name__ == "__main__":
    main()
