"""
登录态校验：检测当前页面是否处于已登录状态。
针对 Exchange OWA 登录页特征。

改进：
- 多策略组合判断（URL + 元素 + 邮件列表）
- 宽松模式：URL 不在登录页 + 页面有大量内容 → 视为已登录
- 失败时自动截图便于排查
"""
from loguru import logger
from browser.selectors import OWASelectors
from browser.selector_helper import try_selectors, try_query_all


class AuthChecker:
    """检测登录状态是否有效。"""

    # OWA 登录页 URL 特征（出现这些 = 未登录）
    LOGIN_URL_PATTERNS = [
        "owa/auth",
        "owa/logon",
        "login.microsoftonline.com",
        "account.live.com",
        "/logon.",
        "/logonp.",
    ]

    # 登录页特征元素（出现这些 = 未登录）
    LOGIN_PAGE_INDICATORS = [
        'input[name="username"]',
        'input[name="password"]',
        'input[type="password"]',
        'form[id*="logon" i]',
        'form[action*="logon" i]',
        'div[id*="logon" i]',
    ]

    # 已登录特征元素（OWA 多版本兼容）
    LOGGED_IN_INDICATORS = [
        # OWA 主壳
        'div[class*="OwaShell"]',
        'div[class*="owaShell"]',
        # 导航栏 / 应用栏
        'div[role="navigation"]',
        'div[class*="AppBar"]',
        'div[aria-label*="导航"]',
        # 邮件列表（最强特征）
        'div[role="listbox"]',
        'div[aria-label*="邮件"]',
        'div[aria-label*="Message"]',
        # 文件夹树
        'div[role="tree"]',
        'div[role="treeitem"][aria-label*="收件箱"]',
        'div[role="treeitem"][aria-label*="Inbox"]',
        # 顶部工具栏
        'div[class*="CommandBar"]',
        'div[class*="ToolBar"]',
    ]

    @staticmethod
    def is_logged_in(page, screenshot_on_fail: bool = True) -> bool:
        """
        判断当前页面是否处于已登录状态。
        多策略组合：
        1. URL 是登录页 → 未登录
        2. 页面有登录表单元素 → 未登录
        3. 页面有已登录特征元素 → 已登录
        4. 宽松兜底：URL 不在登录页 + 页面 HTML 较大 → 已登录
        """
        try:
            current_url = page.url or ""
        except Exception:
            current_url = ""

        logger.debug(f"AuthChecker 检查登录态, URL: {current_url}")

        # 策略 1：URL 是登录页 → 未登录
        for pattern in AuthChecker.LOGIN_URL_PATTERNS:
            if pattern.lower() in current_url.lower():
                logger.warning(f"检测到登录页 URL 特征: {current_url}")
                if screenshot_on_fail:
                    AuthChecker._screenshot(page, "login_url_detected")
                return False

        # 策略 2：页面有登录表单元素 → 未登录
        for sel in AuthChecker.LOGIN_PAGE_INDICATORS:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    logger.warning(f"检测到登录表单元素: {sel}")
                    if screenshot_on_fail:
                        AuthChecker._screenshot(page, "login_form_detected")
                    return False
            except Exception:
                continue

        # 策略 3：页面有已登录特征元素 → 已登录
        for sel in AuthChecker.LOGGED_IN_INDICATORS:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    logger.info(f"检测到已登录特征元素: {sel}")
                    return True
            except Exception:
                continue

        # 策略 4：宽松兜底
        # URL 包含 /owa/ 且不在登录页，且页面内容较多 → 视为已登录
        if AuthChecker._soft_check(page, current_url):
            logger.info("宽松检测判定为已登录")
            return True

        logger.warning("未找到登录后特征元素，登录态可能已过期")
        if screenshot_on_fail:
            AuthChecker._screenshot(page, "no_login_indicator")
        return False

    @staticmethod
    def _soft_check(page, url: str) -> bool:
        """
        宽松检测：当严格选择器都没命中时的兜底判断。
        条件：
        1. URL 含 /owa/ 且不含 logon/auth
        2. 页面 body 有较多子元素（不是空白登录页）
        """
        url_lower = url.lower()
        if "/owa/" not in url_lower and "mail" not in url_lower:
            return False
        if "logon" in url_lower or "auth" in url_lower:
            return False

        # 检查页面是否有足够内容（登录后页面通常有大量 DOM）
        try:
            body_children_count = page.evaluate(
                "() => document.body ? document.body.querySelectorAll('*').length : 0"
            )
            # OWA 登录后页面通常有 1000+ 元素，登录页只有几十个
            if body_children_count > 200:
                logger.debug(f"宽松检测: 页面有 {body_children_count} 个元素，判定为已登录")
                return True
        except Exception:
            pass

        return False

    @staticmethod
    def _screenshot(page, tag: str):
        """失败时自动截图（用于调试）。"""
        try:
            from browser.screenshot import ScreenshotMonitor
            ScreenshotMonitor().capture(page, tag)
        except Exception as e:
            logger.debug(f"自动截图失败: {e}")
