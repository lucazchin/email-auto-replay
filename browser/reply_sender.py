"""
回复发送器：处理 OWA 的回复输入和发送。

OWA 回复流程（右键菜单方式）：
1. 右键点击邮件列表中的邮件 → 弹出上下文菜单
2. 点击菜单中的「答复」选项 → 打开回复编辑器
3. 输入回复内容
4. 点击「发送」

关键点：
- OWA 没有明显的回复按钮，需要右键邮件弹出菜单
- 回复框是 contenteditable div，不能用 fill()
"""
import time
from loguru import logger
from playwright.sync_api import Page
from browser.selectors import OWASelectors as S
from browser.selector_helper import try_click, try_selectors


class ReplySender:
    """管理 OWA 回复发送流程。"""

    def __init__(self, page: Page):
        self.page = page

    def send(self, reply_content: str, mail_item=None):
        """
        完整的回复发送流程：
        1. 右键点击邮件 → 弹出上下文菜单
        2. 点击菜单中的「答复」→ 打开编辑器
        3. 等待回复编辑器加载
        4. 输入回复内容
        5. 验证内容已输入
        6. 点击「发送」
        7. 验证发送成功

        :param reply_content: AI 生成的回复内容
        :param mail_item: 邮件列表元素（已打开的邮件），可选
        """
        # 1. 右键点击邮件弹出菜单
        logger.info("步骤1: 右键点击邮件弹出菜单")
        if not self._open_context_menu(mail_item):
            # 右键菜单失败，尝试用键盘快捷键打开
            logger.warning("右键菜单失败，尝试键盘方式")
            if not self._open_menu_via_keyboard():
                raise RuntimeError("无法打开回复菜单")

        self.page.wait_for_timeout(1500)

        # 2. 点击菜单中的「全部答复」
        logger.info("步骤2: 点击菜单中的「全部答复」")
        if not self._click_reply_option():
            self._screenshot("reply_menu_not_found")
            raise RuntimeError("无法找到全部答菜单项")
        self.page.wait_for_timeout(2000)

        # 3. 定位回复输入框
        logger.info("步骤3: 定位回复输入框")
        input_el = try_selectors(self.page, S.REPLY_INPUT, timeout=10000)
        if not input_el:
            self._screenshot("reply_input_not_found")
            raise RuntimeError("无法找到回复输入框")
        self.page.wait_for_timeout(500)

        # 4. 输入回复内容
        logger.info(f"步骤4: 输入回复内容 ({len(reply_content)} 字符)")
        self._input_content(input_el, reply_content)

        # 5. 验证内容已输入
        self.page.wait_for_timeout(500)
        if not self._verify_content(input_el, reply_content):
            logger.warning("回复内容验证失败，尝试重新输入")
            self._input_content(input_el, reply_content)

        # 6. 点击发送
        logger.info("步骤5: 点击「发送」按钮")
        if not try_click(self.page, S.SEND_BUTTON, timeout=10000):
            raise RuntimeError("无法找到发送按钮")

        # 7. 等待发送完成
        self.page.wait_for_timeout(3000)

        # 8. 验证发送成功
        if self._verify_sent():
            logger.info("回复发送成功")
        else:
            logger.warning("发送状态不确定，请人工确认")

    def _open_context_menu(self, mail_item=None) -> bool:
        """
        右键点击邮件弹出上下文菜单。
        :param mail_item: 邮件元素，如果为 None 则尝试找当前选中的邮件
        :return: 成功返回 True
        """
        try:
            if mail_item is not None:
                # 直接右键指定元素
                mail_item.click(button="right")
                self.page.wait_for_timeout(1000)
                return True

            # 没有传入元素，尝试找当前打开/选中的邮件
            # OWA 打开邮件后，邮件列表中对应项会高亮
            for sel in S.MAIL_ITEM:
                try:
                    items = self.page.query_selector_all(sel)
                    if not items:
                        continue
                    # 找选中的邮件（aria-selected=true 或 class 含 selected）
                    for item in items:
                        try:
                            is_selected = item.get_attribute("aria-selected")
                            cls = (item.get_attribute("class") or "").lower()
                            if is_selected == "true" or "selected" in cls:
                                item.click(button="right")
                                self.page.wait_for_timeout(1000)
                                logger.info(f"右键点击选中邮件成功: {sel}")
                                return True
                        except Exception:
                            continue

                    # 没找到选中的，右键第一个邮件项
                    items[0].click(button="right")
                    self.page.wait_for_timeout(1000)
                    logger.info(f"右键点击第一个邮件成功: {sel}")
                    return True
                except Exception:
                    continue

            logger.warning("未找到邮件列表项")
            return False
        except Exception as e:
            logger.error(f"右键点击邮件失败: {e}")
            return False

    def _open_menu_via_keyboard(self) -> bool:
        """
        键盘方式打开菜单（Shift+F10 或 Menu 键）。
        适用于已选中邮件但右键失败的情况。
        """
        try:
            # 先确保邮件列表有焦点
            for sel in S.MAIL_ITEM:
                try:
                    items = self.page.query_selector_all(sel)
                    if items:
                        items[0].click()
                        self.page.wait_for_timeout(300)
                        break
                except Exception:
                    continue

            # Shift+F10 模拟右键菜单键
            self.page.keyboard.press("Shift+F10")
            self.page.wait_for_timeout(1000)
            return True
        except Exception as e:
            logger.error(f"键盘打开菜单失败: {e}")
            return False

    def _click_reply_option(self) -> bool:
        """
        在右键菜单中点击「全部答复」。
        OWA 右键菜单项可能是：
        - 答复 / Reply
        - 全部答复 / Reply All  ← 优先点击这个
        - 转发 / Forward
        - 删除 / Delete
        等
        """
        # 优先点击「全部答复」
        if try_click(self.page, S.REPLY_ALL_OPTION, timeout=5000):
            logger.info("已点击「全部答复」")
            return True

        # 备用：尝试「答复」
        logger.warning("未找到「全部答复」，尝试「答复」")
        if try_click(self.page, S.REPLY_REPLY_OPTION, timeout=3000):
            logger.info("已点击「答复」")
            return True

        # 最后尝试：通过文本查找菜单项
        try:
            menu_items = self.page.query_selector_all(
                '[role="menuitem"], [role="menuitemradio"], '
                'li[role="menuitem"], div[class*="MenuItem"]'
            )
            for item in menu_items:
                try:
                    text = item.inner_text().strip().lower()
                    # 优先匹配"全部答复"
                    if text in ("全部答复", "reply all", "replyall"):
                        item.click()
                        self.page.wait_for_timeout(500)
                        logger.info(f"通过文本点击菜单项: {text}")
                        return True
                except Exception:
                    continue
            # 再找"答复"
            for item in menu_items:
                try:
                    text = item.inner_text().strip().lower()
                    if text in ("答复", "reply"):
                        item.click()
                        self.page.wait_for_timeout(500)
                        logger.info(f"通过文本点击菜单项: {text}")
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        return False

    def _input_content(self, element, content: str):
        """向 contenteditable 元素输入内容。"""
        element.click()
        self.page.wait_for_timeout(300)

        # 清空已有内容
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
        self.page.wait_for_timeout(200)

        if len(content) <= 2000:
            self.page.keyboard.type(content, delay=10)
        else:
            self._set_content_via_evaluate(element, content)

    def _set_content_via_evaluate(self, element, content: str):
        """通过 JavaScript 设置 contenteditable 内容。"""
        try:
            html_content = content.replace("\n", "<br>")
            element.evaluate(
                """(el, html) => {
                    el.innerHTML = html;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                html_content
            )
            logger.info("通过 evaluate 设置回复内容完成")
        except Exception as e:
            logger.error(f"evaluate 设置内容失败: {e}，回退到逐字输入")
            self.page.keyboard.type(content, delay=5)

    def _verify_content(self, element, expected: str) -> bool:
        """验证回复内容是否成功输入。"""
        try:
            actual = element.inner_text()
            if expected[:50] in actual:
                return True
            logger.warning(f"内容验证不匹配，期望前50字符: {expected[:50]}")
            return False
        except Exception:
            return False

    def _verify_sent(self) -> bool:
        """验证邮件是否发送成功。"""
        try:
            el = self.page.query_selector(S.REPLY_INPUT[0])
            if el is None:
                return True
            return False
        except Exception:
            return True

    def _screenshot(self, tag: str):
        """截图记录。"""
        try:
            from browser.screenshot import ScreenshotMonitor
            ScreenshotMonitor().capture(self.page, tag)
        except Exception:
            pass
