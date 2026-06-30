"""
新邮件实时检测：多种策略组合，实现第一时间发现新邮件。

策略优先级：
1. WebSocket 长连接监听（OWA 原生推送，毫秒级）
2. 页面 DOM 变化监听（MutationObserver，秒级）
3. 未读数轮询（兜底，5 秒级）
"""
import re
import time
import json
from loguru import logger
from playwright.sync_api import Page
from browser.selectors import OWASelectors as S


class NewMailDetector:
    """
    新邮件检测器。
    组合三种策略，确保第一时间发现新邮件。
    """

    def __init__(self, page: Page):
        self.page = page
        self._last_unread_count = None
        self._last_check_time = 0
        self._observer_installed = False
        self._ws_listener_installed = False
        self._new_mail_flag = False  # DOM observer 设置的标志

    def install_realtime_listeners(self):
        """
        安装实时监听器（启动时调用一次）。
        1. MutationObserver 监听邮件列表 DOM 变化
        2. 拦截 OWA 的 WebSocket / fetch 请求
        """
        self._install_dom_observer()
        self._install_network_listener()

    def has_new_mail(self) -> bool:
        """
        快速检测是否有新邮件。
        :return: True=有新邮件，False=无变化
        """
        # 策略 1：检查 DOM observer 标志（最快，毫秒级）
        if self._new_mail_flag:
            self._new_mail_flag = False
            logger.info("🔔 DOM 变化检测到新邮件")
            return True

        # 策略 2：检查未读数变化（兜底，5 秒级）
        current_count = self._get_unread_count()

        if current_count is None:
            logger.debug("无法获取未读数，触发完整检查")
            return True

        if self._last_unread_count is None:
            self._last_unread_count = current_count
            logger.info(f"首次记录未读数: {current_count}")
            return True

        if current_count > self._last_unread_count:
            logger.info(
                f"🔔 检测到新邮件！未读数: {self._last_unread_count} → {current_count}"
            )
            self._last_unread_count = current_count
            return True

        if current_count != self._last_unread_count:
            self._last_unread_count = current_count

        return False

    def _install_dom_observer(self):
        """安装 MutationObserver 监听邮件列表变化。"""
        if self._observer_installed:
            return

        try:
            # 注入 MutationObserver，监听邮件列表区域的新增节点
            self.page.evaluate(
                """
                () => {
                    // 标记，供 Python 端检查
                    window.__newMailDetected = false;

                    const findMailList = () => {
                        // 尝试多种选择器找到邮件列表
                        const selectors = [
                            'div[role="listbox"]',
                            'div[aria-label*="邮件"]',
                            'div[aria-label*="Message"]',
                            'div[class*="MailList"]',
                            'div[class*="mailList"]',
                        ];
                        for (const sel of selectors) {
                            const el = document.querySelector(sel);
                            if (el && el.children.length > 0) return el;
                        }
                        return null;
                    };

                    const setupObserver = () => {
                        const mailList = findMailList();
                        if (!mailList) {
                            // 列表还没渲染，500ms 后重试
                            setTimeout(setupObserver, 500);
                            return;
                        }

                        const observer = new MutationObserver((mutations) => {
                            for (const mutation of mutations) {
                                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                                    // 有新节点添加，可能是新邮件
                                    // 检查新增的节点是否是邮件项
                                    for (const node of mutation.addedNodes) {
                                        if (node.nodeType === 1) {  // Element
                                            const role = node.getAttribute && node.getAttribute('role');
                                            const cls = (node.className || '').toString();
                                            // 邮件项通常是 role=option 或有 data-convid
                                            if (role === 'option' ||
                                                cls.includes('MailItem') ||
                                                cls.includes('mailItem') ||
                                                node.hasAttribute && node.hasAttribute('data-convid')) {
                                                window.__newMailDetected = true;
                                                break;
                                            }
                                        }
                                    }
                                }
                            }
                        });

                        observer.observe(mailList, {
                            childList: true,
                            subtree: true
                        });

                        console.log('[NewMailDetector] MutationObserver 已安装');
                    };

                    setupObserver();
                }
                """
            )
            self._observer_installed = True
            logger.info("DOM MutationObserver 已安装，实时监听邮件列表变化")
        except Exception as e:
            logger.warning(f"安装 DOM observer 失败（不影响功能，退化为轮询）: {e}")

    def _install_network_listener(self):
        """拦截 OWA 的网络请求，监听新邮件通知。"""
        if self._ws_listener_installed:
            return

        try:
            # 监听 WebSocket 消息（OWA 用 WS 推送新邮件通知）
            self.page.on("websocket", self._on_websocket)
            logger.info("WebSocket 监听器已安装，等待 OWA 推送连接")
            self._ws_listener_installed = True
        except Exception as e:
            logger.debug(f"安装 WebSocket 监听器失败: {e}")

    def _on_websocket(self, ws):
        """WebSocket 连接建立时的回调。"""
        try:
            ws.on("framereceived", lambda payload: self._on_ws_frame(payload))
            logger.info("已绑定 WebSocket 帧监听")
        except Exception as e:
            logger.debug(f"绑定 WebSocket 帧监听失败: {e}")

    def _on_ws_frame(self, payload):
        """收到 WebSocket 帧时的回调。"""
        try:
            # OWA 通过 WS 推送新邮件通知，帧内容可能包含 "NewMail" / "new mail" 等
            data = payload
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="ignore")

            data_str = str(data).lower()
            if any(kw in data_str for kw in ["newmail", "new_mail", "newmailnotification",
                                              "itemadded", "item_added", "inboxchanged"]):
                self._new_mail_flag = True
                logger.info("🔔 WebSocket 推送检测到新邮件！")
        except Exception:
            pass

    def check_dom_flag(self):
        """检查 DOM observer 设置的新邮件标志。"""
        if not self._observer_installed:
            return

        try:
            flag = self.page.evaluate("() => window.__newMailDetected || false")
            if flag:
                self._new_mail_flag = True
                # 重置标志
                self.page.evaluate("() => { window.__newMailDetected = false; }")
        except Exception:
            pass

    def _get_unread_count(self):
        """获取当前未读邮件数（兜底策略）。"""
        # 策略 1：从未读数元素获取
        for sel in S.UNREAD_COUNT:
            try:
                el = self.page.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    num_match = re.search(r'(\d+)', text)
                    if num_match:
                        count = int(num_match.group(1))
                        return count
            except Exception:
                continue

        # 策略 2：从收件箱 aria-label 提取
        try:
            inbox_el = self.page.query_selector(
                'div[role="treeitem"][aria-label*="收件箱"], '
                'div[role="treeitem"][aria-label*="Inbox" i]'
            )
            if inbox_el:
                aria = inbox_el.get_attribute("aria-label") or ""
                num_match = re.search(r'(\d+)', aria)
                if num_match:
                    return int(num_match.group(1))
        except Exception:
            pass

        # 策略 3：统计列表中未读邮件
        try:
            unread_items = self.page.query_selector_all(
                'div[role="option"][aria-label*="未读"], '
                'div[role="option"][class*="unread" i], '
                'div[data-convid][class*="unread" i]'
            )
            if unread_items:
                return len(unread_items)
        except Exception:
            pass

        return None

    def reset(self):
        """重置状态。"""
        self._last_unread_count = None
        self._new_mail_flag = False
