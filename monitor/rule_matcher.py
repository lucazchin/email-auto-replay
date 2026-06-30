"""
规则匹配引擎：支持多条件组合匹配。
替代原 sender_matcher.py，支持发件人 + 主题 + 正文关键词 + AND/OR 逻辑 + 优先级。

匹配规则：
1. 每条 rule 可配置 0-3 个匹配条件（sender_pattern / subject_pattern / content_pattern）
2. NULL 的条件视为"不限制"（自动通过）
3. match_logic: AND=所有非 NULL 条件都满足，OR=任一非 NULL 条件满足
4. 多条规则按 priority 升序匹配，第一条命中即返回
"""
import re
from loguru import logger


class RuleMatcher:
    """多条件规则匹配引擎。"""

    @staticmethod
    def match(sender: str, subject: str, body: str, rules: list) -> dict | None:
        """
        对邮件按规则列表进行匹配。
        :param sender: 发件人信息（可能是 "显示名 <邮箱>" 或 "显示名" 或 "邮箱"）
        :param subject: 邮件主题
        :param body: 邮件正文（建议传入清洗后的纯文本）
        :param rules: 规则列表（已按 priority 排序）
        :return: 第一个命中的规则 dict，无匹配返回 None
        """
        if not rules:
            return None

        # 解析 sender：分离显示名和邮箱
        sender_display, sender_email = RuleMatcher._parse_sender(sender)
        # 组合文本：用于宽泛匹配（显示名 + 邮箱一起）
        sender_combined = sender.strip()
        if sender_email and sender_email not in sender_combined:
            sender_combined = f"{sender_combined} {sender_email}"

        logger.debug(
            f"开始匹配 {len(rules)} 条规则: "
            f"sender_display={sender_display}, sender_email={sender_email}, "
            f"subject={subject[:30] if subject else ''}"
        )

        for rule in rules:
            if not RuleMatcher._is_rule_enabled(rule):
                continue

            if RuleMatcher._match_single_rule(
                rule, sender_combined, sender_email, sender_display, subject, body
            ):
                logger.info(
                    f"规则命中: rule#{rule['id']} "
                    f"({rule.get('rule_name', 'unnamed')})"
                )
                return rule

        logger.info("所有规则均未命中")
        return None

    @staticmethod
    def _parse_sender(sender: str):
        """
        从 sender 字符串中解析显示名和邮箱。
        输入格式可能是：
        - "显示名 <email@example.com>"
        - "email@example.com"
        - "显示名"（无邮箱）
        :return: (display_name, email)
        """
        if not sender:
            return "", ""

        import re as _re

        # "Name <email>" 格式
        if "<" in sender and ">" in sender:
            email_match = _re.search(
                r'<([^>]+@[^>]+)>', sender
            )
            if email_match:
                email = email_match.group(1).strip()
                display = sender.split("<")[0].strip()
                return display, email

        # 纯邮箱
        email_match = _re.search(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            sender
        )
        if email_match and sender.strip() == email_match.group():
            return "", sender.strip()

        # 只有显示名
        return sender.strip(), ""

    @staticmethod
    def _is_rule_enabled(rule: dict) -> bool:
        """检查规则是否启用。"""
        enabled = rule.get("enabled", 1)
        return enabled == 1 or enabled is True

    @staticmethod
    def _match_single_rule(rule: dict, sender_combined: str,
                            sender_email: str, sender_display: str,
                            subject: str, body: str) -> bool:
        """
        判断单条规则是否匹配。
        sender_pattern 会同时尝试匹配：
        1. 组合文本（显示名 + 邮箱）
        2. 纯邮箱
        3. 纯显示名
        任一匹配即视为该条件满足。
        """
        logic = (rule.get("match_logic") or "AND").upper()

        # 收集所有配置的条件（非 NULL 的 pattern）
        conditions = []

        sender_pattern = rule.get("sender_pattern")
        if sender_pattern:
            conditions.append(("sender", sender_pattern,
                               (sender_combined, sender_email, sender_display)))

        subject_pattern = rule.get("subject_pattern")
        if subject_pattern:
            conditions.append(("subject", subject_pattern, subject or ""))

        content_pattern = rule.get("content_pattern")
        if content_pattern:
            conditions.append(("content", content_pattern, body or ""))

        # 没有任何条件 → 视为通配，命中
        if not conditions:
            logger.debug(f"rule#{rule.get('id')}: 无匹配条件，直接命中")
            return True

        # 逐个条件匹配
        results = []
        for field_name, pattern, text in conditions:
            if field_name == "sender":
                # sender 特殊处理：尝试多个文本
                matched = RuleMatcher._match_sender(
                    pattern, sender_combined, sender_email, sender_display
                )
            else:
                matched = RuleMatcher._regex_match(pattern, text)
            results.append((field_name, matched))
            logger.debug(
                f"rule#{rule.get('id')} {field_name}: pattern={pattern!r}, "
                f"matched={matched}"
            )

        # 根据 logic 组合
        all_matched = all(r[1] for r in results)
        any_matched = any(r[1] for r in results)

        if logic == "AND":
            return all_matched
        elif logic == "OR":
            return any_matched
        else:
            logger.warning(f"rule#{rule.get('id')} 未知 match_logic: {logic}，按 AND 处理")
            return all_matched

    @staticmethod
    def _match_sender(pattern: str, combined: str, email: str, display: str) -> bool:
        """
        发件人匹配：尝试多个文本，任一匹配即返回 True。
        - 先匹配组合文本（显示名 <邮箱>）
        - 再匹配纯邮箱
        - 再匹配纯显示名
        """
        # 1. 组合文本
        if combined and RuleMatcher._regex_match(pattern, combined):
            return True
        # 2. 纯邮箱
        if email and RuleMatcher._regex_match(pattern, email):
            return True
        # 3. 纯显示名
        if display and RuleMatcher._regex_match(pattern, display):
            return True
        return False

    @staticmethod
    def _regex_match(pattern: str, text: str) -> bool:
        """
        正则匹配，大小写不敏感。
        :param pattern: 正则表达式
        :param text: 待匹配文本
        :return: 是否匹配
        """
        if not pattern:
            return True
        if not text:
            return False
        try:
            return bool(re.search(pattern, text, re.IGNORECASE))
        except re.error as e:
            logger.error(f"正则表达式无效: {pattern}, 错误: {e}")
            return False


# ============================================
# 向后兼容：保留 SenderMatcher 作为 RuleMatcher 的别名
# 旧代码 `from monitor.sender_matcher import SenderMatcher` 仍可使用
# ============================================
class SenderMatcher:
    """[已废弃] 仅匹配发件人的旧接口，内部委托给 RuleMatcher。"""

    @staticmethod
    def match(sender: str, rules: list) -> dict | None:
        """
        [已废弃] 仅按 sender_pattern 匹配。
        新代码请使用 RuleMatcher.match(sender, subject, body, rules)。
        """
        return RuleMatcher.match(sender, "", "", rules)
