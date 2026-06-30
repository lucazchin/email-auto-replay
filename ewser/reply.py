"""
EWS 回复发送器。
通过 exchangelib 直接调用 Exchange API 发送邮件回复。
"""
from loguru import logger
from exchangelib import Message


class EWSReplySender:
    """通过 EWS 发送邮件回复。"""

    @staticmethod
    def send(message: Message, reply_content: str, reply_all: bool = True) -> bool:
        """
        回复邮件。
        :param message: exchangelib Message 对象
        :param reply_content: 回复内容
        :param reply_all: 是否回复全部收件人（默认 True）
        """
        try:
            if reply_all:
                message.reply_all(
                    subject=f"Re: {message.subject or ''}",
                    body=reply_content,
                )
            else:
                message.reply(
                    subject=f"Re: {message.subject or ''}",
                    body=reply_content,
                )
            # exchangelib 的 reply/reply_all 已经直接发送，返回 bool
            logger.info(f"回复发送成功: {message.subject}")
            return True
        except Exception as e:
            logger.error(f"回复发送失败: {e}")
            raise
