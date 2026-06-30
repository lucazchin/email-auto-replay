"""
收件箱轮询核心逻辑（EWS 版）。
使用 exchangelib 替代 Playwright 浏览器自动化，直接通过 EWS API 操作邮箱。
"""
from loguru import logger
from exchangelib import Account, Message
from config.loader import Config
from monitor.rule_matcher import RuleMatcher
from monitor.content_extractor import ContentExtractor
from ai.adapter_factory import get_ai_adapter
from ai.regex_engine import RegexReplyEngine
from db.models import EmailRecord, ReplyRecord, Rule
from ewser.reply import EWSReplySender


class InboxChecker:
    """收件箱检查器（EWS 版），每轮轮询的核心入口。"""

    def __init__(self, account: Account, mailbox: dict):
        self.account = account
        self.mailbox = mailbox
        self.config = Config()
        self.ai_adapter = get_ai_adapter(self.config)
        self.content_extractor = ContentExtractor()
        self.reply_sender = EWSReplySender()

    def run(self):
        """主入口：检查收件箱并处理新邮件。"""
        logger.info(f"开始检查邮箱: {self.mailbox['email']}")

        # 获取所有未读邮件（最多处理 max_emails_per_run 封）
        max_emails = self.config.get("ews", "max_emails_per_run", default=20)
        try:
            # .only() → .order_by() → [:N] 返回 islice，需要 list() 实体化
            unread_messages = list(
                self.account.inbox.filter(is_read=False)
                .only(
                    "message_id", "changekey", "sender", "subject",
                    "text_body", "body", "datetime_received",
                )
                .order_by("-datetime_received")[:max_emails]
            )
        except Exception as e:
            logger.error(f"获取未读邮件失败: {e}")
            return

        if not unread_messages:
            logger.info("无未读邮件")
            return

        logger.info(f"发现 {len(unread_messages)} 封未读邮件")

        # 只处理最新一封（抢简历场景：抢最新到达的）
        self._process_message(unread_messages[0])

        logger.info("本轮检查完成")

    def _process_message(self, message: Message) -> bool:
        """处理单封邮件：提取 → 匹配 → AI回复 → 发送 → 记录。"""
        # 1. 提取 mail_uid（幂等去重核心）
        mail_uid = self._extract_mail_uid(message)
        if not mail_uid:
            logger.warning("无法提取 mail_uid，跳过")
            return False

        # 2. 检查是否已处理
        if EmailRecord.is_processed(mail_uid):
            logger.debug(f"邮件已处理，跳过: {mail_uid}")
            self._mark_read(message)
            return False

        # 3. 提取发件人、主题、正文
        sender = self._extract_sender(message)
        subject = message.subject or ""
        body = self._extract_body(message)

        # 3a. 跳过自己的邮件（防止回复-收到-再回复的死循环）
        own_email = self.account.primary_smtp_address.lower()
        if self._extract_sender_email(message).lower() == own_email:
            logger.info(f"跳过自己的邮件: {subject[:50]}")
            self._mark_read(message)
            return False

        logger.info(
            f"邮件: uid={mail_uid}, "
            f"sender={sender}, "
            f"subject={subject[:50] if subject else ''}"
        )

        # 3b. 二次去重：剥离 Re:/Fwd:/答复:/转发: 前缀后对比发件人+主题
        # 防止邮件被多次转发/回复后主题变化导致的主键去重绕过
        import re as _re
        stripped_subject = _re.sub(
            r'^(?:(?:Re|Fwd|答复|转发)\s*:\s*)+', '', subject, flags=_re.IGNORECASE
        ).strip()
        if EmailRecord.has_replied_same_subject_sender(
            self.mailbox["id"], sender, stripped_subject,
        ):
            logger.info(
                f"发件人+主题(去前缀后)已回复过，跳过: "
                f"sender={sender}, subject={stripped_subject[:30]}"
            )
            self._mark_read(message)
            return False

        # 4. 匹配规则
        rules = Rule.get_active_rules(self.mailbox["id"])
        matched_rule = RuleMatcher.match(sender, subject, body, rules)

        if not matched_rule:
            logger.info(
                f"邮件不匹配任何规则，跳过: "
                f"sender={sender}, subject={subject[:30] if subject else ''}"
            )
            EmailRecord.insert_or_get(
                mail_uid, self.mailbox["id"], sender, subject, body
            )
            self._mark_read(message)
            return False

        # 5. 清洗正文
        clean_body = self.content_extractor.clean(body)

        # 6. 生成回复
        #    regex 模式：正则提取，失败则静默跳过（不回复）
        #    ai 模式：调用 AI 生成
        reply_mode = matched_rule.get("reply_mode", "ai")
        reply_pattern = matched_rule.get("reply_pattern")
        reply_template = matched_rule.get("reply_template")
        reply_content = None

        if reply_mode == "regex" and reply_pattern and reply_template:
            reply_content = RegexReplyEngine.generate(
                reply_pattern=reply_pattern,
                reply_template=reply_template,
                sender=sender,
                subject=subject,
                body=body,           # 原始正文(保留换行), text: 模式走这里
                raw_body=body,       # 原始正文, table: 模式走这里
            )
            if reply_content:
                logger.info(f"正则回复生成 ({len(reply_content)} 字符)")
            else:
                logger.warning(
                    f"正则未匹配到有效内容，跳过回复（不回退AI）: "
                    f"subject={subject[:30] if subject else ''}"
                )
                self._mark_read(message)
                return False
        elif reply_mode == "ai":
            try:
                reply_content = self.ai_adapter.generate(
                    prompt_template=matched_rule["prompt_template"],
                    email_content=clean_body,
                    system_prompt=matched_rule.get("system_prompt"),
                )
                logger.info(f"AI 回复生成完成 ({len(reply_content)} 字符)")
            except Exception as e:
                logger.error(f"AI 回复生成失败: {e}")
                return False

        # 7. 写入数据库
        email_id, already_processed = EmailRecord.insert_or_get(
            mail_uid, self.mailbox["id"], sender, subject, body
        )
        reply_id = ReplyRecord.create(email_id, reply_content, status="pending")

        # 8. 发送回复
        if matched_rule["auto_send"] == 1:
            try:
                self.reply_sender.send(message, reply_content)
                ReplyRecord.update_status(reply_id, "sent")
                EmailRecord.mark_processed(email_id)
                self._mark_read(message)
                logger.info(f"回复发送成功: mail_uid={mail_uid}")
                return True
            except Exception as e:
                ReplyRecord.update_status(reply_id, "failed", str(e))
                logger.error(f"回复发送失败: {e}")
                return False
        else:
            logger.info(f"人工审核模式，未自动发送: mail_uid={mail_uid}")
            EmailRecord.mark_processed(email_id)
            self._mark_read(message)
            return True

    # ── 提取方法 ──

    def _extract_mail_uid(self, message: Message) -> str:
        """
        提取邮件唯一标识。
        仅用 message_id（Exchange 全局唯一、永不变化）。
        注意：changekey 可能随读/写操作而变化，不可用于冪等。
        """
        mid = getattr(message, "message_id", None) or getattr(message, "id", None)
        return f"ews:{mid}" if mid else ""

    def _extract_sender(self, message: Message) -> str:
        """提取发件人信息。返回 "显示名 <邮箱>" 或纯邮箱。"""
        try:
            s = message.sender
            if s is None:
                return ""
            name = getattr(s, "name", "") or ""
            addr = getattr(s, "email_address", "") or ""
            if name and addr:
                return f"{name} <{addr}>"
            if addr:
                return addr
            return name
        except Exception:
            return ""

    def _extract_sender_email(self, message: Message) -> str:
        """提取发件人纯邮箱（用于自我检测）。"""
        try:
            s = message.sender
            if s is None:
                return ""
            return getattr(s, "email_address", "") or ""
        except Exception:
            return ""

    def _extract_body(self, message: Message) -> str:
        """提取邮件正文。优先 text_body（纯文本），否则从 HTML body 提取。"""
        # 优先使用纯文本正文
        text = getattr(message, "text_body", None)
        if text and text.strip():
            return text.strip()

        # 回退到 HTML body
        try:
            from html2text import html2text
            html = getattr(message, "body", None)
            if html and html.strip():
                return html2text(html).strip()
        except ImportError:
            pass

        # 最后尝试 body 的文本形式
        try:
            body_val = getattr(message, "body", None)
            if body_val and str(body_val).strip():
                return str(body_val).strip()
        except Exception:
            pass

        return ""

    def _mark_read(self, message: Message):
        """将邮件标记为已读，避免下次轮询重复扫描。"""
        try:
            message.is_read = True
            message.save(update_fields=["is_read"])
        except Exception as e:
            logger.warning(f"标记已读失败（不影响主流程）: {e}")
