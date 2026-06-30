"""
选择器多级回退查找工具。
依次尝试选择器列表，返回第一个匹配到的元素。
"""
from playwright.sync_api import Page
from loguru import logger


def try_selectors(page: Page, selectors: list, timeout: int = 5000):
    """
    依次尝试选择器列表，返回第一个匹配到的元素。
    所有选择器都失败时返回 None。
    """
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout, state="visible")
            if el:
                logger.debug(f"选择器命中: {sel}")
                return el
        except Exception:
            continue
    logger.warning(f"所有选择器均未命中: {selectors[:2]}...")
    return None


def try_click(page: Page, selectors: list, timeout: int = 5000) -> bool:
    """依次尝试点击选择器列表，成功返回 True。"""
    for sel in selectors:
        try:
            page.click(sel, timeout=timeout)
            logger.debug(f"点击成功: {sel}")
            return True
        except Exception:
            continue
    logger.warning(f"所有点击选择器均未命中: {selectors[:2]}...")
    return False


def try_query_all(page: Page, selectors: list) -> list:
    """
    依次尝试选择器列表，返回第一个命中的所有元素。
    """
    for sel in selectors:
        try:
            items = page.query_selector_all(sel)
            if items and len(items) > 0:
                logger.debug(f"查询到 {len(items)} 个元素: {sel}")
                return items
        except Exception:
            continue
    logger.warning(f"所有查询选择器均未命中: {selectors[:2]}...")
    return []


def try_inner_text(page: Page, selectors: list, timeout: int = 3000) -> str:
    """依次尝试选择器，返回第一个命中元素的 inner_text。"""
    el = try_selectors(page, selectors, timeout=timeout)
    if el:
        return el.inner_text().strip()
    return ""
