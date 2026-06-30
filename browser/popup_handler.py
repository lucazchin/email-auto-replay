"""
OWA 弹窗自动处理：检测并关闭运行时弹窗（存储警告、提示等）。

改进：
- 放宽弹窗检测：不强制要求 role="dialog"，根据文本内容识别
- 增加截图记录：关闭弹窗前后各截一张，便于调试
- 多轮扫描：连续关闭多个弹窗
"""
from loguru import logger
from playwright.sync_api import Page
from browser.selectors import OWASelectors as S


def dismiss_all_popups(page: Page, max_rounds: int = 3) -> int:
    """
    检测并关闭页面上所有已知类型的 OWA 弹窗/提示。
    多轮扫描，因为关一个弹窗可能弹出下一个。
    :param page: Playwright Page 实例
    :param max_rounds: 最大扫描轮数
    :return: 关闭的弹窗总数
    """
    total_dismissed = 0

    for round_idx in range(max_rounds):
        dismissed_this_round = 0

        # 1. 存储容量警告弹窗
        if _dismiss_popup_by_text(page, S.STORAGE_WARNING_POPUP, S.POPUP_CONFIRM_BUTTON,
                                   "存储警告"):
            dismissed_this_round += 1

        # 2. 通用确认弹窗（"确定/OK/关闭" 按钮）
        if _dismiss_generic_popup(page):
            dismissed_this_round += 1

        # 3. 任何可见的对话框
        if _dismiss_any_dialog(page):
            dismissed_this_round += 1

        if dismissed_this_round == 0:
            break

        total_dismissed += dismissed_this_round
        page.wait_for_timeout(800)  # 等待弹窗动画完成

    if total_dismissed > 0:
        logger.info(f"共自动关闭 {total_dismissed} 个弹窗")
    else:
        logger.debug("未检测到弹窗")

    return total_dismissed


def _dismiss_popup_by_text(page: Page, popup_selectors: list, button_selectors: list,
                            name: str) -> bool:
    """根据弹窗文本特征检测并关闭。"""
    popup_found = False
    for sel in popup_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                popup_found = True
                logger.info(f"检测到 {name} 弹窗: {sel}")
                break
        except Exception:
            continue

    if not popup_found:
        return False

    # 截图记录弹窗出现
    _screenshot(page, f"popup_{name}_before")

    # 尝试点击确认按钮
    for sel in button_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
                logger.info(f"已点击 {name} 弹窗的确认按钮: {sel}")
                _screenshot(page, f"popup_{name}_after")
                return True
        except Exception:
            continue

    logger.warning(f"{name} 弹窗未找到可点击的确认按钮")
    return False


def _dismiss_generic_popup(page: Page) -> bool:
    """
    关闭通用确认弹窗。
    策略：查找任何可见的"确定/OK/关闭"按钮，且按钮在某个浮层内。
    """
    for sel in S.POPUP_CONFIRM_BUTTON:
        try:
            btn = page.query_selector(sel)
            if not btn or not btn.is_visible():
                continue

            # 检查按钮是否在浮层内（dialog/modal/popup/overlay）
            in_overlay = btn.evaluate(
                """(el) => {
                    let node = el.parentElement;
                    while (node && node !== document.body) {
                        const role = (node.getAttribute('role') || '').toLowerCase();
                        const cls = (node.className || '').toString().toLowerCase();
                        const id = (node.id || '').toLowerCase();
                        if (
                            role === 'dialog' ||
                            role === 'alertdialog' ||
                            role === 'alert' ||
                            cls.includes('dialog') ||
                            cls.includes('modal') ||
                            cls.includes('popup') ||
                            cls.includes('overlay') ||
                            cls.includes('layer') ||
                            id.includes('dialog') ||
                            id.includes('popup')
                        ) {
                            return true;
                        }
                        node = node.parentElement;
                    }
                    return false;
                }"""
            )
            if in_overlay:
                btn.click()
                page.wait_for_timeout(500)
                logger.info(f"已关闭通用弹窗: {sel}")
                return True
        except Exception:
            continue
    return False


def _dismiss_any_dialog(page: Page) -> bool:
    """
    最后兜底：查找任何 role=dialog 的可见元素，尝试关闭。
    """
    try:
        dialogs = page.query_selector_all(
            '[role="dialog"], [role="alertdialog"], [role="alert"]'
        )
        for dlg in dialogs:
            try:
                if not dlg.is_visible():
                    continue
                # 在对话框内找确认按钮
                for sel in S.POPUP_CONFIRM_BUTTON:
                    try:
                        btn = dlg.query_selector(sel)
                        if btn and btn.is_visible():
                            btn.click()
                            page.wait_for_timeout(500)
                            logger.info(f"已关闭对话框内的按钮: {sel}")
                            return True
                    except Exception:
                        continue

                # 没找到按钮，尝试按 Escape 关闭
                dlg.click()
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                logger.info("已通过 Escape 关闭对话框")
                return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _screenshot(page: Page, tag: str):
    """截图记录。"""
    try:
        from browser.screenshot import ScreenshotMonitor
        ScreenshotMonitor().capture(page, tag)
    except Exception as e:
        logger.debug(f"截图失败: {e}")
