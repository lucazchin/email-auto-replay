"""
自定义异常体系。
"""


class EmailAutoReplyError(Exception):
    """基础异常。"""
    pass


class LoginExpiredError(EmailAutoReplyError):
    """登录态过期。"""
    pass


class SelectorNotFoundError(EmailAutoReplyError):
    """选择器未找到（DOM 结构可能已变化）。"""
    def __init__(self, selector_desc: str):
        super().__init__(f"选择器未找到: {selector_desc}")
        self.selector_desc = selector_desc


class AIGenerationError(EmailAutoReplyError):
    """AI 回复生成失败。"""
    pass


class SendReplyError(EmailAutoReplyError):
    """回复发送失败。"""
    pass


class DatabaseError(EmailAutoReplyError):
    """数据库操作失败。"""
    pass
