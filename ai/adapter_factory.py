"""
AI 适配器工厂：根据配置创建对应的适配器实例。
"""
from ai.base import AIAdapter
from ai.openai_adapter import OpenAIAdapter
from ai.ollama_adapter import OllamaAdapter
from loguru import logger


def get_ai_adapter(config) -> AIAdapter:
    """
    根据配置中的 provider 字段创建 AI 适配器。
    :param config: Config 单例
    :return: AIAdapter 实例
    """
    ai_cfg = config.get("ai")
    if not ai_cfg:
        raise ValueError("配置中缺少 ai 段")

    provider = ai_cfg["provider"]

    if provider in ("deepseek", "openai", "qwen"):
        return OpenAIAdapter(ai_cfg)
    elif provider == "ollama":
        return OllamaAdapter(ai_cfg)
    else:
        raise ValueError(f"不支持的 AI provider: {provider}")
