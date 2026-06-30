"""
发件人规则匹配：支持正则表达式匹配发件人地址。
"""
import re
from loguru import logger


class SenderMatcher:
    @staticmethod
    def match(sender: str, rules: list) -> dict | None:
        """
        将发件人地址与规则列表匹配。
        支持正则匹配，返回第一个命中的规则。
        :param sender: 发件人地址
        :param rules: 规则列表（来自 DB）
        :return: 匹配的规则 dict，无匹配返回 None
        """
        if not sender:
            return None

        for rule in rules:
            pattern = rule["sender_pattern"]
            try:
                if re.search(pattern, sender, re.IGNORECASE):
                    logger.info(f"发件人匹配规则: {sender} -> rule#{rule['id']}")
                    return rule
            except re.error as e:
                logger.error(f"规则#{rule['id']} 正则表达式无效: {pattern}, 错误: {e}")
                continue

        return None
