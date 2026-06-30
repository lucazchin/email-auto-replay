"""
自动登录模块：自动填写账号密码登录 OWA。
支持：
- 单页登录（用户名 + 密码同一页）
- 分步登录（先用户名 → 再密码，常见于 Microsoft 联合登录）
- "保持登录"提示自动确认
- MFA 检测 → 人工兜底
- 登录失败检测 → 重试
- 登录后自动关闭弹窗（存储警告等）
"""
import time
from enum import Enum
from typing import Optional
from loguru import logger
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from browser.selectors import OWASelectors as S
from browser.selector_helper import try_selectors, try_click
from browser.auth_checker import AuthChecker
from browser.popup_handler import dismiss_all_popups


class LoginResult(str, Enum):
    """登录结果枚举。"""
    SUCCESS = "success"                 # 登录成功
    MFA_REQUIRED = "mfa_required"       # 需要二次验证（已人工处理完成也算成功）
    FAILED = "failed"                   # 登录失败（凭据错误等）
    TIMEOUT = "timeout"                 # 登录超时
    CREDENTIAL_MISSING = "cred_missing" # 未配置凭据


class AutoLogin:
    """
    自动登录 OWA 邮箱。

    使用方式：
        auto_login = AutoLogin(page, credentials_config)
        result = auto_login.login(owa_url)
        if result == LoginResult.SUCCESS:
            # 保存 state
    """

    def __init__(self, page: Page, creds_cfg: dict):
        """
        :param page: Playwright Page 实例
        :param creds_cfg: config.yaml 中 owa.credentials 段
        """
        self.page = page
        self.username = creds_cfg.get("username", "")
        self.password = creds_cfg.get("password", "")
        self.domain = creds_cfg.get("domain", "")
        self.login_timeout = creds_cfg.get("login_timeout", 60)
        self.mfa_fallback = creds_cfg.get("mfa_fallback", True)
        self.retry_times = creds_cfg.get("retry_times", 2)
        self.retry_interval = creds_cfg.get("retry_interval", 5)
        self.stay_signed_in = creds_cfg.get("stay_signed_in", True)

    @staticmethod
    def has_credentials(creds_cfg: dict) -> bool:
        """检查是否配置了完整凭据。"""
        return bool(creds_cfg.get("username") and creds_cfg.get("password"))

    def login(self, owa_url: str) -> LoginResult:
        """
        执行完整登录流程。
        :param owa_url: OWA 邮箱首页 URL
        :return: LoginResult
        """
        if not (self.username and self.password):
            logger.error("未配置 OWA 账号或密码，无法自动登录")
            return LoginResult.CREDENTIAL_MISSING

        # 拼接完整用户名（domain\username）
        full_username = self._build_username()
        logger.info(f"开始自动登录: {owa_url} (用户: {self._mask_username(full_username)})")

        for attempt in range(1, self.retry_times + 2):  # retry_times + 首次
            logger.info(f"登录尝试 {attempt}/{self.retry_times + 1}")
            try:
                result = self._attempt_login(owa_url, full_username)
                if result == LoginResult.SUCCESS:
                    logger.info("自动登录成功")
                    return result
                if result == LoginResult.MFA_REQUIRED:
                    # MFA 已人工处理或回退完成，直接返回
                    return result
                # FAILED / TIMEOUT → 重试
                if attempt <= self.retry_times:
                    logger.warning(f"登录失败，{self.retry_interval} 秒后重试")
                    time.sleep(self.retry_interval)
            except Exception as e:
                logger.error(f"登录异常: {e}")
                if attempt <= self.retry_times:
                    time.sleep(self.retry_interval)

        logger.error(f"自动登录失败，已尝试 {self.retry_times + 1} 次")
        return LoginResult.FAILED

    def _attempt_login(self, owa_url: str, full_username: str) -> LoginResult:
        """单次登录尝试。"""
        deadline = time.time() + self.login_timeout

        # 1. 打开登录页
        self.page.goto(owa_url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(1500)

        # 已经登录则直接返回
        if AuthChecker.is_logged_in(self.page):
            logger.info("当前已处于登录状态，无需重复登录")
            return LoginResult.SUCCESS

        # 2. 输入用户名
        if not self._fill_username(full_username, deadline):
            return LoginResult.TIMEOUT

        # 3. 输入密码
        if not self._fill_password(deadline):
            return LoginResult.TIMEOUT

        # 4. 处理"保持登录"提示 / 等待跳转 / MFA 检测
        return self._wait_for_login_complete(deadline)

    def _fill_username(self, username: str, deadline: float) -> bool:
        """填入用户名并提交（可能是 Enter 或"下一步"按钮）。"""
        logger.info("填写用户名")
        el = try_selectors(self.page, S.USERNAME_INPUT, timeout=10000)
        if not el:
            logger.error("未找到用户名输入框")
            return False

        el.click()
        el.fill("")  # 清空
        el.type(username, delay=30)  # 逐字输入，模拟人工
        self.page.wait_for_timeout(500)

        # 尝试点击"下一步"或回车
        clicked = try_click(self.page, S.NEXT_BUTTON, timeout=2000)
        if not clicked:
            self.page.keyboard.press("Enter")

        self.page.wait_for_timeout(1500)
        return True

    def _fill_password(self, deadline: float) -> bool:
        """填入密码并提交。"""
        logger.info("填写密码")
        el = try_selectors(self.page, S.PASSWORD_INPUT, timeout=15000)
        if not el:
            logger.error("未找到密码输入框")
            return False

        el.click()
        el.fill("")
        el.type(self.password, delay=30)
        self.page.wait_for_timeout(500)

        # 点击"登录"/"提交"，或回车
        clicked = try_click(self.page, S.SIGN_IN_BUTTON, timeout=2000)
        if not clicked:
            self.page.keyboard.press("Enter")

        self.page.wait_for_timeout(2000)
        return True

    def _wait_for_login_complete(self, deadline: float) -> LoginResult:
        """
        提交后等待登录完成。可能出现的场景：
        1. "保持登录"提示 → 点"是"
        2. MFA 二次验证 → 等待人工处理（或回退）
        3. 登录错误 → 返回 FAILED
        4. 登录成功跳转到邮箱主页
        """
        logger.info("等待登录完成...")
        mfa_handled = False

        while time.time() < deadline:
            # 优先检查登录错误
            if self._has_login_error():
                logger.error("检测到登录错误提示，凭据可能不正确")
                return LoginResult.FAILED

            # 检查是否已登录成功
            if AuthChecker.is_logged_in(self.page):
                logger.info("登录成功")
                # 登录后自动关闭弹窗（存储警告等）
                dismiss_all_popups(self.page)
                return LoginResult.SUCCESS

            # 处理"保持登录"提示
            if self.stay_signed_in:
                if try_click(self.page, S.STAY_SIGNED_IN_YES, timeout=500):
                    logger.info("已点击「保持登录」")
                    self.page.wait_for_timeout(2000)
                    continue

            # 检测 MFA
            if not mfa_handled and self._has_mfa():
                logger.warning("=" * 50)
                logger.warning("检测到二次验证 (MFA)！")
                logger.warning("请在弹出的浏览器中完成 MFA 验证")
                logger.warning(f"系统将等待最多 {self.login_timeout} 秒")
                logger.warning("=" * 50)
                if not self.mfa_fallback:
                    logger.error("未启用 MFA 人工兜底，登录失败")
                    return LoginResult.FAILED
                mfa_handled = True
                # 继续循环，等待 MFA 完成

            self.page.wait_for_timeout(1500)

        logger.error("登录超时")
        return LoginResult.TIMEOUT

    def _has_mfa(self) -> bool:
        """检测页面是否进入 MFA 流程。"""
        for sel in S.MFA_INDICATORS:
            try:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    logger.debug(f"MFA 指示器命中: {sel}")
                    return True
            except Exception:
                continue
        return False

    def _has_login_error(self) -> bool:
        """检测页面是否有登录错误提示。"""
        for sel in S.LOGIN_ERROR_INDICATORS:
            try:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    text = el.inner_text().strip()
                    if text:
                        logger.debug(f"登录错误指示器命中: {sel}, 文本: {text[:80]}")
                        return True
            except Exception:
                continue
        return False

    def _build_username(self) -> str:
        r"""拼接完整用户名（domain\username 或纯 username）。"""
        if self.domain:
            return f"{self.domain}\\{self.username}"
        return self.username

    @staticmethod
    def _mask_username(username: str) -> str:
        """用户名脱敏（日志显示用）。"""
        if not username:
            return ""
        if "\\" in username:
            domain, user = username.split("\\", 1)
            return f"{domain}\\{user[:2]}***"
        if "@" in username:
            name, domain = username.split("@", 1)
            return f"{name[:2]}***@{domain}"
        return username[:2] + "***"
