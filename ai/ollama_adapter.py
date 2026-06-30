"""
Ollama 本地模型适配器。
"""
import requests
from ai.base import AIAdapter
from loguru import logger


class OllamaAdapter(AIAdapter):
    """Ollama 本地模型适配器。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config["model"]
        logger.info(f"Ollama 适配器初始化: {self.base_url}, model={self.model}")

    def _call_api(self, prompt: str, system_prompt: str = None) -> str:
        # Ollama 无 system/user 角色区分，将 system_prompt 拼接到前面
        if system_prompt:
            prompt = f"{system_prompt}\n\n{prompt}"
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
