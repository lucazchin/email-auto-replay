"""
AutoLogin 单元测试。
测试可单测的逻辑部分：用户名拼接、脱敏、凭据检测、结果枚举。
Playwright 依赖部分通过 mock 测试。
"""
import pytest
from unittest.mock import MagicMock, patch
from browser.auto_login import AutoLogin, LoginResult


class TestAutoLoginConfig:
    """测试配置相关逻辑。"""

    def test_has_credentials_both_present(self):
        cfg = {"username": "alice", "password": "secret"}
        assert AutoLogin.has_credentials(cfg) is True

    def test_has_credentials_missing_username(self):
        cfg = {"username": "", "password": "secret"}
        assert AutoLogin.has_credentials(cfg) is False

    def test_has_credentials_missing_password(self):
        cfg = {"username": "alice", "password": ""}
        assert AutoLogin.has_credentials(cfg) is False

    def test_has_credentials_none_values(self):
        cfg = {"username": None, "password": None}
        assert AutoLogin.has_credentials(cfg) is False

    def test_has_credentials_missing_keys(self):
        cfg = {}
        assert AutoLogin.has_credentials(cfg) is False


class TestUsernameBuilding:
    """测试用户名拼接逻辑。"""

    def test_plain_username(self):
        al = AutoLogin(MagicMock(), {"username": "alice", "password": "x"})
        assert al._build_username() == "alice"

    def test_domain_username(self):
        al = AutoLogin(MagicMock(), {
            "username": "alice",
            "password": "x",
            "domain": "CORP",
        })
        assert al._build_username() == "CORP\\alice"

    def test_email_username(self):
        al = AutoLogin(MagicMock(), {
            "username": "alice@hengtiansoft.com",
            "password": "x",
        })
        assert al._build_username() == "alice@hengtiansoft.com"


class TestUsernameMasking:
    """测试用户名脱敏（日志安全）。"""

    def test_mask_plain_username(self):
        assert AutoLogin._mask_username("alice") == "al***"

    def test_mask_domain_username(self):
        assert AutoLogin._mask_username("CORP\\alice") == "CORP\\al***"

    def test_mask_email_username(self):
        masked = AutoLogin._mask_username("alice@hengtiansoft.com")
        assert masked == "al***@hengtiansoft.com"

    def test_mask_empty(self):
        assert AutoLogin._mask_username("") == ""

    def test_mask_short_username(self):
        # 只有一个字符也能脱敏
        assert AutoLogin._mask_username("a") == "a***"


class TestLoginResultEnum:
    """测试登录结果枚举。"""

    def test_result_values(self):
        assert LoginResult.SUCCESS == "success"
        assert LoginResult.MFA_REQUIRED == "mfa_required"
        assert LoginResult.FAILED == "failed"
        assert LoginResult.TIMEOUT == "timeout"
        assert LoginResult.CREDENTIAL_MISSING == "cred_missing"

    def test_result_is_string(self):
        # LoginResult 继承 str，方便序列化
        assert isinstance(LoginResult.SUCCESS, str)


class TestLoginMissingCredentials:
    """测试凭据缺失时的行为。"""

    def test_login_returns_credential_missing(self):
        page = MagicMock()
        al = AutoLogin(page, {"username": "", "password": ""})
        result = al.login("https://example.com/owa")
        assert result == LoginResult.CREDENTIAL_MISSING

    def test_login_with_only_username(self):
        page = MagicMock()
        al = AutoLogin(page, {"username": "alice", "password": ""})
        result = al.login("https://example.com/owa")
        assert result == LoginResult.CREDENTIAL_MISSING

    def test_login_with_only_password(self):
        page = MagicMock()
        al = AutoLogin(page, {"username": "", "password": "secret"})
        result = al.login("https://example.com/owa")
        assert result == LoginResult.CREDENTIAL_MISSING


class TestMfaAndErrorDetection:
    """测试 MFA 和错误检测（通过 mock page）。"""

    def test_has_mfa_no_elements(self):
        page = MagicMock()
        page.query_selector.return_value = None
        al = AutoLogin(page, {"username": "u", "password": "p"})
        assert al._has_mfa() is False

    def test_has_mfa_with_visible_element(self):
        page = MagicMock()
        el = MagicMock()
        el.is_visible.return_value = True
        page.query_selector.return_value = el
        al = AutoLogin(page, {"username": "u", "password": "p"})
        # 第一个 MFA 选择器命中即返回 True
        assert al._has_mfa() is True

    def test_has_mfa_with_hidden_element(self):
        page = MagicMock()
        el = MagicMock()
        el.is_visible.return_value = False
        page.query_selector.return_value = el
        al = AutoLogin(page, {"username": "u", "password": "p"})
        assert al._has_mfa() is False

    def test_has_login_error_no_elements(self):
        page = MagicMock()
        page.query_selector.return_value = None
        al = AutoLogin(page, {"username": "u", "password": "p"})
        assert al._has_login_error() is False

    def test_has_login_error_with_visible_text(self):
        page = MagicMock()
        el = MagicMock()
        el.is_visible.return_value = True
        el.inner_text.return_value = "密码不正确"
        page.query_selector.return_value = el
        al = AutoLogin(page, {"username": "u", "password": "p"})
        assert al._has_login_error() is True

    def test_has_login_error_with_empty_text(self):
        """错误元素可见但文本为空，应判为无错误。"""
        page = MagicMock()
        el = MagicMock()
        el.is_visible.return_value = True
        el.inner_text.return_value = "   "
        page.query_selector.return_value = el
        al = AutoLogin(page, {"username": "u", "password": "p"})
        assert al._has_login_error() is False


class TestDefaults:
    """测试默认值加载。"""

    def test_default_values(self):
        al = AutoLogin(MagicMock(), {"username": "u", "password": "p"})
        assert al.login_timeout == 60
        assert al.mfa_fallback is True
        assert al.retry_times == 2
        assert al.retry_interval == 5
        assert al.stay_signed_in is True
        assert al.domain == ""

    def test_custom_values(self):
        cfg = {
            "username": "u",
            "password": "p",
            "login_timeout": 120,
            "mfa_fallback": False,
            "retry_times": 5,
            "retry_interval": 10,
            "stay_signed_in": False,
        }
        al = AutoLogin(MagicMock(), cfg)
        assert al.login_timeout == 120
        assert al.mfa_fallback is False
        assert al.retry_times == 5
        assert al.retry_interval == 10
        assert al.stay_signed_in is False
