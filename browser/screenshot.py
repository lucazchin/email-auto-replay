"""
截图监控模块：在关键节点自动截图，便于调试 OWA 页面状态。
截图保存到 logs/screenshots/ 目录，按时间戳命名。
"""
import time
from pathlib import Path
from loguru import logger
from playwright.sync_api import Page
from config.loader import Config


class ScreenshotMonitor:
    """关键节点截图监控。"""

    def __init__(self):
        cfg = Config().get("screenshot", default={}) or {}
        self.enabled = cfg.get("enabled", True)
        self.dir = Path(cfg.get("dir", "logs/screenshots"))
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def capture(self, page: Page, tag: str = "") -> str:
        """
        截取当前页面截图。
        :param page: Playwright Page
        :param tag: 截图标签，用于标识截图场景
        :return: 截图文件路径，禁用时返回空字符串
        """
        if not self.enabled:
            return ""

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            tag_part = f"_{tag}" if tag else ""
            filename = f"{timestamp}{tag_part}.png"
            filepath = self.dir / filename

            page.screenshot(path=str(filepath), full_page=False)
            logger.info(f"📸 截图已保存: {filepath} (tag={tag})")
            return str(filepath)
        except Exception as e:
            logger.warning(f"截图失败 (tag={tag}): {e}")
            return ""

    def capture_full(self, page: Page, tag: str = "") -> str:
        """截取整页截图（包括滚动区域）。"""
        if not self.enabled:
            return ""

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            tag_part = f"_{tag}" if tag else ""
            filename = f"{timestamp}{tag_part}_full.png"
            filepath = self.dir / filename

            page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"📸 整页截图已保存: {filepath} (tag={tag})")
            return str(filepath)
        except Exception as e:
            logger.warning(f"整页截图失败 (tag={tag}): {e}")
            return ""

    def capture_with_html(self, page: Page, tag: str = "") -> str:
        """
        截图并保存对应 HTML 快照（便于排查选择器问题）。
        """
        screenshot_path = self.capture(page, tag)

        if not self.enabled:
            return screenshot_path

        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            tag_part = f"_{tag}" if tag else ""
            html_path = self.dir / f"{timestamp}{tag_part}.html"
            html_content = page.content()
            html_path.write_text(html_content, encoding="utf-8")
            logger.debug(f"HTML 快照已保存: {html_path}")
        except Exception as e:
            logger.warning(f"HTML 快照保存失败: {e}")

        return screenshot_path
