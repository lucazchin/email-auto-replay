"""
AI 适配器抽象基类：定义统一接口，内置重试逻辑。
"""
import time
from abc import ABC, abstractmethod
from loguru import logger


class AIAdapter(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.max_tokens = config.get("max_tokens", 1000)
        self.temperature = config.get("temperature", 0.7)
        self.timeout = config.get("timeout", 30)
        self.retry_times = config.get("retry_times", 3)
        self.retry_interval = config.get("retry_interval", 5)

    @abstractmethod
    def _call_api(self, prompt: str, system_prompt: str = None) -> str:
        """子类实现：调用具体 AI API。
        :param prompt: 用户提示词
        :param system_prompt: 可选的自定义 system prompt，为 None 时使用默认值
        """
        pass

    def generate(self, prompt_template: str, email_content: str,
                 system_prompt: str = None) -> str:
        """
        生成回复内容。包含重试逻辑。
        :param prompt_template: 包含 {email_content} 占位符的提示词模板
        :param email_content: 清洗后的邮件正文
        :param system_prompt: 可选的自定义 system prompt，为 None 时使用默认值
        :return: AI 生成的回复文本
        """
        prompt = prompt_template.replace("{email_content}", email_content)

        # 安全检查：确保 prompt 不超过模型上下文限制
        max_input_chars = 12000
        if len(prompt) > max_input_chars:
            logger.warning(f"Prompt 过长 ({len(prompt)} 字符)，截断处理")
            prompt = prompt[:max_input_chars]

        for attempt in range(1, self.retry_times + 1):
            try:
                logger.info(f"调用 AI 生成回复 (第 {attempt} 次)")
                result = self._call_api(prompt, system_prompt)
                if result and result.strip():
                    return result.strip()
                logger.warning(f"AI 返回空内容 (第 {attempt} 次)")
            except Exception as e:
                logger.error(
                    f"AI 调用失败 (第 {attempt}/{self.retry_times} 次): {e}"
                )
                if attempt < self.retry_times:
                    time.sleep(self.retry_interval)

        raise RuntimeError(f"AI 调用失败，已重试 {self.retry_times} 次")
