"""
登录脚本：自动登录 OWA 并保存 state.json。

流程：
1. 优先使用自动登录（账号密码）
2. 自动登录失败或检测到 MFA → 回退人工模式
3. 保存登录状态到 state/owa_state.json

运行方式：python login.py
"""
import sys
from pathlib import Path
from loguru import logger
from config.loader import Config
from utils.logger_setup import setup_logger
from browser.context_manager import BrowserManager
from browser.auth_checker import AuthChecker
from browser.auto_login import AutoLogin, LoginResult
from browser.popup_handler import dismiss_all_popups
from browser.screenshot import ScreenshotMonitor


def perform_login() -> bool:
    """
    执行登录流程，成功返回 True。
    优先自动登录，失败回退人工。
    """
    cfg = Config()
    owa_cfg = cfg.get("owa")
    browser_cfg = cfg.get("browser")

    owa_url = owa_cfg["url"]
    state_file = owa_cfg["state_file"]
    creds_cfg = owa_cfg.get("credentials", {}) or {}

    # 确保状态目录存在
    Path(state_file).parent.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 50)
    logger.info("  OWA 邮箱登录工具")
    logger.info(f"  目标: {owa_url}")
    logger.info(f"  状态文件: {state_file}")
    logger.info("=" * 50)

    bm = BrowserManager()
    try:
        bm.start()

        # 创建无状态的新上下文
        context = bm._browser.new_context(
            viewport=browser_cfg.get("viewport"),
        )
        from browser.stealth import apply_stealth
        apply_stealth(context)

        page = context.new_page()

        # ===== 判断登录模式 =====
        auto_enabled = creds_cfg.get("enabled", False)
        has_creds = AutoLogin.has_credentials(creds_cfg)

        if auto_enabled and has_creds:
            logger.info("已启用自动登录模式")
            result = _do_auto_login(page, owa_url, creds_cfg)

            if result == LoginResult.SUCCESS:
                # 保存状态
                bm.save_state(context, state_file)
                logger.info(f"✅ 自动登录成功，状态已保存: {state_file}")
                context.close()
                return True

            elif result == LoginResult.MFA_REQUIRED:
                # MFA 已在自动登录过程中人工处理完成，再次验证
                if AuthChecker.is_logged_in(page):
                    bm.save_state(context, state_file)
                    logger.info(f"✅ MFA 验证完成，状态已保存: {state_file}")
                    context.close()
                    return True
                else:
                    logger.warning("MFA 处理后仍未登录，回退人工模式")
                    if _do_manual_login(page):
                        bm.save_state(context, state_file)
                        logger.info(f"✅ 人工登录完成，状态已保存: {state_file}")
                        context.close()
                        return True

            else:
                # FAILED / TIMEOUT / CREDENTIAL_MISSING
                logger.warning(f"自动登录未成功（{result.value}），回退人工模式")
                if _do_manual_login(page):
                    bm.save_state(context, state_file)
                    logger.info(f"✅ 人工登录完成，状态已保存: {state_file}")
                    context.close()
                    return True
        else:
            # 未启用自动登录或无凭据，直接人工
            if not auto_enabled:
                logger.info("未启用自动登录（owa.credentials.enabled=false），使用人工模式")
            else:
                logger.warning("未配置 OWA 账号/密码（OWA_USERNAME / OWA_PASSWORD），使用人工模式")
            if _do_manual_login(page):
                bm.save_state(context, state_file)
                logger.info(f"✅ 登录完成，状态已保存: {state_file}")
                context.close()
                return True

        logger.error("❌ 登录失败")
        context.close()
        return False

    finally:
        bm.stop()


def _do_auto_login(page, owa_url: str, creds_cfg: dict) -> LoginResult:
    """执行自动登录。"""
    try:
        auto_login = AutoLogin(page, creds_cfg)
        return auto_login.login(owa_url)
    except Exception as e:
        logger.error(f"自动登录异常: {e}")
        return LoginResult.FAILED


def _do_manual_login(page) -> bool:
    """人工登录模式：等待用户在浏览器中完成登录。"""
    screenshot = ScreenshotMonitor()
    logger.info("")
    logger.info(">>> 请在浏览器中完成登录 <<<")
    logger.info(">>> 包括：输入用户名、密码、二次验证等 <<<")
    logger.info(">>> 登录成功后，确认收件箱页面完全加载 <<<")
    logger.info(">>> 然后回到终端按 Enter 保存状态")
    logger.info("")

    try:
        input("\n>>> 登录完成后按 Enter 保存状态 <<<\n")
    except (EOFError, KeyboardInterrupt):
        return False

    # 登录前截图
    screenshot.capture(page, "manual_login_before_check")

    if not AuthChecker.is_logged_in(page):
        logger.error("登录状态验证失败！请确认已成功登录后重试")
        # 截图记录验证失败的页面
        screenshot.capture(page, "manual_login_check_failed")
        return False
    logger.info("登录态校验通过")
    # 人工登录后自动关闭弹窗（存储警告等）
    dismiss_all_popups(page)
    # 关闭弹窗后截图
    screenshot.capture(page, "manual_login_after_popup")
    return True


def main():
    setup_logger()
    success = perform_login()
    if success:
        logger.info("现在可以运行 python main.py 启动监控服务")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
