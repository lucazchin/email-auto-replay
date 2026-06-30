"""
浏览器上下文管理：管理 Playwright 生命周期，复用 browser 实例。
"""
from pathlib import Path
from loguru import logger
from playwright.sync_api import sync_playwright, Browser, BrowserContext
from config.loader import Config
from browser.stealth import apply_stealth


class BrowserManager:
    """管理 Playwright 生命周期，复用 browser 实例。"""

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None

    def start(self):
        """启动 Playwright 和浏览器。"""
        cfg = Config().get("browser")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=cfg.get("headless", False),
            slow_mo=cfg.get("slow_mo", 0),
        )
        logger.info("浏览器启动完成")

    def new_context(self, state_file: str = None) -> BrowserContext:
        """创建新的浏览器上下文，加载已保存的登录状态。"""
        cfg = Config().get("browser")
        kwargs = {}
        viewport = cfg.get("viewport")
        if viewport:
            kwargs["viewport"] = viewport
        if cfg.get("user_agent"):
            kwargs["user_agent"] = cfg["user_agent"]

        state_path = Path(state_file) if state_file else None
        if state_path and state_path.exists():
            kwargs["storage_state"] = str(state_path)
            logger.info(f"加载登录状态: {state_path}")
        else:
            logger.warning(f"登录状态文件不存在: {state_path}（首次登录时正常）")

        context = self._browser.new_context(**kwargs)
        apply_stealth(context)
        return context

    def save_state(self, context: BrowserContext, state_file: str):
        """保存当前上下文的登录状态。"""
        state_path = Path(state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=state_file)
        logger.info(f"登录状态已保存: {state_file}")

    def stop(self):
        """关闭浏览器和 Playwright。使用 try 避免阻塞退出。"""
        try:
            if self._browser:
                self._browser.close()
        except Exception as e:
            logger.debug(f"关闭 browser 异常（可忽略）: {e}")
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.debug(f"停止 playwright 异常（可忽略）: {e}")
        logger.info("浏览器已关闭")
