"""
配置加载与校验模块（EWS 版）。
支持 config.yaml + .env 环境变量覆盖。
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """单例配置管理器。"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        # 加载 .env 文件
        project_root = Path(__file__).parent.parent
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        # 加载 config.yaml
        config_path = project_root / "config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {config_path}\n"
                f"请复制 config.yaml.example 为 config.yaml 并填写配置"
            )

        with open(config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f)

        # 环境变量覆盖敏感字段
        if os.getenv("DB_PASSWORD"):
            self._data.setdefault("database", {})["password"] = os.getenv("DB_PASSWORD")
        if os.getenv("AI_API_KEY"):
            self._data.setdefault("ai", {})["api_key"] = os.getenv("AI_API_KEY")
        # EWS 凭据
        ews_cfg = self._data.get("ews", {}) or {}
        if os.getenv("EWS_EMAIL"):
            ews_cfg["email"] = os.getenv("EWS_EMAIL")
        if os.getenv("EWS_PASSWORD"):
            ews_cfg["password"] = os.getenv("EWS_PASSWORD")
        if os.getenv("EWS_SERVER"):
            ews_cfg["server"] = os.getenv("EWS_SERVER")
        if ews_cfg:
            self._data["ews"] = ews_cfg

        self._validate()

    def _validate(self):
        """启动时校验关键配置项。"""
        required_paths = [
            ("database", "host"),
            ("database", "database"),
            ("ai", "provider"),
            ("ews", "email"),
            ("ews", "server"),
        ]
        for path in required_paths:
            val = self._data
            for key in path:
                if not isinstance(val, dict) or key not in val:
                    raise ValueError(f"配置缺失: {'.'.join(path)}")
                val = val[key]
            if val is None or val == "":
                raise ValueError(f"配置值为空: {'.'.join(path)}")

    def get(self, *keys, default=None):
        """
        按层级获取配置值，支持默认值。

        支持两种调用风格：
            cfg.get("ews", "email")                    # 多级 key
            cfg.get("ews", "password", default="")      # 关键字默认值
            cfg.get("ewa", "max_emails", 20)            # 位置默认值
        """
        if keys and not isinstance(keys[-1], str):
            if default is None:
                default = keys[-1]
            keys = keys[:-1]

        val = self._data
        for k in keys:
            if not isinstance(val, dict) or k not in val:
                return default
            val = val[k]
        return val

    def reload(self):
        """重新加载配置（热更新场景）。"""
        self._load()
