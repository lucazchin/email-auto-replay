"""
Config.get() 单元测试。
重点验证位置默认值和关键字默认值的行为，防止回归。
"""
import pytest
import os
from unittest.mock import patch
from pathlib import Path


# 用独立 fixture 加载一份测试配置，避免依赖真实 config.yaml
TEST_CONFIG = {
    "owa": {
        "url": "https://mail.example.com/owa/",
        "state_file": "state/test_state.json",
        "credentials": {
            "enabled": True,
            "username": "testuser",
            "password": "testpass",
            "domain": "",
        },
    },
    "database": {
        "host": "127.0.0.1",
        "database": "test_db",
    },
    "ai": {
        "provider": "deepseek",
    },
    "scheduler": {
        "interval_minutes": 2,
    },
    "logging": {
        "level": "DEBUG",
        "dir": "logs",
    },
}


@pytest.fixture
def config_instance():
    """构造一个加载了 TEST_CONFIG 的 Config 实例。"""
    from config.loader import Config
    # 重置单例
    Config._instance = None
    with patch.object(Config, "_load", lambda self: setattr(self, "_data", TEST_CONFIG.copy())):
        cfg = Config()
    yield cfg
    Config._instance = None


class TestGetBasic:
    """测试基础取值。"""

    def test_get_single_key(self, config_instance):
        assert config_instance.get("owa") == TEST_CONFIG["owa"]

    def test_get_nested_key(self, config_instance):
        assert config_instance.get("owa", "url") == "https://mail.example.com/owa/"

    def test_get_deeply_nested(self, config_instance):
        assert config_instance.get("owa", "credentials", "username") == "testuser"

    def test_get_nonexistent_key_returns_none(self, config_instance):
        assert config_instance.get("nonexistent") is None

    def test_get_nonexistent_nested_returns_none(self, config_instance):
        assert config_instance.get("owa", "nonexistent") is None


class TestGetWithKeywordDefault:
    """测试关键字默认值。"""

    def test_get_with_keyword_default(self, config_instance):
        assert config_instance.get("owa", "missing", default="fallback") == "fallback"

    def test_get_with_keyword_default_dict(self, config_instance):
        # 关键字默认值为 dict
        result = config_instance.get("owa", "missing", default={"a": 1})
        assert result == {"a": 1}

    def test_get_existing_ignores_default(self, config_instance):
        assert config_instance.get("owa", "url", default="fallback") == "https://mail.example.com/owa/"


class TestGetWithPositionalDefault:
    """测试位置默认值（dict.get 习惯）— 这是回归测试的核心。"""

    def test_get_with_positional_dict_default(self, config_instance):
        # 这是触发原 bug 的调用方式：cfg.get("owa", "credentials", {})
        # 修复后应正确返回 {}（因为 "missing" 不存在）或实际值
        result = config_instance.get("owa", "missing_key", {})
        assert result == {}

    def test_get_with_positional_dict_default_existing_key(self, config_instance):
        # key 存在时应返回实际值，不受位置默认值影响
        result = config_instance.get("owa", "credentials", {})
        assert result == TEST_CONFIG["owa"]["credentials"]

    def test_get_with_positional_string_default(self, config_instance):
        # 字符串默认值仍被视为 key（向后兼容）
        # 注意：cfg.get("owa", "url", "fallback") 中 "fallback" 被当成第三个 key
        # 这是不期望的行为，但为了不破坏现有代码，字符串最后位会被当 key
        # 实际：owa 段下找 "url" → "fallback" 两个 key，fallback 不存在返回 None
        result = config_instance.get("owa", "url", "fallback")
        # "fallback" 是字符串，按当前实现会被当成 key
        # owa.url 存在，但 owa.url.fallback 不存在（url 是字符串不是 dict）
        assert result is None

    def test_get_with_positional_int_default(self, config_instance):
        result = config_instance.get("owa", "missing", 10)
        assert result == 10

    def test_get_with_positional_list_default(self, config_instance):
        result = config_instance.get("owa", "missing", [])
        assert result == []

    def test_get_with_positional_bool_default(self, config_instance):
        result = config_instance.get("owa", "missing", False)
        assert result is False

    def test_get_with_positional_none_default(self, config_instance):
        # None 不是字符串，会被当默认值（等价于不传）
        result = config_instance.get("owa", "missing", None)
        assert result is None


class TestGetOriginalBugScenario:
    """复现原始报错场景，确保不再 TypeError。"""

    def test_no_type_error_on_dict_positional_default(self, config_instance):
        """原始 bug: cfg.get("owa", "credentials", {}) 抛 TypeError"""
        # 修复前：{} 被当成 key，{} not in val 触发 TypeError
        # 修复后：{} 被识别为位置默认值
        try:
            result = config_instance.get("owa", "credentials", {})
            assert result == TEST_CONFIG["owa"]["credentials"]
        except TypeError as e:
            pytest.fail(f"不应再抛出 TypeError: {e}")

    def test_no_type_error_on_missing_key_with_dict_default(self, config_instance):
        """缺失 key 时也不应报错"""
        try:
            result = config_instance.get("owa", "nonexistent", {})
            assert result == {}
        except TypeError as e:
            pytest.fail(f"不应再抛出 TypeError: {e}")

    def test_main_py_usage_pattern(self, config_instance):
        """模拟 main.py:58 的实际调用模式"""
        creds_cfg = config_instance.get("owa", "credentials", {}) or {}
        assert creds_cfg == TEST_CONFIG["owa"]["credentials"]
        assert creds_cfg.get("username") == "testuser"

    def test_main_py_usage_pattern_missing(self, config_instance):
        """模拟 credentials 段缺失时的调用模式"""
        creds_cfg = config_instance.get("owa", "missing_creds", {}) or {}
        assert creds_cfg == {}
