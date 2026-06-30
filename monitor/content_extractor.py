"""
邮件正文清洗：
1. HTML 转纯文本
2. 去除引用回复
3. 去除签名
4. 压缩多余空白
"""
import re
import html2text
from loguru import logger


class ContentExtractor:
    def __init__(self):
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = True
        self.h2t.body_width = 0

    def clean(self, raw_body: str) -> str:
        """
        清洗邮件正文。
        :param raw_body: 原始正文（可能含 HTML）
        :return: 清洗后的纯文本
        """
        if not raw_body:
            return ""

        # 1. HTML 转纯文本
        if "<" in raw_body and ">" in raw_body:
            text = self.h2t.handle(raw_body)
        else:
            text = raw_body

        # 2. 去除引用回复
        text = self._strip_quoted_reply(text)

        # 3. 去除签名
        text = self._strip_signature(text)

        # 4. 压缩空白
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        logger.debug(f"正文清洗完成: {len(raw_body)} -> {len(text)} 字符")
        return text

    def _strip_quoted_reply(self, text: str) -> str:
        """去除引用的回复内容。"""
        patterns = [
            r"On .+ wrote:",
            r"在 .+ 写道：",
            r"发件人:.+",
            r"From:.+",
            r"-----原始邮件-----",
            r"-----Original Message-----",
            r"_________________",
            r"From: .+\nSent: .+\nTo: .+\nSubject: .+",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                text = text[: match.start()]
        return text

    def _strip_signature(self, text: str) -> str:
        """去除邮件签名。"""
        # "--" 签名分隔符
        sig_match = re.search(r"^--\s*$", text, re.MULTILINE)
        if sig_match:
            text = text[: sig_match.start()]

        # 常见签名开头
        sig_patterns = [
            r"(此致|敬礼|Best regards|Regards|Sincerely|Thanks)\s*$",
        ]
        for pattern in sig_patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                text = text[: match.start()]

        return text
