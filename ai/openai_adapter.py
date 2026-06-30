"""
OpenAI 兼容适配器：适用于 DeepSeek / OpenAI / Qwen 等。
"""
from openai import OpenAI
from ai.base import AIAdapter
from loguru import logger


class OpenAIAdapter(AIAdapter):
    """适用于 DeepSeek / OpenAI / Qwen 等 OpenAI 兼容接口。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.client = OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
            timeout=config.get("timeout", 30),
        )
        self.model = config["model"]
        logger.info(
            f"AI 适配器初始化: provider={config['provider']}, model={self.model}"
        )

    def _call_api(self, prompt: str, system_prompt: str = None) -> str:
        # 使用规则自定义的 system_prompt，否则使用默认值
        if system_prompt is None:
            system_prompt = (
                "你是一个专业的邮件回复助手。请根据收到的邮件内容，"
                "生成一封礼貌、专业、简洁的回复邮件。"
                "只输出回复正文，不要包含主题行。"
            )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return response.choices[0].message.content
